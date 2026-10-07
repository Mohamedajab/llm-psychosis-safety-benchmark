"""Run the complete workflow using synthetic fixtures; never calls a model API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from psychosis_benchmark.validation_run import run_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", type=int, default=6, choices=range(2, 12))
    parser.add_argument("--families", type=int, default=6, choices=range(2, 7))
    args = parser.parse_args()
    report = run_validation(ROOT, args.output_dir, models=args.models, families=args.families)
    print(json.dumps({key: value for key, value in report.items() if key != "outcomes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
