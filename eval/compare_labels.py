#!/usr/bin/env python3
"""
Compare hand labels to model classifications.

Metrics focus on the Tier 1 / Other boundary (what the specificity score depends on),
plus overall accuracy and a confusion matrix.

Usage:
  python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl
  python eval/compare_labels.py eval/labeled.jsonl data/classified/claims.jsonl \\
      --report eval/RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: skip {path}:{i}: {e}", file=sys.stderr)
    return rows


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def extract_labeled_claims(row: dict) -> list[tuple[str, int]]:
    """Return [(normalized_text, tier), ...] from a hand-labeled posting."""
    out: list[tuple[str, int]] = []
    for claim in row.get("claims") or []:
        text = normalize_text(claim.get("text", ""))
        tier = claim.get("tier")
        if text and tier in (1, 2, 3):
            out.append((text, int(tier)))
    return out


def extract_predicted_claims(row: dict) -> list[tuple[str, int]]:
    """Accept schema.md `claims` or stage2 prompt `classifications` shape."""
    items = row.get("claims") or row.get("classifications") or []
    out: list[tuple[str, int]] = []
    for claim in items:
        text = normalize_text(claim.get("text", ""))
        tier = claim.get("predicted_tier", claim.get("tier"))
        if text and tier in (1, 2, 3):
            out.append((text, int(tier)))
    return out


def looks_like_hand_labels(rows: list[dict]) -> bool:
    """True if a 'predictions' file is really another set of hand labels.

    Model output carries `predicted_tier` and usually a `model` field; hand
    labels carry a bare `tier`. Comparing labels to a copy of themselves gives a
    flattering, meaningless number, and the mistake is silent — this is the
    guard for it. See data/classified/_not_predictions/README.md.
    """
    saw_claim = False
    for row in rows:
        if row.get("model") or row.get("model_version") or row.get(
                "classification_prompt_version"):
            return False
        for claim in row.get("claims") or row.get("classifications") or []:
            saw_claim = True
            if "predicted_tier" in claim:
                return False
    return saw_claim


def index_by_posting(rows: list[dict], extractor) -> dict[str, list[tuple[str, int]]]:
    indexed: dict[str, list[tuple[str, int]]] = {}
    for row in rows:
        pid = str(row.get("posting_id") or row.get("id") or "")
        if not pid:
            continue
        indexed[pid] = extractor(row)
    return indexed


def pair_claims(
    gold: list[tuple[str, int]], pred: list[tuple[str, int]]
) -> list[tuple[int, int]]:
    """Greedy match by exact normalized text; leftovers are unmatched."""
    pred_by_text: dict[str, list[int]] = defaultdict(list)
    for text, tier in pred:
        pred_by_text[text].append(tier)

    pairs: list[tuple[int, int]] = []
    matched_pred: set[tuple[str, int]] = set()

    for text, g_tier in gold:
        bucket = pred_by_text.get(text) or []
        if not bucket:
            continue
        p_tier = bucket.pop(0)
        pairs.append((g_tier, p_tier))
        matched_pred.add((text, p_tier))

    return pairs


def boundary_label(tier: int) -> str:
    return "tier1" if tier == 1 else "other"


def compute_metrics(pairs: list[tuple[int, int]]) -> dict:
    if not pairs:
        return {
            "n": 0,
            "overall_accuracy": None,
            "confusion": {},
            "per_tier": {},
            "tier1_boundary": {},
        }

    n = len(pairs)
    correct = sum(1 for g, p in pairs if g == p)
    confusion: Counter[tuple[int, int]] = Counter(pairs)

    per_tier = {}
    for tier in (1, 2, 3):
        tp = sum(1 for g, p in pairs if g == tier and p == tier)
        fp = sum(1 for g, p in pairs if g != tier and p == tier)
        fn = sum(1 for g, p in pairs if g == tier and p != tier)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall)
            else None
        )
        per_tier[tier] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for g, _ in pairs if g == tier),
        }

    # Tier 1 / Other boundary
    b_correct = sum(
        1 for g, p in pairs if boundary_label(g) == boundary_label(p)
    )
    tp = sum(1 for g, p in pairs if g == 1 and p == 1)
    fp = sum(1 for g, p in pairs if g != 1 and p == 1)
    fn = sum(1 for g, p in pairs if g == 1 and p != 1)
    b_prec = tp / (tp + fp) if (tp + fp) else None
    b_rec = tp / (tp + fn) if (tp + fn) else None
    b_f1 = (
        2 * b_prec * b_rec / (b_prec + b_rec)
        if b_prec is not None and b_rec is not None and (b_prec + b_rec)
        else None
    )

    return {
        "n": n,
        "overall_accuracy": correct / n,
        "confusion": {f"{g}->{p}": c for (g, p), c in sorted(confusion.items())},
        "per_tier": per_tier,
        "tier1_boundary": {
            "accuracy": b_correct / n,
            "precision": b_prec,
            "recall": b_rec,
            "f1": b_f1,
        },
    }


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def fmt_f(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.3f}"


def render_report(
    metrics: dict,
    gold_path: Path,
    pred_path: Path,
    n_gold_postings: int,
    n_pred_postings: int,
    n_matched_postings: int,
    self_agreement: bool = False,
) -> str:
    lines = [
        "# Annotator Pass-to-Pass Agreement" if self_agreement
        else "# Evaluation Results",
        "",
        ("_Two hand-labeling passes compared. This is the annotator noise "
         "floor, not a model result._" if self_agreement else
         "_Human gold labels vs model predictions._"),
        "",
        "## Test Set",
        f"- Gold file: `{gold_path.as_posix()}`",
        f"- Predictions: `{pred_path.as_posix()}`",
        f"- Postings in gold: {n_gold_postings}",
        f"- Postings in predictions: {n_pred_postings}",
        f"- Postings with matched claims: {n_matched_postings}",
        f"- Matched claim pairs: {metrics['n']}",
        "",
        "## Per-Claim Agreement",
        f"- Overall accuracy: {fmt_pct(metrics['overall_accuracy'])}",
        "",
    ]
    for tier in (1, 2, 3):
        t = metrics["per_tier"].get(tier, {})
        lines.append(
            f"- Tier {tier}: precision {fmt_f(t.get('precision'))}, "
            f"recall {fmt_f(t.get('recall'))}, F1 {fmt_f(t.get('f1'))}, "
            f"support {t.get('support', 0)}"
        )

    b = metrics["tier1_boundary"]
    lines += [
        "",
        "## Tier 1 / Other Boundary",
        "(The distinction the specificity score depends on)",
        f"- Accuracy: {fmt_pct(b.get('accuracy'))}",
        f"- Tier 1 precision: {fmt_f(b.get('precision'))}",
        f"- Tier 1 recall: {fmt_f(b.get('recall'))}",
        f"- F1: {fmt_f(b.get('f1'))}",
        "",
        "## Confusion Matrix (gold -> predicted)",
    ]
    for key, count in metrics["confusion"].items():
        lines.append(f"- {key}: {count}")

    lines += [
        "",
        "## Cost & Latency",
        "- Model: _(fill in)_",
        "- Cost per 1,000 postings: _(fill in)_",
        "- Tokens per posting (avg): _(fill in)_",
        "- Wall-clock time per posting: _(fill in)_",
        "",
        "## Disagreements",
        "_(Hand-pick a few cases; note where the model was right and the human wrong.)_",
        "",
        "## Quality Gates",
        f"- Tier 1 boundary accuracy ≥ 80%: "
        f"{'PASS' if (b.get('accuracy') or 0) >= 0.80 else 'FAIL / not yet'}",
        f"- Tier 1 precision ≥ 0.85: "
        f"{'PASS' if (b.get('precision') or 0) >= 0.85 else 'FAIL / not yet'}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare hand labels to model claim classifications"
    )
    parser.add_argument("gold", type=Path, help="Hand-labeled JSONL")
    parser.add_argument("predictions", type=Path, help="Model classified JSONL")
    parser.add_argument(
        "--self-agreement",
        action="store_true",
        help="the 'predictions' file is a second hand-labeling pass, not model "
             "output: measure annotator pass-to-pass agreement instead",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write markdown report (default: print to stdout only)",
    )
    args = parser.parse_args()

    if not args.gold.exists():
        print(f"Error: gold file not found: {args.gold}", file=sys.stderr)
        sys.exit(1)
    if not args.predictions.exists():
        print(f"Error: predictions file not found: {args.predictions}", file=sys.stderr)
        sys.exit(1)

    gold_rows = load_jsonl(args.gold)
    pred_rows = load_jsonl(args.predictions)

    if looks_like_hand_labels(pred_rows) and not args.self_agreement:
        print(
            f"Error: {args.predictions} looks like hand labels, not model "
            f"output.\n"
            f"  No claim carries `predicted_tier` and no row names a model.\n"
            f"  Comparing gold labels to another set of labels measures "
            f"annotator agreement, not model accuracy — and if the two files "
            f"share a lineage it measures nothing at all.\n"
            f"  If that is what you want, pass --self-agreement.\n"
            f"  If you meant to evaluate the model, run Stage 2 first and "
            f"write `predicted_tier` to data/classified/claims.jsonl.",
            file=sys.stderr,
        )
        sys.exit(1)
    gold_idx = index_by_posting(gold_rows, extract_labeled_claims)
    pred_idx = index_by_posting(pred_rows, extract_predicted_claims)

    all_pairs: list[tuple[int, int]] = []
    matched_postings = 0
    for pid, gold_claims in gold_idx.items():
        pred_claims = pred_idx.get(pid)
        if not pred_claims:
            continue
        pairs = pair_claims(gold_claims, pred_claims)
        if pairs:
            matched_postings += 1
            all_pairs.extend(pairs)

    metrics = compute_metrics(all_pairs)
    report = render_report(
        metrics,
        args.gold,
        args.predictions,
        n_gold_postings=len(gold_idx),
        n_pred_postings=len(pred_idx),
        n_matched_postings=matched_postings,
        self_agreement=args.self_agreement,
    )
    print(report)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"\nWrote {args.report}", file=sys.stderr)

    # Exit non-zero if boundary accuracy is known and below target
    acc = metrics["tier1_boundary"].get("accuracy")
    if metrics["n"] == 0:
        print("Error: no matched claim pairs.", file=sys.stderr)
        sys.exit(1)
    if not args.self_agreement and acc is not None and acc < 0.80:
        sys.exit(2)


if __name__ == "__main__":
    main()
