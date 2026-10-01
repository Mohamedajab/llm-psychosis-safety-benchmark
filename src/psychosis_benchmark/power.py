"""Cluster-aware design-sensitivity simulation for pre-study planning."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PowerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    status: str
    seed: int
    simulations: int = Field(ge=100)
    alpha_familywise: float = Field(gt=0, lt=1)
    planned_primary_contrasts: int = Field(ge=1)
    models: int = Field(ge=2)
    scenario_families: int = Field(ge=2)
    contexts: int = Field(ge=1)
    repetitions: int = Field(ge=1)
    turns_per_conversation: int = Field(ge=2)
    baseline_event_probability: float = Field(gt=0, lt=1)
    contrast_log_odds: tuple[float, ...]
    model_random_effect_sd: float = Field(ge=0)
    family_random_effect_sd: float = Field(ge=0)
    conversation_random_effect_sd: float = Field(ge=0)
    notes: tuple[str, ...] = ()

    @field_validator("contrast_log_odds")
    @classmethod
    def effects_are_unique_positive(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or len(value) != len(set(value)) or any(effect <= 0 for effect in value):
            raise ValueError("contrast_log_odds must contain unique positive effects")
        return value


def load_power_plan(path: str | Path) -> PowerPlan:
    with Path(path).open(encoding="utf-8") as handle:
        return PowerPlan.model_validate(yaml.safe_load(handle))


def power_plan_hash(plan: PowerPlan) -> str:
    payload = json.dumps(
        plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _logit(probability: float) -> float:
    return math.log(probability / (1 - probability))


def _inverse_logit(value: float) -> float:
    if value >= 0:
        denominator = 1 + math.exp(-value)
        return 1 / denominator
    exponent = math.exp(value)
    return exponent / (1 + exponent)


def _binary_mean(rng: random.Random, probability: float, turns: int) -> float:
    return sum(rng.random() < probability for _ in range(turns)) / turns


def _one_sample_normal_pvalue(differences: list[float]) -> float:
    if len(differences) < 2:
        return 1.0
    mean = statistics.fmean(differences)
    standard_deviation = statistics.stdev(differences)
    if standard_deviation == 0:
        return 0.0 if mean else 1.0
    z_score = mean / (standard_deviation / math.sqrt(len(differences)))
    return math.erfc(abs(z_score) / math.sqrt(2))


def simulate_design(plan: PowerPlan) -> dict[str, object]:
    """Estimate detection probability with conversation-level paired differences.

    The test approximation is deliberately simple and must not be reused as the final analysis.
    Its purpose is to expose the design assumptions before collection.
    """

    results: list[dict[str, float]] = []
    adjusted_alpha = plan.alpha_familywise / plan.planned_primary_contrasts
    baseline_logit = _logit(plan.baseline_event_probability)
    cluster_count = plan.models * plan.scenario_families * plan.contexts * plan.repetitions
    for effect_index, effect in enumerate(plan.contrast_log_odds):
        rng = random.Random(plan.seed + effect_index)
        detections = 0
        average_differences: list[float] = []
        for _ in range(plan.simulations):
            model_effects = [rng.gauss(0, plan.model_random_effect_sd) for _ in range(plan.models)]
            family_effects = [
                rng.gauss(0, plan.family_random_effect_sd) for _ in range(plan.scenario_families)
            ]
            differences: list[float] = []
            for model_index in range(plan.models):
                for family_index in range(plan.scenario_families):
                    shared = model_effects[model_index] + family_effects[family_index]
                    for _context in range(plan.contexts):
                        for _repetition in range(plan.repetitions):
                            control_probability = _inverse_logit(
                                baseline_logit + shared + rng.gauss(0, plan.conversation_random_effect_sd)
                            )
                            contrast_probability = _inverse_logit(
                                baseline_logit
                                + effect
                                + shared
                                + rng.gauss(0, plan.conversation_random_effect_sd)
                            )
                            differences.append(
                                _binary_mean(rng, contrast_probability, plan.turns_per_conversation)
                                - _binary_mean(rng, control_probability, plan.turns_per_conversation)
                            )
            average_differences.append(statistics.fmean(differences))
            if _one_sample_normal_pvalue(differences) < adjusted_alpha:
                detections += 1
        results.append(
            {
                "contrast_log_odds": effect,
                "approximate_odds_ratio": math.exp(effect),
                "mean_absolute_probability_difference": statistics.fmean(average_differences),
                "estimated_detection_probability": detections / plan.simulations,
            }
        )
    return {
        "schema_version": "1.0.0",
        "plan_version": plan.version,
        "plan_hash": power_plan_hash(plan),
        "seed": plan.seed,
        "simulations": plan.simulations,
        "analysis_unit": "conversation-level paired difference",
        "cluster_count_per_presentation": cluster_count,
        "adjusted_alpha": adjusted_alpha,
        "results": results,
        "warning": (
            "Planning sensitivity only. This normal approximation is not the registered final "
            "mixed-effects analysis."
        ),
    }
