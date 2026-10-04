---
title: "Benchmarking LLMs against an answer key that disagrees with itself"
published: false
tags: devchallenge, kagglechallenge, ai, machinelearning
cover_image:
---

<!--
DRAFT for the Kaggle Benchmarking Challenge. Deadline 11 Oct 2026, 23:59 PDT.
Finish with kaggle/prompts/05_finish_post.md. Every {{PLACEHOLDER}} and every
FILL comment must be gone before publishing. Cover image: upload
kaggle/figures/cover.png in the dev.to editor.
Rule check: no company is named anywhere in this post. Keep it that way.
-->

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23)*

Most benchmarks grade a model against an answer key and treat the key as truth. My answer key is me. I have measured how often I agree with myself on the distinction this benchmark scores: 96% of the time.

So every model here is reported next to that number, on the same claims.

## What I Benchmarked

**Can a model apply a written annotation rule the way the person who wrote it does?**

The items come from an earlier project of mine, [scoring how much of a job ad is a real commitment](https://dev.to/kargut/before-you-report-llm-agreement-measure-the-human-twice-1fn5). Each item is one claim extracted from a job ad. The model puts it in one of three tiers:

- **Tier 1, concrete:** a number, a named technology, a timeframe, a falsifiable commitment. `EUR 60–75k`. `Go and PostgreSQL`.
- **Tier 2, general direction:** real intent, nothing checkable. `We invest in developer growth`.
- **Tier 3, empty slogan:** would fit any ad. `fast-paced environment`.

The headline metric is **Tier 1 boundary accuracy**: does the model draw the line between "concrete" and "everything else" where I drew it? A specificity score rests on that line.

Why this capability? Most LLM work in production looks like this. A person writes a rubric, and a model applies it to text at scale. The rubric's author is the only ground truth, and almost nobody measures the author. Knowledge and reasoning get benchmarks. "Follow my house rule on a judgement call" mostly does not.

### Two tasks, one question

| Task | What the model gets |
|---|---|
| `job-ad-specificity-rule` | The full rulebook as it stood when I labeled the gold set, including one mechanical test: *quote the particular*. The answer includes that quote |
| `job-ad-specificity-definitions` | Tier definitions and examples only: the rulebook before I wrote that test. The answer is a tier and a short reason. This task does not ask for a quote |

The test: a claim is Tier 1 only if you can quote the token that makes it checkable. A number, a named technology, a place, a timeframe. How serious the work sounds is not a criterion.

When I wrote that rule down, my own Tier 1 self-agreement went from 80.6% to 96.0%. The two samples were not matched, so that is not a causal estimate. The pair of tasks asks whether that rule moves a model. Only the rule task is asked to quote a span.

Both prompts come from the repo's git history, at the commits that match my labeling dates. The model gets the rulebook I actually had, not the fixes I wrote down later.

### The data, and what I took out of it

{{N_CLAIMS}} claims, hand-labeled blind. {{N_CEILING}} of them I labeled twice, a day apart. That second pass is the human ceiling, and it is the one comparison in this post where model and human answer exactly the same items.

The claims come from real ads, fetched from public job-board APIs. Anonymisation was the first job, not the last:

- **No claim links to its ad.** Rows carry no posting id, and each ten-claim batch mixes claims from different postings.
- **Names became typed placeholders.** Company, product and award names, people, and employer-level figures like revenue or founding year became `[Employer]`, `[Employer Product]`, `[Figure]`. Role-level numbers stayed: salary bands, years of experience, team size. Those are what Tier 1 is made of.
- **A redaction can change the right answer.** If a claim's only particular was a product name, its label is now at risk. {{N_AT_RISK}} claims were flagged, {{N_DROPPED}} were dropped. No gold label was edited.
- **Two attacks before publishing.** An exact-phrase web search on every employer-describing claim found {{AUDIT_A_HITS}} that led straight to the employer. Then a fresh model, given only the anonymised text, tried to name the employers: {{AUDIT_B_ROUND1}} correct in the first round, {{AUDIT_B_FINAL}} after {{AUDIT_B_ROUNDS}} rounds of further redaction.

The dataset is {{DATASET_VISIBILITY}} on Kaggle. The task code and the leaderboard are public.

## Models Tested

{{N_MODELS}} models, picked to answer three questions rather than to fill a leaderboard.

| Model | Why it is here |
|---|---|
{{MODEL_ROWS}}

<!-- FILL MODEL_ROWS from kaggle/LOG.md step 3 roster: one row per model, "| model | slot: one-line reason |". -->

- **Does any model reach the human ceiling?** The frontier model from each provider on Kaggle's list.
- **Is a mechanical rule cheap to follow?** The small, fast model from the same providers. If the rule really is mechanical, they should not trail far.
- **Does my old number reproduce?** The original pipeline ran through a chat interface. On the {{N_CEILING}} ceiling claims it agreed with my gold labels on 44 of 50; I agreed with myself on 48. Re-running a Claude Opus model through Kaggle tests whether that 88.0% vs 96.0% gap belongs to the method or to one chat session.

Same settings for every model: Kaggle defaults (temperature 0, provider-default reasoning), ten claims per call, the same system prompt.

## Findings

![Tier 1 boundary accuracy per model with 95% intervals, against the human self-agreement band]({{FIGURE_URL}})

| Model | Boundary, rule [95% CI] | Ceiling subset | Rule − definitions | Valid quotes | $ / 1,000 claims |
|---|---|---|---|---|---|
{{RESULT_ROWS}}
| *Me, second blind pass* | — | 48/50 | +15.4pp (unmatched samples) | enforced by my labeling tool | — |

<!-- FILL RESULT_ROWS from kaggle/RESULTS.md headline table. Sort by rule boundary accuracy. Bold every model in the "indistinguishable from the best" group. If step 1 dropped ceiling claims, replace 48/50 with the recomputed value everywhere. -->

With {{N_CLAIMS}} claims an interval is about ±5.5 points wide, so I group rather than rank: {{BEST_GROUP_SENTENCE}}

<!--
FILL the three findings the user chose in LOG step 4, in that order.
Each: a bold one-line claim, then 2–4 short paragraphs with the numbers.
Candidate paragraphs below. Keep the ones that match the results, rewrite
the numbers, delete the rest. Do not keep a branch the data does not support.
-->

### 1. {{FINDING_1_TITLE}}

<!-- CEILING, branch A (no model reaches it):
No model reached my ceiling. The best, {{BEST_MODEL}}, agreed with my gold labels on {{BEST_SUBSET_K}} of the 50 ceiling claims. I agreed with myself on 48. On 50 claims the intervals overlap, so this is a measured gap, not a proven one.
-->
<!-- CEILING, branch B (some reach it):
{{N_AT_CEILING}} models matched my own consistency on the same 50 claims. That does not make them right. It means that on this boundary, my labels stopped being the bottleneck. The rulebook is.
-->

### 2. {{FINDING_2_TITLE}}

<!-- RULE, branch A (rule helps models):
The paragraph that fixed me fixed them. Median move from definitions to rule: {{MEDIAN_DELTA}} points, {{N_SIG}} of {{N_MODELS}} models significant on paired claims (McNemar, discordant counts in the repo). The small models gained most: {{SMALL_DELTA}}.
-->
<!-- RULE, branch B (rule does little):
The rule that moved me fifteen points moved the models {{MEDIAN_DELTA}}. My best guess at why: the rule fixed a human problem, drift between sessions, that a model at temperature 0 does not have. It may also mean the models already arrive with something like the rule. The data here cannot tell those apart.
-->
<!-- RULE, branch C (rule hurts some):
For {{N_WORSE}} models the full rulebook made things worse. {{EXAMPLE_MODEL}} lost {{X}} points, mostly on {{ERROR_SHAPE}}. More rules is not more accuracy.
-->

### 3. {{FINDING_3_TITLE}}

<!-- DISPUTED CLAIMS:
On my second pass I changed 7 of 50 tiers, and 6 of those 7 moved to the original pipeline's answer, without my seeing it. On those seven claims, the Kaggle models sided with my second answer {{K}} times out of {{N}}. When the human and the model disagree, the human is not automatically the one who is right.
-->
<!-- ANSWER-KEY ERRORS:
{{N_ALL_WRONG}} claims were "wrong" for every model. {{N_ALL_WRONG_SUSPECT}} of them are labels I flagged as suspect before any model ran. A benchmark run is a cheap way to find errors in its own answer key. I did not relabel them; editing labels once you have seen the model's answers is the failure blind labeling exists to prevent.
-->
<!-- COST:
{{CHEAPEST_IN_BEST_GROUP}} sits inside the best model's interval at {{COST_RATIO}} of its cost. Kaggle's model proxy reports real tokens, cost and latency per call. My original project estimated cost as characters ÷ 4. The first measured numbers: {{TOKENS_IN_PER_1K}} input and {{TOKENS_OUT_PER_1K}} output tokens per 1,000 claims, {{LATENCY_P50}} median per ten-claim call. The prompt is {{PROMPT_SHARE}} of every input token, so batch size is the cost lever, not the model.
-->
<!-- TIER 3:
Gold has zero Tier 3 claims. A day later, under the same rules, I used Tier 3 on 5 of 50. The models used it on {{T3_RANGE}}. Everyone, me included, is unstable on that boundary, which is why exact-tier accuracy is a floor in this benchmark and boundary accuracy is the headline.
-->
<!-- REPRODUCTION:
Through Kaggle, {{REPRO_MODEL}} scored {{REPRO_K}}/150 on the boundary, against 130/150 from the original chat run. The two runs agreed with each other on {{REPRO_AGREE}} of 150 claims.
-->

### What surprised me

{{SURPRISE}}

Before the full runs I wrote four predictions into the build log. I got {{PRED_RIGHT}} of them right. {{PRED_SENTENCE}}

### What I would measure next

- **A second annotator.** Every number here is agreement with one person. My self-agreement is a ceiling for my labels, not for the truth.
- **A mechanical Tier 3 test.** Tier 1 has one; Tier 3 still has a prose definition, and it shows.
- **Extraction.** This benchmark starts from claims a model already extracted. An extraction error is invisible to it.

### What this benchmark does not measure

- **Truth.** It measures agreement with one person's rulebook.
- **Anything about the employers.** Not honesty, not job quality.
- **General capability.** {{N_CLAIMS}} short claims, one boundary.
- **Difficulty after redaction.** {{N_REDACTED}} of {{N_CLAIMS}} texts were changed by anonymisation, and that can make an item easier or harder.

## My Benchmark

**[Job-ad specificity: rule-following against a measured human ceiling]({{KAGGLE_BENCHMARK_URL}})**

- Tasks: [`job-ad-specificity-rule`]({{TASK_RULE_URL}}) and [`job-ad-specificity-definitions`]({{TASK_DEFINITIONS_URL}})
- Code, prompts, scorer and full results: [github.com/kargut/job-posting-specificity](https://github.com/kargut/job-posting-specificity), under `kaggle/`
- The project behind it: [Before you report LLM agreement, measure the human twice](https://dev.to/kargut/before-you-report-llm-agreement-measure-the-human-twice-1fn5)

### How I built it

Five prompts, run in order by an agent (Claude Opus 5.5). Each one stops at checkpoints and waits for me. They are in the repo under `kaggle/prompts/`, next to the build log the agent kept.

1. **Anonymise.** A private lexicon, typed redaction, a label-at-risk check, two re-identification attacks, a dataset card.
2. **Build.** Prompts pulled from git history. A scorer that had to reproduce the old pipeline's 130/150 and my own 48/50 before any model was called. One template that renders both task files, so they cannot drift apart.
3. **Push and run.** A private dataset, a smoke run on the cheapest model, my approval of the roster, and my predictions in the log before the full runs.
4. **Analyse.** Every run re-scored from raw predictions, stopping if it disagreed with Kaggle's number. No "X beats Y" where the intervals overlap.
5. **Write.** This post, with every number taken from the results file.

{{CHECKPOINT_STORY}}

<!-- FILL CHECKPOINT_STORY from kaggle/LOG.md: one or two sentences on the single moment a checkpoint or golden test caught something real. If nothing was caught, delete the placeholder; do not invent one. -->

What is the ceiling on your eval's answer key, and have you measured it?
