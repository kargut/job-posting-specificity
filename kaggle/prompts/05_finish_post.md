# Step 5 — Finish the dev.to post

Read `kaggle/prompts/00_RUNBOOK.md`, all of `kaggle/LOG.md`, and
`kaggle/RESULTS.md` first. Step 4 must be approved, with the user's three
chosen findings recorded in the log.

## Goal

Turn `writeup/devto-kaggle-post.md` from a draft with placeholders into a
publishable submission. The user publishes it; you do not.

## Sources of truth — nothing else

Every number in the post must come from one of:

1. `kaggle/RESULTS.md` (this benchmark), or
2. the "Numbers already measured" table in `00_RUNBOOK.md` (the earlier project), or
3. `kaggle/LOG.md` (anonymisation counts, roster, predictions, URLs).

If a number you want is in none of them, it does not go in the post. If a
number in the draft contradicts them (for example, step 1 dropped ceiling
claims, so 48/50 and 44/50 changed), the source wins — fix every occurrence.

## Placeholders to fill

| Placeholder | Source |
|---|---|
| `N_CLAIMS`, `N_CEILING`, `N_AT_RISK`, `N_DROPPED`, `N_REDACTED` | LOG step 1 |
| `AUDIT_A_HITS`, `AUDIT_B_ROUND1`, `AUDIT_B_FINAL`, `AUDIT_B_ROUNDS` | LOG step 1 |
| `DATASET_VISIBILITY` | LOG step 3 (`private` / `public`) |
| `N_MODELS`, `MODEL_ROWS` | LOG step 3 roster |
| `RESULT_ROWS`, `BEST_GROUP_SENTENCE` | RESULTS headline table |
| `FINDING_1..3_TITLE` and their paragraphs | the user's three chosen findings, LOG step 4 |
| `SURPRISE`, `PRED_RIGHT`, `PRED_SENTENCE` | RESULTS "predictions vs outcomes" |
| `FIGURE_URL` | leave as `FIGURE_URL` and tell the user to upload `kaggle/figures/boundary.png` in the editor and paste the URL |
| `KAGGLE_BENCHMARK_URL`, `TASK_RULE_URL`, `TASK_DEFINITIONS_URL` | LOG step 3 |
| `CHECKPOINT_STORY` | LOG, any step — only a real event; otherwise delete |
| Example-overlap bullet | LOG step 2 count. Add the bullet in the draft's EXAMPLE OVERLAP comment when the count is above zero. When it is zero, delete the comment |

For each FILL comment with branches: keep only the branch the data supports,
fill its numbers, delete the comment markers and every other branch. If the
user's chosen finding has no prepared branch, write it in the same shape: a
bold one-line claim, then two to four short paragraphs with numbers.

## Voice

Match the first post (`writeup/devto-post.md`): first person, short
declarative sentences, numbers with denominators, limitations stated plainly,
no hype. Do not use "delve", "game-changer", "honestly", "genuinely",
"straightforward", "crucial", "leverage", or exclamation marks. No emoji.
Keep the closing question.

## Template compliance (the challenge requires these)

- First line after front matter: the italic "This is a submission for the
  Kaggle Benchmarking Challenge" line, with its link, unchanged.
- The four headings exist, spelled exactly: `## What I Benchmarked`,
  `## Models Tested`, `## Findings`, `## My Benchmark`. Extra `###`
  subsections are fine.
- Tags: `devchallenge, kagglechallenge, ai, machinelearning` (dev.to allows
  four; these are the template's).
- The Kaggle benchmark link is present and public.
- `published: false` stays — the user flips it.

## Checks — run all, show the output

1. `grep -n "{{" writeup/devto-kaggle-post.md` → nothing.
2. `grep -n "FILL\|<!--" writeup/devto-kaggle-post.md` → only the top
   maintenance comment, which you then delete too (dev.to renders nothing for
   it, but it should not ship).
3. Lexicon scan against `kaggle/private/lexicon.json`, case- and
   diacritic-folded → zero hits.
4. Claim text: the only claim-like strings allowed are the four tier
   examples already in the draft (they come from the rulebook, not from a
   posting) and at most four anonymised examples
   the user explicitly approves. List any other quoted claim text and remove it.
5. Every number: produce a table in chat — number, sentence, source file and
   line. The user reviews it.
6. Word count of the body between 1,100 and 1,700. If over, cut from
   "How I built it" before cutting findings.
7. Every link resolves (the dev.to, GitHub and Kaggle ones); the Kaggle ones
   in a logged-out check by the user.

## Also

- Add a short "Kaggle benchmark" section to `README.md`: two sentences and
  the benchmark link, plus a pointer to `kaggle/RESULTS.md`.
- Append a step 5 section to `kaggle/LOG.md`.
- Propose (do not run) a commit message covering `kaggle/` (code, prompts,
  tasks, LOG, RESULTS, figures), `writeup/devto-kaggle-post.md`, `README.md`
  and `.gitignore`. Before proposing, run `git status` with
  `GIT_OPTIONAL_LOCKS=0` and confirm nothing under `kaggle/data_public/`,
  `kaggle/private/` or any `*.run.json` is staged or untracked-but-visible.

## CHECKPOINT

Show the final post, the number-source table and the check results. Remind
the user of the publishing steps: paste into dev.to, upload the cover and the
figure, set `published: true`, confirm the four tags, submit before
11 October 23:59 PDT. Stop.
