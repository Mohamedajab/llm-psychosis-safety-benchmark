"""Append-only, hash-linked evidence records for model collection."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "run_started",
    "request_started",
    "response_received",
    "request_failed",
    "run_completed",
    "run_failed",
]


class EvidenceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["3.0.0"] = "3.0.0"
    sequence: int = Field(ge=1)
    event_type: EventType
    occurred_at_utc: str
    run_id: str = Field(min_length=1)
    turn: int | None = Field(default=None, ge=1)
    attempt: int | None = Field(default=None, ge=1)
    payload: dict[str, Any]
    previous_hash: str | None
    event_hash: str


class LedgerVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    event_count: int
    final_hash: str | None
    errors: tuple[str, ...] = ()


_SECRET_KEYS = {
    "authorization",
    "api_key",
    "openrouter_api_key",
    "access_token",
    "secret",
    "password",
}


def _assert_no_secrets(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in _SECRET_KEYS:
                raise ValueError(f"secret-like field is forbidden in evidence: {path}.{key}")
            _assert_no_secrets(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_secrets(item, f"{path}[{index}]")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    _assert_no_secrets(payload)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _event_hash(fields: dict[str, Any]) -> str:
    value = {key: item for key, item in fields.items() if key != "event_hash"}
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_events(path: Path) -> list[EvidenceEvent]:
    if not path.exists():
        return []
    events: list[EvidenceEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                events.append(EvidenceEvent.model_validate_json(line))
            except Exception as error:
                raise ValueError(f"invalid evidence line {line_number}: {error}") from error
    return events


def append_event(
    path: str | Path,
    *,
    event_type: EventType,
    run_id: str,
    payload: dict[str, Any],
    turn: int | None = None,
    attempt: int | None = None,
    occurred_at_utc: str | None = None,
) -> EvidenceEvent:
    """Append one event and fsync it before returning.

    A ledger is single-writer. Parallel workers must use one ledger file per run.
    """

    _assert_no_secrets(payload)
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_events(ledger_path)
    if existing and existing[-1].event_type in {"run_completed", "run_failed"}:
        raise ValueError("cannot append after a terminal run event")
    previous_hash = existing[-1].event_hash if existing else None
    fields: dict[str, Any] = {
        "schema_version": "3.0.0",
        "sequence": len(existing) + 1,
        "event_type": event_type,
        "occurred_at_utc": occurred_at_utc or datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "turn": turn,
        "attempt": attempt,
        "payload": payload,
        "previous_hash": previous_hash,
    }
    fields["event_hash"] = _event_hash(fields)
    event = EvidenceEvent.model_validate(fields)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(event.model_dump_json() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def verify_ledger(path: str | Path) -> LedgerVerification:
    ledger_path = Path(path)
    errors: list[str] = []
    try:
        events = _read_events(ledger_path)
    except ValueError as error:
        return LedgerVerification(valid=False, event_count=0, final_hash=None, errors=(str(error),))
    if not events:
        return LedgerVerification(
            valid=False,
            event_count=0,
            final_hash=None,
            errors=("ledger is empty",),
        )
    run_ids = {event.run_id for event in events}
    if len(run_ids) != 1:
        errors.append("ledger contains more than one run_id")
    if events[0].event_type != "run_started":
        errors.append("first event must be run_started")
    for index, event in enumerate(events):
        expected_sequence = index + 1
        if event.sequence != expected_sequence:
            errors.append(f"event {expected_sequence} has sequence {event.sequence}")
        expected_previous = events[index - 1].event_hash if index else None
        if event.previous_hash != expected_previous:
            errors.append(f"event {expected_sequence} has an invalid previous_hash")
        if event.event_hash != _event_hash(event.model_dump(mode="json")):
            errors.append(f"event {expected_sequence} has an invalid event_hash")
        try:
            _assert_no_secrets(event.payload)
        except ValueError as error:
            errors.append(str(error))
        if index < len(events) - 1 and event.event_type in {"run_completed", "run_failed"}:
            errors.append("terminal run event is not final")
    return LedgerVerification(
        valid=not errors,
        event_count=len(events),
        final_hash=events[-1].event_hash,
        errors=tuple(errors),
    )


def ledger_contains_run(path: str | Path, run_id: str) -> bool:
    return any(event.run_id == run_id for event in _read_events(Path(path)))


def read_verified_events(path: str | Path) -> list[EvidenceEvent]:
    """Read only a verified chain; hash validity alone does not prove completion."""
    report = verify_ledger(path)
    if not report.valid:
        raise ValueError(f"invalid evidence ledger: {'; '.join(report.errors)}")
    return _read_events(Path(path))
