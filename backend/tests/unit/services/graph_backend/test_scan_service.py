import importlib
import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _configure_roots(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
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
    return simulations_dir, projects_dir


def _seed_project_graph(projects_dir: Path) -> None:
    project_dir = projects_dir / "proj-graph"
    _write_json(
        project_dir / "project.json",
        {
            "project_id": "proj-graph",
            "name": "Graph Read Project",
            "status": "graph_completed",
            "created_at": "2026-03-31T08:00:00",
            "updated_at": "2026-03-31T08:00:00",
            "files": [],
            "graph_id": "graph-base",
            "ontology": {
                "entity_types": [{"name": "Person", "attributes": []}],
                "edge_types": [{"name": "MENTIONS", "attributes": []}],
            },
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "project_id": "proj-graph",
            "graph_id": "graph-base",
            "total_count": 1,
            "filtered_count": 1,
            "entity_types": ["Person"],
            "entities": [
                {
                    "uuid": "actor-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Tracks labor-market conditions.",
                    "attributes": {"role": "analyst"},
                    "related_edges": [
                        {
                            "direction": "outgoing",
                            "edge_name": "MENTIONS",
                            "fact": "Analyst says hiring is slowing.",
                            "target_node_uuid": "topic-1",
                            "provenance": {
                                "source_unit_ids": ["unit-1"],
                                "citations": [{"citation_id": "cit-1"}],
                            },
                        }
                    ],
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
            "analytical_object_count": 1,
            "analytical_types": ["Topic"],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Labor slowdown",
                    "object_type": "Topic",
                    "summary": "Employment is cooling.",
                    "attributes": {"kind": "macro"},
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "MENTIONS",
                            "fact": "Analyst says hiring is slowing.",
                            "source_node_uuid": "actor-1",
                            "provenance": {
                                "source_unit_ids": ["unit-1"],
                                "citations": [{"citation_id": "cit-1"}],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "actor-1",
                            "name": "Analyst",
                            "labels": ["Entity", "Person"],
                            "summary": "Tracks labor-market conditions.",
                        }
                    ],
                    "provenance": {
                        "source_unit_ids": ["unit-1"],
                        "citations": [{"citation_id": "cit-1"}],
                    },
                }
            ],
        },
    )


def _seed_runtime_graph(simulations_dir: Path) -> None:
    run_dir = (
        simulations_dir
        / "sim-graph"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": "sim-graph",
            "ensemble_id": "0001",
            "run_id": "0001",
            "base_graph_id": "graph-base",
            "runtime_graph_id": "runtime-graph-1",
        },
    )
    _write_json(
        run_dir / "runtime_graph_base_snapshot.json",
        {
            "artifact_type": "runtime_graph_base_snapshot",
            "simulation_id": "sim-graph",
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": "proj-graph",
            "base_graph_id": "graph-base",
            "runtime_graph_id": "runtime-graph-1",
            "actors": [
                {
                    "entity_uuid": "actor-1",
                    "entity_name": "Analyst",
                    "entity_type": "Person",
                    "summary": "Tracks labor-market conditions.",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "linked_object_uuids": ["topic-1"],
                    "stance_hint": "cautious",
                    "sentiment_bias_hint": "neutral",
                }
            ],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Labor slowdown",
                    "object_type": "Topic",
                    "summary": "Employment is cooling.",
                    "provenance": {
                        "source_unit_ids": ["unit-1"],
                        "citations": [{"citation_id": "cit-1"}],
                    },
                    "related_nodes": [
                        {
                            "uuid": "actor-1",
                            "name": "Analyst",
                            "labels": ["Entity", "Person"],
                        }
                    ],
                }
            ],
            "registries": {
                "topics": [
                    {
                        "uuid": "topic-1",
                        "name": "Labor slowdown",
                        "citation_ids": ["cit-1"],
                        "source_unit_ids": ["unit-1"],
                        "linked_actor_uuids": ["actor-1"],
                    }
                ]
            },
        },
    )
    _write_json(
        run_dir / "runtime_graph_state.json",
        {
            "artifact_type": "runtime_graph_state",
            "simulation_id": "sim-graph",
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": "proj-graph",
            "base_graph_id": "graph-base",
            "runtime_graph_id": "runtime-graph-1",
            "transition_count": 2,
        },
    )
    _write_jsonl(
        run_dir / "runtime_graph_updates.jsonl",
        [
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-claim",
                "transition_type": "claim",
                "simulation_id": "sim-graph",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-graph",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
                "platform": "twitter",
                "round_num": 1,
                "timestamp": "2026-03-31T09:00:00",
                "recorded_at": "2026-03-31T09:00:05",
                "agent": {
                    "agent_name": "Analyst",
                    "entity_uuid": "actor-1",
                    "entity_type": "Person",
                    "stance_hint": "cautious",
                    "sentiment_bias_hint": "neutral",
                },
                "payload": {
                    "action_type": "CREATE_POST",
                    "topics": ["Labor slowdown"],
                    "action_args": {
                        "content": "Hiring is weakening.",
                        "topic": "Labor slowdown",
                    },
                },
                "provenance": {
                    "run_scope": "sim-graph::0001::0001",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "graph_object_uuids": ["topic-1"],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": "Analyst create_post :: Hiring is weakening.",
            },
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-event",
                "transition_type": "event",
                "simulation_id": "sim-graph",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-graph",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
                "platform": "twitter",
                "round_num": 1,
                "timestamp": "2026-03-31T09:05:00",
                "recorded_at": "2026-03-31T09:05:02",
                "agent": {
                    "agent_name": "Analyst",
                    "entity_uuid": "actor-1",
                    "entity_type": "Person",
                },
                "payload": {
                    "event_name": "Breaking payroll print",
                    "details": {
                        "content": "Payroll missed expectations.",
                    },
                },
                "provenance": {
                    "run_scope": "sim-graph::0001::0001",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "graph_object_uuids": [],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": "twitter event: Breaking payroll print",
            },
        ],
    )


def test_scan_service_full_scan_is_deterministic_and_normalizes_runtime_history(
    monkeypatch, tmp_path
):
    simulations_dir, projects_dir = _configure_roots(monkeypatch, tmp_path)
    _seed_project_graph(projects_dir)
    _seed_runtime_graph(simulations_dir)

    module = importlib.import_module("app.services.graph_backend.scan_service")
    service = module.GraphScanService()

    nodes_first = service.scan_nodes(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
    )
    nodes_second = service.scan_nodes(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
    )
    edges = service.scan_edges(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
    )

    assert [node["uuid"] for node in nodes_first] == [
        "actor-1",
        "topic-1",
        "runtime-transition:rts-fixed-event",
    ]
    assert nodes_first == nodes_second
    assert edges[0]["uuid"].startswith("graph-edge-")
    assert [edge["uuid"] for edge in edges[1:]] == [
        "rts-fixed-claim",
        "rts-fixed-event",
    ]
    assert edges[1]["created_at"] == "2026-03-31T09:00:00"
    assert edges[1]["attributes"]["history_kind"] == "runtime_transition"
    assert edges[2]["target_node_uuid"] == "runtime-transition:rts-fixed-event"
