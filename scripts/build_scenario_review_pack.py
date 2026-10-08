"""Export scripted user materials only; private labels never enter the Site checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from psychosis_benchmark.evidence_freeze import verify_freeze, write_new_json  # noqa: E402


def build(snapshot: Path, output: Path, private_key: Path):
    if output.exists() or private_key.exists():
        raise FileExistsError("Review pack or private mapping already exists")
    verified = verify_freeze(snapshot)
    inputs = json.loads((snapshot / "raw/inputs.json").read_text(encoding="utf-8"))
    material = []
    selected = {(r["track"], r["row"]["scenario_family"], r["row"]["presentation"]) for r in inputs["rows"]}
    for track, study in inputs["studies"].items():
        for family in study["scenarios"]:
            for condition, variant in family["variants"].items():
                if (track, family["family_id"], condition) not in selected:
                    continue
                material.append((track, family["family_id"], condition, variant["turns"]))
    random.Random(secrets.randbits(128)).shuffle(material)
    items, mapping = [], []
    for n, (track, family, condition, turns) in enumerate(material, 1):
        item_id = f"C{n:03}"
        item = {
            "id": item_id,
            "kind": "scenario",
            "version": "collected-script-review-v1",
            "title": f"Scenario {item_id}",
            "turns": turns,
        }
        item["materialHash"] = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
        items.append(item)
        mapping.append(
            {
                "id": item_id,
                "track": track,
                "family": family,
                "condition": condition,
                "material_hash": item["materialHash"],
            }
        )
    rubric = (ROOT / "docs/ANNOTATION_PROTOCOL_V3.md").read_text(encoding="utf-8")
    rubric_item = {
        "id": "R001",
        "kind": "rubric",
        "version": "annotation-protocol-v3-draft",
        "title": "Draft scoring rubric",
        "text": rubric,
    }
    rubric_item["materialHash"] = hashlib.sha256(json.dumps(rubric_item, sort_keys=True).encode()).hexdigest()
    items.append(rubric_item)
    output.parent.mkdir(parents=True, exist_ok=True)
    private_key.parent.mkdir(parents=True, exist_ok=True)
    # The linkage map stays in the benchmark's ignored private directory.
    if private_key.resolve().is_relative_to(output.parent.resolve()):
        raise ValueError("Private mapping must not be written alongside hosted materials")
    write_new_json(private_key, {"source_root": verified["content_root_sha256"], "mapping": mapping})
    write_new_json(
        output,
        {
            "schemaVersion": "scenario-review-pack-v1",
            "sourceRoot": verified["content_root_sha256"],
            "items": items,
        },
    )
    return {
        "scenario_items": len(material),
        "rubric_items": 1,
        "source_root": verified["content_root_sha256"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--private-map", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(build(a.snapshot_dir, a.output, a.private_map)))
