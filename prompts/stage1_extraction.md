# Stage 1: Claim Extraction

**Task:** Split a job posting into discrete claims.

**Input:** Raw job posting (title + full description)

**Output:** A list of individual claims, each one assertion about the job, team, company, or candidate.

---

## Instructions

1. **Read the posting end to end.** Identify every claim (assertion).

2. **Drop boilerplate.** Do NOT score:
   - Equal-opportunity statements ("We are an equal-opportunity employer")
   - Application instructions ("Apply via our website")
   - Legal disclaimers
   - Contact information
   - Company taglines without assertion

   But DO extract claims about what the hiring *process is*: named interview
   stages, a number of rounds, a stated timeline, whether an onsite is expected.
   "Apply via our website" is an instruction and is dropped; "our average process
   takes around 4 weeks" is a checkable commitment, and is often one of the most
   concrete things in the posting.

3. **One claim per assertion.** Break compound sentences into atomic claims:
   - ❌ "€60k, Go, remote" (one line, but three claims)
   - ✓ Break into: "€60,000", "Go", "remote"

4. **Extract word-for-word.** Use the posting's exact phrasing — copy the
   substring, do not tidy it. Spans are matched against hand labels by exact
   normalized text (case- and whitespace-insensitive only), so silently fixing
   a typo in the posting breaks the pairing in `eval/compare_labels.py`. Leave
   source typos intact.

5. **Order matters for context.** If a claim at the start of a section sets context for claims later, note that (you'll use it in Stage 2).

6. **Tag every claim with a `context_section` from the fixed list below.** Do not
   invent section names. Stage 3 partitions claims into role context and employer
   context using this field, and an invented name silently lands claims in the
   wrong bucket.

---

## Context sections (closed list)

Every claim takes exactly one of these values. If a claim seems to fit none of
them, pick the closest role-context value rather than inventing a name.

**Employer context** — about the company, not the job:

| Value | Covers |
|---|---|
| `Company` | what the company is, does, sells, how big or old it is |
| `Company programs` | philanthropy, public products, press and awards |
| `Culture/values` | how the company says it works and what it says it values |

**Role context** — about the job being advertised:

| Value | Covers |
|---|---|
| `Role` | what the role is, its purpose and scope |
| `Team` | the team joined, its size, mission, who is on it |
| `Responsibilities` | what the person will do |
| `Requirements` | stated musts: experience, skills, credentials |
| `Preferred qualifications` | nice-to-haves, explicitly optional |
| `Tech stack` | named languages, tools, infrastructure |
| `Product scope` | the products or surfaces the role works on |
| `Compensation` | salary, equity, bonus, incentives |
| `Benefits` | leave, budgets, perks, relocation, visas |
| `Location/schedule` | place, remote/hybrid rules, hours, flexibility |
| `Level` | seniority, ladder level, band |
| `Reporting line` | who the role reports to |
| `Hiring process` | interview stages, timeline, what the process involves |

Why the split exists: an employer's philanthropy section is full of numbers,
named places and dates, so it scores as highly specific under Stage 2's test
while promising the candidate nothing. Stage 3 reports the role-context score and
the all-claims score side by side. Extract employer-context claims normally — do
not drop them — just label them honestly.

---

## Output Format

Return a JSON array of claims. Each claim has (`context_section` must be one of
the closed-list values above):

```json
{
  "claim_id": "claim_1",
  "text": "€60,000–75,000 gross",
  "context_section": "Compensation"
}
```

**Full response:**

```json
{
  "posting_id": "YOUR_POSTING_ID_HERE",
  "title": "Job title",
  "company": "Company name",
  "total_claims": 15,
  "claims": [
    {
      "claim_id": "claim_1",
      "text": "€60,000–75,000 gross",
      "context_section": "Compensation"
    },
    {
      "claim_id": "claim_2",
      "text": "Go and PostgreSQL",
      "context_section": "Tech stack"
    },
    {
      "claim_id": "claim_3",
      "text": "two days a week in the Rīga office",
      "context_section": "Location/schedule"
    },
    {
      "claim_id": "claim_4",
      "text": "team of nine",
      "context_section": "Team"
    },
    {
      "claim_id": "claim_5",
      "text": "We invest in developer growth",
      "context_section": "Culture/values"
    }
  ]
}
```

---

## Example: Full Posting → Extracted Claims

### Input Posting:

```
Software Engineer at StartupCo

We're a 30-person startup building API infrastructure. Based in Tallinn,
with offices in London and remote roles. Founded 2019.

We're looking for a Backend Engineer with 5+ years of experience.
The role involves building microservices in Go and Rust.

Compensation: €65,000–85,000 gross, annual bonus 10–20%.
Flexible working: four-day week, or five days remote.
You'll have ownership over your services' roadmap.

We are an equal-opportunity employer. To apply, visit our careers page.
```

### Extracted Claims:

```json
{
  "posting_id": "startupco_001",
  "title": "Software Engineer",
  "company": "StartupCo",
  "total_claims": 12,
  "claims": [
    {"claim_id": "1", "text": "30-person startup", "context_section": "Company"},
    {"claim_id": "2", "text": "API infrastructure", "context_section": "Company"},
    {"claim_id": "3", "text": "Founded 2019", "context_section": "Company"},
    {"claim_id": "4", "text": "Based in Tallinn", "context_section": "Location/schedule"},
    {"claim_id": "5", "text": "offices in London", "context_section": "Location/schedule"},
    {"claim_id": "6", "text": "remote roles", "context_section": "Location/schedule"},
    {"claim_id": "7", "text": "5+ years of experience", "context_section": "Requirements"},
    {"claim_id": "8", "text": "microservices in Go and Rust", "context_section": "Tech stack"},
    {"claim_id": "9", "text": "€65,000–85,000 gross", "context_section": "Compensation"},
    {"claim_id": "10", "text": "annual bonus 10–20%", "context_section": "Compensation"},
    {"claim_id": "11", "text": "four-day week", "context_section": "Location/schedule"},
    {"claim_id": "12", "text": "ownership over your services' roadmap", "context_section": "Responsibilities"}
  ]
}
```

Note: Dropped "We're a fast-paced team" (too generic, no assertion), "equal-opportunity employer" (legal boilerplate), "visit our careers page" (application instruction).

---

## How to Use This Prompt

**In Claude / Claude Code / Gemini (text mode):**
1. Paste this prompt into the chat or editor
2. Paste the job posting
3. Ask the model to extract claims
4. Copy the JSON output

**In Cursor:**
1. Use Cmd+K (or Ctrl+K) and paste the prompt
2. Reference the posting inline or in an open editor tab
3. Let Cursor run the model; copy the result to `data/extracted/claims.jsonl`

**For batch processing:**
Keep this prompt template in a file and iterate over postings with `claude-code`:
```bash
claude code run --prompt-file prompts/stage1_extraction.md --input-file data/raw/postings.txt
```

---

## Quality Check

- [ ] All numeric claims extracted (salary, headcount, years)
- [ ] All specific tech named (Go, PostgreSQL, etc.)
- [ ] All timeframes captured (4-day week, "2 days a week in office")
- [ ] Boilerplate actually dropped (no company taglines, legal, application instructions)
- [ ] Spans are verbatim substrings of the posting (typos and all)
- [ ] No overly broad claims ("we hire good people" — too vague; break into specifics if any)
- [ ] Every `context_section` is one of the closed-list values — no invented names
- [ ] Interview-process claims kept; application instructions dropped
