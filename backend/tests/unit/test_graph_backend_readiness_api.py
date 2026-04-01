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


def test_graph_backend_readiness_endpoint_reports_backend_state(monkeypatch):
    graph_module = _load_graph_api_module()

    monkeypatch.setattr(
        graph_module,
        "describe_graph_backend_readiness",
        lambda: {
            "backend": "graphiti_neo4j",
            "configured": True,
            "ready": False,
            "missing_configuration": [],
            "dependency_status": {
                "graphiti-core": {"available": False, "version": None},
                "neo4j": {"available": True, "version": "5.28.2"},
            },
            "neo4j_probe": {
                "uri": "bolt://127.0.0.1:7687",
                "reachable": True,
                "detail": "connected",
            },
        },
        raising=False,
    )

    client = _build_test_client(graph_module)
    response = client.get("/api/graph/backend/readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["backend"] == "graphiti_neo4j"
    assert payload["data"]["configured"] is True
    assert payload["data"]["ready"] is False
    assert payload["data"]["neo4j_probe"]["reachable"] is True
