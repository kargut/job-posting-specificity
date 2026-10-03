# Step 1 — Build the anonymised benchmark dataset

Read `kaggle/prompts/00_RUNBOOK.md` first. Its hard rules apply throughout.
If `kaggle/LOG.md` does not exist, create it with a one-line header.

## Goal

Turn the 150-claim gold set into a dataset that can sit on Kaggle without
identifying any employer, while keeping every gold label valid. Anonymise as
far as the labels allow, prove it with two re-identification audits, and
record what was lost.

The constraint that makes this harder than find-and-replace: **a redaction
can change the correct tier.** If a Tier 1 claim's only particular is a
product name, replacing it with `[Product]` may or may not leave a
particular. Every redaction is checked against the gold label, and the gold
label is never edited.

## Inputs (all local, gitignored)

| File | Use |
|---|---|
| `eval/labeled.jsonl` | Gold: 15 postings, 150 claims, fields `claim_id, text, tier, reasoning, context_section` |
| `eval/labeled_pass2_blind.jsonl` | Second blind pass, 50 claims — the human ceiling subset |
| `data/raw/raw_postings.jsonl` | Employer names, boards, titles, URLs — for the lexicon only |
| `eval/RESULTS.md` §7 | The seven pre-registered suspect labels |
| `src/pipeline/aggregate.py` | The role/employer frozensets for `context_section` |

## Outputs

| Path | Committed? |
|---|---|
| `kaggle/src/anonymize.py` — deterministic, reads private rules, writes the CSV | yes |
| `kaggle/private/lexicon.json` — every identifying string to scan for | no |
| `kaggle/private/redactions.json` — per-claim manual decisions | no |
| `kaggle/private/id_map.json` + seed — original ids ↔ anonymous ids | no |
| `kaggle/private/audit/` — search results, attack transcripts | no |
| `kaggle/data_public/claims_anon.csv` | no (goes to Kaggle) |
| `kaggle/data_public/DATASET_CARD.md` | no (goes to Kaggle); a copy without examples may be committed |
| `.gitignore` additions | yes |
| `kaggle/LOG.md` section | yes |

## Step 1.1 — gitignore first

Before writing any data file, append to `.gitignore`:

```
# Kaggle challenge: anonymised data and private audit material stay local
kaggle/data_public/
kaggle/private/
kaggle/**/*.run.json
kaggle/.env
kaggle/example_task.py
kaggle/kaggle_benchmarks_reference.md
```

Verify with `git check-ignore -v` on a dummy file in each folder.

## Step 1.2 — the private lexicon

Build `kaggle/private/lexicon.json` from:

- Every `company` value and board token in `data/raw/raw_postings.jsonl`
  (all 11 boards, not just the 15 gold postings), with case and diacritic
  variants, and the bare domain of every posting URL.
- Product, subsidiary, brand and programme names that appear in the 150
  claim texts. Find candidates mechanically (capitalised tokens and
  multi-word proper nouns not in a generic-technology allowlist), then
  review each one yourself.
- Named people, awards and lists, office addresses, internal team or
  programme names.

Generic technologies, standards, languages and certifications are **not**
identifying on their own and stay: `Go`, `PostgreSQL`, `RBAC`, `GDPR`,
`ISO 27001`, `English`. Keep a written allowlist in the lexicon file so the
decision is auditable.

## Step 1.3 — structural anonymisation

Write rows in a seeded random order (seed stored in `kaggle/private/`), one
row per claim, **no posting grouping** — removing the link between claims of
the same ad is the largest single anonymisation gain.

| Column | Content |
|---|---|
| `claim_uid` | `c001`…`c150`, assigned after the shuffle |
| `batch_id` | `b01`…`b15`, consecutive chunks of 10 in shuffled order |
| `text` | claim text after redaction |
| `context_section` | as in gold, lower-cased (generic vocabulary) |
| `context_group` | `role` or `employer`, from the `aggregate.py` frozensets |
| `gold_tier` | unchanged |
| `gold_quote` | for Tier 1 only: the quoted particular from the gold reasoning, after the same redaction as `text`; must be a substring of `text` |
| `pass2_tier` | second-pass tier, blank if not in the subset |
| `in_ceiling_subset` | true for the 50 pass-2 claims |
| `human_exact_unstable` | pass-2 tier ≠ gold tier |
| `human_boundary_unstable` | pass-2 and gold disagree on Tier 1 vs other |
| `preregistered_suspect` | true for the seven labels in `eval/RESULTS.md` §7 |
| `redacted` | true if `text` differs from the original |

Dropped: `posting_id`, `posting_content`, company, board, title, URL,
locations, every timestamp, the free-text reasoning (only the quoted
particular survives), and the original model's predictions (kept privately
for the reproduction check in step 4).

## Step 1.4 — redaction

Typed placeholders, so a reader and a model can still tell what kind of
particular was there:

| Placeholder | Replaces |
|---|---|
| `[Employer]` | the hiring company's own name, any alias |
| `[Employer Product]` | a named product, service or platform of the hiring company |
| `[Other Company]` | a named customer, partner, investor or parent |
| `[Award]` | named awards, rankings, lists |
| `[City]` / `[Country]` | only where the place plus anything else in the claim narrows to one employer; generic office-policy places can stay |
| `[Figure]` | employer-level facts that identify by search: revenue, volume processed, customer counts, headcount, founding year, funding |
| `[Person]` | named people |

Role-level numbers are the substance of Tier 1 and **stay**: salary bands,
years of experience, team size, on-call cadence, office days. They do not identify an employer on their own.

Record every decision in `kaggle/private/redactions.json` and apply it from
`anonymize.py`, so the dataset is reproducible from code plus private rules.

**Label check after redaction.** For every redacted claim:

- Gold Tier 1 whose `gold_quote` was untouched → fine.
- Gold Tier 1 whose `gold_quote` was redacted → mark `label_at_risk`. If the
  placeholder still stands for the same *kind* of particular (a named product
  → `[Employer Product]`), it can stay; if the particular is gone (a figure
  that was the only number), the claim must be dropped, not relabelled.
- Gold Tier 2 that now reads as emptier than before → note it, keep it.

## Step 1.5 — audit A: exact-phrase search

For every `employer`-group claim and every `role` claim with 12+ words or any
digit, run a web search for the redacted text in quotes. A hit is any result
on a page you can attribute to a lexicon employer. Budget about 60 searches;
if more claims qualify, prioritise employer-group claims, then the longest.

For each hit: redact further if a typed placeholder fixes it without
dropping the label, otherwise drop the claim. Employer taglines and mission
statements are the usual culprits — dropping them is acceptable.

Save queries and verdicts in `kaggle/private/audit/search.jsonl`.

## Step 1.6 — audit B: model re-identification attack

Spawn a fresh subagent that has **no** access to `kaggle/private/` or the
repo. Give it only the anonymised CSV's `claim_uid, text, context_section`
columns and this instruction:

> You are testing an anonymised dataset. These are claims from 15 job ads by
> real employers; names were removed. List every employer you can identify,
> with your confidence (high / medium / low) and the claim_uids that gave it
> away. Guess only where you have evidence in the text.

Score its answer against the lexicon yourself: a **hit** is a correct
employer at high or medium confidence. For each hit, redact or drop the
claims it cites, then re-run the attack with a new subagent. Stop when there
are zero high/medium hits, or after three rounds — then report what is left
and let the user decide.

Record for the log: hits in round 1, hits in the final round, claims dropped,
claims further redacted. Counts only, no names.

## Step 1.7 — leak scan and golden checks

`anonymize.py --check` must:

1. Scan `claims_anon.csv` and `DATASET_CARD.md` for every lexicon string,
   case- and diacritic-folded, plus URL and e-mail patterns. **Zero hits** or
   exit non-zero.
2. Print row count, tier counts, rows dropped and why.
3. Recompute human ceiling on surviving ceiling rows. If nothing in the
   subset was dropped it must be exactly **48/50 boundary, 43/50 exact**; if
   anything was dropped, print the new numbers and flag them for the post.
4. Confirm every Tier 1 `gold_quote` is a substring of its `text`.
5. Count `preregistered_suspect` rows (expect 7 unless dropped).

## Step 1.8 — dataset card

`kaggle/data_public/DATASET_CARD.md`, no employer names:

- Source: public job-board APIs, fetched September 2026; 15 postings from 11
  boards; claims extracted by an LLM (Stage 1) and labelled blind by one
  annotator under a written rulebook.
- What each column means; the tier definitions in two lines each.
- Anonymisation steps and both audit results (counts).
- Known label issues, stated plainly: zero Tier 3 in gold; seven
  pre-registered suspect labels; one annotator, so intra- not inter-annotator
  agreement; 150 claims ≈ ±5.5pp at 95% near 87%.
- Intended use: evaluating rule-following classifiers. Not for training.
- Licence: claims are short excerpts from third-party job ads; mark the
  dataset for evaluation research only and say so.

## CHECKPOINT — user review (in chat only)

Show the user, in chat and never in a committed file:

1. A table of every redacted claim: original → anonymised, with the reason.
2. Every dropped claim with the reason.
3. Every `label_at_risk` claim and your keep/drop recommendation.
4. Audit A and audit B results.
5. The leak scan and golden check output.

Wait for explicit approval. Apply any changes the user asks for, re-run the
checks, then write the log section and stop.

## Log section to append

```
## Step 1 — anonymisation (YYYY-MM-DD)
- Rows: 150 in, N out (dropped: k tagline, k figure-only, ...)
- Redacted: N claims; placeholder counts by type
- Audit A: N searches, N hits before → 0 after
- Audit B: round-1 high/medium hits N, final N, rounds R
- Ceiling subset after drops: X/Y boundary, X/Y exact
- Decisions: ...
- Surprises: ...
```
