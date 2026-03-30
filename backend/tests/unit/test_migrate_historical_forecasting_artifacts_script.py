import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATE_SCRIPT_PATH = (
    BACKEND_ROOT / "scripts" / "migrate_historical_forecasting_artifacts.py"
)
SCAN_SCRIPT_PATH = BACKEND_ROOT / "scripts" / "scan_forecasting_artifacts.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_script(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrate_historical_artifacts_repairs_context_and_quarantines_unavailable_grounding(
    tmp_path,
):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-archived"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "forecast_archive.json",
        {
            "artifact_type": "forecast_archive",
            "schema_version": "forecast.archive.v1",
            "archived_at": "2026-03-29T12:00:00",
            "archive_scope": "historical_read_only",
            "reason": "Pre-contract saved simulation is retained for history only.",
        },
    )
    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "simulation_id": "sim-archived",
            "probabilistic_mode": True,
            "mode": "probabilistic",
            "lineage": {
                "project_id": "proj-archived",
                "graph_id": "",
            },
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "schema_version": "probabilistic.report_context.v1",
            "simulation_id": "sim-archived",
            "ensemble_id": "0001",
        },
    )

    migrate_result = _run_script(
        MIGRATE_SCRIPT_PATH,
        "--simulation-data-dir",
        str(simulations_dir),
        "--apply",
    )

    assert migrate_result.returncode == 0, migrate_result.stdout
    assert "Archived simulations inspected: 1" in migrate_result.stdout
    assert "Grounding bundles created: 1" in migrate_result.stdout
    assert "Report contexts patched: 1" in migrate_result.stdout

    grounding_bundle = json.loads(
        (simulation_dir / "grounding_bundle.json").read_text(encoding="utf-8")
    )
    assert grounding_bundle["artifact_type"] == "grounding_bundle"
    assert grounding_bundle["status"] == "unavailable"

    report_context = json.loads(
        (ensemble_dir / "probabilistic_report_context.json").read_text(encoding="utf-8")
    )
    assert report_context["grounding_context"]["status"] == "unavailable"
    assert report_context["confidence_status"]["status"] == "absent"
    assert (
        report_context["confidence_status"]["artifact_readiness"]["calibration_summary"][
            "status"
        ]
        == "absent"
    )

    archive_metadata = json.loads(
        (simulation_dir / "forecast_archive.json").read_text(encoding="utf-8")
    )
    assert archive_metadata["historical_conformance"]["status"] == "quarantined_non_ready"
    assert archive_metadata["historical_conformance"]["quarantined_issue_codes"] == [
        "grounding_bundle_not_ready"
    ]

    scan_result = _run_script(
        SCAN_SCRIPT_PATH,
        "--simulation-data-dir",
        str(simulations_dir),
        "--include-archived",
    )

    assert scan_result.returncode == 0, scan_result.stdout
    assert "Archived historical non-ready issues quarantined explicitly: 1 across 1 simulations" in scan_result.stdout


def test_migrate_historical_artifacts_does_not_mark_ready_grounding_as_remediated_when_other_issues_remain(
    tmp_path,
):
    simulations_dir = tmp_path / "simulations"
    simulation_dir = simulations_dir / "sim-archived"
    ensemble_dir = simulation_dir / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_dir / "forecast_archive.json",
        {
            "artifact_type": "forecast_archive",
            "schema_version": "forecast.archive.v1",
            "archived_at": "2026-03-29T12:00:00",
            "archive_scope": "historical_read_only",
            "reason": "Pre-contract saved simulation is retained for history only.",
        },
    )
    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "simulation_id": "sim-archived",
            "probabilistic_mode": True,
            "mode": "probabilistic",
            "lineage": {
                "project_id": "proj-archived",
                "graph_id": "graph-archived",
            },
        },
    )
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "ready",
            "warnings": [],
        },
    )
    _write_json(
        ensemble_dir / "probabilistic_report_context.json",
        {
            "artifact_type": "probabilistic_report_context",
            "schema_version": "probabilistic.report_context.v1",
            "simulation_id": "sim-archived",
            "ensemble_id": "0001",
            "grounding_context": {
                "status": "ready",
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

    migrate_result = _run_script(
        MIGRATE_SCRIPT_PATH,
        "--simulation-data-dir",
        str(simulations_dir),
        "--apply",
    )

    assert migrate_result.returncode == 0, migrate_result.stdout

    archive_metadata = json.loads(
        (simulation_dir / "forecast_archive.json").read_text(encoding="utf-8")
    )
    assert archive_metadata["historical_conformance"]["status"] == "pending_remediation"
    assert "report_context_missing_calibration_artifact" in archive_metadata[
        "historical_conformance"
    ]["issue_codes"]
    assert "report_context_missing_backtest_artifact" in archive_metadata[
        "historical_conformance"
    ]["issue_codes"]

    scan_result = _run_script(
        SCAN_SCRIPT_PATH,
        "--simulation-data-dir",
        str(simulations_dir),
        "--include-archived",
    )

    assert scan_result.returncode == 2, scan_result.stdout
    assert (
        "Report context implies confidence support but calibration_summary.json is missing"
        in scan_result.stdout
    )
