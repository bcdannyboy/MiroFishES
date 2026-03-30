#!/usr/bin/env python3
"""Migrate archived forecasting artifacts into the current historical contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.grounding import build_grounding_context
from app.services.grounding_bundle_builder import GroundingBundleBuilder
from app.services.probabilistic_report_context import ProbabilisticReportContextBuilder
from forecast_archive import (
    build_historical_conformance_metadata,
    is_forecast_archived,
    load_forecast_archive_metadata,
)
from scripts.scan_forecasting_artifacts import (
    QUARANTINABLE_ARCHIVED_ISSUE_CODES,
    scan_forecasting_artifacts,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair archived forecasting artifacts into the current report/grounding "
            "contract and explicitly quarantine irreducible non-ready history."
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
        help="Write migrated artifacts. Without this flag the script is dry-run only.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _is_probabilistic_prepared(snapshot: Dict[str, Any]) -> bool:
    if snapshot.get("probabilistic_mode") is True:
        return True
    if _normalize_string(snapshot.get("mode")) == "probabilistic":
        return True

    prepared_summary = snapshot.get("prepared_artifact_summary")
    if isinstance(prepared_summary, dict):
        if prepared_summary.get("probabilistic_mode") is True:
            return True
        if _normalize_string(prepared_summary.get("mode")) == "probabilistic":
            return True
    return False


def _resolve_lineage(snapshot: Dict[str, Any], report_context: Optional[Dict[str, Any]]) -> tuple[str, Optional[str]]:
    lineage = snapshot.get("lineage")
    if not isinstance(lineage, dict):
        lineage = ((report_context or {}).get("prepared_artifact_summary") or {}).get("lineage", {})
    if not isinstance(lineage, dict):
        lineage = {}
    project_id = _normalize_string(lineage.get("project_id"))
    graph_id = _normalize_string(lineage.get("graph_id")) or None
    return project_id, graph_id


def _patch_report_context(
    *,
    context: Dict[str, Any],
    context_path: Path,
    simulation_id: str,
    grounding_bundle: Dict[str, Any],
    report_builder: ProbabilisticReportContextBuilder,
    grounding_builder: GroundingBundleBuilder,
) -> bool:
    changed = False
    grounding_context = build_grounding_context(grounding_bundle)
    grounding_summary = grounding_builder.build_summary(grounding_bundle)

    current_grounding_context = context.get("grounding_context")
    if not isinstance(current_grounding_context, dict) or not _normalize_string(
        current_grounding_context.get("status")
    ):
        context["grounding_context"] = grounding_context
        changed = True

    prepared_artifact_summary = context.get("prepared_artifact_summary")
    if isinstance(prepared_artifact_summary, dict):
        current_grounding_summary = prepared_artifact_summary.get("grounding_summary")
        if not isinstance(current_grounding_summary, dict) or not _normalize_string(
            current_grounding_summary.get("status")
        ):
            prepared_artifact_summary["grounding_summary"] = grounding_summary
            changed = True

    ensemble_id = _normalize_string(context.get("ensemble_id"))
    if not ensemble_id:
        ensemble_id = context_path.parent.name.replace("ensemble_", "", 1)

    confidence_inspection = report_builder._inspect_confidence_artifacts(
        ensemble_dir=str(context_path.parent),
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
    )
    generated_confidence_status = report_builder._build_confidence_status(
        confidence_inspection
    )

    current_confidence_status = context.get("confidence_status")
    if not isinstance(current_confidence_status, dict):
        context["confidence_status"] = generated_confidence_status
        changed = True
    else:
        merged_confidence_status = dict(current_confidence_status)
        if not _normalize_string(merged_confidence_status.get("status")):
            merged_confidence_status["status"] = generated_confidence_status["status"]
            changed = True
        if not isinstance(merged_confidence_status.get("artifact_readiness"), dict):
            merged_confidence_status["artifact_readiness"] = generated_confidence_status[
                "artifact_readiness"
            ]
            changed = True
        if not _normalize_string(merged_confidence_status.get("boundary_note")):
            merged_confidence_status["boundary_note"] = generated_confidence_status[
                "boundary_note"
            ]
            changed = True

        for key in (
            "supported_metric_ids",
            "ready_metric_ids",
            "not_ready_metric_ids",
            "gating_reasons",
            "warnings",
        ):
            if not isinstance(merged_confidence_status.get(key), list):
                merged_confidence_status[key] = generated_confidence_status.get(key, [])
                changed = True

        context["confidence_status"] = merged_confidence_status

    return changed


def _update_archive_metadata(
    *,
    simulation_dir: Path,
    grounding_bundle: Dict[str, Any],
    issue_codes: list[str],
) -> Dict[str, Any]:
    archive_metadata = load_forecast_archive_metadata(simulation_dir) or {
        "artifact_type": "forecast_archive",
        "schema_version": "forecast.archive.v1",
        "archive_scope": "historical_read_only",
        "reason": (
            "Historical saved simulation retained for read-only access after "
            "forecasting contract migration."
        ),
    }

    grounding_status = _normalize_string(grounding_bundle.get("status")) or "unavailable"
    warnings = grounding_bundle.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    unresolved_issue_codes = sorted({_normalize_string(code) for code in issue_codes if _normalize_string(code)})

    if not unresolved_issue_codes:
        historical_conformance = build_historical_conformance_metadata(
            status="remediated",
            reason=(
                "Archived simulation artifacts were migrated into the current "
                "forecasting contract without remaining unresolved artifact "
                "conformance gaps."
            ),
            updated_by="migrate_historical_forecasting_artifacts.py",
            details={
                "grounding_status": grounding_status,
            },
        )
    elif set(unresolved_issue_codes).issubset(QUARANTINABLE_ARCHIVED_ISSUE_CODES):
        historical_conformance = build_historical_conformance_metadata(
            status="quarantined_non_ready",
            reason=(
                "Archived simulation remains non-ready after migration. The current "
                "artifact set still does not provide the grounding evidence required "
                "for ready status, so this simulation stays read-only historical "
                "evidence and is excluded from active readiness."
            ),
            updated_by="migrate_historical_forecasting_artifacts.py",
            issue_codes=unresolved_issue_codes,
            quarantined_issue_codes=unresolved_issue_codes,
            details={
                "grounding_status": grounding_status,
                "grounding_warnings": warnings,
            },
        )
    else:
        historical_conformance = build_historical_conformance_metadata(
            status="pending_remediation",
            reason=(
                "Archived simulation still has unresolved forecasting artifact "
                "conformance gaps after migration and cannot be marked remediated "
                "or explicitly quarantined."
            ),
            updated_by="migrate_historical_forecasting_artifacts.py",
            issue_codes=unresolved_issue_codes,
            details={
                "grounding_status": grounding_status,
                "grounding_warnings": warnings,
            },
        )

    archive_metadata["historical_conformance"] = historical_conformance
    return archive_metadata


def main() -> int:
    args = _parse_args()
    simulation_data_dir = Path(args.simulation_data_dir).resolve()

    grounding_builder = GroundingBundleBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    report_builder = ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )

    archived_simulation_dirs = sorted(
        path
        for path in simulation_data_dir.iterdir()
        if path.is_dir() and is_forecast_archived(path)
    ) if simulation_data_dir.exists() else []

    archived_probabilistic_simulations = 0
    grounding_bundles_created = 0
    report_contexts_patched = 0
    archive_metadata_updated = 0
    quarantined_non_ready = 0
    archived_probabilistic_dirs: list[Path] = []

    for simulation_dir in archived_simulation_dirs:
        prepared_snapshot_path = simulation_dir / "prepared_snapshot.json"
        prepared_snapshot = _read_json(prepared_snapshot_path)
        if not prepared_snapshot or not _is_probabilistic_prepared(prepared_snapshot):
            continue

        archived_probabilistic_simulations += 1
        archived_probabilistic_dirs.append(simulation_dir)
        simulation_id = _normalize_string(
            prepared_snapshot.get("simulation_id") or simulation_dir.name
        ) or simulation_dir.name

        existing_context_path = next(
            iter(
                sorted(
                    simulation_dir.glob("ensemble/ensemble_*/probabilistic_report_context.json")
                )
            ),
            None,
        )
        existing_context = _read_json(existing_context_path) if existing_context_path else None

        grounding_bundle_path = simulation_dir / "grounding_bundle.json"
        grounding_bundle = _read_json(grounding_bundle_path)
        if grounding_bundle is None:
            project_id, graph_id = _resolve_lineage(prepared_snapshot, existing_context)
            grounding_bundle = grounding_builder.build_bundle(
                simulation_id=simulation_id,
                project_id=project_id,
                graph_id=graph_id,
            )
            if args.apply:
                _write_json(grounding_bundle_path, grounding_bundle)
            grounding_bundles_created += 1

        for context_path in sorted(
            simulation_dir.glob("ensemble/ensemble_*/probabilistic_report_context.json")
        ):
            context = _read_json(context_path)
            if context is None:
                continue
            if _patch_report_context(
                context=context,
                context_path=context_path,
                simulation_id=simulation_id,
                grounding_bundle=grounding_bundle,
                report_builder=report_builder,
                grounding_builder=grounding_builder,
            ):
                if args.apply:
                    _write_json(context_path, context)
                report_contexts_patched += 1

    if args.apply and archived_probabilistic_dirs:
        _, unresolved_issues = scan_forecasting_artifacts(
            simulation_data_dir,
            include_archived=True,
            apply_historical_quarantine=False,
        )
        issue_codes_by_simulation: dict[Path, list[str]] = {}
        for issue in unresolved_issues:
            issue_path = Path(issue.path).resolve()
            try:
                relative = issue_path.relative_to(simulation_data_dir)
            except ValueError:
                continue
            if not relative.parts:
                continue
            simulation_dir = simulation_data_dir / relative.parts[0]
            issue_codes_by_simulation.setdefault(simulation_dir, []).append(issue.code)

        for simulation_dir in archived_probabilistic_dirs:
            grounding_bundle = _read_json(simulation_dir / "grounding_bundle.json") or {}
            archive_metadata = _update_archive_metadata(
                simulation_dir=simulation_dir,
                grounding_bundle=grounding_bundle,
                issue_codes=issue_codes_by_simulation.get(simulation_dir, []),
            )
            if (
                isinstance(archive_metadata.get("historical_conformance"), dict)
                and archive_metadata["historical_conformance"].get("status")
                == "quarantined_non_ready"
            ):
                quarantined_non_ready += 1
            _write_json(simulation_dir / "forecast_archive.json", archive_metadata)
            archive_metadata_updated += 1
    else:
        for simulation_dir in archived_probabilistic_dirs:
            grounding_bundle = _read_json(simulation_dir / "grounding_bundle.json") or {}
            archive_metadata = _update_archive_metadata(
                simulation_dir=simulation_dir,
                grounding_bundle=grounding_bundle,
                issue_codes=["grounding_bundle_not_ready"]
                if _normalize_string(grounding_bundle.get("status")) != "ready"
                else [],
            )
            if (
                isinstance(archive_metadata.get("historical_conformance"), dict)
                and archive_metadata["historical_conformance"].get("status")
                == "quarantined_non_ready"
            ):
                quarantined_non_ready += 1
            archive_metadata_updated += 1

    lines = [
        "Historical forecasting artifact migration",
        f"Root: {simulation_data_dir}",
        f"Archived simulations inspected: {len(archived_simulation_dirs)}",
        f"Archived probabilistic simulations inspected: {archived_probabilistic_simulations}",
        f"Grounding bundles created: {grounding_bundles_created}",
        f"Report contexts patched: {report_contexts_patched}",
        f"Archive metadata updated: {archive_metadata_updated}",
        f"Historical non-ready quarantined explicitly: {quarantined_non_ready}",
    ]
    if args.apply:
        lines.append("Apply mode: wrote migrated historical artifacts.")
    else:
        lines.append("Dry run only. Re-run with --apply to write migrated historical artifacts.")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
