# Step 2 — Build and validate the Kaggle tasks

Read `kaggle/prompts/00_RUNBOOK.md` and the step 1 section of
`kaggle/LOG.md` first. Step 1 must be approved before this starts.

## Goal

Two Kaggle task files generated from one template, a scorer that provably
matches the repo's existing metric, and a local validation run that shows
per-claim results and real token usage land in the run file.

| Task slug | Rulebook the model gets |
|---|---|
| `job-ad-specificity-rule` | The rulebook **as it stood when the gold set was labelled**, including "quote the particular", the non-criteria list and the escape hatches |
| `job-ad-specificity-definitions` | Tier definitions and examples only — the rulebook as it stood **before** the written Tier 1 rule existed |

Why two: the written rule moved the annotator's own Tier 1 boundary
self-agreement from 80.6% to 96.0%. The pair measures whether the same
paragraph moves models.

## Step 2.1 — environment and SDK facts

1. Python 3.11+. Check `kaggle --version` and `kaggle b --help`; upgrade the
   `kaggle` package if the `benchmarks` command group is missing.
2. From inside `kaggle/`, run `kaggle b init -y`. It writes `.env`,
   `example_task.py` and `kaggle_benchmarks_reference.md` — all gitignored in
   step 1. Read `kaggle_benchmarks_reference.md` fully; where it disagrees
   with the cheat sheet below, it wins.
3. Confirm the SDK imports: `python -c "import kaggle_benchmarks as kbench; print(kbench.__file__)"`.
   Install the SDK the way the reference file says if it does not.

SDK cheat sheet (from Kaggle/kaggle-benchmarks, verify against the installed
source before relying on any line):

```python
import kaggle_benchmarks as kbench
@kbench.task(name="...", store_task=False)   # sub-task: not stored as its own task
def f(llm, batch_id: str, claims_json: str) -> dict: ...
res = f.evaluate(llm=[llm], evaluation_data=df, n_jobs=4,
                 on_failure="continue", max_attempts=3, retry_delay=15)
res.completed_runs.as_dataframe(); res.errored_runs   # aggregate completed only
kbench.system.send(text)                     # system prompt inside a task
llm.prompt(text, schema=PydanticModel)       # structured output, temperature 0 default
kbench.assertions.assert_true(cond, expectation="...")   # recorded, does not raise
run.chat.usage  # Usage(input_tokens, output_tokens, *_cost_nanodollars, total_backend_latency_ms)
# Return annotations allowed: bool, int, float, tuple[int,int], tuple[float,float] (value ± CI), dict
# Every task file must call .run(kbench.llm) at top level, no __main__ guard, # %% cells.
```

## Step 2.2 — the prompts the models receive

Write `kaggle/src/build_prompt.py`. It produces `kaggle/tasks/prompt_rule.md`
and `kaggle/tasks/prompt_definitions.md`.

**Source the text from git history, not from today's files.** The model must
get the rulebook the human had:

- `rule`: `prompts/shared_context.md` and `prompts/stage2_classification.md`
  at the last commit **before** the latest `labeled_at` timestamp in
  `eval/labeled.jsonl` (`git log --before=...`). Later edits added KNOWN
  DEFECT / KNOWN GAP blocks describing fixes the annotator never applied —
  they must not reach the model.
- `definitions`: the same files at the parent of the commit that introduced
  the "Name the Particular" test (`git log -S "Name the Particular"`).

Show the user both commit hashes and a diff summary before going further.

Include, by heading allowlist: tier definitions and examples, decision rules,
the Tier 1 test, non-criteria, escape hatches, boundary cases, reasoning
discipline (`rule` only for the last five). **Exclude**: Dataset Info (it
names boards), scoring formula, "what this score does not measure", output
format and how-to sections from the original prompts, and any KNOWN DEFECT
block.

Append to both variants:

1. A placeholder note: bracketed tokens such as `[Employer]`,
   `[Employer Product]`, `[City]`, `[Figure]` stand for redacted names or
   numbers; say what each stands for and nothing about which tier it implies.
2. The output contract: return every claim_uid exactly once, `tier` in
   {1,2,3}, `quoted_particular` — for Tier 1 the exact substring of the claim
   that is the particular, otherwise empty — and `reasoning` under 25 words.

Leak-scan both files against `kaggle/private/lexicon.json`; zero hits.
Record each file's sha256 and approximate token count in the log.

## Step 2.3 — the scorer, with golden tests before any model call

`kaggle/src/score.py`, pure Python, no SDK import:

- `normalize(s)` — reuse the normaliser logic from
  `eval/ingest_classification.py` (folds en/em dashes and curly quotes,
  collapses whitespace). Copy it; do not import from `eval/`.
- `score_claim(gold_row, pred)` → `boundary_correct`, `exact_correct`,
  `quote_valid` (pred Tier 1 ⇒ non-empty `quoted_particular` that is a
  normalised substring of `text`), `quote_matches_gold` (both Tier 1 and
  one quote contains the other after normalising), `missing`.
- `score_batch(gold_rows, preds)` — a missing claim counts **wrong** on every
  metric and increments `missing`; duplicate claim_uid keeps the first and
  increments `duplicates`; unknown claim_uid is ignored and increments
  `unknown`.
- `wilson(k, n)`.

`kaggle/src/test_score.py` — run with plain `python`, no pytest needed:

1. Feed the original pipeline's predictions (from `data/classified/claims.jsonl`,
   mapped through `kaggle/private/id_map.json`) into the scorer. Over the
   surviving claims it must equal what the repo's `eval/compare_labels.py`
   logic gives on the same claims — **130/150 boundary, 115/150 exact** if
   nothing was dropped.
2. Feed human pass 2 as predictions: **48/50 boundary, 43/50 exact** on the
   ceiling subset if nothing was dropped.
3. Port the 13 quote-rule cases from `eval/label_claims.py --selftest`.
4. Missing, duplicate and unknown claim_uid cases.

All must pass before step 2.4.

## Step 2.4 — the task template

`kaggle/src/task_template.py` + `kaggle/src/build_tasks.py`, which inlines
the scorer and the chosen prompt and writes `kaggle/tasks/task_rule.py` and
`kaggle/tasks/task_definitions.py`. One template, two renders, so the two
tasks cannot drift. Each generated file must be self-contained (a Kaggle task
file becomes one notebook).

Shape:

```python
# %%
import kaggle_benchmarks as kbench, pandas as pd, json, glob, os, pydantic
PROMPT = """..."""        # inlined by build_tasks.py
TASK_VARIANT = "rule"     # or "definitions"
# ... inlined score.py ...

# %%
def load_claims():
    hits = glob.glob("/kaggle/input/**/claims_anon.csv", recursive=True)
    path = hits[0] if hits else os.environ.get("KB_DATA", "../data_public/claims_anon.csv")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    n = os.environ.get("KB_SUBSET")          # local smoke runs only
    return df[df.batch_id.isin(sorted(df.batch_id.unique())[:int(n)])] if n else df

class ClaimTier(pydantic.BaseModel):
    claim_uid: str
    tier: int
    quoted_particular: str
    reasoning: str
class BatchResult(pydantic.BaseModel):
    results: list[ClaimTier]

# %%
@kbench.task(name="classify-batch", store_task=False)
def classify_batch(llm, batch_id: str, claims_json: str) -> dict:
    kbench.system.send(PROMPT)
    out = llm.prompt("Classify these claims:\n" + claims_json, schema=BatchResult)
    return {"batch_id": batch_id, "preds": [r.model_dump() for r in out.results]}

# %%
@kbench.task(name="job-ad-specificity-rule")   # slug differs per render
def specificity(llm) -> tuple[float, float]:
    ...  # evaluate classify_batch over the 15 batches, on_failure="continue"
    ...  # score every claim; a failed batch scores all its claims wrong
    ...  # one kbench.assertions.assert_true per claim:
    ...  #   expectation=f"{claim_uid} boundary" (no claim text)
    ...  # print one line per claim: KB_DETAIL {"claim_uid","pred_tier","boundary_correct",
    ...  #   "exact_correct","quote_valid","quote_matches_gold","missing"}  (no text, no quote)
    ...  # print one KB_USAGE line per batch: tokens in/out, cost nanodollars, latency ms
    ...  # print one KB_SUMMARY line with every aggregate metric
    return (boundary_acc, ci_half_width)      # Wilson, half-width = max distance to bounds

specificity.run(kbench.llm)
```

Rules for the template:

- `claims_json` holds only `claim_uid`, `text`, `context_section` — never a
  gold column. Gold is joined back after the model answers.
- If `tuple[float, float]` does not render as value ± CI on Kaggle, fall back
  to `-> float` and keep the CI in `KB_SUMMARY`. Check the SDK's
  `results.py` for how `MetricWithCI` is displayed before deciding.
- Read usage from each sub-run's chat (`run.chat.usage` or whatever the
  installed source exposes); store `None` honestly when absent.
- Do not set temperature or reasoning effort; record in the log that the
  defaults were used (temperature 0, provider-default reasoning).
- No claim text, quote or reasoning in any printed line or assertion string:
  the backing notebook will be public.

## Step 2.5 — local validation

From `kaggle/`, with `$env:KB_SUBSET="2"`:

```powershell
python tasks\task_rule.py
python tasks\task_definitions.py
```

Check, and show the user:

1. A `*.run.json` was written for each; it contains 20 per-claim assertions,
   `KB_DETAIL`/`KB_USAGE`/`KB_SUMMARY` output and a numeric result.
2. Usage fields are populated (not all `None`).
3. Structural errors: missing / duplicate / unknown counts.
4. Prompt tokens per call vs output tokens per call, and the extrapolated
   cost of one full run (15 batches) per task per model.

If `MODEL_PROXY_API_KEY` has expired, run `kaggle b auth -y` and retry once.

## CHECKPOINT

Show: the two commit hashes the prompts came from, prompt token counts, test
results, the 2-batch validation output, and the per-model cost
extrapolation. Wait for approval. Then write the log section and stop.

## Log section to append

```
## Step 2 — tasks (YYYY-MM-DD)
- Prompt sources: rule @ <hash> (<date>), definitions @ <hash> (<date>)
- Prompt sizes: rule ≈ N tokens, definitions ≈ N tokens; sha256 ...
- Scorer golden tests: pipeline 130/150 & 115/150 reproduced; human 48/50 & 43/50 reproduced
- Validation (2 batches, default model): boundary k/20, usage populated: yes/no
- Extrapolated cost per full run per model: ...
- Decisions: batch size 10, cross-posting batches, return type ...
```
