"""Bounded exploratory long-horizon pilot; no safety scores or confirmatory claims."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.catalogue import verify_live_catalogue  # noqa: E402
from psychosis_benchmark.collection import CollectionError, collect_conversation  # noqa: E402
from psychosis_benchmark.contexts import load_context_histories  # noqa: E402
from psychosis_benchmark.costing import estimate_costs  # noqa: E402
from psychosis_benchmark.design import build_manifest, write_manifest  # noqa: E402
from psychosis_benchmark.expansion import load_expanded_study  # noqa: E402
from psychosis_benchmark.export import export_ledger  # noqa: E402
from psychosis_benchmark.provider import OpenRouterClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--families", nargs="+", default=["ai_attachment"])
    parser.add_argument("--horizon", type=int, choices=[12, 24], default=24)
    parser.add_argument("--contexts", nargs="+", default=["no_history"])
    parser.add_argument("--repetitions", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--budget-usd", type=float, default=1.5)
    parser.add_argument("--workers", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--api-key-stdin", action="store_true")
    args = parser.parse_args()
    study = load_expanded_study(ROOT, horizon=args.horizon)
    if len(set(args.models)) != len(args.models) or set(args.models) - {
        model.model_id for model in study.models.models
    }:
        parser.error("choose unique exact models from the expanded roster")
    if set(args.families) - {family.family_id for family in study.scenarios}:
        parser.error("unknown scenario family")
    if set(args.contexts) - {"no_history", "standard_history_24"}:
        parser.error("only authored no-history and 24-message contexts are available")
    study = study.model_copy(
        update={
            "design": study.design.model_copy(
                update={
                    "generation": study.design.generation.model_copy(update={"max_retries": 0}),
                }
            )
        }
    )
    rows = [
        row
        for row in build_manifest(study, "robustness_depth")
        if row.model_id in args.models
        and row.scenario_family in args.families
        and row.context_condition in args.contexts
        and row.repetition <= args.repetitions
    ]
    costs = estimate_costs(rows, study.models, study.design.generation.max_output_tokens)
    ceiling = sum(
        (cost.prompt_tokens * 0.10 + cost.completion_tokens * 0.40) / 1_000_000
        for cost in costs
        if not cost.model_id.endswith(":free")
    )
    if not rows or ceiling > args.budget_usd or args.budget_usd < 0:
        parser.error(f"empty design or price-capped planning ceiling ${ceiling:.4f} exceeds budget")
    preview = {
        "data_origin": "live_exploratory_pilot" if args.live else "planned_only",
        "models": len(args.models),
        "families": len(args.families),
        "horizon": args.horizon,
        "planned_conversations": len(rows),
        "planned_responses": sum(row.planned_turns for row in rows),
        "price_capped_planning_ceiling_usd": ceiling,
        "safety_ratings_collected": False,
    }
    print(json.dumps(preview), flush=True)
    if not args.live:
        return 0
    if args.output_dir.exists():
        parser.error("use a new output directory; evidence is immutable")
    api_key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        parser.error("API key required via environment or stdin")
    with urllib.request.urlopen(study.models.catalogue_endpoint, timeout=30) as response:
        catalogue = json.load(response)
    selected_panel = study.models.model_copy(
        update={"models": tuple(model for model in study.models.models if model.model_id in args.models)}
    )
    errors = verify_live_catalogue(selected_panel, catalogue)
    unavailable = {model for model in args.models if any(error.startswith(model + ":") for error in errors)}
    args.output_dir.mkdir(parents=True)
    write_manifest(rows, args.output_dir / "manifest.csv")
    (args.output_dir / "study_snapshot.json").write_text(
        study.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "catalogue.json").write_text(
        json.dumps({"data": [item for item in catalogue["data"] if item["id"] in args.models]}, indent=2),
        encoding="utf-8",
    )
    histories = load_context_histories(ROOT / "config/study-v3/contexts")
    system = (ROOT / "config/study-v3/system_prompt.txt").read_text(encoding="utf-8")

    def run_model(model_id):
        summaries = []
        disabled = model_id in unavailable
        for row in sorted(
            (item for item in rows if item.model_id == model_id), key=lambda item: item.execution_order
        ):
            if disabled:
                summaries.append(
                    {
                        "run_id": row.run_id,
                        "model_id": model_id,
                        "status": "not_called_catalogue_changed"
                        if model_id in unavailable
                        else "not_called_after_endpoint_failure",
                        "accepted_responses": 0,
                        "planned_responses": row.planned_turns,
                    }
                )
                continue
            ledger = args.output_dir / "ledgers" / f"{row.run_id}.jsonl"
            try:
                collect_conversation(
                    study=study,
                    row=row,
                    histories=histories,
                    system_prompt=system,
                    client=OpenRouterClient(api_key),
                    ledger_path=ledger,
                )
            except CollectionError:
                pass
            _, summary = export_ledger(
                ledger, study=study, row=row, histories=histories, system_prompt=system
            )
            disabled = summary["status"] != "completed"
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
        return summaries

    summaries = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(run_model, model) for model in args.models]):
            summaries.extend(future.result())
    report = {
        **preview,
        "completed_conversations": sum(item["status"] == "completed" for item in summaries),
        "accepted_responses": sum(item["accepted_responses"] for item in summaries),
        "catalogue_errors": errors,
        "runs": sorted(summaries, key=lambda item: item["run_id"]),
    }
    (args.output_dir / "pilot_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "runs"}), flush=True)
    return 0 if report["completed_conversations"] == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
