import hashlib
import importlib
import io
import json
import sys
from pathlib import Path

from flask import Flask


def _load_graph_api_module():
    sys.modules.pop("app.api.graph", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.graph")


def _load_project_module():
    return importlib.import_module("app.models.project")


def _load_grounding_builder_module():
    return importlib.import_module("app.services.grounding_bundle_builder")


def _build_test_client(graph_module):
    app = Flask(__name__)
    app.register_blueprint(graph_module.graph_bp, url_prefix="/api/graph")
    return app.test_client()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _configure_projects_dir(monkeypatch, tmp_path):
    project_module = _load_project_module()
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )
    return project_module, projects_dir


def test_generate_ontology_persists_source_manifest_and_artifact_summary(monkeypatch, tmp_path):
    graph_module = _load_graph_api_module()
    _, projects_dir = _configure_projects_dir(monkeypatch, tmp_path)

    class _FakeOntologyGenerator:
        def generate(self, **kwargs):
            return {
                "entity_types": [{"name": "Person", "attributes": []}],
                "edge_types": [{"name": "MENTIONS", "source_targets": []}],
                "analysis_summary": "Uploaded memo emphasizes labor-policy uncertainty.",
            }

    monkeypatch.setattr(graph_module, "OntologyGenerator", _FakeOntologyGenerator)
    monkeypatch.setattr(
        graph_module.FileParser,
        "extract_document",
        staticmethod(
            lambda _path: {
                "path": _path,
                "filename": "memo.md",
                "extension": ".md",
                "text": "Labor policy memo.\nWorkers mention slowdown risk and intervention timing.",
                "sha256": hashlib.sha256(b"labor memo").hexdigest(),
                "extraction_warnings": [],
            }
        ),
    )
    monkeypatch.setattr(
        graph_module.TextProcessor,
        "preprocess_text",
        staticmethod(lambda text: text.strip()),
    )

    client = _build_test_client(graph_module)
    response = client.post(
        "/api/graph/ontology/generate",
        data={
            "project_name": "Grounding Test",
            "simulation_requirement": "Forecast whether intervention reduces slowdown risk.",
            "files": [(io.BytesIO(b"labor memo"), "memo.md")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    project_id = payload["project_id"]
    manifest_path = projects_dir / project_id / "source_manifest.json"
    source_units_path = projects_dir / project_id / "source_units.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_units = json.loads(source_units_path.read_text(encoding="utf-8"))

    assert payload["grounding_artifacts"]["source_manifest"]["exists"] is True
    assert payload["grounding_artifacts"]["source_units"]["exists"] is True
    assert payload["grounding_artifacts"]["graph_build_summary"]["exists"] is False
    assert payload["grounding_artifacts"]["graph_phase_timings"]["exists"] is True
    assert payload["grounding_artifacts"]["graph_entity_index"]["exists"] is False
    assert manifest["artifact_type"] == "source_manifest"
    assert manifest["project_id"] == project_id
    assert (
        manifest["simulation_requirement"]
        == "Forecast whether intervention reduces slowdown risk."
    )
    assert manifest["boundary_note"].startswith("Uploaded project sources only")
    assert manifest["source_count"] == 1
    assert manifest["source_artifacts"]["source_units"] == "source_units.json"
    source = manifest["sources"][0]
    assert source["original_filename"] == "memo.md"
    assert source["content_kind"] == "document"
    assert source["extraction_status"] == "succeeded"
    assert source["extracted_text_length"] > 0
    assert source["combined_text_start"] < source["combined_text_end"]
    assert source["sha256"] == hashlib.sha256(b"labor memo").hexdigest()
    assert source["stable_source_id"].startswith("src-")
    assert source["excerpt"].startswith("Labor policy memo.")
    assert source_units["artifact_type"] == "source_units"
    assert source_units["project_id"] == project_id
    assert source_units["source_count"] == 1
    assert source_units["unit_count"] >= 1
    assert source_units["source_artifacts"]["source_manifest"] == "source_manifest.json"
    assert source_units["units"][0]["unit_id"].startswith("su-")
    assert source_units["units"][0]["stable_source_id"] == source["stable_source_id"]
    assert source_units["units"][0]["text"].startswith("Labor policy memo.")

    timings_path = projects_dir / project_id / "graph_phase_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8"))
    assert timings["artifact_type"] == "phase_timings"
    assert set(timings["phases"]) == {"upload_parse", "ontology_generation"}
    assert timings["phases"]["upload_parse"]["metadata"]["uploaded_file_count"] == 1
    assert timings["phases"]["upload_parse"]["metadata"]["parsed_file_count"] == 1
    assert timings["phases"]["upload_parse"]["metadata"]["failed_file_count"] == 0
    assert timings["phases"]["upload_parse"]["metadata"]["total_text_length"] > 0
    assert timings["phases"]["ontology_generation"]["metadata"]["entity_type_count"] == 1
    assert timings["phases"]["ontology_generation"]["metadata"]["edge_type_count"] == 1


def test_generate_ontology_returns_413_when_upload_exceeds_limit(monkeypatch, tmp_path):
    graph_module = _load_graph_api_module()
    _configure_projects_dir(monkeypatch, tmp_path)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    app.register_blueprint(graph_module.graph_bp, url_prefix="/api/graph")
    client = app.test_client()

    response = client.post(
        "/api/graph/ontology/generate",
        data={
            "simulation_requirement": "Forecast whether the upload path rejects oversized founder packs cleanly.",
            "files": [(io.BytesIO(b"x" * 4096), "oversized.md")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["max_upload_bytes"] == 1024
    assert "Upload exceeds the 1 KB limit" in payload["error"]


def test_build_graph_persists_graph_build_summary(monkeypatch, tmp_path):
    graph_module = _load_graph_api_module()
    project_module, projects_dir = _configure_projects_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(graph_module.Config, "ZEP_API_KEY", "test-key", raising=False)

    project = project_module.ProjectManager.create_project(name="Graph Grounding")
    project.simulation_requirement = "Forecast whether intervention reduces slowdown risk."
    project.status = project_module.ProjectStatus.ONTOLOGY_GENERATED
    project.ontology = {
        "entity_types": [{"name": "Person", "attributes": []}],
        "edge_types": [{"name": "MENTIONS", "source_targets": []}],
    }
    project.analysis_summary = "The seed documents emphasize labor-policy debate."
    project.chunk_size = 300
    project.chunk_overlap = 40
    project_module.ProjectManager.save_project(project)
    project_module.ProjectManager.save_extracted_text(
        project.project_id,
        "Chunk A\nChunk B",
    )
    _write_json(
        projects_dir / project.project_id / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project.project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": project.simulation_requirement,
            "boundary_note": "Uploaded project sources only; this artifact does not claim live-web coverage.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "memo.md",
                    "saved_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "size_bytes": 10,
                    "sha256": "abc123",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 14,
                    "combined_text_start": 0,
                    "combined_text_end": 14,
                    "parser_warnings": [],
                    "excerpt": "Chunk A",
                }
            ],
        },
    )

    class _FakeThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self.target = target
            self.args = args
            self.kwargs = kwargs or {}
            self.daemon = daemon

        def start(self):
            self.target(*self.args, **self.kwargs)

    class _FakeBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def create_graph(self, name):
            return "graph-grounded"

        def set_ontology(self, graph_id, ontology):
            return None

        def add_text_batches(self, graph_id, chunks, batch_size=3, progress_callback=None):
            return ["ep-1"]

        def _wait_for_episodes(
            self, graph_id, episode_uuids, progress_callback=None, timeout=600
        ):
            return None

        def get_graph_data(self, graph_id, mode="full", max_nodes=None, max_edges=None):
            raise AssertionError("build should not fetch full graph data for summary counts")

        def get_graph_snapshot(self, graph_id):
            return {
                "graph_id": graph_id,
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person"],
                "nodes": [
                    {
                        "uuid": "node-1",
                        "name": "Analyst",
                        "labels": ["Entity", "Person"],
                        "summary": "Tracked participant",
                        "attributes": {"role": "analyst"},
                    }
                ],
                "edges": [
                    {
                        "uuid": "edge-1",
                        "name": "MENTIONS",
                        "fact": "Analyst mentions rates",
                        "source_node_uuid": "node-1",
                        "target_node_uuid": "node-2",
                        "attributes": {},
                    }
                ],
            }

    monkeypatch.setattr(graph_module, "GraphBuilderService", _FakeBuilder)
    monkeypatch.setattr(
        graph_module.TextProcessor,
        "split_text",
        staticmethod(lambda text, chunk_size, overlap: ["Chunk A", "Chunk B"]),
    )
    monkeypatch.setattr(graph_module.threading, "Thread", _FakeThread)

    client = _build_test_client(graph_module)
    response = client.post(
        "/api/graph/build",
        json={"project_id": project.project_id},
    )

    assert response.status_code == 200
    summary_path = projects_dir / project.project_id / "graph_build_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    timings = json.loads(
        (projects_dir / project.project_id / "graph_phase_timings.json").read_text(
            encoding="utf-8"
        )
    )
    entity_index = json.loads(
        (projects_dir / project.project_id / "graph_entity_index.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["artifact_type"] == "graph_build_summary"
    assert summary["project_id"] == project.project_id
    assert summary["graph_id"] == "graph-grounded"
    assert summary["chunk_size"] == 300
    assert summary["chunk_overlap"] == 40
    assert summary["chunk_count"] == 2
    assert summary["graph_counts"]["node_count"] == 7
    assert summary["graph_counts"]["edge_count"] == 9
    assert summary["source_artifacts"]["source_manifest"] == "source_manifest.json"
    assert summary["ontology_summary"]["analysis_summary"] == (
        "The seed documents emphasize labor-policy debate."
    )
    assert timings["artifact_type"] == "phase_timings"
    assert set(timings["phases"]) >= {"graph_batch_send", "graph_wait"}
    assert entity_index["artifact_type"] == "graph_entity_index"
    assert entity_index["graph_id"] == "graph-grounded"
    assert entity_index["total_count"] == 1
    assert entity_index["filtered_count"] == 1
    assert entity_index["entity_types"] == ["Person"]

    project_response = client.get(f"/api/graph/project/{project.project_id}")
    project_payload = project_response.get_json()["data"]
    assert project_payload["grounding_artifacts"]["graph_build_summary"]["exists"] is True
    assert project_payload["grounding_artifacts"]["graph_phase_timings"]["exists"] is True
    assert project_payload["grounding_artifacts"]["graph_entity_index"]["exists"] is True


def test_grounding_bundle_builder_marks_ready_vs_partial_without_code_analysis(
    monkeypatch, tmp_path
):
    project_module, projects_dir = _configure_projects_dir(monkeypatch, tmp_path)
    simulation_data_dir = tmp_path / "simulations"
    monkeypatch.setattr(
        importlib.import_module("app.config").Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    project_id = "proj-grounding"
    simulation_id = "sim-grounding"
    project_dir = projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": "Forecast whether intervention reduces slowdown risk.",
            "boundary_note": "Uploaded project sources only; this artifact does not claim live-web coverage.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "memo.md",
                    "saved_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "size_bytes": 10,
                    "sha256": "abc123",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 14,
                    "combined_text_start": 0,
                    "combined_text_end": 14,
                    "parser_warnings": [],
                    "excerpt": "Workers mention slowdown risk.",
                }
            ],
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": "graph-1",
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {"source_manifest": "source_manifest.json"},
            "ontology_summary": {
                "analysis_summary": "Seed documents emphasize labor-policy debate.",
                "entity_type_count": 1,
                "edge_type_count": 1,
            },
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 2,
            "graph_counts": {
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person"],
            },
            "warnings": [],
        },
    )

    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )
    builder_module = _load_grounding_builder_module()
    builder = builder_module.GroundingBundleBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )

    bundle = builder.build_grounding_bundle(
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id="graph-1",
    )
    summary = builder.build_grounding_summary(bundle)

    assert bundle["status"] == "ready"
    assert bundle["code_analysis_summary"]["status"] == "not_requested"
    assert bundle["citation_index"]["source"][0]["citation_id"] == "[S1]"
    assert bundle["citation_index"]["graph"][0]["citation_id"] == "[G1]"
    assert summary["status"] == "ready"
    assert summary["citation_counts"] == {"source": 1, "graph": 1, "code": 0}
    assert summary["evidence_count"] == 2

    partial_bundle = builder.build_grounding_bundle(
        simulation_id="sim-partial",
        project_id="missing-project",
        graph_id="graph-missing",
    )
    assert partial_bundle["status"] == "unavailable"
    assert "missing_source_manifest" in partial_bundle["warnings"]


def test_grounding_bundle_builder_degrades_when_graph_summary_mismatches_scope(
    monkeypatch, tmp_path
):
    project_module, projects_dir = _configure_projects_dir(monkeypatch, tmp_path)
    project_id = "proj-grounding"
    project_dir = projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": "Forecast whether intervention reduces slowdown risk.",
            "boundary_note": "Uploaded project sources only; this artifact does not claim live-web coverage.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "memo.md",
                    "saved_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "size_bytes": 10,
                    "sha256": "abc123",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 14,
                    "combined_text_start": 0,
                    "combined_text_end": 14,
                    "parser_warnings": [],
                    "excerpt": "Workers mention slowdown risk.",
                }
            ],
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": "graph-current",
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {"source_manifest": "source_manifest.json"},
            "ontology_summary": {
                "analysis_summary": "Seed documents emphasize labor-policy debate.",
                "entity_type_count": 1,
                "edge_type_count": 1,
            },
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 2,
            "graph_counts": {
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person"],
            },
            "warnings": [],
        },
    )

    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )
    builder_module = _load_grounding_builder_module()
    builder = builder_module.GroundingBundleBuilder()

    bundle = builder.build_grounding_bundle(
        simulation_id="sim-grounding",
        project_id=project_id,
        graph_id="graph-stale",
    )

    assert bundle["status"] == "partial"
    assert bundle["citation_counts"] == {"source": 1, "graph": 0, "code": 0}
    assert bundle["graph_summary"]["status"] == "unavailable"
    assert "graph_build_summary_graph_id_mismatch" in bundle["warnings"]


def test_reset_project_clears_stale_graph_artifacts(monkeypatch, tmp_path):
    graph_module = _load_graph_api_module()
    project_module, projects_dir = _configure_projects_dir(monkeypatch, tmp_path)

    project = project_module.ProjectManager.create_project(name="Reset Grounding")
    project.status = project_module.ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "graph-1"
    project.ontology = {
        "entity_types": [{"name": "Person", "attributes": []}],
        "edge_types": [{"name": "MENTIONS", "source_targets": []}],
    }
    project_module.ProjectManager.save_project(project)
    _write_json(
        projects_dir / project.project_id / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project.project_id,
            "graph_id": "graph-1",
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {"source_manifest": "source_manifest.json"},
            "ontology_summary": {"analysis_summary": "Seed documents emphasize labor-policy debate."},
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 2,
            "graph_counts": {"node_count": 7, "edge_count": 9, "entity_types": ["Person"]},
            "warnings": [],
        },
    )
    _write_json(
        projects_dir / project.project_id / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "graph_id": "graph-1",
            "entity_types": ["Person"],
            "total_count": 1,
            "filtered_count": 1,
            "entities": [],
        },
    )
    _write_json(
        projects_dir / project.project_id / "graph_phase_timings.json",
        {
            "artifact_type": "phase_timings",
            "scope_kind": "project",
            "scope_id": project.project_id,
            "phases": {},
        },
    )

    client = _build_test_client(graph_module)
    response = client.post(f"/api/graph/project/{project.project_id}/reset")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["graph_id"] is None
    assert payload["grounding_artifacts"]["graph_build_summary"]["exists"] is False
    assert payload["grounding_artifacts"]["graph_entity_index"]["exists"] is False
    assert payload["grounding_artifacts"]["graph_phase_timings"]["exists"] is False
    assert not (projects_dir / project.project_id / "graph_build_summary.json").exists()
    assert not (projects_dir / project.project_id / "graph_entity_index.json").exists()
    assert not (projects_dir / project.project_id / "graph_phase_timings.json").exists()
