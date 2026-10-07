from __future__ import annotations

import io
import json
import os
import time

import pytest

from psychosis_benchmark import live_control
from psychosis_benchmark.batch import SpendingBudget
from psychosis_benchmark.evidence import payload_hash
from psychosis_benchmark.live_control import (
    BATCH_NAME,
    BatchLock,
    RuntimeMonitor,
    atomic_json,
    collection_status,
    owner_locked,
    process_alive,
    request_pause,
    resume_collection,
)


def saved_batch(tmp_path):
    directory = tmp_path / "data/raw" / BATCH_NAME
    directory.mkdir(parents=True)
    inputs = {"recorded": "unchanged"}
    (directory / "inputs.json").write_text(json.dumps(inputs))
    (directory / "input_hash.txt").write_text(payload_hash(inputs))
    SpendingBudget(directory / "budget.sqlite3", 5)
    return directory


def test_atomic_status_retries_reader_sharing_violation(tmp_path, monkeypatch):
    original = os.replace
    attempts = []

    def sharing_violation(source, target):
        attempts.append(source)
        if len(attempts) < 3:
            raise PermissionError("test reader")
        original(source, target)

    monkeypatch.setattr(os, "replace", sharing_violation)
    monkeypatch.setattr(live_control.time, "sleep", lambda _: None)
    atomic_json(tmp_path / "status.json", {"state": "running"})
    assert len(attempts) == 3
    assert json.loads((tmp_path / "status.json").read_text()) == {"state": "running"}
    assert not list(tmp_path.glob("*.tmp"))


def test_lock_released_and_stale_collecting_label_is_not_running(tmp_path):
    atomic_json(tmp_path / "progress.json", {"status": "collecting"})
    assert collection_status(tmp_path)["state"] == "stopped"
    lock = BatchLock(tmp_path / "owner.lock")
    assert lock.acquire()
    assert owner_locked(tmp_path)
    assert collection_status(tmp_path)["active"]
    lock.close()
    assert not owner_locked(tmp_path)
    assert collection_status(tmp_path)["state"] == "stopped"


def test_heartbeat_runs_without_new_responses_and_detects_finished_process(tmp_path):
    runtime = RuntimeMonitor(tmp_path, ["test-model"], interval=0.01)
    first = json.loads(runtime.path.read_text())["heartbeat_at_utc"]
    runtime.worker("test-model", state="retry_wait", turn=2, reason="http_429")
    time.sleep(0.05)
    assert json.loads(runtime.path.read_text())["heartbeat_at_utc"] != first
    runtime.set_state("paused", finished_at_utc=live_control.utc_now())
    runtime.close()
    result = collection_status(tmp_path)
    assert result["state"] == "paused"
    assert result["runtime"]["workers"]["test-model"]["turn"] == 2
    assert process_alive(os.getpid())
    assert not process_alive(99999999)


def test_resume_refuses_active_batch_and_input_drift(tmp_path, monkeypatch):
    directory = saved_batch(tmp_path)
    monkeypatch.setattr(live_control.subprocess, "Popen", lambda *a, **kw: pytest.fail("unexpected spawn"))
    lock = BatchLock(directory / "owner.lock")
    assert lock.acquire()
    with pytest.raises(ValueError, match="already_running"):
        resume_collection(tmp_path, "test-key")
    lock.close()
    (directory / "inputs.json").write_text("{}")
    with pytest.raises(ValueError, match="input_hash"):
        resume_collection(tmp_path, "test-key")


def test_resume_uses_stdin_exact_saved_cap_and_prevents_double_start(tmp_path, monkeypatch):
    directory = saved_batch(tmp_path)
    (directory / "STOP").touch()
    captured = {}

    class CapturingStdin(io.BytesIO):
        def close(self):
            captured["stdin_bytes"] = self.getvalue()
            super().close()

    class Process:
        pid = os.getpid()
        stdin = CapturingStdin()

    def spawn(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return Process()

    secret = "test-credential-never-save"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setattr(live_control.subprocess, "Popen", spawn)
    assert resume_collection(tmp_path, secret) == os.getpid()
    assert "--resume" in captured["command"]
    assert captured["command"][-2:] == ["--budget-usd", "5.0"]
    assert secret not in " ".join(captured["command"])
    assert "OPENROUTER_API_KEY" not in captured["kwargs"]["env"]
    assert captured["stdin_bytes"] == (secret + "\n").encode()
    assert not (directory / "STOP").exists()
    for path in directory.iterdir():
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
    with pytest.raises(ValueError, match="already_running"):
        resume_collection(tmp_path, secret)
    request_pause(tmp_path)
    assert (directory / "STOP").exists()


def test_dead_collector_error_overrides_stale_progress(tmp_path):
    atomic_json(tmp_path / "progress.json", {"status": "collecting"})
    atomic_json(tmp_path / "runtime.json", {"status": "failed", "pid": 99999999})
    result = collection_status(tmp_path)
    assert result["state"] == "stopped_error"
    assert not result["active"]
