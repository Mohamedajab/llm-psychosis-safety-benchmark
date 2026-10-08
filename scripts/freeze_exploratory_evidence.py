"""Freeze and verify a closed exploratory dataset without modifying the original evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_sized_exploration import audit_batch  # noqa: E402

from psychosis_benchmark.evidence_freeze import (  # noqa: E402
    file_hash,
    freeze_batch,
    verify_freeze,
    write_new_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verified = verify_freeze(args.snapshot_dir)
        if args.public_receipt:
            receipt = json.loads(args.public_receipt.read_text(encoding="utf-8"))
            if receipt["content_root_sha256"] != verified["content_root_sha256"] or receipt[
                "archive_sha256"
            ] != file_hash(args.snapshot_dir.with_suffix(".zip")):
                raise ValueError("frozen snapshot or archive differs from the public receipt")
            verified["archive_verified"] = True
        print(json.dumps(verified))
        return
    if not args.batch_dir or not args.public_receipt:
        parser.error("batch directory and new public receipt are required")
    if args.public_receipt.exists():
        parser.error("public receipt already exists; never overwrite a freeze")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = freeze_batch(args.batch_dir, args.snapshot_dir, audit=audit_batch, source_commit=commit)
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    write_new_json(args.public_receipt, receipt)
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "content_root_sha256",
                    "archive_sha256",
                    "verified_ledgers",
                    "stored_responses",
                    "completed_conversations",
                    "terminal_failed_conversations",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
