# Stage 2: Claim Classification

**Task:** Classify each claim into one of three tiers.

**Input:** List of extracted claims (from Stage 1)

**Output:** The same claims, each labeled with a tier (1, 2, or 3) and reasoning.

---

## Tier Definitions

### Tier 1 — Concrete
Contains a number, a named technology, a timeframe, a verifiable fact, or a falsifiable commitment.
Someone could later say "you said this and it isn't true."

**Tier 1 Examples:**
- "€60,000–75,000 gross"
- "Go and PostgreSQL"
- "two days a week in the Rīga office"
- "on-call one week in six"
- "four-day week"
- "team of nine"
- "5+ years experience"
- "Founded 2019"

### Tier 2 — General Direction
States a real intent or attribute, but without detail that could be checked.

**Tier 2 Examples:**
- "We invest in developer growth"
- "modern stack"
- "flexible working hours"
- "you'll have ownership of your work"
- "collaborative environment"
- "strong team culture"

Note: bare "competitive salary" (no number) is **Tier 3**, not Tier 2 — see Boundary Cases.

### Tier 3 — Empty Slogan
Could appear verbatim in an ad for a completely different job at a completely different company.

**Tier 3 Examples:**
- "fast-paced environment"
- "we're like a family"
- "rockstar developer"
- "passion for excellence"
- "wear many hats"
- "solving hard problems"
- "impactful work"

---

## Decision Rules

**Tier 1 vs Tier 2 — name the particular.**

Tier 1 is not "does this describe real work?" It is "can I quote a specific
token in the claim and say what kind of particular it is?" One of:

- a number or range — `€65,000–85,000`, `3+ years`, `team of nine`, `10–20%`
- a named technology, tool, framework or taxonomy — `Go`, `Kubernetes`,
  `MITRE ATT&CK`, `Databricks`
- a named place, office or entity — `Tallinn`, `the Rīga office`
- an explicit timeframe or cadence — `four-day week`, `one week in six`,
  `by end of year`, `Founded 2019`
- a named credential with no escape hatch
- a quantified policy — `two days a week in office`, `25 days leave`

**If you cannot quote the token, it is Tier 2** — however senior, technical or
genuinely demanding the work sounds. Seriousness is not a Tier 1 criterion.

### These are NOT Tier 1 reasons

| Tempting reason | Correct tier | Why |
|---|---|---|
| "expert work", "deep technical work" | 2 | Describes difficulty, commits to nothing |
| "works with named teams", "cross-functional" | 2 | Same call as `collaborative environment` |
| "clear work assignment" | 2 | Unless it carries a number, tech or timeframe |
| product/market category (`data infrastructure platform`) | 2 | Same shape as `API infrastructure` |
| domain jargon (`TTPs of threat actors`) | 2 | Not a slogan, but not a particular either |

### Escape hatches

- `B.S. or M.S. Computer Science **or related field, or equivalent
  experience**` → **Tier 2.** The hedge removes the requirement; nothing is
  provable.
- `data tools (**e.g.** Spark, Trino)` → **Tier 1.** The named
  tools remain checkable; `e.g.` widens the list without cancelling names.

A hedge on a **requirement** can dissolve it. A hedge on a **list of named
things** usually does not.

**Tier 2 vs Tier 3:**
- Does it state a real intent specific to this job/company?
- Or could it fit *any* job ad?
- If specific → Tier 2
- If generic → Tier 3

---

## Boundary Cases

**"Competitive salary"** → Tier 3 (no data, generic phrase)

**"Competitive salary: €60–80k"** → Tier 1 (specific number added)

**"Proven track record"** → Tier 3 (not checkable, could apply anywhere)

**"3+ years as a backend engineer"** → Tier 1 (specific requirement, years quantified)

**"Join a growing team"** → Tier 3 (generic growth language, no specifics)

**"Team of 5, growing to 8 by end of year"** → Tier 1 (specific numbers, timeframe)

**"We value work-life balance"** → Tier 2 (intent stated, but not quantified like "4-day week")

**"We love innovation"** → Tier 3 (could apply to any tech company)

**"AWS, Kubernetes, Postgres"** → Tier 1 (specific tech stack named)

**"modern tech stack"** → Tier 2 (intent clear but unspecific)

### Hard cases from real postings (paraphrased)

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

## Reasoning Discipline

The `reasoning` field makes the tier falsifiable. It is not decoration.

- **Tier 1 reasoning must quote a substring of the claim** — the particular
  itself. If you cannot quote it, the tier is wrong. `"checkable tooling"` on a
  claim that names no tooling is exactly the error this rule catches.
- **Tier 2 reasoning must name what is absent:** "no number, named tech or
  timeframe".
- **Tier 3 reasoning must apply the deletion test:** "delete it and nothing is
  lost".
- **Do not reuse one reasoning string across claims of different shape.** A
  template phrase repeated across ten claims means the tier was chosen first
  and the reasoning pasted on afterwards.

---

## Output Format

Return a JSON array with classifications. Each item:

```json
{
  "claim_id": "claim_1",
  "text": "€60,000–75,000 gross",
  "predicted_tier": 1,
  "reasoning": "Explicit salary range with numeric bounds."
}
```

**Full response:**

```json
{
  "posting_id": "startupco_001",
  "model_version": "YOUR_MODEL_HERE",
  "claims": [
    {
      "claim_id": "claim_1",
      "text": "30-person startup",
      "predicted_tier": 1,
      "reasoning": "Specific headcount (number)."
    },
    {
      "claim_id": "claim_2",
      "text": "API infrastructure",
      "predicted_tier": 2,
      "reasoning": "Describes focus area but lacks specifics on what 'API' projects involve."
    },
    {
      "claim_id": "claim_3",
      "text": "Founded 2019",
      "predicted_tier": 1,
      "reasoning": "Specific founding year (verifiable date)."
    },
    {
      "claim_id": "claim_4",
      "text": "Based in Tallinn",
      "predicted_tier": 1,
      "reasoning": "Specific location named."
    },
    {
      "claim_id": "claim_5",
      "text": "remote roles",
      "predicted_tier": 2,
      "reasoning": "States availability but lacks detail on remote policy (how many days? from where?)."
    },
    {
      "claim_id": "claim_6",
      "text": "5+ years of experience",
      "predicted_tier": 1,
      "reasoning": "Specific requirement with quantified years."
    },
    {
      "claim_id": "claim_7",
      "text": "microservices in Go and Rust",
      "predicted_tier": 1,
      "reasoning": "Named technologies (specific and verifiable)."
    },
    {
      "claim_id": "claim_8",
      "text": "€65,000–85,000 gross",
      "predicted_tier": 1,
      "reasoning": "Explicit salary range."
    },
    {
      "claim_id": "claim_9",
      "text": "annual bonus 10–20%",
      "predicted_tier": 1,
      "reasoning": "Specific bonus range with percentage bounds."
    },
    {
      "claim_id": "claim_10",
      "text": "four-day week",
      "predicted_tier": 1,
      "reasoning": "Specific schedule (quantified, verifiable)."
    },
    {
      "claim_id": "claim_11",
      "text": "ownership over your services' roadmap",
      "predicted_tier": 2,
      "reasoning": "States responsibility intent, but 'ownership' is subjective and could mean many things."
    }
  ],
  "summary": {
    "total_classified": 11,
    "tier_1_count": 8,
    "tier_2_count": 2,
    "tier_3_count": 0,
    "specificity_score": 0.73
  }
}
```

---

## How to Use This Prompt

**In Claude / Claude Code / Gemini:**
1. Paste this prompt
2. Paste the extracted claims (from Stage 1 output)
3. Request classifications

**In Cursor:**
```
cmd+K: "Classify these job posting claims into tiers using the taxonomy in prompts/stage2_classification.md"
```
Then reference a file with extracted claims.

**Iteration:**
- If the model's tier assignments don't match hand-labels, adjust the reasoning explanations and re-run.
- Record disagreements in the Disagreements section of `eval/RESULTS.md`,
  noting explicitly any case where the model was right and the human wrong.

---

## Quality Check

- [ ] Every claim has exactly one tier (1, 2, or 3)
- [ ] Reasoning is specific to the claim (not a generic rule)
- [ ] No "this could be 1 or 2" hedging — pick one
- [ ] **Every Tier 1 reasoning quotes a substring of its claim**
- [ ] No reasoning string reused across claims of different shape
- [ ] No claim is Tier 1 for "expert work", "real work" or "works with teams"
- [ ] Tier 3 claims are actually generic (pass the "other ad" test)
- [ ] Specificity score calculated correctly: tier_1 / (tier_1 + tier_2 + tier_3)
