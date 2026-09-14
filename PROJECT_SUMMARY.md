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
| Hand labels (gold) | `eval/labeled.jsonl` | **Done: 150 claims / 15 postings, all blind, `--verify` clean** |
| Post-rule 2nd pass | `eval/labeled_pass2_blind.jsonl` | **Done: 50 claims, blind** |
| Annotator consistency measurement | `eval/annotator_passes.md` | Pre-rule 75.0% exact / 80.6% boundary; **post-rule 86.0% / 96.0%** |
| Stage 2 ingest + validator | `eval/ingest_classification.py` | Working (tiers, claim_ids, text drift, `context_section` carry-through) |
| Blind labeler CLI | `eval/label_claims.py` | Working (stdlib; `--selftest`, `--verify`) |
| Corpus scope filter | `src/pipeline/role_filter.py` | Working (English + software/adjacent) |
| Stage 1 ingest + validator | `eval/ingest_extraction.py` | Working (flattens JSON, enforces verbatim spans) |
| Eval sample + batch builder | `eval/make_batches.py` | Working (scope + dedupe + balanced, seeded) |
| Eval report | `eval/RESULTS.md` | All sections measured (sections 4/6 merged by hand — `--report` wipes them) |
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

## Headline Results

| Measure | Value |
|---|---|
| Annotator self-agreement, boundary — pre-rule → post-rule | 80.6% → **96.0%** |
| Model Tier 1 / Other boundary accuracy | **86.7%** [80, 91] |
| Model Tier 1 precision / recall | 0.902 / 0.754 |
| Model vs annotator post-rule consistency | **−8 to −9pp** |
| Cost per 1,000 postings, as run | ~5.10M in / ~2.81M out tokens (measured from run artifacts, ±15%) |
| Cost per 1,000 postings, all claims classified | ~7.04M in / ~6.43M out tokens |
| Latency per posting | not measurable from a chat-driven pipeline |

The classifier clears both absolute gates and **loses to a careful human** on the
boundary. Measured against the pre-rule floor it appeared to win; re-measuring the
floor inverted the result. Full report: `eval/RESULTS.md`.

## Known Limits of This Release

- **The role/employer split went un-exercised until 2026-09-14.** Stage 2 output
  dropped Stage 1's `context_section`, so every claim defaulted to role context
  and the headline `specificity_score` was byte-identical to
  `specificity_score_all_claims` on all 15 postings. Fixed in
  `ingest_classification.py`; the partition is still unvalidated against hand
  judgement. 28 of 150 claims (18.7%) are employer context.
- **Tier 3 is defined but never observed in the first pass** — 0 of 150 labeled
  claims, though a blind post-rule re-label recovered 5 in 50. Stage 1 suppresses
  company slogans (2.3% of extracted claims are slogan-ish), and the mechanical
  Tier 1 rule lets generic requirements escape Tier 3 on uninformative tokens;
  the re-label shows annotator drift is the larger of the two causes. The score is in practice `tier_1 / (tier_1 + tier_2)` on this corpus.
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

Steps 1-6 of the original plan are complete: gold set labeled blind, post-rule
self-agreement measured, Stage 2 run over all 15 postings, `context_section`
carry-through fixed, Stage 3 run.

1. Commit the `context_section` fix in `eval/ingest_classification.py`
2. Merge Stage 2 + self-agreement numbers into `eval/RESULTS.md` sections 4 and 6
   **by hand** — `--report` regenerates from a template and wipes sections 1, 2,
   3, 5 and 7
3. Decide the three borderline role titles (see `role_filter.py`)
4. Write the dev.to post — consistently under-budgeted; deadline 6 October
5. Optional, only if time allows: an instrumented API run over a stratified
   150-200 posting subset, which would replace the chars/4 cost estimate with
   real `usage` counts and give the first latency number

**Deliberately not next:** scoring the full 780-posting corpus. It needs Stage 1
+ Stage 2 over all of them (~43,600 claims, ~5.5M input / ~5.0M output tokens)
and an API runner that does not exist in this repo. Outside the weekend limit,
and the corpus-wide facts the write-up actually needs — 2,176 fetched, 780 in
scope, seniority and region distributions — come from raw metadata with no LLM
at all.
