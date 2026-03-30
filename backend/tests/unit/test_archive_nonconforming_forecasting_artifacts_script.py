import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "archive_nonconforming_forecasting_artifacts.py"


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


def test_archive_script_marks_only_nonconforming_simulations(tmp_path):
    simulations_dir = tmp_path / "simulations"

    bad_sim_dir = simulations_dir / "sim-bad"
    _write_json(
        bad_sim_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )

    good_sim_dir = simulations_dir / "sim-good"
    _write_json(
        good_sim_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )
    _write_json(
        good_sim_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "status": "ready",
        },
    )

    dry_run = _run_script("--simulation-data-dir", str(simulations_dir))

    assert dry_run.returncode == 0, dry_run.stdout
    assert "Nonconforming simulations found: 1" in dry_run.stdout
    assert "History scope: active + archived" in dry_run.stdout
    assert "This tool audits the full historical backlog" in dry_run.stdout
    assert "Active nonconforming simulations refused archival by default: 1" in dry_run.stdout
    assert not (bad_sim_dir / "forecast_archive.json").exists()

    apply_result = _run_script("--simulation-data-dir", str(simulations_dir), "--apply")

    assert apply_result.returncode == 0, apply_result.stdout
    assert "Archive markers written: 0" in apply_result.stdout
    assert "Active nonconforming simulations refused archival by default: 1" in apply_result.stdout
    assert "History scope: active + archived" in apply_result.stdout
    assert not (bad_sim_dir / "forecast_archive.json").exists()
    assert not (good_sim_dir / "forecast_archive.json").exists()


def test_archive_script_requires_allow_active_before_marking_active_failures(tmp_path):
    simulations_dir = tmp_path / "simulations"
    bad_sim_dir = simulations_dir / "sim-bad"
    _write_json(
        bad_sim_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "probabilistic_mode": True,
            "mode": "probabilistic",
        },
    )

    apply_result = _run_script(
        "--simulation-data-dir",
        str(simulations_dir),
        "--apply",
        "--allow-active",
    )

    assert apply_result.returncode == 0, apply_result.stdout
    assert "Archive markers written: 1" in apply_result.stdout
    assert (bad_sim_dir / "forecast_archive.json").exists()
    archive_metadata = json.loads(
        (bad_sim_dir / "forecast_archive.json").read_text(encoding="utf-8")
    )
    assert archive_metadata["historical_conformance"]["status"] == "pending_remediation"
    assert archive_metadata["historical_conformance"]["issue_codes"] == [
        "prepared_missing_grounding_bundle"
    ]
