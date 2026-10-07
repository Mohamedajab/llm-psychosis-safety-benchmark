"""Non-mutating evidence and request-transcript audit for a sized exploratory batch."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.collection import find_model, find_script  # noqa: E402
from psychosis_benchmark.contexts import ContextHistory, messages_for_condition  # noqa: E402
from psychosis_benchmark.design import canonical_hash  # noqa: E402
from psychosis_benchmark.evidence import payload_hash, read_verified_events  # noqa: E402
from psychosis_benchmark.provider import OpenRouterClient  # noqa: E402
from psychosis_benchmark.schema import ManifestRow, StudyBundle  # noqa: E402


def audit_batch(directory: Path):
    inputs = json.loads((directory / "inputs.json").read_text(encoding="utf-8"))
    if payload_hash(inputs) != (directory / "input_hash.txt").read_text(encoding="utf-8").strip():
        raise ValueError("collection input hash mismatch")
    studies = {key: StudyBundle.model_validate(value) for key, value in inputs["studies"].items()}
    histories = {key: ContextHistory.model_validate(value) for key, value in inputs["histories"].items()}
    output_rows, costs, providers = [], [], Counter()
    truncated = invalid_finish = missing_cost = 0
    expected_paths = {item["row"]["run_id"] + ".jsonl" for item in inputs["rows"]}
    actual_paths = {path.name for path in (directory / "ledgers").glob("*.jsonl")}
    if actual_paths - expected_paths:
        raise ValueError("unexpected ledger not present in recorded manifest")
    for item in inputs["rows"]:
        track, row = item["track"], ManifestRow.model_validate(item["row"])
        study = studies[track]
        ledger = directory / "ledgers" / f"{row.run_id}.jsonl"
        if not ledger.exists():
            output_rows.append(
                {
                    "run_id": row.run_id,
                    "model_id": row.model_id,
                    "track": track,
                    "scenario_family": row.scenario_family,
                    "status": "not_started",
                    "accepted_responses": 0,
                    "planned_responses": row.planned_turns,
                }
            )
            continue
        events = read_verified_events(ledger)
        context = messages_for_condition(study, row.context_condition, histories)
        expected_header = {
            "manifest_row": row.model_dump(mode="json"),
            "study_hash": canonical_hash(study),
            "system_prompt_hash": payload_hash({"system_prompt": inputs["system_prompt"].strip()}),
            "context_hash": payload_hash({"messages": list(context)}),
        }
        if events[0].run_id != row.run_id or events[0].payload != expected_header:
            raise ValueError("manifest or collected inputs do not match ledger")
        messages = [
            {"role": "system", "content": inputs["system_prompt"].strip()},
            *context,
        ]
        script, model = find_script(study, row.script_id), find_model(study, row.model_id)
        current_turn, pending, last_attempt = 1, None, 0
        invalid = False
        for event in events[1:]:
            if event.event_type == "request_started":
                if invalid or pending or event.turn != current_turn or event.attempt != last_attempt + 1:
                    raise ValueError("request sequence invalid")
                request_messages = [*messages, {"role": "user", "content": script.turns[current_turn - 1]}]
                expected = OpenRouterClient.build_payload(
                    model_id=row.model_id,
                    messages=request_messages,
                    generation=study.design.generation,
                    seed=row.planned_seed if model.supports_seed else None,
                    provider_pin=model.provider_pin,
                )
                if event.payload.get("request_hash") != payload_hash(expected):
                    raise ValueError("request transcript hash mismatch")
                pending, last_attempt = event, event.attempt
            elif event.event_type in {"request_failed", "response_received"}:
                if pending is None or (event.turn, event.attempt) != (pending.turn, pending.attempt):
                    raise ValueError("result does not match request")
                if event.event_type == "response_received":
                    if event.payload.get("request_hash") != pending.payload.get("request_hash"):
                        raise ValueError("response request hash mismatch")
                    if (
                        event.payload.get("requested_model_id") != row.model_id
                        or event.payload.get("resolved_model_id") != row.model_id
                    ):
                        raise ValueError("response model mismatch")
                    messages.extend(
                        [
                            {"role": "user", "content": script.turns[current_turn - 1]},
                            {"role": "assistant", "content": event.payload["text"]},
                        ]
                    )
                    current_turn += 1
                    last_attempt = 0
                    finish = event.payload.get("finish_reason")
                    truncated += finish == "length"
                    invalid_finish += finish not in {"length", "stop"}
                    invalid = finish != "stop"
                    cost = event.payload.get("usage", {}).get("cost")
                    if cost is None:
                        missing_cost += 1
                    elif not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                        raise ValueError("invalid recorded cost")
                    else:
                        costs.append(cost)
                    providers[str(event.payload.get("provider_name"))] += 1
                pending = None
        completed = events[-1].event_type == "run_completed"
        response_count = current_turn - 1
        if completed and (invalid or response_count != row.planned_turns or pending is not None):
            raise ValueError("invalid finish labelled complete")
        summary = {
            "run_id": row.run_id,
            "model_id": row.model_id,
            "status": "completed" if completed else "incomplete",
            "accepted_responses": response_count,
            "planned_responses": row.planned_turns,
            "failure_reason": None if completed else events[-1].payload.get("error_code", "interrupted"),
            "ledger_final_hash": events[-1].event_hash,
        }
        output_rows.append({**summary, "track": track, "scenario_family": row.scenario_family})
    models = []
    for model in inputs["plan"]["models"]:
        values = [row for row in output_rows if row["model_id"] == model]
        models.append(
            {
                "model_id": model,
                "planned_conversations": len(values),
                "completed_conversations": sum(row["status"] == "completed" for row in values),
                "stored_responses": sum(row["accepted_responses"] for row in values),
                "failure_reasons": dict(
                    Counter(row.get("failure_reason") for row in values if row.get("failure_reason"))
                ),
            }
        )
    return {
        "data_origin": "live_exploratory_evidence_snapshot",
        "audited_at_utc": datetime.now(UTC).isoformat(),
        "input_hash": payload_hash(inputs),
        "planned_conversations": len(output_rows),
        "planned_responses": sum(row["planned_responses"] for row in output_rows),
        "completed_conversations": sum(row["status"] == "completed" for row in output_rows),
        "stored_responses": sum(row["accepted_responses"] for row in output_rows),
        "verified_ledgers": len(actual_paths),
        "truncated_responses": truncated,
        "invalid_finish_responses": invalid_finish,
        "responses_missing_recorded_cost": missing_cost,
        "recorded_response_cost_usd": math.fsum(costs),
        "providers": dict(providers),
        "models": models,
        "by_track": {
            track: {
                "planned_responses": sum(
                    row["planned_responses"] for row in output_rows if row["track"] == track
                ),
                "stored_responses": sum(
                    row["accepted_responses"] for row in output_rows if row["track"] == track
                ),
            }
            for track in studies
        },
        "safety_ratings_collected": False,
        "warning": (
            "Snapshot may precede subsequent live responses. Stored outputs include incomplete trajectories; "
            "Neither completion nor technical availability measures clinical safety. "
            "Raw dialogue is not released."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("new output path required")
    report = audit_batch(args.batch_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"models", "providers", "by_track"}}
        )
    )


if __name__ == "__main__":
    main()
