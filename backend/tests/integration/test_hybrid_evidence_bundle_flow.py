from __future__ import annotations

import importlib
import json

from app.models.forecasting import ForecastQuestion
from app.services.evidence_bundle_service import (
    EvidenceBundleService,
    UploadedLocalArtifactEvidenceProvider,
)
from app.services.hybrid_evidence_retriever import HybridEvidenceRetriever
from app.services.local_evidence_index import LocalEvidenceIndex


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_hybrid_evidence_bundle_flow_produces_cited_forecast_hints(
    simulation_data_dir,
    tmp_path,
    monkeypatch,
):
    project_module = importlib.import_module("app.models.project")
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )

    project_dir = projects_dir / "proj-integration-hybrid"
    project_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        project_dir / "source_units.json",
        {
            "artifact_type": "source_units",
            "project_id": "proj-integration-hybrid",
            "source_count": 1,
            "unit_count": 2,
            "units": [
                {
                    "unit_id": "su-1",
                    "source_id": "src-1",
                    "stable_source_id": "stable-src-1",
                    "source_sha256": "sha-1",
                    "original_filename": "policy.md",
                    "relative_path": "files/policy.md",
                    "source_order": 1,
                    "unit_order": 1,
                    "unit_type": "paragraph",
                    "char_start": 0,
                    "char_end": 98,
                    "combined_text_start": 0,
                    "combined_text_end": 98,
                    "text": "Payroll softness supports a June rate cut and reinforces easing expectations.",
                    "metadata": {},
                    "extraction_warnings": [],
                },
                {
                    "unit_id": "su-2",
                    "source_id": "src-1",
                    "stable_source_id": "stable-src-1",
                    "source_sha256": "sha-1",
                    "original_filename": "policy.md",
                    "relative_path": "files/policy.md",
                    "source_order": 1,
                    "unit_order": 2,
                    "unit_type": "paragraph",
                    "char_start": 99,
                    "char_end": 188,
                    "combined_text_start": 99,
                    "combined_text_end": 188,
                    "text": "A later survey disputes the easing case and contradicts the earlier optimism.",
                    "metadata": {},
                    "extraction_warnings": [],
                },
            ],
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "project_id": "proj-integration-hybrid",
            "graph_id": "graph-integration-1",
            "total_count": 0,
            "filtered_count": 0,
            "entity_types": [],
            "entities": [],
            "analytical_object_count": 2,
            "analytical_types": ["Claim", "Evidence"],
            "analytical_objects": [
                {
                    "uuid": "claim-support",
                    "name": "June cut support",
                    "labels": ["Claim"],
                    "summary": "Weaker payroll data suggests a June rate cut is likely.",
                    "attributes": {},
                    "related_edges": [],
                    "related_nodes": [],
                    "object_type": "Claim",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "source_ids": ["src-1"],
                        "stable_source_ids": ["stable-src-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "stable-src-1",
                                "original_filename": "policy.md",
                                "relative_path": "files/policy.md",
                                "unit_type": "paragraph",
                                "source_order": 1,
                                "unit_order": 1,
                                "char_start": 0,
                                "char_end": 98,
                                "combined_text_start": 0,
                                "combined_text_end": 98,
                            }
                        ],
                    },
                },
                {
                    "uuid": "evidence-contradict",
                    "name": "Contrary survey",
                    "labels": ["Evidence"],
                    "summary": "A later survey contradicts the easing case.",
                    "attributes": {},
                    "related_edges": [{"edge_name": "contradicts", "fact": "Survey contradicts the easing case."}],
                    "related_nodes": [],
                    "object_type": "Evidence",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-2"],
                        "source_ids": ["src-1"],
                        "stable_source_ids": ["stable-src-1"],
                        "citations": [
                            {
                                "unit_id": "su-2",
                                "source_id": "src-1",
                                "stable_source_id": "stable-src-1",
                                "original_filename": "policy.md",
                                "relative_path": "files/policy.md",
                                "unit_type": "paragraph",
                                "source_order": 1,
                                "unit_order": 2,
                                "char_start": 99,
                                "char_end": 188,
                                "combined_text_start": 99,
                                "combined_text_end": 188,
                            }
                        ],
                    },
                },
            ],
            "graph_node_count": 2,
            "graph_edge_count": 1,
            "object_count": 2,
            "citation_coverage": {
                "source_unit_backed_node_count": 2,
                "source_unit_backed_edge_count": 1,
                "edge_episode_link_count": 2,
            },
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "project_id": "proj-integration-hybrid",
            "graph_id": "graph-integration-1",
            "chunk_count": 2,
            "chunking_strategy": "semantic_source_units",
            "graph_counts": {
                "node_count": 2,
                "edge_count": 1,
                "actor_count": 0,
                "analytical_object_count": 2,
                "entity_types": [],
                "analytical_types": ["Claim", "Evidence"],
            },
            "citation_coverage": {
                "source_unit_backed_node_count": 2,
                "source_unit_backed_edge_count": 1,
                "edge_episode_link_count": 2,
            },
        },
    )

    retriever = HybridEvidenceRetriever(
        embedding_client=type(
            "_FakeEmbeddingClient",
            (),
            {
                "embed_text": staticmethod(
                    lambda text, normalize=True: [1.0, 0.0, 0.0]
                    if "june" in text.lower() or "rate cut" in text.lower()
                    else [0.0, 1.0, 0.0]
                ),
                "embed_texts": staticmethod(
                    lambda texts, normalize=True: [
                        [1.0, 0.0, 0.0]
                        if "june" in text.lower() or "rate cut" in text.lower()
                        else [0.0, 1.0, 0.0]
                        for text in texts
                    ]
                ),
            },
        )(),
        evidence_index=LocalEvidenceIndex(
            index_path=str(tmp_path / "integration-local-evidence.sqlite3")
        ),
    )
    provider = UploadedLocalArtifactEvidenceProvider(
        str(simulation_data_dir),
        hybrid_retriever=retriever,
    )
    service = EvidenceBundleService(providers=[provider])

    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-hybrid-integration-1",
                "project_id": "proj-integration-hybrid",
                "title": "Rate cut outlook",
                "question": "Will the Fed cut rates in June 2026?",
                "question_text": "Will the Fed cut rates in June 2026?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-31T12:00:00",
                "created_at": "2026-03-31T12:00:00",
                "updated_at": "2026-03-31T12:00:00",
            }
        ),
        provider_ids=["uploaded_local_artifacts"],
    )

    assert bundle.status == "ready"
    assert bundle.provider_snapshots[0]["status"] == "ready"
    assert len(bundle.source_entries) >= 2
    assert any(entry.citation_id and entry.citation_id.startswith("[") for entry in bundle.source_entries)
    assert any(entry.metadata.get("forecast_hints") for entry in bundle.source_entries)
    assert any(entry.conflict_status == "supports" for entry in bundle.source_entries)
    assert any(entry.conflict_status == "contradicts" for entry in bundle.source_entries)
