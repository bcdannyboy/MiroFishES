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
        "extract_text",
        staticmethod(
            lambda _path: "Labor policy memo.\nWorkers mention slowdown risk and intervention timing."
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
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["grounding_artifacts"]["source_manifest"]["exists"] is True
    assert payload["grounding_artifacts"]["graph_build_summary"]["exists"] is False
    assert manifest["artifact_type"] == "source_manifest"
    assert manifest["project_id"] == project_id
    assert (
        manifest["simulation_requirement"]
        == "Forecast whether intervention reduces slowdown risk."
    )
    assert manifest["boundary_note"].startswith("Uploaded project sources only")
    assert manifest["source_count"] == 1
    source = manifest["sources"][0]
    assert source["original_filename"] == "memo.md"
    assert source["content_kind"] == "document"
    assert source["extraction_status"] == "succeeded"
    assert source["extracted_text_length"] > 0
    assert source["combined_text_start"] < source["combined_text_end"]
    assert source["sha256"] == hashlib.sha256(b"labor memo").hexdigest()
    assert source["excerpt"].startswith("Labor policy memo.")


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

        def _wait_for_episodes(self, episode_uuids, progress_callback=None, timeout=600):
            return None

        def get_graph_data(self, graph_id, mode="full", max_nodes=None, max_edges=None):
            return {
                "graph_id": graph_id,
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person"],
                "nodes": [],
                "edges": [],
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

    project_response = client.get(f"/api/graph/project/{project.project_id}")
    project_payload = project_response.get_json()["data"]
    assert project_payload["grounding_artifacts"]["graph_build_summary"]["exists"] is True


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


def test_reset_project_clears_stale_graph_build_summary(monkeypatch, tmp_path):
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

    client = _build_test_client(graph_module)
    response = client.post(f"/api/graph/project/{project.project_id}/reset")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["graph_id"] is None
    assert payload["grounding_artifacts"]["graph_build_summary"]["exists"] is False
    assert not (projects_dir / project.project_id / "graph_build_summary.json").exists()
