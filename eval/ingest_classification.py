#!/usr/bin/env python3
"""
Ingest Stage 2 output into data/classified/claims.jsonl, with validation.

The same two silent failures as Stage 1 apply -- pretty-printed JSON reads as
zero rows, and rewritten claim text can never be paired with a hand label -- plus
one that is specific to Stage 2:

  MISSING OR INVALID predicted_tier. `compare_labels.py` skips any claim whose
  tier is not 1, 2 or 3. A model that hedges ("1 or 2"), returns a string, or
  quietly omits a few claims shrinks the eval set without saying so, and the
  reported accuracy is then computed over whatever survived.

This script refuses the batch unless every claim carries a valid tier, every
claim_id is one Stage 1 actually produced, and every text still matches Stage 1
character for character after normalisation.

Usage:
  python eval/ingest_classification.py out.json            # validate (dry run)
  python eval/ingest_classification.py out.json --append   # validate, then write
  python eval/ingest_classification.py out.json --append --force

Re-ingesting a posting_id replaces its row, so a batch can be redone after a
prompt fix without duplicating rows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXTRACTED = Path("data/extracted/claims.jsonl")
GOLD = Path("eval/labeled.jsonl")
OUT = Path("data/classified/claims.jsonl")


def norm(s: str) -> str:
    s = (s or "").lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("–", "-"), ("—", "-"), ("−", "-"), (" ", " ")):
        s = s.replace(a, b)
    return " ".join(s.split())


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def parse_models_output(text: str) -> list[dict]:
    text = text.strip()
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for cand in ([*fences, text] if fences else [text]):
        try:
            data = json.loads(cand.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    out, depth, start, in_str, esc = [], 0, None, False, False
    src = fences[0] if fences else text
    for i, ch in enumerate(src):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    out.append(json.loads(src[start:i + 1]))
                except json.JSONDecodeError:
                    pass
                start = None
    return [d for d in out if isinstance(d, dict)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_output", type=Path)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    # Keep the WHOLE Stage 1 claim, not just its text. context_section has to ride
    # along into data/classified/claims.jsonl: aggregate.py splits role context from
    # employer context on it, and when it is absent every claim defaults to role
    # context, which silently collapses specificity_score into
    # specificity_score_all_claims. Measured 2026-09-14: 150/150 claims arrived with
    # no context_section and the two scores were identical on all 15 postings.
    extracted = {r["posting_id"]: {str(c["claim_id"]): c for c in r["claims"]}
                 for r in load_jsonl(EXTRACTED)}
    if not extracted:
        print(f"error: {EXTRACTED} is empty -- run Stage 1 first", file=sys.stderr)
        sys.exit(1)
    gold = {r["posting_id"]: {str(c["claim_id"]) for c in r["claims"]}
            for r in load_jsonl(GOLD)}

    postings = parse_models_output(args.model_output.read_text(encoding="utf-8"))
    if not postings:
        print("error: found no JSON objects in that file.", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    good: list[dict] = []
    print(f"parsed {len(postings)} posting object(s)\n")

    for p in postings:
        pid = str(p.get("posting_id") or "")
        claims = p.get("claims") or p.get("classifications") or []
        if pid not in extracted:
            errors.append(f"{pid or '(no posting_id)'}: not in Stage 1 output")
            continue
        if not claims:
            errors.append(f"{pid}: no claims")
            continue

        src = extracted[pid]
        bad_tier, unknown_id, drifted = [], [], []
        tiers = {}
        for c in claims:
            cid = str(c.get("claim_id") or "")
            tier = c.get("predicted_tier", c.get("tier"))
            if cid not in src:
                unknown_id.append(cid or "(none)")
                continue
            if tier not in (1, 2, 3):
                bad_tier.append(f"{cid}={tier!r}")
                continue
            if c.get("text") and norm(c["text"]) != norm(src[cid]["text"]):
                drifted.append(cid)
                continue
            tiers[cid] = int(tier)

        covered_gold = len(gold.get(pid, set()) & set(tiers))
        want_gold = len(gold.get(pid, set()))
        ok = not (bad_tier or unknown_id or drifted) and covered_gold == want_gold
        print(f"  {'ok ' if ok else 'BAD'} {pid[:42]:42s} "
              f"{len(tiers):3d} tiered, {covered_gold}/{want_gold} gold covered")
        if bad_tier:
            errors.append(f"{pid}: predicted_tier not 1/2/3 -> {', '.join(bad_tier[:6])}")
        if unknown_id:
            errors.append(f"{pid}: {len(unknown_id)} claim_id(s) Stage 1 never produced")
        if drifted:
            errors.append(f"{pid}: {len(drifted)} claim text(s) changed since Stage 1 "
                          f"-> cannot pair with hand labels")
        if covered_gold < want_gold:
            missing = sorted(gold.get(pid, set()) - set(tiers))
            errors.append(f"{pid}: {want_gold - covered_gold} labeled claim(s) got no "
                          f"tier ({', '.join(missing[:6])}) -- these silently drop "
                          f"out of the evaluation")
        if ok:
            good.append({
                "posting_id": pid,
                "model": p.get("model") or p.get("model_version") or "UNSPECIFIED",
                "classification_prompt_version": p.get(
                    "classification_prompt_version", "1.0"),
                "claims": [{"claim_id": cid, "text": src[cid]["text"],
                            # from Stage 1, not the classifier -- see above
                            "context_section": src[cid].get("context_section"),
                            "predicted_tier": t,
                            "reasoning": next((c.get("reasoning", "") for c in claims
                                               if str(c.get("claim_id")) == cid), "")}
                           for cid, t in tiers.items()],
            })

    print()
    for e in errors:
        print(f"  ERROR: {e}")
    if any(r["model"] == "UNSPECIFIED" for r in good):
        print("  warning: no model name in the output -- set it, cost/latency "
              "reporting needs to say which model produced these tiers")

    if errors and not args.force:
        print("\nNothing written. Fix and re-run, or pass --force.")
        sys.exit(1)
    if not args.append:
        print(f"\nDry run -- {len(good)} posting(s) would be written to {OUT}.")
        return

    existing = {r["posting_id"]: r for r in load_jsonl(OUT)}
    order = [r["posting_id"] for r in load_jsonl(OUT)]
    for row in good:
        if row["posting_id"] not in existing:
            order.append(row["posting_id"])
        existing[row["posting_id"]] = row
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for pid in order:
            f.write(json.dumps(existing[pid], ensure_ascii=False) + "\n")
    n_claims = sum(len(r["claims"]) for r in existing.values())
    print(f"\nwrote {len(good)} posting(s) to {OUT}")
    print(f"  classified so far: {len(existing)}/15 postings, {n_claims} claims")
    left = sorted(set(extracted) - set(existing))
    if left:
        print(f"  still to do ({len(left)})")
    else:
        print("  all 15 done -- next: python eval/compare_labels.py "
              "eval/labeled.jsonl data/classified/claims.jsonl")


if __name__ == "__main__":
    main()
