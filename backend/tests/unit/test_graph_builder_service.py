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


class _FakeEpisode:
    def __init__(self, uuid_, processed):
        self.uuid_ = uuid_
        self.processed = processed


def test_resolve_batch_plan_scales_batch_size_and_caps_concurrency():
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)

    small = service._resolve_batch_plan(total_chunks=3)
    medium = service._resolve_batch_plan(total_chunks=24)
    large = service._resolve_batch_plan(total_chunks=120)

    assert small["batch_size"] == 3
    assert medium["batch_size"] > small["batch_size"]
    assert large["batch_size"] >= medium["batch_size"]
    assert large["batch_size"] <= service.MAX_BATCH_SIZE
    assert small["max_inflight_batches"] >= 1
    assert large["max_inflight_batches"] <= service.MAX_INFLIGHT_BATCHES


def test_add_text_batches_does_not_use_fixed_post_batch_sleep(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)
    add_batch_calls = []

    class _FakeBatchEpisode:
        def __init__(self, uuid_):
            self.uuid_ = uuid_

    class _FakeGraph:
        def add_batch(self, graph_id, episodes):
            add_batch_calls.append((graph_id, len(episodes)))
            start = len(add_batch_calls)
            return [_FakeBatchEpisode(f"ep-{start}-{idx}") for idx, _ in enumerate(episodes)]

    service.client = type("Client", (), {"graph": _FakeGraph()})()
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("fixed sleep should not be used")),
    )

    episode_uuids = service.add_text_batches(
        "graph-1",
        ["a", "b", "c", "d", "e", "f"],
        batch_size=3,
    )

    assert len(episode_uuids) == 6
    assert add_batch_calls == [("graph-1", 3), ("graph-1", 3)]


def test_wait_for_episodes_uses_graph_level_polling(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)
    get_by_graph_id_calls = []

    class _FakeEpisodeClient:
        def get(self, uuid_=None):  # pragma: no cover - current implementation should not use this
            raise AssertionError("episode.get(uuid_=...) should not be used for graph wait")

        def get_by_graph_id(self, graph_id, lastn=None):
            get_by_graph_id_calls.append((graph_id, lastn))
            return type(
                "EpisodeResponse",
                (),
                {
                    "episodes": [
                        _FakeEpisode("ep-1", True),
                        _FakeEpisode("ep-2", True),
                    ]
                },
            )()

    service.client = type(
        "Client",
        (),
        {"graph": type("Graph", (), {"episode": _FakeEpisodeClient()})()},
    )()
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("graph-level wait should not sleep in this test")),
    )

    service._wait_for_episodes(
        "graph-1",
        ["ep-1", "ep-2"],
    )

    assert get_by_graph_id_calls == [("graph-1", 2)]


def test_build_chunk_records_uses_combined_source_unit_offsets():
    module = importlib.import_module("app.services.graph_builder")

    text = "alpha one.\n\nbeta two."
    source_units = [
        {
            "unit_id": "su-src1-0001",
            "source_id": "src-1",
            "stable_source_id": "src-alpha",
            "original_filename": "alpha.md",
            "relative_path": "files/alpha.md",
            "source_order": 1,
            "unit_order": 1,
            "unit_type": "paragraph",
            "char_start": 0,
            "char_end": 10,
            "combined_text_start": 0,
            "combined_text_end": 10,
            "text": "alpha one.",
            "metadata": {},
            "extraction_warnings": [],
        },
        {
            "unit_id": "su-src2-0001",
            "source_id": "src-2",
            "stable_source_id": "src-beta",
            "original_filename": "beta.md",
            "relative_path": "files/beta.md",
            "source_order": 2,
            "unit_order": 1,
            "unit_type": "paragraph",
            "char_start": 0,
            "char_end": 9,
            "combined_text_start": 12,
            "combined_text_end": 21,
            "text": "beta two.",
            "metadata": {},
            "extraction_warnings": [],
        },
    ]

    records = module.build_chunk_records(
        text,
        chunk_size=12,
        overlap=0,
        source_units=source_units,
    )

    assert [record["text"] for record in records] == ["alpha one.", "beta two."]
    assert records[0]["source_unit_ids"] == ["su-src1-0001"]
    assert records[1]["source_unit_ids"] == ["su-src2-0001"]
    assert records[1]["char_start"] == 12
    assert records[1]["char_end"] == 21


def test_get_graph_snapshot_returns_exact_counts_and_entity_types(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)

    monkeypatch.setattr(
        module,
        "fetch_all_nodes",
        lambda client, graph_id, max_items=None: [
            _FakeNode("node-1", "Analyst", ["Entity", "Person"], summary="summary"),
            _FakeNode("node-2", "Desk", ["Entity", "Organization"], summary="summary"),
        ],
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "fetch_all_edges",
        lambda client, graph_id, max_items=None: [
            _FakeEdge(
                "edge-1",
                "MENTIONS",
                "Analyst mentions Desk",
                "node-1",
                "node-2",
            )
        ],
        raising=False,
    )

    snapshot = service.get_graph_snapshot("graph-1")

    assert snapshot["graph_id"] == "graph-1"
    assert snapshot["node_count"] == 2
    assert snapshot["edge_count"] == 1
    assert snapshot["entity_types"] == ["Organization", "Person"]
    assert snapshot["nodes"][0]["uuid"] == "node-1"
    assert snapshot["edges"][0]["uuid"] == "edge-1"
    assert snapshot["edges"][0]["source_node_uuid"] == "node-1"
    assert snapshot["edges"][0]["target_node_uuid"] == "node-2"


def test_get_graph_snapshot_returns_layered_counts_and_type_breakdown(monkeypatch):
    module = importlib.import_module("app.services.graph_builder")
    service = _build_service(module)

    monkeypatch.setattr(
        module,
        "fetch_all_nodes",
        lambda client, graph_id, max_items=None: [
            _FakeNode("node-1", "Analyst", ["Entity", "Person"], summary="summary"),
            _FakeNode("node-2", "June cut likely", ["Entity", "Claim"], summary="summary"),
            _FakeNode("node-3", "Payroll report", ["Entity", "Evidence"], summary="summary"),
        ],
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "fetch_all_edges",
        lambda client, graph_id, max_items=None: [
            _FakeEdge(
                "edge-1",
                "SUPPORTED_BY",
                "June cut likely is supported by payroll report",
                "node-2",
                "node-3",
            )
        ],
        raising=False,
    )

    snapshot = service.get_graph_snapshot("graph-1")

    assert snapshot["graph_id"] == "graph-1"
    assert snapshot["graph_counts"]["actor_count"] == 1
    assert snapshot["graph_counts"]["analytical_object_count"] == 2
    assert snapshot["graph_counts"]["node_type_counts"] == {
        "Claim": 1,
        "Evidence": 1,
        "Person": 1,
    }
    assert snapshot["graph_counts"]["edge_type_counts"] == {"SUPPORTED_BY": 1}
    assert snapshot["graph_counts"]["analytical_types"] == ["Claim", "Evidence"]


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
