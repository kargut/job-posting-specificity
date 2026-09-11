# Getting Started

## 1. Environment

```bash
cd job-posting-specificity
# No required third-party packages — fetcher/eval/aggregate use the stdlib.
python --version   # 3.10+ recommended
```

Do **not** create a `.env` for this project. Greenhouse listing is public.

## 2. Fetch Data

```bash
python src/fetchers/greenhouse.py --boards stripe,datadog,cloudflare --limit 50
```

Or omit `--boards` and enter tokens when prompted. Tokens are the path segment in
`https://boards.greenhouse.io/{token}`.

**Output:** `data/raw/raw_postings.jsonl` (plain-text descriptions, deduped by content hash)

---

## 3. Stage 1 — Extraction, on the eval sample first

Extraction comes **before** hand-labeling. This is deliberate — see
"Why extraction comes first" below.

Build the sample and paste-ready batches first:

```bash
python eval/make_batches.py          # 15 postings, 4 balanced batches
```

Three filters run before sampling, and none is cosmetic:

1. **Scope.** `src/pipeline/role_filter.py` keeps English-language
   software-and-adjacent postings. Unfiltered, **69% of the raw corpus is sales,
   marketing and finance** — the fetcher pulls whole boards and these employers
   hire mostly salespeople. 272 raw → 83 in scope.
2. **Near-duplicate roles.** One posting per (company, normalized title). One
   board listed the same Commercial Sales Engineer role in five cities. 83 → 69.
3. **Balance.** Greedy selection across board, region and seniority at once.
   Board-only stratification gave 14 senior / 1 unspecified with one Baltic
   posting out of nine available; region and seniority are the two rollups this
   project reports, and manager postings make very different claims from IC
   postings.

Deterministic given `--seed`. It prints the composition so you can see what the
eval set covers. `--all-roles` and `--keep-duplicate-titles` disable filters 1
and 2 if you need to inspect what they remove.

Then, per batch, paste `prompts/stage1_extraction.md` followed by
`eval/batches/batchN.txt` into Claude, Cursor, Gemini, etc.

- Output: append JSON lines to `data/extracted/claims.jsonl`

### Why extraction comes first

The metric that matters is the Tier 1 / Other boundary — a **classification**
question. Extracting spans by hand as well costs hours per posting and answers a
different question badly:

- `eval/compare_labels.py` pairs gold and predicted claims by **exact
  normalized text**. Hand-written spans rarely match model spans
  word-for-word, so unmatched gold claims are silently dropped and the reported
  accuracy is computed over whatever happened to coincide — a biased subset.
- Labeling tiers on the model's own spans makes matching exact by
  construction, so every gold claim counts.

Extraction quality is therefore assessed **qualitatively** on 2–3 postings
(step 6), not scored numerically. Span-matching F1 is out of scope for a
weekend.

## 4. Label Tiers — blind, on the extracted spans

You are adjudicating tiers, not finding claims. Use the labeler — it enforces
the protocol below rather than relying on you to remember it:

```bash
python eval/label_claims.py \
  --extracted data/extracted/claims.jsonl \
  --raw data/raw/raw_postings.jsonl \
  --out eval/labeled.jsonl \
  --postings 15 --per-posting 10
```

One claim at a time with its surrounding sentence; press `1`, `2` or `3`;
`?` reprints the rule, `b` goes back, `q` saves and quits. It writes after every
claim, so it is safe to stop anywhere and resume — already-labeled claims are
skipped. It strips any `predicted_tier` from the input before display, so the
input file can be Stage 2 output without the tiers leaking onto the screen.

A Tier 1 press then asks you to **quote the particular**, and rejects anything
that is not literally in the claim. That is the mechanical version of the rule:
if you cannot quote it, it is not Tier 1.

**Rules for the labeling pass:**

1. **Read `prompts/shared_context.md` first**, specifically "The Tier 1 Test:
   Name the Particular". Label against the written rule, not against a feel for
   whether the work sounds real.
2. **Label blind.** Do not look at the model's `predicted_tier` while labeling.
   Anchoring on it inflates agreement and cannot be undone afterwards.
3. **For every Tier 1, quote the particular in the `reasoning` field.** If you
   cannot quote a substring of the claim, it is not Tier 1.
4. **Append to `eval/labeled.jsonl`** (schema in `data/schema.md`). The labeler
   records `label_pass`, `blind` and `spans_from` for you.

Audit a label file at any time — this is what catches a drifted pass:

```bash
python eval/label_claims.py --verify eval/labeled.jsonl
```

It errors on a Tier 1 whose reasoning quotes nothing from its claim, on Tier 1
assigned for a known non-criterion ("expert work", "work in teams", ...), and on
a Tier 1 reasoning reused so often it must be a template. It warns on
`blind: false`. Run `--selftest` to see the quote rule's own test cases.

### How much to label

The unit that matters is **claims, not postings**.

| | Target |
|---|---|
| Postings sampled | ~15 |
| Claims per posting (cap, sampled if more) | 10 |
| Total labeled claims | ~150 |

150 claims gives roughly ±7pp at 95% confidence on an accuracy near 80%.
Reporting "82%, 95% CI [75, 88], n=150" is stronger than an unqualified figure
on a set that was never sized. Do not aim for 50 postings; it buys precision the
rest of the project cannot use.

Three worked examples are already in `eval/labeled.jsonl` so you can see the
format, plus one real posting.

## 5. Measure your own consistency

Before trusting any model number, measure the noise floor.

Re-label ~30 of the claims blind, a day later, into a separate file:

```bash
python eval/label_claims.py --pass 2 --shuffle --relabel \
  --out eval/labeled_pass2.jsonl --limit 30
python eval/compare_labels.py eval/labeled.jsonl eval/labeled_pass2.jsonl \
  --self-agreement
```

`--self-agreement` is required, and that is deliberate: without it
`compare_labels.py` **refuses** a predictions file carrying no `predicted_tier`,
because comparing labels to labels produces a flattering number by accident.
Record the result in `eval/annotator_passes.md`.

This has already been done once, before a written decision rule existed, and it
is why step 4 rule 1 exists: the same annotator moved 7 of 36 claims across the
Tier 1 boundary between two sittings, shifting the posting's specificity score
from 0.333 to 0.472. **A classifier cannot be shown to beat the annotator's own
self-agreement**, so this number bounds what the evaluation can claim.

## 6. Spot-check extraction (qualitative)

On 2–3 postings, read the posting against the extracted claims and note:

- claims the model missed entirely
- single assertions split into two, or two merged into one
- boilerplate that should have been dropped (EEO, apply instructions, legal)

Write these up as prose for the limitations section. Do not score them.

## 7. Stage 2 — Classification (LLM)

Use `prompts/stage2_classification.md` on the extracted claims from step 3.

- Output: `data/classified/claims.jsonl`
- Each claim needs `predicted_tier` ∈ {1, 2, 3}

**Format matters:** `compare_labels.py` parses one JSON object **per line**. A
pretty-printed, multi-line JSON object — what an LLM chat will hand you by
default — parses as zero rows and the eval silently reports nothing. Flatten
before appending:

```bash
python -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1]))))" \
  model_output.json >> data/classified/claims.jsonl
```

### Evaluate

```bash
python eval/compare_labels.py \
  eval/labeled.jsonl \
  data/classified/claims.jsonl \
  --report eval/RESULTS.md
```

**Target:** ≥80% accuracy on the Tier 1 / Other boundary — but read it against
your own self-agreement from step 5. If self-agreement is 81%, an 80% gate
measures nothing. Raise the gate once the written rule has stabilised your own
labeling, and report both numbers side by side.

If the model is below target, refine the taxonomy/prompt and re-run Stage 2
only — extraction does not need repeating.

## 8. Stage 3 — Aggregation (Python)

No LLM needed:

```bash
python src/pipeline/aggregate.py data/classified/claims.jsonl results/ \
  --raw data/raw/raw_postings.jsonl
```

Writes `results/scores.jsonl`, `results/aggregates.json`, `results/summary.md`.

**Reported rollups are seniority and region only.** `aggregate.py` also computes
`sector` and `company_size` per posting and they remain in `scores.jsonl`, but
neither is reported: size came back `unknown` for 143 of 144 postings in the first
corpus (headcount is read out of the posting text, and postings do not state it),
and every board in the corpus is a software/fintech employer, so sector has one
real bucket. Reasoning in `prompts/shared_context.md`.

**Outstanding code change:** `summary_md()` in `src/pipeline/aggregate.py`
(around lines 246-247) still writes a `By Sector` and a `By Company Size` table
into `results/summary.md`. Until those two `table(...)` calls are removed, a
regenerated summary will contain the two rollups this project no longer reports.
Delete them, and keep `by_sector` / `by_size` in `aggregates.json` as
diagnostics.

## 9. Report

Fill cost/latency and disagreement notes in `eval/RESULTS.md`, then update the
README with headline numbers and limitations.

## Workflow Diagram

```
fetch
  └→ extract ~15 postings (LLM, Stage 1)
       ├→ label tiers BLIND on those spans (~150 claims)  ─┐
       │    └→ re-label 30 blind → annotator self-agreement │
       ├→ spot-check extraction by hand (2–3 postings)      │
       └→ classify (LLM, Stage 2) ─────────────────────────┴→ compare_labels.py
                                                                   ↓ (if above noise floor)
                                                   full corpus → aggregate.py → write-up
```
