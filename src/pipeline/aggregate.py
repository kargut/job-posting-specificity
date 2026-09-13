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
from collections import Counter, defaultdict
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


# Role context vs employer context.
#
# Why this split exists: Tier 1 is a mechanical test -- a number, a named place,
# an explicit timeframe -- and an employer's philanthropy or product-marketing
# section passes it effortlessly while promising the candidate nothing. In the
# first extracted batch one posting was 40% employer-context claims and the other
# two were 16% and 18%. Scoring them together means the headline number partly
# measures how much marketing an employer bolts on, so both numbers are reported:
# specificity_score (role context, the headline) and specificity_score_all_claims.
#
# The partition rests on context_section, which is a MODEL OUTPUT, not a checked
# fact. A mislabelled claim lands in the wrong bucket. That is why both numbers
# and employer_context_share are reported rather than one silently-cut number,
# and why unmapped section names are printed instead of quietly defaulting.
EMPLOYER_CONTEXT_SECTIONS = frozenset(
    {"company", "company programs", "culture/values"}
)
ROLE_CONTEXT_SECTIONS = frozenset(
    {
        "role",
        "team",
        "responsibilities",
        "requirements",
        "preferred qualifications",
        "tech stack",
        "product scope",
        "compensation",
        "benefits",
        "location/schedule",
        "level",
        "reporting line",
        "hiring process",
    }
)


def normalize_section(name: str | None) -> str:
    return " ".join((name or "").strip().lower().split())


def claim_context(claim: dict) -> str:
    """"employer" or "role". Unknown sections default to role context -- the
    conservative direction, since it keeps a claim in the headline number rather
    than silently removing it -- and main() prints every name it had to guess."""
    return "employer" if normalize_section(claim.get("context_section")) \
        in EMPLOYER_CONTEXT_SECTIONS else "role"


def unmapped_section(claim: dict) -> str | None:
    sec = normalize_section(claim.get("context_section"))
    if not sec:
        return "(missing)"
    if sec in EMPLOYER_CONTEXT_SECTIONS or sec in ROLE_CONTEXT_SECTIONS:
        return None
    return sec


# Seniority is read from the TITLE. The body is consulted only as a fallback, and
# only for an explicit years-of-experience figure.
#
# Why: the original rule searched title + body for "senior|lead|principal|staff"
# and checked it first. Bodies run ~5,000 characters and the words turn up in
# boilerplate constantly -- "you will lead incident response", "lead the
# development of new detection logic". Measured over 782 in-scope postings, 268
# (34%) were labelled senior with no seniority word in the title at all, giving
# senior 644 / mid 1. A bucket that fires once in 782 is a bug, not a finding.
try:  # the same definition the sampler uses, so scope cannot drift between them
    from pipeline.role_filter import in_scope
except ImportError:  # when run as a script from inside src/
    from role_filter import in_scope  # type: ignore


TITLE_SENIOR = re.compile(
    r"\b(principal|staff|senior|sr\.?|lead|head of|director|vp|"
    r"vice president|distinguished|fellow)\b",
    re.I,
)
TITLE_JUNIOR = re.compile(
    r"\b(junior|jr\.?|graduate|grad|intern|internship|trainee|apprentice|"
    r"entry[- ]level|associate)\b",
    re.I,
)
TITLE_MID = re.compile(r"\b(ii|iii|mid[- ]level|intermediate)\b", re.I)
YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*years?\b", re.I)


def infer_seniority(title: str, claim_texts: list[str]) -> str:
    """Seniority from the job title; body text only for a years-of-experience
    fallback when the title carries no level marker.

    Known ambiguities, accepted rather than guessed at:
      * "Manager" is a function, not a level, so it is NOT a senior marker.
        "Engineering Manager" falls through to the years fallback.
      * "Associate X" reads as junior only when the title has no senior marker,
        so "Associate Director" is senior and "Associate Engineer" is junior.
      * Numeric ladders differ between employers; II and III both map to mid.
    """
    t = title or ""
    if TITLE_SENIOR.search(t):
        return "senior"
    if TITLE_JUNIOR.search(t):
        return "junior"
    if TITLE_MID.search(t):
        return "mid"

    # Fallback: the smallest stated years figure, i.e. the minimum requirement.
    years = [int(m) for m in YEARS.findall(" ".join(claim_texts))]
    if years:
        n = min(years)
        if n >= 5:
            return "senior"
        if n >= 3:
            return "mid"
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


def score_posting(
    row: dict,
    raw_meta: dict | None = None,
    unmapped: Counter | None = None,
) -> dict | None:
    items = claim_items(row)
    scored = [(c, claim_tier(c)) for c in items]
    scored = [(c, t) for c, t in scored if t is not None]
    if not scored:
        return None

    if unmapped is not None:
        for c, _ in scored:
            name = unmapped_section(c)
            if name:
                unmapped[name] += 1

    tiers = [t for _, t in scored]
    t1 = sum(1 for t in tiers if t == 1)
    t2 = sum(1 for t in tiers if t == 2)
    t3 = sum(1 for t in tiers if t == 3)
    total = t1 + t2 + t3
    score_all = t1 / total if total else 0.0

    role_tiers = [t for c, t in scored if claim_context(c) == "role"]
    role_total = len(role_tiers)
    role_t1 = sum(1 for t in role_tiers if t == 1)
    # None, not 0.0: a posting whose every claim is about the employer has no
    # role-context score at all, and averaging a 0.0 in would be a fabrication.
    role_score = round(role_t1 / role_total, 4) if role_total else None
    employer_total = total - role_total

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
        # Headline: role-context claims only. See EMPLOYER_CONTEXT_SECTIONS.
        "specificity_score": role_score,
        "specificity_score_all_claims": round(score_all, 4),
        "role_claims": role_total,
        "role_tier_1_claims": role_t1,
        "employer_claims": employer_total,
        "employer_context_share": round(employer_total / total, 4) if total else 0.0,
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
    """Group by `key` and report both scores side by side.

    `count` is every posting in the group; `scored_count` is how many of them had
    at least one role-context claim. They differ only when a posting is entirely
    employer context, which is itself worth seeing.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in scores:
        groups[str(s.get(key) or "unknown")].append(s)

    def mean(vals: list[float]) -> float | None:
        return round(statistics.mean(vals), 4) if vals else None

    out = []
    for label, rows in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        vals = [r["specificity_score"] for r in rows if r["specificity_score"] is not None]
        all_vals = [r["specificity_score_all_claims"] for r in rows]
        shares = [r["employer_context_share"] for r in rows]
        out.append(
            {
                key if key != "company_size" else "size_bracket": label,
                "count": len(rows),
                "scored_count": len(vals),
                "avg_specificity": mean(vals),
                "median_specificity": round(statistics.median(vals), 4) if vals else None,
                "std_dev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
                "avg_specificity_all_claims": mean(all_vals),
                "avg_employer_context_share": mean(shares),
                "percentiles": percentiles(vals),
            }
        )
    return out


def summary_md(scores: list[dict], aggregates: dict) -> str:
    vals = [s["specificity_score"] for s in scores if s["specificity_score"] is not None]
    all_vals = [s["specificity_score_all_claims"] for s in scores]
    shares = [s["employer_context_share"] for s in scores]
    no_role = len(scores) - len(vals)

    def stat(fn, v: list[float]) -> str:
        return f"{fn(v):.2f}" if v else "—"

    lines = [
        "# Specificity Scores: Summary",
        "",
        "## Overall",
        f"- **Postings analyzed:** {len(scores)}",
        f"- **Average specificity (role context):** {stat(statistics.mean, vals)}",
        f"- **Median specificity (role context):** {stat(statistics.median, vals)}",
        f"- **Std. dev:** {stat(statistics.pstdev, vals) if len(vals) > 1 else '—'}",
        f"- **Range:** {min(vals):.2f}–{max(vals):.2f}" if vals else "- **Range:** —",
        f"- **Average specificity (all claims):** {stat(statistics.mean, all_vals)}",
        f"- **Average employer-context share:** {stat(statistics.mean, shares)}",
        "",
        "Two scores are reported. The headline counts only claims about the role;",
        "the second counts every extracted claim, including the employer's own",
        "company and culture sections. The gap between them is how much of a",
        "posting's apparent specificity is about the employer rather than the job.",
        "The split rests on Stage 1's `context_section`, which is a model output,",
        "not a checked fact — see the limitations section.",
        "",
    ]
    if no_role:
        lines.insert(
            4,
            f"- **Postings with no role-context claims:** {no_role} "
            f"(excluded from the headline average)",
        )

    def table(title: str, rows: list[dict], label_key: str) -> None:
        lines.append(f"## {title}")
        lines.append(f"| {label_key} | Count | Avg (role) | Median (role) | "
                     f"Avg (all claims) | Employer share |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for r in rows:
            label = r.get(label_key) or r.get("size_bracket") or "?"
            def num(key: str) -> str:
                v = r.get(key)
                return f"{v:.2f}" if v is not None else "—"
            lines.append(
                f"| {label} | {r['count']} | {num('avg_specificity')} | "
                f"{num('median_specificity')} | {num('avg_specificity_all_claims')} | "
                f"{num('avg_employer_context_share')} |"
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
    parser.add_argument(
        "--all-roles",
        action="store_true",
        help="score every classified posting, skipping the English + "
             "software/adjacent scope filter the eval set and write-up assume",
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
    out_of_scope = 0
    unmapped: Counter = Counter()
    for row in classified:
        pid = str(row.get("posting_id") or "")
        raw = raw_by_id.get(pid)
        # Corpus scope is enforced here as well as at sampling time. Without it,
        # a full-corpus run aggregates over the ~64% of fetched postings the eval
        # set excludes -- sales, marketing and finance roles -- and the write-up
        # would describe a different corpus than the one it measured.
        if raw is not None and not args.all_roles and not in_scope(raw):
            out_of_scope += 1
            continue
        scored = score_posting(row, raw, unmapped)
        if scored is None:
            skipped += 1
            continue
        scores.append(scored)

    if out_of_scope:
        print(f"Skipped {out_of_scope} posting(s) outside corpus scope "
              f"(English + software/adjacent). Use --all-roles to include them.")

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

    no_role = sum(1 for s in scores if s["specificity_score"] is None)

    print(f"Scored {len(scores)} postings ({skipped} skipped with 0 claims)")
    if no_role:
        print(f"  {no_role} posting(s) had no role-context claims — "
              f"no headline score, all-claims score only")
    if unmapped:
        print("  WARNING: context_section values not in the Stage 1 vocabulary, "
              "counted as ROLE context:")
        for name, n in unmapped.most_common(12):
            print(f"    {n:5d}  {name}")
        print("    Fix prompts/stage1_extraction.md or extend the section sets "
              "in this file; do not leave them guessed.")
    print(f"  {scores_path}")
    print(f"  {agg_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
