"""Single-conversation collection with immutable evidence recording."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from psychosis_benchmark.contexts import ContextHistory, messages_for_condition
from psychosis_benchmark.design import canonical_hash
from psychosis_benchmark.evidence import append_event, payload_hash
from psychosis_benchmark.provider import OpenRouterClient, ProviderCallError
from psychosis_benchmark.schema import ManifestRow, ModelSpec, Script, StudyBundle


class CollectionError(RuntimeError):
    """A run cannot start or cannot complete under the frozen policy."""


def find_script(study: StudyBundle, script_id: str) -> Script:
    for family in study.scenarios:
        candidates = (family.screening_script, *family.variants.values())
        for script in candidates:
            if script.script_id == script_id:
                return script
    raise CollectionError(f"manifest references unknown script: {script_id}")


def find_model(study: StudyBundle, model_id: str) -> ModelSpec:
    for model in study.models.models:
        if model.model_id == model_id:
            return model
    raise CollectionError(f"manifest references unknown model: {model_id}")


def first_request_preview(
    *,
    study: StudyBundle,
    row: ManifestRow,
    histories: dict[str, ContextHistory],
    system_prompt: str,
) -> dict[str, object]:
    script = find_script(study, row.script_id)
    model = find_model(study, row.model_id)
    messages = [{"role": "system", "content": system_prompt.strip()}]
    messages.extend(messages_for_condition(study, row.context_condition, histories))
    messages.append({"role": "user", "content": script.turns[0]})
    seed = row.planned_seed if model.supports_seed else None
    payload = OpenRouterClient.build_payload(
        model_id=model.model_id,
        messages=messages,
        generation=study.design.generation,
        seed=seed,
        provider_pin=model.provider_pin,
    )
    return {
        "run_id": row.run_id,
        "script_id": script.script_id,
        "model_id": model.model_id,
        "context_condition": row.context_condition,
        "planned_turns": len(script.turns),
        "message_count_first_request": len(messages),
        "first_request_hash": payload_hash(payload),
        "provider_pin": model.provider_pin,
    }


def collect_conversation(
    *,
    study: StudyBundle,
    row: ManifestRow,
    histories: dict[str, ContextHistory],
    system_prompt: str,
    client: OpenRouterClient,
    ledger_path: str | Path,
    sleep: Callable[[float], None] = time.sleep,
    frozen_bundle_path: str | Path | None = None,
) -> Path:
    ledger = Path(ledger_path)
    if ledger.exists():
        raise CollectionError("ledger already exists; collected runs are immutable")
    script = find_script(study, row.script_id)
    model = find_model(study, row.model_id)
    if row.stage == "confirmatory":
        if study.design.status != "frozen_pre_collection":
            raise CollectionError("confirmatory collection requires a frozen protocol")
        if not model.eligible_for_confirmatory or not model.provider_pin:
            raise CollectionError("confirmatory collection requires an eligible provider-pinned model")
        if frozen_bundle_path is None:
            raise CollectionError("confirmatory collection requires a verified frozen bundle")
        from psychosis_benchmark.protocol import ProtocolFreezeError, verify_frozen_bundle

        try:
            verify_frozen_bundle(Path(__file__).resolve().parents[2], frozen_bundle_path)
        except (OSError, ValueError, ProtocolFreezeError) as error:
            raise CollectionError("frozen protocol verification failed") from error
    messages = [{"role": "system", "content": system_prompt.strip()}]
    messages.extend(messages_for_condition(study, row.context_condition, histories))
    append_event(
        ledger,
        event_type="run_started",
        run_id=row.run_id,
        payload={
            "manifest_row": row.model_dump(mode="json"),
            "study_hash": canonical_hash(study),
            "system_prompt_hash": payload_hash({"system_prompt": system_prompt.strip()}),
        },
    )
    completed_turns = 0
    for turn_number, user_text in enumerate(script.turns, start=1):
        messages.append({"role": "user", "content": user_text})
        seed = row.planned_seed if model.supports_seed else None
        payload = client.build_payload(
            model_id=model.model_id,
            messages=messages,
            generation=study.design.generation,
            seed=seed,
            provider_pin=model.provider_pin,
        )
        result = None
        last_error: ProviderCallError | None = None
        for attempt in range(1, study.design.generation.max_retries + 2):
            append_event(
                ledger,
                event_type="request_started",
                run_id=row.run_id,
                turn=turn_number,
                attempt=attempt,
                payload={
                    "request_hash": payload_hash(payload),
                    "message_count": len(messages),
                    "provider_pin": model.provider_pin,
                },
            )
            try:
                result = client.complete_once(
                    model_id=model.model_id,
                    messages=messages,
                    generation=study.design.generation,
                    seed=seed,
                    provider_pin=model.provider_pin,
                )
                break
            except ProviderCallError as error:
                last_error = error
                append_event(
                    ledger,
                    event_type="request_failed",
                    run_id=row.run_id,
                    turn=turn_number,
                    attempt=attempt,
                    payload={
                        "error_code": error.code,
                        "http_status": error.status_code,
                        "retryable": error.retryable,
                    },
                )
                if not error.retryable or attempt > study.design.generation.max_retries:
                    break
                sleep(min(30.0, 2 ** (attempt - 1)))
        if result is None:
            append_event(
                ledger,
                event_type="run_failed",
                run_id=row.run_id,
                payload={
                    "completed_turns": completed_turns,
                    "failed_turn": turn_number,
                    "error_code": last_error.code if last_error else "unknown",
                },
            )
            raise CollectionError(f"run failed at turn {turn_number}")
        append_event(
            ledger,
            event_type="response_received",
            run_id=row.run_id,
            turn=turn_number,
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
        messages.append({"role": "assistant", "content": result.text})
        completed_turns += 1
        if result.truncated:
            append_event(
                ledger,
                event_type="run_failed",
                run_id=row.run_id,
                payload={
                    "completed_turns": completed_turns,
                    "failed_turn": turn_number,
                    "error_code": "truncated_response",
                },
            )
            raise CollectionError(f"run truncated at turn {turn_number}")
    append_event(
        ledger,
        event_type="run_completed",
        run_id=row.run_id,
        payload={"completed_turns": completed_turns},
    )
    return ledger
