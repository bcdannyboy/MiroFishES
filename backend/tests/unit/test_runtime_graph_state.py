import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPO_ROOT / "backend" / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _configure_roots(monkeypatch, tmp_path: Path):
    config_module = importlib.import_module("app.config")
    project_module = importlib.import_module("app.models.project")

    simulations_dir = tmp_path / "simulations"
    projects_dir = tmp_path / "projects"
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
        raising=False,
    )
    simulations_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    return simulations_dir, project_module


def _seed_project(project_module, *, project_id: str, graph_id: str) -> None:
    project_dir = Path(project_module.ProjectManager.PROJECTS_DIR) / project_id
    _write_json(
        project_dir / "project.json",
        {
            "project_id": project_id,
            "name": "Runtime Graph Project",
            "status": "graph_completed",
            "created_at": "2026-03-31T08:00:00",
            "updated_at": "2026-03-31T08:00:00",
            "files": [],
            "total_text_length": 120,
            "graph_id": graph_id,
            "ontology": {
                "entity_types": [{"name": "Person", "attributes": []}],
                "edge_types": [],
            },
        },
    )
    project_module.ProjectManager.save_graph_entity_index(
        project_id,
        {
            "artifact_type": "graph_entity_index",
            "project_id": project_id,
            "graph_id": graph_id,
            "citation_coverage": 1.0,
            "entity_count": 1,
            "analytical_object_count": 2,
            "entities": [
                {
                    "uuid": "actor-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Tracks labor-market conditions.",
                    "attributes": {"role": "analyst"},
                    "related_nodes": [
                        {
                            "uuid": "topic-1",
                            "name": "Labor slowdown",
                            "labels": ["Entity", "Topic"],
                            "summary": "Employment is cooling.",
                        },
                        {
                            "uuid": "claim-1",
                            "name": "Hiring is weakening",
                            "labels": ["Entity", "Claim"],
                            "summary": "Payroll growth is softening.",
                        },
                    ],
                }
            ],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Labor slowdown",
                    "object_type": "topic",
                    "summary": "Employment is cooling.",
                    "provenance": {
                        "source_unit_ids": ["unit-1"],
                        "citations": [{"citation_id": "cit-1"}],
                    },
                    "related_nodes": [
                        {"uuid": "actor-1", "name": "Analyst", "labels": ["Entity", "Person"]}
                    ],
                },
                {
                    "uuid": "claim-1",
                    "name": "Hiring is weakening",
                    "object_type": "claim",
                    "summary": "Payroll growth is softening.",
                    "provenance": {
                        "source_unit_ids": ["unit-1"],
                        "citations": [{"citation_id": "cit-1"}],
                    },
                    "related_nodes": [
                        {"uuid": "actor-1", "name": "Analyst", "labels": ["Entity", "Person"]}
                    ],
                },
            ],
        },
    )


def _seed_run_layout(simulations_dir: Path, *, simulation_id: str, project_id: str, graph_id: str) -> Path:
    sim_dir = simulations_dir / simulation_id
    run_dir = sim_dir / "ensemble" / "ensemble_0001" / "runs" / "run_0001"
    _write_json(
        sim_dir / "prepared_world_state.json",
        {
            "artifact_type": "prepared_world_state",
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "world_summary": {
                "headline": "Labor slowdown concerns rise",
                "topic_count": 1,
            },
            "retrieval_contract": {"status": "ready"},
            "grounding_summary": {"status": "ready"},
            "registries": {
                "topics": [
                    {
                        "uuid": "topic-1",
                        "name": "Labor slowdown",
                        "citation_ids": ["cit-1"],
                        "source_unit_ids": ["unit-1"],
                        "linked_actor_uuids": ["actor-1"],
                    }
                ],
                "claims": [
                    {
                        "uuid": "claim-1",
                        "name": "Hiring is weakening",
                        "citation_ids": ["cit-1"],
                        "source_unit_ids": ["unit-1"],
                        "linked_actor_uuids": ["actor-1"],
                    }
                ],
                "evidence": [],
                "metrics": [],
                "time_windows": [],
                "scenarios": [],
                "uncertainty_factors": [],
                "events": [],
            },
            "evidence_signals": [
                {
                    "signal_id": "sig-1",
                    "label": "Hiring is weakening",
                    "topic_names": ["Labor slowdown"],
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                }
            ],
            "citation_ids": ["cit-1"],
            "source_unit_ids": ["unit-1"],
            "conflict_summary": {"contradiction_count": 0},
            "missing_evidence_markers": [],
        },
    )
    _write_json(
        sim_dir / "prepared_agent_states.json",
        {
            "artifact_type": "prepared_agent_states",
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "agent_state_count": 1,
            "agent_states": [
                {
                    "entity_uuid": "actor-1",
                    "entity_name": "Analyst",
                    "entity_type": "Person",
                    "topic_names": ["Labor slowdown"],
                    "claim_names": ["Hiring is weakening"],
                    "evidence_names": ["Payroll report"],
                    "metric_names": ["Payroll growth"],
                    "time_window_names": ["Q2 2026"],
                    "scenario_names": ["Soft landing"],
                    "event_names": ["Payroll miss"],
                    "uncertainty_names": ["Survey noise"],
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "evidence_signals": [{"signal_id": "sig-1"}],
                    "stance_hint": "cautious",
                    "sentiment_bias_hint": "neutral",
                    "worldview_summary": "Focuses on macro labor signals.",
                }
            ],
        },
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": "0001",
            "status": "prepared",
            "base_graph_id": graph_id,
            "runtime_graph_id": None,
            "artifact_paths": {
                "resolved_config": "resolved_config.json",
            },
        },
    )
    _write_json(
        run_dir / "resolved_config.json",
        {
            "artifact_type": "resolved_config",
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": project_id,
            "graph_id": graph_id,
            "base_graph_id": graph_id,
            "time_config": {
                "total_simulation_hours": 24,
                "minutes_per_round": 60,
            },
        },
    )
    return run_dir


class _FakeGraphBackend:
    def __init__(self):
        self.create_calls = []
        self.ontology_calls = []
        self.deleted_graph_ids = []

    def create_runtime_graph(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
        project_id: str | None = None,
        project_name: str | None = None,
    ) -> dict:
        namespace_id = f"mirofish-runtime-{simulation_id}-{ensemble_id}-{run_id}"
        descriptor = {
            "namespace_id": namespace_id,
            "group_id": namespace_id,
            "graph_scope": "runtime",
            "display_name": f"{project_name or project_id or simulation_id} runtime graph",
        }
        self.create_calls.append(
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "project_id": project_id,
                "project_name": project_name,
                "descriptor": descriptor,
            }
        )
        return descriptor

    def register_ontology(self, graph_id: str, ontology: dict) -> None:
        self.ontology_calls.append((graph_id, ontology))

    def delete_graph(self, graph_id: str) -> None:
        self.deleted_graph_ids.append(graph_id)


def test_runtime_graph_manager_provision_hydrates_base_snapshot_and_runtime_state(tmp_path, monkeypatch):
    simulations_dir, project_module = _configure_roots(monkeypatch, tmp_path)
    simulation_id = "sim-runtime-foundation"
    project_id = "proj-runtime"
    base_graph_id = "graph-base-1"

    _seed_project(project_module, project_id=project_id, graph_id=base_graph_id)
    run_dir = _seed_run_layout(
        simulations_dir,
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=base_graph_id,
    )

    runtime_module = importlib.import_module("app.services.runtime_graph_manager")
    ensemble_module = importlib.import_module("app.services.ensemble_manager")

    graph_backend = _FakeGraphBackend()
    manager = runtime_module.RuntimeGraphManager(
        graph_backend=graph_backend,
        ensemble_manager=ensemble_module.EnsembleManager(
            simulation_data_dir=str(simulations_dir)
        ),
    )

    context = manager.provision_runtime_graph(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
        state=SimpleNamespace(
            project_id=project_id,
            graph_id=base_graph_id,
            base_graph_id=base_graph_id,
        ),
    )

    expected_runtime_graph_id = f"mirofish-runtime-{simulation_id}-0001-0001"

    assert context["base_graph_id"] == base_graph_id
    assert context["runtime_graph_id"] == expected_runtime_graph_id

    snapshot = json.loads(
        (run_dir / "runtime_graph_base_snapshot.json").read_text(encoding="utf-8")
    )
    runtime_state = json.loads(
        (run_dir / "runtime_graph_state.json").read_text(encoding="utf-8")
    )
    updates_log = run_dir / "runtime_graph_updates.jsonl"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    resolved_config = json.loads((run_dir / "resolved_config.json").read_text(encoding="utf-8"))

    assert snapshot["artifact_type"] == "runtime_graph_base_snapshot"
    assert snapshot["simulation_id"] == simulation_id
    assert snapshot["base_graph_id"] == base_graph_id
    assert snapshot["runtime_graph_id"] == expected_runtime_graph_id
    assert snapshot["actor_count"] == 1
    assert snapshot["analytical_object_count"] == 2
    assert snapshot["source_artifacts"]["prepared_world_state"] == "prepared_world_state.json"
    assert snapshot["source_artifacts"]["prepared_agent_states"] == "prepared_agent_states.json"
    assert snapshot["source_artifacts"]["graph_entity_index"] == "graph_entity_index.json"
    assert snapshot["actors"][0]["entity_uuid"] == "actor-1"
    assert set(snapshot["actors"][0]["topic_names"]) == {"Labor slowdown"}
    assert snapshot["namespace_model"] == "application-managed"
    assert snapshot["graph_backend"] == "graphiti_neo4j"
    assert snapshot["namespaces"]["base"] == {
        "namespace_id": base_graph_id,
        "group_id": base_graph_id,
        "graph_scope": "base",
        "display_name": base_graph_id,
    }
    assert snapshot["namespaces"]["runtime"] == graph_backend.create_calls[0]["descriptor"]

    assert runtime_state["artifact_type"] == "runtime_graph_state"
    assert runtime_state["base_snapshot_artifact"] == "runtime_graph_base_snapshot.json"
    assert runtime_state["transition_log_artifact"] == "runtime_graph_updates.jsonl"
    assert runtime_state["transition_count"] == 0
    assert runtime_state["transition_counts"]["claim"] == 0
    assert runtime_state["world_summary"]["headline"] == "Labor slowdown concerns rise"
    assert runtime_state["platform_status"]["twitter"] == "pending"
    assert runtime_state["platform_status"]["reddit"] == "pending"
    assert runtime_state["namespace_model"] == "application-managed"
    assert runtime_state["graph_backend"] == "graphiti_neo4j"
    assert runtime_state["namespaces"]["runtime"] == graph_backend.create_calls[0]["descriptor"]
    assert updates_log.exists()
    assert updates_log.read_text(encoding="utf-8") == ""

    assert manifest["runtime_graph_id"] == expected_runtime_graph_id
    assert manifest["graph_namespace_model"] == "application-managed"
    assert manifest["runtime_graph_namespace"] == graph_backend.create_calls[0]["descriptor"]
    assert manifest["artifact_paths"]["runtime_graph_base_snapshot"] == "runtime_graph_base_snapshot.json"
    assert manifest["artifact_paths"]["runtime_graph_state"] == "runtime_graph_state.json"
    assert manifest["artifact_paths"]["runtime_graph_updates"] == "runtime_graph_updates.jsonl"
    assert resolved_config["graph_namespace_model"] == "application-managed"
    assert resolved_config["runtime_graph_namespace"] == graph_backend.create_calls[0]["descriptor"]
    assert resolved_config["runtime_graph_state_artifact"] == "runtime_graph_state.json"
    assert graph_backend.ontology_calls[0][0] == expected_runtime_graph_id


def test_runtime_graph_manager_cleanup_clears_runtime_artifacts_and_ids(tmp_path, monkeypatch):
    simulations_dir, project_module = _configure_roots(monkeypatch, tmp_path)
    simulation_id = "sim-runtime-cleanup"
    project_id = "proj-runtime"
    base_graph_id = "graph-base-1"

    _seed_project(project_module, project_id=project_id, graph_id=base_graph_id)
    run_dir = _seed_run_layout(
        simulations_dir,
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=base_graph_id,
    )

    runtime_module = importlib.import_module("app.services.runtime_graph_manager")
    ensemble_module = importlib.import_module("app.services.ensemble_manager")

    graph_backend = _FakeGraphBackend()
    manager = runtime_module.RuntimeGraphManager(
        graph_backend=graph_backend,
        ensemble_manager=ensemble_module.EnsembleManager(
            simulation_data_dir=str(simulations_dir)
        ),
    )
    manager.provision_runtime_graph(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
        state=SimpleNamespace(
            project_id=project_id,
            graph_id=base_graph_id,
            base_graph_id=base_graph_id,
        ),
    )

    cleanup = manager.cleanup_runtime_graph(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))

    assert cleanup["deleted_runtime_graph_id"] == (
        f"mirofish-runtime-{simulation_id}-0001-0001"
    )
    assert cleanup["runtime_graph_id"] is None
    assert graph_backend.deleted_graph_ids == [
        f"mirofish-runtime-{simulation_id}-0001-0001"
    ]
    assert manifest["base_graph_id"] == base_graph_id
    assert manifest["runtime_graph_id"] is None
    assert "runtime_graph_base_snapshot" not in manifest["artifact_paths"]
    assert "runtime_graph_state" not in manifest["artifact_paths"]
    assert "runtime_graph_updates" not in manifest["artifact_paths"]
    assert (run_dir / "runtime_graph_base_snapshot.json").exists() is False
    assert (run_dir / "runtime_graph_state.json").exists() is False
    assert (run_dir / "runtime_graph_updates.jsonl").exists() is False


def test_runtime_graph_manager_force_reset_deletes_existing_runtime_namespace_before_reprovision(
    tmp_path, monkeypatch
):
    simulations_dir, project_module = _configure_roots(monkeypatch, tmp_path)
    simulation_id = "sim-runtime-reset"
    project_id = "proj-runtime"
    base_graph_id = "graph-base-1"

    _seed_project(project_module, project_id=project_id, graph_id=base_graph_id)
    run_dir = _seed_run_layout(
        simulations_dir,
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=base_graph_id,
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["runtime_graph_id"] = "legacy-runtime-graph"
    _write_json(run_dir / "run_manifest.json", manifest)

    runtime_module = importlib.import_module("app.services.runtime_graph_manager")
    ensemble_module = importlib.import_module("app.services.ensemble_manager")

    graph_backend = _FakeGraphBackend()
    manager = runtime_module.RuntimeGraphManager(
        graph_backend=graph_backend,
        ensemble_manager=ensemble_module.EnsembleManager(
            simulation_data_dir=str(simulations_dir)
        ),
    )

    context = manager.provision_runtime_graph(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
        state=SimpleNamespace(
            project_id=project_id,
            graph_id=base_graph_id,
            base_graph_id=base_graph_id,
        ),
        force_reset=True,
    )

    assert graph_backend.deleted_graph_ids == ["legacy-runtime-graph"]
    assert context["runtime_graph_id"] == "mirofish-runtime-sim-runtime-reset-0001-0001"
