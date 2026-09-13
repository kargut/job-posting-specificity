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

## 2. Test Set **[MEASURED]**

- Postings sampled: **15** (balanced across board, region and seniority)
- Claims labeled: **150** (cap of 10 per posting, sampled from 745 extracted)
- Labeling protocol: tiers adjudicated on Stage 1 spans, blind to
  `predicted_tier`, via `eval/label_claims.py`
- Annotators: 1
- Label file audit: `python eval/label_claims.py --verify eval/labeled.jsonl`
  — 0 errors

### Label distribution

| Tier | Claims | Share |
|---|---|---|
| 1 — Concrete | 61 | 41% |
| 2 — General direction | 89 | 59% |
| 3 — Empty slogan | **0** | **0%** |

Overall specificity across the labeled set: **0.407**. Per-posting scores range
0.00–0.90, median 0.30, so the metric does discriminate between documents.

Label-quality signals: all 89 Tier 2 reasonings were typed by hand rather than
accepting the default, and the 61 Tier 1 claims carry 54 distinct quoted spans.
Particular types cited: named tech 27, number 10, unlabeled 9, credential 9,
named place 6.

## 3. Per-Claim Agreement

> **Tier 3 metrics are not reportable on this corpus.** No claim in the labeled
> set is Tier 3 (see section 5), so Tier 3 precision, recall and F1 are undefined
> and the three-class confusion matrix has an empty row. Per-tier figures below
> cover Tiers 1 and 2 only.

- Overall accuracy: —
- 95% CI: —
- Tier 1 precision / recall / F1: —
- Tier 2 precision / recall / F1: —
- Tier 3 precision / recall / F1: **n/a — no Tier 3 in the gold set**

## 4. Tier 1 / Other Boundary

(The only distinction the specificity score depends on)

- Accuracy: — (target: above 80% **and** above annotator self-agreement)
- Tier 1 precision: — (target ≥ 0.85)
- Tier 1 recall: —
- F1: —
- 95% CI on accuracy: —
- Confusion matrix: —

## 5. Extraction Spot-Check (qualitative) **[MEASURED]**

Extraction is assessed by reading postings against their extracted claims.
Span-matching F1 is deliberately out of scope — see the limitations.

### Mechanical checks, all 15 postings / 745 claims

| Check | Result |
|---|---|
| Claims whose text is verbatim in its posting | **745 / 745 (100%)** |
| Claims matching boilerplate patterns (EEO, accommodations, "apply") | **0** |
| Claims missing `claim_id` or `text` | 0 |
| Duplicate `claim_id` within a posting | 0 |
| Duplicate claim text within a posting | 0 |
| Claim length (chars) | median 71, p90 130, max 257 |
| Claims over 240 chars (whole paragraphs) | 1 |

100% verbatim is the load-bearing number: claims are paired with hand labels by
exact normalized text, so a paraphrased span could never be matched and would
drop out of the evaluation silently.

### Consistency across four separate chat sessions

Per-posting claim counts run 27–80, which is document length, not extractor
drift. Normalised by body length:

| Batch | n | median claims / 1,000 chars | range |
|---|---|---|---|
| batch1 | 4 | 8.2 | 7.2–8.5 |
| batch2 | 4 | 8.0 | 6.4–9.2 |
| batch3 | 3 | 7.4 | 5.6–7.4 |
| batch4 | 4 | 10.2 | 6.4–11.9 |
| **overall** | 15 | **8.1** | 5.6–11.9 (2.1×) |

Within-batch ranges overlap, so the prompt held its behaviour across four
independent sessions. Batch 4 sits high on two postings from one employer whose
copy genuinely packs numbers densely (`Over 100,000 businesses`,
`US$130bn+ processed annually`, `across 30+ countries` are correctly three
claims, not one).

### What extraction missed — read against the source

Two postings read sentence by sentence against their claims:

| Posting | Claims | Sentences ≥45 chars | Uncovered | of which boilerplate | of which real content |
|---|---|---|---|---|---|
| A (51-claim, fintech) | 51 | 58 | 25 | 3 | 22 |
| B (42-claim, infrastructure) | 42 | 57 | 22 | 6 | 16 |

**Boilerplate was dropped correctly** — EEO statements, accommodation notices,
privacy commitments, application instructions, and the "studies show women and
people of colour might hesitate to apply" paragraph.

**The uncovered remainder is overwhelmingly mission and atmosphere language:**

```
We're on a mission to make money work for everyone.
We're waving goodbye to the complicated and confusing ways of traditional banking.
At <company>, we are on a mission to help build a better Internet.
We're a highly ambitious, large-scale technology company with a soul.
```

These are Tier 3 claims by the taxonomy's own deletion test, and they were not
extracted. See "Known bias" below.

**Two genuine misses** were real responsibility claims, not slogans:
`You will be responsible for safeguarding our systems, applications, and data by
ensuring secure…` and `Security engineers take part in a wide variety of tasks
and projects in the team.` Stage 1 skips some responsibility prose.

### Confirmed after labeling: Tier 3 was never observed

Predicted as a bias, measured as a total absence. **0 of 150 labeled claims are
Tier 3.** Two independent causes, and only the first was anticipated.

**Cause 1 — extraction suppresses company slogans.** Only **17 of 745** extracted
claims (2.3%) match slogan patterns, and just 4 reached the 150-claim sample.
The source postings are full of this language; Stage 1 drops it as atmosphere.
The claims never reached the annotator, so Tier 3 could not be chosen.

**Cause 2 — the Tier 1 rule made Tier 3 harder to reach.** Tier 1 was given a
mechanical test ("quote the particular"); the Tier 2 / Tier 3 boundary was left to
the deletion test in prose. Sharpening one boundary destabilised the other. The
same claim shapes that `posting_A` labeled Tier 3 *before* the rule existed now
land in Tier 1 or 2:

| Claim shape | `posting_A` (pre-rule) | New blind set |
|---|---|---|
| "Ability to communicate results clearly and focus on impact" | Tier 3 | — |
| "Excellent written and verbal communication skills in English" | — | **Tier 1**, `credential: "English"` |
| "Strong communication skills — you can clearly articulate technical…" | — | Tier 2 |
| "Ability to work with urgency and focus while adapting…" | — | Tier 2 |
| "strong problem-solving under pressure" | Tier 3 | — |

**This exposes a false-positive class in the Tier 1 rule.** Any generic
requirement containing a quotable-but-uninformative noun escapes Tier 3:
`English` is a named language, not a checkable particular about *this* job —
nearly every posting in the corpus requires it. The same applies to the
employer's own name: 4 Tier 1 claims are justified by quoting `Stripe` in a
Stripe posting, of which only `Stripe Terminal` (a named product) is clearly
defensible.

### What this means for the numbers

The reported 0.407 is an overestimate on **two** counts, both pushing the same
way:

1. Tier 3 is missing from the denominator, so `specificity` is in practice
   `tier_1 / (tier_1 + tier_2)` on this corpus, not the three-tier ratio the
   taxonomy defines.
2. Tier 1 is over-populated by the false-positive class above.

Between-posting comparisons survive — both biases apply uniformly — but absolute
scores should not be quoted as measurements of slogan content.

### The fix, deliberately deferred

Two changes, neither made for this release:

1. **Stage 1** must extract mission and culture statements instead of treating
   them as atmosphere. Prompt change plus a re-run.
2. **The taxonomy needs a mechanical Tier 3 test symmetric with Tier 1's**, plus
   an explicit non-particulars list — the employer's own name, `English`, bare
   skill nouns — so a quotable token that is not job-specific cannot lift a claim
   out of Tier 3.

Labels were **not** retro-edited after this analysis. Changing blind labels once
the pattern is visible is the same anchoring failure the protocol exists to
prevent; the finding is documented instead.

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
- [x] Extraction spot-checked against the source (section 5)
- [ ] Tier 3 observable at all — **FAILS on this corpus (0 of 150)**; scored as a
      two-tier metric, see section 5
- [ ] Cost per 1,000 postings measured
- [ ] Latency per posting measured
