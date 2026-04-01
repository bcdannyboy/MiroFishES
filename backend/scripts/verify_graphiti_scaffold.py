#!/usr/bin/env python3
"""Prompt 1 Graphiti scaffold verification helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (BACKEND_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


from app.services.graph_backend import describe_graph_backend_readiness  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("integration", "smoke", "live"),
        required=True,
        help="Verification wrapper mode to summarize.",
    )
    args = parser.parse_args()

    readiness = describe_graph_backend_readiness()
    payload = {
        "mode": args.mode,
        "status": "scaffold-ready",
        "readiness": readiness,
        "note": (
            "Prompt 1 wrapper sanity is green when the readiness surface executes "
            "and reports honest dependency/config status. Later prompts replace this "
            "with real Graphiti backend flows."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
