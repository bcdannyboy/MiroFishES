import importlib


class _FakeBackend:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot or {
            "graph_id": "graph-1",
            "node_count": 0,
            "edge_count": 0,
            "nodes": [],
            "edges": [],
        }
        self.calls = []

    def create_base_graph(self, *, graph_name, project_id=None):
        self.calls.append(("create_base_graph", graph_name, project_id))
        return {"namespace_id": "mirofish-base-proj-1"}

    def register_ontology(self, namespace_id, ontology):
        self.calls.append(("register_ontology", namespace_id, ontology))

    def add_text_batches(self, namespace_id, chunks, batch_size=None, progress_callback=None):
        self.calls.append(("add_text_batches", namespace_id, list(chunks), batch_size))
        if progress_callback:
            progress_callback("sent", 1.0)
        return ["ep-1", "ep-2"]

    def wait_for_episode_processing(
        self,
        namespace_id,
        episode_ids,
        progress_callback=None,
        timeout=None,
    ):
        self.calls.append(("wait", namespace_id, list(episode_ids), timeout))
        if progress_callback:
            progress_callback("done", 1.0)

    def export_graph_snapshot(self, namespace_id):
        self.calls.append(("export_graph_snapshot", namespace_id))
        payload = dict(self.snapshot)
        payload["graph_id"] = namespace_id
        return payload

    def delete_graph(self, namespace_id):
        self.calls.append(("delete_graph", namespace_id))


def _build_service(snapshot=None):
    module = importlib.import_module("app.services.graph_builder")
    backend = _FakeBackend(snapshot=snapshot)
    service = module.GraphBuilderService(graph_backend=backend, project_id="proj-1")
    return module, service, backend


def test_resolve_batch_plan_scales_batch_size_and_caps_concurrency():
    module, service, _backend = _build_service()

    small = service._resolve_batch_plan(total_chunks=3)
    medium = service._resolve_batch_plan(total_chunks=24)
    large = service._resolve_batch_plan(total_chunks=120)

    assert small["batch_size"] == 3
    assert medium["batch_size"] > small["batch_size"]
    assert large["batch_size"] >= medium["batch_size"]
    assert large["batch_size"] <= service.MAX_BATCH_SIZE
    assert small["max_inflight_batches"] >= 1
    assert large["max_inflight_batches"] <= service.MAX_INFLIGHT_BATCHES


def test_graph_builder_service_delegates_build_primitives_to_graph_backend():
    _module, service, backend = _build_service(
        snapshot={
            "graph_id": "placeholder",
            "node_count": 1,
            "edge_count": 0,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Tracked participant",
                    "attributes": {"role": "analyst"},
                }
            ],
            "edges": [],
        }
    )

    graph_id = service.create_graph("Rates Graph")
    service.set_ontology(graph_id, {"entity_types": [], "edge_types": []})
    episode_ids = service.add_text_batches(graph_id, ["alpha", "beta"], batch_size=2)
    service._wait_for_episodes(graph_id, episode_ids, timeout=600)
    snapshot = service.get_graph_snapshot(graph_id)
    service.delete_graph(graph_id)

    assert graph_id == "mirofish-base-proj-1"
    assert backend.calls[0] == ("create_base_graph", "Rates Graph", "proj-1")
    assert backend.calls[1] == (
        "register_ontology",
        "mirofish-base-proj-1",
        {"entity_types": [], "edge_types": []},
    )
    assert backend.calls[2] == (
        "add_text_batches",
        "mirofish-base-proj-1",
        ["alpha", "beta"],
        2,
    )
    assert backend.calls[3] == ("wait", "mirofish-base-proj-1", ["ep-1", "ep-2"], 600)
    assert backend.calls[4] == ("export_graph_snapshot", "mirofish-base-proj-1")
    assert backend.calls[5] == ("delete_graph", "mirofish-base-proj-1")
    assert snapshot["graph_id"] == "mirofish-base-proj-1"


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


def test_get_graph_snapshot_returns_exact_counts_and_entity_types():
    _module, service, _backend = _build_service(
        snapshot={
            "graph_id": "placeholder",
            "node_count": 2,
            "edge_count": 1,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "summary",
                    "attributes": {},
                },
                {
                    "uuid": "node-2",
                    "name": "Desk",
                    "labels": ["Entity", "Organization"],
                    "summary": "summary",
                    "attributes": {},
                },
            ],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "MENTIONS",
                    "fact": "Analyst mentions Desk",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                    "attributes": {},
                    "source_node_name": "Analyst",
                    "target_node_name": "Desk",
                }
            ],
        }
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


def test_get_graph_snapshot_returns_layered_counts_and_type_breakdown():
    _module, service, _backend = _build_service(
        snapshot={
            "graph_id": "placeholder",
            "node_count": 3,
            "edge_count": 1,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "summary",
                    "attributes": {},
                },
                {
                    "uuid": "node-2",
                    "name": "June cut likely",
                    "labels": ["Entity", "Claim"],
                    "summary": "summary",
                    "attributes": {},
                },
                {
                    "uuid": "node-3",
                    "name": "Payroll report",
                    "labels": ["Entity", "Evidence"],
                    "summary": "summary",
                    "attributes": {},
                },
            ],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "SUPPORTED_BY",
                    "fact": "June cut likely is supported by payroll report",
                    "source_node_uuid": "node-2",
                    "target_node_uuid": "node-3",
                    "attributes": {},
                    "source_node_name": "June cut likely",
                    "target_node_name": "Payroll report",
                }
            ],
        }
    )

    snapshot = service.get_graph_snapshot("graph-1")

    assert snapshot["graph_counts"]["actor_count"] == 1
    assert snapshot["graph_counts"]["analytical_object_count"] == 2
    assert snapshot["graph_counts"]["node_type_counts"] == {
        "Claim": 1,
        "Evidence": 1,
        "Person": 1,
    }
    assert snapshot["graph_counts"]["edge_type_counts"] == {"SUPPORTED_BY": 1}
    assert snapshot["graph_counts"]["analytical_types"] == ["Claim", "Evidence"]


def test_get_graph_data_preview_mode_omits_heavy_fields_and_marks_truncation():
    _module, service, _backend = _build_service(
        snapshot={
            "graph_id": "placeholder",
            "node_count": 2,
            "edge_count": 2,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Detailed summary",
                    "attributes": {"role": "analyst"},
                    "created_at": None,
                },
                {
                    "uuid": "node-2",
                    "name": "Desk",
                    "labels": ["Entity", "Organization"],
                    "summary": "Desk summary",
                    "attributes": {"kind": "team"},
                    "created_at": None,
                },
            ],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "MENTIONS",
                    "fact": "Analyst mentions the plaza",
                    "fact_type": "MENTIONS",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                    "source_node_name": "Analyst",
                    "target_node_name": "Desk",
                    "attributes": {"weight": 2},
                    "created_at": None,
                    "episodes": ["ep-1"],
                },
                {
                    "uuid": "edge-2",
                    "name": "MENTIONS",
                    "fact": "Desk mentions the market",
                    "fact_type": "MENTIONS",
                    "source_node_uuid": "node-2",
                    "target_node_uuid": "node-1",
                    "source_node_name": "Desk",
                    "target_node_name": "Analyst",
                    "attributes": {"weight": 3},
                    "created_at": None,
                    "episodes": ["ep-2"],
                },
            ],
        }
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
    assert payload["node_pages"] == 1
    assert payload["edge_pages"] == 1
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
        "target_node_name": "Desk",
        "created_at": None,
    }


def test_get_graph_data_full_mode_keeps_rich_fields():
    _module, service, _backend = _build_service(
        snapshot={
            "graph_id": "placeholder",
            "node_count": 1,
            "edge_count": 1,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Detailed summary",
                    "attributes": {"role": "analyst"},
                    "created_at": "2026-03-12T09:00:00",
                }
            ],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "MENTIONS",
                    "fact": "Analyst mentions the plaza",
                    "fact_type": "MENTIONS",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                    "source_node_name": "Analyst",
                    "target_node_name": "",
                    "attributes": {"weight": 2},
                    "created_at": "2026-03-12T09:01:00",
                    "valid_at": "2026-03-12T09:01:00",
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": ["ep-1"],
                }
            ],
        }
    )

    payload = service.get_graph_data("graph-1", mode="full")

    assert payload["mode"] == "full"
    assert payload["truncated"] is False
    assert payload["nodes"][0]["summary"] == "Detailed summary"
    assert payload["nodes"][0]["attributes"] == {"role": "analyst"}
    assert payload["edges"][0]["attributes"] == {"weight": 2}
    assert payload["edges"][0]["valid_at"] == "2026-03-12T09:01:00"
    assert payload["edges"][0]["episodes"] == ["ep-1"]
