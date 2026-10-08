"""Verified, write-protected copies of closed exploratory evidence; never a preregistration."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
import zipfile
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from psychosis_benchmark.evidence import payload_hash, read_verified_events
from psychosis_benchmark.live_control import BatchLock

OPERATOR_FILES = {"owner.lock", "launch.lock", "STOP"}


def file_hash(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: dict):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")


def verify_freeze(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    if payload_hash(entries) != manifest["content_root_sha256"]:
        raise ValueError("freeze manifest root mismatch")
    expected = {"manifest.json"}
    for entry in entries:
        relative = Path(entry["path"])
        path = directory / relative
        if relative.is_absolute() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("unsafe manifest path")
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or linked frozen artifact")
        if path.stat().st_size != entry["size_bytes"] or file_hash(path) != entry["sha256"]:
            raise ValueError("frozen artifact changed")
        expected.add(entry["path"])
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("unexpected frozen artifacts")
    return {"verified": True, "files": len(entries), "content_root_sha256": manifest["content_root_sha256"]}


def freeze_batch(source: Path, destination: Path, *, audit: Callable, source_commit: str, protect=True):
    source, destination = source.resolve(), destination.resolve()
    archive = destination.with_suffix(".zip")
    if destination.exists() or archive.exists():
        raise ValueError("new freeze destination required; existing snapshots are never replaced")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("source and snapshot must be disjoint")
    if not (source / "owner.lock").is_file():
        raise ValueError("expected recorded batch owner lock")
    lock = BatchLock(source / "owner.lock")
    if not lock.acquire():
        raise ValueError("collector still owns this batch")
    try:
        progress = json.loads((source / "progress.json").read_text(encoding="utf-8"))
        if progress["status"] not in {"completed", "finished_with_failures"}:
            raise ValueError("batch has not closed")
        report = audit(source)
        if report["verified_ledgers"] != report["planned_conversations"]:
            raise ValueError("not every planned conversation has a ledger")
        failures, terminals = Counter(), Counter()
        for path in (source / "ledgers").glob("*.jsonl"):
            terminal = read_verified_events(path)[-1]
            if terminal.event_type not in {"run_completed", "run_failed"}:
                raise ValueError("nonterminal conversation in closed batch")
            terminals[terminal.event_type] += 1
            if terminal.event_type == "run_failed":
                failures[terminal.payload["error_code"]] += 1
        for field in ("stored_responses", "completed_conversations", "input_hash"):
            if report[field] != progress[field]:
                raise ValueError("progress and audited evidence disagree")
        with sqlite3.connect((source / "budget.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
            cap = db.execute("SELECT limit_usd FROM settings").fetchone()[0]
            committed, recorded, unknown = db.execute("""SELECT
                COALESCE(SUM(COALESCE(charged,reserved)),0), COALESCE(SUM(charged),0),
                SUM(CASE WHEN charged IS NULL THEN 1 ELSE 0 END) FROM requests""").fetchone()
        originals, excluded = {}, []
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("linked evidence cannot be frozen")
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            if path.name in OPERATOR_FILES or path.suffix == ".tmp":
                excluded.append(relative)
                continue
            originals[relative] = file_hash(path)
        destination.mkdir(parents=True)
        marker = destination / "FREEZE_IN_PROGRESS"
        marker.touch(exist_ok=False)
        for relative, digest in originals.items():
            copied = destination / "raw" / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            with (source / relative).open("rb") as original, copied.open("xb") as target:
                for block in iter(lambda: original.read(1024 * 1024), b""):
                    target.write(block)
            if file_hash(copied) != digest or file_hash(source / relative) != digest:
                raise ValueError("evidence changed while copying")
        if any(file_hash(source / relative) != digest for relative, digest in originals.items()):
            raise ValueError("source evidence changed before final verification")
        report["snapshot_closed"] = True
        report["warning"] = (
            "Closed exploratory collection, not achieved planned sample or clinical findings. "
            "Technical failures and unknown billing remain in the frozen record. No human ratings exist."
        )
        frozen_at = datetime.now(UTC).isoformat()
        write_new_json(destination / "audit.json", report)
        write_new_json(
            destination / "metadata.json",
            {
                "kind": "post_collection_exploratory_evidence_freeze",
                "frozen_at_utc": frozen_at,
                "source_batch": source.name,
                "source_commit": source_commit,
                "input_hash": report["input_hash"],
                "excluded_operator_files": excluded,
                "budget": {
                    "cap_usd": cap,
                    "recorded_cost_usd": recorded,
                    "conservative_committed_usd": committed,
                    "unknown_attempts": unknown,
                },
                "not_preregistration": True,
                "protection": (
                    "SHA-256 verification plus OS read-only files; not tamper-proof archival storage"
                ),
                "freeze_tool_sha256": file_hash(Path(__file__)),
            },
        )
        marker.unlink()
        entries = [
            {
                "path": p.relative_to(destination).as_posix(),
                "size_bytes": p.stat().st_size,
                "sha256": file_hash(p),
            }
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        ]
        root_hash = payload_hash(entries)
        write_new_json(
            destination / "manifest.json",
            {
                "schema_version": "1.0",
                "frozen_at_utc": frozen_at,
                "content_root_sha256": root_hash,
                "files": entries,
            },
        )
        verify_freeze(destination)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for path in sorted(destination.rglob("*")):
                if path.is_file():
                    bundle.write(path, arcname=path.relative_to(destination).as_posix())
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise ValueError("archive verification failed")
            for entry in entries:
                if hashlib.sha256(bundle.read(entry["path"])).hexdigest() != entry["sha256"]:
                    raise ValueError("archive content mismatch")
        receipt = {
            "kind": "post_collection_exploratory_evidence_freeze",
            "frozen_at_utc": frozen_at,
            "input_hash": report["input_hash"],
            "source_commit": source_commit,
            "freeze_tool_sha256": file_hash(Path(__file__)),
            "content_root_sha256": root_hash,
            "archive_sha256": file_hash(archive),
            "archive_bytes": archive.stat().st_size,
            "snapshot_files": len(entries),
            "verified_ledgers": report["verified_ledgers"],
            "planned_conversations": report["planned_conversations"],
            "completed_conversations": report["completed_conversations"],
            "terminal_failed_conversations": terminals["run_failed"],
            "planned_responses": report["planned_responses"],
            "stored_responses": report["stored_responses"],
            "truncated_responses": report["truncated_responses"],
            "failure_reasons": dict(failures),
            "budget": {
                "cap_usd": cap,
                "recorded_cost_usd": recorded,
                "conservative_committed_usd": committed,
                "unknown_attempts": unknown,
            },
            "models": report["models"],
            "by_track": report["by_track"],
            "raw_data_publicly_released": False,
            "human_ratings_collected": False,
            "not_preregistration": True,
        }
        if protect:
            for path in [*destination.rglob("*"), archive]:
                if path.is_file():
                    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        return receipt
    finally:
        lock.close()
