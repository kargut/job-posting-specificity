#!/usr/bin/env python3
"""
Greenhouse Job Board API client.

Fetches published jobs from public boards (no auth required for GET).
API: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

Usage:
  python src/fetchers/greenhouse.py --boards stripe,datadog          # whole boards
  python src/fetchers/greenhouse.py --boards stripe:80,veriff        # per-board caps
  python src/fetchers/greenhouse.py --boards stripe --limit 50       # default cap

Per-board amounts, not one flat cap. Boards differ by an order of magnitude (9
jobs to 240+), and a shared cap silently reshapes the corpus.

IMPORTANT — why the default is now "fetch everything": the Greenhouse API returns
a board's full job list in one response, in its own order, which is close to
alphabetical by title. The old `jobs[:limit]` therefore took an ALPHABETICAL
slice, not a sample. Measured on the first corpus: all 45 postings fetched from
one board had titles starting with "A", as did all 10 from another. That produced
a corpus of Account Executives and made two boards look as though they had no
engineering roles at all. When a cap is applied now, jobs are sampled with a
seeded RNG instead of truncated.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
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


def fetch_from_greenhouse(board_token: str) -> list[dict]:
    """Fetch every published job from a public Greenhouse board.

    Returns the full list. Capping is a separate, explicit step (see
    `sample_jobs`) so that the bias is visible rather than baked in here.
    """
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

    return data.get("jobs") or []


def sample_jobs(jobs: list[dict], limit: int, seed: int, token: str) -> list[dict]:
    """Cap a board to `limit` jobs by seeded random sample, never by truncation.

    `limit <= 0` means no cap. The seed is mixed with the board token so each
    board samples independently but reproducibly.
    """
    if limit <= 0 or len(jobs) <= limit:
        return jobs
    rng = random.Random(f"{seed}:{token}")
    picked = rng.sample(range(len(jobs)), limit)
    return [jobs[i] for i in sorted(picked)]


def parse_board_spec(spec: str) -> tuple[str, int | None]:
    """'stripe:80' -> ('stripe', 80);  'stripe' -> ('stripe', None)."""
    if ":" in spec:
        token, _, raw = spec.partition(":")
        token = token.strip()
        try:
            return token, max(0, int(raw.strip()))
        except ValueError:
            print(f"Warning: bad limit in {spec!r}, using the default cap",
                  file=sys.stderr)
            return token, None
    return spec.strip(), None


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
    """Merge postings into the corpus JSONL.

    Two levels of deduplication, because content_hash alone is not enough:

    * `content_hash` catches the same text arriving twice (e.g. the same job
      cross-posted, or a board re-fetched unchanged).
    * `id` catches the same job re-fetched AFTER the employer edited it. The text
      differs, so the hash differs, and an append-only writer keeps both — the
      first corpus ended up with three jobs stored twice, revisions 3 days apart
      with 0.987-1.000 body similarity. On an id collision the NEWER `fetched_at`
      wins and the older row is dropped, so the corpus holds one row per job.

    Returns the number of postings added or refreshed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_file = output_dir / "raw_postings.jsonl"

    by_id: dict[str, dict] = {}
    order: list[str] = []
    hashes: dict[str, str] = {}  # content_hash -> id that owns it

    if corpus_file.exists():
        with corpus_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    job = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid = job.get("id")
                if not pid:
                    continue
                if pid not in by_id:
                    order.append(pid)
                elif (job.get("fetched_at") or "") <= (
                    by_id[pid].get("fetched_at") or ""
                ):
                    continue  # keep the newer row already held
                by_id[pid] = job
                if job.get("content_hash"):
                    hashes[job["content_hash"]] = pid

    changed = 0
    for posting in postings:
        if not posting.get("content"):
            continue  # list endpoint without content, or a blank post
        pid = posting.get("id")
        if not pid:
            continue
        h = posting.get("content_hash")

        if pid in by_id:
            old_at = by_id[pid].get("fetched_at") or ""
            if (posting.get("fetched_at") or "") <= old_at:
                continue
            if by_id[pid].get("content_hash") == h:
                continue  # same job, same text: nothing to refresh
            old_hash = by_id[pid].get("content_hash")
            if old_hash in hashes and hashes[old_hash] == pid:
                del hashes[old_hash]
            by_id[pid] = posting
            if h:
                hashes[h] = pid
            changed += 1
            continue

        if h in hashes:
            continue  # identical text already in the corpus under another id
        by_id[pid] = posting
        order.append(pid)
        if h:
            hashes[h] = pid
        changed += 1

    tmp = corpus_file.with_suffix(corpus_file.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for pid in order:
            if pid in by_id:
                f.write(json.dumps(by_id[pid], ensure_ascii=False) + "\n")
    os.replace(tmp, corpus_file)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch jobs from Greenhouse public boards. "
            "No API key required for listing jobs."
        )
    )
    parser.add_argument(
        "--boards",
        help="Comma-separated board tokens, each optionally with its own cap: "
        "stripe:80,datadog:80,veriff. A token with no cap uses --limit. "
        "If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Default cap per board for tokens with no explicit cap. "
        "0 (the default) means fetch the whole board.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed for per-board sampling when a cap applies (default: 7)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Output directory (default: data/raw)",
    )
    args = parser.parse_args()

    if args.boards:
        specs = [parse_board_spec(t) for t in args.boards.split(",") if t.strip()]
    else:
        specs = [(t, None) for t in prompt_board_tokens()]
    tokens = [t for t, _ in specs]

    if not tokens:
        print("Error: at least one board token is required.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output_dir)
    print(f"Fetching from {len(tokens)} Greenhouse board(s)...")
    total_new = 0

    for token, board_limit in specs:
        print(f"  {token}...", end=" ", flush=True)
        all_jobs = fetch_from_greenhouse(token)
        if not all_jobs:
            print("0 jobs")
            continue
        cap = args.limit if board_limit is None else board_limit
        raw_jobs = sample_jobs(all_jobs, cap, args.seed, token)
        how = (
            "all"
            if len(raw_jobs) == len(all_jobs)
            else f"{len(raw_jobs)} sampled"
        )
        normalized = [
            normalize_posting(job, f"greenhouse_{token}") for job in raw_jobs
        ]
        saved = save_batch(normalized, output_path)
        total_new += saved
        print(f"{len(all_jobs)} on board, {how}, {saved} new/updated")

    print(f"\nTotal postings added or refreshed: {total_new}")
    print(f"Stored in: {output_path / 'raw_postings.jsonl'}")


if __name__ == "__main__":
    main()
