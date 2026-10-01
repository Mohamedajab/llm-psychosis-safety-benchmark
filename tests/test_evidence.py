from __future__ import annotations

import json

import pytest

from psychosis_benchmark.evidence import append_event, payload_hash, verify_ledger


def test_hash_linked_ledger_verifies_and_closes(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    append_event(
        path,
        event_type="run_started",
        run_id="run-1",
        payload={"model_id": "example/model"},
        occurred_at_utc="2026-10-01T00:00:00+00:00",
    )
    append_event(
        path,
        event_type="request_started",
        run_id="run-1",
        turn=1,
        attempt=1,
        payload={"request_hash": payload_hash({"model": "example/model"})},
        occurred_at_utc="2026-10-01T00:00:01+00:00",
    )
    append_event(
        path,
        event_type="response_received",
        run_id="run-1",
        turn=1,
        attempt=1,
        payload={"text": "A response", "finish_reason": "stop"},
        occurred_at_utc="2026-10-01T00:00:02+00:00",
    )
    append_event(
        path,
        event_type="run_completed",
        run_id="run-1",
        payload={"completed_turns": 1},
        occurred_at_utc="2026-10-01T00:00:03+00:00",
    )
    report = verify_ledger(path)
    assert report.valid
    assert report.event_count == 4
    with pytest.raises(ValueError, match="cannot append"):
        append_event(path, event_type="run_completed", run_id="run-1", payload={})


def test_tampering_is_detected(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    append_event(path, event_type="run_started", run_id="run-1", payload={"value": 1})
    row = json.loads(path.read_text(encoding="utf-8"))
    row["payload"]["value"] = 2
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    report = verify_ledger(path)
    assert not report.valid
    assert any("invalid event_hash" in error for error in report.errors)


def test_secret_like_fields_are_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="secret-like"):
        append_event(
            tmp_path / "run.jsonl",
            event_type="run_started",
            run_id="run-1",
            payload={"api_key": "do-not-store"},
        )
