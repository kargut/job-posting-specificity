---
title: "Give an LLM no facts and ask for a job ad. What does it commit to?"
published: https://dev.to/kargut/give-an-llm-no-facts-and-ask-for-a-job-ad-what-does-it-commit-to-2ma5
tags: devchallenge, kagglechallenge, ai, machinelearning
---

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23).*

Job ads are long. The first one I read end to end. After that I scan. I look for the concrete parts: pay, the stack, the team size, where the work happens, what on-call looks like. Everything else is filler I have learned to skip.

I also do not apply because I match every line. I apply when something concrete catches my attention.

More and more of these ads are now drafted by LLMs. So I wanted to know: when a model writes a job ad and is given no facts at all, what does it commit to?

## What I Benchmarked

My main goal was to try Kaggle Benchmarks. I already had a scoring method from an earlier project, so I ported it into a Kaggle notebook. In about two days it went from an empty notebook to a public leaderboard.

**The task.** Every model gets the same brief: a role, a seniority level, and the topics the ad must cover. The brief on the current leaderboard is a junior backend engineer. The ad must cover the service, languages and data stores, code review, team size, location, pay, and the first six months. The brief names no employer and supplies no facts.

The model has three options for every topic:

- **Invent a specific:** "€45,000–55,000", "Go and PostgreSQL", "a team of six".
- **Leave a blank:** "[salary range]".
- **Write around it:** "competitive salary", "a modern stack".

**The judge.** A fixed judge model (Claude Sonnet 4.5, never a contestant) runs two stages:

1. **Extraction:** split the ad into claims, each one an exact substring of the ad.
2. **Classification:** label each claim with one tier.
   - **Concrete:** you can quote a particular. A number, a named tool, a place, a cadence.
   - **General direction:** real intent, nothing checkable. "Flexible hours."
   - **Empty slogan:** fits any ad at any company. "Fast-paced environment."

**The score** is concrete claims divided by all claims, from 0 to 1.

The judge is not trusted on its own. Code enforces the rules after every call:

- A claim that is not a verbatim substring of the ad is rejected.
- A "concrete" label must quote its particular, and that quote must appear in the claim. If not, the claim is demoted to general direction.
- Template blanks like "[salary range]" or "€XX,XXX" are flagged and never count as concrete.
- "English" and bare skill nouns like "communication skills" never count as a particular.

**Higher is not better.** The brief contains no facts, so every concrete claim is made up. The score measures how willing a model is to commit to specifics. Which behaviour you want depends on whether a human fills in the real facts afterwards.

The tier rules come from my earlier project, which scored real job postings. There I measured my own labeling consistency before trusting any model number: [Before you report LLM agreement, measure the human twice](https://dev.to/kargut/before-you-report-llm-agreement-measure-the-human-twice-1fn5).

## Models Tested

I picked the small, fast tier from each vendor. These are the models a company would plug into an HR tool to draft ads at volume. Cost and speed matter there more than peak quality.

| Model | Score | Cost per run | Time per run |
|---|---:|---:|---:|
| Claude Haiku 4.5 | 0.50 | $0.037 | 29 s |
| Gemini 3.7 Flash | 0.48 | $0.062 | 44 s |
| Gemini 2.5 Flash | 0.37 | $0.074 | 60 s |
| GPT-5.4 mini | 0.35 | $0.069 | 45 s |
| Grok 4.5 | error | — | — |

Cost and time are as Kaggle reports them for one run: the ad plus both judge calls. Most of the token count is the judge, not the model under test.

The judge is kept out of the contest on purpose. A model grading its own family's writing is a conflict I did not want to explain.

## Findings

**What one ad looks like.** Gemini 3.7 Flash wrote a 2,528-character ad. The judge extracted 29 claims:

- 14 concrete
- 13 general direction
- 2 empty slogans
- 0 placeholders

No blanks at all. Every topic got either an invented specific or a soft phrase. It never wrote "[salary range]".

**The leaderboard splits into two pairs.** Claude Haiku 4.5 and Gemini 3.7 Flash commit to specifics in about half their claims. Gemini 2.5 Flash and GPT-5.4 mini sit around a third.

**Do not read it as a ranking yet.** The current leaderboard runs one brief, so each score is one ad of roughly 30 claims. For Gemini 3.7 Flash, 14 concrete out of 29 gives a 95% interval of about 0.31 to 0.66. Every model on the board sits inside that interval. The two pairs are a direction to check, not a result.

**The judge is unmeasured on these ads.** On real postings, an earlier version of the rules reached 86.7% agreement with my hand labels on the concrete/not-concrete boundary. That was a different judge model and older prompts. Nobody has hand-checked this judge on generated ads.

**Grok 4.5 failed, and that is by design.** The task refuses to publish a score unless every brief is scored. A partial average across a subset of briefs is a different benchmark, and it would sit on the same leaderboard as if it were not.

**What surprised me on the Kaggle side:**

- A task must return a number, bool or dict. Returning a string fails to store.
- Reasoning models put `<think>` text before their JSON. The built-in schema parser then fails, so the judge parses JSON itself.
- `%choose` keeps only the latest run of the main task. Run it once in the notebook, then add models from the task page.
- Model names contain `/`. Sanitize them before using them in file names.

**Why model choice matters here.** Ads are many and they are long. Getting from an ad to its actual claims takes effort, and that effort goes to a model on both sides. The employer's model decides what gets committed. The candidate's model decides what counts as concrete. Pick the wrong one on the writing side and you get invented salaries. Pick the wrong one on the reading side and "competitive salary" passes as a commitment.

**What I would measure next:**

- **All 20 briefs, several samples each.** The briefs already cover intern to principal, from frontend to production support. One ad per model is not enough.
- **A hand check of the judge** on a sample of generated claims, the same way I checked it on real postings.
- **The split per topic.** Pay is the interesting one: invented number, placeholder, or "competitive".
- **Whether the ad attracts the right people.** This is the metric that matters most, and specificity is only one input to it. It needs outcome data: who applied, and how many were qualified. That data sits with employers and job boards, not in a public benchmark.

## My Benchmark

{% embed https://www.kaggle.com/benchmarks/karlisgutans/job-ad-specificity-what-llms-commit-to/leaderboard %}

Briefs, prompts and judge code are in the notebook. The method behind the tiers is in the repo: [github.com/kargut/job-posting-specificity](https://github.com/kargut/job-posting-specificity).

When you read a job ad, what makes you apply: the concrete details, or something else entirely?
