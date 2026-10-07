from pathlib import Path

import pytest

from psychosis_benchmark.validation_run import run_validation

ROOT = Path(__file__).resolve().parents[1]


def test_complete_workflow_is_simulation_only_and_repeatable(tmp_path):
    first = run_validation(ROOT, tmp_path / "first", models=2, families=2)
    second = run_validation(ROOT, tmp_path / "second", models=2, families=2)
    assert first == second
    assert first["data_origin"] == "synthetic_fixture"
    assert first["conversations"] == 48
    assert first["responses"] == 576
    assert first["verified_ledgers"] == 48
    assert first["synthetic_raw_ratings"] == 1152
    assert first["blinding_audit_passed"]
    assert first["all_ledgers_complete"]
    assert not first["clinical_or_model_performance_claim"]
    with pytest.raises(ValueError, match="already exists"):
        run_validation(ROOT, tmp_path / "first", models=2, families=2)
