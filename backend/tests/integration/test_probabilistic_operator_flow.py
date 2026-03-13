import csv
import importlib
import json
from pathlib import Path


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_simulation_api_module():
    return importlib.import_module("app.api.simulation")


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

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
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
    assert (run_path / "simulation.log").exists() is True
    assert run_key in simulation_module.SimulationRunner._run_states

    status_response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/{run_id}/run-status"
        )
    )

    assert status_response.status_code == 200
    status_payload = status_response.get_json()["data"]
    assert status_payload["runner_status"] == "running"
    assert status_payload["run_id"] == run_id
