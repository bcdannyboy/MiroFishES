from __future__ import annotations

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
