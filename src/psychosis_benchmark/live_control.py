"""Local process controls and non-evidence telemetry for the frozen exploration.

Credentials travel over stdin, never argv or a saved credential file. Telemetry is
replaceable; research ledgers are not. An OS lock remains the collection authority.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from psychosis_benchmark.evidence import payload_hash

BATCH_NAME = "live-sized-exploration-2026-10-07"


def utc_now():
    return datetime.now(UTC).isoformat()


def atomic_json(path: Path, value: dict):
    """Unique temporary file; retry Windows sharing violations from concurrent readers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


class BatchLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if self.path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def owner_locked(directory: Path):
    path = directory / "owner.lock"
    if not path.exists():
        return False
    lock = BatchLock(path)
    acquired = lock.acquire()
    lock.close()
    return not acquired


def process_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_json(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def age_seconds(timestamp):
    try:
        return max(0.0, (datetime.now(UTC) - datetime.fromisoformat(timestamp)).total_seconds())
    except (TypeError, ValueError):
        return None


def collection_status(directory: Path):
    runtime = read_json(directory / "runtime.json")
    controller = read_json(directory / "controller.json")
    progress = read_json(directory / "progress.json")
    locked = owner_locked(directory)
    heartbeat_age = age_seconds(runtime.get("heartbeat_at_utc"))
    launch_age = age_seconds(controller.get("started_at_utc"))
    starting = (
        launch_age is not None
        and launch_age < 120
        and process_alive(controller.get("pid"))
        and runtime.get("pid") != controller.get("pid")
    )
    if locked:
        state = "pausing" if (directory / "STOP").exists() else "running"
    elif starting:
        state = "starting"
    elif progress.get("status") in {"completed", "finished_with_failures"}:
        state = progress["status"]
    elif runtime.get("status") in {"failed", "paused_error"}:
        state = "stopped_error"
    elif runtime.get("status") in {"paused", "incomplete_checkpointed"}:
        state = "paused"
    else:
        state = "stopped"
    return {
        "state": state,
        "active": locked or starting,
        "owner_lock_held": locked,
        "process_alive": process_alive(runtime.get("pid")),
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_fresh": heartbeat_age is not None and heartbeat_age < 20,
        "runtime": runtime,
        "progress": progress,
    }


class RuntimeMonitor:
    """Independent heartbeat, with no prompts, responses, or exception messages."""

    def __init__(self, directory: Path, models: list[str], interval=5.0):
        self.path = directory / "runtime.json"
        self.interval = interval
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.data = {
            "pid": os.getpid(),
            "started_at_utc": utc_now(),
            "status": "starting",
            "workers": {model: {"state": "starting"} for model in models},
        }
        self.flush()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()

    def flush(self):
        with self.lock:
            atomic_json(self.path, {**self.data, "heartbeat_at_utc": utc_now()})

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            try:
                self.flush()
            except OSError as error:
                with self.lock:
                    self.data["telemetry_error_type"] = type(error).__name__

    def set_state(self, state, **fields):
        with self.lock:
            self.data.update(status=state, **fields)

    def worker(self, model, **fields):
        with self.lock:
            self.data["workers"][model].update(updated_at_utc=utc_now(), **fields)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        self.flush()


def resume_collection(root: Path, api_key: str):
    """Resume only the designated recorded batch, with its persisted cap."""
    if not api_key.strip() or "\n" in api_key or "\r" in api_key:
        raise ValueError("valid_single_line_key_required")
    directory = root / "data/raw" / BATCH_NAME
    inputs = read_json(directory / "inputs.json")
    if payload_hash(inputs) != (directory / "input_hash.txt").read_text(encoding="utf-8").strip():
        raise ValueError("recorded_input_hash_mismatch")
    with sqlite3.connect((directory / "budget.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        cap = db.execute("SELECT limit_usd FROM settings").fetchone()[0]
    launch_lock = BatchLock(directory / "launch.lock")
    if not launch_lock.acquire():
        raise ValueError("launch_already_in_progress")
    try:
        status = collection_status(directory)
        if status["active"]:
            raise ValueError("collector_already_running")
        if status["state"] in {"completed", "finished_with_failures"}:
            raise ValueError("collector_finished")
        # STOP is an operator checkpoint, not research evidence.
        (directory / "STOP").unlink(missing_ok=True)
        command = [
            sys.executable,
            str(root / "scripts/run_sized_exploration.py"),
            "--live",
            "--resume",
            "--api-key-stdin",
            "--output-dir",
            str(directory),
            "--budget-usd",
            str(cap),
        ]
        environment = dict(os.environ)
        environment.pop("OPENROUTER_API_KEY", None)
        with (directory / "controller.log").open("ab", buffering=0) as log:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=log,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        try:
            atomic_json(directory / "controller.json", {"pid": process.pid, "started_at_utc": utc_now()})
            process.stdin.write((api_key.strip() + "\n").encode())
            process.stdin.close()
        except OSError:
            process.terminate()
            raise ValueError("collector_did_not_accept_stdin") from None
        return process.pid
    finally:
        launch_lock.close()


def request_pause(root: Path):
    (root / "data/raw" / BATCH_NAME / "STOP").touch()
