from __future__ import annotations

import hashlib

import pytest

from psychosis_benchmark.annotation import (
    RatingRecord,
    SourceAnnotationItem,
    assert_packet_blinded,
    build_annotation_packet,
)


def _item(run: str, model: str, turn: int) -> SourceAnnotationItem:
    response = f"assistant response {run} {turn}"
    return SourceAnnotationItem(
        source_item_id=f"{run}_t{turn}",
        run_id=run,
        model_id=model,
        scenario_family="monitoring",
        presentation="ambiguous",
        context_condition="no_history",
        repetition=1,
        turn=turn,
        transcript=(
            {"role": "user", "content": "I am uncertain about an event."},
            {"role": "assistant", "content": response},
        ),
        response_hash=hashlib.sha256(response.encode()).hexdigest(),
    )


def test_packet_is_deterministic_blinded_and_keeps_conversations_together() -> None:
    source = [
        *[_item("run-a", "vendor/model-a", turn) for turn in range(1, 4)],
        *[_item("run-b", "vendor/model-b", turn) for turn in range(1, 4)],
    ]
    first = build_annotation_packet(
        source, secret=b"a" * 32, rubric_version="rubric-v1", seed=47, block_size=3
    )
    second = build_annotation_packet(
        source, secret=b"a" * 32, rubric_version="rubric-v1", seed=47, block_size=3
    )
    assert first == second
    public = {"items": [item.model_dump(mode="json") for item in first.items]}
    assert_packet_blinded(public)
    assert len({item.block_id for item in first.items}) == 2
    for conversation in {item.blind_conversation_id for item in first.items}:
        blocks = {item.block_id for item in first.items if item.blind_conversation_id == conversation}
        assert len(blocks) == 1
    assert {row.model_id for row in first.key} == {"vendor/model-a", "vendor/model-b"}


def test_packet_rejects_short_secret_and_incomplete_turns() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        build_annotation_packet(
            [_item("run-a", "vendor/model", 1)],
            secret=b"short",
            rubric_version="rubric-v1",
            seed=1,
        )
    with pytest.raises(ValueError, match="missing or duplicate"):
        build_annotation_packet(
            [_item("run-a", "vendor/model", 2)],
            secret=b"a" * 32,
            rubric_version="rubric-v1",
            seed=1,
        )


def test_blinding_audit_rejects_protected_fields() -> None:
    with pytest.raises(ValueError, match="protected fields leaked"):
        assert_packet_blinded({"items": [{"model_id": "revealed"}]})


def test_rating_contract_distinguishes_na_missing_and_unscorable() -> None:
    scored = RatingRecord(
        blind_item_id="item_a",
        rater_code="rater_a",
        rubric_version="rubric-v1",
        rating_status="scored",
        P1=0,
        P2="NA",
        P3="NA",
        P4=0,
        P5=0,
        S1=1,
        S2=1,
        S3=1,
        S4=1,
        S5=1,
    )
    assert scored.P2 == "NA"
    with pytest.raises(ValueError, match="require every axis"):
        RatingRecord(
            blind_item_id="item_b",
            rater_code="rater_a",
            rubric_version="rubric-v1",
            rating_status="scored",
            P1=0,
        )
    with pytest.raises(ValueError, match="require a reason"):
        RatingRecord(
            blind_item_id="item_c",
            rater_code="rater_a",
            rubric_version="rubric-v1",
            rating_status="unscorable",
        )
