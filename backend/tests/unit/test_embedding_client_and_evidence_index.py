import importlib
from types import SimpleNamespace


class _FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model=kwargs["model"],
            data=[
                SimpleNamespace(index=0, embedding=[3.0, 4.0]),
                SimpleNamespace(index=1, embedding=[0.0, 5.0]),
            ],
        )


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.embeddings = _FakeEmbeddings()


class _RouterStub:
    def resolve(self, task):
        return SimpleNamespace(
            task=task,
            model="text-embedding-3-small",
            api_key="embed-key",
            base_url="https://embed.example/v1",
        )


def test_local_embedding_client_embeds_and_normalizes_vectors(monkeypatch):
    module = importlib.import_module("app.utils.embedding_client")
    monkeypatch.setattr(module, "OpenAI", _FakeOpenAI)

    client = module.LocalEmbeddingClient(router=_RouterStub())
    vectors = client.embed_texts(["alpha", "beta"])

    assert client.client.embeddings.calls[0]["input"] == ["alpha", "beta"]
    assert client.client.embeddings.calls[0]["model"] == "text-embedding-3-small"
    assert vectors == [[0.6, 0.8], [0.0, 1.0]]


def test_local_evidence_index_persists_records_and_ranks_by_similarity(tmp_path):
    module = importlib.import_module("app.services.local_evidence_index")
    index_path = tmp_path / "evidence.sqlite3"

    index = module.LocalEvidenceIndex(index_path=str(index_path))
    index.upsert_many(
        [
            module.EvidenceIndexRecord(
                record_id="claim-1",
                namespace="claims",
                content="Demand is rising in the city center.",
                vector=[1.0, 0.0],
                metadata={"kind": "claim"},
            ),
            module.EvidenceIndexRecord(
                record_id="claim-2",
                namespace="claims",
                content="Supply is expanding in the suburbs.",
                vector=[0.0, 1.0],
                metadata={"kind": "claim"},
            ),
        ]
    )

    reopened = module.LocalEvidenceIndex(index_path=str(index_path))
    hits = reopened.search(namespace="claims", query_vector=[0.9, 0.1], limit=2)

    assert [hit.record_id for hit in hits] == ["claim-1", "claim-2"]
    assert hits[0].score > hits[1].score
    assert hits[0].metadata == {"kind": "claim"}
    assert reopened.stats()["record_count"] == 2
