from __future__ import annotations

import importlib
import json

from app.models.forecasting import EvidenceBundle, EvidenceSourceEntry, ForecastQuestion
from app.services.evidence_bundle_service import (
    EvidenceBundleService,
    FixtureExternalEvidenceProvider,
    UnavailableExternalEvidenceProvider,
    UploadedLocalArtifactEvidenceProvider,
)


QUESTION_ID = "forecast-evidence-001"
QUESTION_ISSUED_AT = "2026-03-30T09:00:00"


def _question_payload():
    return {
        "forecast_id": QUESTION_ID,
        "project_id": "proj-evidence-1",
        "title": "Policy support evidence",
        "question": "Will support exceed 55% by June 30, 2026?",
        "question_text": "Will support exceed 55% by June 30, 2026?",
        "question_type": "binary",
        "status": "active",
        "horizon": {"type": "date", "value": "2026-06-30"},
        "issue_timestamp": QUESTION_ISSUED_AT,
        "created_at": QUESTION_ISSUED_AT,
        "updated_at": QUESTION_ISSUED_AT,
        "primary_simulation_id": "sim-evidence-001",
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_evidence_bundle_service_builds_local_bundle_with_provenance_and_citation_index(
    simulation_data_dir,
):
    simulation_dir = simulation_data_dir / "sim-evidence-001"
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "generated_at": QUESTION_ISSUED_AT,
            "graph_id": "graph-1",
            "citation_index": {
                "source": [
                    {
                        "citation_id": "[S1]",
                        "source_id": "src-1",
                        "title": "memo.md",
                        "summary": "Uploaded memo excerpt",
                        "locator": "files/memo.md#chars=0-42",
                        "sha256": "abc123",
                    }
                ],
                "graph": [
                    {
                        "citation_id": "[G1]",
                        "title": "Graph build summary",
                        "summary": "Persisted graph lineage",
                        "locator": "graph:graph-1",
                    }
                ],
            },
        },
    )
    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:05:00",
            "summary": "Prepared simulation snapshot for evidence tests.",
        },
    )

    service = EvidenceBundleService(
        providers=[UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir))]
    )
    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        provider_ids=["uploaded_local_artifacts"],
    )

    assert bundle.status == "ready"
    assert bundle.retrieval_quality["status"] == "bounded_local_only"
    assert bundle.provider_snapshots[0]["status"] == "ready"
    assert len(bundle.source_entries) == 3
    assert bundle.citation_index["all"][0]["citation_id"] == "[S1]"
    provider_specific_citations = [
        citation
        for key, citations in bundle.citation_index.items()
        if key != "all"
        for citation in citations
    ]
    assert any(citation["citation_id"] == "[G1]" for citation in provider_specific_citations)
    assert bundle.source_entries[0].provenance["artifact_type"] == "grounding_bundle"
    assert bundle.source_entries[0].provenance["simulation_id"] == "sim-evidence-001"
    assert bundle.uncertainty_summary["causes"] == []


def test_evidence_bundle_derives_uncertainty_from_stale_conflicting_missing_and_low_relevance():
    bundle = EvidenceBundle.from_dict(
        {
            "bundle_id": "bundle-uncertain",
            "forecast_id": QUESTION_ID,
            "title": "Uncertain bundle",
            "summary": "Used to verify uncertainty derivation.",
            "source_entries": [
                {
                    "source_id": "src-stale",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "uploaded_source",
                    "title": "Old memo",
                    "freshness": {"status": "stale", "score": 0.2},
                    "relevance": {"score": 0.35},
                    "quality": {"score": 0.4},
                    "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                },
                {
                    "source_id": "src-conflict",
                    "provider_id": "fixture_external_provider",
                    "provider_kind": "external_live",
                    "kind": "external_document",
                    "title": "Conflicting article",
                    "freshness": {"status": "fresh", "score": 0.9},
                    "relevance": {"score": 0.42},
                    "quality": {"score": 0.61},
                    "conflict_status": "contradicts",
                    "conflict_markers": [
                        {
                            "kind": "claim_conflict",
                            "reason": "Reported direction contradicts the uploaded memo.",
                        }
                    ],
                    "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                },
            ],
            "provider_snapshots": [
                {
                    "provider_id": "fixture_external_provider",
                    "provider_kind": "external_live",
                    "status": "unavailable",
                }
            ],
            "missing_evidence_markers": [
                {
                    "kind": "missing_resolution_source",
                    "reason": "No named resolution source has been attached yet.",
                }
            ],
            "status": "partial",
            "boundary_note": "Evidence is still incomplete.",
            "created_at": QUESTION_ISSUED_AT,
        }
    )

    assert bundle.conflict_summary["status"] == "conflicting"
    assert set(bundle.uncertainty_summary["causes"]) == {
        "stale_evidence",
        "conflicting_evidence",
        "missing_evidence",
        "provider_unavailable",
        "relevance_uncertain",
    }
    assert bundle.freshness_summary["stale_entry_count"] == 1
    assert bundle.quality_summary["average_score"] == 0.505


def test_evidence_bundle_service_supports_fixture_external_provider_without_overclaiming():
    fixture_provider = FixtureExternalEvidenceProvider(
        entries=[
            EvidenceSourceEntry(
                source_id="ext-1",
                provider_id="fixture_external_provider",
                provider_kind="external_live",
                kind="external_document",
                title="External article",
                summary="Live provider fixture article.",
                citation_id="[E1]",
                locator="https://example.test/article",
                timestamps={"captured_at": QUESTION_ISSUED_AT},
                provenance={"source": "fixture"},
                freshness={"status": "fresh", "score": 0.85},
                relevance={"score": 0.74},
                quality={
                    "score": 0.68,
                    "reason": "Fixture provider returns evidence, but quality remains bounded by provider configuration.",
                },
                notes=["Fixture-based external evidence for provider-contract testing."],
            )
        ]
    )
    service = EvidenceBundleService(
        providers=[
            UploadedLocalArtifactEvidenceProvider(),
            fixture_provider,
            UnavailableExternalEvidenceProvider(),
        ]
    )
    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        provider_ids=["fixture_external_provider"],
    )

    assert bundle.status == "ready"
    assert bundle.retrieval_quality["status"] in {
        "external_live_unverified",
        "mixed_provider_unverified",
    }
    assert bundle.provider_snapshots[0]["provider_kind"] in {"live_external", "external_live"}
    assert bundle.source_entries[0].provenance["source"] == "fixture"
    assert "bounded" in bundle.source_entries[0].quality["reason"].lower()


def test_evidence_bundle_service_marks_sparse_local_only_bundles_as_degraded(
    simulation_data_dir,
):
    simulation_dir = simulation_data_dir / "sim-evidence-001"
    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:05:00",
            "summary": "Prepared simulation snapshot without grounding bundle.",
        },
    )

    service = EvidenceBundleService(
        providers=[UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir))]
    )
    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        provider_ids=["uploaded_local_artifacts"],
    )

    assert bundle.status == "degraded"
    assert bundle.provider_snapshots[0]["status"] == "partial"
    assert bundle.retrieval_quality["status"] == "bounded_local_only"
    assert "sparse_evidence" in bundle.uncertainty_summary["causes"]
    assert "missing_evidence" in bundle.uncertainty_summary["causes"]
    assert any(
        marker.get("code") == "missing_grounding_bundle"
        for marker in bundle.missing_evidence_markers
    )


def test_evidence_bundle_service_replaces_aliased_provider_entries_instead_of_duplicating(
    simulation_data_dir,
):
    simulation_dir = simulation_data_dir / "sim-evidence-001"
    _write_json(
        simulation_dir / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "generated_at": QUESTION_ISSUED_AT,
            "graph_id": "graph-1",
            "citation_index": {
                "source": [
                    {
                        "citation_id": "[S1]",
                        "source_id": "src-1",
                        "title": "memo.md",
                        "summary": "Uploaded memo excerpt",
                        "locator": "files/memo.md#chars=0-42",
                        "sha256": "abc123",
                    }
                ],
                "graph": [],
            },
        },
    )
    _write_json(
        simulation_dir / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:05:00",
            "summary": "Prepared simulation snapshot for evidence tests.",
        },
    )

    existing_bundle = EvidenceBundle.from_dict(
        {
            "bundle_id": "bundle-roundtrip",
            "forecast_id": QUESTION_ID,
            "title": "Aliased public bundle",
            "summary": "Round-tripped through the public API.",
            "source_entries": [
                {
                    "source_id": "src-1",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "uploaded_source",
                    "title": "memo.md",
                    "summary": "Uploaded memo excerpt",
                    "citation_id": "[S1]",
                    "locator": "files/memo.md#chars=0-42",
                    "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                    "freshness": {"status": "unknown", "score": 0.45},
                    "relevance": {"score": 0.62},
                    "quality": {"score": 0.58},
                    "provenance": {"provider": "uploaded_local_artifact"},
                },
                {
                    "source_id": "live-gap",
                    "provider_id": "external_live_unconfigured",
                    "provider_kind": "live_external",
                    "kind": "missing_evidence",
                    "title": "Live external evidence unavailable",
                    "summary": "No live external retrieval adapter is configured in this environment.",
                    "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                    "freshness": {"status": "unknown", "score": 0.0},
                    "relevance": {"score": 0.4},
                    "quality": {"score": 0.0},
                    "conflict_status": "missing",
                    "missing_evidence_markers": ["live_external_provider_unconfigured"],
                    "provenance": {"provider": "live_external"},
                },
            ],
            "provider_snapshots": [
                {
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "status": "ready",
                },
                {
                    "provider_id": "external_live_unconfigured",
                    "provider_kind": "live_external",
                    "status": "unavailable",
                },
            ],
            "missing_evidence_markers": [
                {
                    "provider_id": "external_live_unconfigured",
                    "kind": "live_external_provider_unconfigured",
                    "reason": "No live external evidence provider is configured in this environment.",
                }
            ],
            "question_ids": [QUESTION_ID],
            "prediction_entry_ids": [],
            "status": "degraded",
            "boundary_note": "Evidence remains bounded to public provider aliases.",
            "created_at": QUESTION_ISSUED_AT,
        }
    )

    service = EvidenceBundleService(
        providers=[
            UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir)),
            UnavailableExternalEvidenceProvider(),
        ]
    )
    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        existing_bundle=existing_bundle,
        bundle_id="bundle-roundtrip",
        provider_ids=["uploaded_local_artifacts", "external_live_unconfigured"],
    )

    assert len([entry for entry in bundle.source_entries if entry.citation_id == "[S1]"]) == 1
    assert len([
        provider for provider in bundle.provider_snapshots
        if provider.get("provider_id") in {"uploaded_local_artifact", "uploaded_local_artifacts"}
    ]) == 1
    assert len([
        provider for provider in bundle.provider_snapshots
        if provider.get("provider_id") in {"live_external", "external_live_unconfigured"}
    ]) == 1


def test_evidence_bundle_service_preserves_manual_gap_markers_on_provider_refresh():
    existing_bundle = EvidenceBundle.from_dict(
        {
            "bundle_id": "bundle-existing",
            "forecast_id": QUESTION_ID,
            "title": "Existing evidence",
            "summary": "Manual review attached before provider refresh.",
            "status": "partial",
            "source_entries": [
                {
                    "source_id": "manual-gap",
                    "provider_id": "manual_review",
                    "provider_kind": "manual",
                    "kind": "missing_evidence",
                    "title": "Manual missing-evidence note",
                    "summary": "Reviewer noted that no corroborating external source was attached.",
                    "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                    "freshness": {"status": "unknown", "score": 0.1},
                    "relevance": {"score": 0.4},
                    "quality": {"score": 0.0},
                    "provenance": {"provider": "manual_review"},
                    "conflict_status": "missing",
                    "missing_evidence_markers": [
                        {
                            "kind": "live_corroboration_missing",
                            "reason": "Reviewer noted the corroborating source gap.",
                        }
                    ],
                }
            ],
            "missing_evidence_markers": [
                {
                    "provider_id": "manual_review",
                    "kind": "live_corroboration_missing",
                    "reason": "Reviewer noted the corroborating source gap.",
                }
            ],
            "question_ids": [QUESTION_ID],
            "prediction_entry_ids": ["prediction-1"],
            "boundary_note": "Manual evidence gaps remain explicit during provider refresh.",
            "created_at": QUESTION_ISSUED_AT,
        }
    )

    fixture_provider = FixtureExternalEvidenceProvider(
        entries=[
            EvidenceSourceEntry(
                source_id="ext-1",
                provider_id="fixture_external_provider",
                provider_kind="external_live",
                kind="external_document",
                title="External article",
                summary="External evidence attached during refresh.",
                citation_id="[E1]",
                locator="https://example.test/article",
                timestamps={"captured_at": QUESTION_ISSUED_AT},
                provenance={"source": "fixture"},
                freshness={"status": "fresh", "score": 0.85},
                relevance={"score": 0.74},
                quality={"score": 0.68},
            )
        ]
    )
    service = EvidenceBundleService(providers=[fixture_provider])

    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        existing_bundle=existing_bundle,
        provider_ids=["fixture_external_provider"],
    )

    assert bundle.question_ids == [QUESTION_ID]
    assert bundle.prediction_entry_ids == ["prediction-1"]
    assert any(entry.provider_id == "manual_review" for entry in bundle.source_entries)
    assert any(
        marker.get("provider_id") == "manual_review"
        and marker.get("code") == "live_corroboration_missing"
        for marker in bundle.missing_evidence_markers
    )


def test_evidence_bundle_service_builds_hybrid_local_entries_with_forecast_hints(
    simulation_data_dir,
    monkeypatch,
    tmp_path,
):
    project_module = importlib.import_module("app.models.project")
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )
    project_dir = projects_dir / "proj-evidence-1"
    project_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        project_dir / "source_units.json",
        {
            "artifact_type": "source_units",
            "project_id": "proj-evidence-1",
            "source_count": 1,
            "unit_count": 1,
            "units": [
                {
                    "unit_id": "su-hybrid-0001",
                    "source_id": "src-1",
                    "stable_source_id": "src-alpha",
                    "source_sha256": "sha-1",
                    "original_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "source_order": 1,
                    "unit_order": 1,
                    "unit_type": "paragraph",
                    "char_start": 0,
                    "char_end": 80,
                    "combined_text_start": 0,
                    "combined_text_end": 80,
                    "text": "Payroll preview supported a June rate cut after weaker hiring.",
                    "metadata": {},
                    "extraction_warnings": [],
                }
            ],
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "project_id": "proj-evidence-1",
            "graph_id": "graph-1",
            "total_count": 0,
            "filtered_count": 0,
            "entity_types": [],
            "entities": [],
            "analytical_object_count": 1,
            "analytical_types": ["Claim"],
            "analytical_objects": [
                {
                    "uuid": "claim-1",
                    "name": "June cut likely",
                    "labels": ["Claim"],
                    "summary": "A June rate cut is increasingly likely after weaker payroll data.",
                    "attributes": {},
                    "related_edges": [],
                    "related_nodes": [],
                    "object_type": "Claim",
                    "layer": "analytical",
                    "provenance": {
                        "match_reason": "edge_episode",
                        "episode_ids": ["ep-1"],
                        "chunk_ids": ["chunk-0001"],
                        "source_unit_ids": ["su-hybrid-0001"],
                        "source_ids": ["src-1"],
                        "stable_source_ids": ["src-alpha"],
                        "citation_count": 1,
                        "citations": [
                            {
                                "unit_id": "su-hybrid-0001",
                                "source_id": "src-1",
                                "stable_source_id": "src-alpha",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "source_order": 1,
                                "unit_order": 1,
                                "char_start": 0,
                                "char_end": 80,
                                "combined_text_start": 0,
                                "combined_text_end": 80,
                                "text_excerpt": "Payroll preview supported a June rate cut after weaker hiring.",
                                "reason": "edge_episode",
                            }
                        ],
                    },
                }
            ],
            "graph_node_count": 1,
            "graph_edge_count": 0,
            "object_count": 1,
            "citation_coverage": {
                "source_unit_backed_node_count": 1,
                "source_unit_backed_edge_count": 0,
                "edge_episode_link_count": 1,
            },
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "project_id": "proj-evidence-1",
            "graph_id": "graph-1",
            "chunk_count": 1,
            "chunking_strategy": "semantic_source_units",
            "graph_counts": {
                "node_count": 1,
                "edge_count": 0,
                "actor_count": 0,
                "analytical_object_count": 1,
                "entity_types": ["Claim"],
                "analytical_types": ["Claim"],
            },
            "citation_coverage": {
                "source_unit_backed_node_count": 1,
                "source_unit_backed_edge_count": 0,
                "edge_episode_link_count": 1,
            },
        },
    )

    retriever_module = importlib.import_module("app.services.hybrid_evidence_retriever")
    index_module = importlib.import_module("app.services.local_evidence_index")
    provider = UploadedLocalArtifactEvidenceProvider(
        str(simulation_data_dir),
        hybrid_retriever=retriever_module.HybridEvidenceRetriever(
            embedding_client=type(
                "_FakeEmbeddingClient",
                (),
                {
                    "embed_text": staticmethod(lambda text, normalize=True: [1.0, 1.0, 0.0]),
                    "embed_texts": staticmethod(
                        lambda texts, normalize=True: [[1.0, 1.0, 0.0] for _ in texts]
                    ),
                },
            )(),
            evidence_index=index_module.LocalEvidenceIndex(
                index_path=str(tmp_path / "local_evidence.sqlite3")
            ),
        ),
    )
    service = EvidenceBundleService(providers=[provider])

    bundle = service.build_bundle(
        question=ForecastQuestion.from_dict(_question_payload()),
        provider_ids=["uploaded_local_artifacts"],
    )

    assert bundle.status == "ready"
    assert bundle.provider_snapshots[0]["status"] == "ready"
    assert bundle.source_entries
    assert bundle.source_entries[0].metadata["forecast_hints"]
    assert bundle.source_entries[0].citation_id.startswith("[")
    assert bundle.source_entries[0].provenance["source_unit_ids"] == ["su-hybrid-0001"]
    assert bundle.citation_index["source"][0]["citation_id"] == bundle.source_entries[0].citation_id
