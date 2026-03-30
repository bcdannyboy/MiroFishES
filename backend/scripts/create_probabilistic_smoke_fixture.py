"""
Create a deterministic probabilistic smoke fixture for local QA.

This script avoids live Zep/LLM calls by using the developer-only fixture
builder under `app.services.probabilistic_smoke_fixture`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_ROOT)
for path in (BACKEND_ROOT, REPO_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


from app.services.probabilistic_smoke_fixture import (  # noqa: E402
    DEFAULT_DOCUMENT_TEXT,
    DEFAULT_GRAPH_ID,
    DEFAULT_PROJECT_NAME,
    DEFAULT_SIMULATION_REQUIREMENT,
    SUPPORTED_SMOKE_HYBRID_VARIANTS,
    seed_probabilistic_smoke_fixture,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a deterministic probabilistic simulation fixture for local smoke testing."
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help="Project name recorded in the persisted smoke fixture.",
    )
    parser.add_argument(
        "--graph-id",
        default=DEFAULT_GRAPH_ID,
        help="Synthetic graph identifier stored in the fixture metadata. Leave empty to skip frontend graph fetches during smoke runs.",
    )
    parser.add_argument(
        "--simulation-requirement",
        default=DEFAULT_SIMULATION_REQUIREMENT,
        help="Simulation requirement written into the fixture.",
    )
    parser.add_argument(
        "--document-text",
        default=DEFAULT_DOCUMENT_TEXT,
        help="Synthetic extracted text stored under the fixture project.",
    )
    parser.add_argument(
        "--uncertainty-profile",
        default="balanced",
        help="Probabilistic uncertainty profile to persist during prepare.",
    )
    parser.add_argument(
        "--outcome-metric",
        action="append",
        dest="outcome_metrics",
        help="Outcome metric id to persist. Repeat for multiple metrics.",
    )
    parser.add_argument(
        "--run-count",
        type=int,
        default=0,
        help="Optional number of stored runs to pre-create under one ensemble.",
    )
    parser.add_argument(
        "--root-seed",
        type=int,
        default=101,
        help="Root seed used when pre-creating an ensemble.",
    )
    parser.add_argument(
        "--seed-completed-report",
        action="store_true",
        help="Also persist one synthetic completed probabilistic report with embedded report context.",
    )
    parser.add_argument(
        "--report-run-id",
        default=None,
        help="Optional run_id to bind the synthetic completed report to. Defaults to the first seeded run.",
    )
    parser.add_argument(
        "--hybrid-answer-variant",
        default="binary",
        choices=sorted(SUPPORTED_SMOKE_HYBRID_VARIANTS),
        help="Hybrid forecast workspace variant to embed in the seeded completed report.",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Optional path to also write the JSON fixture payload to disk.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = seed_probabilistic_smoke_fixture(
        project_name=args.project_name,
        graph_id=args.graph_id,
        simulation_requirement=args.simulation_requirement,
        document_text=args.document_text,
        uncertainty_profile=args.uncertainty_profile,
        outcome_metrics=args.outcome_metrics,
        create_ensemble_run_count=args.run_count,
        ensemble_root_seed=args.root_seed,
        seed_completed_report=args.seed_completed_report,
        report_run_id=args.report_run_id,
        hybrid_answer_variant=args.hybrid_answer_variant,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_file:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
