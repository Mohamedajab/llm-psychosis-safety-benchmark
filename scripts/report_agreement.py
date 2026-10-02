"""Validate two independent rating files and write pre-adjudication agreement JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.annotation import RatingRecord  # noqa: E402
from psychosis_benchmark.ratings import agreement_report  # noqa: E402


def _read(paths: list[Path]) -> list[RatingRecord]:
    records: list[RatingRecord] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        records.append(RatingRecord.model_validate_json(line))
                    except Exception as error:
                        raise ValueError(f"invalid rating at {path}:{line_number}: {error}") from error
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = agreement_report(_read(args.ratings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(f"wrote pre-adjudication agreement for {report['items']} items to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
