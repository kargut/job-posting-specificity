<!-- 1. Paste this note at the top of the post, right under the challenge line. -->

> **Update, 7 October 2026:** the benchmark now runs all 20 briefs. The one-brief results below did not hold up. See [Update: 20 briefs](#update-20-briefs) at the end.

<!-- 2. Paste this section at the end of the post, after "My Benchmark". -->

## Update: 20 briefs

The first leaderboard ran one brief. I wrote that it was a direction to check, not a result. So I checked it. I ran all 20 briefs, from intern to principal, with the same judge and the same prompts.

{% embed https://www.kaggle.com/benchmarks/karlisgutans/job-ad-specificity-20-what-llms-commit-to/leaderboard %}

| Model | 1 brief | 20 briefs | Cost, 20 briefs | Time, 20 briefs |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash | 0.48 | **0.48** | $1.31 | 16 min |
| Claude Haiku 4.5 | 0.50 | **0.37** | $0.91 | 12 min |
| Gemini 2.5 Flash | 0.37 | **0.28** | $1.49 | 21 min |
| GPT-5.4 mini | 0.35 | **0.19** | $1.19 | 14 min |
| Grok 4.5 | error | error | — | — |

Cost and time cover the full run: 20 ads plus 40 judge calls, as Kaggle reports them.

**What changed:**

- **The two pairs are gone.** One ad put Claude Haiku 4.5 and Gemini 3.7 Flash level at about half. Over 20 ads, the four models sit on four separate steps, from 0.48 down to 0.19.
- **Only one model held still.** Gemini 3.7 Flash scored 0.48 on one ad and 0.48 on twenty. Every other model dropped. GPT-5.4 mini dropped the most, from 0.35 to 0.19.
- **The spread is wide.** Gemini 3.7 Flash makes almost one claim in two concrete. GPT-5.4 mini makes fewer than one in five. Same briefs, same judge, and a 2.5 times difference in how much each model invents.
- **The first brief was an easy one to be concrete about.** It was a junior backend engineer, and it asked for languages and data stores. That topic invites named tools. A brief for an engineering manager or a technical writer gives a model less to name. This is my reading, not a measured result: I have not yet broken the scores down per brief.
- **Grok 4.5 failed again.** The task publishes no score unless every brief is scored. At least one Grok brief failed in both runs.

**What it cost.** A full run cost $0.91 to $1.49 per model and took 12 to 21 minutes. Claude Haiku 4.5 was both the cheapest and the fastest.

**The lesson.** The first post already said not to read one ad as a ranking. The 20-brief run shows why. One ad per model is a demo. Twenty is the start of a benchmark.

**Still open:**

- The spread across briefs, so the gaps between models get an interval.
- What each model does with pay: an invented number, a placeholder, or "competitive".
- A hand check of the judge on generated ads.
