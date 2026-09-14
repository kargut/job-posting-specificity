---
title: "Scoring job ads with an LLM: the model was the easy part"
published: false
tags: ai, llm, machinelearning, showdev
canonical_url:
---

<!--
Draft for dev.to. Iterate here, publish from here.

Alternate titles:
- "I measured how much of a job ad actually says something. Then I measured myself."
- "Before you report LLM agreement, measure the human twice"

Alternate tags (max 4 on dev.to): career, datascience, python, evaluation
Rule check: no company is named anywhere in this post. Keep it that way.
-->

Every job ad makes claims. Most of them say nothing.

"Competitive salary." "Fast-paced environment." "You will own your work." Delete those sentences and the ad loses no information. Next to them sit real commitments: a salary band, a named database, two days a week in the office, on-call one week in six.

I wanted a number for that ratio. Specifically: what proportion of a posting is concrete commitment, and can it be measured consistently enough to compare postings against each other?

The pipeline took a weekend. Trusting its output took considerably longer.

## The pipeline

Three stages, deliberately separate so each can be evaluated on its own:

| Stage | What | How |
|---|---|---|
| 1 — Extraction | Split a posting into discrete claims | LLM |
| 2 — Classification | Assign each claim a tier | LLM |
| 3 — Aggregation | Scores and rollups | Deterministic Python |

The taxonomy carries the whole project:

- **Tier 1 — Concrete:** contains a number, a named technology, a timeframe, or a falsifiable commitment. `EUR 60k`. `Go and PostgreSQL`. `team of nine`.
- **Tier 2 — General direction:** real intent, no checkable detail. `We invest in developer growth`. `modern stack`.
- **Tier 3 — Empty slogan:** would fit any ad for any job at any company. `fast-paced`. `rockstar developer`.

Score: `tier_1 / all scored claims`, per posting. A proportion rather than a count, so a 200-word ad and a 2,000-word ad stay comparable.

Corpus: 2,176 postings from 11 public Greenhouse boards, filtered down to 780 software-and-adjacent roles. Public job board APIs only, no scraping. Gold set: 15 postings, 150 claims, hand-labeled blind. No company is named anywhere in the results.

## The number

Mean specificity across the gold set: **0.407**. Per posting it runs 0.00 to 0.90, median 0.30.

So roughly four claims in ten name something checkable. The spread matters more than the mean: the metric separates postings from each other, which is the minimum bar for it being worth anything.

I am not going to defend 0.407 as an absolute measurement. The rest of this post is why.

## Measuring the annotator before the model

The standard recipe for an LLM evaluation is to hand-label a gold set and report agreement. I did that. Then, before writing down a single accuracy number, I labeled 36 of the same claims a second time, a day apart, blind to my first pass.

I agreed with myself on **75.0%** of exact tiers and **80.6%** of the Tier 1 boundary — the distinction the score actually rests on.

The specificity score of that one posting moved from 0.333 to 0.472 between passes. Forty-two percent relative movement, on a document that had not changed a character.

My quality gate was "at least 80% on the Tier 1 boundary". The gate was sitting on the noise floor. A model clearing it would have been indistinguishable from one merely as inconsistent as I am.

### The fix was a written rule, not a better prompt

Tier 1 became a mechanical test: **quote the particular.** A claim is Tier 1 only if you can point at a number, a named technology, a named place, an explicit timeframe, or a quantified policy. Seriousness of the work is not a criterion. "Expert work" and "works closely with the security team" name nothing checkable. Both are Tier 2.

Then I enforced the rule in tooling. The labeler refuses a Tier 1 whose reasoning does not literally quote a substring of its own claim. Run against my drifted pass, the linter flags 34 errors.

A blind 50-claim re-label after the rule:

| Measure | Pre-rule | Post-rule |
|---|---|---|
| Exact tier | 75.0% | **86.0%** |
| Tier 1 boundary | 80.6% | **96.0%** |

**Plus 15.4 points on the boundary, from writing the definition down properly.** That is the largest single result in the project, and no model call was involved in producing it.

## The model loses to the human

With a trustworthy floor, the classifier numbers mean something:

| Measure | Value | 95% CI |
|---|---|---|
| Exact-tier accuracy | 76.7% | 69–83 |
| **Tier 1 boundary accuracy** | **86.7%** | 80–91 |
| Tier 1 precision / recall | 0.902 / 0.754 | |

Against the pre-rule floor of 80.6%, the model looked six points better than the human. Against the re-measured floor of 96.0%, it sits nine points below.

Same model output. Opposite conclusion. **Which floor you pick decides the answer**, and most write-ups never publish a floor at all.

One result points the other way, and a reader should weigh it. In the blind post-rule pass I changed 7 tiers, and **6 of those 7 landed on the model's answer** — without ever seeing the model's output. Part of the measured disagreement is my gold set being wrong, not the model.

## The bug that made the headline metric inert

A posting's Tier 1 claims are not all about the job. A philanthropy section passes the mechanical test effortlessly: named programmes, named products, round numbers, nothing promised to the candidate. So Stage 1 tags every claim with a section, and Stage 3 reports a role-context score separately from an all-claims score.

The Stage 2 ingest built its lookup as `{claim_id: text}`. The section tag was dropped on the floor. Every claim defaulted to role context, employer claims came back as 0 on all 15 postings, and the headline score was byte-identical to the all-claims score.

Two numbers that are designed to differ were the same number, silently, for days. What caught it was a warning I had written into the aggregator months earlier and never once triggered.

After the fix: 28 of 150 claims (18.7%) are employer context. The mean moves 0.3400 to 0.3325, which is nothing. Per posting it moves up to 0.125 in both directions, which is not nothing: 0.500 to 0.375 one way, 0.400 to 0.500 the other.

The lesson I would take from it: **a derived metric that never disagrees with its baseline is not a metric yet.** Assert on the difference.

## Tier 3 never fired

Zero of 150 gold claims landed in Tier 3. The tier built for empty slogans, run over a corpus of job ads, found nothing.

Two causes, both upstream of the classifier:

1. **Stage 1 drops slogans as atmosphere.** Mission and culture language never reaches the annotator at all. A Stage 1 error is invisible to a Stage 2 metric.
2. **Sharpening one boundary destabilised another.** Tier 1 got a mechanical test. Tier 3 kept a prose test. `Excellent written and verbal communication skills in English` became **Tier 1** on the quoted token `English` — a named language, not a particular about this job.

The blind re-label makes it sharper. The same annotator, the same written rules, a day later, produced 5 Tier 3 labels in 50 claims. A 0% rate and a 10% rate are both consistent with the taxonomy as written. That is a worse problem than an unused tier, and I shipped it as a documented finding rather than patching it into looking good.

The consequence is stated in the README: on this corpus the score is in practice `tier_1 / (tier_1 + tier_2)`, inflated twice over. Comparisons between postings survive, because the bias runs the same direction for all of them. Absolute values must not be quoted as measurements of slogan content.

## Three data bugs, one of which invalidated a week of statistics

None of these are LLM problems. All three would have changed a published number.

- `--limit 25` plus `jobs[:limit]` took an alphabetical slice, not a sample. Every posting pulled from one board had a title starting with "A". Every per-board statistic produced before I found it was invalid.
- Seniority was inferred from title plus body, so "you will lead incident response" made 268 of 781 postings senior. Now it reads the title first, with an audited minimum-years fallback.
- The fetcher deduplicated on a content hash, so a posting re-fetched after an employer edited it was stored twice. Now it dedupes on id, newest wins.

## Cost

Measured from the artifacts of the real run — batch files, prompt files, model output — at roughly four characters per token, then scaled. This is payload, not billed tokens: no cache accounting, no API overhead. Treat it as plus or minus 15% and as a floor.

| Per 1,000 postings | Input | Output |
|---|---:|---:|
| As run (10 sampled claims per posting) | 5.10M | 2.81M |
| All claims classified | 7.04M | 6.43M |

The number worth acting on: **the prompt is about 61% of all input tokens**, and 76% at Stage 2, where the payload is a short list of claim spans sitting next to a long taxonomy. Prompt caching and batch size are the entire cost story here. Batching alone, at 3.75 postings per call, halved my first estimate.

Latency I cannot report honestly. The run was driven through a chat interface rather than an API client, so wall-clock time measures my typing speed.

## What the score does not measure

- **Not honesty.** A precise promise can be broken. A vague ad can conceal a good job.
- **Not quality.** Some excellent employers write badly.
- **Not intent.** Most filler is copied from a template by someone who did not choose it.

And the method's own limits, stated plainly. One annotator, so there is no inter-annotator agreement, only intra-annotator. Gold tiers sit on model-extracted spans, so an extraction error cannot be counted wrong. 150 claims, so roughly 7 points of confidence interval at 95% — an improvement of a few points is not a claim this set can support. The scope filter matches words rather than functions: I audited three borderline titles by hand, one was a genuine false positive, and the fix went into the rule instead of a hardcoded exclusion list.

## What I would tell someone building the same thing

- Label a slice twice, blind, before you write down any accuracy number. Your own self-agreement is the ceiling, and it is lower than you think.
- Write the boundary rule as a mechanical test, then enforce it in code. The linter that refuses an unquoted Tier 1 was worth more than every prompt iteration combined.
- Log a warning when two metrics that should differ do not.
- Publish the result that makes you look worse. The model losing to the human is the only number here a reader can actually use.

Code, prompts and the full evaluation report: [github.com/kargut/job-posting-specificity](https://github.com/kargut/job-posting-specificity)

How do you establish a floor before reporting LLM agreement numbers, or do you report against the model's own run-to-run consistency instead?
