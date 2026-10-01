from __future__ import annotations

from pathlib import Path

from psychosis_benchmark.catalogue import load_snapshot, verify_live_catalogue, verify_snapshot
from psychosis_benchmark.design import load_study

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study-v3"


def test_catalogue_snapshot_matches_model_panel() -> None:
    study = load_study(CONFIG)
    snapshot = load_snapshot(CONFIG / "catalogue_snapshot_2026-09-30.json")
    assert snapshot["catalogue_model_count"] == 464
    assert verify_snapshot(study.models, snapshot) == []


def test_live_catalogue_comparison_detects_price_drift() -> None:
    study = load_study(CONFIG)
    snapshot = load_snapshot(CONFIG / "catalogue_snapshot_2026-09-30.json")
    data = []
    for row in snapshot["selected_models"]:
        data.append(
            {
                "id": row["id"],
                "context_length": row["context_length"],
                "pricing": {
                    "prompt": row["prompt_usd_per_million"] / 1_000_000,
                    "completion": row["completion_usd_per_million"] / 1_000_000,
                },
                "top_provider": {"max_completion_tokens": row["max_completion_tokens"]},
                "supported_parameters": row["supported_parameters"],
                "architecture": {"modality": row["modality"]},
            }
        )
    assert verify_live_catalogue(study.models, {"data": data}) == []
    data[0]["pricing"]["completion"] = 0.1 / 1_000_000
    errors = verify_live_catalogue(study.models, {"data": data})
    assert errors == ["google/gemma-4-26b-a4b-it:free: completion price changed"]
