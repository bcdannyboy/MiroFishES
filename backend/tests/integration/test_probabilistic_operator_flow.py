import csv
import importlib
import json
from pathlib import Path

from app.models.forecasting import ForecastQuestion
from app.services.forecast_manager import ForecastManager


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_simulation_api_module():
    return importlib.import_module("app.api.simulation")


def _load_simulation_runner_module():
    return importlib.import_module("app.services.simulation_runner")


def _load_simulation_market_extractor_module():
    return importlib.import_module("app.services.simulation_market_extractor")


def _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module=None):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    if manager_module is not None:
        monkeypatch.setattr(
            manager_module.SimulationManager,
            "SIMULATION_DATA_DIR",
            str(simulation_data_dir),
        )


def _configure_project_grounding_dir(monkeypatch, project_root):
    project_module = importlib.import_module("app.models.project")
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(project_root),
        raising=False,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_project_grounding_artifacts(
    monkeypatch,
    simulation_data_dir,
    *,
    project_id: str,
    graph_id: str,
    simulation_requirement: str,
    document_text: str,
):
    project_root = Path(simulation_data_dir).parent / "projects"
    _configure_project_grounding_dir(monkeypatch, project_root)
    project_dir = project_root / project_id
    excerpt = " ".join(document_text.split())[:180]

    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": simulation_requirement,
            "boundary_note": "Integration-test fixture inputs only.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "fixture-source-1",
                    "original_filename": "fixture.md",
                    "saved_filename": "fixture.md",
                    "relative_path": "files/fixture.md",
                    "size_bytes": len(document_text.encode("utf-8")),
                    "sha256": "fixture-sha256",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": len(document_text),
                    "combined_text_start": 0,
                    "combined_text_end": len(document_text),
                    "parser_warnings": [],
                    "excerpt": excerpt,
                }
            ],
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {"source_manifest": "source_manifest.json"},
            "ontology_summary": {
                "analysis_summary": "Integration-test graph provenance for probabilistic operator flow.",
                "entity_type_count": 1,
                "edge_type_count": 1,
            },
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 1,
            "graph_counts": {
                "node_count": 1,
                "edge_count": 0,
                "entity_types": ["Person"],
            },
            "warnings": [],
        },
    )


def _build_app_client(monkeypatch):
    importlib.import_module("app.api.simulation")
    runner_module = importlib.import_module("app.services.simulation_runner")
    monkeypatch.setattr(
        runner_module.SimulationRunner,
        "register_cleanup",
        classmethod(lambda cls: None),
        raising=False,
    )
    app_module = importlib.import_module("app")
    app = app_module.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _fake_filtered_entities():
    reader_module = importlib.import_module("app.services.zep_entity_reader")
    return reader_module.FilteredEntities(
        entities=[
            reader_module.EntityNode(
                uuid="entity-1",
                name="Analyst",
                labels=["Entity", "Person"],
                summary="A tracked participant",
                attributes={"role": "analyst"},
            )
        ],
        entity_types={"Person"},
        total_count=1,
        filtered_count=1,
    )


class _FakeProfile:
    def __init__(self, user_id, user_name):
        self.user_id = user_id
        self.user_name = user_name

    def to_reddit_format(self):
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.user_name.title(),
            "bio": "Synthetic profile",
            "persona": "Helpful analyst",
        }

    def to_twitter_format(self):
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.user_name.title(),
            "bio": "Synthetic profile",
            "persona": "Helpful analyst",
        }


class _FakeProfileGenerator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def generate_profiles_from_entities(self, *args, **kwargs):
        return [_FakeProfile(1, "agent_one")]

    def save_profiles(self, profiles, file_path, platform):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if platform == "reddit":
            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    [profile.to_reddit_format() for profile in profiles],
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
            return

        rows = [profile.to_twitter_format() for profile in profiles]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


class _FakeSimulationParameters:
    def __init__(self, simulation_id, project_id, graph_id, simulation_requirement):
        self.generation_reasoning = "Integration test reasoning"
        self.payload = {
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "time_config": {
                "total_simulation_hours": 24,
                "minutes_per_round": 60,
            },
            "agent_configs": [
                {
                    "agent_id": 0,
                    "entity_uuid": "entity-1",
                    "entity_name": "Analyst",
                    "entity_type": "Person",
                    "activity_level": 0.5,
                    "posts_per_hour": 1.0,
                    "comments_per_hour": 1.0,
                    "active_hours": [8, 9, 10],
                    "response_delay_min": 5,
                    "response_delay_max": 15,
                    "sentiment_bias": 0.0,
                    "stance": "neutral",
                    "influence_weight": 1.0,
                }
            ],
            "event_config": {
                "initial_posts": [],
                "scheduled_events": [],
                "hot_topics": ["seed"],
                "narrative_direction": "neutral",
            },
            "twitter_config": {
                "platform": "twitter",
                "echo_chamber_strength": 0.5,
            },
            "reddit_config": {
                "platform": "reddit",
                "echo_chamber_strength": 0.5,
            },
            "generated_at": "2026-03-10T12:00:00",
            "generation_reasoning": "Integration test reasoning",
        }

    def to_dict(self):
        return json.loads(json.dumps(self.payload))


class _FakeSimulationConfigGenerator:
    def generate_config(self, **kwargs):
        return _FakeSimulationParameters(
            simulation_id=kwargs["simulation_id"],
            project_id=kwargs["project_id"],
            graph_id=kwargs["graph_id"],
            simulation_requirement=kwargs["simulation_requirement"],
        )


class _FakeRunState:
    def __init__(
        self,
        simulation_id,
        ensemble_id=None,
        run_id=None,
        runner_status="running",
    ):
        self.simulation_id = simulation_id
        self.ensemble_id = ensemble_id
        self.run_id = run_id
        self.runner_status = runner_status

    def to_dict(self):
        return {
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "runner_status": self.runner_status,
            "runtime_scope": "ensemble_run" if self.ensemble_id and self.run_id else "legacy",
            "runtime_key": (
                f"{self.simulation_id}::{self.ensemble_id}::{self.run_id}"
                if self.ensemble_id and self.run_id
                else self.simulation_id
            ),
            "runtime_dir": "/tmp/fake-run",
            "current_round": 3,
            "total_rounds": 12,
            "progress_percent": 25.0,
            "simulated_hours": 3,
            "total_simulation_hours": 12,
            "twitter_actions_count": 5,
            "reddit_actions_count": 7,
            "total_actions_count": 12,
        }


def _install_prepare_stubs(monkeypatch, manager_module):
    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module,
        "SimulationConfigGenerator",
        _FakeSimulationConfigGenerator,
    )


def _prepare_simulation(simulation_data_dir, monkeypatch):
    manager_module = _load_manager_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)
    simulation_requirement = "Forecast discussion spread"
    document_text = "seed text"
    _seed_project_grounding_artifacts(
        monkeypatch,
        simulation_data_dir,
        project_id="proj-1",
        graph_id="graph-1",
        simulation_requirement=simulation_requirement,
        document_text=document_text,
    )

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement=simulation_requirement,
        document_text=document_text,
        probabilistic_mode=True,
        uncertainty_profile="balanced",
        outcome_metrics=["simulation.total_actions"],
    )
    return state


def _create_ensemble(client, simulation_id, *, run_count=1, max_concurrency=1, root_seed=101):
    response = client.post(
        f"/api/simulation/{simulation_id}/ensembles",
        json={
            "run_count": run_count,
            "max_concurrency": max_concurrency,
            "root_seed": root_seed,
        },
    )
    assert response.status_code == 200
    return response.get_json()["data"]


def _install_runner_state_lookup(monkeypatch, simulation_module):
    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        run_key = f"{simulation_id}::{ensemble_id}::{run_id}"
        return simulation_module.SimulationRunner._run_states.get(run_key)

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )


def _seed_runtime_artifacts(run_path: Path):
    (run_path / "simulation.log").write_text("runtime-log", encoding="utf-8")
    (run_path / "metrics.json").write_text("{}", encoding="utf-8")
    (run_path / "run_state.json").write_text("{}", encoding="utf-8")
    (run_path / "twitter").mkdir(parents=True, exist_ok=True)
    (run_path / "twitter" / "actions.jsonl").write_text("{}", encoding="utf-8")


def _write_run_manifest(run_path: Path, **updates):
    manifest_path = run_path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(updates)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def test_operator_flow_stops_cleans_and_retries_the_same_run_via_app_client(
    simulation_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    ensemble_payload = _create_ensemble(client, state.simulation_id, root_seed=111)
    run = ensemble_payload["runs"][0]
    run_id = run["run_id"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(run["path"])
    run_key = f"{state.simulation_id}::{ensemble_id}::{run_id}"

    _seed_runtime_artifacts(run_path)
    simulation_module.SimulationRunner._run_states = {
        run_key: _FakeRunState(
            state.simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        )
    }
    _install_runner_state_lookup(monkeypatch, simulation_module)

    def _fake_stop_simulation(simulation_id, ensemble_id=None, run_id=None):
        stopped_state = _FakeRunState(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="stopped",
        )
        simulation_module.SimulationRunner._run_states[
            f"{simulation_id}::{ensemble_id}::{run_id}"
        ] = stopped_state
        return stopped_state

    start_calls = []

    def _fake_start_simulation(**kwargs):
        start_calls.append(kwargs)
        started_state = _FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )
        simulation_module.SimulationRunner._run_states[
            f"{kwargs['simulation_id']}::{kwargs['ensemble_id']}::{kwargs['run_id']}"
        ] = started_state
        return started_state

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "stop_simulation",
        _fake_stop_simulation,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        _fake_start_simulation,
        raising=False,
    )

    stop_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/{run_id}/stop"
    )

    assert stop_response.status_code == 200
    assert stop_response.get_json()["data"]["runner_status"] == "stopped"

    cleanup_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": [run_id]},
    )

    assert cleanup_response.status_code == 200
    cleanup_payload = cleanup_response.get_json()["data"]
    assert cleanup_payload["cleaned_run_ids"] == [run_id]
    assert run_key not in simulation_module.SimulationRunner._run_states
    assert (run_path / "simulation.log").exists() is False
    assert (run_path / "metrics.json").exists() is False
    assert (run_path / "twitter" / "actions.jsonl").exists() is False

    status_response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/{run_id}/run-status"
        )
    )

    assert status_response.status_code == 200
    status_payload = status_response.get_json()["data"]
    assert status_payload["runner_status"] == "idle"
    assert status_payload["storage_status"] == "prepared"

    restart_response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/{run_id}/start"
        ),
        json={"platform": "parallel"},
    )

    assert restart_response.status_code == 200
    restart_payload = restart_response.get_json()["data"]
    assert [call["run_id"] for call in start_calls] == [run_id]
    assert restart_payload["run_id"] == run_id
    assert restart_payload["runner_status"] == "running"
    assert restart_payload["force_restarted"] is False


def test_operator_flow_rerun_endpoint_creates_child_lineage_via_app_client(
    simulation_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    client = _build_app_client(monkeypatch)

    ensemble_payload = _create_ensemble(client, state.simulation_id, root_seed=131)
    ensemble_id = ensemble_payload["ensemble_id"]
    source_run = ensemble_payload["runs"][0]
    source_run_path = Path(source_run["path"])
    _write_run_manifest(
        source_run_path,
        status="failed",
        lifecycle={
            "start_count": 1,
            "retry_count": 0,
            "cleanup_count": 0,
            "last_launch_reason": "initial_start",
        },
    )

    rerun_response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/{source_run['run_id']}/rerun"
        )
    )

    assert rerun_response.status_code == 200
    rerun_payload = rerun_response.get_json()["data"]
    assert rerun_payload["source_run_id"] == source_run["run_id"]
    assert rerun_payload["run"]["run_id"] == "0002"
    assert rerun_payload["run"]["status"] == "prepared"

    rerun_detail = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0002"
        )
    )

    assert rerun_detail.status_code == 200
    rerun_manifest = rerun_detail.get_json()["data"]["run_manifest"]
    assert rerun_manifest["lineage"]["kind"] == "rerun"
    assert rerun_manifest["lineage"]["source_run_id"] == "0001"
    assert rerun_manifest["lineage"]["parent_run_id"] == "0001"
    assert rerun_manifest["lifecycle"]["start_count"] == 0
    assert rerun_manifest["lifecycle"]["retry_count"] == 0


def test_operator_flow_links_forecast_workspace_to_ensemble_and_run_scope_via_app_client(
    simulation_data_dir,
    forecast_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )
    forecast_manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(
        forecast_manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    manager = ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-link-1",
                "project_id": "proj-1",
                "title": "Run-linked question",
                "question": "Will the run-linked control plane stay attached through Step 3?",
                "question_type": "binary",
                "status": "active",
                "horizon": "2026-06-30",
                "resolution_criteria_ids": [],
                "primary_simulation_id": state.simulation_id,
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
            }
        )
    )

    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    def _fake_start_simulation(**kwargs):
        return _FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        _fake_start_simulation,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 111,
            "forecast_id": "forecast-link-1",
        },
    )
    assert create_response.status_code == 200
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]

    start_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/start",
        json={"platform": "parallel", "forecast_id": "forecast-link-1"},
    )
    assert start_response.status_code == 200

    linked_workspace = manager.get_workspace("forecast-link-1")
    assert linked_workspace is not None
    linked_payload = linked_workspace.to_dict()
    assert linked_payload["simulation_scope"]["simulation_id"] == state.simulation_id
    assert linked_payload["simulation_scope"]["ensemble_ids"] == [ensemble_id]
    assert linked_payload["simulation_scope"]["run_ids"] == ["0001"]
    assert linked_payload["lifecycle_metadata"]["current_stage"] == "forecast_workspace"


def test_operator_flow_cleanup_rejects_active_runs_via_app_client(
    simulation_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    ensemble_payload = _create_ensemble(client, state.simulation_id, root_seed=151)
    run = ensemble_payload["runs"][0]
    run_id = run["run_id"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(run["path"])
    run_key = f"{state.simulation_id}::{ensemble_id}::{run_id}"

    _seed_runtime_artifacts(run_path)
    simulation_module.SimulationRunner._run_states = {
        run_key: _FakeRunState(
            state.simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        )
    }
    _install_runner_state_lookup(monkeypatch, simulation_module)

    cleanup_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": [run_id]},
    )

    assert cleanup_response.status_code == 409
    cleanup_payload = cleanup_response.get_json()
    assert cleanup_payload["success"] is False
    assert cleanup_payload["active_run_ids"] == [run_id]


def test_operator_flow_persists_and_loads_simulation_market_artifacts_via_app_client(
    simulation_data_dir,
    forecast_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )
    forecast_manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(
        forecast_manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    manager = ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-market-flow-1",
                "project_id": "proj-1",
                "title": "Synthetic market flow question",
                "question": "Will the simulated market hold a majority above 50%?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "primary_simulation_id": state.simulation_id,
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
            }
        )
    )

    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    def _fake_start_simulation(**kwargs):
        return _FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        _fake_start_simulation,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 211,
            "forecast_id": "forecast-market-flow-1",
        },
    )
    assert create_response.status_code == 200
    ensemble_payload = create_response.get_json()["data"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(ensemble_payload["runs"][0]["path"])

    start_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/start",
        json={"platform": "parallel", "forecast_id": "forecast-market-flow-1"},
    )
    assert start_response.status_code == 200

    _write_json(
        run_path / "run_state.json",
        {
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
            "run_key": f"{state.simulation_id}::{ensemble_id}::0001",
            "run_dir": str(run_path),
            "config_path": str(run_path / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-30T09:55:00",
            "updated_at": "2026-03-30T10:10:00",
            "completed_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "status": "completed",
        },
    )
    (run_path / "twitter").mkdir(parents=True, exist_ok=True)
    (run_path / "twitter" / "actions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 1,
                        "timestamp": "2026-03-30T10:00:00",
                        "platform": "twitter",
                        "agent_id": 1,
                        "agent_name": "Analyst A",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "I put this near 62%.",
                            "forecast_probability": 0.62,
                            "confidence": 0.6,
                            "rationale_tags": ["base_rate"],
                        },
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round": 2,
                        "timestamp": "2026-03-30T10:05:00",
                        "platform": "twitter",
                        "agent_id": 2,
                        "agent_name": "Analyst B",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "Closer to 44%.",
                            "forecast_probability": "44%",
                            "confidence": "low",
                            "rationale_tags": ["inflation"],
                            "missing_information_requests": ["Need revisions"],
                        },
                        "success": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    extractor_module = _load_simulation_market_extractor_module()
    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    persisted = extractor.persist_run_market_artifacts(
        state.simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
        run_dir=str(run_path),
    )
    _write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "artifact_paths": {
                **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")).get("artifact_paths", {}),
                "simulation_market_manifest": "simulation_market_manifest.json",
                "agent_belief_book": "agent_belief_book.json",
                "belief_update_trace": "belief_update_trace.json",
                "disagreement_summary": "disagreement_summary.json",
                "market_snapshot": "market_snapshot.json",
                "argument_map": "argument_map.json",
                "missing_information_signals": "missing_information_signals.json",
            },
        },
    )

    assert persisted["manifest"]["extraction_status"] == "ready"
    manager.attach_simulation_scope(
        "forecast-market-flow-1",
        simulation_id=state.simulation_id,
        ensemble_ids=[ensemble_id],
        run_ids=["0001"],
        latest_ensemble_id=ensemble_id,
        latest_run_id="0001",
        source_stage="integration_test",
    )
    workspace = manager.generate_hybrid_forecast_answer(
        "forecast-market-flow-1",
        requested_at="2026-03-30T10:30:00",
    )
    answer = workspace.forecast_answers[-1]
    simulation_market_trace = next(
        item
        for item in answer.answer_payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation_market"
    )

    assert simulation_market_trace["used_in_best_estimate"] is True
    assert simulation_market_trace["confidence_inputs"]["provenance_status"] == "partial"
    assert answer.answer_payload["simulation_market_context"]["included"] is True
    assert answer.answer_payload["best_estimate"] is not None

    detail_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()["data"]
    assert detail_payload["simulation_market"]["simulation_market_manifest"]["forecast_id"] == "forecast-market-flow-1"
    assert detail_payload["simulation_market"]["market_snapshot"]["synthetic_consensus_probability"] == 0.53
    assert detail_payload["simulation_market_summary"]["artifact_type"] == "simulation_market_summary"
    assert detail_payload["simulation_market_summary"]["synthetic_consensus_probability"] == 0.53
    assert detail_payload["simulation_market_provenance"]["status"] == "partial"
    assert detail_payload["run_manifest"]["artifact_paths"]["market_snapshot"] == "market_snapshot.json"

    resolve_response = client.post(
        "/api/forecast/questions/forecast-market-flow-1/resolve",
        json={
            "status": "resolved_true",
            "resolved_at": "2026-07-01T10:00:00",
            "resolution_note": "Observed yes.",
        },
    )
    assert resolve_response.status_code == 200, resolve_response.get_data(as_text=True)

    score_response = client.post(
        "/api/forecast/questions/forecast-market-flow-1/score",
        json={
            "observed_outcome": True,
            "scoring_methods": ["brier_score", "log_score"],
            "recorded_at": "2026-07-01T10:05:00",
        },
    )
    assert score_response.status_code == 200
    score_payload = score_response.get_json()
    assert score_payload["workspace"]["lifecycle_metadata"]["current_stage"] == "scoring_event"
    assert len(score_payload["workspace"]["scoring_events"]) == 2


def test_operator_flow_builds_report_context_from_hybrid_workspace(
    simulation_data_dir,
    forecast_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )
    forecast_manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(
        forecast_manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    manager = ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-report-flow-1",
                "project_id": "proj-1",
                "title": "Report-context linked question",
                "question": "Will report generation preserve the hybrid forecast workspace context?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "primary_simulation_id": state.simulation_id,
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
            }
        )
    )

    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    def _fake_start_simulation(**kwargs):
        return _FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        _fake_start_simulation,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 311,
            "forecast_id": "forecast-report-flow-1",
        },
    )
    assert create_response.status_code == 200
    ensemble_payload = create_response.get_json()["data"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(ensemble_payload["runs"][0]["path"])
    manifest_path = run_path / "run_manifest.json"
    resolved_config_path = run_path / "resolved_config.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved_payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    manifest_payload["base_graph_id"] = "graph-1"
    manifest_payload["runtime_graph_id"] = "runtime-graph-1"
    manifest_payload["graph_id"] = "graph-1"
    resolved_payload["base_graph_id"] = "graph-1"
    resolved_payload["runtime_graph_id"] = "runtime-graph-1"
    resolved_payload["graph_id"] = "graph-1"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    resolved_config_path.write_text(
        json.dumps(resolved_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    start_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/start",
        json={"platform": "parallel", "forecast_id": "forecast-report-flow-1"},
    )
    assert start_response.status_code == 200

    _write_json(
        run_path / "run_state.json",
        {
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
            "run_key": f"{state.simulation_id}::{ensemble_id}::0001",
            "run_dir": str(run_path),
            "config_path": str(run_path / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-30T09:55:00",
            "updated_at": "2026-03-30T10:10:00",
            "completed_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "status": "completed",
        },
    )
    (run_path / "twitter").mkdir(parents=True, exist_ok=True)
    (run_path / "twitter" / "actions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 1,
                        "timestamp": "2026-03-30T10:00:00",
                        "platform": "twitter",
                        "agent_id": 1,
                        "agent_name": "Analyst A",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "This looks better than a coin flip.",
                            "forecast_probability": 0.62,
                            "confidence": 0.6,
                            "rationale_tags": ["base_rate"],
                        },
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round": 2,
                        "timestamp": "2026-03-30T10:05:00",
                        "platform": "twitter",
                        "agent_id": 2,
                        "agent_name": "Analyst B",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "I still see some downside risk.",
                            "forecast_probability": "44%",
                            "confidence": "low",
                            "rationale_tags": ["risk"],
                            "missing_information_requests": ["Need revisions"],
                        },
                        "success": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    extractor_module = _load_simulation_market_extractor_module()
    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    persisted = extractor.persist_run_market_artifacts(
        state.simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
        run_dir=str(run_path),
    )
    _write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "artifact_paths": {
                **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")).get("artifact_paths", {}),
                "simulation_market_manifest": "simulation_market_manifest.json",
                "agent_belief_book": "agent_belief_book.json",
                "belief_update_trace": "belief_update_trace.json",
                "disagreement_summary": "disagreement_summary.json",
                "market_snapshot": "market_snapshot.json",
                "argument_map": "argument_map.json",
                "missing_information_signals": "missing_information_signals.json",
            },
        },
    )

    assert persisted["manifest"]["extraction_status"] == "ready"
    manager.attach_simulation_scope(
        "forecast-report-flow-1",
        simulation_id=state.simulation_id,
        ensemble_ids=[ensemble_id],
        run_ids=["0001"],
        latest_ensemble_id=ensemble_id,
        latest_run_id="0001",
        source_stage="integration_test",
    )
    workspace = manager.generate_hybrid_forecast_answer(
        "forecast-report-flow-1",
        requested_at="2026-03-30T10:30:00",
    )
    answer = workspace.forecast_answers[-1]
    report_context_module = importlib.import_module(
        "app.services.probabilistic_report_context"
    )
    probabilistic_context = (
        report_context_module.ProbabilisticReportContextBuilder(
            simulation_data_dir=str(simulation_data_dir)
        ).build_context(
            simulation_id=state.simulation_id,
            ensemble_id=ensemble_id,
            run_id="0001",
        )
    )

    assert probabilistic_context["forecast_workspace"]["forecast_question"]["question_text"] == (
        "Will report generation preserve the hybrid forecast workspace context?"
    )
    assert probabilistic_context["forecast_workspace"]["prediction_ledger"]["entry_count"] == 1
    assert probabilistic_context["forecast_workspace"]["forecast_answer"]["answer_type"] == (
        "hybrid_forecast"
    )
    assert probabilistic_context["selected_run"]["simulation_market"]["market_snapshot"][
        "synthetic_consensus_probability"
    ] == 0.53
    assert probabilistic_context["simulation_market_summary"][
        "synthetic_consensus_probability"
    ] == 0.53
    assert probabilistic_context["signal_provenance_summary"]["status"] == "partial"
    assert probabilistic_context["forecast_object"]["latest_answer_id"] == answer.answer_id


def test_operator_flow_rejects_invalid_simulation_market_provenance_during_hybrid_generation(
    simulation_data_dir,
    forecast_data_dir,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )
    forecast_manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(
        forecast_manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    state = _prepare_simulation(simulation_data_dir, monkeypatch)
    manager = ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-market-flow-invalid",
                "project_id": "proj-1",
                "title": "Synthetic market invalid provenance question",
                "question": "Will the simulated market hold a majority above 50%?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "primary_simulation_id": state.simulation_id,
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
            }
        )
    )

    client = _build_app_client(monkeypatch)
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        lambda **kwargs: _FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 241,
            "forecast_id": "forecast-market-flow-invalid",
        },
    )
    assert create_response.status_code == 200
    ensemble_payload = create_response.get_json()["data"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(ensemble_payload["runs"][0]["path"])

    start_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/start",
        json={"platform": "parallel", "forecast_id": "forecast-market-flow-invalid"},
    )
    assert start_response.status_code == 200

    _write_json(
        run_path / "run_state.json",
        {
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
            "run_key": f"{state.simulation_id}::{ensemble_id}::0001",
            "run_dir": str(run_path),
            "config_path": str(run_path / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-30T09:55:00",
            "updated_at": "2026-03-30T10:10:00",
            "completed_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "status": "completed",
        },
    )
    (run_path / "twitter").mkdir(parents=True, exist_ok=True)
    (run_path / "twitter" / "actions.jsonl").write_text(
        json.dumps(
            {
                "round": 1,
                "timestamp": "2026-03-30T10:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "CREATE_POST",
                "action_args": {
                    "content": "I put this near 68%.",
                    "forecast_probability": 0.68,
                    "confidence": 0.55,
                    "rationale_tags": ["base_rate"],
                },
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    extractor_module = _load_simulation_market_extractor_module()
    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    extractor.persist_run_market_artifacts(
        state.simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
        run_dir=str(run_path),
    )
    belief_book_path = run_path / "agent_belief_book.json"
    belief_book = json.loads(belief_book_path.read_text(encoding="utf-8"))
    belief_book["beliefs"][0]["reference"]["source_artifact"] = "twitter/missing_actions.jsonl"
    belief_book_path.write_text(
        json.dumps(belief_book, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manager.attach_simulation_scope(
        "forecast-market-flow-invalid",
        simulation_id=state.simulation_id,
        ensemble_ids=[ensemble_id],
        run_ids=["0001"],
        latest_ensemble_id=ensemble_id,
        latest_run_id="0001",
        source_stage="integration_test",
    )
    workspace = manager.generate_hybrid_forecast_answer(
        "forecast-market-flow-invalid",
        requested_at="2026-03-30T10:35:00",
    )
    answer = workspace.forecast_answers[-1]
    simulation_market_trace = next(
        item
        for item in answer.answer_payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation_market"
    )

    assert simulation_market_trace["status"] == "abstained"
    assert simulation_market_trace["abstain_reason"] == "invalid_simulation_market_provenance"
    assert answer.answer_payload["abstain"] is True
