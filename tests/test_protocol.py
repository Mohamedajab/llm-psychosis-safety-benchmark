from __future__ import annotations

from pathlib import Path

import pytest

from psychosis_benchmark.protocol import (
    ProtocolFreezeError,
    build_bundle_preview,
    freeze_blockers,
    write_frozen_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def test_draft_protocol_is_explicitly_blocked() -> None:
    blockers = freeze_blockers(ROOT)
    assert "confirmatory model panel has not been selected" in blockers
    assert "ethics_record.yaml status must be approved" in blockers
    assert "scenario_review.yaml status must be approved" in blockers
    assert "deep_history_96 has no authored context history" in blockers


def test_bundle_preview_is_stable_and_contains_result_changing_files() -> None:
    first = build_bundle_preview(ROOT)
    second = build_bundle_preview(ROOT)
    assert first == second
    paths = {row["path"] for row in first["files"]}
    assert "config/study-v3/design.yaml" in paths
    assert "config/study-v3/system_prompt.txt" in paths
    assert "src/psychosis_benchmark/collection.py" in paths
    assert len(first["bundle_hash"]) == 64


def test_frozen_bundle_cannot_be_written_while_blocked(tmp_path) -> None:
    with pytest.raises(ProtocolFreezeError):
        write_frozen_bundle(ROOT, tmp_path / "bundle.json")
    assert not (tmp_path / "bundle.json").exists()
