import importlib
import sys


def _load_graphiti_factory_module():
    for module_name in (
        "app.services.graph_backend.graphiti_factory",
        "app.services.graph_backend.settings",
        "app.services.graph_backend",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.graphiti_factory")


def _load_neo4j_factory_module():
    for module_name in (
        "app.services.graph_backend.neo4j_factory",
        "app.services.graph_backend.settings",
        "app.services.graph_backend",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.neo4j_factory")


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
    assert runtime.graphiti_factory.client_builder == "async_graphiti"
    assert runtime.graphiti_factory.client_kwargs == {
        "uri": "bolt://127.0.0.1:7687",
        "user": "neo4j",
        "password": "local-pass",
    }
    assert runtime.graphiti_factory.model_config == {
        "extraction_model": runtime.settings.graphiti_extraction_model,
        "embedding_model": runtime.settings.graphiti_embedding_model,
    }
    assert runtime.neo4j_factory.driver_builder == "graph_database_driver"
    assert runtime.neo4j_factory.connection_kwargs == {
        "uri": "bolt://127.0.0.1:7687",
        "auth": ("neo4j", "local-pass"),
    }


def test_neo4j_factory_build_driver_uses_graph_database_driver(monkeypatch):
    neo4j_module = _load_neo4j_factory_module()
    captures = {}

    class _FakeDriver:
        def execute_query(self, query):
            captures["healthcheck_query"] = query
            return [{"ok": 1}], None, None

    class _FakeGraphDatabase:
        @staticmethod
        def driver(uri, *, auth):
            captures["uri"] = uri
            captures["auth"] = auth
            return _FakeDriver()

    monkeypatch.setattr(neo4j_module, "GraphDatabase", _FakeGraphDatabase, raising=False)

    factory = neo4j_module.build_neo4j_factory(
        neo4j_module.GraphBackendSettings(
            backend="graphiti_neo4j",
            neo4j_uri="bolt://127.0.0.1:8765",
            neo4j_user="neo4j",
            neo4j_password="graph-pass",
            graphiti_extraction_model="gpt-4.1-mini",
            graphiti_embedding_model="text-embedding-3-small",
            build_batch_size=3,
            search_limit=12,
            scan_limit=250,
            runtime_batch_size=25,
        )
    )
    driver = factory.build_driver()
    ok = factory.run_healthcheck(driver)

    assert captures["uri"] == "bolt://127.0.0.1:8765"
    assert captures["auth"] == ("neo4j", "graph-pass")
    assert captures["healthcheck_query"] == "RETURN 1 AS ok"
    assert ok is True
