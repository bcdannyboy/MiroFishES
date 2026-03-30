import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "scan_forecasting_artifacts.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_forecast_workspace(
    root: Path,
    *,
    forecast_id: str,
    question_type: str,
    question_spec: dict,
    answer_payload: dict,
    confidence_semantics: str = "calibrated",
    backtest_status: str = "available",
    calibration_status: str = "ready",
    resolved_case_count: int = 3,
) -> None:
    workspace_dir = root / forecast_id
    _write_json(
        workspace_dir / "workspace_manifest.json",
        {
            "artifact_type": "forecast_workspace_manifest",
            "forecast_id": forecast_id,
            "question_type": question_type,
        },
    )
    _write_json(
        workspace_dir / "forecast_question.json",
        {
            "forecast_id": forecast_id,
            "project_id": "proj-1",
            "title": f"{question_type.title()} forecast",
            "question": "Fixture question",
            "question_text": "Fixture question",
            "question_type": question_type,
            "question_spec": question_spec,
            "status": "active",
            "horizon": {"type": "date", "value": "2026-12-31"},
            "issue_timestamp": "2026-03-30T09:00:00",
            "created_at": "2026-03-30T09:00:00",
            "updated_at": "2026-03-30T09:00:00",
        },
    )
    _write_json(
        workspace_dir / "forecast_answers.json",
        [
            {
                "answer_id": f"{forecast_id}-answer-1",
                "forecast_id": forecast_id,
                "answer_type": "hybrid_forecast",
                "summary": "Fixture answer",
                "worker_ids": ["worker-base-rate"],
                "prediction_entry_ids": ["entry-1"],
                "confidence_semantics": confidence_semantics,
                "created_at": "2026-03-30T10:00:00",
                "answer_payload": answer_payload,
                "evaluation_summary": {
                    "status": "available",
                    "case_count": resolved_case_count,
                    "resolved_case_count": resolved_case_count,
                },
                "benchmark_summary": {"status": "available"},
                "backtest_summary": {"status": backtest_status},
                "calibration_summary": {"status": calibration_status},
                "confidence_basis": {
                    "status": "available" if resolved_case_count > 0 else "unavailable",
                    "benchmark_status": "available",
                    "backtest_status": backtest_status,
                    "calibration_status": calibration_status,
                },
            }
        ],
    )


def _write_archive_marker(
    simulation_dir: Path,
    *,
    historical_conformance: dict | None = None,
) -> None:
    payload = {
        "artifact_type": "forecast_archive",
        "schema_version": "forecast.archive.v1",
        "archived_at": "2026-03-29T12:00:00",
        "archive_scope": "historical_read_only",
        "reason": "Pre-contract saved simulation is retained for history only.",
    }
    if historical_conformance is not None:
        payload["historical_conformance"] = historical_conformance
    _write_json(simulation_dir / "forecast_archive.json", payload)


def test_scan_forecasting_artifacts_passes_for_conforming_fixture(tmp_path):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-001"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "ready",
        },
    )
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
        },
    )
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "probability_mode": "empirical",
            "grounding_context": {
                "status": "ready",
                "boundary_note": "fixture",
            },
            "confidence_status": {
                "status": "ready",
                "artifact_readiness": {
                    "calibration_summary": {"status": "valid"},
                    "backtest_summary": {"status": "valid"},
                    "provenance": {"status": "valid"},
                },
            },
            "calibration_provenance": {
                "mode": "backtested",
            },
            "source_artifacts": {
                "grounding_bundle": "grounding_bundle.json",
                "calibration_summary": "calibration_summary.json",
                "backtest_summary": "backtest_summary.json",
            },
        },
    )

    result = _run_script("--simulation-data-dir", str(simulations_dir))

    assert result.returncode == 0, result.stdout
    assert "Result: no conformance failures found" in result.stdout
    assert "History scope: active-only" in result.stdout


def test_scan_forecasting_artifacts_flags_grounding_and_confidence_overclaims(tmp_path):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-002"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "unavailable",
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "probability_mode": "empirical",
            "grounding_context": {
                "boundary_note": "missing status",
            },
            "confidence_status": {
                "status": "ready",
            },
            "source_artifacts": {
                "calibration_summary": "calibration_summary.json",
                "backtest_summary": "backtest_summary.json",
            },
        },
    )

    result = _run_script("--simulation-data-dir", str(simulations_dir))

    assert result.returncode == 2
    assert "grounding_bundle.json is present but status is not ready" in result.stdout
    assert "Report context grounding_context is missing status" in result.stdout
    assert "Report context confidence_status is missing artifact_readiness" in result.stdout
    assert (
        "Report context implies confidence support but calibration_summary.json is missing"
        in result.stdout
    )
    assert (
        "Report context implies confidence support but backtest_summary.json is missing"
        in result.stdout
    )


def test_scan_forecasting_artifacts_skips_archived_historical_simulations_by_default(tmp_path):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-archived"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "unavailable",
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "confidence_status": {
                "status": "ready",
            },
        },
    )
    _write_archive_marker(simulation_dir)

    default_result = _run_script("--simulation-data-dir", str(simulations_dir))

    assert default_result.returncode == 0, default_result.stdout
    assert "Archived historical simulations skipped by default: 1" in default_result.stdout
    assert "This run is active-only. Re-run with --include-archived for a full historical scan." in default_result.stdout
    assert "Result: no persisted probabilistic simulations or report contexts were found." in default_result.stdout
    assert "Historical archived simulations were not audited in this run." in default_result.stdout
    assert "grounding_bundle.json is present but status is not ready" not in default_result.stdout

    included_result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--include-archived",
    )

    assert included_result.returncode == 2
    assert "History scope: active + archived" in included_result.stdout
    assert "grounding_bundle.json is present but status is not ready" in included_result.stdout


def test_scan_forecasting_artifacts_distinguishes_active_and_archived_issue_scope(tmp_path):
    simulations_dir = tmp_path / "simulations"
    active_sim_dir = simulations_dir / "sim-active"
    archived_sim_dir = simulations_dir / "sim-archived"

    _write_json(
        active_sim_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        active_sim_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "unavailable",
        },
    )
    _write_json(
        archived_sim_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        archived_sim_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "unavailable",
        },
    )
    _write_archive_marker(archived_sim_dir)

    result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--include-archived",
    )

    assert result.returncode == 2, result.stdout
    assert "Issue scope summary: active=1, archived=1" in result.stdout
    assert "[active]" in result.stdout
    assert "[archived]" in result.stdout
    assert "Archived historical failures remain counted in all-history scans" in result.stdout


def test_scan_forecasting_artifacts_accepts_explicit_archived_grounding_quarantine(tmp_path):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-archived"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "unavailable",
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "grounding_context": {
                "status": "unavailable",
            },
            "confidence_status": {
                "status": "absent",
                "artifact_readiness": {
                    "calibration_summary": {"status": "absent"},
                    "backtest_summary": {"status": "absent"},
                    "provenance": {"status": "absent"},
                },
            },
        },
    )
    _write_archive_marker(
        simulation_dir,
        historical_conformance={
            "schema_version": "forecast.archive.conformance.v1",
            "status": "quarantined_non_ready",
            "reason": "Grounding remains unavailable for archived read-only history.",
            "quarantined_issue_codes": ["grounding_bundle_not_ready"],
            "updated_at": "2026-03-30T12:00:00",
            "updated_by": "fixture",
        },
    )

    result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--include-archived",
    )

    assert result.returncode == 0, result.stdout
    assert "History scope: active + archived" in result.stdout
    assert "Archived historical non-ready issues quarantined explicitly: 1 across 1 simulations" in result.stdout
    assert "Result: no unresolved conformance failures found in the scanned forecasting artifacts." in result.stdout
    assert "Archived quarantined simulations remain read-only and non-ready." in result.stdout


def test_scan_forecasting_artifacts_handles_missing_simulation_directory(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    result = _run_script("--simulation-data-dir", str(missing_dir))

    assert result.returncode == 0, result.stdout
    assert "Simulation directories scanned: 0" in result.stdout
    assert "Directories actually inspected: 0" in result.stdout
    assert "Result: no persisted probabilistic simulations or report contexts were found." in result.stdout


def test_scan_forecasting_artifacts_accepts_typed_calibrated_forecast_workspaces(tmp_path):
    simulations_dir = tmp_path / "simulations"
    forecasts_dir = tmp_path / "forecasts"

    _write_forecast_workspace(
        forecasts_dir,
        forecast_id="forecast-categorical",
        question_type="categorical",
        question_spec={"outcome_labels": ["win", "stretch", "miss"]},
        answer_payload={
            "question_type": "categorical",
            "best_estimate": {
                "value_type": "categorical_distribution",
                "value_semantics": "forecast_distribution",
                "distribution": {"win": 0.62, "stretch": 0.24, "miss": 0.14},
                "top_label": "win",
            },
        },
    )
    _write_forecast_workspace(
        forecasts_dir,
        forecast_id="forecast-numeric",
        question_type="numeric",
        question_spec={"unit": "usd_millions", "interval_levels": [50, 80, 90]},
        answer_payload={
            "question_type": "numeric",
            "best_estimate": {
                "value_type": "numeric_interval",
                "value_semantics": "numeric_interval_estimate",
                "point_estimate": 42,
                "intervals": [{"level": 80, "low": 36, "high": 50}],
            },
        },
    )

    result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--forecast-data-dir",
        str(forecasts_dir),
    )

    assert result.returncode == 0, result.stdout
    assert "Forecast workspaces scanned: 2" in result.stdout
    assert "Typed forecast answers scanned: 2" in result.stdout
    assert "Result: no conformance failures found" in result.stdout


def test_scan_forecasting_artifacts_flags_hollow_calibrated_nonbinary_forecast_answers(tmp_path):
    simulations_dir = tmp_path / "simulations"
    forecasts_dir = tmp_path / "forecasts"

    _write_forecast_workspace(
        forecasts_dir,
        forecast_id="forecast-numeric-invalid",
        question_type="numeric",
        question_spec={"unit": "usd_millions", "interval_levels": [50, 80, 90]},
        answer_payload={
            "question_type": "numeric",
            "best_estimate": {
                "value_type": "numeric_estimate",
                "value_semantics": "numeric_estimate",
                "value": 42,
            },
        },
        backtest_status="not_run",
        calibration_status="not_applicable",
        resolved_case_count=0,
    )

    result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--forecast-data-dir",
        str(forecasts_dir),
    )

    assert result.returncode == 2, result.stdout
    assert "Calibrated numeric forecast answers must store best_estimate as a numeric_interval_estimate payload." in result.stdout
    assert "Calibrated non-binary forecast answers require backtest_summary.status to be available or ready." in result.stdout
    assert "Calibrated non-binary forecast answers require calibration_summary.status to be ready." in result.stdout
    assert "Calibrated non-binary forecast answers require at least one resolved evaluation case." in result.stdout
