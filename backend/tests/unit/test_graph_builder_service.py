import importlib

from app.utils.zep_paging import PageFetchResult


class _FakeNode:
    def __init__(self, uuid_, name, labels, summary="", attributes=None, created_at=None):
        self.uuid_ = uuid_
        self.name = name
        self.labels = labels
        self.summary = summary
        self.attributes = attributes or {}
        self.created_at = created_at


class _FakeEdge:
    def __init__(
        self,
        uuid_,
        name,
        fact,
        source_node_uuid,
        target_node_uuid,
        *,
        attributes=None,
        created_at=None,
        valid_at=None,
        invalid_at=None,
        expired_at=None,
        episodes=None,
    ):
        self.uuid_ = uuid_
        self.name = name
        self.fact = fact
        self.source_node_uuid = source_node_uuid
        self.target_node_uuid = target_node_uuid
        self.attributes = attributes or {}
        self.created_at = created_at
        self.valid_at = valid_at
        self.invalid_at = invalid_at
        self.expired_at = expired_at
        self.episodes = episodes or []


def _build_service(module):
    service = module.GraphBuilderService.__new__(module.GraphBuilderService)
    service.client = object()
    return service


def test_get_graph_data_preview_mode_omits_heavy_fields_and_marks_truncation(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)

    monkeypatch.setattr(
        module,
        "fetch_node_window",
        lambda client, graph_id, max_items=None: PageFetchResult(
            items=[
                _FakeNode(
                    "node-1",
                    "Analyst",
                    ["Entity", "Person"],
                    summary="Detailed summary",
                    attributes={"role": "analyst"},
                )
            ],
            page_count=2,
            truncated=True,
            has_more=True,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "fetch_edge_window",
        lambda client, graph_id, max_items=None: PageFetchResult(
            items=[
                _FakeEdge(
                    "edge-1",
                    "MENTIONS",
                    "Analyst mentions the plaza",
                    "node-1",
                    "node-2",
                    attributes={"weight": 2},
                    episodes=["ep-1"],
                )
            ],
            page_count=3,
            truncated=True,
            has_more=True,
        ),
        raising=False,
    )

    payload = service.get_graph_data(
        "graph-1",
        mode="preview",
        max_nodes=1,
        max_edges=1,
    )

    assert payload["graph_id"] == "graph-1"
    assert payload["mode"] == "preview"
    assert payload["truncated"] is True
    assert payload["returned_nodes"] == 1
    assert payload["returned_edges"] == 1
    assert payload["requested_max_nodes"] == 1
    assert payload["requested_max_edges"] == 1
    assert payload["node_pages"] == 2
    assert payload["edge_pages"] == 3
    assert payload["nodes"][0] == {
        "uuid": "node-1",
        "name": "Analyst",
        "labels": ["Entity", "Person"],
        "created_at": None,
    }
    assert payload["edges"][0] == {
        "uuid": "edge-1",
        "name": "MENTIONS",
        "fact": "Analyst mentions the plaza",
        "fact_type": "MENTIONS",
        "source_node_uuid": "node-1",
        "target_node_uuid": "node-2",
        "source_node_name": "Analyst",
        "target_node_name": "",
        "created_at": None,
    }


def test_get_graph_data_full_mode_keeps_rich_fields(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)

    monkeypatch.setattr(
        module,
        "fetch_node_window",
        lambda client, graph_id, max_items=None: PageFetchResult(
            items=[
                _FakeNode(
                    "node-1",
                    "Analyst",
                    ["Entity", "Person"],
                    summary="Detailed summary",
                    attributes={"role": "analyst"},
                    created_at="2026-03-12T09:00:00",
                )
            ],
            page_count=1,
            truncated=False,
            has_more=False,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "fetch_edge_window",
        lambda client, graph_id, max_items=None: PageFetchResult(
            items=[
                _FakeEdge(
                    "edge-1",
                    "MENTIONS",
                    "Analyst mentions the plaza",
                    "node-1",
                    "node-2",
                    attributes={"weight": 2},
                    created_at="2026-03-12T09:01:00",
                    valid_at="2026-03-12T09:01:00",
                    invalid_at=None,
                    expired_at=None,
                    episodes=["ep-1"],
                )
            ],
            page_count=1,
            truncated=False,
            has_more=False,
        ),
        raising=False,
    )

    payload = service.get_graph_data("graph-1", mode="full")

    assert payload["mode"] == "full"
    assert payload["truncated"] is False
    assert payload["nodes"][0]["summary"] == "Detailed summary"
    assert payload["nodes"][0]["attributes"] == {"role": "analyst"}
    assert payload["edges"][0]["attributes"] == {"weight": 2}
    assert payload["edges"][0]["valid_at"] == "2026-03-12T09:01:00"
    assert payload["edges"][0]["episodes"] == ["ep-1"]

