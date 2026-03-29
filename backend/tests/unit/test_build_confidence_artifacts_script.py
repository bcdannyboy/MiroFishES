import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "build_confidence_artifacts.py"


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


def test_build_confidence_artifacts_script_writes_backtest_and_calibration(tmp_path):
    simulation_data_dir = tmp_path / "simulations"
    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "observed_truth_registry.json",
        {
            "artifact_type": "observed_truth_registry",
            "schema_version": "probabilistic.observed_truth.v2",
            "generator_version": "probabilistic.observed_truth.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "registry_scope": {
                "level": "ensemble",
                "simulation_id": "sim-001",
                "ensemble_id": "0001",
            },
            "cases": [
                {
                    "case_id": "case-1",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.1,
                    "observed_value": False,
                },
                {
                    "case_id": "case-2",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.2,
                    "observed_value": False,
                },
                {
                    "case_id": "case-3",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.3,
                    "observed_value": False,
                },
                {
                    "case_id": "case-4",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.3,
                    "observed_value": True,
                },
                {
                    "case_id": "case-5",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.7,
                    "observed_value": True,
                },
                {
                    "case_id": "case-6",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.7,
                    "observed_value": False,
                },
                {
                    "case_id": "case-7",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.8,
                    "observed_value": True,
                },
                {
                    "case_id": "case-8",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.8,
                    "observed_value": True,
                },
                {
                    "case_id": "case-9",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.9,
                    "observed_value": True,
                },
                {
                    "case_id": "case-10",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.9,
                    "observed_value": True,
                },
            ],
            "quality_summary": {"status": "complete", "warnings": []},
        },
    )

    result = _run_script(
        "--simulation-id",
        "sim-001",
        "--ensemble-id",
        "0001",
        "--simulation-data-dir",
        str(simulation_data_dir),
    )

    assert result.returncode == 0, result.stderr
    backtest = json.loads((ensemble_dir / "backtest_summary.json").read_text(encoding="utf-8"))
    calibration = json.loads(
        (ensemble_dir / "calibration_summary.json").read_text(encoding="utf-8")
    )
    assert backtest["schema_version"] == "probabilistic.backtest.v2"
    assert calibration["schema_version"] == "probabilistic.calibration.v2"
    assert calibration["metric_calibrations"]["simulation.completed"]["readiness"]["ready"] is True


def test_build_confidence_artifacts_script_strict_ready_fails_for_not_ready_calibration(
    tmp_path,
):
    simulation_data_dir = tmp_path / "simulations"
    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "observed_truth_registry.json",
        {
            "artifact_type": "observed_truth_registry",
            "schema_version": "probabilistic.observed_truth.v2",
            "generator_version": "probabilistic.observed_truth.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "cases": [
                {
                    "case_id": f"case-{index}",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.8,
                    "observed_value": True,
                }
                for index in range(1, 11)
            ],
        },
    )

    result = _run_script(
        "--simulation-id",
        "sim-001",
        "--ensemble-id",
        "0001",
        "--simulation-data-dir",
        str(simulation_data_dir),
        "--strict-ready",
    )

    assert result.returncode != 0
    assert "not ready" in result.stderr.lower()
