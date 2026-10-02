"""Command-line tools for the prospective Study V3 design."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.analysis_plan import load_analysis_plan  # noqa: E402
from psychosis_benchmark.costing import estimate_costs  # noqa: E402
from psychosis_benchmark.design import (  # noqa: E402
    StudyConfigurationError,
    build_manifest,
    canonical_hash,
    load_study,
    validate_study,
    write_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=ROOT / "config" / "study-v3")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate configs without calling a model API")
    manifest = subparsers.add_parser("manifest", help="write a deterministic planned manifest")
    manifest.add_argument("--profile", required=True)
    manifest.add_argument("--output", type=Path, required=True)
    cost = subparsers.add_parser("estimate-cost", help="estimate token and catalogue price ceilings")
    cost.add_argument("--profile", required=True)
    subparsers.add_parser("readiness", help="show why confirmatory collection is blocked")
    return parser


def _load(args: argparse.Namespace):
    return load_study(args.config_root)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        study = _load(args)
        report = validate_study(study)
        if args.command == "validate":
            analysis_plan = load_analysis_plan(args.config_root / "analysis_plan.yaml")
            print(f"study hash: {canonical_hash(study)}")
            print(f"analysis plan: {analysis_plan.plan_version} ({analysis_plan.status})")
            print(f"scenario families: {len(study.scenarios)}")
            print(f"screening models: {len(study.models.models)}")
            for warning in report.warnings:
                print(f"WARNING: {warning}")
            for error in report.errors:
                print(f"ERROR: {error}")
            return 0 if report.ok else 1
        if args.command == "readiness":
            blockers = list(report.errors) + list(report.warnings)
            if blockers:
                print("CONFIRMATORY COLLECTION BLOCKED")
                for blocker in blockers:
                    print(f"- {blocker}")
                return 2
            print("Configuration checks pass; external ethics and reviewer evidence still apply.")
            return 0
        rows = build_manifest(study, args.profile)
        if args.command == "manifest":
            path = write_manifest(rows, args.output)
            print(f"wrote {len(rows)} conversations to {path}")
            print(f"planned responses: {sum(row.planned_turns for row in rows)}")
            return 0
        if args.command == "estimate-cost":
            estimates = estimate_costs(rows, study.models, study.design.generation.max_output_tokens)
            total = 0.0
            print("model\tconversations\tresponses\tprompt_tokens\tcompletion_tokens\tceiling_usd")
            for estimate in estimates:
                total += estimate.total_cost_usd
                print(
                    f"{estimate.model_id}\t{estimate.conversations}\t"
                    f"{estimate.planned_responses}\t{estimate.prompt_tokens}\t"
                    f"{estimate.completion_tokens}\t{estimate.total_cost_usd:.4f}"
                )
            print(f"TOTAL\t\t\t\t\t{total:.4f}")
            return 0
    except (StudyConfigurationError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
