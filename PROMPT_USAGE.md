# Using the Prompts Across Environments

Stages **1** and **2** are LLM prompts. Stage **3** is `src/pipeline/aggregate.py` (do not paste hundreds of postings into a chat for scoring).

Hand labeling sits **between** Stage 1 and Stage 2: you label tiers on the spans
Stage 1 extracted. See `GETTING_STARTED.md` sections 3-5.

---

## Prompts

1. `prompts/stage1_extraction.md` — split postings into claims  
2. `prompts/stage2_classification.md` — assign Tier 1 / 2 / 3  
3. `prompts/shared_context.md` — taxonomy reference (keep open while labeling)

---

## Claude / Gemini (web)

1. Paste the stage prompt  
2. Paste 5–10 postings (or, for Stage 2, the extracted claims)  
3. For Stage 1, save the reply to a file and run
   `python eval/ingest_extraction.py out.json --append` — it flattens the JSON and
   refuses spans that are not verbatim. For Stage 2, append **one object per
   line** to the matching `*.jsonl`.
   Flatten pretty-printed output first — `compare_labels.py` and
   `aggregate.py` parse line by line, and a multi-line object reads as zero
   rows with no error:
   `python -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1]))))" out.json >> data/classified/claims.jsonl`

Batch large corpora manually: split input, run several chats, concatenate outputs.

---

## Cursor

1. Open the raw or extracted JSONL  
2. Inline edit / Agent: “Apply `prompts/stage1_extraction.md` to the next N postings; append valid JSONL”  
3. Spot-check a few claims against the taxonomy before scaling

---

## Claude Code / CLI agents

Point the agent at the prompt file + input JSONL and ask it to write output JSONL. There is no special `claude code batch` flag required by this repo — any agent that can read/write files works.

---

## Cost-Effective Loop

Extraction first, then hand labels — not the other way round. The boundary
metric is a classification metric, so hand-labeling tiers on the model's own
extracted spans is both faster and the only way `compare_labels.py` can pair
every gold claim (it matches on exact normalized text).

1. Run Stage 1 on a **~15-posting sample** (~150 claims after a 10-per-posting cap)
2. Hand-label tiers on those spans with `python eval/label_claims.py` — it hides
   `predicted_tier` and refuses a Tier 1 whose reasoning does not quote the claim
3. Re-label ~30 claims blind (`--pass 2 --shuffle --relabel`) and compare with
   `compare_labels.py ... --self-agreement` — that is the noise floor the model
   number has to be read against
4. Run Stage 2 on the same claims
5. `python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl`
6. Iterate the Stage 2 prompt until the Tier 1 / Other boundary clears both 80%
   **and** your own self-agreement
7. Then scale extraction/classification to the full corpus
8. `python src/pipeline/aggregate.py data/classified/claims.jsonl results/`

**Do not** iterate the prompt against labels you produced while looking at the
model's output. That measures agreement with yourself-anchored-on-the-model, and
it only ever goes up.

**Model tip:** a mid-tier model (e.g. Sonnet-class or Flash-class) is usually
enough; spend tokens on the eval set, not on premature full-corpus runs.

---

## Validation Checklist

### Stage 1
- [ ] Claims are verbatim substrings of the posting, typos included  
- [ ] Boilerplate dropped (EEO, apply instructions, legal)  
- [ ] Each claim has `claim_id`, `text`, `context_section`

### Stage 2
- [ ] Every claim has exactly one `predicted_tier` (1, 2, or 3)  
- [ ] Reasoning is claim-specific  
- [ ] Every Tier 1 reasoning quotes a substring of its own claim  
- [ ] Nothing is Tier 1 for "expert work" / "real work" / "works with teams"  
- [ ] “Competitive salary” without a number → Tier 3  

### Stage 3
- [ ] `aggregate.py` produced scores in `[0, 1]`  
- [ ] Postings with 0 claims excluded  
- [ ] Rollups look sane vs a few hand-checked postings  
