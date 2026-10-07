"""Preview or run a bounded technical screen of exact free and low-cost endpoints."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.catalogue import verify_live_catalogue  # noqa: E402
from psychosis_benchmark.collection import CollectionError, collect_conversation  # noqa: E402
from psychosis_benchmark.contexts import load_context_histories  # noqa: E402
from psychosis_benchmark.costing import estimate_costs  # noqa: E402
from psychosis_benchmark.design import build_manifest, load_study, write_manifest  # noqa: E402
from psychosis_benchmark.export import export_ledger  # noqa: E402
from psychosis_benchmark.provider import OpenRouterClient  # noqa: E402
from psychosis_benchmark.schema import ModelPanel, ModelSpec  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--api-key-stdin", action="store_true")
    parser.add_argument("--max-conversations", type=int, default=6)
    parser.add_argument("--tier", choices=["free", "low_cost", "all"], default="all")
    parser.add_argument("--budget-usd", type=float, default=1.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model-extension", type=Path)
    parser.add_argument("--extension-only", action="store_true")
    parser.add_argument("--max-retries", type=int, choices=range(0, 4))
    args = parser.parse_args()
    if args.max_conversations < 1:
        parser.error("max-conversations must be positive")
    study = load_study(ROOT / "config" / "study-v3")
    extension_ids: set[str] = set()
    if args.model_extension:
        extension = yaml.safe_load(args.model_extension.read_text(encoding="utf-8"))
        additions = tuple(ModelSpec.model_validate(value) for value in extension["models"])
        panel = ModelPanel.model_validate(
            {
                **study.models.model_dump(mode="json"),
                "models": [model.model_dump(mode="json") for model in (*study.models.models, *additions)],
            }
        )
        study = study.model_copy(update={"models": panel})
        extension_ids = {model.model_id for model in additions}
    elif args.extension_only:
        parser.error("extension-only requires model-extension")
    if args.max_retries is not None:
        generation = study.design.generation.model_copy(update={"max_retries": args.max_retries})
        study = study.model_copy(
            update={"design": study.design.model_copy(update={"generation": generation})}
        )
    selected_models = [
        model
        for model in study.models.models
        if (args.tier == "all" or model.tier.value == args.tier)
        and (not args.extension_only or model.model_id in extension_ids)
    ]
    # Round-robin by scenario so the first pilot gives every endpoint a chance.
    all_rows = build_manifest(study, "screening")
    candidates = []
    for family in sorted({row.scenario_family for row in all_rows}):
        candidates.extend(
            row
            for model in selected_models
            for row in all_rows
            if row.scenario_family == family and row.model_id == model.model_id
        )
    planned = candidates[: args.max_conversations]
    estimates = estimate_costs(planned, study.models, study.design.generation.max_output_tokens)
    router_ceiling = sum(
        (item.prompt_tokens * 0.10 + item.completion_tokens * 0.40) / 1_000_000
        for item in estimates
        if not item.model_id.endswith(":free")
    )
    retry_ceiling = router_ceiling * (study.design.generation.max_retries + 1)
    if retry_ceiling > args.budget_usd or args.budget_usd < 0:
        parser.error(f"planned retry ceiling {retry_ceiling:.4f} exceeds budget")
    print(
        json.dumps(
            {
                "mode": "live" if args.live else "preview",
                "tier": args.tier,
                "conversations": len(planned),
                "responses": sum(row.planned_turns for row in planned),
                "budget_usd": args.budget_usd,
                "catalogue_retry_ceiling_usd": retry_ceiling,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if not args.live:
        return 0
    api_key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        parser.error("OPENROUTER_API_KEY or --api-key-stdin is required")
    # Refuse changed/paid metadata before sending any generation request.
    request = urllib.request.Request(
        study.models.catalogue_endpoint, headers={"User-Agent": "psychosis-safety-benchmark/3.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        catalogue = json.load(response)
    selected_ids = {row.model_id for row in planned}
    selected_panel = study.models.model_copy(
        update={"models": tuple(model for model in selected_models if model.model_id in selected_ids)}
    )
    errors = verify_live_catalogue(selected_panel, catalogue)
    unavailable_models = {
        model.model_id
        for model in selected_models
        if any(error.startswith(f"{model.model_id}:") for error in errors)
    }
    if errors:
        print(
            json.dumps(
                {"catalogue_errors": errors, "policy": "skip_changed_endpoints_without_substitution"},
                indent=2,
            ),
            flush=True,
        )
    if args.output_dir.exists() and not args.resume:
        parser.error("output directory already exists; use --resume to skip terminal ledgers")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = args.output_dir / "catalogue.json"
    if not snapshot.exists():
        (args.output_dir / "study_snapshot.json").write_text(
            study.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        selected_rows = [row for row in catalogue["data"] if row.get("id") in selected_ids]
        snapshot.write_text(
            json.dumps({"checked_at_utc": datetime.now(UTC).isoformat(), "data": selected_rows}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        write_manifest(planned, args.output_dir / "manifest.csv")
    histories = load_context_histories(ROOT / "config" / "study-v3" / "contexts")
    system_prompt = (ROOT / "config" / "study-v3" / "system_prompt.txt").read_text(encoding="utf-8")
    client = OpenRouterClient(api_key)
    summaries = []
    disabled_models: set[str] = set()
    for row in planned:
        ledger = args.output_dir / "ledgers" / f"{row.run_id}.jsonl"
        if not ledger.exists() and row.model_id not in disabled_models | unavailable_models:
            try:
                collect_conversation(
                    study=study,
                    row=row,
                    histories=histories,
                    system_prompt=system_prompt,
                    client=client,
                    ledger_path=ledger,
                )
            except CollectionError:
                pass  # The reason is in the immutable ledger, never in provider error text.
        if ledger.exists():
            _, summary = export_ledger(
                ledger, study=study, row=row, histories=histories, system_prompt=system_prompt
            )
            summaries.append(summary)
            if summary["status"] != "completed":
                disabled_models.add(row.model_id)
        else:
            summaries.append(
                {
                    "run_id": row.run_id,
                    "model_id": row.model_id,
                    "status": "not_called_catalogue_changed"
                    if row.model_id in unavailable_models
                    else "not_called_after_endpoint_failure",
                    "accepted_responses": 0,
                    "planned_responses": row.planned_turns,
                }
            )
        print(json.dumps(summaries[-1], sort_keys=True), flush=True)
    result = {
        "data_origin": "live_technical_screening",
        "safety_ratings": "not_collected",
        "completed_conversations": sum(item["status"] == "completed" for item in summaries),
        "planned_conversations": len(planned),
        "accepted_responses": sum(item["accepted_responses"] for item in summaries),
        "catalogue_errors": errors,
        "tier": args.tier,
        "budget_usd": args.budget_usd,
        "catalogue_retry_ceiling_usd": retry_ceiling,
        "runs": summaries,
    }
    (args.output_dir / "screening_report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({key: value for key, value in result.items() if key != "runs"}, sort_keys=True), flush=True
    )
    return 0 if result["completed_conversations"] == len(planned) else 2


if __name__ == "__main__":
    raise SystemExit(main())
