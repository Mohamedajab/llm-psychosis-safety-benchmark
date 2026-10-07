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
from psychosis_benchmark.evidence import payload_hash  # noqa: E402
from psychosis_benchmark.expansion import load_expanded_study  # noqa: E402
from psychosis_benchmark.export import export_ledger  # noqa: E402
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


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


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
    # OS advisory lock releases on process exit/crash, unlike a stale PID file.
    lock_handle = (args.output_dir / "owner.lock").open("a+b")
    lock_handle.seek(0)
    lock_handle.write(b"0")
    lock_handle.flush()
    lock_handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        parser.error("another process owns this batch")
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
        else:
            summary[row.run_id] = {
                "run_id": row.run_id,
                "model_id": row.model_id,
                "track": track,
                "status": "not_started",
                "accepted_responses": 0,
                "planned_responses": row.planned_turns,
            }
    started_at = datetime.now(UTC).isoformat()

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

    def refresh(row, track):
        _, state = export_ledger(
            args.output_dir / "ledgers" / f"{row.run_id}.jsonl",
            study=studies[track],
            row=row,
            histories=histories,
            system_prompt=inputs["system_prompt"],
        )
        with progress_lock:
            summary[row.run_id] = {**state, "track": track}
        write_progress()

    def run_model(model_id):
        if model_id in blocked:
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
                return
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
                    on_response=lambda r=row, t=track: refresh(r, t),
                    stop_requested=lambda: stop.is_set() or (args.output_dir / "STOP").exists(),
                )
                refresh(row, track)
                print(json.dumps({"model": model_id, "run_id": row.run_id, "status": status}), flush=True)
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
                return
            except Exception:
                # Do not log exception text: transport internals may include credentials.
                stop.set()
                print(
                    json.dumps({"model": model_id, "status": "paused", "reason": "unexpected_error"}),
                    flush=True,
                )
                raise RuntimeError("batch paused; inspect evidence without exposing credentials") from None

    write_progress()
    with ThreadPoolExecutor(max_workers=len(models)) as pool:
        list(pool.map(run_model, models))
    report = write_progress(
        "completed"
        if all(item["status"] == "completed" for item in summary.values())
        else "incomplete_checkpointed"
    )
    print(
        json.dumps({key: value for key, value in report.items() if key not in {"runs", "models"}}), flush=True
    )
    lock_handle.close()
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
