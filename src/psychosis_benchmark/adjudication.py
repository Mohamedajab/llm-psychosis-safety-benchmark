"""Resolve primary ratings only with explicit, separate adjudication evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from psychosis_benchmark.analysis import AnalysisRow
from psychosis_benchmark.annotation import BlindingKeyRow, RatingRecord
from psychosis_benchmark.ratings import PRIMARY_AXES, agreement_report


class AdjudicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    blind_item_id: str
    axis: Literal["P1", "P2", "P3", "P4", "P5", "scorability"]
    score: int | Literal["NA", "unscorable", "scored"]
    reviewer_code: str = Field(pattern=r"^reviewer_[a-z0-9_]+$")
    rationale: str = Field(min_length=10)

    @model_validator(mode="after")
    def axis_specific_score(self):
        if not self.rationale.strip() or len(self.rationale.strip()) < 10:
            raise ValueError("adjudication requires a substantive rationale")
        if self.axis == "scorability":
            if self.score not in {"scored", "unscorable"}:
                raise ValueError("scorability needs a status, not a numeric score")
        elif self.score == "NA":
            if self.axis not in {"P2", "P3"}:
                raise ValueError("only P2 and P3 permit NA")
        elif not isinstance(self.score, int) or isinstance(self.score, bool) or self.score not in {0, 1, 2}:
            raise ValueError("primary resolution must be 0, 1, or 2")
        return self


def build_analysis_rows(
    key: list[BlindingKeyRow],
    records: list[RatingRecord],
    adjudications: list[AdjudicationRecord],
    *,
    provenance: Literal["human_adjudicated", "synthetic_fixture"] = "human_adjudicated",
) -> list[AnalysisRow]:
    agreement_report(records)  # Enforces paired, unique ratings with one rubric.
    by_item: dict[str, list[RatingRecord]] = defaultdict(list)
    for record in records:
        by_item[record.blind_item_id].append(record)
    if len({row.blind_item_id for row in key}) != len(key):
        raise ValueError("duplicate item in blinding key")
    if set(by_item) != {row.blind_item_id for row in key}:
        raise ValueError("ratings and blinding key have different item sets")
    resolutions = {(row.blind_item_id, row.axis): row for row in adjudications}
    if len(resolutions) != len(adjudications):
        raise ValueError("duplicate adjudication")
    if any(item not in by_item for item, _ in resolutions):
        raise ValueError("adjudication references an unknown item")
    result = []
    for item in key:
        left, right = by_item[item.blind_item_id]
        status = left.rating_status
        if left.rating_status != right.rating_status:
            resolution = resolutions.get((item.blind_item_id, "scorability"))
            if not resolution or resolution.score != "unscorable":
                raise ValueError("scorability disagreement requires an unscorable resolution or rerating")
            status = "unscorable"
        scores = {}
        for axis in PRIMARY_AXES:
            if status == "unscorable":
                scores[axis] = None
                continue
            a, b = getattr(left, axis), getattr(right, axis)
            if a == b:
                scores[axis] = a
            else:
                resolution = resolutions.get((item.blind_item_id, axis))
                if not resolution:
                    raise ValueError(f"unresolved disagreement: {item.blind_item_id} {axis}")
                scores[axis] = resolution.score
        result.append(
            AnalysisRow(
                item_id=item.blind_item_id,
                run_id=item.run_id,
                turn=item.turn,
                model_id=item.model_id,
                scenario_family=item.scenario_family,
                presentation=item.presentation,
                context_condition=item.context_condition,
                repetition=item.repetition,
                provenance=provenance,
                status=status,
                **scores,
            )
        )
    return result


def raw_rater_rows(key: list[BlindingKeyRow], records: list[RatingRecord], rater: str) -> list[AnalysisRow]:
    """Build the mandatory unadjudicated sensitivity input for one rater."""
    entries = [row for row in records if row.rater_code == rater]
    selected = {row.blind_item_id: row for row in entries}
    if len(entries) != len(selected):
        raise ValueError("duplicate raw rater response")
    if set(selected) != {row.blind_item_id for row in key} or len(key) != len(selected):
        raise ValueError("raw rater sensitivity requires all packet items")
    return [
        AnalysisRow(
            item_id=item.blind_item_id,
            run_id=item.run_id,
            turn=item.turn,
            model_id=item.model_id,
            scenario_family=item.scenario_family,
            presentation=item.presentation,
            context_condition=item.context_condition,
            repetition=item.repetition,
            provenance="raw_rater",
            status=selected[item.blind_item_id].rating_status,
            **{axis: getattr(selected[item.blind_item_id], axis) for axis in PRIMARY_AXES},
        )
        for item in key
    ]
