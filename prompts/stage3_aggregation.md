# Stage 3: Aggregation & Analysis

**Task:** Aggregate classified claims into per-posting specificity scores and roll
up **by seniority and region**.

> **Reported rollups are seniority and region only.** `sector` and
> `company_size` are still computed per posting and kept in
> `results/scores.jsonl` as diagnostics, but they are not reported: size resolves
> to `unknown` for 143 of 144 postings (headcount is inferred from the posting
> text, and postings do not state it), and every board in the corpus is a
> software/fintech employer so sector has one real bucket. See
> `prompts/shared_context.md` → "Rollups we do not report, and why".
>
> **Every number in the examples below is invented** to show the shape of the
> output. Real figures live in `results/` after a run.

**Input:** Classified claims from Stage 2 (with tier assignments)

**Output:** Specificity scores, metadata, and aggregate statistics.

---

## Scoring Formula

For each posting:

```
specificity_score = tier_1_claims / (tier_1 + tier_2 + tier_3)
```

Example:
- Tier 1 claims: 8
- Tier 2 claims: 2
- Tier 3 claims: 1
- **Specificity score:** 8 / 11 = 0.73

---

## Per-Posting Output

For each classified posting, output:

```json
{
  "posting_id": "startupco_001",
  "title": "Software Engineer",
  "company": "StartupCo",
  "source": "greenhouse_startupco",
  "posted_at": "2026-09-01",
  "total_claims": 11,
  "tier_1_claims": 8,
  "tier_2_claims": 2,
  "tier_3_claims": 1,
  "specificity_score": 0.73,
  "metadata": {
    "location_primary": "Tallinn",
    "location_secondary": ["London", "Remote"],
    "company_size": "30-50",
    "sector": "software",
    "seniority": "mid-to-senior"
  }
}
```

**Save all per-posting scores to:** `results/scores.jsonl`

---

## Aggregation Levels

After scoring all postings, calculate rollups:

### By Seniority
```json
{
  "seniority": "senior",
  "count": 156,
  "avg_specificity": 0.61
}
```

### By Region
```json
{
  "region": "baltics",
  "count": 34,
  "avg_specificity": 0.56,
  "median_specificity": 0.57,
  "percentiles": {"p10": 0.21, "p25": 0.38, "p50": 0.57, "p75": 0.70, "p90": 0.81}
}
```

---

## Computed but NOT reported

Kept in `results/scores.jsonl` for auditing; excluded from the write-up and from
`results/summary.md`.

### By Sector — not reported (one real bucket)
```json
{
  "sector": "software",
  "count": 245,
  "avg_specificity": 0.58,
  "median_specificity": 0.61,
  "std_dev": 0.16,
  "percentiles": {
    "p10": 0.28,
    "p25": 0.45,
    "p50": 0.61,
    "p75": 0.72,
    "p90": 0.85
  }
}
```

### By Company Size — not reported (99% `unknown`)
```json
{
  "size_bracket": "50-200",
  "count": 89,
  "avg_specificity": 0.62,
  "median_specificity": 0.64,
  "by_sector": {
    "software": {"avg_specificity": 0.64, "count": 45},
    "data": {"avg_specificity": 0.59, "count": 22}
  }
}
```

---

## Metadata Rules

Assign metadata based on posting content (use Stage 1 claims + common sense):

**Company Size** (diagnostic only — not reported):
- "1–10 people" → `"1-10"`
- "30-person startup" → `"10-50"`
- "250+ employees" → `"200+"`
- Unknown → `"unknown"`

**Sector** (diagnostic only — not reported; this is really *department*):
- Roles with "Engineer", "Developer", "Architecture" → `"software"`
- Roles with "Data", "Analytics", "ML" → `"data"`
- Roles with "Product", "Manager" (non-technical) → `"product"`
- Roles with "Design", "UX" → `"design"`
- Other → `"other"`

**Seniority:**
- "5+ years", "Senior", "Lead" → `"senior"`
- "2-4 years", "Mid-level" → `"mid"`
- "0-2 years", "Junior", "Graduate" → `"junior"`
- Not specified → `"unspecified"`

**Region:**
- Mentions of Baltics (LV, LT, EE) → `"baltics"`
- Mentions of EU → `"eu"`
- Remote or global → `"remote"`
- Specific country where listed → Use ISO 2-letter code

---

## Output Files

### 1. Per-posting scores
**File:** `results/scores.jsonl`

One line per posting with full score + metadata.

### 2. Aggregate statistics
**File:** `results/aggregates.json`

```json
{
  "generated_at": "2026-09-10T15:30:00Z",
  "corpus_size": 1043,
  "by_seniority": [...],
  "by_region": [...],
  "by_sector": [...],
  "by_size": [...]
}
```

### 3. Summary statistics
**File:** `results/summary.md`

```markdown
# Specificity Scores: Summary

## Overall
- **Postings analyzed:** 1,043
- **Average specificity:** 0.58
- **Median specificity:** 0.61
- **Std. dev:** 0.16
- **Range:** 0.05–0.97

## By Seniority
| Level | Count | Avg | Median |
|-------|-------|-----|--------|
| Junior | 145 | 0.54 | 0.56 |
| Mid | 456 | 0.58 | 0.60 |
| Senior | 289 | 0.61 | 0.64 |
| Unspecified | 153 | 0.56 | 0.58 |

## By Region
| Region | Count | Avg | Median |
|--------|-------|-----|--------|
| Baltics | 78 | 0.55 | 0.57 |
| EU | 445 | 0.58 | 0.61 |
| Remote | 334 | 0.60 | 0.62 |
| Other | 186 | 0.57 | 0.60 |
```

---

## How to Use

**Primary path (recommended):**

```bash
python src/pipeline/aggregate.py data/classified/claims.jsonl results/ \
  --raw data/raw/raw_postings.jsonl
```

**LLM spot-check only:** paste this prompt with 10–20 classified postings to sanity-check a few scores against the script output. Do not use an LLM as the production aggregator.

---

## Output Quality Checks

- [ ] Every posting has exactly one score (0.0 ≤ score ≤ 1.0)
- [ ] Aggregates match when recalculated (audit a few hand)
- [ ] No division-by-zero (postings with 0 claims are excluded)
- [ ] Seniority and region assigned consistently (the two reported rollups)
- [ ] `results/summary.md` contains no sector or size table
- [ ] Percentiles are in order (p10 < p25 < p50 < p75 < p90)
- [ ] Summary charts are readable and not misleading

