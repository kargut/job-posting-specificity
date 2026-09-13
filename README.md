# job-posting-specificity

**A three-stage pipeline that scores how much of a job posting is concrete commitment versus filler.**

Portfolio piece: GitHub repo + one write-up, focused on taxonomy design, evaluation, and honest limitations — not a hosted product.

## Quick Start

```bash
# 1. Fetch jobs (stdlib only — no pip install required)
python src/fetchers/greenhouse.py --boards stripe,datadog --limit 50

# 2. Stage 1: build a stratified sample, then extract claims with an LLM
python eval/make_batches.py   # → eval/batches/batchN.txt + prompts/stage1_extraction.md
# 3. Hand-label TIERS on those spans, blind — the labeler enforces the rule
python eval/label_claims.py --postings 15 --per-posting 10
python eval/label_claims.py --verify eval/labeled.jsonl
# 4. Stage 2: classify the same claims (LLM + prompts/stage2_classification.md), then evaluate
python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl \
  --report eval/RESULTS.md

# 5. Score + aggregate (deterministic — no LLM)
python src/pipeline/aggregate.py data/classified/claims.jsonl results/ \
  --raw data/raw/raw_postings.jsonl
```

No `.env` or stored API keys. Greenhouse public boards need no auth; pass `--boards` or enter tokens when prompted.

## What It Does

| Stage | What | How |
|-------|------|-----|
| **1 — Extraction** | Split posting into discrete claims | LLM + `prompts/stage1_extraction.md` |
| **2 — Classification** | Assign each claim Tier 1 / 2 / 3 | LLM + `prompts/stage2_classification.md` |
| *(gold labels)* | Human tiers on Stage 1 spans, blind | `eval/label_claims.py` |
| **3 — Aggregation** | Specificity scores + rollups by seniority and region | `src/pipeline/aggregate.py` |

### Taxonomy

- **Tier 1 (Concrete):** Number, named tech, timeframe, or falsifiable commitment (`€60k`, `Go + PostgreSQL`, `team of nine`)
- **Tier 2 (General direction):** Real intent, unspecific (`We invest in developer growth`, `modern stack`)
- **Tier 3 (Empty slogan):** Generic filler (`fast-paced`, `we're like a family`)

**The Tier 1 test** is mechanical, because it has to be: *quote the particular.*
A claim is Tier 1 only if you can point at a number, a named technology, a named
place, an explicit timeframe, an unhedged credential, or a quantified policy.
"Expert work", "works with the security and data science teams" and "financial
infrastructure platform" name nothing checkable — all Tier 2. Seriousness of the
work is not a Tier 1 criterion. Full rule and worked boundary cases:
`prompts/shared_context.md`.

**Score:** `specificity = tier_1 / (tier_1 + tier_2 + tier_3)`

## Project Structure

```
.
├── src/fetchers/greenhouse.py     # Greenhouse Job Board API client
├── src/pipeline/aggregate.py      # Stage 3 scoring + seniority/region rollups
├── prompts/                       # Stage 1–2 prompts (+ shared taxonomy)
├── data/schema.md                 # Canonical JSON shapes
├── data/raw/                      # Fetched postings (gitignored)
├── data/extracted/                # Stage 1 output (gitignored)
├── data/classified/               # Stage 2 output (gitignored)
├── eval/labeled.jsonl             # Hand labels (gitignored; local only)
├── eval/make_batches.py           # Stratified eval sample → Stage 1 batches
├── eval/label_claims.py           # Blind tier labeler + label linter
├── eval/compare_labels.py         # Agreement metrics
├── eval/annotator_passes.md       # Intra-annotator consistency measurement
├── eval/RESULTS.md                # Evaluation report
└── results/                       # scores.jsonl, aggregates.json, summary.md
```

## Evaluation

Full report: `eval/RESULTS.md`. Protocol: `GETTING_STARTED.md` sections 3-6.

### Annotator consistency comes first

Before reporting any model accuracy, the annotator was measured against
themselves. The same 36 extracted claims from one real posting were tier-labeled
twice, a day apart, before a written decision rule existed:

| Measure | Value |
|---|---|
| Exact-tier self-agreement | 75.0% (9 of 36 changed) |
| Tier 1 / Other boundary self-agreement | 80.6% (7 of 36 crossed) |
| Specificity score, pass 1 → pass 2 | 0.333 → 0.472 |

The headline score moved 42% in relative terms with no change to the document.
The original ≥80% quality gate was therefore sitting exactly on the noise floor:
a model hitting it would have been indistinguishable from one merely as
inconsistent as the human.

The fix was to turn the Tier 1 boundary into a mechanical test — quote the
particular — and to enforce it in the tooling rather than in a habit:
`eval/label_claims.py` refuses a Tier 1 whose reasoning does not quote the
claim, and `--verify` audits an existing label file for the same thing. Run
against the drifted pass, it flags 34 errors. Per-claim diff:
`eval/annotator_passes.md`.

`compare_labels.py` also now refuses a predictions file that carries no
`predicted_tier`: comparing hand labels to hand labels measures annotator
agreement at best, and nothing at all when the two files share a lineage.

### Model agreement

_Not yet measured. Numbers go here once Stage 2 has been run against the blind
labels; the boundary figure will be reported with a 95% CI and alongside
post-rule annotator self-agreement, not on its own._

| Measure | Value |
|---|---|
| Claims in eval set | — |
| Tier 1 / Other boundary accuracy | — |
| Tier 1 precision | — |
| Cost per 1,000 postings | — |
| Latency per posting | — |

## Limitations of the Method

Distinct from what the score does not measure (below) — these are weaknesses in
how the number was produced.

1. **One annotator.** There is no inter-annotator agreement, only
   intra-annotator. A second labeler would likely disagree more than the
   annotator disagreed with themselves.
2. **Gold labels sit on model-extracted spans.** Tiers were adjudicated on
   Stage 1's output rather than on independently extracted claims. This makes
   claim pairing exact and the classification metric honest, but it means
   **extraction errors are invisible to the boundary metric** — a claim the
   extractor never found cannot be counted wrong.
3. **Extraction is not scored numerically, and it omits slogans — which
   inflates every score.** Stage 1 is spot-checked by reading postings against
   their claims, not scored (span-matching F1 was judged out of scope). All 745
   extracted claims are verbatim and no boilerplate slipped through, but reading
   two postings sentence by sentence showed the extractor skipping mission and
   atmosphere language — "we're on a mission to make money work for everyone",
   "a highly ambitious, large-scale technology company with a soul". Those are
   Tier 3 by the taxonomy's own deletion test.

   Because the score is `tier_1 / (tier_1 + tier_2 + tier_3)`, dropping slogans
   removes Tier 3 from the **denominator only**, so the bias runs one way: scores
   are too high. If every omitted non-boilerplate sentence in those two postings
   were Tier 3, their scores would fall by 30% and 28% relative — an upper bound
   near 29%, not an estimate, since some omitted sentences are not slogans and
   some restate an extracted claim. **Absolute specificity scores are therefore
   optimistic by an unquantified margin; comparisons between postings still hold,
   because the bias applies to all of them in the same direction.** The fix is a
   Stage 1 prompt change and a re-run. Detail in `eval/RESULTS.md` section 5.
4. **Small eval set.** ~150 claims, so the boundary accuracy carries roughly
   ±7pp at 95% confidence. Claims of a few points' improvement are not
   supportable at this size.
5. **Anchoring risk in the first labels.** The initial pass was made with model
   output visible, which inflates agreement in a way that cannot be undone.
   Those labels were redone blind; the protocol now requires it.
6. **Equal weight per claim.** A salary range counts the same as a named
   database. A posting can raise its score by listing technologies while
   staying silent on pay.
7. **Only two rollups are reported: seniority and region.** Size and sector were
   dropped because the data does not support them, not because they were
   uninteresting. `company_size` is inferred from the posting text and resolved
   to `unknown` for **143 of 144** postings in the first corpus — job postings do
   not state headcount, and a larger sample cannot fix that. Every board in the
   corpus is a software or fintech employer, so a sector rollup has one real
   bucket; what the code separates is *department*, a narrower claim. Both values
   stay in `results/scores.jsonl` as diagnostics.
8. **The corpus needs filtering, and the filter is imperfect.** Greenhouse serves
   whole boards, and these employers hire mostly salespeople: of 2,176 fetched
   postings only 36% are software-or-adjacent, and 2% are not in English. A scope
   filter (`src/pipeline/role_filter.py`) cuts it to 781 postings, 701 after
   collapsing repeated role titles.
   "Adjacent" deliberately includes pre-sales technical roles. The filter is
   keyword-based, so it admits occasional borderline cases — an operations or
   enablement role whose title carries a technical word — and would need a
   hand-audited exclusion list to be airtight.
9. **Seniority is inferred from the title, and some titles carry no level.**
   "Manager" is a function rather than a level, so `Engineering Manager` falls
   through to a stated-minimum-years fallback and otherwise lands in
   `unspecified` (96 of 781). Numeric ladders differ between employers, so II and
   III both map to `mid`. These are documented choices, not measurements.
10. **Greenhouse only, English only.** Large US tech employers are
   over-represented, and their postings are written by people with a legal
   review process. Findings should not be read as applying to small European
   employers.

## What This Score Does NOT Measure

- **Not honesty.** A precise promise can be broken; a vague ad can conceal a good job.
- **Not quality.** Some excellent employers write badly.
- **Not intent.** Much filler is copied from a template.
- **Not the candidate's experience.** Document information content only.

## Data Sources

1. **Greenhouse Job Board API** (public boards, no auth for GET)
2. Lever / Ashby (similar public APIs — not wired yet)
3. Hacker News "Who is hiring?" (via Algolia — not wired yet)

Avoid LinkedIn / Indeed (ToS + optics).

## Files to Commit

**Commit:** `src/`, `prompts/`, `data/schema.md`, `eval/` (scripts, `RESULTS.md`, `annotator_passes.md` — not `labeled.jsonl`), docs, `.gitignore`

**Do not commit:** `.env`, `data/raw/*.jsonl`, `data/extracted/`, `data/classified/`, `eval/labeled.jsonl`, full `results/` corpus

## Workflow

See `GETTING_STARTED.md`. Prompt usage tips: `PROMPT_USAGE.md`. Taxonomy: `prompts/shared_context.md`.
