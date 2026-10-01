"""Check readiness or write a deterministic Study V3 protocol bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.protocol import (  # noqa: E402
    ProtocolFreezeError,
    build_bundle_preview,
    freeze_blockers,
    write_frozen_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    blockers = freeze_blockers(ROOT)
    if args.preview:
        print(json.dumps(build_bundle_preview(ROOT), indent=2, sort_keys=True))
    if blockers:
        print("PROTOCOL FREEZE BLOCKED")
        for blocker in blockers:
            print(f"- {blocker}")
        return 1
    if args.write:
        try:
            path = write_frozen_bundle(ROOT, args.write)
        except ProtocolFreezeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"wrote frozen protocol bundle: {path}")
    else:
        print("protocol readiness checks pass; use --write to create the bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
