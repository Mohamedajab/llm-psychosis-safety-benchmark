"""Start the loopback-only research lab with optional, explicit local collection controls."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from streamlit.web import cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-collection-controls", action="store_true")
    parser.add_argument("--api-key-stdin", action="store_true")
    args = parser.parse_args()
    if args.api_key_stdin:
        key = sys.stdin.readline().strip()
        if not key:
            parser.error("a key is required on stdin")
        os.environ["OPENROUTER_API_KEY"] = key
    if args.enable_collection_controls:
        os.environ["BENCHMARK_ENABLE_COLLECTION_CONTROLS"] = "1"
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.argv = [
        "streamlit",
        "run",
        str(root / "streamlit_app.py"),
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--server.headless=true",
    ]
    cli.main()


if __name__ == "__main__":
    main()
