"""Reproducible workload and assumed-variance sensitivity for a reduced exploration."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.power import load_power_plan, simulate_design  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.simulations < 100 or args.output.exists():
        parser.error("at least 100 simulations and a new output path are required")
    baseline = load_power_plan(ROOT / "config/study-v3/power.yaml")
    designs = []
    for name, models, families, repetitions in (
        ("original_six_family", 6, 6, 2),
        ("selected_six_model_core", 6, 10, 1),
        ("six_model_two_samples", 6, 10, 2),
        ("eight_model_one_sample", 8, 10, 1),
        ("unreduced_eight_model_core", 8, 10, 3),
    ):
        for slope_sd in (0.25, 0.50):
            plan = baseline.model_copy(
                update={
                    "version": f"{name}_slope{str(slope_sd).replace('.', '_')}",
                    "models": models,
                    "scenario_families": families,
                    "repetitions": repetitions,
                    "family_random_slope_sd": slope_sd,
                    "simulations": args.simulations,
                }
            )
            result = simulate_design(plan)
            for item in result["results"]:
                probability = item["estimated_detection_probability"]
                item["monte_carlo_standard_error"] = math.sqrt(
                    probability * (1 - probability) / args.simulations
                )
            designs.append(
                {
                    "design": name,
                    "assumptions": plan.model_dump(mode="json"),
                    "core_responses": models * families * 3 * 2 * repetitions * 12,
                    "result": result,
                }
            )
            print(f"finished {plan.version}", flush=True)
    report = {
        "data_origin": "planning_simulation_not_live_results",
        "designs": designs,
        "decision": "six models, ten families, one sample per core cell; narrow long extension",
        "selected_core_conversations": 360,
        "selected_core_responses": 4320,
        "selected_extension_conversations": 36,
        "selected_extension_responses": 864,
        "selected_total_responses": 5184,
        "full_double_rating_hours_at_one_minute_each": 172.8,
        "unreduced_total_responses": 51840,
        "warning": "Binary proxy under assumed variance, not empirical or joint ordinal power. "
        "The ten-family test-resolution advantage depends on an unverified independent-block "
        "assumption. More responses do not substitute for scenario validity or human annotation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
