# Evaluation Results

Sections marked **MEASURED** contain real numbers. Everything else is a
placeholder (`—`) and must not be quoted anywhere until filled by
`eval/compare_labels.py` or a measured run.

```bash
python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl \
  --report eval/RESULTS.md
```

Note: running the command above regenerates this file from the script's template
and will drop the annotator-consistency section below. Keep
`eval/annotator_passes.md` as the source of truth for it and paste it back, or
write the report to a scratch path and merge by hand.

---

## 1. Annotator Consistency — the noise floor **[MEASURED]**

The same 36 model-extracted claims from one real eval posting (`posting_A`;
large US fintech, senior IC role — no company named, per the aggregate-only
rule) were tier-labeled twice by the same annotator, one day apart, **before any
written decision rule existed**.

| Measure | Value |
|---|---|
| Claims | 36 |
| Exact-tier agreement between passes | **75.0%** (9 of 36 changed) |
| Tier 1 / Other boundary agreement | **80.6%** (7 of 36 crossed) |
| Specificity score, pass 1 | 0.333 (T1=12, T2=19, T3=5) |
| Specificity score, pass 2 | 0.472 (T1=17, T2=12, T3=7) |

The headline score moved **42% in relative terms** with no change to the
document and no change to the taxonomy — only to the annotator's unwritten sense
of the Tier 1 boundary.

**Consequence for every model number below:** a classifier at 80% boundary
agreement with these labels is at the annotator's own noise floor and cannot be
distinguished from one that is simply as inconsistent as the human. The original
≥80% quality gate was therefore set at the level of noise.

**What was changed in response:** the Tier 1 boundary was rewritten as a
mechanical test — "name the particular you can quote" — in
`prompts/shared_context.md`, with the six specific reasons that caused the drift
listed as explicit non-criteria ("expert work", "works with named teams",
product category, and so on). Full per-claim diff in
`eval/annotator_passes.md`.

Enforcement, not just documentation: `eval/label_claims.py` refuses a Tier 1
whose reasoning does not quote its claim, and `--verify` reports 34 errors when
run against the drifted pass.

### Post-rule consistency (re-measure after relabeling)

| Measure | Value |
|---|---|
| Claims re-labeled blind | — |
| Exact-tier agreement | — |
| Tier 1 / Other boundary agreement | — (expect > 90% if the rule works) |

---

## 2. Test Set **[MEASURED]**

- Postings sampled: **15** (balanced across board, region and seniority)
- Claims labeled: **150** (cap of 10 per posting, sampled from 745 extracted)
- Labeling protocol: tiers adjudicated on Stage 1 spans, blind to
  `predicted_tier`, via `eval/label_claims.py`
- Annotators: 1
- Label file audit: `python eval/label_claims.py --verify eval/labeled.jsonl`
  — 0 errors

### Label distribution

| Tier | Claims | Share |
|---|---|---|
| 1 — Concrete | 61 | 41% |
| 2 — General direction | 89 | 59% |
| 3 — Empty slogan | **0** | **0%** |

Overall specificity across the labeled set: **0.407**. Per-posting scores range
0.00–0.90, median 0.30, so the metric does discriminate between documents.

Label-quality signals: all 89 Tier 2 reasonings were typed by hand rather than
accepting the default, and the 61 Tier 1 claims carry 54 distinct quoted spans.
Particular types cited: named tech 27, number 10, unlabeled 9, credential 9,
named place 6.

## 3. Per-Claim Agreement **[MEASURED]**

150 gold claims, all 150 paired (zero text drift between Stage 1 and Stage 2).

- Exact-tier accuracy: **76.7%** — 95% CI [69, 83]

| Tier | Precision | Recall | F1 | Gold support |
|---|---|---|---|---|
| 1 — Concrete | 0.902 | 0.754 | 0.821 | 61 |
| 2 — General direction | 0.831 | 0.775 | 0.802 | 89 |
| 3 — Empty slogan | 0.000 | n/a | n/a | **0** |

> **Tier 3 precision of 0.000 is an artifact, not a result.** The model predicted
> Tier 3 sixteen times; the gold set contains none, so precision is 0/16 and
> recall is undefined. It measures the absence of Tier 3 in the labels, not the
> model's ability to find slogans. See section 5 and section 7.

### Confusion matrix (gold → predicted)

| | →1 | →2 | →3 |
|---|---|---|---|
| **gold 1** | 46 | 14 | 1 |
| **gold 2** | 5 | 69 | 15 |
| **gold 3** | 0 | 0 | 0 |

### Score comparison

| | Tier 1 | Tier 2 | Tier 3 | Specificity |
|---|---|---|---|---|
| Human gold | 61 | 89 | 0 | **0.407** |
| Model | 51 | 83 | 16 | **0.340** |

The model scores this corpus **lower** than the annotator did. It is more
conservative about Tier 1 and willing to use Tier 3, both of which push the ratio
down. Given the two structural biases in section 5 — which both inflate the human
figure — the model's 0.340 is arguably the better estimate of the two.

## 4. Tier 1 / Other Boundary **[MEASURED]**

The only distinction the specificity score depends on.

| Measure | Value |
|---|---|
| Accuracy | **86.7%** |
| 95% CI | **[80, 91]** |
| Tier 1 precision | 0.902 |
| Tier 1 recall | 0.754 |
| F1 | 0.821 |
| Claim pairs | 150 |

**Read against the noise floor, not against zero** — but note which floor.

The only self-agreement figure available is **80.6%, measured before the written
Tier 1 rule existed**, on a different posting (section 1). The model sits +6.1pp
above that, with a CI lower bound of 80 landing exactly on it.

> **This comparison is against the annotator's worst consistency, not their
> current one.** The rule in `prompts/shared_context.md` was written precisely to
> raise that number, and post-rule self-agreement has not been measured. If it
> comes in around 90%, the model at 86.7% is *below* the annotator and the
> conclusion of this section inverts. Until that 30-claim re-label is done, the
> only defensible statement is: **the classifier beats the annotator's pre-rule
> consistency.** It is not yet known whether it beats the annotator's post-rule
> consistency, and this report does not claim so.

Quality gates, both cleared:

- Tier 1 boundary accuracy ≥ 80% — **PASS** (86.7%)
- Tier 1 precision ≥ 0.85 — **PASS** (0.902)

Recall of 0.754 is the weaker half: the model declines Tier 1 on a quarter of the
claims the annotator accepted. Section 7 shows that on several of those the model
is defensibly right, so this understates it.

**A smoke test on the first 4 postings gave 92.5% on the same boundary.** The full
15 gave 86.7%. A 40-claim slice was optimistic by ~6pp — worth remembering before
quoting any partial run.

## 5. Extraction Spot-Check (qualitative) **[MEASURED]**

Extraction is assessed by reading postings against their extracted claims.
Span-matching F1 is deliberately out of scope — see the limitations.

### Mechanical checks, all 15 postings / 745 claims

| Check | Result |
|---|---|
| Claims whose text is verbatim in its posting | **745 / 745 (100%)** |
| Claims matching boilerplate patterns (EEO, accommodations, "apply") | **0** |
| Claims missing `claim_id` or `text` | 0 |
| Duplicate `claim_id` within a posting | 0 |
| Duplicate claim text within a posting | 0 |
| Claim length (chars) | median 71, p90 130, max 257 |
| Claims over 240 chars (whole paragraphs) | 1 |

100% verbatim is the load-bearing number: claims are paired with hand labels by
exact normalized text, so a paraphrased span could never be matched and would
drop out of the evaluation silently.

### Consistency across four separate chat sessions

Per-posting claim counts run 27–80, which is document length, not extractor
drift. Normalised by body length:

| Batch | n | median claims / 1,000 chars | range |
|---|---|---|---|
| batch1 | 4 | 8.2 | 7.2–8.5 |
| batch2 | 4 | 8.0 | 6.4–9.2 |
| batch3 | 3 | 7.4 | 5.6–7.4 |
| batch4 | 4 | 10.2 | 6.4–11.9 |
| **overall** | 15 | **8.1** | 5.6–11.9 (2.1×) |

Within-batch ranges overlap, so the prompt held its behaviour across four
independent sessions. Batch 4 sits high on two postings from one employer whose
copy genuinely packs numbers densely (`Over 100,000 businesses`,
`US$130bn+ processed annually`, `across 30+ countries` are correctly three
claims, not one).

### What extraction missed — read against the source

Two postings read sentence by sentence against their claims:

| Posting | Claims | Sentences ≥45 chars | Uncovered | of which boilerplate | of which real content |
|---|---|---|---|---|---|
| A (51-claim, fintech) | 51 | 58 | 25 | 3 | 22 |
| B (42-claim, infrastructure) | 42 | 57 | 22 | 6 | 16 |

**Boilerplate was dropped correctly** — EEO statements, accommodation notices,
privacy commitments, application instructions, and the "studies show women and
people of colour might hesitate to apply" paragraph.

**The uncovered remainder is overwhelmingly mission and atmosphere language:**

```
We're on a mission to make money work for everyone.
We're waving goodbye to the complicated and confusing ways of traditional banking.
At <company>, we are on a mission to help build a better Internet.
We're a highly ambitious, large-scale technology company with a soul.
```

These are Tier 3 claims by the taxonomy's own deletion test, and they were not
extracted. See "Known bias" below.

**Two genuine misses** were real responsibility claims, not slogans:
`You will be responsible for safeguarding our systems, applications, and data by
ensuring secure…` and `Security engineers take part in a wide variety of tasks
and projects in the team.` Stage 1 skips some responsibility prose.

### Confirmed after labeling: Tier 3 was never observed

Predicted as a bias, measured as a total absence. **0 of 150 labeled claims are
Tier 3.** Two independent causes, and only the first was anticipated.

**Cause 1 — extraction suppresses company slogans.** Only **17 of 745** extracted
claims (2.3%) match slogan patterns, and just 4 reached the 150-claim sample.
The source postings are full of this language; Stage 1 drops it as atmosphere.
The claims never reached the annotator, so Tier 3 could not be chosen.

**Cause 2 — the Tier 1 rule made Tier 3 harder to reach.** Tier 1 was given a
mechanical test ("quote the particular"); the Tier 2 / Tier 3 boundary was left to
the deletion test in prose. Sharpening one boundary destabilised the other. The
same claim shapes that `posting_A` labeled Tier 3 *before* the rule existed now
land in Tier 1 or 2:

| Claim shape | `posting_A` (pre-rule) | New blind set |
|---|---|---|
| "Ability to communicate results clearly and focus on impact" | Tier 3 | — |
| "Excellent written and verbal communication skills in English" | — | **Tier 1**, `credential: "English"` |
| "Strong communication skills — you can clearly articulate technical…" | — | Tier 2 |
| "Ability to work with urgency and focus while adapting…" | — | Tier 2 |
| "strong problem-solving under pressure" | Tier 3 | — |

**This exposes a false-positive class in the Tier 1 rule.** Any generic
requirement containing a quotable-but-uninformative noun escapes Tier 3:
`English` is a named language, not a checkable particular about *this* job —
nearly every posting in the corpus requires it. The same applies to the
employer's own name: 4 Tier 1 claims are justified by quoting `Stripe` in a
Stripe posting, of which only `Stripe Terminal` (a named product) is clearly
defensible.

### What this means for the numbers

The reported 0.407 is an overestimate on **two** counts, both pushing the same
way:

1. Tier 3 is missing from the denominator, so `specificity` is in practice
   `tier_1 / (tier_1 + tier_2)` on this corpus, not the three-tier ratio the
   taxonomy defines.
2. Tier 1 is over-populated by the false-positive class above.

Between-posting comparisons survive — both biases apply uniformly — but absolute
scores should not be quoted as measurements of slogan content.

### The fix, deliberately deferred

Two changes, neither made for this release:

1. **Stage 1** must extract mission and culture statements instead of treating
   them as atmosphere. Prompt change plus a re-run.
2. **The taxonomy needs a mechanical Tier 3 test symmetric with Tier 1's**, plus
   an explicit non-particulars list — the employer's own name, `English`, bare
   skill nouns — so a quotable token that is not job-specific cannot lift a claim
   out of Tier 3.

Labels were **not** retro-edited after this analysis. Changing blind labels once
the pattern is visible is the same anchoring failure the protocol exists to
prevent; the finding is documented instead.

## 6. Cost & Latency **[ESTIMATED — read the caveats]**

### Which model produced these tiers

`data/classified/claims.jsonl` records `"model": "claude-opus-5"` on every row.
**That is a label, not a measurement.** Stage 2 was run through a chat interface
configured with that identifier; the model actually serving any given turn can
differ, and a chat session gives no way to verify it. Treat the version as
approximate provenance. An instrumented API run is the only way to attest to it.

### Token estimate

Stage 1 and Stage 2 were both run by pasting into a chat, so no token counts were
captured. The figures below are **derived from character counts of the actual
files on disk** — exact and reproducible — converted at a 4-chars-per-token rule
of thumb. JSON tokenises worse than prose, so treat the token numbers as ±25%.

| Stage 2 input | Chars | ≈ Tokens |
|---|---|---|
| Prompt + shared context, re-sent per batch (×4) | 94,240 | 23,560 |
| Claim batches (4 files) | 29,361 | 7,340 |
| **Total input** | **123,601** | **~30,900** |
| **Total output** | **44,331** | **~11,100** |

Per posting: **~2,060 input / ~740 output tokens**.
Per 1,000 postings: **~2.06M input / ~0.74M output tokens**.

Cost per 1,000 postings = `2.06 × input_rate + 0.74 × output_rate` (rates per
million tokens, taken from the vendor's current price list at time of writing —
deliberately not hard-coded here, because published rates change and a stale
number in a README is worse than an arithmetic instruction).

### The finding: 76% of input tokens are prompt, not data

Of ~2,060 input tokens per posting, roughly **1,570 are the prompt** re-sent with
each batch and only ~490 are the claims being classified. At four postings per
batch the taxonomy is paid for four times over.

Batching ten postings instead of four drops prompt overhead from ~1,570 to ~590
tokens per posting — **input cost falls by about 48%** with no change to the
prompt or the model. For a chat-driven pipeline, batch size is the single largest
cost lever.

### Wall clock

| Measure | Value |
|---|---|
| Operator cycle time per batch (paste → wait → save → ingest) | 28, 10, 8 min |
| Model response, batch 1 only, by stopwatch | ~2 min |
| **Inference latency per posting** | **not instrumented** |

The batch times come from output-file timestamps and are **operator cycle time**,
not inference latency — they include reading, saving and ingesting. The 28 → 10 →
8 trend is the operator learning the loop, not the model speeding up.

**Inference latency is not reported because a chat-driven pipeline cannot measure
it.** Response time in a chat UI includes queueing and streaming and cannot be
separated from them. A single stopwatch reading of ~2 minutes for 4 postings (~30
s/posting) is recorded only as an order of magnitude. Quoting a per-posting
latency from this setup would be a fabricated number, so none is quoted.

### What would close this properly

A 20-claim instrumented API run returns exact token counts and real latency in
well under an hour. It was not done here because the project's scope forbids
stored credentials — a deliberate trade, recorded rather than hidden.

## 7. Disagreements **[MEASURED]**

23 of 150 claims disagree. They are not randomly distributed — they cluster on the
two boundaries section 5 predicted would be weak.

### The pre-registration paid off

Seven labels were recorded as suspect in this section **before Stage 2 was run**,
so that a later disagreement could not be explained away after the fact. The model
disagreed on **4 of the 7**, and all four are the group flagged as "likely wrong":

| Pre-registered claim | Human | Model | Called it? |
|---|---|---|---|
| "Millions of companies—from the world's largest enterprises…use Stripe…" | 1 | **2** | Yes — flagged *likely wrong* |
| "Stripe Terminal helps Stripe users extend their online presence…" | 1 | **2** | Yes — flagged *defensible*, model disagrees anyway |
| "The Terminal team's mission is to make it as easy for businesses…" | 1 | **2** | Yes — flagged *borderline* |
| "Share research insights that deepen Stripe's understanding of user needs" | 1 | **3** | Yes — flagged *likely wrong*; model went further, to Tier 3 |
| "Proficient in both spoken and written English." | 1 | 1 | No — model agreed with the human |
| "Excellent written and verbal communication skills in English" | 1 | 1 | No — model agreed |
| "on a mission to empower small businesses across the globe" | 2 | 2 | No — model agreed |

**Every claim justified by quoting the employer's own name was downgraded by the
model.** That confirms the false-positive class named in section 5 and, on these
four, the model is right and the annotator wrong.

**The `English` predictions were wrong, and they were mine.** Both were flagged as
suspect Tier 1s; the model independently agreed with the human. So did the slogan
call. Three of seven pre-registrations did not survive contact — recorded here
because a pre-registration you only report when it wins is worthless.

### Where the model is right and the human is wrong

**Tier 1 the annotator missed (gold 2 → model 1, 5 claims).** Each quotes a real,
auditable particular:

```
"more than 425 local government election websites in 33 states"   two auditable counts
"connections to over 350 platforms businesses use everyday"       a counted surface
"one of our local offices around the globe, from New York to Bangkok"  named offices
"named to Entrepreneur Magazine's Top Company Cultures list"      a named publication
"A basic understanding of SQL and Data / BI tools"                a named query language
```

These are Tier 1 by the written rule and were labeled Tier 2. The annotator's
Tier 1 errors therefore run in **both** directions, not just the permissive one.

**Tier 3 the annotator never used (gold 2 → model 3, 15 claims; gold 1 → 3, 1).**
The model applied the deletion test the taxonomy defines and the annotator stopped
applying:

```
"You can balance strategy and execution, translating ambitious goals into tangible outcomes"
   model: "balance strategy and execution" would read identically in an ad for a different job
"comfortable making decisions in environments where there is rarely a perfect answer"
   model: removing the line costs the reader nothing
"can navigate ambiguity and create clarity where goals…are not yet defined"
   model: delete it and nothing is lost
```

16 Tier 3 predictions against 0 in gold settles the section 5 question: **Tier 3
was reachable from this taxonomy — the annotator's boundary had moved.** The
mechanical Tier 1 rule pulled claims up out of Tier 3 and nothing pulled them
back down.

### Where the human is probably right

**Gold 1 → model 2, 14 claims.** Several are the model over-applying its own
escape-hatch reasoning to qualified technology mentions:

```
"primarily in Swift"   model: "primarily" qualifies the named language
```

`Swift` is a named technology and the hedge is about proportion of time, not about
whether Swift is used. The written rule says a hedge on a *list of named things*
does not dissolve it. Here the annotator followed the rule and the model did not.

### What this changes

Nothing in the gold set. Labels were not edited after seeing model output — that
is the anchoring failure the whole protocol exists to prevent. The conclusion is
about the **taxonomy**, not the labels: Tier 1 needs a non-particulars exclusion
list and Tier 3 needs a mechanical test, both already written up in section 5 as
the deferred fix.

## Quality Gates

| Gate | Status |
|---|---|
| Tier 1 boundary accuracy ≥ 80% | **PASS** — 86.7%, 95% CI [80, 91] |
| Tier 1 boundary above annotator self-agreement | **PASS, narrowly** — +6.1pp over the 80.6% floor, but the CI lower bound sits on it |
| Tier 1 precision ≥ 0.85 | **PASS** — 0.902 |
| Extraction spot-checked against the source | **PASS** — section 5 |
| Cost per 1,000 postings | **ESTIMATED** — from character counts, method and ±25% stated (section 6) |
| Latency per posting | **NOT MEASURABLE** from a chat-driven pipeline; needs an instrumented API run (section 6) |
| Tier 3 observable at all | **FAIL** — 0 of 150 gold claims; scored as a two-tier metric (sections 5, 7) |
| Annotator self-agreement re-measured after the written rule | **NOT DONE** — 30-claim blind re-label, needs a day's gap |

Two gates are unmet and neither is hidden: latency cannot be obtained from this
setup, and Tier 3 never appeared in the labels. Both have a stated cause and a
stated fix.
