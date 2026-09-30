"""Strict contracts for the prospective Study V3 configuration."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Reject undeclared fields so protocol drift fails visibly."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Tier(StrEnum):
    FREE = "free"
    LOW_COST = "low_cost"


class Presentation(StrEnum):
    SCREENING = "screening"
    CONTROL = "control"
    AMBIGUOUS = "ambiguous"
    FIXED_BELIEF = "fixed_belief"


class GenerationConfig(StrictModel):
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_output_tokens: int = Field(ge=1, le=8192)
    timeout_seconds: float = Field(gt=0, le=300)
    max_retries: int = Field(ge=0, le=5)
    allow_model_fallback: Literal[False]
    retain_reasoning: Literal[False]


class ContextConfig(StrictModel):
    prior_message_count: int = Field(ge=0, le=512)


class PhaseConfig(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    start_turn: int = Field(ge=1, le=12)
    end_turn: int = Field(ge=1, le=12)

    @model_validator(mode="after")
    def ordered(self) -> PhaseConfig:
        if self.end_turn < self.start_turn:
            raise ValueError("phase end_turn cannot precede start_turn")
        return self


class ProfileConfig(StrictModel):
    stage: Literal["development", "screening", "confirmatory", "robustness"]
    model_selector: Literal["all", "continuity", "confirmatory"]
    scenario_set: Literal["screening", "confirmatory"]
    presentations: tuple[Presentation, ...]
    contexts: tuple[str, ...]
    repetitions: tuple[int, ...]
    seed: int

    @field_validator("repetitions")
    @classmethod
    def repetitions_are_unique_positive(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or len(value) != len(set(value)) or any(item < 1 for item in value):
            raise ValueError("repetitions must be unique positive integers")
        return value


class ConfirmatoryPanelConfig(StrictModel):
    required_models: int = Field(ge=2)
    minimum_model_families: int = Field(ge=2)
    minimum_paid_anchors: int = Field(ge=1)
    maximum_models_per_family: int = Field(ge=1)
    selected_model_ids: tuple[str, ...] = ()


class FreezeRequirements(StrictModel):
    provider_pin_required: Literal[True]
    ethics_record_required: Literal[True]
    scenario_review_required: Literal[True]
    rater_calibration_required: Literal[True]
    sample_size_simulation_required: Literal[True]


class DesignConfig(StrictModel):
    protocol_version: str
    status: Literal["draft_pre_collection", "frozen_pre_collection", "complete"]
    scenario_schema_version: str
    manifest_seed: int
    generation: GenerationConfig
    contexts: dict[str, ContextConfig]
    phases: tuple[PhaseConfig, ...]
    profiles: dict[str, ProfileConfig]
    confirmatory_panel: ConfirmatoryPanelConfig
    freeze_requirements: FreezeRequirements

    @model_validator(mode="after")
    def validate_factor_references(self) -> DesignConfig:
        if set(self.profiles) != {
            "development",
            "screening",
            "confirmatory",
            "robustness_depth",
        }:
            raise ValueError("the four declared study profiles are required")
        for name, profile in self.profiles.items():
            unknown_contexts = set(profile.contexts) - set(self.contexts)
            if unknown_contexts:
                raise ValueError(f"profile {name} references unknown contexts: {unknown_contexts}")
            if profile.scenario_set == "screening" and profile.presentations != (Presentation.SCREENING,):
                raise ValueError("screening scenario sets require only the screening presentation")
            if profile.scenario_set == "confirmatory" and Presentation.SCREENING in profile.presentations:
                raise ValueError("confirmatory profiles cannot include screening scripts")
        covered = [turn for phase in self.phases for turn in range(phase.start_turn, phase.end_turn + 1)]
        if covered != list(range(1, 13)):
            raise ValueError("phases must cover turns 1 through 12 once and in order")
        return self


class EligibilityConfig(StrictModel):
    minimum_context_tokens: int = Field(ge=8192)
    maximum_prompt_usd_per_million: float = Field(ge=0)
    maximum_completion_usd_per_million: float = Field(ge=0)
    require_exact_slug: Literal[True]
    require_text_output: Literal[True]
    require_provider_pin_for_confirmatory: Literal[True]


class ModelSpec(StrictModel):
    model_id: str
    display_name: str
    family: str
    organisation: str
    tier: Tier
    role: Literal["general", "continuity", "domain_specialised_exploratory", "paid_anchor"]
    context_tokens: int = Field(ge=1)
    max_completion_tokens: int = Field(ge=1)
    prompt_usd_per_million: float = Field(ge=0)
    completion_usd_per_million: float = Field(ge=0)
    supports_seed: bool
    provider_pin: str | None
    include_in_screening: bool
    eligible_for_confirmatory: bool

    @field_validator("model_id")
    @classmethod
    def exact_slug_only(cls, value: str) -> str:
        lowered = value.casefold()
        if "/" not in value or value in {"openrouter/free", "openrouter/auto"}:
            raise ValueError("model_id must be an exact provider/model slug")
        if "latest" in lowered or "*" in value:
            raise ValueError("moving aliases and wildcards are forbidden")
        return value

    @model_validator(mode="after")
    def price_matches_tier(self) -> ModelSpec:
        free_price = self.prompt_usd_per_million == self.completion_usd_per_million == 0
        if self.tier == Tier.FREE and not free_price:
            raise ValueError("free models must have zero catalogue prices")
        if self.tier == Tier.LOW_COST and free_price:
            raise ValueError("low-cost anchors must have a non-zero catalogue price")
        if self.eligible_for_confirmatory and not self.provider_pin:
            raise ValueError("confirmatory eligibility requires a provider pin")
        return self


class ModelPanel(StrictModel):
    version: str
    provider: Literal["openrouter"]
    catalogue_endpoint: str
    catalogue_checked_at_utc: str
    price_currency: Literal["USD"]
    price_unit: Literal["million_tokens"]
    eligibility: EligibilityConfig
    models: tuple[ModelSpec, ...]
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_panel(self) -> ModelPanel:
        ids = [model.model_id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("model IDs must be unique")
        for model in self.models:
            if model.context_tokens < self.eligibility.minimum_context_tokens:
                raise ValueError(f"{model.model_id} is below the minimum context length")
            if model.prompt_usd_per_million > self.eligibility.maximum_prompt_usd_per_million:
                raise ValueError(f"{model.model_id} exceeds the prompt price ceiling")
            if model.completion_usd_per_million > self.eligibility.maximum_completion_usd_per_million:
                raise ValueError(f"{model.model_id} exceeds the completion price ceiling")
        return self


class Script(StrictModel):
    script_id: str = Field(pattern=r"^[a-z0-9_]+$")
    manipulation: str | None = None
    turns: tuple[str, ...]

    @field_validator("turns")
    @classmethod
    def nonblank_turns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not turn.strip() for turn in value):
            raise ValueError("scripts require nonblank turns")
        return value


class ScenarioFamily(StrictModel):
    schema_version: str
    family_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    title: str
    evaluation_construct: str = Field(alias="construct")
    review_status: Literal["pending_clinical_and_lived_experience_review", "reviewed", "frozen"]
    screening_script: Script
    variants: dict[Literal["control", "ambiguous", "fixed_belief"], Script]

    @model_validator(mode="after")
    def validate_scripts(self) -> ScenarioFamily:
        if len(self.screening_script.turns) != 4:
            raise ValueError("technical screening scripts must contain four turns")
        if set(self.variants) != {"control", "ambiguous", "fixed_belief"}:
            raise ValueError("each family requires three matched presentation variants")
        if any(len(script.turns) != 12 for script in self.variants.values()):
            raise ValueError("confirmatory scripts must contain twelve turns")
        ids = [
            self.screening_script.script_id,
            *(item.script_id for item in self.variants.values()),
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("script IDs must be unique within a family")
        return self


class ManifestRow(StrictModel):
    schema_version: Literal["3.0.0"] = "3.0.0"
    protocol_version: str
    stage: str
    run_id: str
    scenario_family: str
    script_id: str
    presentation: Presentation
    model_id: str
    model_tier: Tier
    context_condition: str
    prior_message_count: int
    repetition: int
    planned_turns: int
    planned_seed: int
    execution_order: int
    status: Literal["planned"] = "planned"


class StudyBundle(StrictModel):
    design: DesignConfig
    models: ModelPanel
    scenarios: tuple[ScenarioFamily, ...]


class ValidationReport(StrictModel):
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors
