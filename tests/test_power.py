from __future__ import annotations

from pathlib import Path

from psychosis_benchmark.power import PowerPlan, load_power_plan, simulate_design

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "study-v3" / "power.yaml"


def test_registered_power_plan_has_conversation_clusters() -> None:
    plan = load_power_plan(PLAN)
    assert plan.models == 6
    assert plan.turns_per_conversation == 12
    assert plan.simulations >= 1000


def test_simulation_is_deterministic_and_bounded() -> None:
    plan = PowerPlan(
        version="test",
        status="test",
        seed=11,
        simulations=100,
        alpha_familywise=0.05,
        planned_primary_contrasts=3,
        models=3,
        scenario_families=3,
        contexts=1,
        repetitions=1,
        turns_per_conversation=6,
        baseline_event_probability=0.2,
        contrast_log_odds=(0.2, 0.8),
        model_random_effect_sd=0.2,
        family_random_effect_sd=0.2,
        conversation_random_effect_sd=0.3,
    )
    first = simulate_design(plan)
    second = simulate_design(plan)
    assert first == second
    probabilities = [row["estimated_detection_probability"] for row in first["results"]]
    assert all(0 <= probability <= 1 for probability in probabilities)
    assert probabilities[1] >= probabilities[0]
