import importlib
import sys


def _load_settings_module():
    for module_name in (
        "app.services.graph_backend.settings",
        "app.services.graph_backend",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.settings")


def test_graph_backend_settings_resolve_graphiti_scaffold(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti_neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:8687")
    monkeypatch.setenv("NEO4J_USER", "graph-user")
    monkeypatch.setenv("NEO4J_PASSWORD", "graph-pass")
    monkeypatch.setenv("GRAPHITI_EXTRACTION_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("GRAPHITI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("GRAPH_BACKEND_BATCH_SIZE", "7")
    monkeypatch.setenv("GRAPH_BACKEND_SEARCH_LIMIT", "19")
    monkeypatch.setenv("GRAPH_BACKEND_SCAN_LIMIT", "211")
    monkeypatch.setenv("GRAPH_BACKEND_RUNTIME_BATCH_SIZE", "13")

    settings_module = _load_settings_module()
    settings = settings_module.GraphBackendSettings.from_env()

    assert settings.backend == "graphiti_neo4j"
    assert settings.neo4j_uri == "bolt://127.0.0.1:8687"
    assert settings.neo4j_user == "graph-user"
    assert settings.neo4j_password == "graph-pass"
    assert settings.graphiti_extraction_model == "gpt-4.1-mini"
    assert settings.graphiti_embedding_model == "text-embedding-3-small"
    assert settings.build_batch_size == 7
    assert settings.search_limit == 19
    assert settings.scan_limit == 211
    assert settings.runtime_batch_size == 13
    assert settings.validate() == []


def test_graph_backend_settings_report_missing_neo4j_secret(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti_neo4j")
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    settings_module = _load_settings_module()
    settings = settings_module.GraphBackendSettings.from_env()

    assert settings.validate() == ["NEO4J_PASSWORD is not configured"]


def test_config_validate_no_longer_requires_zep_api_key(monkeypatch):
    for module_name in ("app.config", "app.services.graph_backend.settings"):
        sys.modules.pop(module_name, None)

    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    config_module = importlib.import_module("app.config")

    assert config_module.Config.validate() == []
