import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"

for path in (BACKEND_ROOT, SCRIPTS_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _load_runner_module():
    sys.modules.pop("app.services.simulation_runner", None)
    return importlib.import_module("app.services.simulation_runner")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeGraphBuilder:
    def __init__(self):
        self.deleted = []

    def create_graph(self, _name: str) -> str:
        return "runtime-graph-integration"

    def set_ontology(self, _graph_id: str, _ontology: dict) -> None:
        return None

    def delete_graph(self, graph_id: str) -> None:
        self.deleted.append(graph_id)


def test_runtime_graph_components_hydrate_emit_and_cleanup_in_one_run(tmp_path, monkeypatch):
    config_module = importlib.import_module("app.config")
    project_module = importlib.import_module("app.models.project")
    ensemble_module = importlib.import_module("app.services.ensemble_manager")
    runtime_module = importlib.import_module("app.services.runtime_graph_manager")
    runner_module = _load_runner_module()
    action_logger_module = importlib.import_module("action_logger")

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
    monkeypatch.setattr(
        runner_module.SimulationRunner,
        "RUN_STATE_DIR",
        str(simulations_dir),
    )

    simulation_id = "sim-runtime-integration"
    project_id = "proj-runtime-integration"
    base_graph_id = "graph-base-integration"
    sim_dir = simulations_dir / simulation_id
    run_dir = sim_dir / "ensemble" / "ensemble_0001" / "runs" / "run_0001"

    _write_json(
        projects_dir / project_id / "project.json",
        {
            "project_id": project_id,
            "name": "Integration Runtime Project",
            "status": "graph_completed",
            "created_at": "2026-03-31T08:00:00",
            "updated_at": "2026-03-31T08:00:00",
            "files": [],
            "graph_id": base_graph_id,
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
            "graph_id": base_graph_id,
            "entity_count": 1,
            "analytical_object_count": 1,
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
                        }
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
                }
            ],
        },
    )
    _write_json(
        sim_dir / "prepared_world_state.json",
        {
            "artifact_type": "prepared_world_state",
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": base_graph_id,
            "world_summary": {"headline": "Labor slowdown concerns rise"},
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
                "claims": [],
                "evidence": [],
                "metrics": [],
                "time_windows": [],
                "scenarios": [],
                "uncertainty_factors": [],
                "events": [],
            },
            "evidence_signals": [],
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
            "graph_id": base_graph_id,
            "agent_state_count": 1,
            "agent_states": [
                {
                    "entity_uuid": "actor-1",
                    "entity_name": "Analyst",
                    "entity_type": "Person",
                    "topic_names": ["Labor slowdown"],
                    "claim_names": ["Hiring is weakening"],
                    "evidence_names": ["Payroll report"],
                    "metric_names": [],
                    "time_window_names": [],
                    "scenario_names": [],
                    "event_names": [],
                    "uncertainty_names": [],
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "evidence_signals": [],
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
            "artifact_paths": {"resolved_config": "resolved_config.json"},
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
            "graph_id": base_graph_id,
            "base_graph_id": base_graph_id,
            "time_config": {"total_simulation_hours": 12, "minutes_per_round": 60},
        },
    )

    manager = runtime_module.RuntimeGraphManager(
        graph_builder=_FakeGraphBuilder(),
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

    logger = action_logger_module.PlatformActionLogger("twitter", str(run_dir))
    logger.log_round_start(1, 8)
    logger.log_action(
        round_num=1,
        agent_id=7,
        agent_name="Analyst",
        action_type="CREATE_POST",
        action_args={"content": "Hiring is weakening.", "topic": "Labor slowdown"},
    )
    logger.log_round_end(1, 1)

    actions = runner_module.SimulationRunner.get_all_actions(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )
    runtime_state = json.loads(
        (run_dir / "runtime_graph_state.json").read_text(encoding="utf-8")
    )
    cleanup = runner_module.SimulationRunner.cleanup_simulation_logs(
        simulation_id=simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )

    assert [action.agent_name for action in actions] == ["Analyst"]
    assert runtime_state["transition_count"] >= 3
    assert runtime_state["transition_counts"]["claim"] == 1
    assert cleanup["success"] is True
    assert (run_dir / "runtime_graph_state.json").exists() is False
    assert (run_dir / "runtime_graph_updates.jsonl").exists() is False
    assert (run_dir / "runtime_graph_base_snapshot.json").exists() is False
