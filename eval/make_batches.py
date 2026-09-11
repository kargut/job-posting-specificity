#!/usr/bin/env python3
"""
Build the eval sample and paste-ready Stage 1 batches.

The sample is stratified across boards, not drawn uniformly: 144 of the 307
postings come from three large US employers, so a uniform draw would spend half
the eval set on one kind of document and tell you nothing about how the
classifier behaves on small or European postings. One posting per board first,
then fill the remainder round-robin. Deterministic given --seed.

Usage:
  python eval/make_batches.py                      # 15 postings, 4 batches
  python eval/make_batches.py --postings 15 --batches 4 --seed 7

Writes (all gitignored — they contain real posting text):
  eval/batches/batch{N}.txt   paste after prompts/stage1_extraction.md
  eval/batches/sample_ids.txt the chosen posting ids, one per line
"""

from __future__ import annotations

import argparse
import ast
import json
import random
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


def stratified_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """One per board first, then round-robin. Deterministic."""
    by_board: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_board[r.get("source") or "unknown"].append(r)

    rng = random.Random(seed)
    for board in by_board:
        by_board[board].sort(key=lambda r: str(r.get("id")))
        rng.shuffle(by_board[board])

    picked: list[dict] = []
    boards = sorted(by_board)
    round_i = 0
    while len(picked) < n:
        progressed = False
        for b in boards:
            if len(picked) >= n:
                break
            if round_i < len(by_board[b]):
                picked.append(by_board[b][round_i])
                progressed = True
        if not progressed:
            break
        round_i += 1
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
    args = ap.parse_args()

    rows = load_raw(args.raw)
    sample = stratified_sample(rows, args.postings, args.seed)
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

    print(f"corpus {len(rows)} postings, {len({r.get('source') for r in rows})} boards")
    print(f"sample {len(sample)} postings, seed {args.seed}")
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
