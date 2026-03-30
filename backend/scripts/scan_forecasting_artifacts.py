#!/usr/bin/env python3
"""Scan persisted probabilistic artifacts for forecasting conformance gaps."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from forecast_archive import is_forecast_archived, load_forecast_archive_metadata


RULE_TITLES = {
    "prepared_missing_grounding_bundle": (
        "Probabilistic prepared simulation is missing grounding_bundle.json"
    ),
    "grounding_bundle_not_ready": "grounding_bundle.json is present but status is not ready",
    "invalid_prepared_snapshot_json": "prepared_snapshot.json could not be parsed",
    "invalid_grounding_bundle_json": "grounding_bundle.json could not be parsed",
    "invalid_report_context_json": (
        "probabilistic_report_context.json could not be parsed"
    ),
    "report_context_missing_grounding_context": (
        "Report context is missing grounding_context"
    ),
    "report_context_missing_grounding_status": (
        "Report context grounding_context is missing status"
    ),
    "report_context_missing_confidence_status": (
        "Report context is missing confidence_status"
    ),
    "report_context_missing_confidence_artifact_readiness": (
        "Report context confidence_status is missing artifact_readiness"
    ),
    "report_context_missing_calibration_artifact": (
        "Report context implies confidence support but calibration_summary.json is missing"
    ),
    "report_context_missing_backtest_artifact": (
        "Report context implies confidence support but backtest_summary.json is missing"
    ),
    "report_context_ready_missing_calibration_provenance": (
        "Report context marks confidence ready but lacks calibration_provenance"
    ),
    "report_context_ready_invalid_artifact_readiness": (
        "Report context marks confidence ready but artifact_readiness is not fully valid"
    ),
    "report_context_calibration_provenance_without_ready": (
        "Report context exposes calibration_provenance without confidence_status.ready"
    ),
    "report_context_calibrated_summary_without_ready": (
        "Report context exposes calibrated_summary without confidence_status.ready"
    ),
    "invalid_workspace_manifest_json": "forecast workspace_manifest.json could not be parsed",
    "invalid_forecast_question_json": "forecast_question.json could not be parsed",
    "invalid_forecast_answers_json": "forecast_answers.json could not be parsed",
    "forecast_answer_typed_best_estimate_shape_mismatch": (
        "Calibrated non-binary forecast answer has a typed best_estimate shape mismatch"
    ),
    "forecast_answer_calibrated_missing_backtest": (
        "Calibrated non-binary forecast answer is missing ready backtest status"
    ),
    "forecast_answer_calibrated_missing_calibration": (
        "Calibrated non-binary forecast answer is missing ready calibration status"
    ),
    "forecast_answer_calibrated_missing_resolved_cases": (
        "Calibrated non-binary forecast answer has no resolved evaluation cases"
    ),
}

QUARANTINABLE_ARCHIVED_ISSUE_CODES = frozenset(
    {
        "grounding_bundle_not_ready",
    }
)


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ScanStats:
    simulation_dirs: int
    active_simulation_dirs: int
    archived_simulation_dirs: int
    scanned_simulation_dirs: int
    probabilistic_prepared_sims: int
    report_contexts: int
    forecast_workspaces: int
    typed_forecast_answers: int
    archived_skipped: int = 0
    quarantined_archived_issues: int = 0
    quarantined_archived_simulation_dirs: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan backend/uploads/simulations for persisted probabilistic artifacts "
            "that overstate forecasting readiness."
        )
    )
    parser.add_argument(
        "--simulation-data-dir",
        default="backend/uploads/simulations",
        help="Directory containing persisted simulation artifact folders.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="Maximum example paths to print per failing rule.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help=(
            "Scan historical-only archived simulations too. By default the scanner "
            "evaluates only active forecasting artifacts."
        ),
    )
    parser.add_argument(
        "--forecast-data-dir",
        default="backend/uploads/forecasts",
        help="Directory containing persisted forecast workspace folders.",
    )
    return parser.parse_args()


def _normalize_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _read_json(path: Path, *, invalid_code: str, issues: List[Issue]) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(
            Issue(
                code=invalid_code,
                path=str(path),
                message=f"{path.name} is not valid JSON: {exc}",
            )
        )
        return None

    if not isinstance(payload, dict):
        issues.append(
            Issue(
                code=invalid_code,
                path=str(path),
                message=f"{path.name} must contain a top-level JSON object.",
            )
        )
        return None
    return payload


def _read_json_value(path: Path, *, invalid_code: str, issues: List[Issue]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(
            Issue(
                code=invalid_code,
                path=str(path),
                message=f"{path.name} is not valid JSON: {exc}",
            )
        )
        return None


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


def _issue_scope(
    issue: Issue,
    *,
    simulation_data_dir: Path,
    forecast_data_dir: Optional[Path] = None,
) -> str:
    issue_path = Path(issue.path).resolve()
    try:
        relative = issue_path.relative_to(simulation_data_dir.resolve())
    except ValueError:
        if forecast_data_dir is not None:
            try:
                issue_path.relative_to(forecast_data_dir.resolve())
            except ValueError:
                return "unknown"
            return "forecast_workspace"
        return "unknown"

    if not relative.parts:
        return "unknown"

    simulation_dir = simulation_data_dir.resolve() / relative.parts[0]
    return "archived" if is_forecast_archived(simulation_dir) else "active"


def _simulation_dir_for_issue(issue: Issue, *, simulation_data_dir: Path) -> Optional[Path]:
    issue_path = Path(issue.path).resolve()
    try:
        relative = issue_path.relative_to(simulation_data_dir.resolve())
    except ValueError:
        return None
    if not relative.parts:
        return None
    return simulation_data_dir.resolve() / relative.parts[0]


def _issue_is_explicitly_quarantined(
    issue: Issue,
    *,
    simulation_data_dir: Path,
) -> bool:
    if issue.code not in QUARANTINABLE_ARCHIVED_ISSUE_CODES:
        return False

    simulation_dir = _simulation_dir_for_issue(issue, simulation_data_dir=simulation_data_dir)
    if simulation_dir is None or not is_forecast_archived(simulation_dir):
        return False

    archive_metadata = load_forecast_archive_metadata(simulation_dir)
    if not isinstance(archive_metadata, dict):
        return False

    historical_conformance = archive_metadata.get("historical_conformance")
    if not isinstance(historical_conformance, dict):
        return False

    if _normalize_string(historical_conformance.get("status")) != "quarantined_non_ready":
        return False

    quarantined_issue_codes = {
        _normalize_string(code)
        for code in (historical_conformance.get("quarantined_issue_codes") or [])
    }
    return issue.code in quarantined_issue_codes


def _report_context_implies_confidence_support(
    context: Dict[str, Any],
    confidence_status: Optional[Dict[str, Any]],
) -> bool:
    if context.get("calibration_provenance") or context.get("calibrated_summary"):
        return True

    source_artifacts = context.get("source_artifacts")
    if isinstance(source_artifacts, dict) and (
        "calibration_summary" in source_artifacts or "backtest_summary" in source_artifacts
    ):
        return True

    if isinstance(confidence_status, dict):
        return _normalize_string(confidence_status.get("status")) in {"ready", "not_ready"}

    return False


def _scan_report_context(
    context_path: Path,
    *,
    issues: List[Issue],
) -> None:
    context = _read_json(
        context_path,
        invalid_code="invalid_report_context_json",
        issues=issues,
    )
    if context is None:
        return

    grounding_context = context.get("grounding_context")
    if not isinstance(grounding_context, dict):
        issues.append(
            Issue(
                code="report_context_missing_grounding_context",
                path=str(context_path),
                message=(
                    "probabilistic_report_context.json is missing grounding_context, "
                    "so Step 4/5 cannot explain upstream grounding truthfully."
                ),
            )
        )
    elif not _normalize_string(grounding_context.get("status")):
        issues.append(
            Issue(
                code="report_context_missing_grounding_status",
                path=str(context_path),
                message=(
                    "probabilistic_report_context.json has grounding_context but no "
                    "grounding status."
                ),
            )
        )

    confidence_status = context.get("confidence_status")
    if not isinstance(confidence_status, dict):
        issues.append(
            Issue(
                code="report_context_missing_confidence_status",
                path=str(context_path),
                message=(
                    "probabilistic_report_context.json is missing confidence_status, "
                    "so the saved report context cannot tell absent vs not_ready vs ready."
                ),
            )
        )
        confidence_status = None

    artifact_readiness = None
    if isinstance(confidence_status, dict):
        artifact_readiness = confidence_status.get("artifact_readiness")
        if not isinstance(artifact_readiness, dict):
            issues.append(
                Issue(
                    code="report_context_missing_confidence_artifact_readiness",
                    path=str(context_path),
                    message=(
                        "confidence_status is present but artifact_readiness is missing."
                    ),
                )
            )
            artifact_readiness = None

    if not _report_context_implies_confidence_support(context, confidence_status):
        return

    ensemble_dir = context_path.parent
    calibration_path = ensemble_dir / "calibration_summary.json"
    backtest_path = ensemble_dir / "backtest_summary.json"

    if not calibration_path.exists():
        issues.append(
            Issue(
                code="report_context_missing_calibration_artifact",
                path=str(context_path),
                message=(
                    "Report context implies confidence support, but "
                    "calibration_summary.json is missing from the ensemble directory."
                ),
            )
        )

    if not backtest_path.exists():
        issues.append(
            Issue(
                code="report_context_missing_backtest_artifact",
                path=str(context_path),
                message=(
                    "Report context implies confidence support, but "
                    "backtest_summary.json is missing from the ensemble directory."
                ),
            )
        )

    status = _normalize_string((confidence_status or {}).get("status"))
    if context.get("calibration_provenance") and status != "ready":
        issues.append(
            Issue(
                code="report_context_calibration_provenance_without_ready",
                path=str(context_path),
                message=(
                    "Report context exposes calibration_provenance even though "
                    "confidence_status.status is not ready."
                ),
            )
        )

    if context.get("calibrated_summary") and status != "ready":
        issues.append(
            Issue(
                code="report_context_calibrated_summary_without_ready",
                path=str(context_path),
                message=(
                    "Report context exposes calibrated_summary even though "
                    "confidence_status.status is not ready."
                ),
            )
        )

    if status != "ready":
        return

    if not isinstance(context.get("calibration_provenance"), dict):
        issues.append(
            Issue(
                code="report_context_ready_missing_calibration_provenance",
                path=str(context_path),
                message=(
                    "confidence_status.status is ready, but calibration_provenance "
                    "is missing."
                ),
            )
        )

    expected_names = ("calibration_summary", "backtest_summary", "provenance")
    for name in expected_names:
        readiness = (artifact_readiness or {}).get(name)
        if not isinstance(readiness, dict) or _normalize_string(readiness.get("status")) != "valid":
            issues.append(
                Issue(
                    code="report_context_ready_invalid_artifact_readiness",
                    path=str(context_path),
                    message=(
                        "confidence_status.status is ready, but "
                        f"artifact_readiness.{name}.status is not valid."
                    ),
                )
            )
            break


def _scan_forecast_workspace(
    workspace_dir: Path,
    *,
    issues: List[Issue],
) -> int:
    manifest_path = workspace_dir / "workspace_manifest.json"
    if manifest_path.exists():
        _read_json(
            manifest_path,
            invalid_code="invalid_workspace_manifest_json",
            issues=issues,
        )

    question_path = workspace_dir / "forecast_question.json"
    if not question_path.exists():
        return 0
    question = _read_json(
        question_path,
        invalid_code="invalid_forecast_question_json",
        issues=issues,
    )
    if question is None:
        return 0

    answers_path = workspace_dir / "forecast_answers.json"
    if not answers_path.exists():
        return 0
    answers_payload = _read_json_value(
        answers_path,
        invalid_code="invalid_forecast_answers_json",
        issues=issues,
    )
    if not isinstance(answers_payload, list):
        issues.append(
            Issue(
                code="invalid_forecast_answers_json",
                path=str(answers_path),
                message="forecast_answers.json must contain a top-level JSON array.",
            )
        )
        return 0

    question_type = _normalize_string(question.get("question_type"))
    typed_answer_count = 0
    for answer in answers_payload:
        if not isinstance(answer, dict):
            continue
        if question_type not in {"categorical", "numeric"}:
            continue
        typed_answer_count += 1
        if _normalize_string(answer.get("confidence_semantics")) != "calibrated":
            continue

        answer_payload = answer.get("answer_payload")
        if not isinstance(answer_payload, dict):
            answer_payload = {}
        best_estimate = answer_payload.get("best_estimate")
        if not isinstance(best_estimate, dict):
            best_estimate = {}
        best_estimate_type = _normalize_string(best_estimate.get("value_type"))
        best_estimate_semantics = _normalize_string(
            best_estimate.get("value_semantics") or best_estimate.get("semantics")
        )

        if question_type == "categorical":
            if best_estimate_type not in {"categorical_distribution", "distribution"} or best_estimate_semantics != "forecast_distribution":
                issues.append(
                    Issue(
                        code="forecast_answer_typed_best_estimate_shape_mismatch",
                        path=str(answers_path),
                        message=(
                            "Calibrated categorical forecast answers must store best_estimate "
                            "as a forecast_distribution with categorical_distribution payloads."
                        ),
                    )
                )
        elif question_type == "numeric":
            if best_estimate_type != "numeric_interval" or best_estimate_semantics != "numeric_interval_estimate":
                issues.append(
                    Issue(
                        code="forecast_answer_typed_best_estimate_shape_mismatch",
                        path=str(answers_path),
                        message=(
                            "Calibrated numeric forecast answers must store best_estimate "
                            "as a numeric_interval_estimate payload."
                        ),
                    )
                )

        backtest_summary = answer.get("backtest_summary")
        if not isinstance(backtest_summary, dict):
            backtest_summary = {}
        if _normalize_string(backtest_summary.get("status")) not in {"available", "ready"}:
            issues.append(
                Issue(
                    code="forecast_answer_calibrated_missing_backtest",
                    path=str(answers_path),
                    message=(
                        "Calibrated non-binary forecast answers require backtest_summary.status "
                        "to be available or ready."
                    ),
                )
            )

        calibration_summary = answer.get("calibration_summary")
        if not isinstance(calibration_summary, dict):
            calibration_summary = {}
        if _normalize_string(calibration_summary.get("status")) != "ready":
            issues.append(
                Issue(
                    code="forecast_answer_calibrated_missing_calibration",
                    path=str(answers_path),
                    message=(
                        "Calibrated non-binary forecast answers require calibration_summary.status "
                        "to be ready."
                    ),
                )
            )

        evaluation_summary = answer.get("evaluation_summary")
        if not isinstance(evaluation_summary, dict):
            evaluation_summary = {}
        resolved_case_count = evaluation_summary.get("resolved_case_count", 0)
        try:
            resolved_case_count = int(resolved_case_count or 0)
        except (TypeError, ValueError):
            resolved_case_count = 0
        if resolved_case_count <= 0:
            issues.append(
                Issue(
                    code="forecast_answer_calibrated_missing_resolved_cases",
                    path=str(answers_path),
                    message=(
                        "Calibrated non-binary forecast answers require at least one resolved evaluation case."
                    ),
                )
            )
    return typed_answer_count


def scan_forecasting_artifacts(
    simulation_data_dir: Path,
    *,
    forecast_data_dir: Optional[Path] = None,
    include_archived: bool = False,
    apply_historical_quarantine: bool = True,
) -> tuple[ScanStats, List[Issue]]:
    issues: List[Issue] = []

    simulation_dir_exists = simulation_data_dir.exists()
    forecast_dir_exists = forecast_data_dir is not None and forecast_data_dir.exists()

    if not simulation_dir_exists and not forecast_dir_exists:
        return ScanStats(
            simulation_dirs=0,
            active_simulation_dirs=0,
            archived_simulation_dirs=0,
            scanned_simulation_dirs=0,
            probabilistic_prepared_sims=0,
            report_contexts=0,
            forecast_workspaces=0,
            typed_forecast_answers=0,
            archived_skipped=0,
        ), issues

    simulation_dirs = (
        sorted(path for path in simulation_data_dir.iterdir() if path.is_dir())
        if simulation_dir_exists
        else []
    )

    archived_dirs = [
        path for path in simulation_dirs if is_forecast_archived(path)
    ]
    active_dirs = [path for path in simulation_dirs if path not in archived_dirs]

    probabilistic_prepared_sims = 0
    report_contexts = 0
    forecast_workspaces = 0
    typed_forecast_answers = 0
    archived_skipped = len(archived_dirs) if not include_archived else 0

    scanned_dirs = active_dirs if not include_archived else simulation_dirs

    for simulation_dir in scanned_dirs:
        prepared_snapshot_path = simulation_dir / "prepared_snapshot.json"
        if prepared_snapshot_path.exists():
            prepared_snapshot = _read_json(
                prepared_snapshot_path,
                invalid_code="invalid_prepared_snapshot_json",
                issues=issues,
            )
            if prepared_snapshot and _is_probabilistic_prepared(prepared_snapshot):
                probabilistic_prepared_sims += 1
                grounding_bundle_path = simulation_dir / "grounding_bundle.json"
                if not grounding_bundle_path.exists():
                    issues.append(
                        Issue(
                            code="prepared_missing_grounding_bundle",
                            path=str(prepared_snapshot_path),
                            message=(
                                "prepared_snapshot.json marks this simulation as "
                                "probabilistic, but grounding_bundle.json is missing."
                            ),
                        )
                    )
                else:
                    grounding_bundle = _read_json(
                        grounding_bundle_path,
                        invalid_code="invalid_grounding_bundle_json",
                        issues=issues,
                    )
                    if grounding_bundle is not None:
                        status = _normalize_string(grounding_bundle.get("status"))
                        if status != "ready":
                            issues.append(
                                Issue(
                                    code="grounding_bundle_not_ready",
                                    path=str(grounding_bundle_path),
                                    message=(
                                        "grounding_bundle.json exists but status is "
                                        f"{status or '<missing>'}, not ready."
                                    ),
                                )
                            )

        for context_path in sorted(
            simulation_dir.glob("ensemble/ensemble_*/probabilistic_report_context.json")
        ):
            report_contexts += 1
            _scan_report_context(context_path, issues=issues)

    if forecast_data_dir is not None and forecast_data_dir.exists():
        for workspace_dir in sorted(path for path in forecast_data_dir.iterdir() if path.is_dir()):
            forecast_workspaces += 1
            typed_forecast_answers += _scan_forecast_workspace(
                workspace_dir,
                issues=issues,
            )

    unresolved_issues: List[Issue] = []
    quarantined_archived_simulations: set[Path] = set()
    quarantined_archived_issue_count = 0
    for issue in issues:
        if include_archived and apply_historical_quarantine and _issue_is_explicitly_quarantined(
            issue,
            simulation_data_dir=simulation_data_dir,
        ):
            quarantined_archived_issue_count += 1
            simulation_dir = _simulation_dir_for_issue(
                issue,
                simulation_data_dir=simulation_data_dir,
            )
            if simulation_dir is not None:
                quarantined_archived_simulations.add(simulation_dir)
            continue
        unresolved_issues.append(issue)

    stats = ScanStats(
        simulation_dirs=len(simulation_dirs),
        active_simulation_dirs=len(active_dirs),
        archived_simulation_dirs=len(archived_dirs),
        scanned_simulation_dirs=len(scanned_dirs),
        probabilistic_prepared_sims=probabilistic_prepared_sims,
        report_contexts=report_contexts,
        forecast_workspaces=forecast_workspaces,
        typed_forecast_answers=typed_forecast_answers,
        archived_skipped=archived_skipped,
        quarantined_archived_issues=quarantined_archived_issue_count,
        quarantined_archived_simulation_dirs=len(quarantined_archived_simulations),
    )
    return stats, unresolved_issues


def _format_summary(
    *,
    simulation_data_dir: Path,
    forecast_data_dir: Optional[Path],
    stats: ScanStats,
    issues: Iterable[Issue],
    max_examples: int,
) -> str:
    issues = list(issues)
    grouped: Dict[str, List[Issue]] = defaultdict(list)
    scoped_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    scope_totals: Counter[str] = Counter()
    for issue in issues:
        grouped[issue.code].append(issue)
        scope = _issue_scope(
            issue,
            simulation_data_dir=simulation_data_dir,
            forecast_data_dir=forecast_data_dir,
        )
        scoped_counts[issue.code][scope] += 1
        scope_totals[scope] += 1

    lines = [
        "Forecasting artifact conformance scan",
        f"Root: {simulation_data_dir}",
        f"Simulation directories scanned: {stats.simulation_dirs}",
        f"Active simulations scanned: {stats.active_simulation_dirs}",
        f"Archived historical simulations present: {stats.archived_simulation_dirs}",
        f"Directories actually inspected: {stats.scanned_simulation_dirs}",
        f"Probabilistic prepared simulations scanned: {stats.probabilistic_prepared_sims}",
        f"Probabilistic report contexts scanned: {stats.report_contexts}",
        f"Forecast workspaces scanned: {stats.forecast_workspaces}",
        f"Typed forecast answers scanned: {stats.typed_forecast_answers}",
    ]
    if stats.archived_skipped:
        lines.append("History scope: active-only")
        lines.append(f"Archived historical simulations skipped by default: {stats.archived_skipped}")
        lines.append(
            "This run is active-only. Re-run with --include-archived for a full historical scan."
        )
    elif stats.archived_simulation_dirs and stats.scanned_simulation_dirs:
        lines.append("History scope: active + archived")
    else:
        lines.append("History scope: active-only")

    if not issues:
        if (
            stats.probabilistic_prepared_sims == 0
            and stats.report_contexts == 0
            and stats.forecast_workspaces == 0
        ):
            lines.append(
                "Result: no persisted probabilistic simulations or report contexts were found."
            )
            lines.append(
                "This is not artifact proof of forecasting readiness; it only means the active scan had nothing to evaluate."
            )
            if stats.archived_skipped:
                lines.append(
                    "Historical archived simulations were not audited in this run."
                )
        else:
            if stats.archived_skipped:
                lines.append(
                    "Result: no conformance failures found in the active forecasting artifacts."
                )
                lines.append(
                    "Historical archived simulations were not audited in this run."
                )
            else:
                if stats.quarantined_archived_issues:
                    lines.append(
                        "Result: no unresolved conformance failures found in the scanned forecasting artifacts."
                    )
                    lines.append(
                        "Archived historical non-ready issues quarantined explicitly: "
                        f"{stats.quarantined_archived_issues} across "
                        f"{stats.quarantined_archived_simulation_dirs} simulations"
                    )
                    lines.append(
                        "Archived quarantined simulations remain read-only and non-ready."
                    )
                else:
                    lines.append(
                        "Result: no conformance failures found in the scanned forecasting artifacts."
                    )
        return "\n".join(lines)

    lines.append(
        f"Result: FAIL. Found {len(issues)} issues across {len(grouped)} failing rules."
    )
    lines.append(
        "A green broad repo verify would not catch these persisted artifact problems."
    )
    if scope_totals:
        lines.append(
            "Issue scope summary: "
            f"active={scope_totals.get('active', 0)}, "
            f"archived={scope_totals.get('archived', 0)}, "
            f"forecast_workspace={scope_totals.get('forecast_workspace', 0)}, "
            f"unknown={scope_totals.get('unknown', 0)}"
        )
        if stats.quarantined_archived_issues:
            lines.append(
                "Archived historical non-ready issues quarantined explicitly: "
                f"{stats.quarantined_archived_issues} across "
                f"{stats.quarantined_archived_simulation_dirs} simulations"
            )
            lines.append(
                "Archived quarantined simulations remain read-only and non-ready."
            )
        if scope_totals.get("archived", 0):
            lines.append(
                "Archived historical failures remain counted in all-history scans; archive markers classify read-only history and do not suppress failures."
            )

    for code in sorted(grouped):
        examples = grouped[code][:max_examples]
        active_count = scoped_counts[code].get("active", 0)
        archived_count = scoped_counts[code].get("archived", 0)
        unknown_count = scoped_counts[code].get("unknown", 0)
        lines.append("")
        lines.append(
            f"- {RULE_TITLES.get(code, code)}: {len(grouped[code])} "
            f"(active: {active_count}, archived: {archived_count}, unknown: {unknown_count})"
        )
        for issue in examples:
            scope = _issue_scope(
                issue,
                simulation_data_dir=simulation_data_dir,
                forecast_data_dir=forecast_data_dir,
            )
            lines.append(f"  [{scope}] {issue.path}")
            lines.append(f"    {issue.message}")

    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    simulation_data_dir = Path(args.simulation_data_dir).resolve()
    forecast_data_dir = Path(args.forecast_data_dir).resolve()
    stats, issues = scan_forecasting_artifacts(
        simulation_data_dir,
        forecast_data_dir=forecast_data_dir,
        include_archived=args.include_archived,
    )
    print(
        _format_summary(
            simulation_data_dir=simulation_data_dir,
            forecast_data_dir=forecast_data_dir,
            stats=stats,
            issues=issues,
            max_examples=max(1, args.max_examples),
        )
    )
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
