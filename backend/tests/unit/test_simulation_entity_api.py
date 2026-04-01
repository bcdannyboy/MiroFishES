import importlib
import sys

from flask import Flask


def _load_simulation_api_module():
    sys.modules.pop("app.api.simulation", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.simulation")


def _build_test_client(simulation_module):
    app = Flask(__name__)
    app.register_blueprint(simulation_module.simulation_bp, url_prefix="/api/simulation")
    return app.test_client()


def test_entities_endpoint_uses_graph_entity_reader_without_zep_credentials(
    monkeypatch,
):
    simulation_module = _load_simulation_api_module()
    config_module = importlib.import_module("app.config")
    captures = {}

    class _FakeFilteredEntities:
        def to_dict(self):
            return {
                "entities": [{"uuid": "actor-1", "name": "Analyst"}],
                "entity_types": ["Person"],
                "total_count": 1,
                "filtered_count": 1,
            }

    class _FakeReader:
        def filter_defined_entities(
            self,
            *,
            graph_id,
            defined_entity_types=None,
            enrich_with_edges=True,
            project_id=None,
            graph_ids=None,
        ):
            captures["filter"] = {
                "graph_id": graph_id,
                "defined_entity_types": defined_entity_types,
                "enrich_with_edges": enrich_with_edges,
                "project_id": project_id,
                "graph_ids": graph_ids,
            }
            return _FakeFilteredEntities()

    monkeypatch.setattr(
        simulation_module,
        "GraphEntityReader",
        _FakeReader,
        raising=False,
    )

    client = _build_test_client(simulation_module)
    response = client.get(
        "/api/simulation/entities/graph-base"
        "?graph_ids=graph-base,runtime-graph-1&entity_types=Person&enrich=false"
    )

    assert response.status_code == 200
    assert captures["filter"] == {
        "graph_id": "graph-base",
        "defined_entity_types": ["Person"],
        "enrich_with_edges": False,
        "project_id": None,
        "graph_ids": ["graph-base", "runtime-graph-1"],
    }
    payload = response.get_json()["data"]
    assert payload["filtered_count"] == 1
    assert payload["entity_types"] == ["Person"]


def test_entity_detail_endpoint_uses_graph_entity_reader_without_zep_credentials(
    monkeypatch,
):
    simulation_module = _load_simulation_api_module()
    config_module = importlib.import_module("app.config")
    captures = {}

    class _FakeEntity:
        def to_dict(self):
            return {
                "uuid": "actor-1",
                "name": "Analyst",
                "labels": ["Entity", "Person"],
                "summary": "Tracks runtime shifts.",
                "attributes": {},
                "related_edges": [],
                "related_nodes": [],
            }

    class _FakeReader:
        def get_entity_with_context(
            self,
            graph_id,
            entity_uuid,
            *,
            graph_ids=None,
            project_id=None,
        ):
            captures["detail"] = {
                "graph_id": graph_id,
                "entity_uuid": entity_uuid,
                "graph_ids": graph_ids,
                "project_id": project_id,
            }
            return _FakeEntity()

    monkeypatch.setattr(
        simulation_module,
        "GraphEntityReader",
        _FakeReader,
        raising=False,
    )

    client = _build_test_client(simulation_module)
    response = client.get(
        "/api/simulation/entities/graph-base/actor-1"
        "?graph_ids=graph-base,runtime-graph-1"
    )

    assert response.status_code == 200
    assert captures["detail"] == {
        "graph_id": "graph-base",
        "entity_uuid": "actor-1",
        "graph_ids": ["graph-base", "runtime-graph-1"],
        "project_id": None,
    }
    payload = response.get_json()["data"]
    assert payload["name"] == "Analyst"
