"""Offline checks for the time-stamped OpenRouter catalogue snapshot."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from psychosis_benchmark.schema import ModelPanel


def load_snapshot(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or not isinstance(value.get("selected_models"), list):
        raise ValueError("catalogue snapshot has no selected_models list")
    return value


def verify_snapshot(panel: ModelPanel, snapshot: dict[str, Any]) -> list[str]:
    """Compare result-changing panel fields with the captured catalogue rows."""

    errors: list[str] = []
    rows = {row.get("id"): row for row in snapshot["selected_models"]}
    expected_ids = {model.model_id for model in panel.models}
    if set(rows) != expected_ids:
        errors.append("snapshot and model panel contain different model IDs")
    for model in panel.models:
        row = rows.get(model.model_id)
        if row is None:
            continue
        comparisons = {
            "context_length": model.context_tokens,
            "max_completion_tokens": model.max_completion_tokens,
            "prompt_usd_per_million": model.prompt_usd_per_million,
            "completion_usd_per_million": model.completion_usd_per_million,
        }
        for field, expected in comparisons.items():
            if row.get(field) != expected:
                errors.append(f"{model.model_id}: snapshot {field} differs from models.yaml")
        if "text" not in str(row.get("modality", "")).split("->")[-1]:
            errors.append(f"{model.model_id}: snapshot does not declare text output")
        if "max_tokens" not in row.get("supported_parameters", []):
            errors.append(f"{model.model_id}: max_tokens is not listed as supported")
    return errors


def verify_live_catalogue(panel: ModelPanel, response: dict[str, Any]) -> list[str]:
    """Compare the planned panel with a fresh OpenRouter catalogue response."""

    data = response.get("data")
    if not isinstance(data, list):
        return ["live catalogue response has no data list"]
    rows = {row.get("id"): row for row in data if isinstance(row, dict)}
    errors: list[str] = []
    for model in panel.models:
        row = rows.get(model.model_id)
        if row is None:
            errors.append(f"{model.model_id}: endpoint is absent from the live catalogue")
            continue
        try:
            prompt_price = float(row["pricing"]["prompt"]) * 1_000_000
            completion_price = float(row["pricing"]["completion"]) * 1_000_000
            context_length = int(row["context_length"])
            max_completion = int(row["top_provider"]["max_completion_tokens"])
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{model.model_id}: incomplete live metadata ({error})")
            continue
        if not math.isclose(prompt_price, model.prompt_usd_per_million, abs_tol=1e-9):
            errors.append(f"{model.model_id}: prompt price changed")
        if not math.isclose(completion_price, model.completion_usd_per_million, abs_tol=1e-9):
            errors.append(f"{model.model_id}: completion price changed")
        if context_length != model.context_tokens:
            errors.append(f"{model.model_id}: context length changed")
        if max_completion != model.max_completion_tokens:
            errors.append(f"{model.model_id}: maximum completion length changed")
        parameters = row.get("supported_parameters") or []
        if "max_tokens" not in parameters:
            errors.append(f"{model.model_id}: max_tokens is no longer declared")
        modality = str((row.get("architecture") or {}).get("modality", ""))
        if "->text" not in modality:
            errors.append(f"{model.model_id}: live endpoint no longer declares text output")
    return errors
