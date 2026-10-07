from pathlib import Path

import pytest

from psychosis_benchmark.design import build_manifest, canonical_hash, load_study, validate_study
from psychosis_benchmark.expansion import load_expanded_study

ROOT = Path(__file__).resolve().parents[1]


def test_expansion_is_separate_balanced_and_not_frozen():
    original_hash = canonical_hash(load_study(ROOT / "config/study-v3"))
    expanded = load_expanded_study(ROOT)
    assert len(expanded.scenarios) == 10
    assert len(expanded.models.models) == 16
    assert sum(model.tier.value == "low_cost" for model in expanded.models.models) == 10
    assert expanded.design.confirmatory_panel.required_models == 8
    assert expanded.design.confirmatory_panel.minimum_paid_anchors == 5
    assert not validate_study(expanded).errors
    assert not expanded.design.confirmatory_panel.selected_model_ids
    assert canonical_hash(load_study(ROOT / "config/study-v3")) == original_hash


def test_long_horizon_preserves_first_twelve_turns_and_does_not_add_blocks():
    core = load_expanded_study(ROOT, horizon=12)
    long = load_expanded_study(ROOT, horizon=24)
    assert not validate_study(long).errors
    for first, second in zip(core.scenarios, long.scenarios, strict=True):
        assert first.family_id == second.family_id
        for presentation in first.variants:
            assert second.variants[presentation].turns[:12] == first.variants[presentation].turns
            assert len(second.variants[presentation].turns) == 24
    rows = build_manifest(long, "robustness_depth")
    assert len(rows) == 16 * 10 * 3 * 2 * 3
    assert {row.planned_turns for row in rows} == {24}
    assert {row.stage for row in rows} == {"robustness"}
    assert len({row.scenario_family for row in rows}) == 10


def test_unsupported_horizon_is_not_silently_truncated():
    with pytest.raises(ValueError, match="12 or 24"):
        load_expanded_study(ROOT, horizon=48)
