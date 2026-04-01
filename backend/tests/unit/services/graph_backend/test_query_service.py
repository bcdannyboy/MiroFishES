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


def _seed_base_and_runtime_graphs(simulations_dir: Path, projects_dir: Path) -> None:
    project_dir = projects_dir / "proj-query"
    _write_json(
        project_dir / "project.json",
        {
            "project_id": "proj-query",
            "name": "Query Project",
            "status": "graph_completed",
            "created_at": "2026-03-31T08:00:00",
            "updated_at": "2026-03-31T08:00:00",
            "files": [],
            "graph_id": "graph-base",
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "project_id": "proj-query",
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
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "MENTIONS",
                            "fact": "Analyst says hiring is slowing.",
                            "source_node_uuid": "actor-1",
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
                }
            ],
        },
    )
    run_dir = (
        simulations_dir
        / "sim-query"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": "sim-query",
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
            "simulation_id": "sim-query",
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": "proj-query",
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
            "simulation_id": "sim-query",
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": "proj-query",
            "base_graph_id": "graph-base",
            "runtime_graph_id": "runtime-graph-1",
            "transition_count": 1,
        },
    )
    _write_jsonl(
        run_dir / "runtime_graph_updates.jsonl",
        [
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-claim",
                "transition_type": "claim",
                "simulation_id": "sim-query",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-query",
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
                    "run_scope": "sim-query::0001::0001",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "graph_object_uuids": ["topic-1"],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": "Analyst create_post :: Hiring is weakening.",
            }
        ],
    )


def test_query_service_reads_nodes_edges_and_searches_merged_graphs(monkeypatch, tmp_path):
    simulations_dir, projects_dir = _configure_roots(monkeypatch, tmp_path)
    _seed_base_and_runtime_graphs(simulations_dir, projects_dir)

    module = importlib.import_module("app.services.graph_backend.query_service")
    service = module.GraphQueryService()

    search_result = service.search_graph(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
        query="hiring",
        limit=10,
        scope="edges",
    )
    entity_summary = service.get_entity_summary(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
        entity_name="Analyst",
    )
    node = service.get_node_detail(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
        node_uuid="actor-1",
    )

    assert search_result["facts"] == [
        "Analyst says hiring is slowing.",
        "Analyst create_post :: Hiring is weakening.",
    ]
    assert search_result["edges"][0]["uuid"].startswith("graph-edge-")
    assert search_result["edges"][1]["uuid"] == "rts-fixed-claim"
    assert entity_summary["entity_info"]["uuid"] == "actor-1"
    assert entity_summary["related_edges"][0]["uuid"].startswith("graph-edge-")
    assert entity_summary["related_edges"][1]["uuid"] == "rts-fixed-claim"
    assert node["labels"] == ["Entity", "Person"]
