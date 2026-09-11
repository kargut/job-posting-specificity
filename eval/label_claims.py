#!/usr/bin/env python3
"""
Blind tier labeler for job-posting claims.

Shows one extracted claim at a time and records Tier 1 / 2 / 3. Never displays a
model's predicted tier, and refuses a Tier 1 whose reasoning does not quote a
substring of the claim itself.

Why those two rules: see prompts/shared_context.md ("The Tier 1 Test: Name the
Particular") and eval/annotator_passes.md. Labeling with model output visible
inflates agreement in a way that cannot be undone afterwards; a Tier 1 whose
reasoning quotes nothing is a tier assigned on a non-criterion.

Label:
  python eval/label_claims.py --extracted data/extracted/claims.jsonl \
      --raw data/raw/raw_postings.jsonl --out eval/labeled.jsonl

  --postings N      postings to sample (default 15)
  --per-posting N   claim cap per posting, sampled if more (default 10)
  --seed N          sampling seed (default 7)
  --pass N          label_pass to record (default: next unused for the posting)
  --shuffle         shuffle claim order (default on when --pass > 1)
  --relabel         re-label claims already present for this pass
  --limit N         stop after N claims this session

Verify:
  python eval/label_claims.py --verify eval/labeled.jsonl

Pass-to-pass agreement needs no extra tool — compare_labels.py reads `tier` as
well as `predicted_tier`, so treat pass 1 as gold and pass 2 as predictions:
  python eval/compare_labels.py pass1.jsonl pass2.jsonl

Keys while labeling: 1 2 3 = tier, s = skip, b = back, ? = rule, q = save & quit.

Test cases below are paraphrased from real postings: this repo commits code and
aggregates only, and never names an individual company.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Reasons that are never sufficient for Tier 1. Each one caused a real
# mislabel; see eval/annotator_passes.md.
BANNED_TIER1_REASONS = [
    "expert work",
    "real work",
    "work in teams",
    "works in teams",
    "work with teams",
    "clear work assignment",
    "serious work",
    "deep work",
    "technical work",
]

RULE_TEXT = """\
TIER 1 — quote the particular. One of:
    number or range            €65,000–85,000 · 3+ years · team of nine · 10–20%
    named tech / framework     Go · Kubernetes · MITRE ATT&CK · Postgres
    named place or entity      Tallinn · the Rīga office
    explicit timeframe         four-day week · one week in six · by end of year
    unhedged credential        B.Sc. Computer Science
    quantified policy          two days a week in office · 25 days leave
  If you cannot quote the token, it is NOT Tier 1 — however expert, technical
  or genuinely demanding the work sounds. Seriousness is not a criterion.
  A hedge on a requirement dissolves it ("or equivalent experience" → Tier 2).
  A hedge on a list of named things does not ("e.g. Spark, Trino" → Tier 1).

TIER 2 — real intent, nothing checkable. Name what is missing.
  Includes: product category, "works with the X and Y teams", domain jargon.

TIER 3 — empty slogan. Delete the sentence; if nothing is lost, it is Tier 3."""


# ---------------------------------------------------------------- utilities


def norm(s: str) -> str:
    """Lowercase, collapse whitespace, and fold the punctuation variants that
    differ between a posting and what a human retypes."""
    s = (s or "").lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-"),
                 ("−", "-"), (" ", " ")):
        s = s.replace(a, b)
    return " ".join(s.split())


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "you", "our",
    "are", "has", "have", "will", "can", "any", "all", "other", "others",
    "work", "works", "working", "team", "teams", "role", "roles", "about",
    "into", "across", "within", "their", "them", "they", "its", "also",
    "more", "most", "such", "than", "then", "when", "while", "where", "which",
    "who", "what", "how", "not", "but", "out", "own", "use", "using", "used",
    "help", "helps", "make", "makes", "new", "good", "great", "well", "very",
}

CURRENCY = "€$£%+"


def _informative_tokens(claim_text: str) -> set[str]:
    """Tokens from the claim that could be 'the particular' — numbers, named
    things, domain terms. Deliberately excludes common words so that a
    reasoning like "work in teams" cannot pass by accident."""
    raw = (claim_text or "").split()
    out: set[str] = set()
    for raw_tok in raw:
        tok = norm(raw_tok).strip(".,;:()[]\"'")
        if not tok:
            continue
        has_digit = any(ch.isdigit() for ch in raw_tok)
        has_cur = any(ch in CURRENCY for ch in raw_tok)
        # capitalized mid-claim suggests a proper noun / named technology
        is_proper = raw_tok[:1].isupper() and raw_tok.lower() != raw_tok
        if has_digit or has_cur:
            out.add(tok)
        elif tok in STOPWORDS:
            # a capitalized stopword is almost always sentence-initial, not a
            # proper noun: "Work cross-functionally ..." must not make "work"
            # count as a particular.
            continue
        elif is_proper or len(tok) >= 6:
            out.add(tok)
    return out


def is_quote_of(claim_text: str, quote: str) -> tuple[bool, str]:
    """Is `quote` literally lifted from the claim? Used for the quote typed at
    the prompt, where the intent is unambiguous — unlike quotes_particular,
    which has to find the quote inside free-form reasoning."""
    q, c = norm(quote), norm(claim_text)
    if len(q) < 2:
        return False, "too short to be a particular"
    if q in STOPWORDS:
        return False, f'"{quote}" is a common word, not a particular'
    if q not in c:
        return False, f'"{quote}" is not in the claim'
    return True, ""


def quotes_particular(claim_text: str, reasoning: str) -> bool:
    """True if `reasoning` points at the claim's own words.

    Two ways to satisfy it:
      1. an explicitly quoted span in the reasoning that is a substring of the
         claim (the normal case — the CLI writes reasonings this way);
      2. an informative token from the claim appearing verbatim in the
         reasoning (numbers, currency, proper nouns, or words >= 6 chars that
         are not stopwords).

    LIMITATION, stated honestly: this proves the reasoning quotes the posting,
    not that the quoted words are a genuine particular. "teams" or "security"
    can be quoted for a claim that commits to nothing. That is what
    BANNED_TIER1_REASONS and human review are for. The check exists to catch
    the documented failure mode — a Tier 1 whose reasoning quotes nothing at
    all, e.g. "checkable tooling" on a claim naming no tooling.
    """
    c, r = norm(claim_text), norm(reasoning)
    if not c or not r:
        return False
    for quoted in re.findall(
            r'["\u201c\u2018\']([^"\u201d\u2019\']{2,})["\u201d\u2019\']',
            reasoning):
        q = norm(quoted)
        if q and q in c:
            return True
    for tok in _informative_tokens(claim_text):
        if tok in r:
            return True
    # a run of >= 3 consecutive words lifted from the claim is not an accident,
    # even when every word in it is common ("one week in six")
    words = c.split()
    for n in range(len(words), 2, -1):
        for i in range(len(words) - n + 1):
            if " ".join(words[i:i + n]) in r:
                return True
    return False


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"warning: {path}:{i} skipped: {e}", file=sys.stderr)
    return rows


def write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def getch() -> str:
    """One keypress, no Enter. Falls back to line input where unavailable."""
    try:
        import msvcrt  # Windows
        ch = msvcrt.getwch()
        return "\r" if ch in "\r\n" else ch
    except ImportError:
        pass
    try:
        import termios
        import tty
        if not sys.stdin.isatty():
            raise OSError
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch
    except Exception:
        line = sys.stdin.readline()
        if not line:
            return "q"
        return line.strip()[:1] or "\r"


def width() -> int:
    return max(60, min(100, shutil.get_terminal_size((88, 24)).columns))


def wrap(text: str, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width(), initial_indent=indent,
                         subsequent_indent=" " * len(indent))


def rule(ch: str = "-") -> str:
    return ch * width()


# ---------------------------------------------------------------- labeling


def build_queue(extracted: list[dict], n_postings: int, per_posting: int,
                seed: int, shuffle: bool) -> tuple[list[tuple[str, dict]], dict]:
    """Sample postings and claims deterministically. Returns (queue, meta)."""
    rng = random.Random(seed)
    postings = [r for r in extracted if (r.get("claims") or r.get("classifications"))]
    postings.sort(key=lambda r: str(r.get("posting_id") or ""))
    if n_postings and len(postings) > n_postings:
        postings = rng.sample(postings, n_postings)
        postings.sort(key=lambda r: str(r.get("posting_id") or ""))

    queue: list[tuple[str, dict]] = []
    meta: dict[str, dict] = {}
    dropped_tiers = 0
    for row in postings:
        pid = str(row.get("posting_id") or row.get("id") or "")
        claims = list(row.get("claims") or row.get("classifications") or [])
        for c in claims:
            # Blind: the model's tier must never reach the screen.
            if c.pop("predicted_tier", None) is not None:
                dropped_tiers += 1
            c.pop("confidence", None)
            c.pop("reasoning", None)
        if per_posting and len(claims) > per_posting:
            claims = rng.sample(claims, per_posting)
            claims.sort(key=lambda c: str(c.get("claim_id")))
        meta[pid] = {
            "posting_content": row.get("posting_content") or row.get("content") or "",
            "title": row.get("title") or "",
            "company": row.get("company") or "",
            "spans_from": row.get("extraction_prompt_version")
            and f"stage1@{row['extraction_prompt_version']}" or "stage1",
        }
        for c in claims:
            queue.append((pid, c))
    if shuffle:
        rng.shuffle(queue)
    meta["__dropped_model_tiers__"] = dropped_tiers
    return queue, meta


def ask_reasoning(tier: int, claim_text: str) -> str | None:
    """Collect reasoning, enforcing the quote rule for Tier 1.
    Returns None if the annotator backs out of the tier."""
    if tier == 1:
        while True:
            print(wrap("Quote the particular — the posting's own words that make "
                       "this checkable. Enter = re-pick the tier.", "  "))
            try:
                q = input("  quote > ").strip()
            except EOFError:
                return None
            if not q:
                print(wrap("Nothing quoted, so it is not Tier 1.", "  ! "))
                return None
            ok, why = is_quote_of(claim_text, q)
            if not ok:
                print(wrap(why + " — quote the claim verbatim, or press Enter "
                           "to re-pick the tier.", "  ! "))
                continue
            try:
                kind = input("  type [n]umber/[t]ech/[p]lace/[d]ate/"
                             "[c]redential/[o]ther > ").strip().lower()
            except EOFError:
                kind = ""
            kinds = {"n": "number", "t": "named tech", "p": "named place",
                     "d": "timeframe", "c": "credential", "o": "particular"}
            return f'{kinds.get(kind, "particular")}: "{q}"'
    if tier == 2:
        default = "no number, named tech or timeframe"
        try:
            r = input(f"  missing [{default}] > ").strip()
        except EOFError:
            r = ""
        return r or default
    default = "delete it and nothing is lost"
    try:
        r = input(f"  why [{default}] > ").strip()
    except EOFError:
        r = ""
    return r or default


def context_snippet(content: str, claim_text: str, chars: int = 300) -> str:
    """The sentence-ish neighbourhood of the claim inside the posting."""
    if not content:
        return ""
    hay, needle = norm(content), norm(claim_text)
    # map normalized index back approximately by searching raw text first
    idx = content.lower().find(claim_text.lower()[:40])
    if idx < 0:
        idx = hay.find(needle[:40])
        if idx < 0:
            return ""
    start = max(0, idx - chars // 3)
    end = min(len(content), idx + len(claim_text) + chars // 2)
    snip = content[start:end].strip().replace("\n", " ")
    snip = " ".join(snip.split())
    return ("..." if start > 0 else "") + snip + ("..." if end < len(content) else "")


def label_session(args: argparse.Namespace) -> int:
    extracted = load_jsonl(Path(args.extracted))
    if not extracted:
        print(f"error: no rows in {args.extracted}", file=sys.stderr)
        return 1

    raw_by_id = {}
    if args.raw:
        for r in load_jsonl(Path(args.raw)):
            raw_by_id[str(r.get("id") or r.get("posting_id") or "")] = r

    shuffle = args.shuffle or (args.label_pass or 1) > 1
    queue, meta = build_queue(extracted, args.postings, args.per_posting,
                              args.seed, shuffle)
    dropped = meta.pop("__dropped_model_tiers__", 0)

    out_path = Path(args.out)
    existing = load_jsonl(out_path)
    by_pid = {str(r.get("posting_id")): r for r in existing}

    # which (pid, claim_id) already labeled in the target pass
    target_pass = args.label_pass
    done: set[tuple[str, str]] = set()
    for r in existing:
        rp = r.get("label_pass")
        if target_pass is None or rp == target_pass:
            for c in r.get("claims") or []:
                done.add((str(r.get("posting_id")), str(c.get("claim_id"))))

    todo = [(p, c) for (p, c) in queue
            if args.relabel or (p, str(c.get("claim_id"))) not in done]
    if args.limit:
        todo = todo[:args.limit]

    print(rule("="))
    print("  BLIND TIER LABELING")
    print(rule("="))
    if dropped:
        print(wrap(f"{dropped} model tiers were present in the input and have "
                   f"been discarded — they are never shown.", "  * "))
    print(wrap(f"{len(todo)} claims to label "
               f"({len(queue)} sampled, {len(queue) - len(todo)} already done).", "  "))
    print(wrap("Keys: 1 2 3 = tier · s = skip · b = back · ? = rule · q = save & quit", "  "))
    print(rule("="))

    labels: dict[tuple[str, str], dict] = {}
    i = 0
    quit_early = False
    while i < len(todo):
        pid, claim = todo[i]
        cid = str(claim.get("claim_id"))
        m = meta.get(pid, {})
        rawrow = raw_by_id.get(pid, {})
        content = m.get("posting_content") or rawrow.get("content") or ""
        title = m.get("title") or rawrow.get("title") or ""
        company = m.get("company") or rawrow.get("company") or ""

        print()
        print(rule())
        head = f"[{i + 1}/{len(todo)}]"
        where = " · ".join(x for x in (title, company,
                                       claim.get("context_section") or "") if x)
        print(f"  {head}  {where}" if where else f"  {head}")
        snip = context_snippet(content, claim.get("text", ""))
        if snip:
            print()
            print(wrap(snip, "    "))
        print()
        print(wrap(claim.get("text", ""), "  >> "))
        print()
        sys.stdout.write("  tier (1/2/3) > ")
        sys.stdout.flush()

        key = getch()
        print(key if key in "123sbq?" else "")

        if key == "q":
            quit_early = True
            break
        if key == "s":
            i += 1
            continue
        if key == "b":
            i = max(0, i - 1)
            continue
        if key == "?":
            print()
            print(rule())
            print(RULE_TEXT)
            print(rule())
            continue
        if key not in "123":
            print("  ? unrecognised key")
            continue

        tier = int(key)
        reasoning = ask_reasoning(tier, claim.get("text", ""))
        if reasoning is None:
            continue  # re-ask this claim

        labels[(pid, cid)] = {
            "claim_id": cid,
            "text": claim.get("text", ""),
            "tier": tier,
            "reasoning": reasoning,
        }
        if claim.get("context_section"):
            labels[(pid, cid)]["context_section"] = claim["context_section"]

        # persist after every claim
        flush(labels, by_pid, meta, out_path, target_pass)
        i += 1

    flush(labels, by_pid, meta, out_path, target_pass)
    n = len(labels)
    counts = Counter(v["tier"] for v in labels.values())
    print()
    print(rule("="))
    print(f"  {n} claims labeled this session"
          + (" (quit early)" if quit_early else ""))
    if n:
        print(f"  T1={counts[1]}  T2={counts[2]}  T3={counts[3]}"
              f"   specificity={counts[1] / n:.3f}")
    print(f"  written to {out_path}")
    print(rule("="))
    return 0


def flush(labels: dict, by_pid: dict, meta: dict, out_path: Path,
          target_pass: int | None) -> None:
    """Merge this session's labels into the output file."""
    if not labels:
        return
    grouped: dict[str, list[dict]] = defaultdict(list)
    for (pid, _cid), lab in labels.items():
        grouped[pid].append(lab)

    for pid, labs in grouped.items():
        m = meta.get(pid, {})
        row = by_pid.get(pid)
        if row is None:
            row = {
                "posting_id": pid,
                "posting_content": m.get("posting_content", ""),
                "spans_from": m.get("spans_from", "stage1"),
                "label_pass": target_pass or 1,
                "blind": True,
                "claims": [],
            }
            by_pid[pid] = row
        row["labeled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row.setdefault("blind", True)
        row.setdefault("label_pass", target_pass or 1)
        existing = {str(c.get("claim_id")): c for c in row.get("claims") or []}
        for lab in labs:
            existing[lab["claim_id"]] = lab
        row["claims"] = sorted(
            existing.values(),
            key=lambda c: (len(str(c.get("claim_id"))), str(c.get("claim_id"))),
        )
    write_jsonl_atomic(out_path, list(by_pid.values()))


# ---------------------------------------------------------------- verify


def verify(path: Path) -> int:
    rows = load_jsonl(path)
    if not rows:
        print(f"error: no rows in {path}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    reason_uses: Counter[str] = Counter()
    reason_shapes: dict[str, set[int]] = defaultdict(set)
    total = 0

    for row in rows:
        pid = str(row.get("posting_id"))
        synthetic = bool(row.get("synthetic")) or row.get("spans_from") == "synthetic"
        if not synthetic:
            if row.get("blind") is False:
                warnings.append(
                    f"{pid}: blind=false — labeled with model output visible, "
                    f"not usable for headline numbers")
            elif "blind" not in row:
                warnings.append(f"{pid}: no `blind` field — provenance unknown")
            if "label_pass" not in row:
                warnings.append(f"{pid}: no `label_pass` field")

        for c in row.get("claims") or []:
            total += 1
            cid = c.get("claim_id")
            tier = c.get("tier")
            text = c.get("text") or ""
            reasoning = c.get("reasoning") or ""
            loc = f"{pid}#{cid}"

            if tier not in (1, 2, 3):
                errors.append(f"{loc}: tier {tier!r} not in 1/2/3")
                continue
            if not text.strip():
                errors.append(f"{loc}: empty claim text")
            if not reasoning.strip():
                errors.append(f"{loc}: empty reasoning")
                continue

            reason_shapes[norm(reasoning)].add(tier)
            if tier == 1:
                reason_uses[norm(reasoning)] += 1

            if tier == 1:
                if not quotes_particular(text, reasoning):
                    errors.append(
                        f"{loc}: TIER 1 quotes nothing from the claim — "
                        f'reasoning "{reasoning[:60]}" for "{text[:60]}"')
                low = norm(reasoning)
                for banned in BANNED_TIER1_REASONS:
                    if banned in low:
                        errors.append(
                            f'{loc}: TIER 1 on a non-criterion ("{banned}")')

    # A repeated Tier 2 reason is fine — "what is missing" is often the same
    # thing. A repeated Tier 1 reason means the particular was not named.
    for reason, n in reason_uses.items():
        if n >= 4:
            warnings.append(
                f'Tier 1 reasoning reused {n}x: "{reason[:60]}" — a particular '
                f"is specific to its claim, so this is a template smell")
    for reason, tiers in reason_shapes.items():
        if len(tiers) > 1:
            warnings.append(
                f'reasoning "{reason[:50]}" used for tiers {sorted(tiers)} — '
                f"same words, different tier")

    print(rule("="))
    print(f"  VERIFY {path}")
    print(rule("="))
    print(f"  {len(rows)} postings, {total} claims")
    print()
    if errors:
        print(f"  {len(errors)} ERROR(S)")
        for e in errors:
            print(wrap(e, "    - "))
        print()
    if warnings:
        print(f"  {len(warnings)} warning(s)")
        for w in warnings:
            print(wrap(w, "    - "))
        print()
    if not errors and not warnings:
        print("  clean")
    elif not errors:
        print("  no errors")
    print(rule("="))
    return 1 if errors else 0


# ---------------------------------------------------------------- selftest


SELFTEST_CASES = [
    # (claim, reasoning, expected quotes_particular)
    ("3+ years of experience conducting incident response",
     'number: "3+ years"', True),
    ("using ATT&CK-mapped detection and signal enrichment",
     'named tech: "ATT&CK"', True),
    ("Expert knowledge of Python and SQL",
     'named tech: "Python and SQL"', True),
    ("€65,000–85,000 gross", 'number: "€65,000–85,000"', True),
    ("Experience with data processing and analysis tools (e.g. Spark, Trino)",
     'named tech: "Spark, Trino"', True),
    # the documented failure: reasoning quotes nothing
    ("using ATT&CK-mapped detection and signal enrichment",
     "checkable tooling", False),
    ("data infrastructure platform for enterprises",
     "checkable tooling", False),
    ("investigating high-risk accounts and identifying complex abuse patterns",
     "expert work", False),
    # must not pass on common words alone
    ("Work cross-functionally with security, fraud and data science teams",
     "work in teams", False),
    ("works directly with affected customers to resolve technical incidents",
     "clear work assignment", False),
    ("Lead incident root cause analyses to identify gaps in current systems",
     "not mentioned how to do it", False),
    # unquoted but genuinely pointing at the claim
    ("Team of 5, growing to 8 by end of year", "growing to 8 by end of year", True),
    ("On-call one week in six", "one week in six", True),
]


def selftest() -> int:
    failures = 0
    for claim, reasoning, expected in SELFTEST_CASES:
        got = quotes_particular(claim, reasoning)
        if got != expected:
            failures += 1
            print(f"  FAIL expected={expected} got={got}")
            print(f"       claim:     {claim[:70]}")
            print(f"       reasoning: {reasoning}")
    banned_hit = quotes_particular("Work with the security team", "work in teams")
    print(f"  {len(SELFTEST_CASES) - failures}/{len(SELFTEST_CASES)} quote-rule cases pass")
    print(f"  banned-phrase backstop covers: {sorted(BANNED_TIER1_REASONS)[:3]} ...")
    return 1 if failures else 0


# ---------------------------------------------------------------- cli


def main() -> None:
    p = argparse.ArgumentParser(
        description="Blind tier labeler with Tier 1 quote enforcement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--verify", metavar="LABELED",
                   help="lint a labeled file instead of labeling")
    p.add_argument("--extracted", default="data/extracted/claims.jsonl")
    p.add_argument("--raw", default="data/raw/raw_postings.jsonl")
    p.add_argument("--out", default="eval/labeled.jsonl")
    p.add_argument("--postings", type=int, default=15)
    p.add_argument("--per-posting", type=int, default=10)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--pass", dest="label_pass", type=int, default=1)
    p.add_argument("--shuffle", action="store_true")
    p.add_argument("--relabel", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--rule", action="store_true", help="print the tier rule and exit")
    p.add_argument("--selftest", action="store_true",
                   help="run the quote-rule test cases and exit")
    args = p.parse_args()

    if args.rule:
        print(RULE_TEXT)
        sys.exit(0)
    if args.selftest:
        sys.exit(selftest())
    if args.verify:
        sys.exit(verify(Path(args.verify)))
    try:
        sys.exit(label_session(args))
    except KeyboardInterrupt:
        print("\ninterrupted — labels up to the last claim were saved")
        sys.exit(130)


if __name__ == "__main__":
    main()
