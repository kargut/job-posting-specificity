---
title: "Before you report LLM agreement, measure the human twice"
published: true
url: https://dev.to/kargut/before-you-report-llm-agreement-measure-the-human-twice-1fn5
tags: ai, llm, python, machinelearning
---

<!--
Published 2026-09-14:
https://dev.to/kargut/before-you-report-llm-agreement-measure-the-human-twice-1fn5
The live post is the source of record; this file is the repo copy.

Rule check: no company is named anywhere in this post. Keep it that way.
-->

I set out to score how much of a job ad is a real commitment. The number I got is not the interesting part. The interesting part is that I agreed with myself only 75% of the time until I wrote the rule down.

"Competitive salary." "Fast-paced environment." "You will own your work." Delete those sentences and the ad loses no information. Next to them sit real commitments: a salary band, a named database, two days a week in the office, on-call one week in six.

The extract-classify-score loop was a weekend. Getting a number I would stand behind was not.

Code, prompts and the full evaluation report: [github.com/kargut/job-posting-specificity](https://github.com/kargut/job-posting-specificity)

## What a claim looks like

Three stages, deliberately separate so each can be evaluated on its own:

| Stage | What | How |
|---|---|---|
| 1 — Extraction | Split a posting into discrete claims | LLM |
| 2 — Classification | Assign each claim a tier | LLM |
| 3 — Aggregation | Scores and rollups | Deterministic Python |

- **Tier 1 — Concrete:** contains a number, a named technology, a timeframe, or a falsifiable commitment. `EUR 60k`. `Go and PostgreSQL`. `team of nine`.
- **Tier 2 — General direction:** real intent, no checkable detail. `We invest in developer growth`. `modern stack`.
- **Tier 3 — Empty slogan:** would fit any ad for any job at any company. `fast-paced`. `rockstar developer`.

Score: `tier_1 / all scored claims`, per posting. A proportion rather than a count, so a 200-word ad and a 2,000-word ad stay comparable.

On 15 ads, about 4 in 10 claims were checkable — and that number is an overestimate. The gold set is 15 postings, 150 claims, hand-labeled blind, sampled from public Greenhouse job board APIs. No scraping, and no company is named anywhere in the results. Per posting the score runs 0.00 to 0.90, median 0.30, so the metric does separate documents. I am not quoting the 0.407 gold-set mean as a measurement of how specific job ads are. The rest of this post is why that figure is inflated.

Four claims, anonymised, under the rule as written:

| Claim | What you can quote | Tier |
|---|---|---|
| `EUR 60–75k, band 4` | `EUR 60–75k` | 1 |
| `We invest in developer growth` | — | 2 |
| `Excellent written and verbal communication skills in English` | `English` | 1 — a named language, not a particular about this job |
| `fast-paced environment` | — | never extracted: Stage 1 drops slogans as atmosphere |

The third row is a real gold label. The fourth never reaches the annotator at all. Both are why "about 4 in 10" overstates how much of an ad is a checkable commitment.

## Measure the human twice

The standard recipe for an LLM evaluation is to hand-label a gold set and report agreement. I did that. Then, before writing down a single accuracy number, I labeled 36 of the same claims a second time, a day apart, blind to my first pass.

I agreed with myself on **75.0%** of exact tiers and **80.6%** of the Tier 1 boundary — the distinction the score actually rests on.

The specificity score of that one posting moved from 0.333 to 0.472 between passes. Forty-two percent relative movement, on a document that had not changed a character.

My quality gate was "at least 80% on the Tier 1 boundary". The gate was sitting on the noise floor. A model clearing it would have been indistinguishable from one merely as inconsistent as I am.

### The fix was a written rule, not a better prompt

Tier 1 became a mechanical test: **quote the particular.** A claim is Tier 1 only if you can point at a number, a named technology, a named place, an explicit timeframe, or a quantified policy. Seriousness of the work is not a criterion. "Expert work" and "works closely with the security team" name nothing checkable. Both are Tier 2.

Then I enforced the rule in tooling. The labeler refuses a Tier 1 whose reasoning does not literally quote a substring of its own claim. Run against my drifted pass of 36 claims, the linter flags **34 errors**.

A blind 50-claim re-label after the rule:

| Measure | Pre-rule (n=36, one posting) | Post-rule (n=50, 15 postings) |
|---|---|---|
| Exact tier | 75.0% | **86.0%** |
| Tier 1 boundary | 80.6% | **96.0%** |

The floor moved a lot after the rule. The samples are not matched — 36 claims from one posting under an earlier extraction, versus 50 claims across 15 postings from the current run — so do not treat +15.4pp as a causal estimate. Consistency improved. That is the claim. No model call was involved in producing it.

## Same model output, opposite conclusion

With a floor I would actually use, the classifier numbers mean something:

| Measure | Value | 95% CI |
|---|---|---|
| Exact-tier accuracy | 76.7% | 69–83 |
| **Tier 1 boundary accuracy** | **86.7%** | 80–91 |
| Tier 1 precision / recall | 0.902 / 0.754 | |

Against the pre-rule floor of 80.6%, the model looked six points better than the human. Against the re-measured floor of 96.0%, it sits nine points below.

Same model output. Opposite conclusion. **Which floor you pick decides the answer**, and most write-ups never publish a floor at all.

Against my second-pass ceiling the model loses; against the labels I later recanted, part of the loss is me. In the blind post-rule pass I changed 7 tiers, and **6 of those 7 landed on the model's answer** — without ever seeing the model's output.

## Tier 3 never fired

Zero of 150 gold claims landed in Tier 3. The tier built for empty slogans, run on these 15 job ads, found nothing.

Two causes, both upstream of the classifier:

1. **Stage 1 drops slogans as atmosphere.** Mission and culture language never reaches the annotator at all. A Stage 1 error is invisible to a Stage 2 metric.
2. **Sharpening one boundary destabilised another.** Tier 1 got a mechanical test. Tier 3 kept a prose test. That is the `English` row in the table above: a quotable token that is not a particular about the job.

The blind re-label makes it sharper. The same annotator, the same written rules, a day later, produced 5 Tier 3 labels in 50 claims. A 0% rate and a 10% rate are both consistent with the taxonomy as written. That is a worse problem than an unused tier, and I shipped it as a documented finding rather than patching it into looking good.

The consequence: on this gold set the score is in practice `tier_1 / (tier_1 + tier_2)`, inflated twice over. Comparisons between postings survive, because the bias runs the same direction for all of them. Absolute values must not be quoted as measurements of slogan content.

## A slice that was not a sample

`--limit 25` plus `jobs[:limit]` took an alphabetical slice, not a sample. Every posting pulled from one board had a title starting with "A". Every per-board statistic produced before I found it was invalid. Not an LLM problem; it would have changed a published number.

Cost, from the run artifacts: the prompt is about 61% of all input tokens, 76% at Stage 2, so caching and batch size are the whole story — batching at 3.75 postings per call halved my first estimate.

## What the score does not measure

- **Not honesty.** A precise promise can be broken. A vague ad can conceal a good job.
- **Not quality.** Some excellent employers write badly.
- **Not intent.** Most filler is copied from a template by someone who did not choose it.
- **Not slogan content.** The 0.407 mean is an overestimate on two counts, both pushing the same way: missing Tier 3 in the denominator, and false-positive Tier 1s like `English`.

The method's own limits, stated plainly. One annotator, so there is no inter-annotator agreement, only intra-annotator. Gold tiers sit on model-extracted spans, so an extraction error cannot be counted wrong. 150 claims, so roughly 7 points of confidence interval at 95% — an improvement of a few points is not a claim this set can support. The scope filter matches words rather than functions: I audited three borderline titles by hand, one was a genuine false positive, and the fix went into the rule instead of a hardcoded exclusion list.

## What I would tell someone building the same thing

- Label a slice twice, blind, before you write down any accuracy number. Your own self-agreement is the ceiling, and it is lower than you think.
- Log a warning when two metrics that should differ do not.
- Write the boundary rule as a mechanical test, then enforce it in code. The linter that refuses an unquoted Tier 1 was worth more than every prompt iteration combined.
- Publish the result that makes you look worse.

Do you measure yourself twice before you report model agreement, or do you only check the model against the model?
