"""Preview or execute one immutable Study V3 manifest row."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.collection import (  # noqa: E402
    CollectionError,
    collect_conversation,
    first_request_preview,
)
from psychosis_benchmark.contexts import load_context_histories  # noqa: E402
from psychosis_benchmark.design import build_manifest, load_study  # noqa: E402
from psychosis_benchmark.provider import OpenRouterClient  # noqa: E402
from psychosis_benchmark.schema import ManifestRow  # noqa: E402


def _load_manifest(path: Path) -> list[ManifestRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [ManifestRow.model_validate(row) for row in csv.DictReader(handle)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--live", action="store_true", help="make provider calls; default is preview")
    args = parser.parse_args()

    config_root = ROOT / "config" / "study-v3"
    study = load_study(config_root)
    histories = load_context_histories(config_root / "contexts")
    system_prompt = (config_root / "system_prompt.txt").read_text(encoding="utf-8")
    expected = {row.run_id: row for row in build_manifest(study, args.profile)}
    supplied = {row.run_id: row for row in _load_manifest(args.manifest)}
    if supplied.keys() != expected.keys() or any(supplied[key] != expected[key] for key in expected):
        print("ERROR: supplied manifest differs from the deterministic profile manifest", file=sys.stderr)
        return 1
    try:
        row = supplied[args.run_id]
    except KeyError:
        print("ERROR: run-id is not present in the manifest", file=sys.stderr)
        return 1
    preview = first_request_preview(
        study=study,
        row=row,
        histories=histories,
        system_prompt=system_prompt,
    )
    if not args.live:
        print(json.dumps(preview, indent=2, sort_keys=True))
        print("PREVIEW ONLY: no provider call or evidence file was created")
        return 0
    if args.ledger is None:
        print("ERROR: --ledger is required with --live", file=sys.stderr)
        return 1
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is required with --live", file=sys.stderr)
        return 1
    try:
        collect_conversation(
            study=study,
            row=row,
            histories=histories,
            system_prompt=system_prompt,
            client=OpenRouterClient(api_key),
            ledger_path=args.ledger,
        )
    except CollectionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"completed {row.run_id}; evidence: {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
