from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from psychosis_benchmark.analysis import AnalysisRow, analyse, trajectory_summary
from psychosis_benchmark.analysis_plan import load_analysis_plan
from psychosis_benchmark.schema import ManifestRow, Presentation, Tier
from psychosis_benchmark.statistics import crossed_bootstrap_interval

ROOT = Path(__file__).resolve().parents[1]


def _data(repetitions: int = 1):
    manifest, rows = [], []
    for model, family, presentation, repetition in itertools.product(
        ("m1", "m2"),
        range(6),
        ("control", "ambiguous", "fixed_belief"),
        range(1, repetitions + 1),
    ):
        run = f"{model}-{family}-{presentation}-{repetition}"
        factors = dict(
            run_id=run,
            model_id=model,
            scenario_family=f"family_{family}",
            context_condition="no_history",
            repetition=repetition,
        )
        manifest.append(
            ManifestRow(
                **factors,
                protocol_version="test",
                stage="development",
                script_id=f"{family}_{presentation}",
                presentation=Presentation(presentation),
                model_tier=Tier.FREE,
                prior_message_count=0,
                planned_turns=12,
                planned_seed=1,
                execution_order=len(manifest) + 1,
            )
        )
        for turn in range(1, 13):
            rows.append(
                AnalysisRow(
                    **factors,
                    item_id=f"{run}-{turn}",
                    turn=turn,
                    presentation=presentation,
                    provenance="synthetic_fixture",
                    status="scored",
                    P1=2 if presentation == "fixed_belief" else 0,
                    P2=2 if presentation == "fixed_belief" else 0,
                    P3=2 if presentation == "fixed_belief" else 1,
                    P4=1 if presentation == "ambiguous" else 0,
                    P5=0,
                )
            )
    return manifest, rows


def _plan():
    plan = load_analysis_plan(ROOT / "config/study-v3/analysis_plan.yaml")
    return plan.model_copy(
        update={"uncertainty": plan.uncertainty.model_copy(update={"bootstrap_simulations": 1000})}
    )


def test_known_effects_and_correct_six_block_holm_resolution():
    manifest, rows = _data()
    report = analyse(manifest, rows, _plan(), allow_synthetic=True)
    assert [outcome["estimate"] for outcome in report["outcomes"]] == [2.0, 2.0, 1.0, 1.0]
    assert all(outcome["p_value"] == 0.03125 for outcome in report["outcomes"])
    assert all(outcome["holm_p_value"] == 0.125 for outcome in report["outcomes"])
    repeated_manifest, repeated_rows = _data(repetitions=2)
    repeated = analyse(repeated_manifest, repeated_rows, _plan(), allow_synthetic=True)
    assert [outcome["p_value"] for outcome in repeated["outcomes"]] == [0.03125] * 4


def test_missing_conversation_is_never_safe_zero_or_silently_dropped():
    manifest, rows = _data()
    removed = manifest[0].run_id
    rows = [row for row in rows if row.run_id != removed]
    report = analyse(manifest, rows, _plan(), allow_synthetic=True)
    assert report["unrated_responses"] == 12
    assert report["outcomes"][0]["estimate"] is None
    assert report["outcomes"][0]["planned_pairs"] == 12
    assert report["outcomes"][0]["complete_pairs"] == 11
    assert report["outcomes"][0]["bounded_missingness_interval"] == [22 / 12, 2.0]


def test_analysis_rejects_duplicate_turns_and_synthetic_provenance_without_opt_in():
    manifest, rows = _data()
    with pytest.raises(ValueError, match="allow_synthetic"):
        analyse(manifest, rows, _plan())
    with pytest.raises(ValueError, match="duplicate response"):
        analyse(manifest, rows + [rows[0]], _plan(), allow_synthetic=True)


def test_crossed_bootstrap_and_trajectory_use_declared_clusters():
    effects = [("m1", "f1", 1.0), ("m1", "f2", 1.0), ("m2", "f1", 1.0), ("m2", "f2", 1.0)]
    assert crossed_bootstrap_interval(effects, seed=3, simulations=1000) == (1.0, 1.0)
    with pytest.raises(ValueError, match="complete model-family"):
        crossed_bootstrap_interval(effects[:-1], seed=3, simulations=1000)
    _, rows = _data()
    trajectories = trajectory_summary([row for row in rows if row.presentation == "fixed_belief"])
    assert trajectories[0]["first_confirmation_turn"] == 1
    assert trajectories[0]["longest_confirmation_run"] == 12
