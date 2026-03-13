import importlib


def test_search_graph_merges_multiple_graphs_with_deterministic_dedupe(monkeypatch):
    module = importlib.import_module("app.services.zep_tools")
    service = module.ZepToolsService.__new__(module.ZepToolsService)

    results_by_graph = {
        "graph-base": module.SearchResult(
            facts=["shared fact", "base-only fact"],
            edges=[
                {
                    "uuid": "edge-base",
                    "name": "MENTIONS",
                    "fact": "shared fact",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                }
            ],
            nodes=[
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Base analyst summary",
                }
            ],
            query="plaza",
            total_count=2,
        ),
        "graph-runtime": module.SearchResult(
            facts=["shared fact", "runtime-only fact"],
            edges=[
                {
                    "uuid": "edge-runtime",
                    "name": "OBSERVES",
                    "fact": "runtime-only fact",
                    "source_node_uuid": "node-3",
                    "target_node_uuid": "node-4",
                }
            ],
            nodes=[
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Base analyst summary",
                },
                {
                    "uuid": "node-3",
                    "name": "Plaza",
                    "labels": ["Entity", "Place"],
                    "summary": "Runtime plaza summary",
                },
            ],
            query="plaza",
            total_count=2,
        ),
    }

    monkeypatch.setattr(
        service,
        "_search_single_graph",
        lambda graph_id, query, limit, scope: results_by_graph[graph_id],
        raising=False,
    )

    result = service.search_graph(
        graph_id="graph-base",
        graph_ids=["graph-base", "graph-runtime"],
        query="plaza",
        limit=10,
        scope="edges",
    )

    assert result.query == "plaza"
    assert result.facts == ["shared fact", "base-only fact", "runtime-only fact"]
    assert [edge["uuid"] for edge in result.edges] == ["edge-base", "edge-runtime"]
    assert [node["uuid"] for node in result.nodes] == ["node-1", "node-3"]
    assert result.total_count == 3

