import importlib
import sys

from flask import Flask


def _load_report_api_module():
    sys.modules.pop("app.api.report", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.report")


def _build_test_client(report_module):
    app = Flask(__name__)
    app.register_blueprint(report_module.report_bp, url_prefix="/api/report")
    return app.test_client()


def test_report_search_tool_uses_graph_query_tools_for_multigraph_scope(monkeypatch):
    report_module = _load_report_api_module()
    captures = {}

    class _FakeResult:
        def to_dict(self):
            return {
                "facts": ["Runtime graph fact"],
                "edges": [],
                "nodes": [],
                "query": "runtime graph fact",
                "total_count": 1,
            }

    class _FakeGraphTools:
        def search_graph(self, *, graph_id, graph_ids=None, query, limit=10):
            captures["search"] = {
                "graph_id": graph_id,
                "graph_ids": graph_ids,
                "query": query,
                "limit": limit,
            }
            return _FakeResult()

    monkeypatch.setattr(
        report_module,
        "GraphQueryToolsService",
        lambda: _FakeGraphTools(),
        raising=False,
    )

    client = _build_test_client(report_module)
    response = client.post(
        "/api/report/tools/search",
        json={
            "graph_id": "graph-base",
            "graph_ids": ["graph-base", "runtime-graph-1"],
            "query": "runtime graph fact",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert captures["search"] == {
        "graph_id": "graph-base",
        "graph_ids": ["graph-base", "runtime-graph-1"],
        "query": "runtime graph fact",
        "limit": 5,
    }
    payload = response.get_json()["data"]
    assert payload["facts"] == ["Runtime graph fact"]
    assert payload["query"] == "runtime graph fact"
