# Shared Context: Job Posting Specificity Scoring

**Project:** Measure how much of a job posting is concrete commitment vs. filler.

**Taxonomy (Definition of Tiers):**

## Tier 1 — Concrete
Contains a number, a named technology, a timeframe, a verifiable fact, or a falsifiable commitment. Someone could later say "you said this and it isn't true."

**Examples:**
- "€60,000–75,000 gross"
- "Go and PostgreSQL"
- "two days a week in the Rīga office"
- "on-call one week in six"
- "four-day week"
- "team of nine"

## Tier 2 — General Direction
States a real intent or attribute, but without detail that could be checked.

**Examples:**
- "We invest in developer growth"
- "modern stack"
- "flexible working hours"
- "you'll have ownership of your work"

## Tier 3 — Empty Slogan
Could appear verbatim in an ad for a completely different job at a completely different company without changing meaning.

**Examples:**
- "fast-paced environment"
- "we're like a family"
- "rockstar developer"
- "passion for excellence"
- "wear many hats"

**Test for Tier 3:** Delete the sentence. If nothing is lost, it is a slogan.

**Test for Tier 1 vs Tier 2:** Could a candidate be disappointed in a provable way?

---

## The Tier 1 Test: Name the Particular

Tier 1 is not "does this describe real work?" — it is "can I point at a
specific token in the claim and name what kind of particular it is?"

Before assigning Tier 1, quote the particular and name its type:

| Type | Examples |
|---|---|
| Number or range | `€65,000–85,000`, `3+ years`, `team of nine`, `10–20%` |
| Named technology, tool, framework or taxonomy | `Go`, `Kubernetes`, `Postgres`, `MITRE ATT&CK`, `Databricks` |
| Named place, office or entity | `Tallinn`, `the Rīga office`, `offices in London` |
| Explicit timeframe or cadence | `four-day week`, `one week in six`, `by end of year`, `Founded 2019` |
| Named credential, with no escape hatch | `B.Sc. Computer Science` (but see Escape Hatches below) |
| Quantified policy | `two days a week in office`, `25 days leave`, `annual bonus 10–20%` |

**If you cannot quote the token, it is not Tier 1.** No matter how senior,
technical, expert or genuinely real the work sounds. Seriousness is not a
Tier 1 criterion.

### Not Tier 1 criteria

These are the ways this boundary is most often got wrong. Each of them is
Tier 2 (real intent, nothing checkable), not Tier 1:

- **"Expert / specialist / deep work."** `investigating high-risk accounts and
  identifying complex abuse patterns` describes demanding work and commits to
  nothing checkable. Tier 2.
- **"Works with named teams."** `work cross-functionally with the security, risk
  and data science teams` names internal org units, not a particular you can
  check on day one. Tier 2 — the same call as `collaborative environment`.
- **"Clear work assignment."** `works directly with affected customers to
  resolve incidents rapidly` — `rapidly` is unquantified. Tier 2.
- **Product or market category.** `data infrastructure platform for
  enterprises` is the same shape as `API infrastructure`. Tier 2.
- **Domain jargon alone.** `understanding the TTPs of threat actors` is
  domain-specific, so it is not an interchangeable slogan — but it names no
  particular either. Tier 2, not Tier 1 and not Tier 3.

### Escape hatches

A particular can be cancelled by the hedge wrapped around it. Ask whether the
hedge removes the commitment:

- `B.S. or M.S. Computer Science **or related field, or equivalent
  experience**` → **Tier 2.** After the hedge, nothing is actually required,
  so no candidate can be disappointed in a provable way.
- `data tools (**e.g.** Spark, Trino)` → **Tier 1.** The named
  tools are still checkable facts about the stack; `e.g.` widens the list
  without cancelling the names.

Rule of thumb: a hedge on a **requirement** can dissolve it; a hedge on a
**list of named things** usually does not.

### Reasoning discipline

The `reasoning` field exists to make the tier falsifiable, not to justify it
after the fact.

- For **Tier 1**, the reasoning must quote a substring of the claim — the
  actual particular. `"checkable tooling"` attached to a claim containing no
  tooling is the failure mode this rule exists to catch.
- For **Tier 2**, name what is missing: `"no number, tech or timeframe"`.
- For **Tier 3**, apply the deletion test explicitly.
- Never reuse a reasoning string across claims of different shape. A template
  phrase appearing on ten claims means the tier was chosen first and the
  reasoning pasted on.

---

## What This Score Does NOT Measure

- **Not honesty.** A precise promise can be broken; a vague ad can conceal a good job.
- **Not quality.** Some excellent employers write badly.
- **Not intent.** Much filler is copied from a template by someone who did not choose it.
- **Not the candidate's experience.** This measures the information content of a document, nothing more.

---

## Scoring Formula

```
specificity_score = tier_1_claims / (tier_1 + tier_2 + tier_3)
```

Using a proportion (not a count) normalizes for posting length.

---

## Key Rules

1. **Boilerplate = Dropped.** Equal-opportunity statements, application instructions, legal disclaimers are not scored.

2. **One claim per assertion.** A claim is one assertion about the job, team, company, or candidate.

3. **Extract before scoring.** Break the posting into individual claims first (Stage 1). Classification (Stage 2) comes after.

4. **No interpretation.** Score what the posting says, not what you assume it means.

5. **Context from position.** A claim at the start carries the same weight as one at the end (no positional weighting yet).

6. **Requirements vs. Offers.** At v1: score them the same way. ("5+ years Go" and "€60k" both score identically.)

---

## Boundary Cases

**"Competitive salary"** — Tier 3 (no number, generic phrase).

**"Competitive salary: €60–80k"** — Tier 1 (specific range given).

**"Proven track record"** — Tier 3 (not checkable, could apply anywhere).

**"3+ years as a backend engineer"** — Tier 1 (specific requirement, verifiable).

**"Join a growing team"** — Tier 3 (generic, applies everywhere).

**"Team of 5, growing to 8 by end of year"** — Tier 1 (specific numbers, timeframe).

### From real postings (paraphrased)

These are the cases that actually caused annotator disagreement, drawn from
`posting_A` in the eval set. **Wording is paraphrased and no company is named**
— the repo commits code and aggregates only. The shape of each case, which is
what teaches the boundary, is unchanged. Measurement: `eval/annotator_passes.md`.

| Claim (paraphrased) | Tier | Why |
|---|---|---|
| "data infrastructure platform for enterprises" | 2 | Product category; same shape as "API infrastructure" |
| "a cross-disciplinary group of incident managers, investigators, security engineers and data scientists" | 1 | Enumerated roles — a checkable fact about team composition |
| "works directly with affected customers to resolve incidents rapidly" | 2 | "rapidly" is unquantified |
| "operating primarily across three European time zones" | 2 | "primarily" cancels the named zones |
| "investigating high-risk accounts and identifying complex abuse patterns" | 2 | Demanding work, no particular |
| "classifying findings using MITRE ATT&CK" | 1 | Named framework |
| "work cross-functionally with the security, risk and data science teams" | 2 | Named internal teams are not a day-one checkable |
| "3+ years of experience conducting incident response" | 1 | Quantified requirement |
| "B.S. or M.S. Computer Science or related field, or equivalent experience" | 2 | Escape hatch dissolves the requirement |
| "expert knowledge of Python and SQL" | 1 | Named technologies |
| "experience with data tools (e.g. Spark, Trino)" | 1 | Named tools survive the "e.g." |
| "an adversarial mindset, understanding the TTPs of threat actors" | 2 | Domain-specific, so not a slogan; no particular, so not Tier 1 |
| "ability to communicate results clearly and focus on impact" | 3 | Fits any posting; deletion loses nothing |
---

## Dataset Info

- **Sources:** Greenhouse Job Board API (public boards), Lever, Ashby, HN "Who is hiring?"
- **Language:** English-language postings only (v1)
- **Roles:** Software and adjacent roles
- **Target corpus:** ~1,000 postings
- **Aggregation:** By **seniority** and **region** only (NEVER by individual company)

### Rollups we do not report, and why

`aggregate.py` still computes `sector` and `company_size` per posting — they stay
in `results/scores.jsonl` as diagnostics — but neither is reported, because
neither is supported by the data:

- **Company size.** It is inferred from the posting text ("30-person startup",
  "team of nine"). Measured over the first 144-posting corpus, it resolved to
  `unknown` for **143 of 144** postings. Widening the corpus does not help: job
  postings simply do not state headcount, so this is a property of the documents,
  not of the sample.
- **Sector.** Every board in the corpus is a software or fintech employer, so a
  sector rollup has one real bucket. What `infer_sector` actually separates is
  *department* (engineering / data / product / design), which is a different and
  much narrower claim than "sector".

"Postings almost never state headcount" is itself a finding about specificity and
belongs in the write-up as prose — not as a rollup table that is 99% one cell.
