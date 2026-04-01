import importlib
import json
from pathlib import Path


def _load_reader_module():
    return importlib.import_module("app.services.graph_entity_reader")


def test_graph_entity_reader_module_exports_only_graph_native_reader():
    reader_module = _load_reader_module()

    assert reader_module.GraphEntityReader.__name__ == "GraphEntityReader"
    assert getattr(reader_module, "ZepEntityReader", None) is None


def _configure_project_dir(monkeypatch, project_root: Path):
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


def _entity_index_payload(*, project_id: str, graph_id: str) -> dict:
    return {
        "artifact_type": "graph_entity_index",
        "schema_version": "forecast.grounding.v1",
        "generator_version": "forecast.grounding.generator.v1",
        "project_id": project_id,
        "graph_id": graph_id,
        "generated_at": "2026-03-29T09:06:00",
        "total_count": 1,
        "filtered_count": 1,
        "entity_types": ["Person"],
        "entities": [
            {
                "uuid": "entity-1",
                "name": "Analyst",
                "labels": ["Entity", "Person"],
                "summary": "A tracked participant",
                "attributes": {"role": "analyst"},
                "related_edges": [
                    {
                        "direction": "outgoing",
                        "edge_name": "MENTIONS",
                        "fact": "Analyst mentions policy",
                        "target_node_uuid": "node-2",
                    }
                ],
                "related_nodes": [
                    {
                        "uuid": "node-2",
                        "name": "Policy Desk",
                        "labels": ["Entity", "Organization"],
                        "summary": "A connected organization",
                    }
                ],
            }
        ],
    }


def test_filter_defined_entities_uses_project_entity_index_before_remote_reads(
    monkeypatch, tmp_path
):
    reader_module = _load_reader_module()
    _configure_project_dir(monkeypatch, tmp_path / "projects")

    config_module = importlib.import_module("app.config")
    project_dir = tmp_path / "projects" / "proj-1"
    _write_json(
        project_dir / "graph_entity_index.json",
        _entity_index_payload(project_id="proj-1", graph_id="graph-1"),
    )

    reader = reader_module.GraphEntityReader()
    monkeypatch.setattr(
        reader,
        "get_all_nodes",
        lambda graph_id: (_ for _ in ()).throw(
            AssertionError("local entity index should avoid remote node reads")
        ),
    )
    monkeypatch.setattr(
        reader,
        "get_all_edges",
        lambda graph_id: (_ for _ in ()).throw(
            AssertionError("local entity index should avoid remote edge reads")
        ),
    )

    filtered = reader.filter_defined_entities(
        graph_id="graph-1",
        defined_entity_types=["Person"],
        enrich_with_edges=True,
        project_id="proj-1",
    )

    assert filtered.filtered_count == 1
    assert filtered.total_count == 1
    assert filtered.entity_types == {"Person"}
    assert filtered.entities[0].name == "Analyst"
    assert filtered.entities[0].related_edges[0]["edge_name"] == "MENTIONS"


def test_filter_defined_entities_falls_back_to_remote_when_entity_index_graph_mismatches(
    monkeypatch, tmp_path
):
    reader_module = _load_reader_module()
    _configure_project_dir(monkeypatch, tmp_path / "projects")

    config_module = importlib.import_module("app.config")
    project_dir = tmp_path / "projects" / "proj-1"
    _write_json(
        project_dir / "graph_entity_index.json",
        _entity_index_payload(project_id="proj-1", graph_id="graph-stale"),
    )

    reader = reader_module.GraphEntityReader()
    node_calls = []
    edge_calls = []
    monkeypatch.setattr(
        reader,
        "get_all_nodes",
        lambda graph_id: node_calls.append(graph_id) or [
            {
                "uuid": "entity-1",
                "name": "Analyst",
                "labels": ["Entity", "Person"],
                "summary": "A tracked participant",
                "attributes": {"role": "analyst"},
            }
        ],
    )
    monkeypatch.setattr(
        reader,
        "get_all_edges",
        lambda graph_id: edge_calls.append(graph_id) or [],
    )

    filtered = reader.filter_defined_entities(
        graph_id="graph-1",
        defined_entity_types=["Person"],
        enrich_with_edges=True,
        project_id="proj-1",
    )

    assert filtered.filtered_count == 1
    assert node_calls == ["graph-1"]
    assert edge_calls == ["graph-1"]


def test_build_filtered_entities_excludes_analytical_objects_by_default():
    reader_module = _load_reader_module()
    nodes = [
        {
            "uuid": "node-1",
            "name": "Analyst",
            "labels": ["Entity", "Person"],
            "summary": "A tracked participant",
            "attributes": {"role": "analyst"},
        },
        {
            "uuid": "node-2",
            "name": "Rate cut likely by June",
            "labels": ["Entity", "Claim"],
            "summary": "An analytical claim node",
            "attributes": {"confidence": "medium"},
        },
    ]

    default_filtered = reader_module.build_filtered_entities_from_payloads(
        nodes,
        [],
        enrich_with_edges=False,
    )
    claim_filtered = reader_module.build_filtered_entities_from_payloads(
        nodes,
        [],
        defined_entity_types=["Claim"],
        enrich_with_edges=False,
    )

    assert default_filtered.filtered_count == 1
    assert default_filtered.entity_types == {"Person"}
    assert default_filtered.entities[0].name == "Analyst"
    assert claim_filtered.filtered_count == 1
    assert claim_filtered.entity_types == {"Claim"}
    assert claim_filtered.entities[0].name == "Rate cut likely by June"


def test_get_entity_with_context_merges_runtime_edges_without_legacy_credentials(
    monkeypatch, tmp_path
):
    reader_module = _load_reader_module()
    _configure_project_dir(monkeypatch, tmp_path / "projects")

    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(tmp_path / "simulations"),
        raising=False,
    )

    project_dir = tmp_path / "projects" / "proj-graph"
    _write_json(
        project_dir / "project.json",
        {
            "project_id": "proj-graph",
            "name": "Graph Reader Project",
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
        tmp_path
        / "simulations"
        / "sim-reader"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": "sim-reader",
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
            "simulation_id": "sim-reader",
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
                    "linked_object_uuids": ["topic-1"],
                }
            ],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Labor slowdown",
                    "object_type": "Topic",
                    "summary": "Employment is cooling.",
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
            "simulation_id": "sim-reader",
            "ensemble_id": "0001",
            "run_id": "0001",
            "project_id": "proj-graph",
            "base_graph_id": "graph-base",
            "runtime_graph_id": "runtime-graph-1",
            "transition_count": 1,
        },
    )
    (run_dir / "runtime_graph_updates.jsonl").write_text(
        json.dumps(
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-claim",
                "transition_type": "claim",
                "simulation_id": "sim-reader",
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
                    "run_scope": "sim-reader::0001::0001",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "graph_object_uuids": ["topic-1"],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": "Analyst create_post :: Hiring is weakening.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    reader = reader_module.GraphEntityReader()
    entity = reader.get_entity_with_context(
        graph_id="graph-base",
        entity_uuid="actor-1",
        graph_ids=["graph-base", "runtime-graph-1"],
    )

    assert entity is not None
    assert [edge["edge_name"] for edge in entity.related_edges] == [
        "MENTIONS",
        "CLAIM",
    ]
    assert {node["uuid"] for node in entity.related_nodes} == {"topic-1"}
