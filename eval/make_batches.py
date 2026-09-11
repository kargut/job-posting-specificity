#!/usr/bin/env python3
"""
Build the eval sample and paste-ready Stage 1 batches.

Three filters run before sampling, because the raw corpus does not match the
project's stated scope on its own:

1. SCOPE. src/pipeline/role_filter.in_scope keeps English-language
   software-and-adjacent postings. Unfiltered, 79% of the raw corpus was sales,
   marketing and finance -- these employers hire mostly salespeople, and the
   fetcher pulls whole boards.
2. NEAR-DUPLICATE ROLES. One posting per (company, normalized title). One board
   listed the same Commercial Sales Engineer role in five cities; five variants of
   one role from one employer measure the same document five times.
3. BALANCE. Greedy balanced selection across board, region and seniority at once.
   Board-only stratification is not enough: it produced a sample of 14 senior and
   1 unspecified with a single Baltic posting out of 9 available. Region and
   seniority are the two rollups this project reports, and manager postings make
   very different claims from IC postings, so an eval set skewed on either
   dimension mis-measures the classifier.

Deterministic given --seed.

Usage:
  python eval/make_batches.py                      # 15 postings, 4 batches
  python eval/make_batches.py --postings 15 --batches 4 --seed 7
  python eval/make_batches.py --all-roles          # skip the scope filter
  python eval/make_batches.py --keep-duplicate-titles

Writes (all gitignored — they contain real posting text):
  eval/batches/batch{N}.txt   paste after prompts/stage1_extraction.md
  eval/batches/sample_ids.txt the chosen posting ids, one per line
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def load_raw(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_locations(row: dict) -> list[dict]:
    locs = row.get("locations")
    if isinstance(locs, str):
        try:
            locs = ast.literal_eval(locs)
        except Exception:
            locs = []
    return locs or []


def dedupe_titles(rows: list[dict]) -> list[dict]:
    """One posting per (company, normalized title)."""
    seen: set[tuple[str, str]] = set()
    out = []
    for r in sorted(rows, key=lambda r: str(r.get("id"))):
        t = (r.get("title") or "").lower()
        t = re.sub(r"\(.*?\)", " ", t)
        t = re.sub(r"\b(amer|emea|apac|latam|na|west|east|north|south|remote|"
                   r"based in)\b", " ", t)
        t = " ".join(re.sub(r"[^a-z ]", " ", t).split())
        key = (r.get("company") or "", t)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def balanced_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Greedy selection balancing board, region and seniority simultaneously.

    At each step, pick the candidate whose (board, region, seniority) cells are
    currently least represented. Deterministic: ties break on a seeded shuffle.
    """
    try:
        from pipeline.aggregate import infer_region, infer_seniority
    except Exception:  # pragma: no cover
        infer_region = lambda locs: "unknown"          # noqa: E731
        infer_seniority = lambda t, c: "unknown"       # noqa: E731

    def cells(r: dict) -> tuple[str, str, str]:
        return (
            r.get("source") or "unknown",
            infer_region(parse_locations(r)),
            infer_seniority(r.get("title", ""), [r.get("content", "")]),
        )

    pool = sorted(rows, key=lambda r: str(r.get("id")))
    random.Random(seed).shuffle(pool)
    counts: list[Counter] = [Counter(), Counter(), Counter()]
    picked: list[dict] = []

    while pool and len(picked) < n:
        best, best_cost = None, None
        for r in pool:
            # lower is better: how crowded this posting's cells already are
            cost = tuple(counts[i][c] for i, c in enumerate(cells(r)))
            if best_cost is None or cost < best_cost:
                best, best_cost = r, cost
        picked.append(best)
        for i, c in enumerate(cells(best)):
            counts[i][c] += 1
        pool.remove(best)
    return picked

def pack_batches(rows: list[dict], k: int) -> list[list[dict]]:
    """Greedy bin-packing by content length so no batch is twice another."""
    batches: list[list[dict]] = [[] for _ in range(k)]
    sizes = [0] * k
    for r in sorted(rows, key=lambda r: -len(r.get("content") or "")):
        i = sizes.index(min(sizes))
        batches[i].append(r)
        sizes[i] += len(r.get("content") or "")
    return [sorted(b, key=lambda r: str(r.get("id"))) for b in batches]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw/raw_postings.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("eval/batches"))
    ap.add_argument("--postings", type=int, default=15)
    ap.add_argument("--batches", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--all-roles", action="store_true",
                    help="skip the English/software scope filter")
    ap.add_argument("--keep-duplicate-titles", action="store_true",
                    help="keep every variant of a repeated role title")
    args = ap.parse_args()

    raw = load_raw(args.raw)
    rows = raw
    if not args.all_roles:
        from pipeline.role_filter import in_scope
        rows = [r for r in rows if in_scope(r)]
    after_scope = len(rows)
    if not args.keep_duplicate_titles:
        rows = dedupe_titles(rows)
    sample = balanced_sample(rows, args.postings, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    (args.out / "sample_ids.txt").write_text(
        "\n".join(r["id"] for r in sample) + "\n", encoding="utf-8")

    for i, batch in enumerate(pack_batches(sample, args.batches), 1):
        with (args.out / f"batch{i}.txt").open("w", encoding="utf-8") as f:
            for r in batch:
                f.write(f"===== posting_id: {r['id']} =====\n")
                f.write(f"TITLE: {r.get('title','')}\n\n{r.get('content','')}\n\n")

    # composition, so you can see what the eval set actually covers
    try:
        from pipeline.aggregate import infer_region, infer_seniority
        region = Counter(infer_region(parse_locations(r)) for r in sample)
        sen = Counter(infer_seniority(r.get("title", ""), [r.get("content", "")])
                      for r in sample)
    except Exception:
        region = sen = Counter()

    print(f"raw corpus        {len(raw)} postings, "
          f"{len({r.get('source') for r in raw})} boards")
    print(f"  in scope        {after_scope}"
          f"{'  (filter skipped)' if args.all_roles else ''}")
    print(f"  distinct roles  {len(rows)}")
    print(f"sample            {len(sample)} postings, seed {args.seed}")
    print(f"  boards   {dict(Counter(r.get('source','') for r in sample))}")
    if region:
        print(f"  region   {dict(region)}")
        print(f"  seniority{dict(sen)}")
    for i in range(1, args.batches + 1):
        p = args.out / f"batch{i}.txt"
        n = p.read_text(encoding="utf-8").count("===== posting_id:")
        print(f"  {p}  {n} postings, {len(p.read_text(encoding='utf-8')):,} chars")


if __name__ == "__main__":
    main()
