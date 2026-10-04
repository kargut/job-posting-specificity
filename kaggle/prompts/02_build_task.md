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
# llm.prompt() keeps history inside one chat. A second call sees the first.
# kbench.chats.new(name, orphan=True) starts a chat with no parent history.
# Confirm the signature in the installed source before using it.
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

Append the same placeholder note to both variants: bracketed tokens such as
`[Employer]`, `[Employer Product]`, `[City]`, `[Figure]` stand for redacted
names or numbers; say what each stands for and nothing about which tier it
implies.

Append a different output contract to each variant. The definitions contract
must not teach the mechanical test.

- `rule`: return every claim_uid exactly once, `tier` in {1,2,3},
  `quoted_particular` — for Tier 1 the exact substring of the claim that is
  the particular, otherwise empty — and `reasoning` under 25 words.
- `definitions`: return every claim_uid exactly once, `tier` in {1,2,3}, and
  `reasoning` under 25 words. Do not mention quotes, particulars, evidence
  spans, or substrings.

Then check the ablation was not filled back in:

1. `prompt_definitions.md` and `task_definitions.py` contain no
   `quoted_particular`.
2. The definitions output contract does not tell the model to quote, name, or
   return a span.
3. If the git-sourced definitions body itself contains "Name the Particular"
   or an instruction to quote a token as the Tier 1 test, stop and show that
   passage. That means the parent commit is already the rule. Do not delete
   historical text to make the check pass.

Leak-scan both files against `kaggle/private/lexicon.json`; zero hits.
Record each file's sha256 and approximate token count in the log.

## Step 2.3 — the scorer, with golden tests before any model call

`kaggle/src/score.py`, pure Python, no SDK import:

- `normalize(s)` — copy `norm` from `eval/label_claims.py` (lowercase, fold
  en/em dashes and curly quotes, collapse whitespace). Copy it; do not import
  from `eval/`. It is the same body as `eval/ingest_classification.py`.
- Copy `STOPWORDS` and `is_quote_of` from `eval/label_claims.py` verbatim.
  That is the function the labeler uses when a quote is typed as its own
  field, which is what `quoted_particular` is. Do not copy
  `quotes_particular` or `_informative_tokens`. Those search free-text
  reasoning for a quoted span, an informative token, or a run of three or
  more words. `--selftest` and `--verify` call `quotes_particular`. This
  scorer does not.
- `quote_valid` calls `is_quote_of(text, quoted_particular)` and keeps the
  boolean only. On a Tier 1 prediction that means all three of: at least 2
  characters after normalize, not a member of `STOPWORDS`, and a normalized
  substring of the claim. Any one failure is `false`, including an empty
  quote. Non-Tier-1 predictions leave `quote_valid` null; they are not in
  that share. A quote the model was not asked to judge is not a failure.
- `score_claim(gold_row, pred)` → `boundary_correct`, `exact_correct`,
  `quote_valid`, `quote_matches_gold` (rule variant only, and only when both
  sides are Tier 1: one normalized quote contains the other), `missing`.
  `quote_matches_gold` is containment. It does not call `is_quote_of`.
  Definitions predictions have no quote field. Those two flags are `null`
  there, not `false`.
- `score_batch(gold_rows, preds)` — a missing claim counts **wrong** on
  boundary and exact in the all-claims score and increments `missing`. It has
  no Tier 1 prediction, so `quote_valid` stays null. The same claim is excluded
  from `boundary_answered` and `exact_answered`. Duplicate claim_uid keeps the
  first and increments `duplicates`; unknown claim_uid is ignored and increments
  `unknown`. A failed batch is ten missing claims, not ten wrong tiers.
- `wilson(k, n)`.

`kaggle/src/test_score.py` — run with plain `python`, no pytest needed:

1. Feed the original pipeline's predictions (from `data/classified/claims.jsonl`,
   mapped through `kaggle/private/id_map.json`) into the scorer. Over the
   surviving claims it must equal what the repo's `eval/compare_labels.py`
   logic gives on the same claims — **130/150 boundary, 115/150 exact** if
   nothing was dropped.
2. Feed human pass 2 as predictions: **48/50 boundary, 43/50 exact** on the
   ceiling subset if nothing was dropped.
3. `is_quote_of` cases, asserted through `quote_valid` on a Tier 1 prediction.
   These replace the old "port the 13 selftest cases" instruction. The 13
   cases call `quotes_particular(claim, reasoning)`. Passing them would not
   mean `quote_valid` matches the labeler. Do not import `quotes_particular`,
   do not copy it into the test, and do not report a green run as "same
   metric as `label_claims.py`".

   The quote field is the span itself, and `is_quote_of` accepts it:

   | Claim | `quoted_particular` | Expected |
   |---|---|---|
   | `3+ years of experience conducting incident response` | `3+ years` | true |
   | `using ATT&CK-mapped detection and signal enrichment` | `ATT&CK` | true |
   | `Expert knowledge of Python and SQL` | `Python and SQL` | true |
   | `€65,000–85,000 gross` | `€65,000-85,000` | true |
   | `Experience with data processing and analysis tools (e.g. Spark, Trino)` | `Spark, Trino` | true |
   | `Team of 5, growing to 8 by end of year` | `growing to 8 by end of year` | true |
   | `On-call one week in six` | `one week in six` | true |

   A non-empty substring is not enough. `is_quote_of` rejects these:

   | Claim | `quoted_particular` | Expected | Why |
   |---|---|---|---|
   | `On-call one week in six` | `a` | false | shorter than 2 characters |
   | `On-call one week in six` | empty | false | shorter than 2 characters |
   | `Work cross-functionally with security, fraud and data science teams` | `teams` | false | stopword, even though it occurs in the claim |
   | `Work cross-functionally with security, fraud and data science teams` | `work` | false | stopword |
   | `using ATT&CK-mapped detection and signal enrichment` | `checkable tooling` | false | not a substring |

   These two would pass `quotes_particular` if handed to it as reasoning,
   because `ATT&CK` or the quoted span occurs inside the string. As a quote
   field they must fail, because the whole string is not a substring:

   | Claim | `quoted_particular` | Expected |
   |---|---|---|
   | `using ATT&CK-mapped detection and signal enrichment` | `checkable tooling ATT&CK` | false |
   | `€65,000–85,000 gross` | `number: "€65,000–85,000"` | false |

   The test file states, in a comment next to the assertions: `quote_valid`
   agrees with `is_quote_of` on a dedicated quote field. It does not agree
   with `quotes_particular`, `--selftest`, or `--verify`.
4. Missing, duplicate and unknown claim_uid cases.

All must pass before step 2.4. A pass means boundary and exact match the
golden counts, and `quote_valid` matches `is_quote_of` on the table above.

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

# Rule render only. The definitions render has claim_uid, tier, reasoning —
# no quoted_particular field and no description that mentions one.
# The schema is sent to the model; a shared class would leak the test.
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
    # One prompt per call. Step 2.5 checks that the next batch does not see
    # this one. system.send and llm.prompt move inside chats.new only if
    # that check fails. See the rules under the template.
    kbench.system.send(PROMPT)
    out = llm.prompt("Classify these claims:\n" + claims_json, schema=BatchResult)
    return {"batch_id": batch_id, "preds": [r.model_dump() for r in out.results]}

# %%
@kbench.task(name="job-ad-specificity-rule")   # slug differs per render
def specificity(llm) -> tuple[float, float]:
    ...  # evaluate classify_batch over the 15 batches, on_failure="continue"
    ...  # a failed batch marks all its claims missing. Missing counts wrong in
    ...  #   boundary_all (the returned leaderboard number) and is left out of
    ...  #   boundary_answered
    ...  # one kbench.assertions.assert_true per claim:
    ...  #   expectation=f"{claim_uid} boundary" (no claim text)
    ...  # print one line per claim: KB_DETAIL {"claim_uid","pred_tier","boundary_correct",
    ...  #   "exact_correct","quote_valid","quote_matches_gold","missing"}  (no text, no quote)
    ...  #   missing is true when the batch failed or the claim got no tier
    ...  # print one KB_USAGE line per batch, with batch_id, so step 2.5 can
    ...  #   compare them: input_tokens, output_tokens, cost nanodollars, latency ms
    ...  # print one KB_SUMMARY line with boundary_all, boundary_answered,
    ...  #   n_unanswered, and every other aggregate metric
    return (boundary_all, ci_half_width)      # Wilson on all claims; failures count wrong

specificity.run(kbench.llm)
```

Rules for the template:

- `claims_json` holds only `claim_uid`, `text`, `context_section` — never a
  gold column. Gold is joined back after the model answers.
- The two renders share the scorer and the batch loop. They do not share the
  response schema. `TASK_VARIANT == "definitions"` uses a model with
  `claim_uid`, `tier`, and `reasoning` only. Do not add an optional quote
  field "for later". `KB_DETAIL` on that variant prints `quote_valid` and
  `quote_matches_gold` as JSON `null`.
- If `tuple[float, float]` does not render as value ± CI on Kaggle, fall back
  to `-> float` and keep the CI in `KB_SUMMARY`. Check the SDK's
  `results.py` for how `MetricWithCI` is displayed before deciding.
- Read usage from each sub-run's chat (`run.chat.usage` or whatever the
  installed source exposes); store `None` honestly when absent.
- The smoke run in step 2.5 uses `n_jobs=1`. Parallel batches can hide a
  shared chat. Raise `n_jobs` only after that run shows the two batches are
  isolated.
- If step 2.5 fails the history check, `classify_batch` becomes:

  ```python
  with kbench.chats.new(f"batch-{batch_id}", orphan=True):
      kbench.system.send(PROMPT)
      out = llm.prompt("Classify these claims:\n" + claims_json, schema=BatchResult)
  ```

  Both calls stay inside the block. `orphan=True` means the new chat is not
  nested in the parent history; confirm that against the installed source and
  use whichever argument starts a chat with no prior messages.
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
2. Usage fields are populated (not all `None`). If `input_tokens` is missing
   on either batch, stop. There is no way to tell whether batch 2 saw batch 1,
   and the cost extrapolation would be a guess.
3. Structural errors: missing / duplicate / unknown counts.
4. **History check, before any cost number.** Inside one chat, `llm.prompt()`
   keeps history, so a second batch would send the system prompt again plus
   the first batch's claims and answer. `evaluate()` may already start a fresh
   run per row. The tokens decide. For each task, read `input_tokens` on
   batch 1 and batch 2 from `KB_USAGE`:
   - Pass: batch 2 is between 0.75× and 1.25× batch 1. Both batches hold 10
     claims, so the prompts should be about the same size.
   - Fail: batch 2 is above 1.5× batch 1, or batch 2 − batch 1 is larger than
     batch 1's `output_tokens`. The second call is carrying the first.
   On a failure, replace the `classify_batch` body with the `chats.new(...,
   orphan=True)` form in the template. `system.send` and `llm.prompt` both go
   inside that block. Confirm `orphan` against the installed source; use the
   argument that starts a chat with no parent messages. Re-run this smoke test
   at `n_jobs=1`. Do not push, and do not extrapolate cost, until both tasks
   pass.
5. Prompt tokens per call vs output tokens per call, and the extrapolated
   cost of one full run. Use the mean `input_tokens` of the two passing
   batches × 15, twice (one per task). A leaking run grows with batch number,
   so 15 × the second batch overstates the real cost.

If `MODEL_PROXY_API_KEY` has expired, run `kaggle b auth -y` and retry once.

## CHECKPOINT

Show: the two commit hashes the prompts came from, the two output contracts
side by side, prompt token counts, the definitions-file check from step 2.2,
test results, the 2-batch validation output, the batch-1 vs batch-2
`input_tokens` for both tasks, whether `chats.new` was required, and the
per-model cost extrapolation from the passing batches. Wait for approval.
Then write the log section and stop.

## Log section to append

```
## Step 2 — tasks (YYYY-MM-DD)
- Prompt sources: rule @ <hash> (<date>), definitions @ <hash> (<date>)
- Prompt sizes: rule ≈ N tokens, definitions ≈ N tokens; sha256 ...
- Scorer golden tests: pipeline 130/150 & 115/150 reproduced; human 48/50 & 43/50 reproduced
- quote_valid: copied is_quote_of + STOPWORDS from label_claims.py; tests above passed. Not quotes_particular, not label_claims.py --selftest
- Validation (2 batches, n_jobs=1, default model): boundary k/20, usage populated: yes/no
- History check: batch2 input_tokens / batch1 input_tokens = ... (rule), ... (definitions); chats.new: used / not needed
- Extrapolated cost per full run per model, from the mean of the two passing batches: ...
- Output contracts differ: rule asks for quoted_particular; definitions asks for tier + reasoning only
- Decisions: batch size 10, cross-posting batches, return type ...
```
