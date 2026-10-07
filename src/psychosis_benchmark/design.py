"""Load, validate, and expand the prospective Study V3 design."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from itertools import product
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from psychosis_benchmark.schema import (
    DesignConfig,
    ManifestRow,
    ModelPanel,
    ModelSpec,
    Presentation,
    ScenarioFamily,
    Script,
    StudyBundle,
    ValidationReport,
)

DEFAULT_CONFIG_ROOT = Path("config/study-v3")


class StudyConfigurationError(ValueError):
    """Configuration cannot support the requested operation."""


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise StudyConfigurationError(f"missing configuration: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as error:
        raise StudyConfigurationError(f"malformed YAML in {path}: {error}") from error


def _parse(path: Path, model_type: type[Any]) -> Any:
    try:
        return model_type.model_validate(_load_yaml(path))
    except ValidationError as error:
        raise StudyConfigurationError(f"invalid configuration in {path}: {error}") from error


def load_study(config_root: str | Path = DEFAULT_CONFIG_ROOT) -> StudyBundle:
    root = Path(config_root)
    design = _parse(root / "design.yaml", DesignConfig)
    models = _parse(root / "models.yaml", ModelPanel)
    scenario_paths = sorted((root / "scenarios").glob("*.yaml"))
    if not scenario_paths:
        raise StudyConfigurationError("no scenario families found")
    scenarios = tuple(_parse(path, ScenarioFamily) for path in scenario_paths)
    return StudyBundle(design=design, models=models, scenarios=scenarios)


def validate_study(study: StudyBundle) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if len(study.scenarios) < 6:
        errors.append(f"at least six scenario families are required; found {len(study.scenarios)}")
    family_ids = [scenario.family_id for scenario in study.scenarios]
    if len(family_ids) != len(set(family_ids)):
        errors.append("scenario family IDs must be unique")
    script_ids = [
        script.script_id
        for scenario in study.scenarios
        for script in (scenario.screening_script, *scenario.variants.values())
    ]
    if len(script_ids) != len(set(script_ids)):
        errors.append("script IDs must be globally unique")
    for scenario in study.scenarios:
        if any(
            len(script.turns) != study.design.phases[-1].end_turn for script in scenario.variants.values()
        ):
            errors.append(f"{scenario.family_id} does not match the declared trajectory horizon")
        if scenario.schema_version != study.design.scenario_schema_version:
            errors.append(f"{scenario.family_id} has the wrong schema version")
        if scenario.review_status != "frozen":
            warnings.append(f"{scenario.family_id} is not frozen after expert review")
    screening = [model for model in study.models.models if model.include_in_screening]
    if len(screening) < 2:
        errors.append("at least two screening models are required")
    selected = study.design.confirmatory_panel.selected_model_ids
    if not selected:
        warnings.append("confirmatory model panel has not been selected")
    else:
        known = {model.model_id: model for model in study.models.models}
        missing = set(selected) - set(known)
        if missing:
            errors.append(f"unknown confirmatory model IDs: {sorted(missing)}")
        chosen = [known[model_id] for model_id in selected if model_id in known]
        rule = study.design.confirmatory_panel
        if len(chosen) != rule.required_models:
            errors.append(f"confirmatory panel requires {rule.required_models} models")
        if len({model.family for model in chosen}) < rule.minimum_model_families:
            errors.append("confirmatory panel has too few model families")
        if sum(model.tier.value == "low_cost" for model in chosen) < rule.minimum_paid_anchors:
            errors.append("confirmatory panel has too few paid anchors")
        for model in chosen:
            if not model.eligible_for_confirmatory or not model.provider_pin:
                errors.append(f"{model.model_id} is not frozen with a provider pin")
        family_counts = {family: 0 for family in {model.family for model in chosen}}
        for model in chosen:
            family_counts[model.family] += 1
        if any(count > rule.maximum_models_per_family for count in family_counts.values()):
            errors.append("confirmatory panel exceeds the per-family cap")
    if study.design.status != "frozen_pre_collection":
        warnings.append("protocol status is draft_pre_collection")
    return ValidationReport(errors=tuple(errors), warnings=tuple(warnings))


def _select_models(study: StudyBundle, selector: str) -> tuple[ModelSpec, ...]:
    if selector == "all":
        return tuple(model for model in study.models.models if model.include_in_screening)
    if selector == "continuity":
        return tuple(model for model in study.models.models if model.role == "continuity")
    if selector == "confirmatory":
        selected = study.design.confirmatory_panel.selected_model_ids
        if not selected:
            raise StudyConfigurationError(
                "confirmatory panel is intentionally empty until provider pins and the selection rule pass"
            )
        by_id = {model.model_id: model for model in study.models.models}
        return tuple(by_id[model_id] for model_id in selected)
    raise StudyConfigurationError(f"unknown model selector: {selector}")


def _select_scripts(
    study: StudyBundle, scenario_set: str, presentations: tuple[Presentation, ...]
) -> tuple[tuple[ScenarioFamily, Presentation, Script], ...]:
    selected: list[tuple[ScenarioFamily, Presentation, Script]] = []
    for scenario in sorted(study.scenarios, key=lambda item: item.family_id):
        if scenario_set == "screening":
            selected.append((scenario, Presentation.SCREENING, scenario.screening_script))
            continue
        for presentation in presentations:
            script = scenario.variants[presentation.value]
            selected.append((scenario, presentation, script))
    return tuple(selected)


def _run_id(
    protocol: str,
    profile_name: str,
    script_id: str,
    model_id: str,
    context: str,
    repetition: int,
) -> str:
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:10]
    return f"{protocol}_{profile_name}_{script_id}_{digest}_{context}_r{repetition}"


def build_manifest(study: StudyBundle, profile_name: str) -> list[ManifestRow]:
    try:
        profile = study.design.profiles[profile_name]
    except KeyError as error:
        raise StudyConfigurationError(f"unknown profile: {profile_name}") from error
    models = _select_models(study, profile.model_selector)
    scripts = _select_scripts(study, profile.scenario_set, profile.presentations)
    factors = list(product(scripts, models, profile.contexts, profile.repetitions))
    random.Random(profile.seed).shuffle(factors)
    rows: list[ManifestRow] = []
    for order, ((scenario, presentation, script), model, context_name, repetition) in enumerate(
        factors, start=1
    ):
        context = study.design.contexts[context_name]
        rows.append(
            ManifestRow(
                protocol_version=study.design.protocol_version,
                stage=profile.stage,
                run_id=_run_id(
                    study.design.protocol_version,
                    profile_name,
                    script.script_id,
                    model.model_id,
                    context_name,
                    repetition,
                ),
                scenario_family=scenario.family_id,
                script_id=script.script_id,
                presentation=presentation,
                model_id=model.model_id,
                model_tier=model.tier,
                context_condition=context_name,
                prior_message_count=context.prior_message_count,
                repetition=repetition,
                planned_turns=len(script.turns),
                planned_seed=profile.seed + repetition,
                execution_order=order,
            )
        )
    if len({row.run_id for row in rows}) != len(rows):
        raise StudyConfigurationError("manifest run IDs are not unique")
    return rows


def write_manifest(rows: list[ManifestRow], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(ManifestRow.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item.execution_order):
            writer.writerow(row.model_dump(mode="json"))
    return path


def canonical_hash(study: StudyBundle) -> str:
    value = study.model_dump(mode="json")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
