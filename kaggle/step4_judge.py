# =============================================================================
# STEP 4 — The judge: Stage 1 extraction + Stage 2 classification
# Paste this whole file into ONE Kaggle notebook cell, after steps 1–3.
#
# Ported from the repo's prompts/shared_context.md, stage1_extraction.md and
# stage2_classification.md, with three deliberate changes:
#   1. The Stage 1 KNOWN DEFECT is fixed: mission / culture / values statements
#      are extracted (they are the Tier 3 class), not dropped as atmosphere.
#   2. The Tier 3 KNOWN GAP's non-particulars list is part of the Tier 1 rule.
#   3. New for generated ads: placeholders ("[salary range]", "€XX,XXX") are
#      flagged and never count as a particular.
# The code enforces what ingest_extraction.py / label_claims.py enforced:
# verbatim spans, closed-list sections, every claim classified once, and a
# Tier 1 must quote a substring of its own claim.
# =============================================================================
import json
import re
import unicodedata

from pydantic import BaseModel, ValidationError

import kaggle_benchmarks as kbench

# JUDGE is set in step 1 — one fixed model, never MODEL_A or MODEL_B.

# --- Closed vocabulary (stage1_extraction.md) --------------------------------
EMPLOYER_SECTIONS = {"Company", "Company programs", "Culture/values"}
ROLE_SECTIONS = {
    "Role", "Team", "Responsibilities", "Requirements", "Preferred qualifications",
    "Tech stack", "Product scope", "Compensation", "Benefits", "Location/schedule",
    "Level", "Reporting line", "Hiring process",
}
ALL_SECTIONS = EMPLOYER_SECTIONS | ROLE_SECTIONS

# --- Structured-output schemas -----------------------------------------------
class ExtractedClaim(BaseModel):
    text: str             # verbatim substring of the ad
    context_section: str  # one of ALL_SECTIONS

class Extraction(BaseModel):
    claims: list[ExtractedClaim]

class ClassifiedClaim(BaseModel):
    claim_id: int              # the number given in the input list
    predicted_tier: int        # 1, 2 or 3
    particular: str = ""       # Tier 1: exact substring of the claim; otherwise ""
    placeholder: bool = False  # claim contains a template blank
    reasoning: str = ""

class Classification(BaseModel):
    claims: list[ClassifiedClaim]

# --- Stage 1 prompt -----------------------------------------------------------
STAGE1_PROMPT = """You are Stage 1 of a job-posting specificity pipeline: CLAIM EXTRACTION.

Task: split the job ad you are given into discrete claims. A claim is one assertion
about the job, team, company, or candidate.

RULES
1. Read the ad end to end and identify every claim.
2. EXTRACT mission, culture and values statements as claims ("we're on a mission to
   ...", "we move fast", "we're like a family", "passion for excellence"). They are not
   boilerplate. They are the empty-slogan class, and dropping them corrupts the score.
3. DROP boilerplate only: equal-opportunity statements, application instructions
   ("apply via...", "send your CV"), legal disclaimers, contact information, and bare
   section headings ("About the role", "What you'll do").
   KEEP claims about what the hiring process is: named stages, number of rounds,
   a stated timeline. "Our process takes around 4 weeks" is a claim; "apply now" is not.
4. ONE CLAIM PER ASSERTION. Split compound sentences into atomic claims:
   "€60k, Go, remote" is three claims: "€60k", "Go", "remote".
   Each claim must still be a contiguous substring of the ad.
5. COPY WORD FOR WORD. Every `text` must be an exact contiguous substring of the ad,
   including typos, punctuation, brackets and placeholders. Do not tidy, paraphrase,
   join non-adjacent words, or drop bullets' inner words. Omit leading bullet symbols.
6. PLACEHOLDERS. If the ad contains template blanks such as "[salary range]",
   "€XX,XXX", "{city}" or "TBD", extract the claim containing them verbatim like any
   other claim.
7. Tag every claim with exactly one context_section from this CLOSED list. Never
   invent a name. If nothing fits, pick the closest ROLE-context value.

   Employer context (about the company, not the job):
   - Company: what the company is, does, sells, how big or old it is
   - Company programs: philanthropy, public products, press and awards
   - Culture/values: how the company says it works and what it says it values

   Role context (about the job being advertised):
   - Role: what the role is, its purpose and scope
   - Team: the team joined, its size, mission, who is on it
   - Responsibilities: what the person will do
   - Requirements: stated musts: experience, skills, credentials
   - Preferred qualifications: nice-to-haves, explicitly optional
   - Tech stack: named languages, tools, infrastructure
   - Product scope: the products or surfaces the role works on
   - Compensation: salary, equity, bonus, incentives
   - Benefits: leave, budgets, perks, relocation, visas
   - Location/schedule: place, remote/hybrid rules, hours, flexibility, on-call schedule
   - Level: seniority, ladder level, band
   - Reporting line: who the role reports to
   - Hiring process: interview stages, timeline, what the process involves

EXAMPLE
Ad:
  We're a 30-person startup building API infrastructure. Based in Tallinn, with offices
  in London and remote roles. Founded 2019. We're a fast-paced team.
  We're looking for a Backend Engineer with 5+ years of experience. The role involves
  building microservices in Go and Rust.
  Compensation: €65,000–85,000 gross, annual bonus 10–20%.
  Flexible working: four-day week, or five days remote.
  You'll have ownership over your services' roadmap.
  We are an equal-opportunity employer. To apply, visit our careers page.
Claims:
  "30-person startup" (Company); "API infrastructure" (Company); "Founded 2019" (Company);
  "We're a fast-paced team" (Culture/values); "Based in Tallinn" (Location/schedule);
  "offices in London" (Location/schedule); "remote roles" (Location/schedule);
  "5+ years of experience" (Requirements); "microservices in Go and Rust" (Tech stack);
  "€65,000–85,000 gross" (Compensation); "annual bonus 10–20%" (Compensation);
  "four-day week" (Location/schedule); "ownership over your services' roadmap" (Responsibilities)
Dropped: "We are an equal-opportunity employer" (legal), "To apply, visit our careers page"
(application instruction).

Return every claim in order of appearance."""

# --- Stage 2 prompt -----------------------------------------------------------
STAGE2_PROMPT = """You are Stage 2 of a job-posting specificity pipeline: CLAIM CLASSIFICATION.

Classify each numbered claim into exactly one tier. Pick one; never hedge.

TIER 1 - CONCRETE
Contains a number, a named technology, a timeframe, a verifiable fact, or a falsifiable
commitment. Someone could later say "you said this and it isn't true."
Examples: "€60,000–75,000 gross", "Go and PostgreSQL", "two days a week in the Rīga office",
"on-call one week in six", "four-day week", "team of nine", "5+ years experience", "Founded 2019".

TIER 2 - GENERAL DIRECTION
States a real intent or attribute specific to this job, but without detail that could be checked.
Examples: "We invest in developer growth", "modern stack", "flexible working hours",
"you'll have ownership of your work", "collaborative environment", "strong team culture".

TIER 3 - EMPTY SLOGAN
Could appear verbatim in an ad for a completely different job at a completely different
company without changing meaning. Test: delete it; if nothing is lost, it is a slogan.
Examples: "fast-paced environment", "we're like a family", "rockstar developer",
"passion for excellence", "wear many hats", "solving hard problems", "impactful work".

TIER 1 vs TIER 2 - NAME THE PARTICULAR
Tier 1 is not "does this describe real work?". It is "can I quote a specific token in the
claim and say what kind of particular it is?". One of:
- a number or range: "€65,000–85,000", "3+ years", "team of nine", "10–20%"
- a named technology, tool, framework or taxonomy: "Go", "Kubernetes", "MITRE ATT&CK"
- a named place, office or entity: "Tallinn", "the Rīga office"
- an explicit timeframe or cadence: "four-day week", "one week in six", "by end of year"
- a named credential with no escape hatch
- a quantified policy: "two days a week in office", "25 days leave"
If you cannot quote the token, it is Tier 2, however senior, technical or demanding the
work sounds. Seriousness is not a Tier 1 criterion.

NOT Tier 1 reasons (each is Tier 2):
- "expert work", "deep technical work": describes difficulty, commits to nothing
- "works with named teams", "cross-functional": same call as "collaborative environment"
- a clear work assignment with no number, tech or timeframe ("resolve incidents rapidly")
- a product or market category ("data infrastructure platform for enterprises")
- domain jargon alone ("understanding the TTPs of threat actors")

NON-PARTICULARS (never lift a claim to Tier 1; they do not stop it being Tier 3):
- English or another language nearly every posting requires
- bare skill nouns: "communication skills", "problem-solving"
- the employer's own name
A quotable token counts only when it is specific to this job.

PLACEHOLDERS (generated ads may contain template blanks):
- "[salary range]", "€XX,XXX", "{city}", "TBD", "[X] days" and the like are NOT particulars.
- A claim whose only would-be particular is a placeholder is Tier 2 (it shows intent to
  state a fact but states none). Set placeholder = true on any claim containing one.

ESCAPE HATCHES
- "B.S. or M.S. Computer Science or related field, or equivalent experience" -> Tier 2:
  the hedge removes the requirement, nothing is provable.
- "data tools (e.g. Spark, Trino)" -> Tier 1: named tools stay checkable; "e.g." widens the
  list without cancelling the names.
A hedge on a REQUIREMENT can dissolve it. A hedge on a LIST OF NAMED THINGS usually does not.
"primarily", "typically", "around" with no number cancel what follows.

TIER 2 vs TIER 3
States a real intent specific to this job or company -> Tier 2. Could fit any job ad -> Tier 3.

BOUNDARY CASES
"Competitive salary" -> 3 | "Competitive salary: €60–80k" -> 1 | "Proven track record" -> 3
"3+ years as a backend engineer" -> 1 | "Join a growing team" -> 3
"Team of 5, growing to 8 by end of year" -> 1 | "We value work-life balance" -> 2
"We love innovation" -> 3 | "AWS, Kubernetes, Postgres" -> 1 | "modern tech stack" -> 2
"a cross-disciplinary group of incident managers, investigators, security engineers and data
 scientists" -> 1 (enumerated roles) | "operating primarily across three European time zones"
 -> 2 ("primarily" cancels) | "classifying findings using MITRE ATT&CK" -> 1
"work cross-functionally with the security, risk and data science teams" -> 2
"Excellent written and verbal communication skills in English" -> 3 (English is a non-particular)
"ability to communicate results clearly and focus on impact" -> 3

OUTPUT, one entry per input claim, using the claim's number as claim_id:
- predicted_tier: 1, 2 or 3
- particular: for Tier 1, the exact token copied character for character from the claim
  (must be a substring of that claim); for Tier 2 and 3, ""
- placeholder: true if the claim contains a template blank, else false
- reasoning: Tier 1 quotes the particular and names its type; Tier 2 names what is missing
  ("no number, named tech or timeframe"); Tier 3 applies the deletion test. Write it for this
  claim; never reuse one reasoning string across claims of different shape."""

# --- Code-level enforcement ----------------------------------------------------
_FOLD = str.maketrans({
    "–": "-", "—": "-", "−": "-",      # en/em dash, minus
    "‘": "'", "’": "'", "“": '"', "”": '"',
    " ": " ",
})
PLACEHOLDER_RE = re.compile(
    r"\[[^\]]*\]|\{[^}]*\}|<[a-z _-]+>|\bX{2,}\b|\bTBD\b|\bTBC\b|\$X|€X|£X",
    re.IGNORECASE,
)
NON_PARTICULARS = {"english", "communication skills", "problem-solving", "problem solving"}

def norm(s: str) -> str:
    """Same idea as the repo's normaliser: case, whitespace, dashes, curly quotes."""
    s = unicodedata.normalize("NFKC", s).translate(_FOLD).casefold()
    return re.sub(r"\s+", " ", s).strip()

def has_placeholder(s: str) -> bool:
    return bool(PLACEHOLDER_RE.search(s))

def _check_extraction(ad: str, extraction: Extraction):
    """Keep verbatim, de-duplicated claims; force the closed section list."""
    ad_n = norm(ad)
    kept, seen = [], set()
    rejected_nonverbatim = duplicates = section_fixed = 0
    for c in extraction.claims:
        t = c.text.strip().lstrip("-•*· ").strip()
        tn = norm(t)
        if not tn or tn not in ad_n:
            rejected_nonverbatim += 1
            continue
        if tn in seen:
            duplicates += 1
            continue
        seen.add(tn)
        section = c.context_section.strip()
        if section not in ALL_SECTIONS:
            section, section_fixed = "Role", section_fixed + 1   # closest role-context default
        kept.append({"text": t, "context_section": section})
    return kept, {"rejected_nonverbatim": rejected_nonverbatim,
                  "duplicates": duplicates, "section_fixed": section_fixed}

def _apply_classification(claims: list[dict], classification: Classification):
    """Attach tiers; enforce one tier per claim and the quote-the-particular rule."""
    by_id = {}
    for c in classification.claims:
        if c.claim_id not in by_id:          # first answer wins on a repeated id
            by_id[c.claim_id] = c
    unclassified = tier1_demoted = 0
    out = []
    for i, claim in enumerate(claims, start=1):
        c = by_id.get(i)
        if c is None or c.predicted_tier not in (1, 2, 3):
            unclassified += 1
            continue
        tier = c.predicted_tier
        particular = c.particular.strip()
        placeholder = bool(c.placeholder) or has_placeholder(claim["text"])
        if tier == 1:
            p = norm(particular)
            if (not p or p not in norm(claim["text"]) or has_placeholder(particular)
                    or p in NON_PARTICULARS):
                tier, tier1_demoted = 2, tier1_demoted + 1   # "cannot quote it -> Tier 2"
        out.append({**claim, "tier": tier,
                    "particular": particular if tier == 1 else "",
                    "placeholder": placeholder, "reasoning": c.reasoning})
    return out, {"unclassified": unclassified, "tier1_demoted": tier1_demoted}

def _score(claims: list[dict]) -> dict:
    def tiers(cs):
        return [sum(c["tier"] == t for c in cs) for t in (1, 2, 3)]
    t1, t2, t3 = tiers(claims)
    n = t1 + t2 + t3
    role = [c for c in claims if c["context_section"] in ROLE_SECTIONS]
    r1, r2, r3 = tiers(role)
    rn = r1 + r2 + r3
    return {
        "n_claims": n, "tier1": t1, "tier2": t2, "tier3": t3,
        "specificity": t1 / n if n else 0.0,                # tier_1 / (t1 + t2 + t3)
        "n_role_claims": rn,
        "role_specificity": r1 / rn if rn else 0.0,         # Stage 3's headline split
        "employer_claims": n - rn,
        "placeholders": sum(c["placeholder"] for c in claims),
    }

# --- Robust JSON from any model (incl. reasoning models that emit <think>) -----
# kbench's built-in schema= parser takes the whole reply when it finds no
# ```json block, so a reply starting with "<think>" fails. We ask for JSON in the
# prompt, take plain text, and parse it ourselves.
def _json_instruction(model) -> str:
    return ("\n\nReturn ONLY one JSON object matching this JSON schema, inside a "
            "```json code block, with no text after it:\n"
            + json.dumps(model.model_json_schema()))

def _parse_json(text: str, model):
    t = text.split("</think>")[-1]                  # drop visible reasoning
    blocks = re.findall(r"```(?:json|JSON)?\s*(.*?)```", t, re.S)
    for cand in blocks[::-1] + [t]:                 # last code block first
        for open_, close in (("{", "}"), ("[", "]")):
            s, e = cand.find(open_), cand.rfind(close)
            if s == -1 or e <= s:
                continue
            raw = cand[s:e + 1]
            if open_ == "[":                        # bare list -> {"claims": [...]}
                raw = '{"claims": ' + raw + "}"
            try:
                return model.model_validate_json(raw)
            except ValidationError:
                continue
    return None

def _ask(judge_llm, chat_name: str, system: str, user: str, model):
    """One fresh chat; one retry asking for JSON only if the first reply won't parse."""
    with kbench.chats.new(chat_name, system_instructions=system):
        reply = judge_llm.prompt(user + _json_instruction(model))
        parsed = _parse_json(str(reply), model)
        if parsed is None:
            reply = judge_llm.prompt("Your reply could not be parsed. Return ONLY the "
                                     "JSON object in a ```json code block.")
            parsed = _parse_json(str(reply), model)
    if parsed is None:
        raise ValueError(f"{chat_name}: judge returned no parsable JSON. "
                         f"Reply starts: {str(reply)[:300]!r}")
    return parsed

# --- The judge -----------------------------------------------------------------
def judge(ad: str, judge_llm) -> dict:
    """Stage 1 then Stage 2, each in a fresh chat so the judge never sees the
    conversation that wrote the ad. Call it from inside a kbench task."""
    extraction = _ask(judge_llm, "judge_stage1", STAGE1_PROMPT, f"JOB AD:\n\n{ad}", Extraction)
    claims, s1_checks = _check_extraction(ad, extraction)

    if not claims:
        return {**_score([]), **s1_checks, "unclassified": 0, "tier1_demoted": 0, "claims": []}

    numbered = "\n".join(f'{i}. [{c["context_section"]}] {c["text"]}'
                         for i, c in enumerate(claims, start=1))
    classification = _ask(judge_llm, "judge_stage2", STAGE2_PROMPT,
                          f"CLAIMS:\n\n{numbered}", Classification)
    classified, s2_checks = _apply_classification(claims, classification)

    return {**_score(classified), **s1_checks, **s2_checks, "claims": classified}


# =============================================================================
# Try it on the two ads from step 3 (the `ads` dict). Second notebook cell.
# =============================================================================
@kbench.task(store_task=False)
def judge_one(llm, ad) -> dict:
    return judge(ad, llm)

import pandas as pd

judged = {}
for m, ad in ads.items():
    judged[m] = judge_one.run(llm=kbench.llms[JUDGE], ad=ad).result
    j = judged[m]
    print(f"\n===== {m}")
    print({k: v for k, v in j.items() if k != "claims"})
    display(pd.DataFrame(j["claims"])[["tier", "context_section", "placeholder", "particular", "text"]])
