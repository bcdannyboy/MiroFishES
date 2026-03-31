import importlib
import json
from pathlib import Path


def _load_reader_module():
    return importlib.import_module("app.services.zep_entity_reader")


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
    monkeypatch.setattr(config_module.Config, "ZEP_API_KEY", "test-key", raising=False)
    project_dir = tmp_path / "projects" / "proj-1"
    _write_json(
        project_dir / "graph_entity_index.json",
        _entity_index_payload(project_id="proj-1", graph_id="graph-1"),
    )

    reader = reader_module.ZepEntityReader()
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
    monkeypatch.setattr(config_module.Config, "ZEP_API_KEY", "test-key", raising=False)
    project_dir = tmp_path / "projects" / "proj-1"
    _write_json(
        project_dir / "graph_entity_index.json",
        _entity_index_payload(project_id="proj-1", graph_id="graph-stale"),
    )

    reader = reader_module.ZepEntityReader()
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
