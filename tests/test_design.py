from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from psychosis_benchmark.costing import estimate_costs
from psychosis_benchmark.design import (
    StudyConfigurationError,
    build_manifest,
    canonical_hash,
    load_study,
    validate_study,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study-v3"


@pytest.fixture(scope="module")
def study():
    return load_study(CONFIG)


def test_configuration_is_valid_but_not_frozen(study) -> None:
    report = validate_study(study)
    assert report.errors == ()
    assert "confirmatory model panel has not been selected" in report.warnings
    assert "protocol status is draft_pre_collection" in report.warnings


def test_scenario_matrix_is_complete(study) -> None:
    assert len(study.scenarios) == 6
    assert {len(scenario.screening_script.turns) for scenario in study.scenarios} == {4}
    assert sum(len(scenario.variants) for scenario in study.scenarios) == 18
    for scenario in study.scenarios:
        assert set(scenario.variants) == {"control", "ambiguous", "fixed_belief"}
        assert {len(script.turns) for script in scenario.variants.values()} == {12}


def test_screening_manifest_is_balanced_and_reproducible(study) -> None:
    first = build_manifest(study, "screening")
    second = build_manifest(study, "screening")
    assert first == second
    assert len(first) == 66
    assert sum(row.planned_turns for row in first) == 264
    assert len({row.run_id for row in first}) == 66
    assert set(Counter(row.model_id for row in first).values()) == {6}
    assert set(Counter(row.scenario_family for row in first).values()) == {11}


def test_confirmatory_manifest_fails_closed_until_panel_is_frozen(study) -> None:
    with pytest.raises(StudyConfigurationError, match="confirmatory panel is intentionally empty"):
        build_manifest(study, "confirmatory")


def test_model_panel_has_exact_diverse_low_cost_endpoints(study) -> None:
    models = study.models.models
    assert len(models) == 11
    assert sum(model.tier.value == "free" for model in models) == 6
    assert len({model.family for model in models}) == 9
    assert all("latest" not in model.model_id for model in models)
    assert all(model.model_id not in {"openrouter/free", "openrouter/auto"} for model in models)
    assert max(model.completion_usd_per_million for model in models) <= 0.40


def test_screening_cost_estimate_keeps_free_models_at_zero(study) -> None:
    rows = build_manifest(study, "screening")
    estimates = estimate_costs(rows, study.models, study.design.generation.max_output_tokens)
    assert len(estimates) == 11
    by_id = {item.model_id: item for item in estimates}
    for model in study.models.models:
        if model.tier.value == "free":
            assert by_id[model.model_id].total_cost_usd == 0
        else:
            assert by_id[model.model_id].total_cost_usd > 0


def test_study_hash_is_stable(study) -> None:
    first = canonical_hash(study)
    second = canonical_hash(load_study(CONFIG))
    assert len(first) == 64
    assert first == second
