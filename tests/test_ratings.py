from __future__ import annotations

import pytest

from psychosis_benchmark.annotation import RatingRecord
from psychosis_benchmark.ratings import agreement_report


def _rating(item: str, rater: str, *, p2: int | str = 1) -> RatingRecord:
    return RatingRecord(
        blind_item_id=item,
        rater_code=rater,
        rubric_version="rubric-v1",
        rating_status="scored",
        P1=1,
        P2=p2,
        P3=1,
        P4=0,
        P5=0,
        S1=1,
        S2=1,
        S3=1,
        S4=1,
        S5=1,
    )


def test_agreement_report_preserves_na_decisions() -> None:
    records = [
        _rating("item-a", "rater_a", p2="NA"),
        _rating("item-a", "rater_b", p2="NA"),
        _rating("item-b", "rater_a", p2=1),
        _rating("item-b", "rater_b", p2=2),
    ]
    report = agreement_report(records)
    assert report["items"] == 2
    assert report["axes"]["P2"]["na_decision_agreement"] == 1.0
    assert report["axes"]["P2"]["numeric_pairs"] == 1
    assert report["axes"]["P2"]["exact_agreement"] == 0.5


def test_agreement_report_rejects_incomplete_and_duplicate_ratings() -> None:
    with pytest.raises(ValueError, match="exactly two"):
        agreement_report([_rating("item-a", "rater_a")])
    duplicate = [_rating("item-a", "rater_a"), _rating("item-a", "rater_a")]
    with pytest.raises(ValueError, match="duplicate rating"):
        agreement_report(duplicate)
