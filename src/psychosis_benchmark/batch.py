"""Exploratory checkpoint collection with persistent conservative spending reservations.

Never replaces a stored response or appends to a terminal ledger. A resume continues
the same transcript; unknown deliveries remain budgeted at their upper estimate.
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from psychosis_benchmark.collection import find_model, find_script
from psychosis_benchmark.contexts import ContextHistory, messages_for_condition
from psychosis_benchmark.design import canonical_hash
from psychosis_benchmark.evidence import append_event, payload_hash, read_verified_events
from psychosis_benchmark.provider import OpenRouterClient, ProviderCallError
from psychosis_benchmark.schema import ManifestRow, StudyBundle


class BatchPaused(RuntimeError):
    """A resumable checkpoint, not an observation of safety or a terminal failure."""


class SpendingBudget:
    def __init__(self, path: Path, limit_usd: float):
        if not math.isfinite(limit_usd) or limit_usd <= 0:
            raise ValueError("positive finite budget required")
        self.path = path
        self.limit = limit_usd
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (limit_usd REAL NOT NULL)")
            row = db.execute("SELECT limit_usd FROM settings").fetchone()
            if row and row[0] != limit_usd:
                raise ValueError("resume must retain the original spending cap")
            if not row:
                db.execute("INSERT INTO settings VALUES (?)", (limit_usd,))
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, reserved REAL NOT NULL, charged REAL,
                status TEXT NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=60)

    def reserve(self, request_id: str, amount: float):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("invalid reservation")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            total = db.execute(
                "SELECT COALESCE(SUM(COALESCE(charged, reserved)),0) FROM requests"
            ).fetchone()[0]
            if total + amount > self.limit:
                raise BatchPaused("local_spending_cap")
            db.execute("INSERT INTO requests VALUES (?, ?, NULL, 'reserved')", (request_id, amount))

    def settle(self, request_id: str, cost: float | None, status: str):
        if cost is not None and (not math.isfinite(cost) or cost < 0):
            raise ValueError("invalid recorded cost")
        with self.connect() as db:
            db.execute(
                "UPDATE requests SET charged=?, status=? WHERE request_id=?", (cost, status, request_id)
            )

    def snapshot(self):
        with self.connect() as db:
            total, actual, uncertain, attempts = db.execute("""SELECT
                COALESCE(SUM(COALESCE(charged, reserved)),0),
                COALESCE(SUM(charged),0),
                SUM(CASE WHEN charged IS NULL THEN 1 ELSE 0 END), COUNT(*) FROM requests""").fetchone()
        return {
            "cap_usd": self.limit,
            "recorded_cost_usd": actual,
            "conservative_committed_usd": total,
            "unsettled_or_unknown_attempts": uncertain or 0,
            "reserved_attempts": attempts,
        }


def request_ceiling(model_id: str, messages: list[dict[str, str]], max_tokens: int) -> float:
    if model_id.endswith(":free"):
        return 0.0
    # UTF-8 byte count plus generous role/template overhead is an upper planning
    # estimate, not a tokenizer measurement. An unexpected excess cost stops the run.
    input_bound = 1024 + sum(len(m["content"].encode("utf-8")) + 128 for m in messages)
    return (input_bound * 0.10 + max_tokens * 0.40) / 1_000_000


def checkpoint_conversation(
    *,
    study: StudyBundle,
    row: ManifestRow,
    histories: dict[str, ContextHistory],
    system_prompt: str,
    client: OpenRouterClient,
    ledger: Path,
    budget: SpendingBudget,
    attempts_per_session: int = 5,
    interval_seconds: float = 3,
    sleep: Callable[[float], None] = time.sleep,
    on_response: Callable[[], None] = lambda: None,
    on_activity: Callable[[dict], None] = lambda _: None,
    stop_requested: Callable[[], bool] = lambda: False,
) -> str:
    if row.stage == "confirmatory":
        raise ValueError("checkpoint runner is exploratory only")
    script = find_script(study, row.script_id)
    model = find_model(study, row.model_id)
    context = messages_for_condition(study, row.context_condition, histories)
    messages = [{"role": "system", "content": system_prompt.strip()}, *context]
    start = {
        "manifest_row": row.model_dump(mode="json"),
        "study_hash": canonical_hash(study),
        "system_prompt_hash": payload_hash({"system_prompt": system_prompt.strip()}),
        "context_hash": payload_hash({"messages": list(context)}),
    }
    events = read_verified_events(ledger) if ledger.exists() else []
    if events:
        if events[0].run_id != row.run_id or events[0].payload != start:
            raise ValueError("checkpoint snapshot, context, system, or manifest drift")
    else:
        append_event(ledger, event_type="run_started", run_id=row.run_id, payload=start)
    completed = 0
    last_response = None
    last_attempt: dict[int, int] = {}
    pending = None
    # Validate every previous request against the reconstructed transcript, not
    # just its hash chain. Only accepted recorded responses advance the transcript.
    for event in events[1:]:
        if event.event_type == "request_started":
            if event.turn != completed + 1 or completed >= len(script.turns):
                raise ValueError("checkpoint request out of order")
            current_messages = [*messages, {"role": "user", "content": script.turns[completed]}]
            payload = client.build_payload(
                model_id=row.model_id,
                messages=current_messages,
                generation=study.design.generation,
                seed=row.planned_seed if model.supports_seed else None,
                provider_pin=model.provider_pin,
            )
            if event.payload.get("request_hash") != payload_hash(payload):
                raise ValueError("checkpoint request transcript drift")
            if pending is not None or event.attempt != last_attempt.get(event.turn, 0) + 1:
                raise ValueError("checkpoint attempt sequence invalid")
            last_attempt[event.turn] = event.attempt
            pending = event
        elif event.event_type in {"response_received", "request_failed"}:
            if pending is None or (event.turn, event.attempt) != (pending.turn, pending.attempt):
                raise ValueError("checkpoint result has no matching request")
            if event.event_type == "response_received":
                last_response = event
                if event.payload.get("request_hash") != pending.payload["request_hash"]:
                    raise ValueError("checkpoint response hash mismatch")
                if (
                    event.payload.get("requested_model_id") != row.model_id
                    or event.payload.get("resolved_model_id") != row.model_id
                ):
                    raise ValueError("checkpoint response model mismatch")
                text = event.payload.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("checkpoint response is empty")
                messages.extend(
                    [
                        {"role": "user", "content": script.turns[completed]},
                        {"role": "assistant", "content": text},
                    ]
                )
                completed += 1
            pending = None
    if events and events[-1].event_type in {"run_completed", "run_failed"}:
        if events[-1].event_type == "run_completed" and completed != row.planned_turns:
            raise ValueError("terminal completion has wrong response count")
        return "completed" if events[-1].event_type == "run_completed" else "failed"
    if last_response is not None:
        finish = last_response.payload.get("finish_reason")
        if finish != "stop":
            append_event(
                ledger,
                event_type="run_failed",
                run_id=row.run_id,
                payload={
                    "completed_turns": completed,
                    "failed_turn": completed,
                    "error_code": "truncated_response" if finish == "length" else "invalid_finish_reason",
                },
            )
            return "failed"
        recorded_cost = last_response.payload.get("usage", {}).get("cost")
        before_response = messages[:-1]
        ceiling = request_ceiling(row.model_id, before_response, study.design.generation.max_output_tokens)
        if not row.model_id.endswith(":free") and (recorded_cost is None or recorded_cost > ceiling + 1e-9):
            raise BatchPaused("cost_missing_or_exceeds_reservation")
    if events and events[-1].event_type == "run_paused":
        delay = events[-1].payload.get("retry_not_before_delay_seconds", 0)
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(events[-1].occurred_at_utc)).total_seconds()
        remaining = max(0, delay - elapsed)
        if remaining > 60:
            raise BatchPaused("retry_after_not_elapsed")
        if remaining:
            sleep(remaining)
        if events[-1].payload.get("error_code") == "cost_missing_or_exceeds_reservation":
            raise BatchPaused("cost_missing_or_exceeds_reservation")
    if pending is not None:
        append_event(
            ledger,
            event_type="request_failed",
            run_id=row.run_id,
            turn=pending.turn,
            attempt=pending.attempt,
            payload={"error_code": "interrupted_delivery_unknown", "retryable": True, "http_status": None},
        )
    for turn in range(completed + 1, len(script.turns) + 1):
        messages.append({"role": "user", "content": script.turns[turn - 1]})
        payload = client.build_payload(
            model_id=row.model_id,
            messages=messages,
            generation=study.design.generation,
            seed=row.planned_seed if model.supports_seed else None,
            provider_pin=model.provider_pin,
        )
        for session_attempt in range(attempts_per_session):
            if stop_requested():
                append_event(
                    ledger,
                    event_type="run_paused",
                    run_id=row.run_id,
                    payload={"error_code": "operator_checkpoint", "next_turn": turn},
                )
                raise BatchPaused("operator_checkpoint")
            attempt = last_attempt.get(turn, 0) + 1
            request_id = f"{row.run_id}:{turn}:{attempt}:{uuid4().hex}"
            ceiling = request_ceiling(row.model_id, messages, study.design.generation.max_output_tokens)
            try:
                budget.reserve(request_id, ceiling)
            except BatchPaused as error:
                append_event(
                    ledger,
                    event_type="run_paused",
                    run_id=row.run_id,
                    payload={"error_code": str(error), "next_turn": turn},
                )
                raise
            append_event(
                ledger,
                event_type="request_started",
                run_id=row.run_id,
                turn=turn,
                attempt=attempt,
                payload={
                    "request_hash": payload_hash(payload),
                    "message_count": len(messages),
                    "provider_pin": model.provider_pin,
                    "budget_reservation_id": request_id,
                },
            )
            last_attempt[turn] = attempt
            on_activity(
                {
                    "state": "requesting",
                    "turn": turn,
                    "attempt": attempt,
                    "request_started_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            try:
                result = client.complete_once(
                    model_id=row.model_id,
                    messages=messages,
                    generation=study.design.generation,
                    seed=row.planned_seed if model.supports_seed else None,
                    provider_pin=model.provider_pin,
                )
            except ProviderCallError as error:
                # Explicit HTTP rejections have no delivered completion. Unknown
                # transport/server/format outcomes retain their reservation.
                rejection = error.status_code in {400, 401, 402, 403, 404, 429}
                budget.settle(request_id, 0.0 if rejection else None, error.code)
                append_event(
                    ledger,
                    event_type="request_failed",
                    run_id=row.run_id,
                    turn=turn,
                    attempt=attempt,
                    payload={
                        "error_code": error.code,
                        "http_status": error.status_code,
                        "retryable": error.retryable,
                        "retry_after_seconds": error.retry_after_seconds,
                    },
                )
                if not error.retryable:
                    append_event(
                        ledger,
                        event_type="run_failed",
                        run_id=row.run_id,
                        payload={"completed_turns": turn - 1, "failed_turn": turn, "error_code": error.code},
                    )
                    return "failed"
                delay = max(interval_seconds, min(60, 5 * 2**session_attempt), error.retry_after_seconds or 0)
                on_activity(
                    {
                        "state": "retry_wait",
                        "turn": turn,
                        "attempt": attempt,
                        "reason": error.code,
                        "retry_delay_seconds": delay,
                    }
                )
                if session_attempt + 1 == attempts_per_session or delay > 60:
                    append_event(
                        ledger,
                        event_type="run_paused",
                        run_id=row.run_id,
                        payload={
                            "error_code": error.code,
                            "next_turn": turn,
                            "retry_not_before_delay_seconds": delay,
                        },
                    )
                    raise BatchPaused(error.code) from None
                sleep(delay)
                continue
            cost = result.usage.get("cost")
            if row.model_id.endswith(":free") and cost is None:
                cost = 0.0
            budget.settle(request_id, cost, "response_received")
            append_event(
                ledger,
                event_type="response_received",
                run_id=row.run_id,
                turn=turn,
                attempt=attempt,
                payload={
                    "text": result.text,
                    "requested_model_id": result.requested_model_id,
                    "resolved_model_id": result.resolved_model_id,
                    "provider_name": result.provider_name,
                    "generation_id": result.generation_id,
                    "request_id": result.request_id,
                    "finish_reason": result.finish_reason,
                    "usage": result.usage,
                    "latency_ms": result.latency_ms,
                    "request_hash": result.request_hash,
                    "truncated": result.truncated,
                },
            )
            on_response()
            messages.append({"role": "assistant", "content": result.text})
            invalid_finish = result.finish_reason not in {"stop", "length"}
            if result.truncated or invalid_finish:
                append_event(
                    ledger,
                    event_type="run_failed",
                    run_id=row.run_id,
                    payload={
                        "completed_turns": turn,
                        "failed_turn": turn,
                        "error_code": "truncated_response" if result.truncated else "invalid_finish_reason",
                    },
                )
                return "failed"
            if cost is None or cost > ceiling + 1e-9:
                append_event(
                    ledger,
                    event_type="run_paused",
                    run_id=row.run_id,
                    payload={"error_code": "cost_missing_or_exceeds_reservation", "next_turn": turn + 1},
                )
                raise BatchPaused("cost_missing_or_exceeds_reservation")
            sleep(interval_seconds)
            break
    append_event(
        ledger, event_type="run_completed", run_id=row.run_id, payload={"completed_turns": len(script.turns)}
    )
    return "completed"
