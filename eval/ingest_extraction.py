#!/usr/bin/env python3
"""
Ingest Stage 1 output into data/extracted/claims.jsonl, with validation.

Stage 1 is pasted into a chat, so its output arrives as whatever the model felt
like emitting. Two failure modes are silent and both are fatal downstream:

  1. PRETTY-PRINTED JSON. compare_labels.py and aggregate.py parse one object per
     LINE. A multi-line object reads as zero rows and every metric comes back
     empty with no error. This script flattens whatever it is given -- a single
     object, an array, concatenated objects, or a ```json fenced block.

  2. TIDIED SPANS. Claims are paired with hand labels by exact normalized text.
     If the model paraphrases, trims, or silently fixes a typo in the posting,
     the claim can never be matched and is dropped from the evaluation without
     comment. This script checks every claim text against the posting it came
     from and refuses the batch if spans are not verbatim.

  3. INVENTED context_section NAMES. Stage 3 partitions claims into role context
     and employer context on this field. A name outside the closed list ("Tech"
     for "Tech stack") is not an error anywhere downstream -- aggregate.py just
     files the claim under employer context and the role-context score moves for
     a reason nobody can see. This script refuses the batch if any claim carries
     a section name that is not in the closed list.

Usage:
  python eval/ingest_extraction.py out.json              # validate only (dry run)
  python eval/ingest_extraction.py out.json --append     # validate, then write
  python eval/ingest_extraction.py out.json --append --force   # write anyway

Re-ingesting the same posting_id replaces its earlier row, so a batch can be
redone after fixing a prompt without duplicating rows.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

RAW = Path("data/raw/raw_postings.jsonl")
OUT = Path("data/extracted/claims.jsonl")
SAMPLE = Path("eval/batches/sample_ids.txt")

# Closed list from prompts/stage1_extraction.md. Keep the two in sync: the prompt
# is what the model reads, this is what refuses the batch when it improvises.
EMPLOYER_SECTIONS = ("Company", "Company programs", "Culture/values")
ROLE_SECTIONS = ("Role", "Team", "Responsibilities", "Requirements",
                 "Preferred qualifications", "Tech stack", "Product scope",
                 "Compensation", "Benefits", "Location/schedule", "Level",
                 "Reporting line", "Hiring process")
CONTEXT_SECTIONS = frozenset(EMPLOYER_SECTIONS + ROLE_SECTIONS)


def norm(s: str) -> str:
    s = (s or "").lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("–", "-"), ("—", "-"), ("−", "-"), (" ", " ")):
        s = s.replace(a, b)
    return " ".join(s.split())


def parse_models_output(text: str) -> list[dict]:
    """Accept an object, an array, concatenated objects, or a fenced block."""
    text = text.strip()
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidates = [*fences, text] if fences else [text]

    for cand in candidates:
        cand = cand.strip()
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]

    # concatenated top-level objects: walk braces outside strings
    out, depth, start, in_str, esc = [], 0, None, False, False
    src = candidates[0]
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


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_output", type=Path)
    ap.add_argument("--append", action="store_true", help="write after validating")
    ap.add_argument("--force", action="store_true", help="write despite errors")
    args = ap.parse_args()

    raw = {r["id"]: r for r in load_jsonl(RAW)}
    if not raw:
        print(f"error: {RAW} is empty", file=sys.stderr)
        sys.exit(1)
    sample = set(SAMPLE.read_text(encoding="utf-8").split()) if SAMPLE.exists() else set()

    postings = parse_models_output(args.model_output.read_text(encoding="utf-8"))
    if not postings:
        print("error: found no JSON objects in that file.", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    warnings: list[str] = []
    good: list[dict] = []

    print(f"parsed {len(postings)} posting object(s)\n")
    for p in postings:
        pid = str(p.get("posting_id") or p.get("id") or "")
        claims = p.get("claims") or []
        if pid not in raw:
            errors.append(f"{pid or '(no posting_id)'}: not in the corpus — "
                          f"check posting_id was copied exactly")
            continue
        if sample and pid not in sample:
            warnings.append(f"{pid}: not in eval/batches/sample_ids.txt")
        if not claims:
            errors.append(f"{pid}: no claims")
            continue

        body = norm(raw[pid]["content"])
        bad_spans, bad_sections, missing_fields = [], [], 0
        for c in claims:
            if not c.get("claim_id") or not (c.get("text") or "").strip():
                missing_fields += 1
                continue
            if norm(c["text"]) not in body:
                bad_spans.append(c["text"])
            section = (c.get("context_section") or "").strip()
            if section not in CONTEXT_SECTIONS:
                bad_sections.append((c["claim_id"], section))

        verbatim = len(claims) - len(bad_spans) - missing_fields
        ok_sections = len(claims) - len(bad_sections) - missing_fields
        status = "ok " if not (bad_spans or bad_sections or missing_fields) else "BAD"
        print(f"  {status} {pid[:44]:44s} {len(claims):3d} claims, "
              f"{verbatim} verbatim, {ok_sections} sections in list")
        if missing_fields:
            errors.append(f"{pid}: {missing_fields} claim(s) missing claim_id or text")
        if bad_spans:
            errors.append(f"{pid}: {len(bad_spans)} claim(s) not verbatim in the posting")
            for t in bad_spans[:4]:
                print(f"        not found: {t[:88]}")
            if len(bad_spans) > 4:
                print(f"        ... and {len(bad_spans) - 4} more")
        if bad_sections:
            errors.append(f"{pid}: {len(bad_sections)} claim(s) with a context_section "
                          f"outside the closed list")
            for cid, section in bad_sections[:4]:
                near = difflib.get_close_matches(section, CONTEXT_SECTIONS, n=1, cutoff=0.4)
                hint = f' -- did you mean "{near[0]}"?' if near else ""
                print(f'        {cid}: "{section or "(empty)"}" not in the closed list{hint}')
            if len(bad_sections) > 4:
                print(f"        ... and {len(bad_sections) - 4} more")
        if not bad_spans and not bad_sections and not missing_fields:
            good.append({"posting_id": pid,
                         "title": raw[pid].get("title", ""),
                         "company": raw[pid].get("company", ""),
                         "extraction_prompt_version": p.get("extraction_prompt_version", "1.0"),
                         "total_claims": len(claims),
                         "claims": claims})

    print()
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR:   {e}")

    if errors and not args.force:
        print("\nNothing written. Fix the spans (copied verbatim from the posting, "
              "typos included) and the context_section values (closed list in "
              "prompts/stage1_extraction.md), then re-run, or pass --force.")
        sys.exit(1)

    if not args.append:
        print(f"\nDry run — {len(good)} posting(s) would be written to {OUT}.")
        print("Re-run with --append to write.")
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

    total_claims = sum(r["total_claims"] for r in existing.values())
    done = len(existing)
    print(f"\nwrote {len(good)} posting(s) to {OUT}")
    print(f"  extracted so far: {done}/15 postings, {total_claims} claims")
    if sample:
        left = sorted(sample - set(existing))
        if left:
            print(f"  still to do ({len(left)}): {', '.join(x[:28] for x in left[:5])}"
                  + (" ..." if len(left) > 5 else ""))
        else:
            print("  all 15 postings extracted — next: python eval/label_claims.py")


if __name__ == "__main__":
    main()
