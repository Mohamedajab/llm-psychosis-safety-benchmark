"""Pre-adjudication agreement reports from strict independent rating records."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from psychosis_benchmark.annotation import RatingRecord
from psychosis_benchmark.statistics import weighted_kappa

PRIMARY_AXES = ("P1", "P2", "P3", "P4", "P5")


def agreement_report(records: list[RatingRecord]) -> dict[str, Any]:
    """Calculate axis-level agreement without silently accepting incomplete pairs."""

    if not records:
        raise ValueError("at least one rating record is required")
    if len({record.rater_code for record in records}) != 2:
        raise ValueError("agreement requires the same two independent raters")
    if len({record.rubric_version for record in records}) != 1:
        raise ValueError("ratings use different rubric versions")
    seen: set[tuple[str, str]] = set()
    grouped: dict[str, list[RatingRecord]] = defaultdict(list)
    for record in records:
        identity = (record.blind_item_id, record.rater_code)
        if identity in seen:
            raise ValueError(f"duplicate rating for {identity[0]} by {identity[1]}")
        seen.add(identity)
        grouped[record.blind_item_id].append(record)
    incomplete = sorted(item_id for item_id, values in grouped.items() if len(values) != 2)
    if incomplete:
        raise ValueError(f"items do not have exactly two independent ratings: {incomplete[:5]}")
    if any(len({value.rater_code for value in values}) != 2 for values in grouped.values()):
        raise ValueError("paired records must come from two distinct raters")

    scored_pairs = [
        tuple(sorted(values, key=lambda item: item.rater_code))
        for values in grouped.values()
        if all(value.rating_status == "scored" for value in values)
    ]
    unscorable_pairs = len(grouped) - len(scored_pairs)
    axes: dict[str, Any] = {}
    for axis in PRIMARY_AXES:
        pairs = [(getattr(left, axis), getattr(right, axis)) for left, right in scored_pairs]
        raw_exact = sum(left == right for left, right in pairs) / len(pairs) if pairs else None
        numeric = [(left, right) for left, right in pairs if isinstance(left, int) and isinstance(right, int)]
        kappa = (
            weighted_kappa([left for left, _ in numeric], [right for _, right in numeric])
            if numeric
            else None
        )
        axis_report: dict[str, Any] = {
            "paired_items": len(pairs),
            "exact_agreement": raw_exact,
            "numeric_pairs": len(numeric),
            "linear_weighted_kappa": kappa,
            "kappa_status": "defined" if kappa is not None else "undefined_no_variation_or_no_numeric_pairs",
            "score_counts": {
                "rater_left": dict(Counter(str(left) for left, _ in pairs)),
                "rater_right": dict(Counter(str(right) for _, right in pairs)),
            },
        }
        if axis in {"P2", "P3"}:
            axis_report["na_decision_agreement"] = (
                sum((left == "NA") == (right == "NA") for left, right in pairs) / len(pairs)
                if pairs
                else None
            )
        axes[axis] = axis_report
    return {
        "schema_version": "3.0.0",
        "items": len(grouped),
        "fully_scored_pairs": len(scored_pairs),
        "pairs_with_unscorable_record": unscorable_pairs,
        "axes": axes,
    }
