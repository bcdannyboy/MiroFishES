import importlib


def test_config_validate_accepts_openai_api_key_alias(monkeypatch):
    config_module = importlib.import_module("app.config")

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")

    assert config_module.Config.validate() == []


def test_task_model_router_resolves_task_scoped_routes(monkeypatch, tmp_path):
    config_module = importlib.import_module("app.config")
    router_module = importlib.import_module("app.utils.model_routing")

    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_REASONING_MODEL", "gpt-5-mini")
    monkeypatch.setenv("OPENAI_REPORT_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LOCAL_EMBEDDING_API_KEY", "local-embed-key")
    monkeypatch.setenv("LOCAL_EMBEDDING_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "mxbai-embed-large")
    monkeypatch.setenv("LOCAL_EVIDENCE_INDEX_PATH", str(tmp_path / "evidence-index.sqlite3"))

    routes = config_module.Config.get_task_model_routes()
    router = router_module.TaskModelRouter()

    assert routes["default"].model == "gpt-4o-mini"
    assert routes["reasoning"].model == "gpt-5-mini"
    assert routes["report"].model == "gpt-4.1-mini"
    assert routes["embedding"].model == "mxbai-embed-large"
    assert routes["embedding"].base_url == "http://127.0.0.1:11434/v1"
    assert routes["embedding"].api_key == "local-embed-key"
    assert config_module.Config.get_local_evidence_index_path() == str(
        tmp_path / "evidence-index.sqlite3"
    )

    default_route = router.resolve("default")
    reasoning_route = router.resolve("reasoning")
    embedding_route = router.resolve("embedding")

    assert default_route.model == "gpt-4o-mini"
    assert reasoning_route.model == "gpt-5-mini"
    assert embedding_route.model == "mxbai-embed-large"
    assert embedding_route.base_url == "http://127.0.0.1:11434/v1"
