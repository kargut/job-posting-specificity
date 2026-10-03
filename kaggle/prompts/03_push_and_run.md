# Step 3 — Dataset, push, run, publish

Read `kaggle/prompts/00_RUNBOOK.md` and the step 1–2 sections of
`kaggle/LOG.md` first. Both must be approved.

Kaggle CLI pacing applies to every command here: say the exact command, run
it (or hand it to the user if the device shell cannot reach kaggle.com),
show the output, stop at checkpoints. Kaggle username: ask the user once and
write it into the log as `<KAGGLE_USER>`.

## Step 3.1 — private Kaggle dataset

```powershell
kaggle datasets init -p kaggle\data_public
```

Edit `dataset-metadata.json`: title `Job-ad claim specificity — anonymised gold set`,
slug `job-ad-claim-specificity`, licence per the dataset card, description =
the dataset card's first two paragraphs. Leak-scan the metadata file against
the lexicon. Then:

```powershell
kaggle datasets create -p kaggle\data_public
```

No `--public` flag: it stays private. Confirm with
`kaggle datasets status <KAGGLE_USER>/job-ad-claim-specificity`.

## Step 3.2 — push both tasks, smoke-run one cheap model

```powershell
kaggle b t push job-ad-specificity-rule -f kaggle\tasks\task_rule.py -d <KAGGLE_USER>/job-ad-claim-specificity --wait
kaggle b t push job-ad-specificity-definitions -f kaggle\tasks\task_definitions.py -d <KAGGLE_USER>/job-ad-claim-specificity --wait
kaggle b t models
```

Every re-push must repeat the `-d` flag, or the dataset is silently detached.

Pick the cheapest model in the list, run both tasks on it with `--wait`, then
`kaggle b t status` and `kaggle b t log` for that model. Confirm the server
run found the dataset under `/kaggle/input/` and produced 150 `KB_DETAIL`
lines. If it errored, fix, re-push (with `-d`), re-run. Do not continue on a
broken task.

## Step 3.3 — choose the models

From `kaggle b t models` and `kaggle b quota`, propose a roster of **6–8
models**, one line of rationale each, built from these slots:

| Slot | Why it is in the benchmark |
|---|---|
| Frontier model from each provider on the list | Does anyone reach the human ceiling? |
| Small / fast model from the same providers | The rule is mechanical — does a cheap model apply it as well? This is the cost question the project cares about |
| One or two open-weights models | Can it run without a commercial API at all? |
| The Claude Opus model closest to the original pipeline's | Reproduction check: the chat run scored 130/150 boundary, 44/50 on the ceiling subset |

Estimate the cost of the full plan from the step 3.2 usage: models × 2 tasks
× one run each. Show the remaining quota.

### CHECKPOINT — roster approval and pre-registration

Before any full run, ask the user to approve the roster **and to write their
own predictions into `kaggle/LOG.md`**, in their words, for:

1. Will any model's boundary accuracy reach the human ceiling (96.0% on the
   ceiling subset)?
2. Will the written rule improve models the way it improved the human?
3. Will small models trail frontier ones by more than the CI width (≈5pp)?
4. Which way will models lean on the Tier 2/3 boundary?

Pre-registration was how the project protected its own numbers from
hindsight; the post will compare outcomes against these lines. Do not write
the predictions for the user and do not suggest answers.

## Step 3.4 — full runs

Repeat `-m` once per model:

```powershell
kaggle b t run job-ad-specificity-rule -m <m1> -m <m2> ... --wait
kaggle b t run job-ad-specificity-definitions -m <m1> -m <m2> ... --wait
kaggle b t status job-ad-specificity-rule
kaggle b t status job-ad-specificity-definitions
```

For any errored run: `kaggle b t log <task> -m <model>`, classify the cause
(quota, timeout, schema failure, provider refusal), re-run once. A model that
fails structurally on every attempt is a finding, not something to hide —
keep it in the results with its error.

Download everything into the private folder:

```powershell
kaggle b t download job-ad-specificity-rule -o kaggle\private\runs -s
kaggle b t download job-ad-specificity-definitions -o kaggle\private\runs -s
```

## Step 3.5 — optional: measure the model twice

Only if quota allows after 3.4 and the user agrees. The project's central
move was measuring the human twice; do the same for the two best models on
the `rule` task, using the 50-claim ceiling subset: run locally through
`kbench.llms["<model>"]` twice with identical settings and keep the per-claim
predictions in `kaggle/private/runs/repeat/`. Step 4 turns these into model
self-agreement. At temperature 0 the answer may be "identical" — that is
still worth reporting.

## Step 3.6 — publish and assemble the benchmark

1. Check the backing notebooks' outputs (downloaded with `-s`) contain no
   claim text — only claim_uids, flags and numbers.
2. Publish both tasks:
   ```powershell
   kaggle b t publish job-ad-specificity-rule
   kaggle b t publish job-ad-specificity-definitions
   ```
3. The CLI cannot create a benchmark collection. Give the user, ready to
   paste into the Kaggle web UI (Benchmarks → New benchmark):
   - Title: `Job-ad specificity: rule-following against a measured human ceiling`
   - A 120–180 word description: what an item is, the three tiers, the two
     tasks and why, the headline metric, the human ceiling numbers, the
     anonymisation in one sentence, link to the GitHub repo. No employer
     names, no claim text. Leak-scan it before handing it over.
   - Both tasks added.
4. Ask the user to open the benchmark URL in a logged-out / private window
   and confirm the leaderboard is visible.

### CHECKPOINT — public visibility

If the leaderboard or tasks are not viewable while the dataset is private,
stop and put the choice to the user:

- (a) make the anonymised dataset public on Kaggle — it passed both audits,
  but it is still claim-level text from real ads, which goes beyond the
  project's "aggregate results only" rule;
- (b) keep it private and find another way for the benchmark to be public;
- (c) something else the user proposes.

Do not decide this yourself.

## Log section to append

```
## Step 3 — Kaggle (YYYY-MM-DD)
- Dataset: <KAGGLE_USER>/job-ad-claim-specificity (private|public)
- Tasks pushed: versions ...
- Smoke run: <model>, 150 KB_DETAIL lines: yes
- Roster: model — slot — one-line reason
- User predictions recorded: yes (see below, in the user's words)
- Runs: completed N / errored N (causes ...)
- Quota used: ...
- Optional repeat runs: done / skipped
- Benchmark URL: https://www.kaggle.com/benchmarks/...
- Public check (logged out): leaderboard visible yes/no
```
