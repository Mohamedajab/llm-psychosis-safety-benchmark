"""Compare the planned panel with the current public OpenRouter catalogue."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.catalogue import verify_live_catalogue  # noqa: E402
from psychosis_benchmark.design import load_study  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    study = load_study(ROOT / "config" / "study-v3")
    request = urllib.request.Request(
        study.models.catalogue_endpoint,
        headers={"Accept": "application/json", "User-Agent": "psychosis-safety-benchmark/3.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:  # noqa: S310
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"ERROR: catalogue request failed: {type(error).__name__}", file=sys.stderr)
        return 1
    errors = verify_live_catalogue(study.models, payload)
    print(f"checked_at_utc: {datetime.now(UTC).isoformat()}")
    print(f"planned_endpoints: {len(study.models.models)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("all planned endpoints and result-changing catalogue fields match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
