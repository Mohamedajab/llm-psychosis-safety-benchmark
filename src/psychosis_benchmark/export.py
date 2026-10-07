"""Reconstruct annotation transcripts from verified collection evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from psychosis_benchmark.annotation import SourceAnnotationItem
from psychosis_benchmark.collection import find_script
from psychosis_benchmark.contexts import ContextHistory, messages_for_condition
from psychosis_benchmark.design import canonical_hash
from psychosis_benchmark.evidence import payload_hash, read_verified_events
from psychosis_benchmark.schema import ManifestRow, StudyBundle


def export_ledger(
    path: Path,
    *,
    study: StudyBundle,
    row: ManifestRow,
    histories: dict[str, ContextHistory],
    system_prompt: str,
) -> tuple[list[SourceAnnotationItem], dict[str, Any]]:
    events = read_verified_events(path)
    started = events[0]
    if started.run_id != row.run_id or started.payload.get("manifest_row") != row.model_dump(mode="json"):
        raise ValueError("evidence and supplied manifest disagree")
    if started.payload.get("study_hash") != canonical_hash(study):
        raise ValueError("study changed since collection; use the recorded configuration")
    if started.payload.get("system_prompt_hash") != payload_hash({"system_prompt": system_prompt.strip()}):
        raise ValueError("system prompt changed since collection")
    script = find_script(study, row.script_id)
    messages = [{"role": "system", "content": system_prompt.strip()}]
    messages.extend(messages_for_condition(study, row.context_condition, histories))
    received = [event for event in events if event.event_type == "response_received"]
    if [event.turn for event in received] != list(range(1, len(received) + 1)):
        raise ValueError("response sequence has missing or duplicate turns")
    items = []
    for event in received:
        turn = event.turn
        assert turn is not None
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("recorded response text is empty")
        messages.append({"role": "user", "content": script.turns[turn - 1]})
        messages.append({"role": "assistant", "content": text})
        items.append(
            SourceAnnotationItem(
                source_item_id=f"{row.run_id}:turn:{turn}",
                run_id=row.run_id,
                model_id=row.model_id,
                scenario_family=row.scenario_family,
                presentation=row.presentation.value,
                context_condition=row.context_condition,
                repetition=row.repetition,
                turn=turn,
                transcript=tuple(dict(message) for message in messages),
                response_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    terminal = events[-1]
    complete = terminal.event_type == "run_completed" and len(items) == row.planned_turns
    if terminal.event_type == "run_completed" and not complete:
        raise ValueError("completed ledger has wrong response count")
    summary = {
        "run_id": row.run_id,
        "model_id": row.model_id,
        "status": "completed" if complete else "incomplete",
        "accepted_responses": len(items),
        "planned_responses": row.planned_turns,
        "failure_reason": None if complete else terminal.payload.get("error_code", "interrupted"),
        "ledger_final_hash": terminal.event_hash,
    }
    return items, summary
