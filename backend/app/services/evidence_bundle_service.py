"""
Evidence bundle acquisition and normalization services.

This layer broadens forecast evidence handling beyond the original local
grounding artifact while keeping bounded semantics explicit. Local uploaded
artifacts remain the only exercised provider in this environment by default;
live external providers are pluggable and degrade to explicit unavailability
rather than implied coverage.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from ..config import Config
from ..models.forecasting import EvidenceBundle, EvidenceSourceEntry, ForecastQuestion
from .grounding_bundle_builder import GroundingBundleBuilder
from .hybrid_evidence_retriever import HybridEvidenceRetriever


class UploadedLocalArtifactEvidenceProvider:
    """Normalize persisted uploaded/local artifacts into bundle entries."""

    provider_id = "uploaded_local_artifact"
    provider_kind = "uploaded_local_artifact"
    label = "Uploaded and stored local artifacts"
    is_live = False

    def __init__(
        self,
        simulation_data_dir: Optional[str] = None,
        hybrid_retriever: Optional[HybridEvidenceRetriever] = None,
    ) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.get_simulation_data_dir()
        self.grounding_builder = GroundingBundleBuilder(
            simulation_data_dir=self.simulation_data_dir
        )
        self._hybrid_retriever = hybrid_retriever

    @property
    def hybrid_retriever(self) -> HybridEvidenceRetriever:
        if self._hybrid_retriever is None:
            self._hybrid_retriever = HybridEvidenceRetriever()
        return self._hybrid_retriever

    def collect(
        self,
        *,
        question: ForecastQuestion,
        existing_bundle: Optional[EvidenceBundle] = None,
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        simulation_id = question.primary_simulation_id
        project_id = getattr(question, "project_id", None)
        notes = [
            "Local artifact evidence is bounded to persisted project and simulation files.",
        ]
        if not simulation_id and not project_id:
            return {
                "provider_snapshot": {
                    "provider_id": self.provider_id,
                    "provider_kind": self.provider_kind,
                    "label": self.label,
                    "is_live": self.is_live,
                    "status": "unavailable",
                    "retrieval_quality": "bounded_local_artifacts",
                    "collected_at": now,
                    "entry_count": 0,
                    "notes": notes
                    + [
                        "Neither project_id nor primary_simulation_id is linked to this forecast question, so local artifact evidence could not be collected."
                    ],
                },
                "entries": [],
                "missing_evidence_markers": [
                    {
                        "marker_id": f"{self.provider_id}-missing-simulation-link",
                        "provider_id": self.provider_id,
                        "provider_kind": self.provider_kind,
                        "kind": "missing_local_artifact_link",
                        "reason": "No project_id or primary_simulation_id is linked to this forecast question.",
                        "recorded_at": now,
                    }
                ],
            }

        entries: List[EvidenceSourceEntry] = []
        missing_markers: List[Dict[str, Any]] = []
        grounding_bundle = (
            self.grounding_builder.load_bundle(simulation_id)
            if simulation_id
            else None
        )
        if not project_id and isinstance(grounding_bundle, dict):
            project_id = grounding_bundle.get("project_id")

        hybrid_hits = []
        if project_id:
            try:
                retrieval = self.hybrid_retriever.retrieve(
                    project_id=project_id,
                    query=question.question_text or question.title,
                    question_type=question.question_type,
                    issue_timestamp=question.issue_timestamp,
                    limit=6,
                )
                hybrid_hits = list(retrieval.hits)
                missing_markers.extend(retrieval.missing_evidence_markers)
                notes.append(
                    "Hybrid local retrieval searched embedded source units plus graph-native analytical objects."
                )
                notes.append(
                    f"Hybrid retrieval indexed {retrieval.index_stats.get('record_count', 0)} local evidence records."
                )
                entries.extend(
                    self._normalize_hybrid_entries(
                        retrieval_hits=hybrid_hits,
                        project_id=project_id,
                        simulation_id=simulation_id,
                    )
                )
            except Exception as exc:
                notes.append(
                    f"Hybrid local retrieval was unavailable and fell back to persisted grounding artifacts: {exc}"
                )
                missing_markers.append(
                    {
                        "marker_id": f"{self.provider_id}-hybrid-retrieval-unavailable",
                        "provider_id": self.provider_id,
                        "provider_kind": self.provider_kind,
                        "kind": "hybrid_retrieval_unavailable",
                        "reason": str(exc),
                        "recorded_at": now,
                    }
                )

        if not entries and grounding_bundle:
            missing_markers = [
                marker
                for marker in missing_markers
                if marker.get("kind")
                not in {
                    "missing_source_units",
                    "missing_graph_entity_index",
                    "no_ranked_local_evidence",
                }
            ]
            entries.extend(
                self._normalize_grounding_bundle_entries(
                    simulation_id=simulation_id,
                    grounding_bundle=grounding_bundle,
                )
            )
        elif simulation_id and not grounding_bundle and not entries:
            missing_markers.append(
                {
                    "marker_id": f"{self.provider_id}-missing-grounding-bundle",
                    "provider_id": self.provider_id,
                    "provider_kind": self.provider_kind,
                    "kind": "missing_grounding_bundle",
                    "reason": "No grounding_bundle.json is available for the linked simulation.",
                    "recorded_at": now,
                }
            )

        prepared_snapshot = self._load_simulation_json(
            simulation_id,
            "prepared_snapshot.json",
        ) if simulation_id else None
        if prepared_snapshot:
            entries.append(
                EvidenceSourceEntry(
                    source_id=f"{simulation_id}-prepared-snapshot",
                    provider_id=self.provider_id,
                    provider_kind=self.provider_kind,
                    kind="prepared_snapshot",
                    title="Prepared simulation snapshot",
                    summary=(
                        prepared_snapshot.get("summary")
                        or "Prepared simulation snapshot persisted for stored-run handoff."
                    ),
                    locator=f"{simulation_id}/prepared_snapshot.json",
                    timestamps={
                        "captured_at": prepared_snapshot.get("generated_at")
                        or prepared_snapshot.get("created_at")
                        or now
                    },
                    provenance={
                        "artifact_type": prepared_snapshot.get(
                            "artifact_type", "prepared_snapshot"
                        ),
                        "simulation_id": simulation_id,
                        "relative_path": "prepared_snapshot.json",
                    },
                    freshness={
                        "status": "unknown",
                        "score": 0.45,
                        "reason": "Prepared snapshots describe stored artifact state but not live-world recency.",
                    },
                    relevance={
                        "score": 0.6,
                        "reason": "Prepared simulation state is scoped to the linked simulation for this forecast question.",
                    },
                    quality={
                        "score": 0.52,
                        "reason": "Prepared snapshots preserve artifact lineage but do not by themselves validate real-world coverage.",
                        "heuristic": "artifact_presence",
                    },
                    notes=[
                        "Prepared snapshots are operational artifacts, not direct resolution evidence.",
                    ],
                )
            )

        status = "ready" if entries else "unavailable"
        if entries and missing_markers:
            status = "partial"

        return {
            "provider_snapshot": {
                "provider_id": self.provider_id,
                "provider_kind": self.provider_kind,
                "label": self.label,
                "is_live": self.is_live,
                "status": status,
                "retrieval_quality": "bounded_local_artifacts",
                "collected_at": now,
                "simulation_id": simulation_id,
                "project_id": project_id,
                "entry_count": len(entries),
                "notes": notes,
            },
            "entries": entries,
            "missing_evidence_markers": missing_markers,
        }

    def _normalize_hybrid_entries(
        self,
        *,
        retrieval_hits: List[Dict[str, Any]],
        project_id: str,
        simulation_id: Optional[str],
    ) -> List[EvidenceSourceEntry]:
        normalized_hits = sorted(
            retrieval_hits,
            key=lambda item: (
                0 if item.get("record_type") == "source_unit" else 1,
                -float(item.get("score", 0.0)),
                str(item.get("record_id") or ""),
            ),
        )
        entries: List[EvidenceSourceEntry] = []
        for hit in normalized_hits:
            provenance = dict(hit.get("provenance") or {})
            provenance.setdefault("project_id", project_id)
            if simulation_id:
                provenance.setdefault("simulation_id", simulation_id)
            provenance.setdefault(
                "retrieval",
                {
                    "record_type": hit.get("record_type"),
                    "score": hit.get("score"),
                    "score_components": hit.get("score_components", {}),
                },
            )
            metadata = {
                "forecast_hints": list(hit.get("forecast_hints") or []),
                "hybrid_retrieval": {
                    "record_id": hit.get("record_id"),
                    "record_type": hit.get("record_type"),
                    "score": hit.get("score"),
                    "score_components": hit.get("score_components", {}),
                    "citations": list(hit.get("citations") or []),
                },
            }
            entries.append(
                EvidenceSourceEntry(
                    source_id=str(hit.get("record_id") or ""),
                    provider_id=self.provider_id,
                    provider_kind=self.provider_kind,
                    kind=(
                        "uploaded_source"
                        if hit.get("record_type") == "source_unit"
                        else "graph_provenance"
                    ),
                    title=hit.get("title") or "Hybrid evidence",
                    summary=hit.get("summary") or "",
                    citation_id=hit.get("citation_id"),
                    locator=hit.get("locator"),
                    timestamps={},
                    provenance=provenance,
                    freshness=hit.get("freshness", {}),
                    relevance=hit.get("relevance", {}),
                    quality=hit.get("quality", {}),
                    conflict_status=hit.get("conflict_status", "none"),
                    conflict_markers=hit.get("conflict_markers", []),
                    missing_evidence_markers=[],
                    notes=[],
                    metadata=metadata,
                )
            )
        return entries

    def _normalize_grounding_bundle_entries(
        self,
        *,
        simulation_id: str,
        grounding_bundle: Dict[str, Any],
    ) -> List[EvidenceSourceEntry]:
        entries: List[EvidenceSourceEntry] = []
        captured_at = (
            grounding_bundle.get("generated_at") or datetime.now().isoformat()
        )
        citation_index = grounding_bundle.get("citation_index") or {}
        for citation in citation_index.get("source", []) or []:
            if not isinstance(citation, dict):
                continue
            entries.append(
                EvidenceSourceEntry(
                    source_id=citation.get("source_id")
                    or citation.get("citation_id")
                    or f"{simulation_id}-source-{len(entries) + 1}",
                    provider_id=self.provider_id,
                    provider_kind=self.provider_kind,
                    kind="uploaded_source",
                    title=citation.get("title") or "Uploaded source excerpt",
                    summary=citation.get("summary") or "",
                    citation_id=citation.get("citation_id"),
                    locator=citation.get("locator"),
                    timestamps={"captured_at": captured_at},
                    provenance={
                        "artifact_type": "grounding_bundle",
                        "simulation_id": simulation_id,
                        "sha256": citation.get("sha256"),
                    },
                    freshness={
                        "status": "unknown",
                        "score": 0.45,
                        "reason": "Uploaded local sources preserve bounded provenance but do not expose live retrieval recency.",
                    },
                    relevance={
                        "score": 0.62,
                        "reason": "Uploaded sources were attached to the linked project/simulation context.",
                    },
                    quality={
                        "score": 0.58,
                        "reason": "Uploaded excerpts have direct provenance but still represent bounded local evidence only.",
                        "heuristic": "local_artifact_completeness",
                    },
                )
            )
        for citation in citation_index.get("graph", []) or []:
            if not isinstance(citation, dict):
                continue
            entries.append(
                EvidenceSourceEntry(
                    source_id=citation.get("citation_id")
                    or f"{simulation_id}-graph-{len(entries) + 1}",
                    provider_id=self.provider_id,
                    provider_kind=self.provider_kind,
                    kind="graph_summary",
                    title=citation.get("title") or "Graph build summary",
                    summary=citation.get("summary") or "",
                    citation_id=citation.get("citation_id"),
                    locator=citation.get("locator"),
                    timestamps={"captured_at": captured_at},
                    provenance={
                        "artifact_type": "grounding_bundle",
                        "simulation_id": simulation_id,
                        "graph_id": grounding_bundle.get("graph_id"),
                    },
                    freshness={
                        "status": "timeless",
                        "score": 0.5,
                        "reason": "Graph-build provenance is derived from stored project artifacts rather than live retrieval.",
                    },
                    relevance={
                        "score": 0.57,
                        "reason": "Graph provenance describes structured context for the linked simulation, not direct outcome truth.",
                    },
                    quality={
                        "score": 0.54,
                        "reason": "Graph summaries preserve derivation lineage but can omit source-level nuance.",
                        "heuristic": "derived_graph_provenance",
                    },
                )
            )
        return entries

    def _load_simulation_json(
        self,
        simulation_id: str,
        filename: str,
    ) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.simulation_data_dir, simulation_id, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)


class UnavailableExternalEvidenceProvider:
    """Graceful external-live placeholder when no provider is configured."""

    provider_id = "live_external"
    provider_kind = "live_external"
    label = "Live external evidence provider"
    is_live = True

    def collect(
        self,
        *,
        question: ForecastQuestion,
        existing_bundle: Optional[EvidenceBundle] = None,
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "provider_snapshot": {
                "provider_id": self.provider_id,
                "provider_kind": self.provider_kind,
                "label": self.label,
                "is_live": self.is_live,
                "status": "unavailable",
                "retrieval_quality": "not_configured",
                "collected_at": now,
                "entry_count": 0,
                "notes": [
                    "No live external evidence provider is configured in this environment.",
                    "The architecture is pluggable, but retrieval quality does not improve until a provider actually returns entries.",
                ],
            },
            "entries": [
                {
                    "entry_id": "live-external-gap",
                    "source_type": "missing_evidence",
                    "provider_id": self.provider_id,
                    "provider_kind": self.provider_kind,
                    "title": "Live external evidence unavailable",
                    "summary": "No live external retrieval adapter is configured in this environment.",
                    "captured_at": now,
                    "freshness": {"status": "unknown"},
                    "relevance": {"score": 0.4},
                    "provenance": {
                        "provider": self.provider_id,
                        "adapter_status": "unconfigured",
                    },
                    "quality_score": 0.0,
                    "conflict_status": "missing",
                    "missing_evidence_markers": ["live_external_provider_unconfigured"],
                }
            ],
            "missing_evidence_markers": [
                {
                    "marker_id": "live_external_provider_unconfigured",
                    "provider_id": self.provider_id,
                    "provider_kind": self.provider_kind,
                    "kind": "live_external_provider_unconfigured",
                    "reason": "No live external evidence provider is configured in this environment.",
                    "recorded_at": now,
                }
            ],
        }


class FixtureExternalEvidenceProvider:
    """Test-only external provider that returns injected entries."""

    provider_kind = "live_external"
    label = "Fixture external evidence provider"
    is_live = True

    def __init__(
        self,
        *,
        provider_id: str = "fixture_external_provider",
        status: str = "ready",
        entries: Optional[Iterable[Dict[str, Any] | EvidenceSourceEntry]] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        self.provider_id = provider_id
        self.status = status
        self.entries = list(entries or [])
        self.notes = list(notes or [])

    def collect(
        self,
        *,
        question: ForecastQuestion,
        existing_bundle: Optional[EvidenceBundle] = None,
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        normalized_entries = [
            item if isinstance(item, EvidenceSourceEntry) else EvidenceSourceEntry.from_dict(item)
            for item in self.entries
        ]
        return {
            "provider_snapshot": {
                "provider_id": self.provider_id,
                "provider_kind": self.provider_kind,
                "label": self.label,
                "is_live": self.is_live,
                "status": self.status,
                "collected_at": now,
                "entry_count": len(normalized_entries),
                "notes": list(self.notes),
            },
            "entries": normalized_entries,
            "missing_evidence_markers": [],
        }


class EvidenceBundleService:
    """Compose normalized evidence bundles from one or more providers."""

    def __init__(self, providers: Optional[Iterable[Any]] = None) -> None:
        configured_providers = list(
            providers
            or [
                UploadedLocalArtifactEvidenceProvider(),
                UnavailableExternalEvidenceProvider(),
            ]
        )
        self.providers = {provider.provider_id: provider for provider in configured_providers}

    @staticmethod
    def _normalize_provider_id(provider_id: Optional[str]) -> Optional[str]:
        provider_aliases = {
            "uploaded_local": "uploaded_local_artifact",
            "uploaded_local_artifact": "uploaded_local_artifact",
            "uploaded_local_artifacts": "uploaded_local_artifact",
            "external_live": "live_external",
            "external_live_unconfigured": "live_external",
            "live_external": "live_external",
        }
        return provider_aliases.get(provider_id, provider_id)

    def list_provider_capabilities(self) -> List[Dict[str, Any]]:
        capabilities: List[Dict[str, Any]] = []
        for provider in self.providers.values():
            capabilities.append(
                {
                    "provider_id": provider.provider_id,
                    "provider_kind": provider.provider_kind,
                    "label": provider.label,
                    "is_live": provider.is_live,
                }
            )
        return capabilities

    def build_bundle(
        self,
        *,
        question: ForecastQuestion,
        existing_bundle: Optional[EvidenceBundle] = None,
        bundle_id: Optional[str] = None,
        provider_ids: Optional[List[str]] = None,
    ) -> EvidenceBundle:
        selected_providers = self._select_providers(provider_ids)
        preserved_entries = self._preserve_unselected_entries(
            existing_bundle,
            selected_provider_ids={provider.provider_id for provider in selected_providers},
        )
        preserved_provider_snapshots = self._preserve_unselected_provider_snapshots(
            existing_bundle,
            selected_provider_ids={provider.provider_id for provider in selected_providers},
        )
        preserved_missing_markers = self._preserve_unselected_missing_markers(
            existing_bundle,
            selected_provider_ids={provider.provider_id for provider in selected_providers},
        )

        collected_entries = list(preserved_entries)
        provider_snapshots = list(preserved_provider_snapshots)
        missing_markers = list(preserved_missing_markers)
        for provider in selected_providers:
            collected = provider.collect(question=question, existing_bundle=existing_bundle)
            provider_snapshot = dict(collected.get("provider_snapshot") or {})
            provider_snapshot.setdefault("provider_id", provider.provider_id)
            provider_snapshot.setdefault("provider_kind", provider.provider_kind)
            provider_snapshot.setdefault("label", provider.label)
            provider_snapshot.setdefault("is_live", provider.is_live)
            provider_snapshots.append(provider_snapshot)
            for entry in collected.get("entries", []):
                normalized = (
                    entry
                    if isinstance(entry, EvidenceSourceEntry)
                    else EvidenceSourceEntry.from_dict(entry)
                )
                collected_entries.append(normalized)
            for marker in collected.get("missing_evidence_markers", []):
                if isinstance(marker, dict):
                    missing_markers.append(dict(marker))

        if existing_bundle is not None:
            question_ids = sorted(
                set(existing_bundle.question_ids + [question.forecast_id])
            )
            prediction_entry_ids = list(existing_bundle.prediction_entry_ids)
            title = existing_bundle.title
            summary = existing_bundle.summary
            boundary_note = existing_bundle.boundary_note
        else:
            question_ids = [question.forecast_id]
            prediction_entry_ids = []
            title = question.title or "Forecast evidence bundle"
            summary = (
                "Bounded forecast evidence assembled from configured providers."
            )
            boundary_note = (
                "Evidence remains bounded to the providers listed in this bundle. Missing, stale, sparse, or conflicting evidence stays explicit."
            )

        status = self._derive_bundle_status(collected_entries, provider_snapshots)
        return EvidenceBundle(
            bundle_id=bundle_id or (existing_bundle.bundle_id if existing_bundle else f"{question.forecast_id}-bundle"),
            forecast_id=question.forecast_id,
            title=title,
            summary=summary,
            source_entries=collected_entries,
            provider_snapshots=provider_snapshots,
            missing_evidence_markers=missing_markers,
            question_ids=question_ids,
            prediction_entry_ids=prediction_entry_ids,
            status=status,
            boundary_note=boundary_note,
            created_at=existing_bundle.created_at if existing_bundle else question.issue_timestamp,
        )

    def _select_providers(self, provider_ids: Optional[List[str]]) -> List[Any]:
        if not provider_ids:
            return list(self.providers.values())
        provider_aliases = {
            "uploaded_local_artifacts": "uploaded_local_artifact",
            "external_live_unconfigured": "live_external",
        }
        selected: List[Any] = []
        for provider_id in provider_ids:
            provider = self.providers.get(provider_id) or self.providers.get(
                provider_aliases.get(provider_id, "")
            )
            if provider is None:
                raise ValueError(f"Unknown evidence provider: {provider_id}")
            selected.append(provider)
        return selected

    @staticmethod
    def _preserve_unselected_entries(
        existing_bundle: Optional[EvidenceBundle],
        *,
        selected_provider_ids: set[str],
    ) -> List[EvidenceSourceEntry]:
        if existing_bundle is None:
            return []
        normalized_selected_ids = {
            EvidenceBundleService._normalize_provider_id(provider_id)
            for provider_id in selected_provider_ids
        }
        return [
            entry
            for entry in existing_bundle.source_entries
            if EvidenceBundleService._normalize_provider_id(entry.provider_id)
            not in normalized_selected_ids
        ]

    @staticmethod
    def _preserve_unselected_provider_snapshots(
        existing_bundle: Optional[EvidenceBundle],
        *,
        selected_provider_ids: set[str],
    ) -> List[Dict[str, Any]]:
        if existing_bundle is None:
            return []
        normalized_selected_ids = {
            EvidenceBundleService._normalize_provider_id(provider_id)
            for provider_id in selected_provider_ids
        }
        return [
            dict(snapshot)
            for snapshot in existing_bundle.provider_snapshots
            if EvidenceBundleService._normalize_provider_id(snapshot.get("provider_id"))
            not in normalized_selected_ids
        ]

    @staticmethod
    def _preserve_unselected_missing_markers(
        existing_bundle: Optional[EvidenceBundle],
        *,
        selected_provider_ids: set[str],
    ) -> List[Any]:
        if existing_bundle is None:
            return []
        normalized_selected_ids = {
            EvidenceBundleService._normalize_provider_id(provider_id)
            for provider_id in selected_provider_ids
        }
        preserved: List[Any] = []
        for marker in existing_bundle.missing_evidence_markers:
            if isinstance(marker, dict):
                if (
                    EvidenceBundleService._normalize_provider_id(marker.get("provider_id"))
                    not in normalized_selected_ids
                ):
                    preserved.append(dict(marker))
            else:
                preserved.append(marker)
        return preserved

    @staticmethod
    def _derive_bundle_status(
        entries: List[EvidenceSourceEntry],
        provider_snapshots: List[Dict[str, Any]],
    ) -> str:
        if not entries:
            return "unavailable"
        if any(snapshot.get("status") == "unavailable" for snapshot in provider_snapshots):
            return "degraded"
        if any(snapshot.get("status") == "partial" for snapshot in provider_snapshots):
            return "degraded"
        return "ready"
