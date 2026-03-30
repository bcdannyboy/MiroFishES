#!/usr/bin/env python3
"""Mark stale forecasting artifacts as historical-only archived simulations."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from forecast_archive import (
    build_historical_conformance_metadata,
    is_forecast_archived,
    write_forecast_archive_metadata,
)
from scripts.scan_forecasting_artifacts import Issue, scan_forecasting_artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive saved simulations whose persisted forecasting artifacts no longer "
            "conform to the live-readiness contract."
        )
    )
    parser.add_argument(
        "--simulation-data-dir",
        default="backend/uploads/simulations",
        help="Directory containing saved simulation folders.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write forecast_archive.json markers. Without this flag the script is dry-run only.",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Rewrite existing archive markers instead of leaving them untouched.",
    )
    parser.add_argument(
        "--allow-active",
        action="store_true",
        help=(
            "Allow writing archive markers onto currently active simulations. "
            "Use sparingly: archival excludes artifacts from active readiness gates and is not remediation."
        ),
    )
    return parser.parse_args()


def _simulation_dir_for_issue(issue: Issue, simulation_data_dir: Path) -> Path | None:
    issue_path = Path(issue.path).resolve()
    try:
        relative = issue_path.relative_to(simulation_data_dir)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return simulation_data_dir / relative.parts[0]


def main() -> int:
    args = _parse_args()
    simulation_data_dir = Path(args.simulation_data_dir).resolve()

    stats, issues = scan_forecasting_artifacts(
        simulation_data_dir,
        include_archived=True,
    )

    by_simulation: dict[Path, list[Issue]] = defaultdict(list)
    for issue in issues:
        simulation_dir = _simulation_dir_for_issue(issue, simulation_data_dir)
        if simulation_dir is not None:
            by_simulation[simulation_dir].append(issue)

    lines = [
        "Forecasting archive backfill",
        f"Root: {simulation_data_dir}",
        f"Simulation directories scanned: {stats.simulation_dirs}",
        f"Active simulations present: {stats.active_simulation_dirs}",
        f"Archived historical simulations present: {stats.archived_simulation_dirs}",
        "History scope: active + archived",
        f"Nonconforming simulations found: {len(by_simulation)}",
    ]

    if not by_simulation:
        lines.append("No nonconforming simulations need archival markers.")
        print("\n".join(lines))
        return 0

    written = 0
    already_archived = 0
    active_refused = 0
    examples: list[str] = []

    for simulation_dir in sorted(by_simulation):
        simulation_id = simulation_dir.name
        simulation_issues = by_simulation[simulation_dir]
        archived = is_forecast_archived(simulation_dir)
        if archived and not args.rewrite:
            already_archived += 1
        elif not archived and not args.allow_active:
            active_refused += 1
        elif args.apply:
            issue_codes = sorted({issue.code for issue in simulation_issues})
            write_forecast_archive_metadata(
                simulation_dir,
                reason=(
                    "Historical-only archive: this saved simulation fails the current "
                    "forecasting artifact conformance contract and is excluded from "
                    "active readiness gates."
                ),
                archived_by="archive_nonconforming_forecasting_artifacts.py",
                source="scan_forecasting_artifacts.py",
                issue_count=len(simulation_issues),
                historical_conformance=build_historical_conformance_metadata(
                    status="pending_remediation",
                    reason=(
                        "Archived simulation still has unresolved forecasting artifact "
                        "conformance gaps. Historical archive status does not suppress "
                        "those gaps from all-history audits."
                    ),
                    updated_by="archive_nonconforming_forecasting_artifacts.py",
                    issue_codes=issue_codes,
                ),
            )
            written += 1

        sample_codes = ", ".join(sorted({issue.code for issue in simulation_issues})[:3])
        examples.append(f"- {simulation_id}: {len(simulation_issues)} issues ({sample_codes})")

    if args.apply:
        lines.append(f"Archive markers written: {written}")
        if already_archived:
            lines.append(f"Already archived and left unchanged: {already_archived}")
        if active_refused:
            lines.append(
                f"Active nonconforming simulations refused archival by default: {active_refused}"
            )
            lines.append(
                "Re-run with --allow-active only if you intentionally want to exclude active failures from readiness gates."
            )
    else:
        lines.append("Dry run only. Re-run with --apply to write archive markers.")
        lines.append(
            "This tool audits the full historical backlog; it does not change active-readiness results by itself."
        )
        if active_refused:
            lines.append(
                f"Active nonconforming simulations refused archival by default: {active_refused}"
            )
            lines.append(
                "Archiving is exclusion metadata, not remediation."
            )

    lines.append("Examples:")
    lines.extend(examples[:10])
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
