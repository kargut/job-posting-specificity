#!/usr/bin/env python3
"""
Build paste-ready Stage 2 input from Stage 1's extracted claims.

Stage 2 classifies CLAIMS, not postings, so its input is the claim list -- not
the job ads again. Batches reuse the Stage 1 grouping in eval/batches/, so
"batch 1" means the same postings in both stages and a smoke test on one batch
covers a known slice.

Only claims that carry a hand label are emitted by default: an unlabeled claim
costs tokens and can never appear in an agreement number. --all-claims includes
every extracted claim (what you want for a full-corpus scoring run, not for eval).

Usage:
  python eval/make_stage2_batches.py                # labeled claims only
  python eval/make_stage2_batches.py --batch 1      # just one batch
  python eval/make_stage2_batches.py --all-claims

Writes eval/stage2_batches/batchN.txt (gitignored -- contains posting text).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXTRACTED = Path("data/extracted/claims.jsonl")
GOLD = Path("eval/labeled.jsonl")
SRC_BATCHES = Path("eval/batches")
OUT = Path("eval/stage2_batches")


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0, help="emit only this batch")
    ap.add_argument("--all-claims", action="store_true",
                    help="include claims with no hand label")
    args = ap.parse_args()

    extracted = {r["posting_id"]: r for r in load_jsonl(EXTRACTED)}
    if not extracted:
        raise SystemExit(f"error: {EXTRACTED} is empty -- run Stage 1 first")

    labeled: dict[str, set[str]] = {}
    for r in load_jsonl(GOLD):
        labeled[r["posting_id"]] = {str(c["claim_id"]) for c in r["claims"]}

    groups: dict[int, list[str]] = {}
    for p in sorted(SRC_BATCHES.glob("batch*.txt")):
        n = int(re.search(r"batch(\d+)", p.stem).group(1))
        groups[n] = re.findall(r"===== posting_id: (\S+) =====",
                               p.read_text(encoding="utf-8"))
    if not groups:
        raise SystemExit(f"error: no batches in {SRC_BATCHES} -- run make_batches.py")

    OUT.mkdir(parents=True, exist_ok=True)
    total_claims = 0
    for n, pids in sorted(groups.items()):
        if args.batch and n != args.batch:
            continue
        blocks, count = [], 0
        for pid in pids:
            row = extracted.get(pid)
            if not row:
                continue
            keep = [c for c in row["claims"]
                    if args.all_claims or str(c["claim_id"]) in labeled.get(pid, set())]
            if not keep:
                continue
            count += len(keep)
            blocks.append(json.dumps({
                "posting_id": pid,
                "title": row.get("title", ""),
                "total_claims": len(keep),
                "claims": [{"claim_id": str(c["claim_id"]),
                            "text": c["text"],
                            "context_section": c.get("context_section", "")}
                           for c in keep],
            }, ensure_ascii=False, indent=2))
        path = OUT / f"batch{n}.txt"
        path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        total_claims += count
        print(f"  {path}  {len(blocks)} postings, {count} claims, "
              f"{len(path.read_text(encoding='utf-8')):,} chars")
    scope = "all extracted" if args.all_claims else "labeled only"
    print(f"total {total_claims} claims ({scope})")


if __name__ == "__main__":
    main()
