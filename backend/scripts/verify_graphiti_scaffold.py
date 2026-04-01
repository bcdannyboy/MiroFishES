#!/usr/bin/env python3
"""Graphiti backend readiness verification helper."""

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
from app.services.graph_backend.live_probe import (  # noqa: E402
    apply_managed_local_graph_defaults,
    run_live_graphiti_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("integration", "smoke", "live"),
        required=True,
        help="Verification wrapper mode to summarize.",
    )
    args = parser.parse_args()

    managed_local_defaults = None
    if args.mode in {"smoke", "live"}:
        managed_local_defaults = apply_managed_local_graph_defaults()

    readiness = describe_graph_backend_readiness()
    live_probe = None
    exit_code = 0
    if args.mode in {"smoke", "live"}:
        live_probe = run_live_graphiti_probe()
        exit_code = 0 if live_probe.get("status") == "passed" else 1
    payload = {
        "mode": args.mode,
        "status": (
            "passed"
            if exit_code == 0
            else "failed"
        ),
        "readiness": readiness,
        "live_probe": live_probe,
        "note": (
            "Graphiti verification is green when the readiness surface executes "
            "and the local probe can build a client, export a seeded namespace, "
            "search merged base/runtime artifacts, and read runtime history."
        ),
        "managed_local_defaults": managed_local_defaults,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
