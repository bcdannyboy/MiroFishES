"""
Forecast-facing grounding bundle builder.

The bundle is intentionally bounded:
- uploaded-source provenance comes only from persisted project artifacts,
- graph provenance comes only from the stored graph-build summary,
- repo-local code analysis is explicit when present and explicit when absent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models.grounding import (
    BUNDLE_BOUNDARY_NOTE,
    GROUNDING_GENERATOR_VERSION,
    GROUNDING_SCHEMA_VERSION,
    build_default_code_analysis_summary,
    build_grounding_summary,
)
from ..models.project import ProjectManager


class GroundingBundleBuilder:
    """Compose one deterministic upstream grounding bundle per simulation."""

    GROUNDING_BUNDLE_FILENAME = "grounding_bundle.json"

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def build_bundle(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build one bounded grounding bundle from persisted project artifacts."""
        raw_source_manifest = ProjectManager.get_source_manifest(project_id)
        raw_graph_summary = ProjectManager.get_graph_build_summary(project_id)
        warnings: List[str] = []
        source_artifacts: Dict[str, str] = {}

        source_manifest = self._validate_source_manifest(
            raw_source_manifest,
            expected_project_id=project_id,
            warnings=warnings,
        )
        graph_summary = self._validate_graph_summary(
            raw_graph_summary,
            expected_project_id=project_id,
            expected_graph_id=graph_id,
            warnings=warnings,
        )

        source_citations: List[Dict[str, Any]] = []
        graph_citations: List[Dict[str, Any]] = []
        code_citations: List[Dict[str, Any]] = []
        evidence_items: List[Dict[str, Any]] = []

        if source_manifest:
            source_artifacts["source_manifest"] = "source_manifest.json"
            source_citations = self._build_source_citations(source_manifest)
            evidence_items.extend(
                self._build_source_evidence_items(source_citations)
            )
        elif raw_source_manifest is None:
            warnings.append("missing_source_manifest")

        if graph_summary:
            source_artifacts["graph_build_summary"] = "graph_build_summary.json"
            graph_citations = self._build_graph_citations(graph_summary, graph_id=graph_id)
            evidence_items.extend(self._build_graph_evidence_items(graph_citations))
        elif raw_graph_summary is None:
            warnings.append("missing_graph_build_summary")

        code_analysis_summary = build_default_code_analysis_summary()

        status = "unavailable"
        if source_manifest and graph_summary and evidence_items:
            status = "ready"
        elif source_manifest or graph_summary:
            status = "partial"

        citation_counts = {
            "source": len(source_citations),
            "graph": len(graph_citations),
            "code": len(code_citations),
        }

        bundle = {
            "artifact_type": "grounding_bundle",
            "schema_version": GROUNDING_SCHEMA_VERSION,
            "generator_version": GROUNDING_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id or (graph_summary or {}).get("graph_id"),
            "generated_at": datetime.now().isoformat(),
            "status": status,
            "boundary_note": BUNDLE_BOUNDARY_NOTE,
            "warnings": warnings,
            "source_artifacts": source_artifacts,
            "source_summary": self._build_source_summary(source_manifest),
            "graph_summary": self._build_graph_summary(
                graph_summary,
                graph_id=graph_id,
            ),
            "code_analysis_summary": code_analysis_summary,
            "citation_index": {
                "source": source_citations,
                "graph": graph_citations,
                "code": code_citations,
            },
            "citation_counts": citation_counts,
            "evidence_items": evidence_items[:5],
            "evidence_count": len(evidence_items[:5]),
        }
        return bundle

    def build_grounding_bundle(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible alias for the explicit grounding contract wording."""
        return self.build_bundle(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
        )

    def build_summary(self, bundle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Return the compact grounding summary attached to other artifacts."""
        return build_grounding_summary(
            bundle,
            artifact_filename=self.GROUNDING_BUNDLE_FILENAME,
        )

    def build_grounding_summary(
        self, bundle: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Backward-compatible alias for summary generation."""
        return self.build_summary(bundle)

    def load_bundle(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Load a persisted simulation grounding bundle when present."""
        bundle_path = os.path.join(
            self.simulation_data_dir,
            simulation_id,
            self.GROUNDING_BUNDLE_FILENAME,
        )
        if not os.path.exists(bundle_path):
            return None
        with open(bundle_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _build_source_citations(self, source_manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create stable citations for uploaded-source evidence."""
        citations: List[Dict[str, Any]] = []
        for index, source in enumerate(source_manifest.get("sources", [])[:4], start=1):
            if not isinstance(source, dict):
                continue
            start = source.get("combined_text_start")
            end = source.get("combined_text_end")
            locator = source.get("relative_path") or source.get("saved_filename")
            if locator and start is not None and end is not None:
                locator = f"{locator}#chars={start}-{end}"
            citations.append(
                {
                    "citation_id": f"[S{index}]",
                    "kind": "source",
                    "source_id": source.get("source_id"),
                    "title": source.get("original_filename"),
                    "locator": locator,
                    "summary": source.get("excerpt"),
                    "sha256": source.get("sha256"),
                }
            )
        return citations

    def _build_graph_citations(
        self,
        graph_summary: Dict[str, Any],
        *,
        graph_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Create stable citations for graph-build provenance."""
        if not isinstance(graph_summary, dict):
            return []
        graph_counts = graph_summary.get("graph_counts", {}) or {}
        summary = (
            graph_summary.get("ontology_summary", {}) or {}
        ).get("analysis_summary") or (
            f"Graph {graph_id or graph_summary.get('graph_id')}: "
            f"{graph_counts.get('node_count', 0)} nodes, {graph_counts.get('edge_count', 0)} edges."
        )
        return [
            {
                "citation_id": "[G1]",
                "kind": "graph",
                "title": "Graph build summary",
                "locator": f"graph:{graph_id or graph_summary.get('graph_id')}",
                "summary": summary,
            }
        ]

    def _build_source_evidence_items(
        self,
        citations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Turn uploaded-source citations into bounded evidence items."""
        items: List[Dict[str, Any]] = []
        for citation in citations:
            items.append(
                {
                    "citation_id": citation.get("citation_id"),
                    "kind": "source",
                    "title": citation.get("title"),
                    "summary": citation.get("summary"),
                    "locator": citation.get("locator"),
                    "support_label": "Uploaded source excerpt",
                }
            )
        return items

    def _build_graph_evidence_items(
        self,
        citations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Turn graph provenance citations into bounded evidence items."""
        items: List[Dict[str, Any]] = []
        for citation in citations:
            items.append(
                {
                    "citation_id": citation.get("citation_id"),
                    "kind": "graph",
                    "title": citation.get("title"),
                    "summary": citation.get("summary"),
                    "locator": citation.get("locator"),
                    "support_label": "Persisted graph-build provenance",
                }
            )
        return items

    def _build_source_summary(
        self,
        source_manifest: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Summarize uploaded-source provenance without inlining the full manifest."""
        if not source_manifest:
            return {
                "status": "unavailable",
                "source_count": 0,
            }
        return {
            "status": "ready",
            "source_count": source_manifest.get("source_count", 0),
            "simulation_requirement": source_manifest.get("simulation_requirement"),
        }

    def _build_graph_summary(
        self,
        graph_summary: Optional[Dict[str, Any]],
        *,
        graph_id: Optional[str],
    ) -> Dict[str, Any]:
        """Summarize graph provenance without inlining the full graph artifact."""
        if not graph_summary:
            return {
                "status": "unavailable",
                "graph_id": graph_id,
            }
        graph_counts = graph_summary.get("graph_counts", {}) or {}
        return {
            "status": "ready",
            "graph_id": graph_summary.get("graph_id", graph_id),
            "chunk_count": graph_summary.get("chunk_count"),
            "node_count": graph_counts.get("node_count"),
            "edge_count": graph_counts.get("edge_count"),
            "analysis_summary": (
                graph_summary.get("ontology_summary", {}) or {}
            ).get("analysis_summary"),
        }

    def _validate_source_manifest(
        self,
        source_manifest: Optional[Dict[str, Any]],
        *,
        expected_project_id: str,
        warnings: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Reject source manifests that do not actually belong to the requested project."""
        if not isinstance(source_manifest, dict):
            return None
        if source_manifest.get("project_id") != expected_project_id:
            warnings.append("source_manifest_project_id_mismatch")
            return None
        return source_manifest

    def _validate_graph_summary(
        self,
        graph_summary: Optional[Dict[str, Any]],
        *,
        expected_project_id: str,
        expected_graph_id: Optional[str],
        warnings: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Reject graph summaries that no longer match the active simulation scope."""
        if not isinstance(graph_summary, dict):
            return None
        if graph_summary.get("project_id") != expected_project_id:
            warnings.append("graph_build_summary_project_id_mismatch")
            return None
        summary_graph_id = graph_summary.get("graph_id")
        if expected_graph_id and summary_graph_id and summary_graph_id != expected_graph_id:
            warnings.append("graph_build_summary_graph_id_mismatch")
            return None
        return graph_summary
