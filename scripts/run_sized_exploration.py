"""Collect the specified smaller exploration; snapshot first, checkpoint, never overwrite evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.batch import BatchPaused, SpendingBudget, checkpoint_conversation  # noqa: E402
from psychosis_benchmark.catalogue import verify_live_catalogue  # noqa: E402
from psychosis_benchmark.contexts import ContextHistory, load_context_histories  # noqa: E402
from psychosis_benchmark.design import build_manifest  # noqa: E402
from psychosis_benchmark.evidence import payload_hash, read_verified_events  # noqa: E402
from psychosis_benchmark.expansion import load_expanded_study  # noqa: E402
from psychosis_benchmark.export import export_ledger  # noqa: E402
from psychosis_benchmark.live_control import BatchLock, RuntimeMonitor, atomic_json  # noqa: E402
from psychosis_benchmark.provider import OpenRouterClient  # noqa: E402
from psychosis_benchmark.schema import ManifestRow, StudyBundle  # noqa: E402


def prepare_inputs():
    plan = yaml.safe_load(
        (ROOT / "config/research-expansion/sized-exploration.yaml").read_text(encoding="utf-8")
    )
    studies, rows = {}, []
    for track, horizon in (("core", 12), ("long_extension", 24)):
        study = load_expanded_study(ROOT, horizon=horizon)
        study = study.model_copy(
            update={
                "design": study.design.model_copy(
                    update={
                        "protocol_version": f"study-v3.2.0-sized-exploratory-h{horizon}",
                        "generation": study.design.generation.model_copy(update={"max_output_tokens": 4096}),
                    }
                )
            }
        )
        studies[track] = study.model_dump(mode="json")
        spec = plan[track]
        selected = [
            row
            for row in build_manifest(study, "robustness_depth")
            if row.model_id in plan["models"]
            and row.repetition in spec["repetitions"]
            and row.context_condition in spec["contexts"]
            and row.presentation.value in spec["presentations"]
            and (spec["families"] == "all_ten" or row.scenario_family in spec["families"])
        ]
        rows.extend({"track": track, "row": row.model_dump(mode="json")} for row in selected)
    return {
        "plan": plan,
        "studies": studies,
        "rows": rows,
        "system_prompt": (ROOT / "config/study-v3/system_prompt.txt").read_text(encoding="utf-8"),
        "histories": {
            key: value.model_dump(mode="json")
            for key, value in load_context_histories(ROOT / "config/study-v3/contexts").items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--api-key-stdin", action="store_true")
    parser.add_argument("--budget-usd", type=float, default=5.0)
    args = parser.parse_args()
    if args.output_dir.exists() and not args.resume:
        parser.error("new output directory required; use --resume to continue exact recorded inputs")
    if args.resume:
        inputs = json.loads((args.output_dir / "inputs.json").read_text(encoding="utf-8"))
        recorded_hash = (args.output_dir / "input_hash.txt").read_text(encoding="utf-8").strip()
        if payload_hash(inputs) != recorded_hash:
            parser.error("recorded collection inputs were altered")
    else:
        inputs = prepare_inputs()
    input_hash = payload_hash(inputs)
    expected_conversations = len(inputs["rows"])
    expected_responses = sum(item["row"]["planned_turns"] for item in inputs["rows"])
    preview = {
        "planned_conversations": expected_conversations,
        "planned_responses": expected_responses,
        "input_hash": input_hash,
        "budget_usd": args.budget_usd,
        "data_origin": "live_exploratory" if args.live else "planned_only",
    }
    print(json.dumps(preview), flush=True)
    if not args.live:
        return 0
    api_key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        parser.error("provide key through stdin or environment, never a command-line argument")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    owner = BatchLock(args.output_dir / "owner.lock")
    if not owner.acquire():
        parser.error("another process owns this batch")
    runtime = None
    try:
        runtime = RuntimeMonitor(args.output_dir, inputs["plan"]["models"])
        return collect(args, inputs, preview, api_key, runtime)
    except Exception as error:
        # Exception text/tracebacks can contain secrets or generated content.
        if runtime:
            runtime.set_state("failed", error_type=type(error).__name__, error_operation="collection")
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}), flush=True)
        return 1
    finally:
        try:
            if runtime:
                runtime.close()
        finally:
            owner.close()


def collect(args, inputs, preview, api_key, runtime):
    input_hash = preview["input_hash"]
    if not args.resume:
        atomic_json(args.output_dir / "inputs.json", inputs)
        (args.output_dir / "input_hash.txt").write_text(input_hash + "\n", encoding="utf-8")
    studies = {key: StudyBundle.model_validate(value) for key, value in inputs["studies"].items()}
    histories = {key: ContextHistory.model_validate(value) for key, value in inputs["histories"].items()}
    rows = [(item["track"], ManifestRow.model_validate(item["row"])) for item in inputs["rows"]]
    models = inputs["plan"]["models"]
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalogue = json.load(response)
    panel = studies["core"].models
    panel = panel.model_copy(
        update={"models": tuple(model for model in panel.models if model.model_id in models)}
    )
    catalogue_errors = verify_live_catalogue(panel, catalogue)
    blocked = {model for model in models if any(error.startswith(model + ":") for error in catalogue_errors)}
    atomic_json(
        args.output_dir / ("catalogue_resume.json" if args.resume else "catalogue.json"),
        {
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "data": [item for item in catalogue["data"] if item["id"] in models],
            "errors": catalogue_errors,
        },
    )
    budget = SpendingBudget(args.output_dir / "budget.sqlite3", args.budget_usd)
    progress_lock = threading.Lock()
    stop = threading.Event()
    summary = {}
    last_response_at = None
    for track, row in rows:
        ledger = args.output_dir / "ledgers" / f"{row.run_id}.jsonl"
        if ledger.exists():
            _, state = export_ledger(
                ledger,
                study=studies[track],
                row=row,
                histories=histories,
                system_prompt=inputs["system_prompt"],
            )
            state["track"] = track
            summary[row.run_id] = state
            recorded_events = read_verified_events(ledger)
            state["terminal"] = recorded_events[-1].event_type in {"run_completed", "run_failed"}
            response_times = [
                event.occurred_at_utc for event in recorded_events if event.event_type == "response_received"
            ]
            if response_times:
                last_response_at = max(last_response_at or "", max(response_times))
        else:
            summary[row.run_id] = {
                "run_id": row.run_id,
                "model_id": row.model_id,
                "track": track,
                "status": "not_started",
                "accepted_responses": 0,
                "planned_responses": row.planned_turns,
            }
    previous_progress = args.output_dir / "progress.json"
    previous = json.loads(previous_progress.read_text(encoding="utf-8")) if previous_progress.exists() else {}
    resumed_at = datetime.now(UTC).isoformat()
    started_at = previous.get("started_at_utc", resumed_at)
    worker_errors = {}

    def write_progress(status="collecting"):
        with progress_lock:
            model_summary = []
            for model in models:
                values = [item for item in summary.values() if item["model_id"] == model]
                model_summary.append(
                    {
                        "model_id": model,
                        "planned_conversations": len(values),
                        "completed_conversations": sum(item["status"] == "completed" for item in values),
                        "stored_responses": sum(item["accepted_responses"] for item in values),
                    }
                )
            report = {
                **preview,
                "status": status,
                "started_at_utc": started_at,
                "last_resumed_at_utc": resumed_at if args.resume else None,
                "last_response_at_utc": last_response_at,
                "updated_at_utc": datetime.now(UTC).isoformat(),
                "completed_conversations": sum(item["status"] == "completed" for item in summary.values()),
                "stored_responses": sum(item["accepted_responses"] for item in summary.values()),
                "budget": budget.snapshot(),
                "models": model_summary,
                "catalogue_errors": catalogue_errors,
                "safety_ratings_collected": False,
                "runs": list(summary.values()),
            }
            atomic_json(args.output_dir / "progress.json", report)
            return report

    def refresh(row, track, response_received=False):
        nonlocal last_response_at
        _, state = export_ledger(
            args.output_dir / "ledgers" / f"{row.run_id}.jsonl",
            study=studies[track],
            row=row,
            histories=histories,
            system_prompt=inputs["system_prompt"],
        )
        with progress_lock:
            state["terminal"] = read_verified_events(args.output_dir / "ledgers" / f"{row.run_id}.jsonl")[
                -1
            ].event_type in {"run_completed", "run_failed"}
            summary[row.run_id] = {**state, "track": track}
            if response_received:
                last_response_at = datetime.now(UTC).isoformat()
        runtime.worker(
            row.model_id,
            run_id=row.run_id,
            accepted_responses=state["accepted_responses"],
            planned_responses=row.planned_turns,
        )
        if response_received:
            runtime.worker(row.model_id, last_response_at_utc=last_response_at, state="collecting")
        write_progress()

    def run_model(model_id):
        if model_id in blocked:
            runtime.worker(model_id, state="catalogue_blocked", reason="catalogue_drift")
            with progress_lock:
                for item in summary.values():
                    if item["model_id"] == model_id and item["status"] == "not_started":
                        item.update(status="not_called_catalogue_changed", failure_reason="catalogue_drift")
            write_progress()
            return
        client = OpenRouterClient(api_key)
        ordered = sorted(
            ((track, row) for track, row in rows if row.model_id == model_id),
            key=lambda item: (item[0] != "core", item[1].execution_order),
        )
        for track, row in ordered:
            if stop.is_set() or (args.output_dir / "STOP").exists():
                runtime.worker(model_id, state="paused", reason="operator_checkpoint")
                return
            # Never reopen or replace an accepted terminal conversation.
            if summary[row.run_id].get("terminal"):
                continue
            runtime.worker(model_id, state="collecting", run_id=row.run_id, track=track)
            try:
                status = checkpoint_conversation(
                    study=studies[track],
                    row=row,
                    histories=histories,
                    system_prompt=inputs["system_prompt"],
                    client=client,
                    ledger=args.output_dir / "ledgers" / f"{row.run_id}.jsonl",
                    budget=budget,
                    attempts_per_session=inputs["plan"]["generation"]["max_attempts_per_turn_per_session"],
                    interval_seconds=inputs["plan"]["generation"]["minimum_request_interval_seconds"],
                    on_response=lambda r=row, t=track: refresh(r, t, response_received=True),
                    on_activity=lambda fields, m=model_id: runtime.worker(m, **fields),
                    stop_requested=lambda: stop.is_set() or (args.output_dir / "STOP").exists(),
                )
                refresh(row, track)
                print(json.dumps({"model": model_id, "run_id": row.run_id, "status": status}), flush=True)
                runtime.worker(model_id, state=status, reason=summary[row.run_id].get("failure_reason"))
                if status == "failed" and summary[row.run_id].get("failure_reason") in {
                    "http_401",
                    "http_402",
                    "http_403",
                    "http_404",
                    "resolved_model_mismatch",
                }:
                    return
            except BatchPaused as error:
                refresh(row, track)
                if str(error) in {"local_spending_cap", "cost_missing_or_exceeds_reservation"}:
                    stop.set()
                print(json.dumps({"model": model_id, "status": "paused", "reason": str(error)}), flush=True)
                runtime.worker(model_id, state="paused", reason=str(error))
                return
            except Exception as error:
                # Do not log exception text: transport internals may include credentials.
                stop.set()
                worker_errors[model_id] = type(error).__name__
                runtime.set_state("pausing", error_type=type(error).__name__, error_operation="worker")
                runtime.worker(model_id, state="paused_error", error_type=type(error).__name__)
                print(
                    json.dumps(
                        {
                            "model": model_id,
                            "status": "paused",
                            "reason": "unexpected_error",
                            "error_type": type(error).__name__,
                        }
                    ),
                    flush=True,
                )
                return
        runtime.worker(model_id, state="finished")

    runtime.set_state("running")
    write_progress()
    with ThreadPoolExecutor(max_workers=len(models)) as pool:
        list(pool.map(run_model, models))
    status = (
        "paused_error"
        if worker_errors
        else (
            "completed"
            if all(item["status"] == "completed" for item in summary.values())
            else "finished_with_failures"
            if all(item.get("terminal") for item in summary.values())
            else "incomplete_checkpointed"
        )
    )
    report = write_progress(status)
    runtime.set_state(
        report["status"], finished_at_utc=datetime.now(UTC).isoformat(), worker_errors=worker_errors
    )
    print(
        json.dumps({key: value for key, value in report.items() if key not in {"runs", "models"}}), flush=True
    )
    return 0 if report["status"] == "completed" else 1 if worker_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
