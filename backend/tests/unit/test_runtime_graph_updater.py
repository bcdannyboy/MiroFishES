import importlib
import sys
import time


def _load_runtime_graph_updater_module():
    for module_name in (
        "app.services.runtime_graph_updater",
        "app.services.graph_backend",
        "app.services.graph_backend.settings",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.runtime_graph_updater")


class _FakeGraphBackend:
    def __init__(self):
        self.calls = []

    def append_runtime_events(
        self,
        namespace_id,
        events,
        batch_size=None,
        progress_callback=None,
    ):
        del progress_callback
        self.calls.append((namespace_id, list(events), batch_size))
        return [f"episode-{len(self.calls)}"]


def test_runtime_graph_updater_batches_serialized_runtime_events():
    module = _load_runtime_graph_updater_module()
    backend = _FakeGraphBackend()
    settings = module.GraphBackendSettings(
        backend="graphiti_neo4j",
        neo4j_uri="bolt://127.0.0.1:7687",
        neo4j_user="neo4j",
        neo4j_password="local-pass",
        graphiti_extraction_model="gpt-4.1-mini",
        graphiti_embedding_model="text-embedding-3-small",
        build_batch_size=3,
        search_limit=12,
        scan_limit=250,
        runtime_batch_size=2,
    )
    updater = module.RuntimeGraphUpdater(
        run_key="sim-runtime::0001::0001",
        base_graph_id="mirofish-base-proj-runtime",
        runtime_graph_id="mirofish-runtime-sim-runtime-0001-0001",
        run_dir="/tmp/runtime-probe",
        graph_backend=backend,
        settings=settings,
    )
    updater.SEND_INTERVAL = 0
    updater.start()

    updater.add_activity_from_dict(
        {
            "agent_id": 7,
            "agent_name": "Analyst",
            "action_type": "CREATE_POST",
            "action_args": {"content": "Hiring is weakening.", "topic": "Labor slowdown"},
            "round": 1,
            "timestamp": "2026-03-31T09:00:00",
        },
        "twitter",
    )
    updater.add_activity_from_dict(
        {
            "agent_id": 7,
            "agent_name": "Analyst",
            "action_type": "LIKE_POST",
            "action_args": {
                "post_content": "Payroll growth slowed again.",
                "post_author_name": "Macro Desk",
                "topic": "Labor slowdown",
            },
            "round": 1,
            "timestamp": "2026-03-31T09:05:00",
        },
        "twitter",
    )

    deadline = time.time() + 1.0
    while not backend.calls and time.time() < deadline:
        time.sleep(0.01)
    updater.stop()

    assert len(backend.calls) == 1
    namespace_id, events, batch_size = backend.calls[0]
    assert namespace_id == "mirofish-runtime-sim-runtime-0001-0001"
    assert batch_size == 2
    assert len(events) == 2
    assert events[0]["artifact_type"] == "runtime_graph_memory_update"
    assert events[0]["base_graph_id"] == "mirofish-base-proj-runtime"
    assert events[0]["runtime_graph_id"] == "mirofish-runtime-sim-runtime-0001-0001"
    assert events[0]["platform"] == "twitter"
    assert events[0]["action"]["action_type"] == "CREATE_POST"
    assert events[1]["transition_type"] == "belief_update"
