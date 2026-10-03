# Kaggle Benchmarking Challenge — runbook

Read this file first in every session. Then run the numbered prompt for the
step you are on. One prompt per session is fine; each one starts by reading
`kaggle/LOG.md` to see where the previous one stopped.

**Model:** Claude Opus 5.5, with the repo folder connected
(`C:\work\claude_vague\job-posting-specificity`).
**Challenge:** https://dev.to/challenges/kaggle-2026-09-23 — submissions close
**11 October 2026, 23:59 PDT** (12 October, 09:59 Riga/Kyiv time).
**Job search starts 6 October.** Target: post ready by Monday 5 October.

## What we are building

A public Kaggle benchmark made from this project's existing gold set, run
against several models, plus one dev.to post in the challenge template.

| Step | Prompt | Output | Rough time |
|---|---|---|---|
| 1 | `01_anonymize.md` | Anonymised claim dataset, audit results, dataset card | 2–3 h |
| 2 | `02_build_task.md` | Two Kaggle task files, a scorer with golden tests, local validation | 2–3 h |
| 3 | `03_push_and_run.md` | Private Kaggle dataset, pushed + run + published tasks, benchmark page | 1–2 h + waiting |
| 4 | `04_analyze.md` | `kaggle/RESULTS.md`, figures | 1–2 h |
| 5 | `05_finish_post.md` | `writeup/devto-kaggle-post.md` finished, README link | 1 h |

The benchmark in one paragraph: each item is one claim extracted from a job
ad. The model applies the project's written tier rulebook and says whether the
claim is Tier 1 (concrete), 2 (general direction) or 3 (empty slogan). The
headline metric is **Tier 1 boundary accuracy** against the blind gold labels.
Two tasks: `job-ad-specificity-rule` (the full rulebook, including "quote the
particular") and `job-ad-specificity-definitions` (definitions and examples
only — the rulebook as it stood before the written rule). Every model is
reported next to the **human ceiling measured on the same claims**.

## Numbers already measured — do not re-derive, check against them

From `eval/` and the project doc `claude/eval-method-decisions.md`. Any script
that touches the same data must reproduce these exactly or stop and report.

| Quantity | Value |
|---|---|
| Gold set | 15 postings, 150 claims, all blind. T1 61, T2 89, T3 0 |
| Human self-agreement, pre-rule (36 claims, one posting) | exact 75.0%, boundary 80.6% |
| Human self-agreement, post-rule (50 claims, `labeled_pass2_blind.jsonl`) | exact 43/50 = 86.0%, boundary 48/50 = 96.0% (Wilson 86.5–98.9) |
| Original pipeline (chat run, configured as `claude-opus-5`), 150 claims | exact 115/150 = 76.7%, boundary 130/150 = 86.7% (80.3–91.2) |
| Original pipeline on the **same 50** ceiling claims | exact 37/50 = 74.0%, boundary 44/50 = 88.0% (76.2–94.4) |
| Human pass-2 changes | 7 of 50 tiers changed; 6 of those 7 moved to the model's answer |
| Human pass-2 Tier 3 | 5 of 50 (10%); gold has 0 of 150 |
| Cost estimate it replaces | chars/4, Stage 2 as run ≈ 2,070 in / 910 out tokens per posting |

The matched-50 row is new: it was computed on 2026-10-03 from the local files
and closes the old caveat that model and human were measured on different sets.

## Hard rules (from the project instructions — they override anything else)

1. **Never name a company** — not in committed files, not in `kaggle/LOG.md`,
   not in `kaggle/RESULTS.md`, not in the Kaggle dataset, task, notebook or
   benchmark description, not in the post. Use `[Employer]`-style placeholders.
   Real names may appear only in chat and in `kaggle/private/` (gitignored).
2. **Do not commit the corpus.** `kaggle/data_public/`, `kaggle/private/` and
   any `*.run.json` are gitignored. Only code, prompts, the log and aggregate
   results are committed. The anonymised dataset goes to Kaggle as a
   **private** dataset unless the user decides otherwise at a checkpoint.
3. **No claim text in committed files**, except at most four anonymised
   example claims the user approves for the post.
4. **Never edit gold labels.** Not to fix a known-wrong label, not after
   anonymisation. Flag, don't fix.
5. Do not touch `eval/RESULTS.md`. Never run `compare_labels.py --report`
   against it.
6. Weekend-sized. No hosted app, no UI, no new data collection, no full-corpus
   run. If a step grows past its time budget, stop and say so.
7. Do not `git commit` or `git push` unless the user asks in that session.
   Propose a commit message instead. Use `GIT_OPTIONAL_LOCKS=0` for any git
   read; if `.git/index.lock` appears, move it aside and say so.

## Working conventions

- **Checkpoints.** Each prompt has `CHECKPOINT` lines. At each one: show what
  you did and the numbers, then stop and wait for the user. Do not chain past
  a checkpoint, even when the next step looks obvious.
- **The log.** Append one section per step to `kaggle/LOG.md`:
  date, what was done, exact commands, decisions with one-line reasons, the
  numbers produced, and anything that surprised you. No company names, no
  claim text. The post's "how I built it" section is written from this log.
- **Shell.** Python and Kaggle CLI run on the user's Windows machine.
  - In Cowork, use the device shell on the connected folder. If a command
    needs kaggle.com and the device shell's network refuses it, do not retry
    from the cloud workspace: print the exact PowerShell command for the user,
    wait for them to paste the output back.
  - PowerShell 5.1 redirects as UTF-16LE with a BOM — never `> file` and then
    parse it. Check `$PSVersionTable.PSVersion`; write files from Python.
  - No `VAR=value cmd` prefix in PowerShell; use `$env:VAR="value"`.
  - Every JSONL file here is one object per line. Pretty-printed JSON reads as
    zero rows with no error.
- **Kaggle CLI pacing.** Follow the Kaggle `write-kaggle-benchmarks` skill's
  rule: state the exact command, run it, show the output, stop. Repeat `-m`
  and `-d` once per value; never space-separate them.

## Folder layout this work creates

```
kaggle/
  prompts/            these files (committed)
  LOG.md              build log (committed)
  src/                anonymize.py, build_prompt.py, build_tasks.py,
                      score.py, test_score.py, analyze.py (committed)
  tasks/              generated task_rule.py, task_definitions.py,
                      prompt_rule.md, prompt_definitions.md (committed)
  RESULTS.md          aggregate results only (committed)
  figures/            PNGs for the post (committed)
  data_public/        claims_anon.csv, DATASET_CARD.md, dataset-metadata.json
                      (gitignored — uploaded to Kaggle)
  private/            lexicon, redaction map, seeds, attack transcripts,
                      downloaded runs (gitignored — never leaves the machine)
writeup/devto-kaggle-post.md   the challenge post
```

## If something contradicts this runbook

Stop and ask. In particular: if Kaggle requires the dataset to be public for
the benchmark to be viewable, that is the user's decision at the checkpoint
in step 3, not yours.
