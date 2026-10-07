"""Compare draft designs under the same assumptions; never certify study power."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.power import load_power_plan, simulate_design  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=250)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/design_sensitivity.json")
    args = parser.parse_args()
    if args.simulations < 100:
        parser.error("at least 100 planning simulations required")
    if args.output.exists():
        parser.error("output exists; use a new path to preserve the prior plan")
    baseline = load_power_plan(ROOT / "config/study-v3/power.yaml")
    comparisons = []
    full = []
    for name, models, families, repetitions, turns in (
        ("original_draft", 6, 6, 2, 12),
        ("extra_turns_only", 6, 6, 2, 24),
        ("broader_core", 8, 10, 3, 12),
        ("long_horizon_exploratory", 8, 10, 3, 24),
    ):
        plan = baseline.model_copy(
            update={
                "version": name,
                "models": models,
                "scenario_families": families,
                "repetitions": repetitions,
                "turns_per_conversation": turns,
                "simulations": args.simulations,
            }
        )
        result = simulate_design(plan)
        full.append({"design": name, "assumptions": plan.model_dump(mode="json"), "result": result})
        for item in result["results"]:
            probability = item["estimated_detection_probability"]
            comparisons.append(
                {
                    "design": name,
                    "models": models,
                    "families": families,
                    "repetitions": repetitions,
                    "turns": turns,
                    "effect_log_odds": item["contrast_log_odds"],
                    "detection_probability": probability,
                    "monte_carlo_standard_error": math.sqrt(
                        probability * (1 - probability) / args.simulations
                    ),
                    "minimum_two_sided_p": result["minimum_two_sided_p"],
                }
            )
        print(f"completed {name}: {args.simulations} simulations per effect", flush=True)
    report = {
        "data_origin": "planning_simulation",
        "comparison": comparisons,
        "designs": full,
        "warning": (
            "Binary proxy, assumed variance, first Holm hurdle only. Monte Carlo error is not effect "
            "uncertainty. No design is approved or proven powered; more turns cannot fix six-block "
            "test resolution."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
