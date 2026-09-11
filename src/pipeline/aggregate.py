#!/usr/bin/env python3
"""
Stage 3: score postings and roll up aggregates.

Deterministic — no LLM required. Takes classified claims JSONL and writes:
  results/scores.jsonl
  results/aggregates.json
  results/summary.md

Usage:
  python src/pipeline/aggregate.py data/classified/claims.jsonl results/
  python src/pipeline/aggregate.py data/classified/claims.jsonl results/ \\
      --raw data/raw/raw_postings.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: skip {path}:{i}: {e}", file=sys.stderr)
    return rows


def claim_items(row: dict) -> list[dict]:
    return row.get("claims") or row.get("classifications") or []


def claim_tier(claim: dict) -> int | None:
    tier = claim.get("predicted_tier", claim.get("tier"))
    return int(tier) if tier in (1, 2, 3) else None


def infer_seniority(title: str, claim_texts: list[str]) -> str:
    blob = " ".join([title] + claim_texts).lower()
    if re.search(r"\b(principal|staff|lead|senior|sr\.?)\b", blob):
        return "senior"
    if re.search(r"\b(junior|jr\.?|graduate|intern|entry[- ]level)\b", blob):
        return "junior"
    if re.search(r"\b(mid[- ]level|intermediate)\b", blob):
        return "mid"
    if re.search(r"\b([5-9]\+|1[0-9]\+)\s*years?\b", blob):
        return "senior"
    if re.search(r"\b([0-2]|0–2|0-2)\s*\+?\s*years?\b", blob):
        return "junior"
    return "unspecified"


def infer_sector(title: str, departments: list[str]) -> str:
    blob = " ".join([title] + departments).lower()
    if re.search(r"\b(data|analytics|machine learning|ml|ai research)\b", blob):
        return "data"
    if re.search(r"\b(design|ux|ui|product designer)\b", blob):
        return "design"
    if re.search(r"\b(product manager|product owner)\b", blob):
        return "product"
    if re.search(
        r"\b(engineer|developer|software|backend|frontend|sre|devops|platform)\b",
        blob,
    ):
        return "software"
    return "other"


def infer_region(locations: list[dict]) -> str:
    names = " ".join((loc.get("name") or "") for loc in locations).lower()
    if re.search(r"\b(r[iī]ga|tallinn|vilnius|latvia|lithuania|estonia|baltics?)\b", names):
        return "baltics"
    if re.search(r"\bremote\b", names) and len(locations) <= 1:
        return "remote"
    if re.search(
        r"\b(berlin|amsterdam|paris|london|dublin|madrid|lisbon|stockholm|"
        r"helsinki|warsaw|prague|vienna|munich|europe|eu)\b",
        names,
    ):
        return "eu"
    if not names.strip():
        return "unknown"
    return "other"


def infer_company_size(claim_texts: list[str]) -> str:
    blob = " ".join(claim_texts).lower()
    m = re.search(r"\b(\d{1,5})[-\u2013–](\d{1,5})\s*(people|employees|person)\b", blob)
    if m:
        n = int(m.group(1))
    else:
        m = (
            re.search(r"\b(\d{1,5})[-\u2013–]person\b", blob)
            or re.search(r"\b(\d{1,5})\s*(people|employees)\b", blob)
            or re.search(r"\b(?:team|staff|company|startup)\s+of\s+(\d{1,5})\b", blob)
            or re.search(r"\b(\d{1,5})-person\b", blob)
        )
        n = int(m.group(1)) if m else None

    if n is None:
        return "unknown"
    if n <= 10:
        return "1-10"
    if n <= 50:
        return "10-50"
    if n <= 200:
        return "50-200"
    return "200+"


def score_posting(row: dict, raw_meta: dict | None = None) -> dict | None:
    items = claim_items(row)
    tiers = [t for t in (claim_tier(c) for c in items) if t is not None]
    if not tiers:
        return None

    t1 = sum(1 for t in tiers if t == 1)
    t2 = sum(1 for t in tiers if t == 2)
    t3 = sum(1 for t in tiers if t == 3)
    total = t1 + t2 + t3
    score = t1 / total if total else 0.0

    claim_texts = [c.get("text") or "" for c in items]
    meta = raw_meta or {}
    title = row.get("title") or meta.get("title") or ""
    company = row.get("company") or meta.get("company") or ""
    departments = meta.get("departments") or []
    locations = meta.get("locations") or []

    # Prefer explicit metadata on the classified row if present
    existing = row.get("metadata") or {}
    sector = existing.get("sector") or infer_sector(title, departments)
    seniority = existing.get("seniority") or infer_seniority(title, claim_texts)
    region = existing.get("region") or infer_region(locations)
    size = existing.get("company_size") or infer_company_size(claim_texts)

    primary_loc = None
    if locations:
        primary_loc = locations[0].get("name")
    primary_loc = existing.get("location_primary") or primary_loc

    return {
        "posting_id": row.get("posting_id") or meta.get("id"),
        "title": title,
        "company": company,
        "source": meta.get("source") or row.get("source"),
        "location_primary": primary_loc,
        "posted_at": (meta.get("posted_at") or "")[:10] or None,
        "total_claims": total,
        "tier_1_claims": t1,
        "tier_2_claims": t2,
        "tier_3_claims": t3,
        "specificity_score": round(score, 4),
        "sector": sector,
        "company_size": size,
        "seniority": seniority,
        "region": region,
    }


def percentiles(values: list[float]) -> dict:
    if not values:
        return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}
    qs = statistics.quantiles(values, n=10, method="inclusive") if len(values) >= 2 else [values[0]] * 9
    # quantiles n=10 → 9 cut points at 10%..90%
    def q(p: int) -> float:
        if len(values) == 1:
            return values[0]
        idx = {10: 0, 25: 1, 50: 4, 75: 6, 90: 8}[p]
        # For p25/p75 use n=4 quantiles when possible
        if p in (25, 50, 75) and len(values) >= 2:
            q4 = statistics.quantiles(values, n=4, method="inclusive")
            return {25: q4[0], 50: q4[1], 75: q4[2]}[p]
        return qs[idx]

    return {
        "p10": round(q(10), 4),
        "p25": round(q(25), 4),
        "p50": round(q(50), 4),
        "p75": round(q(75), 4),
        "p90": round(q(90), 4),
    }


def rollup(scores: list[dict], key: str) -> list[dict]:
    groups: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        groups[str(s.get(key) or "unknown")].append(s["specificity_score"])

    out = []
    for label, vals in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(
            {
                key if key != "company_size" else "size_bracket": label,
                "count": len(vals),
                "avg_specificity": round(statistics.mean(vals), 4),
                "median_specificity": round(statistics.median(vals), 4),
                "std_dev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
                "percentiles": percentiles(vals),
            }
        )
    return out


def summary_md(scores: list[dict], aggregates: dict) -> str:
    vals = [s["specificity_score"] for s in scores]
    lines = [
        "# Specificity Scores: Summary",
        "",
        "## Overall",
        f"- **Postings analyzed:** {len(scores)}",
        f"- **Average specificity:** {statistics.mean(vals):.2f}" if vals else "- **Average specificity:** —",
        f"- **Median specificity:** {statistics.median(vals):.2f}" if vals else "- **Median specificity:** —",
        f"- **Std. dev:** {statistics.pstdev(vals):.2f}" if len(vals) > 1 else "- **Std. dev:** —",
        f"- **Range:** {min(vals):.2f}–{max(vals):.2f}" if vals else "- **Range:** —",
        "",
    ]

    def table(title: str, rows: list[dict], label_key: str) -> None:
        lines.append(f"## {title}")
        lines.append(f"| {label_key} | Count | Avg | Median |")
        lines.append("|---|---:|---:|---:|")
        for r in rows:
            label = r.get(label_key) or r.get("size_bracket") or "?"
            lines.append(
                f"| {label} | {r['count']} | {r['avg_specificity']:.2f} | "
                f"{r['median_specificity']:.2f} |"
            )
        lines.append("")

    table("By Seniority", aggregates["by_seniority"], "seniority")
    table("By Region", aggregates["by_region"], "region")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate classified claims into specificity scores"
    )
    parser.add_argument(
        "classified",
        type=Path,
        help="Classified claims JSONL (or a directory containing claims.jsonl)",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory (usually results/)",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("data/raw/raw_postings.jsonl"),
        help="Optional raw postings JSONL for title/location metadata",
    )
    args = parser.parse_args()

    classified_path = args.classified
    if classified_path.is_dir():
        classified_path = classified_path / "claims.jsonl"

    if not classified_path.exists():
        print(f"Error: classified file not found: {classified_path}", file=sys.stderr)
        sys.exit(1)

    classified = load_jsonl(classified_path)
    raw_by_id = {
        str(r.get("id")): r for r in load_jsonl(args.raw) if r.get("id") is not None
    }

    scores: list[dict] = []
    skipped = 0
    for row in classified:
        pid = str(row.get("posting_id") or "")
        scored = score_posting(row, raw_by_id.get(pid))
        if scored is None:
            skipped += 1
            continue
        scores.append(scored)

    if not scores:
        print("Error: no scorable postings found.", file=sys.stderr)
        sys.exit(1)

    aggregates = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_size": len(scores),
        "by_sector": rollup(scores, "sector"),
        "by_size": rollup(scores, "company_size"),
        "by_seniority": rollup(scores, "seniority"),
        "by_region": rollup(scores, "region"),
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    scores_path = out / "scores.jsonl"
    with scores_path.open("w", encoding="utf-8") as f:
        for s in scores:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    agg_path = out / "aggregates.json"
    agg_path.write_text(json.dumps(aggregates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary_path = out / "summary.md"
    summary_path.write_text(summary_md(scores, aggregates), encoding="utf-8")

    print(f"Scored {len(scores)} postings ({skipped} skipped with 0 claims)")
    print(f"  {scores_path}")
    print(f"  {agg_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
