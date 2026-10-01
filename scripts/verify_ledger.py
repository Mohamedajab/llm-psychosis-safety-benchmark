"""Verify a Study V3 hash-linked JSONL evidence ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.evidence import verify_ledger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    report = verify_ledger(args.ledger)
    print(f"valid: {report.valid}")
    print(f"events: {report.event_count}")
    print(f"final_hash: {report.final_hash}")
    for error in report.errors:
        print(f"ERROR: {error}")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
