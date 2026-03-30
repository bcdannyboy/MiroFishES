import importlib
from pathlib import Path
import csv
import json


def _configure_fixture_paths(tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    projects_dir = uploads_dir / "projects"
    simulations_dir = uploads_dir / "simulations"
    projects_dir.mkdir(parents=True, exist_ok=True)
    simulations_dir.mkdir(parents=True, exist_ok=True)

    config_module = importlib.import_module("app.config")
    project_module = importlib.import_module("app.models.project")
    simulation_manager_module = importlib.import_module("app.services.simulation_manager")

    monkeypatch.setattr(
        config_module.Config,
        "UPLOAD_FOLDER",
        str(uploads_dir),
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulations_dir),
        raising=False,
    )
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
    )
    monkeypatch.setattr(
        simulation_manager_module.SimulationManager,
        "SIMULATION_DATA_DIR",
        str(simulations_dir),
    )

    return projects_dir, simulations_dir


def test_seed_probabilistic_smoke_fixture_creates_prepared_probabilistic_simulation(
    tmp_path,
    monkeypatch,
):
    projects_dir, simulations_dir = _configure_fixture_paths(tmp_path, monkeypatch)
    smoke_fixture_module = importlib.import_module(
        "app.services.probabilistic_smoke_fixture"
    )
    simulation_api_module = importlib.import_module("app.api.simulation")

    fixture = smoke_fixture_module.seed_probabilistic_smoke_fixture(
        graph_id="",
        projects_dir=str(projects_dir),
        simulation_data_dir=str(simulations_dir),
    )

    assert fixture["fixture_type"] == "probabilistic_step2_step3_smoke"
    assert fixture["simulation_route"] == f"/simulation/{fixture['simulation_id']}"
    assert fixture["prepared_artifact_summary"]["probabilistic_mode"] is True
    assert fixture["prepared_artifact_summary"]["mode"] == "probabilistic"
    assert fixture["prepared_artifact_summary"]["forecast_readiness"]["ready"] is True
    assert fixture["ensemble"] is None

    simulation_dir = Path(fixture["simulation_dir"])
    assert Path(fixture["project_dir"]).exists()
    assert simulation_dir.exists()
    assert (simulation_dir / "simulation_config.json").exists()
    assert (simulation_dir / "simulation_config.base.json").exists()
    assert (simulation_dir / "uncertainty_spec.json").exists()
    assert (simulation_dir / "outcome_spec.json").exists()
    assert (simulation_dir / "prepared_snapshot.json").exists()
    assert (simulation_dir / "grounding_bundle.json").exists()
    assert (simulation_dir / "probabilistic_smoke_fixture.json").exists()
    assert (simulation_dir / "twitter_profiles.csv").exists()
    assert (simulation_dir / "reddit_profiles.json").exists()

    with (simulation_dir / "twitter_profiles.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert set(rows[0].keys()) == {
        "user_id",
        "name",
        "username",
        "user_char",
        "description",
    }
    assert rows[0]["user_char"]

    reddit_profiles = json.loads(
        (simulation_dir / "reddit_profiles.json").read_text(encoding="utf-8")
    )
    assert reddit_profiles[0]["persona"]

    is_prepared, prepare_info = simulation_api_module._check_simulation_prepared(
        fixture["simulation_id"],
        require_probabilistic_artifacts=True,
    )
    assert is_prepared is True
    assert prepare_info["prepared_artifact_summary"]["probabilistic_mode"] is True


def test_seed_probabilistic_smoke_fixture_can_optionally_seed_an_ensemble(
    tmp_path,
    monkeypatch,
):
    projects_dir, simulations_dir = _configure_fixture_paths(tmp_path, monkeypatch)
    smoke_fixture_module = importlib.import_module(
        "app.services.probabilistic_smoke_fixture"
    )
    ensemble_manager_module = importlib.import_module("app.services.ensemble_manager")

    fixture = smoke_fixture_module.seed_probabilistic_smoke_fixture(
        graph_id="",
        projects_dir=str(projects_dir),
        simulation_data_dir=str(simulations_dir),
        create_ensemble_run_count=3,
        ensemble_root_seed=17,
    )

    assert fixture["ensemble"] is not None
    assert fixture["ensemble"]["run_ids"] == ["0001", "0002", "0003"]

    ensemble_manager = ensemble_manager_module.EnsembleManager(
        simulation_data_dir=str(simulations_dir)
    )
    loaded = ensemble_manager.load_ensemble(
        fixture["simulation_id"],
        fixture["ensemble"]["ensemble_id"],
    )

    assert loaded["state"]["run_count"] == 3
    assert loaded["state"]["root_seed"] == 17
    assert [run["run_id"] for run in loaded["runs"]] == ["0001", "0002", "0003"]


def test_seed_probabilistic_smoke_fixture_can_seed_a_completed_probabilistic_report(
    tmp_path,
    monkeypatch,
):
    projects_dir, simulations_dir = _configure_fixture_paths(tmp_path, monkeypatch)
    smoke_fixture_module = importlib.import_module(
        "app.services.probabilistic_smoke_fixture"
    )
    report_agent_module = importlib.import_module("app.services.report_agent")

    fixture = smoke_fixture_module.seed_probabilistic_smoke_fixture(
        graph_id="",
        projects_dir=str(projects_dir),
        simulation_data_dir=str(simulations_dir),
        create_ensemble_run_count=2,
        ensemble_root_seed=19,
        seed_completed_report=True,
        report_run_id="0001",
    )

    assert fixture["ensemble"] is not None
    assert fixture["report"] is not None
    assert fixture["report"]["run_id"] == "0001"
    assert fixture["report"]["report_route"].startswith("/report/")
    assert fixture["report"]["interaction_route"].startswith("/interaction/")

    report = report_agent_module.ReportManager.get_report(fixture["report"]["report_id"])
    assert report is not None
    assert report.status == report_agent_module.ReportStatus.COMPLETED
    assert report.ensemble_id == fixture["ensemble"]["ensemble_id"]
    assert report.run_id == "0001"
    assert report.probabilistic_context["artifact_type"] == "probabilistic_report_context"
    assert report.probabilistic_context["selected_run"]["run_id"] == "0001"
    assert report.probabilistic_context["probability_mode"] == "empirical"
