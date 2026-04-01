import importlib
import sys


def _load_runtime_event_ingestor_module():
    for module_name in (
        "app.services.graph_backend.runtime_event_ingestor",
        "app.services.graph_backend.graphiti_factory",
        "app.services.graph_backend.settings",
        "app.services.graph_backend",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.runtime_event_ingestor")


class _FakeGraphiti:
    def __init__(self):
        self.calls = []

    async def add_episode(self, **kwargs):
        self.calls.append(kwargs)
        return {"uuid": f"episode-{len(self.calls)}"}


class _FakeGraphitiFactory:
    def __init__(self, client):
        self.client = client

    def build_client(self):
        return self.client

    def get_episode_type(self, member_name="text"):
        return member_name


def test_runtime_event_ingestor_batches_structured_events_into_graphiti_episodes():
    module = _load_runtime_event_ingestor_module()
    client = _FakeGraphiti()
    ingestor = module.GraphitiRuntimeEventIngestor()

    episode_ids = ingestor.ingest_runtime_events(
        namespace_id="mirofish-runtime-sim-1-0001-0001",
        events=[
            {
                "artifact_type": "runtime_state_transition",
                "transition_type": "claim",
                "human_readable": "Analyst create_post :: Hiring is weakening",
            },
            {
                "artifact_type": "runtime_state_transition",
                "transition_type": "belief_update",
                "human_readable": "Analyst belief update via like_post",
            },
            {
                "artifact_type": "runtime_state_transition",
                "transition_type": "topic_shift",
                "human_readable": "Analyst shifted attention to Labor slowdown",
            },
        ],
        batch_size=2,
        graphiti_factory=_FakeGraphitiFactory(client),
    )

    assert episode_ids == ["episode-1", "episode-2"]
    assert len(client.calls) == 2
    assert client.calls[0]["group_id"] == "mirofish-runtime-sim-1-0001-0001"
    assert client.calls[0]["name"] == "mirofish-runtime-sim-1-0001-0001-runtime-batch-0001"
    assert client.calls[0]["source"] == "text"
    assert client.calls[0]["source_description"] == "MiroFishES runtime event batch"
    assert client.calls[0]["episode_body"].count("\n") == 1
    assert '"transition_type": "claim"' in client.calls[0]["episode_body"]
    assert '"transition_type": "belief_update"' in client.calls[0]["episode_body"]
    assert client.calls[1]["name"] == "mirofish-runtime-sim-1-0001-0001-runtime-batch-0002"
    assert '"transition_type": "topic_shift"' in client.calls[1]["episode_body"]
