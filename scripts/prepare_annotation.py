"""Create a rater packet and a separate private blinding key from source JSONL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psychosis_benchmark.annotation import (  # noqa: E402
    SourceAnnotationItem,
    assert_packet_blinded,
    build_annotation_packet,
)


def _read_jsonl(path: Path) -> list[SourceAnnotationItem]:
    items: list[SourceAnnotationItem] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    items.append(SourceAnnotationItem.model_validate_json(line))
                except Exception as error:
                    raise ValueError(f"invalid source line {line_number}: {error}") from error
    return items


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--rater-packet", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--rubric-version", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--block-size", type=int, default=60)
    parser.add_argument("--secret-env", default="BENCHMARK_BLINDING_SECRET")
    args = parser.parse_args()
    secret_value = os.environ.get(args.secret_env)
    if secret_value is None:
        parser.error(f"environment variable {args.secret_env} is required")
    if args.rater_packet.resolve() == args.private_key.resolve():
        parser.error("rater packet and private key must be different files")
    packet = build_annotation_packet(
        _read_jsonl(args.input),
        secret=secret_value.encode(),
        rubric_version=args.rubric_version,
        seed=args.seed,
        block_size=args.block_size,
    )
    public = [item.model_dump(mode="json") for item in packet.items]
    assert_packet_blinded({"items": public})
    private = [item.model_dump(mode="json") for item in packet.key]
    _write_jsonl(args.rater_packet, public)
    _write_jsonl(args.private_key, private)
    print(f"wrote {len(public)} blinded items to {args.rater_packet}")
    print(f"wrote private key to {args.private_key}; keep it from raters and out of version control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
