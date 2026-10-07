"""Rebuild registered estimand tables from JSONL ratings without model calls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.analysis import AnalysisRow, analyse, trajectory_summary  # noqa: E402
from psychosis_benchmark.analysis_plan import load_analysis_plan  # noqa: E402
from psychosis_benchmark.schema import ManifestRow  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=ROOT / "config/study-v3/analysis_plan.yaml")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists; use a new directory to retain prior analyses")
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        manifest = [ManifestRow.model_validate(value) for value in csv.DictReader(handle)]
    with args.ratings.open(encoding="utf-8") as handle:
        rows = [AnalysisRow.model_validate_json(line) for line in handle if line.strip()]
    report = analyse(manifest, rows, load_analysis_plan(args.plan), allow_synthetic=args.allow_synthetic)
    report["inputs_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.manifest, args.ratings, args.plan)
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "estimates.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    (args.output_dir / "trajectories.json").write_text(
        json.dumps(trajectory_summary(rows), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fields = [
        "estimand",
        "axis",
        "contrast",
        "planned_pairs",
        "complete_pairs",
        "estimate",
        "confidence_interval",
        "p_value",
        "holm_p_value",
        "status",
    ]
    with (args.output_dir / "estimates.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["outcomes"])
    print(
        f"wrote {len(report['outcomes'])} estimands; origin: {report['data_origin']}; "
        f"status: {report['analysis_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
