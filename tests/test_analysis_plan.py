from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from psychosis_benchmark.analysis_plan import AnalysisPlan, load_analysis_plan

ROOT = Path(__file__).resolve().parents[1]


def test_repository_analysis_plan_is_strict_and_explicitly_draft() -> None:
    plan = load_analysis_plan(ROOT / "config" / "study-v3" / "analysis_plan.yaml")
    assert plan.status == "draft_pre_review"
    assert [estimand.axis for estimand in plan.primary_estimands] == ["P1", "P2", "P3", "P4"]
    assert plan.multiplicity.method == "holm"
    assert plan.analysis_unit == "conversation"


def test_unknown_fields_and_invalid_turn_masks_fail() -> None:
    path = ROOT / "config" / "study-v3" / "analysis_plan.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    value["undeclared_choice"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AnalysisPlan.model_validate(value)
    value.pop("undeclared_choice")
    value["primary_estimands"][0]["turns"] = [1, 1, 13]
    with pytest.raises(ValidationError, match="turn masks"):
        AnalysisPlan.model_validate(value)


def test_plan_cannot_freeze_with_open_decisions() -> None:
    path = ROOT / "config" / "study-v3" / "analysis_plan.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    value["status"] = "frozen_pre_collection"
    with pytest.raises(ValidationError, match="unresolved analysis decisions"):
        AnalysisPlan.model_validate(value)
