# Step 4 — Analyse the runs

Read `kaggle/prompts/00_RUNBOOK.md` and the step 1–3 sections of
`kaggle/LOG.md` first.

## Goal

Turn the downloaded runs into `kaggle/RESULTS.md` and two figures, in the
same style as `eval/RESULTS.md`: every number with its denominator, CIs where
a proportion is reported, and no ranking claim the CIs do not support.

## Inputs

- `kaggle/private/runs/**` — run files, logs and source notebooks
- `kaggle/data_public/claims_anon.csv` — gold and subset flags
- `kaggle/private/id_map.json` + `data/classified/claims.jsonl` — original
  pipeline predictions, for the chat-run comparison
- `kaggle/private/runs/repeat/` — if step 3.5 ran
- The user's pre-registered predictions in `kaggle/LOG.md`

## Step 4.1 — one per-claim table

`kaggle/src/analyze.py` parses every run into one private table
`kaggle/private/per_claim.csv`: model, task variant, claim_uid, pred_tier,
the scorer flags, plus per-batch usage. Prefer the run file's recorded
assertions/results; fall back to `KB_DETAIL` lines. **Re-score from
predictions with `kaggle/src/score.py`** and check both scores. The task's
returned metric must equal `boundary_all`. `KB_SUMMARY`'s answered figure
must equal `boundary_answered`. A mismatch stops the analysis.

Each model × variant must have exactly as many rows as the dataset. A row
with no prediction is `missing`. It counts wrong in the all-claims score and
is excluded from the answered score. Report both counts.

One failed batch is 10 claims. On a 150-claim set that is 6.7 points, which
is larger than the roughly ±5.5 point interval around the boundary. A schema
failure can invent a gap the sample cannot otherwise support. The leaderboard
number still counts those claims wrong, so the failure stays visible. The
comparison across models uses the answered score.

## Step 4.2 — metrics

Per model × variant:

| Metric | Notes |
|---|---|
| Tier 1 boundary accuracy, all claims, Wilson 95% | The number the task returns. Missing claims count wrong. This is the leaderboard value |
| Unanswered claims | `n_unanswered` / n. A failed batch, a missing claim_uid, or a tier that did not parse. This sits in the headline table beside the all-claims accuracy |
| Tier 1 boundary accuracy, answered claims only, Wilson 95% on that denominator | Claims that came back with a tier. This is the number used to group models and to draw the figure. When it differs from the all-claims number, both appear in the headline table |
| Same pair, on the ceiling subset | All-claims and answered, each with its own denominator. The human line stays 48/50 (or the recomputed value from step 1) |
| Same, excluding `preregistered_suspect` rows | Do the suspect labels move the ranking? Drop unanswered rows here too, and say how many were dropped |
| Exact-tier accuracy | A floor: gold has no Tier 3, so every Tier 3 prediction is wrong by construction. Say so in the table caption. Report all-claims and answered |
| Tier 1 precision / recall / F1 | On answered claims. Recall < precision means the model is stricter than the annotator, as the original pipeline was (0.754 / 0.902) |
| Quote validity | **Rule task only.** Share of answered Tier 1 predictions for which `is_quote_of` accepts `quoted_particular`: at least 2 characters after normalize, not a stopword, and a normalized substring of the claim. This is the labeler's check for a quote typed as its own field. It is not `quotes_particular`, and it is not what `label_claims.py --selftest` or `--verify` measure. Definitions rows leave this blank; the model was not asked for a quote |
| Quote agreement with gold | **Rule task only.** Of answered claims both call Tier 1, share where the quoted particulars overlap. Blank on the definitions task |
| Tier 3 rate | Among answered claims. Compare with gold 0/150 and human pass 2: 5/50 |
| Structural errors | unanswered / duplicate / unknown claim_uids, as counts |
| Tokens, cost, latency | Per 1,000 claims, from Kaggle's usage fields. Also per 1,000 postings at the corpus's 745 claims / 15 postings ≈ 49.7 claims per posting — Stage 2 only, say so |

Across models:

1. **Rule vs definitions.** Per model, the boundary-accuracy difference on
   claims **both** variants answered, and an exact McNemar test on those
   paired claims. A claim missing on either side is not a discordant pair.
   Report how many pairs were dropped, and the discordant counts, not just p.
   Put it next to the human's own move (80.6% → 96.0%, unmatched samples, so
   not causal).
2. **The disputed claims.** On the ceiling-subset claims where human pass 2
   changed the tier, how often does each model agree with pass 2 versus gold?
   Skip a model that did not answer that claim. n is small (7 exact, 2
   boundary) — report counts, no percentages.
3. **Where all models disagree with gold.** Claims that every model which
   **returned a tier** on the `rule` task gets wrong on the boundary. An
   unanswered claim is not a wrong tier. How many, how many are
   pre-registered suspects, how many are `label_at_risk` from step 1. These
   are candidates for gold errors, not model errors — but do not relabel.
4. **Comparison with the chat run.** For the Claude Opus model in that slot:
   all-claims boundary and answered boundary, next to the chat run's 130/150,
   plus claim-level agreement on claims the Kaggle run answered. The prompt,
   the batching, and the redacted text all differ. Report the agreement as a
   comparison of two setups. Do not write that the result shows whether the
   old gap was the method or one chat session.
5. **Cost-effectiveness.** Answered boundary accuracy against $ per 1,000
   claims, one point per model. Name the cheapest model whose answered CI
   overlaps the best model's. Do not call a model expensive or cheap because
   one failed batch lowered its all-claims score.
6. **Model self-agreement** (only if step 3.5 ran): exact and boundary
   agreement between the two repeat runs, on the ceiling subset, next to the
   human's 86.0% / 96.0%.

Ranking discipline: with ~150 claims the boundary CI is about ±5.5pp, and one
unanswered batch is about 6.7pp. Group models on the **answered** boundary
into "statistically indistinguishable from the best" and the rest. Never
write "X beats Y" where their answered CIs overlap. A model with unanswered
claims stays in the table with that count. If its all-claims score is the
thing that separates it, the sentence is that the batch returned no tiers.
That is not a finding about the rubric, and it does not lead the post.

## Step 4.3 — compare with the pre-registered predictions

For each prediction the user wrote in step 3, one line: what was predicted,
what happened, right / wrong / unclear. Keep the user's wording.

## Step 4.4 — figures

Load the `dataviz` skill first if it is available.

1. `kaggle/figures/boundary.png` — one row per model, sorted by answered
   `rule` accuracy: filled dot + Wilson interval for `rule`, hollow dot for
   `definitions`; a shaded vertical band for the human ceiling (value and
   Wilson interval on the ceiling subset), labelled with its n. The dots are
   the answered-claims accuracies. Readable at dev.to body width (~700 px).
2. `kaggle/figures/cover.png` — 1000 × 420, the dev.to cover ratio: title of
   the post plus the boundary chart simplified. No logos, no brand marks.

## Step 4.5 — `kaggle/RESULTS.md`

Sections: setup (dataset size after anonymisation, prompt sources, roster,
date, settings); headline table; ceiling comparison; rule vs definitions;
disputed claims; cost and latency; chat-run comparison; predictions vs outcomes;
what this benchmark does **not** measure (it measures agreement with one
annotator's rulebook on 150 claims — not truth, not job-ad quality, not
general model capability; Tier 2/3 instability makes exact-tier a floor;
anonymisation may have changed some items' difficulty). Two further limits,
stated there when they apply:

- The chat-run comparison uses a different prompt, different batching, and
  redacted text. Agreement with 130/150 compares the two setups.
- If step 2 logged any gold claim close to a worked example in the rule
  prompt, give the count. Those examples were paraphrased from this gold
  set, and a close claim inflates the rule task. Claim text stays out of
  this file. If the log says zero, omit the point.

No claim text, no company names. Leak-scan the file against the lexicon.

## CHECKPOINT

Show the headline table, the figure, and a ranked list of the five findings
you think are most surprising, each with its numbers. Ask the user which
three the post should lead with. Then write the log section and stop.

## Log section to append

```
## Step 4 — analysis (YYYY-MM-DD)
- Re-scored metrics match task-returned metrics: yes (N runs) — returned metric is boundary_all
- Best answered rule boundary: <model> X% [lo–hi]; indistinguishable group: ...
- Models with unanswered claims: <model> k/n, all-claims X%, answered Y%
- Human ceiling (subset): 48/50 = 96.0% [86.5–98.9]; models at or above: ...
- Rule vs definitions: ...
- Chat-run comparison: agreement k/n on answered claims; 130/150 is a different prompt, batching, and redacted text
- Cost: cheapest within best CI: <model>, $X per 1,000 claims
- Predictions: k right / k wrong / k unclear
- Findings chosen by user for the post: 1. 2. 3.
```
