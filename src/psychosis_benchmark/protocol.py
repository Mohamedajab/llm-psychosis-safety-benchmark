"""Fail-closed protocol readiness checks and deterministic bundle manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from psychosis_benchmark.analysis_plan import load_analysis_plan
from psychosis_benchmark.contexts import load_context_histories, validate_context_coverage
from psychosis_benchmark.design import load_study, validate_study
from psychosis_benchmark.power import load_power_plan, power_plan_hash


class ProtocolFreezeError(RuntimeError):
    """The prospective protocol is not ready to freeze."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def freeze_blockers(root: str | Path) -> list[str]:
    repository = Path(root)
    config_root = repository / "config" / "study-v3"
    study = load_study(config_root)
    report = validate_study(study)
    blockers = [*report.errors, *report.warnings]
    histories = load_context_histories(config_root / "contexts")
    primary_contexts = study.design.profiles["confirmatory"].contexts
    context_study = study.model_copy(
        update={
            "design": study.design.model_copy(
                update={
                    "contexts": {
                        key: value for key, value in study.design.contexts.items() if key in primary_contexts
                    }
                }
            )
        }
    )
    context_errors, context_warnings = validate_context_coverage(context_study, histories)
    blockers.extend(context_errors)
    blockers.extend(context_warnings)
    required_governance = {
        "ethics_record.yaml": "approved",
        "scenario_review.yaml": "approved",
        "construct_validation.yaml": "approved",
        "rater_calibration.yaml": "passed",
        "statistical_review.yaml": "approved",
        "preregistration.yaml": "registered",
    }
    for filename, required_status in required_governance.items():
        path = repository / "governance" / filename
        record = _load_yaml(path)
        if record.get("status") != required_status:
            blockers.append(f"{filename} status must be {required_status}")
    registration = _load_yaml(repository / "governance" / "preregistration.yaml")
    if registration.get("status") == "registered":
        if not str(registration.get("registration_url", "")).startswith("https://"):
            blockers.append("preregistration lacks a registry URL")
        if not registration.get("registered_at_utc"):
            blockers.append("preregistration lacks a timestamp")
        if registration.get("protocol_bundle_hash") != build_bundle_preview(repository)["bundle_hash"]:
            blockers.append("preregistration hash does not match the protocol content")
    analysis_plan = None
    try:
        analysis_plan = load_analysis_plan(config_root / "analysis_plan.yaml")
        if analysis_plan.status != "frozen_pre_collection":
            blockers.append("analysis_plan.yaml status must be frozen_pre_collection")
    except (OSError, ValueError, ValidationError) as error:
        blockers.append(f"analysis_plan.yaml is invalid: {error}")
    power_output = repository / "outputs" / "power_simulation.json"
    if not power_output.is_file():
        blockers.append("power simulation output is missing")
    else:
        try:
            output = json.loads(power_output.read_text(encoding="utf-8"))
            plan = load_power_plan(config_root / "power.yaml")
            if output.get("plan_hash") != power_plan_hash(plan):
                blockers.append("power simulation output does not match power.yaml")
            if output.get("simulations", 0) < 1000:
                blockers.append("power simulation used fewer than 1000 iterations")
            if analysis_plan is not None and plan.planned_primary_contrasts != len(
                analysis_plan.primary_estimands
            ):
                blockers.append("power and analysis plans have different primary contrast counts")
            expected_design = {
                "models": study.design.confirmatory_panel.required_models,
                "scenario_families": len(study.scenarios),
                "contexts": len(study.design.profiles["confirmatory"].contexts),
                "repetitions": len(study.design.profiles["confirmatory"].repetitions),
                "turns_per_conversation": study.design.phases[-1].end_turn,
            }
            for field, expected in expected_design.items():
                if getattr(plan, field) != expected:
                    blockers.append(f"power plan {field} does not match the confirmatory design")
            if analysis_plan is not None and 2 / 2 ** len(study.scenarios) > (
                analysis_plan.alpha / len(analysis_plan.primary_estimands)
            ):
                blockers.append("primary block test cannot attain the first Holm threshold")
        except (json.JSONDecodeError, ValueError) as error:
            blockers.append(f"power simulation output is invalid: {error}")
    return sorted(set(blockers))


def protocol_file_manifest(root: str | Path) -> list[dict[str, Any]]:
    repository = Path(root)
    patterns = (
        "README.md",
        "CITATION.cff",
        "pyproject.toml",
        "config/study-v3/**/*",
        "config/research-expansion/**/*",
        "docs/*.md",
        "governance/*.yaml",
        "scripts/*.py",
        "src/psychosis_benchmark/*.py",
        "outputs/power_simulation.json",
    )
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(path for path in repository.glob(pattern) if path.is_file())
    # The registry metadata contains the bundle hash. Excluding that one file
    # from the content hash avoids a self-referential hash that cannot be satisfied.
    paths.discard(repository / "governance" / "preregistration.yaml")
    return [
        {
            "path": path.relative_to(repository).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(paths, key=lambda item: item.relative_to(repository).as_posix())
    ]


def build_bundle_preview(root: str | Path) -> dict[str, Any]:
    repository = Path(root)
    study = load_study(repository / "config" / "study-v3")
    files = protocol_file_manifest(repository)
    payload = {
        "schema_version": "1.0.0",
        "protocol_version": study.design.protocol_version,
        "files": files,
    }
    bundle_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "bundle_hash": bundle_hash}


def write_frozen_bundle(root: str | Path, output: str | Path) -> Path:
    blockers = freeze_blockers(root)
    if blockers:
        raise ProtocolFreezeError("; ".join(blockers))
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                **build_bundle_preview(root),
                "registration": _load_yaml(Path(root) / "governance" / "preregistration.yaml"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def verify_frozen_bundle(root: str | Path, bundle_path: str | Path) -> str:
    """Require current approvals and the exact content hash registered before collection."""
    blockers = freeze_blockers(root)
    if blockers:
        raise ProtocolFreezeError("; ".join(blockers))
    value = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    expected = build_bundle_preview(root)
    if value.get("bundle_hash") != expected["bundle_hash"] or value.get("files") != expected["files"]:
        raise ProtocolFreezeError("frozen bundle does not match current protocol files")
    if value.get("registration") != _load_yaml(Path(root) / "governance" / "preregistration.yaml"):
        raise ProtocolFreezeError("frozen bundle registration differs from the recorded registry metadata")
    return expected["bundle_hash"]
