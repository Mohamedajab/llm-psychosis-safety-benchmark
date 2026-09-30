from __future__ import annotations

from pathlib import Path

from psychosis_benchmark.catalogue import load_snapshot, verify_snapshot
from psychosis_benchmark.design import load_study

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study-v3"


def test_catalogue_snapshot_matches_model_panel() -> None:
    study = load_study(CONFIG)
    snapshot = load_snapshot(CONFIG / "catalogue_snapshot_2026-09-30.json")
    assert snapshot["catalogue_model_count"] == 464
    assert verify_snapshot(study.models, snapshot) == []
