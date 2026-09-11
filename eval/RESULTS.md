# Evaluation Results

Sections marked **MEASURED** contain real numbers. Everything else is a
placeholder (`—`) and must not be quoted anywhere until filled by
`eval/compare_labels.py` or a measured run.

```bash
python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl \
  --report eval/RESULTS.md
```

Note: running the command above regenerates this file from the script's template
and will drop the annotator-consistency section below. Keep
`eval/annotator_passes.md` as the source of truth for it and paste it back, or
write the report to a scratch path and merge by hand.

---

## 1. Annotator Consistency — the noise floor **[MEASURED]**

The same 36 model-extracted claims from one real eval posting (`posting_A`;
large US fintech, senior IC role — no company named, per the aggregate-only
rule) were tier-labeled twice by the same annotator, one day apart, **before any
written decision rule existed**.

| Measure | Value |
|---|---|
| Claims | 36 |
| Exact-tier agreement between passes | **75.0%** (9 of 36 changed) |
| Tier 1 / Other boundary agreement | **80.6%** (7 of 36 crossed) |
| Specificity score, pass 1 | 0.333 (T1=12, T2=19, T3=5) |
| Specificity score, pass 2 | 0.472 (T1=17, T2=12, T3=7) |

The headline score moved **42% in relative terms** with no change to the
document and no change to the taxonomy — only to the annotator's unwritten sense
of the Tier 1 boundary.

**Consequence for every model number below:** a classifier at 80% boundary
agreement with these labels is at the annotator's own noise floor and cannot be
distinguished from one that is simply as inconsistent as the human. The original
≥80% quality gate was therefore set at the level of noise.

**What was changed in response:** the Tier 1 boundary was rewritten as a
mechanical test — "name the particular you can quote" — in
`prompts/shared_context.md`, with the six specific reasons that caused the drift
listed as explicit non-criteria ("expert work", "works with named teams",
product category, and so on). Full per-claim diff in
`eval/annotator_passes.md`.

Enforcement, not just documentation: `eval/label_claims.py` refuses a Tier 1
whose reasoning does not quote its claim, and `--verify` reports 34 errors when
run against the drifted pass.

### Post-rule consistency (re-measure after relabeling)

| Measure | Value |
|---|---|
| Claims re-labeled blind | — |
| Exact-tier agreement | — |
| Tier 1 / Other boundary agreement | — (expect > 90% if the rule works) |

---

## 2. Test Set

- Postings sampled: —
- Claims labeled: — (target ~150)
- Claims per posting cap: 10
- Labeling protocol: tiers adjudicated on Stage 1 spans, blind to
  `predicted_tier`, via `eval/label_claims.py`
- Label file audit: `python eval/label_claims.py --verify eval/labeled.jsonl`
- Annotators: 1

---

## 3. Per-Claim Agreement

- Overall accuracy: —
- 95% CI: —
- Tier 1 precision / recall / F1: —
- Tier 2 precision / recall / F1: —
- Tier 3 precision / recall / F1: —

## 4. Tier 1 / Other Boundary

(The only distinction the specificity score depends on)

- Accuracy: — (target: above 80% **and** above annotator self-agreement)
- Tier 1 precision: — (target ≥ 0.85)
- Tier 1 recall: —
- F1: —
- 95% CI on accuracy: —
- Confusion matrix: —

## 5. Extraction Spot-Check (qualitative, not scored)

Extraction is assessed by reading 2–3 postings against their extracted claims.
Span-matching F1 is deliberately out of scope.

- Postings reviewed: —
- Claims missed entirely: —
- Assertions wrongly split / wrongly merged: —
- Boilerplate not dropped: —

## 6. Cost & Latency

- Model: —
- Cost per 1,000 postings: —
- Tokens per posting (avg): extraction —, classification —
- Wall-clock time per posting: —

## 7. Disagreements

Hand-picked cases where human and model disagreed. Note explicitly where the
**model was right and the human wrong** — after section 1, that is a live
possibility and saying so is part of the point.

## Quality Gates

- [ ] Tier 1 boundary accuracy ≥ 80%
- [ ] Tier 1 boundary accuracy above annotator self-agreement
- [ ] Tier 1 precision ≥ 0.85
- [ ] Annotator self-agreement re-measured after the written rule
- [ ] Cost per 1,000 postings measured
- [ ] Latency per posting measured
