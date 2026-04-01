import importlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"

for path in (BACKEND_ROOT, SCRIPTS_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_runtime_state(tmp_path: Path, monkeypatch) -> Path:
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(tmp_path / "simulations"),
        raising=False,
    )

    state_module = importlib.import_module("app.services.runtime_graph_state_store")
    run_dir = (
        tmp_path
        / "simulations"
        / "sim-logger"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    store = state_module.RuntimeGraphStateStore(str(run_dir))
    store.initialize(
        simulation_id="sim-logger",
        ensemble_id="0001",
        run_id="0001",
        project_id="proj-logger",
        base_graph_id="graph-base-logger",
        runtime_graph_id="runtime-graph-logger",
        prepared_world_state={
            "artifact_type": "prepared_world_state",
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
        prepared_agent_states={
            "artifact_type": "prepared_agent_states",
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
                    "evidence_signals": [],
                    "stance_hint": "cautious",
                    "sentiment_bias_hint": "neutral",
                    "worldview_summary": "Focuses on macro labor signals.",
                }
            ],
        },
        graph_index_payload={
            "artifact_type": "graph_entity_index",
            "graph_id": "graph-base-logger",
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
        run_dir / "run_manifest.json",
        {
            "simulation_id": "sim-logger",
            "ensemble_id": "0001",
            "run_id": "0001",
            "base_graph_id": "graph-base-logger",
            "runtime_graph_id": "runtime-graph-logger",
        },
    )
    return run_dir


def test_platform_action_logger_dual_writes_structured_runtime_transitions(tmp_path, monkeypatch):
    run_dir = _seed_runtime_state(tmp_path, monkeypatch)
    action_logger_module = importlib.import_module("action_logger")

    logger = action_logger_module.PlatformActionLogger("twitter", str(run_dir))
    logger.log_simulation_start(
        {
            "time_config": {"total_simulation_hours": 12},
            "agent_configs": [{"agent_id": 7}],
        }
    )
    logger.log_event(
        round_num=0,
        event_name="Breaking payroll print",
        details={"content": "Payroll growth missed expectations."},
    )
    logger.log_round_start(1, 9)
    logger.log_action(
        round_num=1,
        agent_id=7,
        agent_name="Analyst",
        action_type="CREATE_POST",
        action_args={"content": "Hiring is weakening.", "topic": "Labor slowdown"},
    )
    logger.log_action(
        round_num=1,
        agent_id=7,
        agent_name="Analyst",
        action_type="LIKE_POST",
        action_args={
            "post_content": "Payroll growth slowed again.",
            "post_author_name": "Macro Desk",
            "topic": "Labor slowdown",
        },
    )
    logger.log_action(
        round_num=1,
        agent_id=7,
        agent_name="Analyst",
        action_type="SEARCH_POSTS",
        action_args={"query": "Labor slowdown"},
    )
    logger.log_intervention(
        round_num=1,
        intervention_name="Moderator pin",
        details={"content": "Pinned the payroll thread for visibility."},
    )
    logger.log_round_end(1, 3)
    logger.log_simulation_end(1, 3)

    action_lines = (
        run_dir / "twitter" / "actions.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    transition_lines = (
        run_dir / "runtime_graph_updates.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    runtime_state = json.loads(
        (run_dir / "runtime_graph_state.json").read_text(encoding="utf-8")
    )

    assert len(action_lines) == 7
    transitions = [json.loads(line) for line in transition_lines]
    transition_types = {item["transition_type"] for item in transitions}
    assert {
        "round_state",
        "event",
        "claim",
        "exposure",
        "belief_update",
        "topic_shift",
        "intervention",
    } <= transition_types
    assert all(item["simulation_id"] == "sim-logger" for item in transitions)
    assert all(item["runtime_graph_id"] == "runtime-graph-logger" for item in transitions)
    assert all(item["base_graph_id"] == "graph-base-logger" for item in transitions)
    assert all(item["platform"] == "twitter" for item in transitions)
    assert all("timestamp" in item and item["timestamp"] for item in transitions)

    assert runtime_state["transition_count"] == len(transitions)
    assert runtime_state["transition_counts"]["claim"] == 1
    assert runtime_state["transition_counts"]["event"] == 1
    assert runtime_state["transition_counts"]["intervention"] == 1
    assert runtime_state["transition_counts"]["belief_update"] == 1
    assert runtime_state["transition_counts"]["topic_shift"] == 1
    assert runtime_state["current_round"] == 1
    assert runtime_state["platform_status"]["twitter"] == "completed"
    assert "Labor slowdown" in runtime_state["active_topics"]
    assert runtime_state["recent_transitions"][-1]["transition_type"] == "round_state"
