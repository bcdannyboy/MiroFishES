import importlib
import sys


def _load_graph_backend_module():
    for module_name in (
        "app.services.graph_backend.graphiti_factory",
        "app.services.graph_backend.neo4j_factory",
        "app.services.graph_backend.settings",
        "app.services.graph_backend",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend")


def test_build_graph_backend_runtime_exposes_prompt1_scaffold(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti_neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "local-pass")

    backend_module = _load_graph_backend_module()
    runtime = backend_module.build_graph_backend_runtime()

    assert runtime.backend == "graphiti_neo4j"
    assert runtime.settings.neo4j_uri == "bolt://127.0.0.1:7687"
    assert runtime.graphiti_factory.distribution_name == "graphiti-core"
    assert runtime.neo4j_factory.distribution_name == "neo4j"
    assert runtime.graphiti_factory.client_builder == "deferred"
    assert runtime.neo4j_factory.driver_builder == "deferred"
