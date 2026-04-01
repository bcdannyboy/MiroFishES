import importlib
import sys


def _load_live_probe_module():
    for module_name in (
        "app.services.graph_backend.live_probe",
        "app.services.graph_backend",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.live_probe")


def test_live_probe_module_exposes_graphiti_build_search_update_probe():
    probe_module = _load_live_probe_module()

    assert hasattr(probe_module, "run_live_graphiti_probe")


def test_live_probe_module_applies_managed_local_defaults(monkeypatch):
    probe_module = _load_live_probe_module()

    for key in (
        "GRAPH_BACKEND",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "GRAPHITI_LIVE_NEO4J_BOLT_PORT",
        "GRAPHITI_LIVE_NEO4J_USER",
        "GRAPHITI_LIVE_NEO4J_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    defaults = probe_module.apply_managed_local_graph_defaults()

    assert defaults == {
        "GRAPH_BACKEND": "graphiti_neo4j",
        "NEO4J_URI": "bolt://127.0.0.1:17687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "mirofish-graphiti-live",
        "OPENAI_API_KEY": "smoke-local-key",
        "LLM_API_KEY": "smoke-local-key",
    }
