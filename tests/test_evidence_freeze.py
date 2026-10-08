import json
import zipfile

import pytest

from psychosis_benchmark.batch import SpendingBudget
from psychosis_benchmark.evidence import append_event
from psychosis_benchmark.evidence_freeze import file_hash, freeze_batch, verify_freeze
from psychosis_benchmark.live_control import BatchLock


def source_fixture(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    owner = BatchLock(directory / "owner.lock")
    assert owner.acquire()
    owner.close()
    ledger = directory / "ledgers/run.jsonl"
    append_event(ledger, event_type="run_started", run_id="run", payload={})
    append_event(ledger, event_type="run_failed", run_id="run", payload={"error_code": "empty_response"})
    (directory / "inputs.json").write_text('{"unchanged":true}')
    (directory / "progress.json").write_text(
        json.dumps(
            {
                "status": "finished_with_failures",
                "stored_responses": 0,
                "completed_conversations": 0,
                "input_hash": "fixturehash",
            }
        )
    )
    SpendingBudget(directory / "budget.sqlite3", 5)
    return directory


def audit_fixture(_):
    return {
        "verified_ledgers": 1,
        "planned_conversations": 1,
        "planned_responses": 4,
        "stored_responses": 0,
        "completed_conversations": 0,
        "input_hash": "fixturehash",
        "truncated_responses": 0,
        "models": [],
        "by_track": {},
    }


def test_freeze_preserves_source_and_archive_verifies(tmp_path):
    source = source_fixture(tmp_path)
    originals = {path: file_hash(path) for path in source.rglob("*") if path.is_file()}
    destination = tmp_path / "snapshot"
    receipt = freeze_batch(source, destination, audit=audit_fixture, source_commit="fixture", protect=False)
    assert verify_freeze(destination)["content_root_sha256"] == receipt["content_root_sha256"]
    assert receipt["terminal_failed_conversations"] == 1
    assert receipt["human_ratings_collected"] is False
    assert receipt["raw_data_publicly_released"] is False
    assert all(file_hash(path) == digest for path, digest in originals.items())
    assert not (destination / "raw/owner.lock").exists()
    with zipfile.ZipFile(destination.with_suffix(".zip")) as archive:
        assert archive.testzip() is None
        assert "manifest.json" in archive.namelist()
    with pytest.raises(ValueError, match="never replaced"):
        freeze_batch(source, destination, audit=audit_fixture, source_commit="fixture", protect=False)


def test_freeze_refuses_running_or_unclosed_batch(tmp_path):
    source = source_fixture(tmp_path)
    lock = BatchLock(source / "owner.lock")
    assert lock.acquire()
    with pytest.raises(ValueError, match="still owns"):
        freeze_batch(source, tmp_path / "snapshot", audit=audit_fixture, source_commit="fixture")
    lock.close()
    (source / "progress.json").write_text('{"status":"collecting"}')
    with pytest.raises(ValueError, match="has not closed"):
        freeze_batch(source, tmp_path / "snapshot", audit=audit_fixture, source_commit="fixture")


def test_verify_detects_changes_and_extra_files(tmp_path):
    source = source_fixture(tmp_path)
    destination = tmp_path / "snapshot"
    freeze_batch(source, destination, audit=audit_fixture, source_commit="fixture", protect=False)
    (destination / "unexpected.txt").touch()
    with pytest.raises(ValueError, match="unexpected"):
        verify_freeze(destination)
    (destination / "unexpected.txt").unlink()
    (destination / "raw/inputs.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        verify_freeze(destination)
