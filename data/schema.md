# Data Schema

## Raw Postings (`data/raw/raw_postings.jsonl`)

One JSON object per line. Each line is a normalized job posting from any source.

```json
{
  "id": "greenhouse_token_12345",
  "source": "greenhouse_companyname",
  "source_id": 12345,
  "title": "Senior Software Engineer",
  "company": "Company Name",
  "url": "https://...",
  "content": "Full HTML/text of job description",
  "content_hash": "abc123def456",
  "departments": ["Engineering", "Backend"],
  "locations": [
    {"name": "Rīga", "country": "LV"},
    {"name": "Remote", "country": null}
  ],
  "posted_at": "2026-09-01T10:00:00Z",
  "fetched_at": "2026-09-10T15:30:00Z"
}
```

## Labeled Corpus (`eval/labeled.jsonl`)

Human gold labels for the evaluation set. **This file holds blind labels only.**

| File | Contents |
|---|---|
| `eval/labeled.jsonl` | The gold set: 15 postings, 150 claims, every row `blind: true` |
| `eval/labeled_pass1.jsonl` | One posting labeled before the written Tier 1 rule existed, `blind: false`. Kept solely as the first term of the intra-annotator agreement measurement |
| `eval/labeled_pass2.jsonl` | The second pass over that same posting, the other term |
| `eval/labeled_pass2_blind.jsonl` | 50 gold claims re-labeled blind a day later, under the written rule. Second term of the post-rule self-agreement measurement. Never merged into gold |
| `eval/labeled_examples.jsonl` | Three synthetic postings that demonstrate the file format |

Keeping non-blind labels out of `labeled.jsonl` means no model-agreement number
can accidentally be computed against labels made with model output visible. All
four are gitignored — they contain real posting text.

**Tiers are adjudicated on Stage 1's extracted spans, not on independently
extracted claims.** `eval/compare_labels.py` pairs gold and predicted claims by
exact normalized text, so labeling the model's own spans makes pairing exact by
construction and stops gold claims being silently dropped. The trade-off is
stated in the README limitations: extraction errors are invisible to the
boundary metric.

```json
{
  "posting_id": "greenhouse_token_12345",
  "posting_content": "Full job description text",
  "spans_from": "stage1@1.0",
  "label_pass": 2,
  "blind": true,
  "labeled_at": "2026-09-11T13:18:00Z",
  "claims": [
    {
      "claim_id": "claim_1",
      "text": "€60,000–75,000 gross",
      "tier": 1,
      "reasoning": "quotes the particular: \"€60,000–75,000\""
    },
    {
      "claim_id": "claim_2",
      "text": "modern stack",
      "tier": 2,
      "reasoning": "no number, named tech or timeframe"
    }
  ]
}
```

**Provenance fields** (all optional; `compare_labels.py` ignores them, they exist
so a label set can be audited later):

| Field | Meaning |
|---|---|
| `spans_from` | Which extraction run produced the spans being labeled |
| `label_pass` | 1, 2, … — which labeling sitting this is. Needed to compute intra-annotator agreement |
| `blind` | `true` if the annotator could not see `predicted_tier` while labeling. A label set with `blind: false` must not be used for headline numbers |
| `labeled_at` | Timestamp of the pass |

**Reasoning field rule:** for `tier: 1`, the reasoning must quote a substring of
`text`. A Tier 1 reasoning that quotes nothing means the tier was assigned on a
non-criterion — see `prompts/shared_context.md`.

**Tier definitions:**
- **1 (Concrete):** Number, named tech, timeframe, verifiable fact, falsifiable commitment
- **2 (General direction):** Real intent/attribute, no checkable detail
- **3 (Empty):** Generic slogan, could apply to any job

## Extracted Claims (`data/extracted/claims.jsonl`)

Output from Stage 1 (extraction). Model-predicted claims per posting.

```json
{
  "posting_id": "greenhouse_token_12345",
  "model": "claude-opus-5",
  "extraction_prompt_version": "1.0",
  "claims": [
    {
      "claim_id": "extr_1",
      "text": "€60,000–75,000 gross",
      "position": 234
    },
    {
      "claim_id": "extr_2",
      "text": "Go and PostgreSQL"
    }
  ],
  "extracted_at": "2026-09-10T15:30:00Z"
}
```

## Classified Claims (`data/classified/claims.jsonl`)

Output from Stage 2 (classification). Tiers assigned to extracted claims.

```json
{
  "posting_id": "greenhouse_token_12345",
  "model": "claude-opus-5",
  "classification_prompt_version": "1.0",
  "claims": [
    {
      "claim_id": "extr_1",
      "text": "€60,000–75,000 gross",
      "context_section": "compensation",
      "predicted_tier": 1,
      "confidence": 0.98,
      "reasoning": "Explicit salary range is concrete"
    }
  ],
  "classified_at": "2026-09-10T15:30:00Z"
}
```

**On `context_section`:** copied through from Stage 1 by
`eval/ingest_classification.py`, **not produced by the classifier.** Stage 3
partitions role context from employer context on it. If it is absent, every claim
silently defaults to role context and `specificity_score` collapses into
`specificity_score_all_claims` — which is exactly what happened until 2026-09-14.
`aggregate.py` prints a warning naming any value outside the Stage 1 vocabulary;
that warning firing on `(missing)` means the ingest step dropped the field.

**On the `model` field:** when a stage is run through a chat interface, this
records the identifier that interface was configured with, **not a verified
measurement of the serving model** — the model actually serving a turn can differ
and a chat session gives no way to check. Only an instrumented API run can attest
to a version. See `eval/RESULTS.md` section 6.

Acceptable alternate key: `classifications` instead of `claims` (same object shape). `eval/compare_labels.py` and `src/pipeline/aggregate.py` accept either.

## Results (`results/scores.jsonl`)

Aggregated per-posting specificity scores.

`specificity_score` is the **headline** and counts role-context claims only;
`specificity_score_all_claims` counts every claim including the employer's own
company and culture sections. `specificity_score` is `null` — not `0.0` — for a
posting whose every claim is employer context, since averaging a fabricated zero
in would be worse than excluding it. Rollups report `count` and `scored_count`
separately for that reason.

`sector` and `company_size` are present but **not reported** — they are
diagnostics. `company_size` resolved to `unknown` for 143 of 144 postings in the
first corpus, and every board sampled is a software/fintech employer. Only
`seniority` and `region` are rolled up. See `prompts/shared_context.md` →
"Rollups we do not report, and why".

```json
{
  "posting_id": "greenhouse_token_12345",
  "title": "Senior Software Engineer",
  "company": "Company Name",
  "source": "greenhouse_companyname",
  "location_primary": "Rīga",
  "posted_at": "2026-09-01",
  "total_claims": 15,
  "tier_1_claims": 6,
  "tier_2_claims": 7,
  "tier_3_claims": 2,
  "specificity_score": 0.40,
  "specificity_score_all_claims": 0.40,
  "role_claims": 12,
  "role_tier_1_claims": 5,
  "employer_claims": 3,
  "employer_context_share": 0.20,
  "sector": "software",
  "company_size": "50-200",
  "seniority": "senior",
  "region": "baltics"
}
```

## Evaluation Metrics (`eval/RESULTS.md`)

Final evaluation report (human vs model agreement).

> **The numbers in the block below are invented illustrations of the shape of
> the report.** They are not results. Real measured values live in
> `eval/RESULTS.md` and `eval/annotator_passes.md`, and anything not yet
> measured is shown there as `—`. Do not quote these.

```
# Evaluation Results

## Test Set
- Total postings labeled: 50
- Total claims labeled: 723
- Inter-annotator agreement (when applicable): —

## Per-Claim Agreement
- Overall accuracy: 82%
- Tier 1 precision: 0.87
- Tier 1 recall: 0.79
- Tier 2 precision: 0.81
- Tier 2 recall: 0.85
- Tier 3 precision: 0.80
- Tier 3 recall: 0.78

## Tier 1 / Other Boundary
(The main distinction the score depends on)
- Accuracy: 89%
- F1: 0.85
- Confusion matrix: [...]

## Cost & Latency
- Model: claude-opus-5 (chat-configured identifier; see RESULTS.md section 6)
- Cost per 1,000 postings: €2.14
- Tokens per posting (avg): extraction 450, classification 320, total 770
- Wall-clock time per posting: 2.3s

## Disagreements (Hand-picked examples)
[Cases where human and model disagreed; note cases where model was right]
```

## Annotator Consistency (`eval/annotator_passes.md`)

Free-form markdown, not a data file. Records the same claims labeled in two or
more passes by the same annotator, with exact-tier and Tier 1 / Other agreement
between passes, plus the per-claim diff. This measurement bounds what any
human-vs-model agreement number can mean, so it is committed alongside the code
even though `eval/labeled.jsonl` is not.
