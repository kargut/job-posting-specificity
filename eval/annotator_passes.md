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

The figures above use **raw pass-1 tiers**, listed above. The gold file
`eval/labeled.jsonl` now holds pass 1 **plus one deliberate correction** —
claim 26 moved to tier 2, because "or related field, or equivalent experience"
dissolves the requirement. So re-running the comparison against the current gold
gives slightly different numbers:

```bash
python eval/compare_labels.py eval/labeled.jsonl eval/labeled_pass2.jsonl \
    --self-agreement
```

| | raw pass 1 vs pass 2 | current gold vs pass 2 |
|---|---|---|
| Exact-tier agreement | 75.0% | 77.8% |
| Tier 1 / Other agreement | 80.6% | 83.3% |

The gap is that single correction, not drift. Quote the left column as the
pre-rule noise floor.

`--self-agreement` is required: without it `compare_labels.py` refuses a
predictions file that carries no `predicted_tier`, because comparing labels to
labels silently produces a flattering number.
