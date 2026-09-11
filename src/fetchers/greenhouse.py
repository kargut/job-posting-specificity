#!/usr/bin/env python3
"""
Greenhouse Job Board API client.

Fetches published jobs from public boards (no auth required for GET).
API: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

Usage:
  python src/fetchers/greenhouse.py --boards stripe,airbnb --limit 50
  python src/fetchers/greenhouse.py --limit 100   # prompts for board tokens
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GREENHOUSE_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

# Common public boards useful for a software-focused corpus (override with --boards).
DEFAULT_EXAMPLE_BOARDS = ("stripe", "datadog", "cloudflare", "shopify", "github")


class _HTMLToText(HTMLParser):
    """Minimal HTML → plain text converter."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style"}:
            self._skip = True
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")
        elif tag == "td":
            self._parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = html.unescape(raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(content: str) -> str:
    """Decode Greenhouse HTML entities and strip tags to plain text."""
    if not content:
        return ""
    # Greenhouse often double-encodes entities (&lt;p&gt;…); unescape twice.
    decoded = html.unescape(html.unescape(content))
    parser = _HTMLToText()
    try:
        parser.feed(decoded)
        parser.close()
        return parser.text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", decoded).strip()


def prompt_board_tokens() -> list[str]:
    """Ask for board tokens when --boards is not provided."""
    print(
        "Enter Greenhouse board tokens (comma-separated).\n"
        "Find them in careers URLs, e.g. "
        "https://boards.greenhouse.io/stripe → stripe\n"
        "Examples: " + ", ".join(DEFAULT_EXAMPLE_BOARDS)
    )
    raw = input("Board tokens: ").strip()
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens:
        print("Error: at least one board token is required.", file=sys.stderr)
        sys.exit(1)
    return tokens


def fetch_from_greenhouse(board_token: str, limit: int = 100) -> list[dict]:
    """Fetch jobs from a public Greenhouse board (all jobs, then truncate)."""
    params = urlencode({"content": "true"})
    url = GREENHOUSE_JOBS_URL.format(board_token=board_token) + f"?{params}"
    req = Request(url, headers={"User-Agent": "job-posting-specificity/1.0"})

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            print(
                f"Board '{board_token}' not found (404). "
                "Check the token in https://boards.greenhouse.io/{{token}}",
                file=sys.stderr,
            )
        else:
            print(f"HTTP {e.code} fetching {board_token}: {e}", file=sys.stderr)
        return []
    except URLError as e:
        print(f"Network error fetching {board_token}: {e}", file=sys.stderr)
        return []

    jobs = data.get("jobs") or []
    return jobs[:limit]


def _location_entries(job: dict) -> list[dict]:
    """Normalize location + offices into a list of {name, country}."""
    locations: list[dict] = []
    primary = (job.get("location") or {}).get("name")
    if primary:
        locations.append({"name": primary, "country": None})

    for office in job.get("offices") or []:
        name = office.get("name")
        # offices[].location is a string like "New York, NY, United States", not a dict
        office_loc = office.get("location")
        if isinstance(office_loc, dict):
            office_loc = office_loc.get("name")
        label = name or office_loc
        if not label:
            continue
        if any(loc["name"] == label for loc in locations):
            continue
        locations.append({"name": label, "country": None})

    return locations


def normalize_posting(job: dict, source: str) -> dict:
    """Map a Greenhouse job object to the canonical posting schema."""
    plain = html_to_text(job.get("content") or "")
    company = (job.get("company_name") or "").strip()
    title = (job.get("title") or "").strip()

    return {
        "id": f"{source}_{job.get('id', 'unknown')}",
        "source": source,
        "source_id": job.get("id"),
        "title": title,
        "company": company,
        "url": job.get("absolute_url") or "",
        "content": plain,
        "content_hash": hashlib.sha256(plain.encode("utf-8")).hexdigest()[:16],
        "departments": [
            d.get("name") for d in (job.get("departments") or []) if d.get("name")
        ],
        "locations": _location_entries(job),
        "posted_at": job.get("first_published") or job.get("updated_at") or "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def save_batch(postings: list[dict], output_dir: Path) -> int:
    """Append postings to JSONL, deduplicating by content_hash."""
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_file = output_dir / "raw_postings.jsonl"
    existing_hashes: set[str] = set()

    if corpus_file.exists():
        with corpus_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    job = json.loads(line)
                    h = job.get("content_hash")
                    if h:
                        existing_hashes.add(h)
                except json.JSONDecodeError:
                    continue

    saved = 0
    with corpus_file.open("a", encoding="utf-8") as f:
        for posting in postings:
            h = posting["content_hash"]
            if h in existing_hashes:
                continue
            # Skip empty descriptions (list endpoint without content, or blank posts)
            if not posting.get("content"):
                continue
            f.write(json.dumps(posting, ensure_ascii=False) + "\n")
            existing_hashes.add(h)
            saved += 1
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch jobs from Greenhouse public boards. "
            "No API key required for listing jobs."
        )
    )
    parser.add_argument(
        "--boards",
        help="Comma-separated board tokens (e.g. stripe,datadog). "
        "If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max jobs to keep per board (default: 100)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Output directory (default: data/raw)",
    )
    args = parser.parse_args()

    if args.boards:
        tokens = [t.strip() for t in args.boards.split(",") if t.strip()]
    else:
        tokens = prompt_board_tokens()

    if not tokens:
        print("Error: at least one board token is required.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output_dir)
    print(f"Fetching from {len(tokens)} Greenhouse board(s)...")
    total_new = 0

    for token in tokens:
        print(f"  {token}...", end=" ", flush=True)
        raw_jobs = fetch_from_greenhouse(token, limit=args.limit)
        if not raw_jobs:
            print("0 jobs")
            continue
        normalized = [
            normalize_posting(job, f"greenhouse_{token}") for job in raw_jobs
        ]
        saved = save_batch(normalized, output_path)
        total_new += saved
        print(f"{len(raw_jobs)} fetched, {saved} new")

    print(f"\nTotal new postings saved: {total_new}")
    print(f"Stored in: {output_path / 'raw_postings.jsonl'}")


if __name__ == "__main__":
    main()
