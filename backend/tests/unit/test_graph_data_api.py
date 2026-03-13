import importlib
import sys

from flask import Flask


def _load_graph_api_module():
    sys.modules.pop("app.api.graph", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.graph")


def _build_test_client(graph_module):
    app = Flask(__name__)
    app.register_blueprint(graph_module.graph_bp, url_prefix="/api/graph")
    return app.test_client()


def test_graph_data_endpoint_forwards_preview_mode_and_caps(monkeypatch):
    graph_module = _load_graph_api_module()
    captures = {}

    class _FakeBuilder:
        def __init__(self, *args, **kwargs):
            captures["builder_init"] = kwargs

        def get_graph_data(
            self,
            graph_id,
            *,
            mode="full",
            max_nodes=None,
            max_edges=None,
        ):
            captures["graph_id"] = graph_id
            captures["mode"] = mode
            captures["max_nodes"] = max_nodes
            captures["max_edges"] = max_edges
            return {
                "graph_id": graph_id,
                "mode": mode,
                "truncated": True,
                "returned_nodes": 50,
                "returned_edges": 80,
                "total_nodes": 50,
                "total_edges": 80,
                "nodes": [],
                "edges": [],
            }

    monkeypatch.setattr(
        graph_module,
        "GraphBuilderService",
        _FakeBuilder,
        raising=False,
    )

    client = _build_test_client(graph_module)
    response = client.get(
        "/api/graph/data/graph-123?mode=preview&max_nodes=50&max_edges=80"
    )

    assert response.status_code == 200
    assert captures["graph_id"] == "graph-123"
    assert captures["mode"] == "preview"
    assert captures["max_nodes"] == 50
    assert captures["max_edges"] == 80
    payload = response.get_json()["data"]
    assert payload["mode"] == "preview"
    assert payload["truncated"] is True
    assert payload["returned_nodes"] == 50
    assert payload["returned_edges"] == 80

