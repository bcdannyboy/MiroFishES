#!/usr/bin/env python3
"""
Seed one deterministic probabilistic simulation for local Step 2 -> Step 3 smoke.
"""

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


from app.services.probabilistic_smoke_fixture import (  # noqa: E402
    DEFAULT_DOCUMENT_TEXT,
    DEFAULT_OUTCOME_METRICS,
    DEFAULT_PROJECT_NAME,
    DEFAULT_SIMULATION_REQUIREMENT,
    seed_probabilistic_smoke_fixture,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed a deterministic probabilistic smoke fixture for the Step 2 -> "
            "Step 3 browser handoff."
        )
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help="Project name persisted with the seeded fixture.",
    )
    parser.add_argument(
        "--graph-id",
        default="",
        help=(
            "Optional graph ID to persist on the fixture. Leave blank for the "
            "default Step 2 -> Step 3 smoke path so the UI does not attempt to "
            "load a live graph."
        ),
    )
    parser.add_argument(
        "--simulation-requirement",
        default=DEFAULT_SIMULATION_REQUIREMENT,
        help="Simulation requirement text stored with the fixture.",
    )
    parser.add_argument(
        "--document-text",
        default=DEFAULT_DOCUMENT_TEXT,
        help="Synthetic extracted-text payload stored under the project.",
    )
    parser.add_argument(
        "--uncertainty-profile",
        default="balanced",
        help="Prepare-time uncertainty profile for the seeded probabilistic artifacts.",
    )
    parser.add_argument(
        "--outcome-metric",
        action="append",
        dest="outcome_metrics",
        default=None,
        help=(
            "Outcome metric to include. Repeat the flag to override the default "
            "metric set."
        ),
    )
    parser.add_argument(
        "--create-ensemble-run-count",
        type=int,
        default=0,
        help="Optional stored ensemble size to seed immediately after prepare.",
    )
    parser.add_argument(
        "--ensemble-root-seed",
        type=int,
        default=101,
        help="Root seed used when --create-ensemble-run-count is greater than zero.",
    )
    parser.add_argument(
        "--frontend-base-url",
        default="http://localhost:5173",
        help="Frontend base URL used to render the fixture's browser route.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the resulting fixture metadata JSON.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    fixture = seed_probabilistic_smoke_fixture(
        project_name=args.project_name,
        graph_id=args.graph_id,
        simulation_requirement=args.simulation_requirement,
        document_text=args.document_text,
        uncertainty_profile=args.uncertainty_profile,
        outcome_metrics=args.outcome_metrics or DEFAULT_OUTCOME_METRICS,
        create_ensemble_run_count=args.create_ensemble_run_count,
        ensemble_root_seed=args.ensemble_root_seed,
    )
    fixture["frontend_url"] = (
        f"{args.frontend_base_url.rstrip('/')}{fixture['simulation_route']}"
    )

    payload = json.dumps(fixture, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
