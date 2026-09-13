# Project Summary

Weekend-sized LLM pipeline: taxonomy → extract → classify → evaluate → aggregate.

## What Exists

| Piece | Path | Status |
|-------|------|--------|
| Greenhouse fetcher | `src/fetchers/greenhouse.py` | Working; per-board caps, seeded sampling, whole boards by default |
| Claim extraction prompt | `prompts/stage1_extraction.md` | Ready |
| Classification prompt | `prompts/stage2_classification.md` | Ready |
| Shared taxonomy | `prompts/shared_context.md` | Ready |
| Aggregation (scores + seniority/region rollups) | `src/pipeline/aggregate.py` | Working |
| Label agreement checker | `eval/compare_labels.py` | Working |
| Hand labels | `eval/labeled.jsonl` | 3 synthetic examples + `posting_A` (36 claims), blind=false. Grow to ~150 blind claims |
| Annotator consistency measurement | `eval/annotator_passes.md` | Measured: 75.0% exact / 80.6% boundary self-agreement |
| Blind labeler CLI | `eval/label_claims.py` | Working (stdlib; `--selftest`, `--verify`) |
| Corpus scope filter | `src/pipeline/role_filter.py` | Working (English + software/adjacent) |
| Stage 1 ingest + validator | `eval/ingest_extraction.py` | Working (flattens JSON, enforces verbatim spans) |
| Eval sample + batch builder | `eval/make_batches.py` | Working (scope + dedupe + balanced, seeded) |
| Eval report | `eval/RESULTS.md` | Annotator section measured; model sections empty |
| Data schema | `data/schema.md` | Reference |

## Intentionally Not Built

- Lever / Ashby / HN fetchers (Greenhouse is enough for v1)
- (Reversed 2026-09-13, with evidence) `sumup` and `wolt` were briefly dropped for
  contributing 0 and 1 in-scope postings. That evidence was an artefact of
  alphabetical truncation. On a full fetch sumup contributes **45 in-scope
  postings — 5th of 11 boards** — and is the **largest single source of the
  `baltics` bucket (10 of 20)**, the one geographic rollup this project reports.
  wolt contributes 22, including 19 to `eu`. Both kept.
- Span-matching F1 for Stage 1 (extraction is spot-checked by reading, not scored)
- Inter-annotator agreement (one annotator; only intra-annotator is available)
- Hosted UI or charts app
- Automatic LLM batch runner (use Claude/Cursor/Gemini + the prompt files)
- Per-company leaderboards (aggregates only: seniority / region)
- Rollups by company size — `company_size` is inferred from posting text and came
  back `unknown` for 143 of 144 postings; postings do not state headcount, so a
  bigger corpus will not fix it. Kept as a per-posting diagnostic only.
- Rollups by sector — every board in the corpus is a software/fintech employer, so
  the rollup has one real bucket. What the code separates is *department*.

## Known Limits of This Release

- **Tier 3 is defined but never observed** — 0 of 150 labeled claims. Stage 1
  suppresses company slogans (2.3% of extracted claims are slogan-ish), and the
  mechanical Tier 1 rule lets generic requirements escape Tier 3 on uninformative
  tokens. The score is in practice `tier_1 / (tier_1 + tier_2)` on this corpus.
  Shipped as a documented finding rather than fixed; the fix is a Stage 1 prompt
  change, a re-run and a re-label. See `eval/RESULTS.md` section 5.

## Design Choices

1. **Three stages** — evaluate and swap models independently.
2. **Prompts for judgment, code for math** — Stage 3 is deterministic Python.
3. **Extract first, then hand-label tiers** — the boundary metric is a
   classification metric, and `compare_labels.py` pairs claims by exact text.
   Labeling tiers on Stage 1's spans makes pairing exact and removes hours of
   hand extraction; extraction is spot-checked qualitatively instead. Labeling
   is done blind to `predicted_tier`.
4. **Measure the annotator before the model** — the Tier 1 boundary turned out
   to be only 80.6% self-consistent before it was written down as a mechanical
   test, which is the whole reason the taxonomy now names the particular
   explicitly.
5. **No company call-outs** — portfolio-friendly, privacy-respecting rollups.
6. **No stored credentials** — Greenhouse GET is public; scripts never write secrets.

## Next Steps

1. Re-label `posting_A` blind under the written Tier 1 rule
   (`python eval/label_claims.py --pass 3 --relabel`); gold currently holds
   pass 1 + the corrected degree-requirement call, and is marked blind=false
2. `python eval/make_batches.py`, then Stage 1 over the 15-posting sample →
   ~150 claims after a 10-per-posting cap
3. Label tiers blind; re-label ~30 claims to re-measure self-agreement
4. Stage 2 on the same claims, then `python eval/compare_labels.py ...`
5. Spot-check extraction on 2-3 postings for the limitations section
6. `python src/pipeline/aggregate.py ...` over the full corpus
7. Publish findings + limitations
