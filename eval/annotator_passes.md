# Intra-annotator consistency: `posting_A`

The same 36 model-extracted claims from one real eval posting, referred to as `posting_A` (large US fintech, senior individual-contributor role — the id-to-pseudonym mapping stays in the local, gitignored label file) were tier-labeled twice
by the same annotator, on 2026-09-10 (pass 1) and 2026-09-11 (pass 2), before any
written decision rule existed. No company is named here, per the project's
aggregate-only rule.

| Measure | Value |
|---|---|
| Claims | 36 |
| Exact-tier agreement between passes | 75.0% (9 changed) |
| Tier 1 / Other boundary agreement | 80.6% (7 crossed) |
| Specificity score, pass 1 | 0.333 (T1=12, T2=19, T3=5) |
| Specificity score, pass 2 | 0.472 (T1=17, T2=12, T3=7) |

The headline score moved 42% in relative terms with no change to the document and
no change to the taxonomy — only to the annotator's unwritten sense of the
Tier 1 boundary. This sets the ceiling on what model/human agreement can mean:
a classifier at 80% boundary agreement is at the annotator's own noise floor.

## Pass 1 tiers (by claim_id)

1:2  2:1  3:1  4:2  5:2  6:2  7:2  8:2  9:2  10:2 11:2 12:2
13:2 14:1 15:2 16:1 17:2 18:1 19:2 20:2 21:2 22:3 23:2 24:1
25:1 26:1 27:1 28:3 29:1 30:3 31:3 32:2 33:1 34:1 35:2 36:3

## Claims that moved

| id | pass 1 | pass 2 | pass 2 reasoning given |
|---|---|---|---|
| 1  | 2 | 1 | "checkable tooling" |
| 5  | 2 | 1 | "clear work assignment" |
| 8  | 2 | 1 | "expert work" |
| 15 | 2 | 1 | "expert work" |
| 20 | 2 | 1 | "work in teams" |
| 21 | 2 | 1 | "work in teams" |
| 23 | 2 | 3 | "general IT" |
| 26 | 1 | 2 | "Vague degree requirement" |
| 32 | 2 | 3 | "general IT" |

## Reproducing these numbers

```bash
python eval/compare_labels.py eval/labeled_pass1.jsonl eval/labeled_pass2.jsonl \
    --self-agreement
```

Both passes now live in their own files. `eval/labeled.jsonl` holds only the
blind gold set (15 postings, 150 claims, all `blind: true`), so nothing
non-blind can leak into a model-agreement number.

| | value |
|---|---|
| Exact-tier agreement | 77.8% |
| Tier 1 / Other agreement | 83.3% |

These differ slightly from the 75.0% / 80.6% quoted above because
`labeled_pass1.jsonl` carries one deliberate correction — claim 26 moved to
Tier 2, the escape hatch. The raw pass-1 tiers are listed above; quote
**75.0% / 80.6%** as the pre-rule noise floor, since that is the honest
before-and-after on identical labels.

`--self-agreement` is required: without it `compare_labels.py` refuses a
predictions file carrying no `predicted_tier`, because comparing labels to
labels silently produces a flattering number.

## Post-rule self-agreement — MEASURED 2026-09-14

50 claims from the blind gold set, re-labeled blind a day after the first pass,
under the written Tier 1 rule.

```bash
python eval/label_claims.py --pass 2 --shuffle --relabel \
    --out eval/labeled_pass2_blind.jsonl --limit 50
python eval/compare_labels.py eval/labeled.jsonl eval/labeled_pass2_blind.jsonl \
    --self-agreement
```

| Measure | Pre-rule | Post-rule | Change |
|---|---|---|---|
| Exact-tier | 75.0% (n=36) | **86.0%** [74, 93] (n=50) | +11.0pp |
| Tier 1 / Other | 80.6% (n=36) | **96.0%** [87, 99] (n=50) | +15.4pp |

Changed tiers: 7 of 50 — confusion 1→1 20, 1→2 2, 2→2 23, 2→3 5. Five of the
seven are Tier 2 → Tier 3, which is why `RESULTS.md` section 5 now treats
annotator drift as the dominant cause of the Tier 3 absence.

**Not a controlled experiment.** Pre-rule is one posting under an earlier
extraction run; post-rule is 50 claims across 15 postings from the current run.
The rule changed and so did the corpus. The move is large enough to attribute
mostly to the rule, but not cleanly measurable as such.

**Consequence.** The noise floor this project measures against moved from 80.6%
to 96.0%, which inverts the comparison with the classifier: the model's 86.7%
beat the pre-rule floor by +6.1pp and loses to the post-rule floor by 9.3pp
(-8.0pp on matched claims). See `RESULTS.md` section 4.

Six of the seven changes independently landed on the model's answer, with no
Stage 2 output ever shown for these claims — see `RESULTS.md` section 7.
