"""Strict machine-readable contract for the prospective statistical analysis plan."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MultiplicityPlan(PlanModel):
    method: Literal["holm"]
    family: Literal["primary_estimands"]


class Estimand(PlanModel):
    id: str = Field(pattern=r"^E[1-9][0-9]*_[a-z0-9_]+$")
    axis: Literal["P1", "P2", "P3", "P4", "P5"]
    direction: Literal["higher_is_worse", "higher_is_better"]
    turns: tuple[int, ...]
    contrast: Literal["fixed_belief_minus_control", "ambiguous_minus_control"]

    @field_validator("turns")
    @classmethod
    def valid_turn_mask(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or tuple(sorted(set(value))) != value or any(turn not in range(1, 13) for turn in value):
            raise ValueError("turn masks must be unique, ordered, and within 1 through 12")
        return value


class AggregationPlan(PlanModel):
    turn_to_conversation: Literal["arithmetic_mean_of_prespecified_turns"]
    primary_total_score: Literal["forbidden"]
    na_policy: Literal["report_and_exclude_axis_specific_na_only"]
    minimum_scorable_turn_fraction: float = Field(gt=0, le=1)


class ModelPlan(PlanModel):
    primary: Literal["cumulative_link_mixed_model"]
    fixed_effects: tuple[Literal["presentation", "context_condition", "presentation_by_context"], ...]
    random_effects: tuple[Literal["model_id", "scenario_family", "repetition"], ...]
    fallback: Literal["matched_conversation_level_sign_flip"]


class UncertaintyPlan(PlanModel):
    interval: Literal["cluster_bootstrap"]
    resampling_clusters: tuple[Literal["model_id", "scenario_family"], ...]
    bootstrap_seed: int
    bootstrap_simulations: int = Field(ge=999)


class MissingnessPlan(PlanModel):
    primary: Literal["complete_prespecified_conversations"]
    report_by: tuple[Literal["model_id", "presentation", "context_condition", "failure_reason"], ...]
    sensitivity: Literal["worst_and_best_bounded_scores"]


class AnalysisPlan(PlanModel):
    plan_version: str = Field(pattern=r"^analysis-v[0-9].+$")
    status: Literal["draft_pre_review", "frozen_pre_collection"]
    analysis_unit: Literal["conversation"]
    alpha: float = Field(gt=0, lt=1)
    confidence_level: float = Field(gt=0, lt=1)
    primary_rating: Literal["adjudicated"]
    sensitivity_rating: Literal["independent_raw_raters"]
    multiplicity: MultiplicityPlan
    primary_estimands: tuple[Estimand, ...]
    aggregation: AggregationPlan
    model: ModelPlan
    uncertainty: UncertaintyPlan
    missingness: MissingnessPlan
    analysis_decisions_pending_review: tuple[str, ...]

    @model_validator(mode="after")
    def validate_complete_plan(self) -> AnalysisPlan:
        ids = [estimand.id for estimand in self.primary_estimands]
        if len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("exactly four uniquely named primary estimands are required")
        if not self.analysis_decisions_pending_review and self.status == "draft_pre_review":
            raise ValueError("a draft plan must list its unresolved decisions")
        if self.analysis_decisions_pending_review and self.status == "frozen_pre_collection":
            raise ValueError("a frozen plan cannot contain unresolved analysis decisions")
        if set(self.model.fixed_effects) != {
            "presentation",
            "context_condition",
            "presentation_by_context",
        }:
            raise ValueError("all prespecified fixed effects are required exactly once")
        if set(self.model.random_effects) != {"model_id", "scenario_family", "repetition"}:
            raise ValueError("all prespecified random effects are required exactly once")
        if set(self.uncertainty.resampling_clusters) != {"model_id", "scenario_family"}:
            raise ValueError("the interval must account for model and scenario-family clustering")
        return self


def load_analysis_plan(path: str | Path) -> AnalysisPlan:
    with Path(path).open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return AnalysisPlan.model_validate(value)
