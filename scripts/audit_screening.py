"""Verify live screening batches and produce a public technical audit, without safety scores."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.contexts import load_context_histories  # noqa: E402
from psychosis_benchmark.design import load_study  # noqa: E402
from psychosis_benchmark.evidence import read_verified_events  # noqa: E402
from psychosis_benchmark.export import export_ledger  # noqa: E402
from psychosis_benchmark.schema import ManifestRow, StudyBundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batches", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--annotation-source", type=Path)
    args = parser.parse_args()
    histories = load_context_histories(ROOT / "config/study-v3/contexts")
    system = (ROOT / "config/study-v3/system_prompt.txt").read_text(encoding="utf-8")
    models = defaultdict(
        lambda: {
            "planned_conversations": 0,
            "completed_conversations": 0,
            "accepted_responses": 0,
            "provider_names": set(),
            "status_counts": Counter(),
            "failure_reasons": Counter(),
            "response_cost_usd_recorded": 0.0,
            "response_costs_missing": 0,
            "truncated_responses": 0,
            "generation_ids": [],
            "ledger_hashes": [],
        }
    )
    annotation = []
    provenance = []
    seen_runs = set()
    for batch in args.batches:
        snapshot = batch / "study_snapshot.json"
        study = (
            StudyBundle.model_validate_json(snapshot.read_text(encoding="utf-8"))
            if snapshot.exists()
            else load_study(ROOT / "config/study-v3")
        )
        report_path = batch / "screening_report.json"
        if not report_path.exists():
            report_path = batch / "pilot_report.json"
        if not report_path.exists():
            raise ValueError(f"batch has not finished: {batch.name}")
        batch_report = json.loads(report_path.read_text(encoding="utf-8"))
        summaries = {row["run_id"]: row for row in batch_report["runs"]}
        with (batch / "manifest.csv").open(encoding="utf-8", newline="") as handle:
            manifest = [ManifestRow.model_validate(value) for value in csv.DictReader(handle)]
        if set(summaries) != {row.run_id for row in manifest}:
            raise ValueError("batch report and manifest differ")
        for row in manifest:
            if row.run_id in seen_runs:
                raise ValueError("overlapping run IDs across batches")
            seen_runs.add(row.run_id)
            item = models[row.model_id]
            item["tier"] = row.model_tier.value
            item["planned_conversations"] += 1
            summary = summaries[row.run_id]
            ledger = batch / "ledgers" / f"{row.run_id}.jsonl"
            if ledger.exists():
                source, verified = export_ledger(
                    ledger, study=study, row=row, histories=histories, system_prompt=system
                )
                if (
                    verified["status"] != summary["status"]
                    or verified["accepted_responses"] != summary["accepted_responses"]
                ):
                    raise ValueError("batch summary disagrees with verified ledger")
                annotation.extend(source)
                item["ledger_hashes"].append(verified["ledger_final_hash"])
                for event in read_verified_events(ledger):
                    if event.event_type == "response_received":
                        item["truncated_responses"] += bool(event.payload.get("truncated"))
                        item["provider_names"].add(event.payload.get("provider_name"))
                        usage = event.payload.get("usage", {})
                        if "cost" in usage:
                            item["response_cost_usd_recorded"] += usage["cost"]
                        else:
                            item["response_costs_missing"] += 1
                        item["generation_ids"].append(event.payload.get("generation_id"))
            item["status_counts"][summary["status"]] += 1
            item["accepted_responses"] += summary["accepted_responses"]
            item["completed_conversations"] += summary["status"] == "completed"
            if summary.get("failure_reason"):
                item["failure_reasons"][summary["failure_reason"]] += 1
        provenance.append(
            {
                "batch": batch.name,
                "data_origin": batch_report["data_origin"],
                "catalogue_errors": batch_report.get("catalogue_errors", []),
            }
        )
    public_models = []
    for model_id, values in sorted(models.items()):
        public_models.append(
            {
                "model_id": model_id,
                **{
                    key: sorted(value, key=str) if isinstance(value, set) else value
                    for key, value in values.items()
                },
            }
        )
    report = {
        "data_origin": (
            "live_technical_screening"
            if all(item["data_origin"] == "live_technical_screening" for item in provenance)
            else "live_exploratory_pilot"
        ),
        "safety_ratings_collected": False,
        "behavioural_rankings_supported": False,
        "planned_models": len(models),
        "models_with_accepted_responses": sum(value["accepted_responses"] > 0 for value in models.values()),
        "paid_models_with_accepted_responses": sum(
            value["accepted_responses"] > 0 and value["tier"] == "low_cost" for value in models.values()
        ),
        "completed_conversations": sum(value["completed_conversations"] for value in models.values()),
        "planned_conversations": sum(value["planned_conversations"] for value in models.values()),
        "accepted_responses": sum(value["accepted_responses"] for value in models.values()),
        "truncated_responses": sum(value["truncated_responses"] for value in models.values()),
        "response_count_note": (
            "Accepted means stored, not clinically validated; includes partial and truncated outputs."
        ),
        "batches": provenance,
        "models": public_models,
        "billing_note": (
            "Recorded costs cover stored responses only. Missing costs and failed requests require "
            "generation-level reconciliation; this report is not a bill."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    if args.annotation_source:
        args.annotation_source.parent.mkdir(parents=True, exist_ok=True)
        with args.annotation_source.open("x", encoding="utf-8") as handle:
            for item in annotation:
                handle.write(item.model_dump_json() + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"models", "batches", "billing_note"}},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
