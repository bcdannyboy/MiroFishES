import csv
import importlib
import json
from pathlib import Path

from flask import Flask


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_simulation_api_module():
    return importlib.import_module("app.api.simulation")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _configure_project_grounding_dir(monkeypatch, project_root: Path):
    project_module = importlib.import_module("app.models.project")
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(project_root),
        raising=False,
    )
    return project_module


def _write_project_grounding_artifacts(
    monkeypatch,
    project_root: Path,
    *,
    project_id: str,
    graph_id: str = "graph-1",
):
    _configure_project_grounding_dir(monkeypatch, project_root)
    project_dir = project_root / project_id
    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": "Forecast discussion spread",
            "boundary_note": "Uploaded project sources only; this artifact does not claim live-web coverage.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "memo.md",
                    "saved_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "size_bytes": 10,
                    "sha256": "abc123",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 42,
                    "combined_text_start": 0,
                    "combined_text_end": 42,
                    "parser_warnings": [],
                    "excerpt": "Workers mention slowdown risk and policy response.",
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
                "analysis_summary": "Uploaded evidence emphasizes labor-policy timing.",
                "entity_type_count": 1,
                "edge_type_count": 1,
            },
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 2,
            "graph_counts": {
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person"],
            },
            "warnings": [],
        },
    )


def _build_test_client(simulation_module):
    app = Flask(__name__)
    app.register_blueprint(simulation_module.simulation_bp, url_prefix="/api/simulation")
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
        self.generation_reasoning = "Test reasoning"
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
            "generated_at": "2026-03-08T12:00:00",
            "generation_reasoning": "Test reasoning",
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


class _FakeActionRecord:
    def __init__(self, **payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


def _install_prepare_stubs(monkeypatch, manager_module):
    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _FakeSimulationConfigGenerator
    )


def _prepare_simulation(
    simulation_data_dir,
    monkeypatch,
    probabilistic_mode=True,
    with_grounding=True,
):
    manager_module = _load_manager_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)
    if probabilistic_mode and with_grounding:
        _write_project_grounding_artifacts(
            monkeypatch,
            Path(simulation_data_dir).parent / "projects",
            project_id="proj-1",
            graph_id="graph-1",
        )

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=probabilistic_mode,
        uncertainty_profile="balanced" if probabilistic_mode else None,
        outcome_metrics=["simulation.total_actions"] if probabilistic_mode else None,
    )
    return state


def test_ensemble_create_endpoint_persists_simulation_scoped_storage(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == "0001"
    assert payload["state"]["prepared_run_count"] == 2
    assert payload["state"]["run_ids"] == ["0001", "0002"]
    assert payload["runs"][0]["seed_metadata"]["resolution_seed"] == 17


def test_ensemble_endpoints_list_and_load_runs(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 23,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]

    list_response = client.get(f"/api/simulation/{state.simulation_id}/ensembles")
    detail_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}"
    )
    runs_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs"
    )
    run_detail_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001"
    )

    assert list_response.status_code == 200
    assert list_response.get_json()["data"][0]["ensemble_id"] == ensemble_id

    assert detail_response.status_code == 200
    assert detail_response.get_json()["data"]["state"]["root_seed"] == 23

    assert runs_response.status_code == 200
    assert runs_response.get_json()["data"]["total_runs"] == 2
    assert runs_response.get_json()["data"]["truncated"] is False
    assert [run["run_id"] for run in runs_response.get_json()["data"]["runs"]] == [
        "0001",
        "0002",
    ]

    assert run_detail_response.status_code == 200
    assert (
        run_detail_response.get_json()["data"]["run_manifest"]["seed_metadata"]["resolution_seed"]
        == 23
    )


def test_ensemble_run_detail_endpoint_includes_runtime_status(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 37,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        captures.update(
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
            }
        )
        return _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001"
    )

    assert response.status_code == 200
    assert captures == {
        "simulation_id": state.simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": "0001",
    }
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["runtime_status"]["simulation_id"] == state.simulation_id
    assert payload["runtime_status"]["ensemble_id"] == ensemble_id
    assert payload["runtime_status"]["run_id"] == "0001"
    assert payload["runtime_status"]["runner_status"] == "running"
    assert payload["runtime_status"]["storage_status"] == "prepared"


def test_ensemble_run_actions_endpoint_uses_run_scoped_runner_helpers(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 53,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    class _FakeAction:
        def to_dict(self):
            return {
                "round_num": 4,
                "platform": "twitter",
                "agent_id": 7,
                "agent_name": "Agent Seven",
                "action_type": "CREATE_POST",
                "action_args": {"content": "hello"},
                "success": True,
            }

    def _fake_get_actions(**kwargs):
        captures.update(kwargs)
        return [_FakeAction()]

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_actions",
        _fake_get_actions,
        raising=False,
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/actions"
            "?limit=2&offset=3&platform=twitter&agent_id=7&round_num=4"
        )
    )

    assert response.status_code == 200
    assert captures == {
        "simulation_id": state.simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": "0001",
        "limit": 2,
        "offset": 3,
        "platform": "twitter",
        "agent_id": 7,
        "round_num": 4,
    }
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["count"] == 1
    assert payload["actions"][0]["agent_id"] == 7
    assert payload["actions"][0]["platform"] == "twitter"


def test_ensemble_run_timeline_endpoint_uses_run_scoped_runner_helpers(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 59,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_get_timeline(
        simulation_id,
        ensemble_id=None,
        run_id=None,
        start_round=0,
        end_round=None,
    ):
        captures.update(
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "start_round": start_round,
                "end_round": end_round,
            }
        )
        return [
            {
                "round_num": 3,
                "twitter_actions_count": 2,
                "reddit_actions_count": 1,
                "total_actions_count": 3,
            }
        ]

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_timeline",
        _fake_get_timeline,
        raising=False,
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/timeline"
            "?start_round=3&end_round=8"
        )
    )

    assert response.status_code == 200
    assert captures == {
        "simulation_id": state.simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": "0001",
        "start_round": 3,
        "end_round": 8,
    }
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["count"] == 1
    assert payload["timeline"][0]["round_num"] == 3


def test_ensemble_summary_endpoint_returns_aggregate_summary(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
    )

    client = _build_test_client(simulation_module)
    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    run_path = Path(create_response.get_json()["data"]["runs"][0]["path"])
    (run_path / "metrics.json").write_text(
        json.dumps(
            {
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 3,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/summary"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert (
        payload["metric_summaries"]["simulation.total_actions"]["mean"] == 3.0
    )


def test_ensemble_clusters_endpoint_returns_scenario_clusters(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
    )

    client = _build_test_client(simulation_module)
    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    run_path = Path(create_response.get_json()["data"]["runs"][0]["path"])
    (run_path / "metrics.json").write_text(
        json.dumps(
            {
                "extracted_at": "2026-03-08T12:00:00",
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 3,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/clusters"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["cluster_count"] == 1
    assert payload["clusters"][0]["prototype_run_id"] == "0001"


def test_ensemble_sensitivity_endpoint_returns_sensitivity_artifact(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
    )

    client = _build_test_client(simulation_module)
    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_paths = {
        run["run_id"]: Path(run["path"])
        for run in payload["runs"]
    }

    manifest_one = json.loads(
        (run_paths["0001"] / "run_manifest.json").read_text(encoding="utf-8")
    )
    manifest_one["resolved_values"] = {
        "twitter_config.echo_chamber_strength": 0.2,
    }
    (run_paths["0001"] / "run_manifest.json").write_text(
        json.dumps(manifest_one, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_paths["0001"] / "metrics.json").write_text(
        json.dumps(
            {
                "extracted_at": "2026-03-09T12:00:01",
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 3,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest_two = json.loads(
        (run_paths["0002"] / "run_manifest.json").read_text(encoding="utf-8")
    )
    manifest_two["resolved_values"] = {
        "twitter_config.echo_chamber_strength": 0.8,
    }
    (run_paths["0002"] / "run_manifest.json").write_text(
        json.dumps(manifest_two, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_paths["0002"] / "metrics.json").write_text(
        json.dumps(
            {
                "extracted_at": "2026-03-09T12:00:02",
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 9,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/sensitivity"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["simulation_id"] == state.simulation_id
    assert data["ensemble_id"] == ensemble_id
    assert data["artifact_type"] == "sensitivity"
    assert data["methodology"]["analysis_mode"] == "observational_resolved_values"
    assert data["driver_rankings"][0]["driver_id"] == "twitter_config.echo_chamber_strength"


def test_ensemble_sensitivity_endpoint_returns_driver_rankings(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
    )

    client = _build_test_client(simulation_module)
    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    run_one_path = Path(create_response.get_json()["data"]["runs"][0]["path"])
    run_two_path = Path(create_response.get_json()["data"]["runs"][1]["path"])

    run_one_manifest = json.loads(
        (run_one_path / "run_manifest.json").read_text(encoding="utf-8")
    )
    run_one_manifest["resolved_values"] = {
        "twitter_config.echo_chamber_strength": 0.2
    }
    (run_one_path / "run_manifest.json").write_text(
        json.dumps(run_one_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_one_path / "metrics.json").write_text(
        json.dumps(
            {
                "extracted_at": "2026-03-08T12:00:01",
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 3,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    run_two_manifest = json.loads(
        (run_two_path / "run_manifest.json").read_text(encoding="utf-8")
    )
    run_two_manifest["resolved_values"] = {
        "twitter_config.echo_chamber_strength": 0.8
    }
    (run_two_path / "run_manifest.json").write_text(
        json.dumps(run_two_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_two_path / "metrics.json").write_text(
        json.dumps(
            {
                "extracted_at": "2026-03-08T12:00:02",
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    "simulation.total_actions": {
                        "metric_id": "simulation.total_actions",
                        "label": "Simulation Total Actions",
                        "aggregation": "count",
                        "unit": "count",
                        "probability_mode": "empirical",
                        "value": 11,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/sensitivity"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["driver_count"] == 1
    assert payload["driver_rankings"][0]["field_path"] == (
        "twitter_config.echo_chamber_strength"
    )


def test_ensemble_create_endpoint_rejects_disabled_flag(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        False,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
        },
    )

    assert response.status_code == 403
    assert "disabled" in response.get_json()["error"]


def test_prepare_capabilities_endpoint_reports_ensemble_storage_flag(monkeypatch):
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.Config,
        "ENSEMBLE_RUNTIME_ENABLED",
        False,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.get("/api/simulation/prepare/capabilities")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["probabilistic_ensemble_storage_enabled"] is True
    assert payload["ensemble_runtime_enabled"] is True


def test_ensemble_create_endpoint_rejects_legacy_prepare_inputs(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=False)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Forecast artifacts are incomplete. Missing files: "
        "simulation_config.base.json, grounding_bundle.json, uncertainty_spec.json, "
        "outcome_spec.json, prepared_snapshot.json."
    )


def test_ensemble_create_endpoint_rejects_partial_probabilistic_sidecars(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_dir = Path(simulation_data_dir) / state.simulation_id
    (simulation_dir / "uncertainty_spec.json").unlink()

    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir)
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "uncertainty_spec.json" in payload["error"]
    assert payload["prepare_info"]["prepared_artifact_summary"]["probabilistic_mode"] is False
    assert (
        "uncertainty_spec.json"
        in payload["prepare_info"]["prepared_artifact_summary"]["missing_probabilistic_artifacts"]
    )


def test_ensemble_create_endpoint_rejects_unready_grounding_bundle(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(
        simulation_data_dir,
        monkeypatch,
        probabilistic_mode=True,
        with_grounding=False,
    )

    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir)
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert (
        payload["error"]
        == "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
    )
    assert payload["prepare_info"]["prepared_artifact_summary"]["artifact_completeness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "missing_artifacts": [],
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["grounding_readiness"] == {
        "ready": False,
        "status": "unavailable",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["forecast_readiness"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["workflow_handoff_status"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
        "semantics": "workflow_handoff_status",
    }


def test_ensemble_runs_endpoint_applies_result_cap(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 3,
            "max_concurrency": 1,
            "root_seed": 31,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]

    runs_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs?limit=2"
    )

    assert runs_response.status_code == 200
    payload = runs_response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["limit"] == 2
    assert payload["total_runs"] == 3
    assert payload["truncated"] is True
    assert [run["run_id"] for run in payload["runs"]] == ["0001", "0002"]


def test_ensemble_run_start_endpoint_launches_one_member_run(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 31,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_start_simulation(**kwargs):
        captures.update(kwargs)
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
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

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/start"
        ),
        json={
            "platform": "parallel",
            "max_rounds": 9,
            "close_environment_on_complete": True,
        },
    )

    assert response.status_code == 200
    assert captures["simulation_id"] == state.simulation_id
    assert captures["ensemble_id"] == ensemble_id
    assert captures["run_id"] == "0001"
    assert captures["platform"] == "parallel"
    assert captures["max_rounds"] == 9
    assert captures["close_environment_on_complete"] is True
    payload = response.get_json()["data"]
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["runner_status"] == "running"
    assert payload["close_environment_on_complete"] is True


def test_ensemble_run_start_endpoint_rejects_launch_when_concurrency_is_full(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 31,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    start_calls = []

    def _fake_start_simulation(**kwargs):
        start_calls.append(kwargs)
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
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
        lambda simulation_id, ensemble_id=None, run_id=None: (
            _FakeRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                runner_status="running",
            )
            if run_id == "0001"
            else None
        ),
        raising=False,
    )

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0002/start"
        ),
        json={
            "platform": "parallel",
        },
    )

    assert response.status_code == 400
    assert start_calls == []
    payload = response.get_json()
    assert "max_concurrency" in payload["error"]
    assert "0001" in payload["error"]
    assert payload["active_run_ids"] == ["0001"]
    assert payload["max_concurrency"] == 1


def test_ensemble_run_start_endpoint_provisions_runtime_graph_and_returns_graph_ids(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 31,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {"start": None, "runtime_graph": None}

    class _FakeRuntimeGraphManager:
        def provision_runtime_graph(
            self,
            *,
            simulation_id,
            ensemble_id,
            run_id,
            state,
            force_reset=False,
        ):
            captures["runtime_graph"] = {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "base_graph_id": state.graph_id,
                "force_reset": force_reset,
            }
            return {
                "base_graph_id": state.graph_id,
                "runtime_graph_id": "runtime-graph-1",
            }

    def _fake_start_simulation(**kwargs):
        captures["start"] = kwargs
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module,
        "RuntimeGraphManager",
        lambda: _FakeRuntimeGraphManager(),
        raising=False,
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

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/start"
        ),
        json={
            "platform": "parallel",
            "max_rounds": 9,
            "enable_graph_memory_update": True,
            "close_environment_on_complete": True,
        },
    )

    assert response.status_code == 200
    assert captures["runtime_graph"] == {
        "simulation_id": state.simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": "0001",
        "base_graph_id": "graph-1",
        "force_reset": False,
    }
    assert captures["start"]["graph_id"] == "runtime-graph-1"
    payload = response.get_json()["data"]
    assert payload["graph_memory_update_enabled"] is True
    assert payload["graph_id"] == "graph-1"
    assert payload["base_graph_id"] == "graph-1"
    assert payload["runtime_graph_id"] == "runtime-graph-1"


def test_ensemble_run_status_endpoint_returns_run_scoped_state(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 19,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        ),
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/run-status"
        )
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["runner_status"] == "running"


def test_ensemble_run_status_endpoint_includes_base_and_runtime_graph_ids(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 19,
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_path = Path(payload["runs"][0]["path"])
    manifest_path = run_path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["base_graph_id"] = "graph-1"
    manifest["runtime_graph_id"] = "runtime-graph-1"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        ),
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/run-status"
        )
    )

    assert response.status_code == 200
    run_status = response.get_json()["data"]
    assert run_status["base_graph_id"] == "graph-1"
    assert run_status["runtime_graph_id"] == "runtime-graph-1"
    assert run_status["graph_id"] == "graph-1"


def test_ensemble_run_stop_endpoint_targets_one_member_run(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 29,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_stop_simulation(simulation_id, ensemble_id=None, run_id=None):
        captures.update(
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
            }
        )
        return _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="stopped",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "stop_simulation",
        _fake_stop_simulation,
        raising=False,
    )

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/stop"
        )
    )

    assert response.status_code == 200
    assert captures == {
        "simulation_id": state.simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": "0001",
    }
    payload = response.get_json()["data"]
    assert payload["runner_status"] == "stopped"
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"


def test_ensemble_start_endpoint_launches_all_member_runs_when_capacity_allows(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 2,
            "root_seed": 41,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = []

    def _fake_start_simulation(**kwargs):
        captures.append(kwargs)
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
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

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/start",
        json={
            "platform": "parallel",
            "max_rounds": 9,
        },
    )

    assert response.status_code == 200
    assert len(captures) == 2
    assert [capture["run_id"] for capture in captures] == ["0001", "0002"]
    assert all(capture["simulation_id"] == state.simulation_id for capture in captures)
    assert all(capture["ensemble_id"] == ensemble_id for capture in captures)
    assert all(capture["platform"] == "parallel" for capture in captures)
    assert all(capture["max_rounds"] == 9 for capture in captures)
    assert all(capture["close_environment_on_complete"] is False for capture in captures)

    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["requested_run_ids"] == ["0001", "0002"]
    assert payload["started_run_count"] == 2
    assert payload["started_run_ids"] == ["0001", "0002"]
    assert payload["deferred_run_ids"] == []
    assert payload["active_run_ids"] == []
    assert [run["run_id"] for run in payload["runs"]] == ["0001", "0002"]
    assert all(run["runner_status"] == "running" for run in payload["runs"])


def test_ensemble_status_endpoint_returns_poll_safe_summary(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 3,
            "max_concurrency": 1,
            "root_seed": 43,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]

    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        if run_id == "0001":
            return _FakeRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                runner_status="running",
            )
        if run_id == "0002":
            return _FakeRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                runner_status="completed",
            )
        return None

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/status?limit=2"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["total_runs"] == 3
    assert payload["limit"] == 2
    assert payload["truncated"] is True
    assert payload["ensemble_status"] == "running"
    assert payload["status_counts"] == {
        "prepared": 1,
        "running": 1,
        "completed": 1,
    }
    assert payload["active_run_ids"] == ["0001"]
    assert payload["completed_run_ids"] == ["0002"]
    assert [run["run_id"] for run in payload["runs"]] == ["0001", "0002"]
    assert [run["runner_status"] for run in payload["runs"]] == [
        "running",
        "completed",
    ]


def test_ensemble_status_endpoint_uses_completed_storage_status_when_runtime_state_is_missing(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 47,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    manifest_path = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{ensemble_id}"
        / "runs"
        / "run_0001"
        / "run_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/status?limit=5"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["ensemble_status"] == "completed"
    assert payload["status_counts"] == {"completed": 1}
    assert payload["completed_run_ids"] == ["0001"]
    assert payload["storage_status_counts"] == {"completed": 1}
    assert payload["runner_status_counts"] == {"idle": 1}
    assert payload["runs"][0]["storage_status"] == "completed"
    assert payload["runs"][0]["runner_status"] == "idle"


def test_ensemble_status_endpoint_keeps_active_runs_dominant_when_other_runs_only_have_storage_completion(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 53,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    manifest_path = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{ensemble_id}"
        / "runs"
        / "run_0002"
        / "run_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        if run_id == "0001":
            return _FakeRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                runner_status="running",
            )
        return None

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/status?limit=5"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["ensemble_status"] == "running"
    assert payload["status_counts"] == {
        "running": 1,
        "completed": 1,
    }
    assert payload["active_run_ids"] == ["0001"]
    assert payload["completed_run_ids"] == ["0002"]
    assert payload["runs"][1]["storage_status"] == "completed"
    assert payload["runs"][1]["runner_status"] == "idle"


def test_ensemble_start_endpoint_enforces_max_concurrency_and_reports_active_context(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 3,
            "max_concurrency": 2,
            "root_seed": 47,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    start_calls = []

    def _fake_start_simulation(**kwargs):
        start_calls.append(kwargs)
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
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
        lambda simulation_id, ensemble_id=None, run_id=None: (
            _FakeRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                runner_status="running",
            )
            if run_id == "0001"
            else None
        ),
        raising=False,
    )

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/start",
        json={"platform": "parallel"},
    )

    assert response.status_code == 200
    assert [call["run_id"] for call in start_calls] == ["0002"]
    payload = response.get_json()["data"]
    assert payload["requested_run_ids"] == ["0001", "0002", "0003"]
    assert payload["started_run_ids"] == ["0002"]
    assert payload["deferred_run_ids"] == ["0003"]
    assert payload["started_run_count"] == 1
    assert payload["deferred_run_count"] == 1
    assert payload["active_run_ids"] == ["0001"]
    assert payload["active_requested_run_ids"] == ["0001"]
    assert payload["active_other_run_ids"] == []
    assert payload["active_run_count"] == 1
    assert payload["available_start_slots"] == 1
    assert [run["run_id"] for run in payload["runs"]] == ["0002"]


def test_ensemble_run_start_endpoint_force_retries_active_member_run(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 49,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {
        "stopped": [],
        "cleaned": [],
        "started": [],
    }

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "stop_simulation",
        lambda simulation_id, ensemble_id=None, run_id=None: captures["stopped"].append(
            (simulation_id, ensemble_id, run_id)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "cleanup_simulation_logs",
        lambda simulation_id, ensemble_id=None, run_id=None: captures["cleaned"].append(
            (simulation_id, ensemble_id, run_id)
        ),
        raising=False,
    )

    def _fake_start_simulation(**kwargs):
        captures["started"].append(kwargs)
        return _FakeRunState(
            simulation_id=kwargs["simulation_id"],
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

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/"
            f"{ensemble_id}/runs/0001/start"
        ),
        json={
            "platform": "parallel",
            "force": True,
        },
    )

    assert response.status_code == 200
    assert captures["stopped"] == [(state.simulation_id, ensemble_id, "0001")]
    assert captures["cleaned"] == [(state.simulation_id, ensemble_id, "0001")]
    assert [capture["run_id"] for capture in captures["started"]] == ["0001"]

    payload = response.get_json()["data"]
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["runner_status"] == "running"
    assert payload["force_restarted"] is True


def test_ensemble_run_detail_includes_runtime_status(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 53,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: _FakeRunState(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        ),
        raising=False,
    )

    response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001"
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["run_id"] == "0001"
    assert payload["runtime_status"]["simulation_id"] == state.simulation_id
    assert payload["runtime_status"]["ensemble_id"] == ensemble_id
    assert payload["runtime_status"]["run_id"] == "0001"
    assert payload["runtime_status"]["runner_status"] == "running"


def test_ensemble_run_actions_endpoint_is_run_scoped(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 59,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_get_actions(**kwargs):
        captures.update(kwargs)
        return [
            _FakeActionRecord(
                round_num=1,
                timestamp="2026-03-08T12:00:00",
                platform="twitter",
                agent_id=7,
                agent_name="Analyst",
                action_type="CREATE_POST",
                action_args={"content": "hello"},
                result=None,
                success=True,
            )
        ]

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_actions",
        _fake_get_actions,
        raising=False,
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/actions"
            "?limit=5&platform=twitter"
        )
    )

    assert response.status_code == 200
    assert captures["simulation_id"] == state.simulation_id
    assert captures["ensemble_id"] == ensemble_id
    assert captures["run_id"] == "0001"
    assert captures["limit"] == 5
    assert captures["platform"] == "twitter"
    payload = response.get_json()["data"]
    assert payload["count"] == 1
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["actions"][0]["agent_name"] == "Analyst"


def test_ensemble_run_timeline_endpoint_is_run_scoped(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 61,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    captures = {}

    def _fake_get_timeline(**kwargs):
        captures.update(kwargs)
        return [
            {
                "round_num": 1,
                "twitter_actions": 2,
                "reddit_actions": 1,
                "total_actions": 3,
            }
        ]

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_timeline",
        _fake_get_timeline,
        raising=False,
    )

    response = client.get(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/timeline"
            "?start_round=1&end_round=3"
        )
    )

    assert response.status_code == 200
    assert captures["simulation_id"] == state.simulation_id
    assert captures["ensemble_id"] == ensemble_id
    assert captures["run_id"] == "0001"
    assert captures["start_round"] == 1
    assert captures["end_round"] == 3
    payload = response.get_json()["data"]
    assert payload["count"] == 1
    assert payload["simulation_id"] == state.simulation_id
    assert payload["ensemble_id"] == ensemble_id
    assert payload["run_id"] == "0001"
    assert payload["timeline"][0]["total_actions"] == 3


def test_ensemble_run_rerun_endpoint_clones_run_with_lineage(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 61,
        },
    )
    ensemble_id = create_response.get_json()["data"]["ensemble_id"]
    source_run = create_response.get_json()["data"]["runs"][0]
    source_path = Path(source_run["path"])
    source_manifest = json.loads(
        (source_path / "run_manifest.json").read_text(encoding="utf-8")
    )
    source_manifest["status"] = "failed"
    source_manifest["lifecycle"] = {
        "start_count": 1,
        "retry_count": 0,
        "cleanup_count": 0,
        "last_launch_reason": "initial_start",
    }
    (source_path / "run_manifest.json").write_text(
        json.dumps(source_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    response = client.post(
        (
            f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}"
            "/runs/0001/rerun"
        )
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["source_run_id"] == "0001"
    assert payload["run"]["run_id"] == "0002"
    assert payload["run"]["status"] == "prepared"

    rerun_detail = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0002"
    )
    assert rerun_detail.status_code == 200
    rerun_manifest = rerun_detail.get_json()["data"]["run_manifest"]
    assert rerun_manifest["lineage"]["kind"] == "rerun"
    assert rerun_manifest["lineage"]["source_run_id"] == "0001"
    assert rerun_manifest["lineage"]["parent_run_id"] == "0001"
    assert rerun_manifest["lifecycle"]["start_count"] == 0
    assert rerun_manifest["lifecycle"]["retry_count"] == 0


def test_ensemble_cleanup_endpoint_resets_targeted_runs_only(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 71,
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_paths = {
        run["run_id"]: Path(run["path"])
        for run in payload["runs"]
    }

    for run_id, run_path in run_paths.items():
        (run_path / "simulation.log").write_text(f"log-{run_id}", encoding="utf-8")
        (run_path / "run_state.json").write_text("{}", encoding="utf-8")
        (run_path / "metrics.json").write_text("{}", encoding="utf-8")
        (run_path / "twitter").mkdir(parents=True, exist_ok=True)
        (run_path / "twitter" / "actions.jsonl").write_text("{}", encoding="utf-8")

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": ["0001"]},
    )

    assert response.status_code == 200
    cleanup_payload = response.get_json()["data"]
    assert cleanup_payload["cleaned_run_ids"] == ["0001"]
    assert cleanup_payload["cleaned_run_count"] == 1
    assert (run_paths["0001"] / "simulation.log").exists() is False
    assert (run_paths["0001"] / "metrics.json").exists() is False
    assert (run_paths["0001"] / "twitter" / "actions.jsonl").exists() is False
    assert (run_paths["0001"] / "resolved_config.json").exists() is True
    assert (run_paths["0002"] / "simulation.log").exists() is True


def test_ensemble_cleanup_endpoint_clears_in_memory_run_state(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 73,
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_path = Path(payload["runs"][0]["path"])
    run_id = payload["runs"][0]["run_id"]

    run_key = f"{state.simulation_id}::{ensemble_id}::{run_id}"
    simulation_module.SimulationRunner._run_states = {
        run_key: _FakeRunState(
            state.simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="completed",
        )
    }

    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        key = f"{simulation_id}::{ensemble_id}::{run_id}"
        return simulation_module.SimulationRunner._run_states.get(key)

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": [run_id]},
    )

    assert response.status_code == 200
    assert run_key not in simulation_module.SimulationRunner._run_states

    status_response = client.get(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/{run_id}/run-status"
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()["data"]
    assert status_payload["runner_status"] == "idle"
    assert status_payload["storage_status"] == "prepared"


def test_ensemble_cleanup_endpoint_deletes_runtime_graph_and_clears_runtime_graph_id(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 73,
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_payload = payload["runs"][0]
    run_path = Path(run_payload["path"])
    run_id = run_payload["run_id"]
    manifest_path = run_path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["base_graph_id"] = "graph-1"
    manifest["runtime_graph_id"] = "runtime-graph-1"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    captures = {"cleanup_runtime_graph": []}

    class _FakeRuntimeGraphManager:
        def cleanup_runtime_graph(self, *, simulation_id, ensemble_id, run_id):
            captures["cleanup_runtime_graph"].append(
                (simulation_id, ensemble_id, run_id)
            )
            return {
                "base_graph_id": "graph-1",
                "runtime_graph_id": None,
                "deleted_runtime_graph_id": "runtime-graph-1",
            }

    monkeypatch.setattr(
        simulation_module,
        "RuntimeGraphManager",
        lambda: _FakeRuntimeGraphManager(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": [run_id]},
    )

    assert response.status_code == 200
    assert captures["cleanup_runtime_graph"] == [
        (state.simulation_id, ensemble_id, run_id)
    ]
    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated_manifest["base_graph_id"] == "graph-1"
    assert updated_manifest["runtime_graph_id"] is None


def test_ensemble_cleanup_endpoint_rejects_active_runs(
    simulation_data_dir, monkeypatch
):
    state = _prepare_simulation(simulation_data_dir, monkeypatch, probabilistic_mode=True)
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 79,
        },
    )
    payload = create_response.get_json()["data"]
    ensemble_id = payload["ensemble_id"]
    run_path = Path(payload["runs"][0]["path"])
    run_id = payload["runs"][0]["run_id"]

    (run_path / "simulation.log").write_text("still-running", encoding="utf-8")
    (run_path / "run_state.json").write_text("{}", encoding="utf-8")

    run_key = f"{state.simulation_id}::{ensemble_id}::{run_id}"
    simulation_module.SimulationRunner._run_states = {
        run_key: _FakeRunState(
            state.simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            runner_status="running",
        )
    }

    def _fake_get_run_state(simulation_id, ensemble_id=None, run_id=None):
        key = f"{simulation_id}::{ensemble_id}::{run_id}"
        return simulation_module.SimulationRunner._run_states.get(key)

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        _fake_get_run_state,
        raising=False,
    )

    response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/cleanup",
        json={"run_ids": [run_id]},
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["active_run_ids"] == [run_id]
    assert run_key in simulation_module.SimulationRunner._run_states
    assert (run_path / "simulation.log").exists() is True
