import pytest

from psychosis_benchmark.adjudication import AdjudicationRecord, build_analysis_rows, raw_rater_rows
from psychosis_benchmark.annotation import BlindingKeyRow, RatingRecord


def _key():
    return BlindingKeyRow(
        blind_item_id="item",
        blind_conversation_id="conversation",
        source_item_id="source",
        run_id="run",
        model_id="vendor/model",
        scenario_family="family",
        presentation="control",
        context_condition="no_history",
        repetition=1,
        turn=1,
        response_hash="a" * 64,
    )


def _rating(rater, score):
    return RatingRecord(
        blind_item_id="item",
        rater_code=rater,
        rubric_version="rubric",
        rating_status="scored",
        P1=score,
        P2=0,
        P3=0,
        P4=0,
        P5=0,
        S1=1,
        S2=1,
        S3=1,
        S4=1,
        S5=1,
    )


def test_disagreement_cannot_be_silently_averaged_or_relabelled():
    records = [_rating("rater_a", 0), _rating("rater_b", 2)]
    with pytest.raises(ValueError, match="unresolved disagreement"):
        build_analysis_rows([_key()], records, [])
    resolution = AdjudicationRecord(
        blind_item_id="item",
        axis="P1",
        score=1,
        reviewer_code="reviewer_c",
        rationale="The anchor supports the middle category.",
    )
    rows = build_analysis_rows([_key()], records, [resolution])
    assert rows[0].P1 == 1
    assert rows[0].provenance == "human_adjudicated"
    assert records[0].P1 == 0 and records[1].P1 == 2


@pytest.mark.parametrize("axis,score", [("P1", "NA"), ("P2", 3), ("P1", True), ("scorability", 1)])
def test_invalid_adjudication_is_rejected(axis, score):
    with pytest.raises(ValueError):
        AdjudicationRecord(
            blind_item_id="item",
            axis=axis,
            score=score,
            reviewer_code="reviewer_c",
            rationale="An explicit review rationale.",
        )


def test_raw_rater_sensitivity_rejects_duplicate_items():
    with pytest.raises(ValueError, match="duplicate"):
        raw_rater_rows([_key()], [_rating("rater_a", 0), _rating("rater_a", 1)], "rater_a")
