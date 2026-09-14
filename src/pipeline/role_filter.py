#!/usr/bin/env python3
"""
Corpus scope filter: English-language, software-and-adjacent roles.

Why this exists: the Greenhouse fetcher pulls whole boards, and these employers
hire mostly salespeople. Unfiltered, 79% of the corpus was sales, marketing and
finance (94 distinct departments, `Commercial Sales` 17 vs `Engineering` 8),
against a stated scope of "software and adjacent roles, English only". Sampling or
aggregating over that measures a classifier on finance postings while the write-up
claims software.

"Adjacent" is defined to INCLUDE pre-sales technical roles — sales engineering,
solutions engineering, customer engineering — because they are written for a
technical reader and make technical claims. It EXCLUDES quota-carrying sales
(account executives, BDRs), marketing, finance, legal, recruiting and support.

One definition, used by both the eval sampler and the aggregator, so the corpus
the numbers describe is the corpus the write-up claims.
"""

from __future__ import annotations

import ast
import re

# Technical role in the title. Pre-sales engineering variants are deliberate.
TECH_TITLE = re.compile(
    r"\b("
    r"software|backend|back-end|frontend|front-end|full-?stack|"
    r"engineer|engineering|developer|programmer|architect|"
    r"sre|site reliability|devops|platform|infrastructure|"
    r"security|cryptograph|"
    r"data scientist|data engineer|data science|analytics engineer|"
    r"machine learning|deep learning|\bml\b|\bai\b|research scientist|"
    r"\bqa\b|test automation|quality engineer|"
    r"mobile|android|ios|embedded|firmware|"
    r"database|dba\b|cloud|kubernetes|"
    r"technical program|technical product|technical writer|"
    r"solutions? engineer|sales engineer|customer engineer|"
    r"support engineer|forward deployed"
    r")\b",
    re.I,
)

# Non-technical function, even when a technical word appears in the title.
#
# The operations group is here because TECH_TITLE matches bare `platform`, and
# "Ad Platform Operations" is the advertising product, not a platform team. That
# posting is ad ops -- ad-server hygiene, yield groups, line items, programmatic
# deals, "accelerate premium programmatic revenue" -- and reads at the 2nd
# percentile of technical-token density across the in-scope corpus. Matching a
# word is not matching a function, so the fix belongs in the rule rather than in
# a hand-kept list of titles: the sampler and the aggregator share this module
# precisely so scope cannot drift between them.
NON_TECH_TITLE = re.compile(
    r"\b("
    r"ad (?:platform )?operations|adops|ad ops|"
    r"revenue operations|sales operations|business operations|"
    r"account executive|account manager|"
    r"\bsales\b(?!\s*engineer)|\bbdr\b|business development|"
    r"sales development|quota|"
    r"marketing|brand|content strategist|communications|social media|"
    r"events?|community manager|"
    r"recruit|talent acquisition|people partner|hr business|"
    r"finance|fp&a|investor|accounting|controller|treasury|payroll|tax\b|"
    r"legal|counsel|compliance officer|"
    r"customer success|customer support specialist|"
    r"procacciatore|agente di commercio"
    r")\b",
    re.I,
)

# Department fallback, for technical roles with an opaque title.
TECH_DEPT = re.compile(
    r"\b("
    r"engineering|software|infrastructure|platform|security|"
    r"data|analytics|research|r&d|product development|"
    r"solution engineering|sales engineering|customer engineering|"
    r"technology|devops|sre|machine learning"
    r")\b",
    re.I,
)

# Crude but effective: a non-English posting has few English function words.
_EN = re.compile(r"\b(the|and|you|with|for|our|are|will|that|this)\b", re.I)
MIN_EN_HITS = 10


def departments_text(row: dict) -> str:
    deps = row.get("departments")
    if isinstance(deps, str):
        try:
            deps = ast.literal_eval(deps)
        except Exception:
            deps = []
    out = []
    for d in deps or []:
        out.append(d.get("name", "") if isinstance(d, dict) else str(d))
    return " ".join(out)


def is_english(row: dict) -> bool:
    return len(_EN.findall(row.get("content") or "")) >= MIN_EN_HITS


def is_software_role(row: dict) -> bool:
    title = row.get("title") or ""
    if NON_TECH_TITLE.search(title):
        return False
    if TECH_TITLE.search(title):
        return True
    return bool(TECH_DEPT.search(departments_text(row)))


def in_scope(row: dict) -> bool:
    """English-language software-or-adjacent posting."""
    return is_english(row) and is_software_role(row)


def explain(row: dict) -> str:
    """Why a posting was kept or dropped — for auditing the filter."""
    if not is_english(row):
        return "dropped: not English"
    title = row.get("title") or ""
    m = NON_TECH_TITLE.search(title)
    if m:
        return f"dropped: non-technical function ({m.group(0)!r} in title)"
    m = TECH_TITLE.search(title)
    if m:
        return f"kept: technical title ({m.group(0)!r})"
    m = TECH_DEPT.search(departments_text(row))
    if m:
        return f"kept: technical department ({m.group(0)!r})"
    return "dropped: no technical signal in title or department"
