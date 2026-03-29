"""
Upstream grounding artifact helpers.

These helpers keep the repo's grounding contract explicit and compact:
- uploaded-source provenance is bounded to project-local files,
- graph provenance is bounded to one persisted graph build summary,
- repo-local code analysis is optional and never implied when absent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


GROUNDING_SCHEMA_VERSION = "forecast.grounding.v1"
GROUNDING_GENERATOR_VERSION = "forecast.grounding.generator.v1"
SOURCE_BOUNDARY_NOTE = (
    "Uploaded project sources only; this artifact does not claim live-web coverage."
)
BUNDLE_BOUNDARY_NOTE = (
    "Uploaded project sources only; graph facts come from the stored graph build summary, "
    "and repo-local code analysis appears only when an explicit code-analysis artifact is attached."
)
CODE_ANALYSIS_BOUNDARY_NOTE = (
    "Repo-local code analysis is optional in this phase. Missing code-analysis artifacts do not imply comprehensive coverage."
)


def build_default_code_analysis_summary() -> Dict[str, Any]:
    """Return the explicit default when no repo-local code analysis is attached."""
    return {
        "status": "not_requested",
        "boundary_note": CODE_ANALYSIS_BOUNDARY_NOTE,
        "citation_count": 0,
    }


def build_grounding_summary(
    bundle: Optional[Dict[str, Any]],
    *,
    artifact_filename: str = "grounding_bundle.json",
) -> Dict[str, Any]:
    """Create the compact grounding summary attached to prepare/report surfaces."""
    payload = bundle or {}
    citation_counts = payload.get("citation_counts")
    if not isinstance(citation_counts, dict):
        citation_counts = {
            "source": len(payload.get("citation_index", {}).get("source", []) or []),
            "graph": len(payload.get("citation_index", {}).get("graph", []) or []),
            "code": len(payload.get("citation_index", {}).get("code", []) or []),
        }

    evidence_items = payload.get("evidence_items")
    if not isinstance(evidence_items, list):
        evidence_items = []

    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    return {
        "status": payload.get("status", "unavailable"),
        "artifact_filename": artifact_filename,
        "evidence_count": payload.get("evidence_count", len(evidence_items)),
        "citation_counts": citation_counts,
        "boundary_note": payload.get("boundary_note", BUNDLE_BOUNDARY_NOTE),
        "warnings": warnings,
    }


def build_grounding_context(bundle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Expose one report-safe upstream grounding block."""
    payload = bundle or {}
    summary = build_grounding_summary(payload)
    return {
        **summary,
        "source_artifacts": payload.get("source_artifacts", {}),
        "source_summary": payload.get("source_summary", {}),
        "graph_summary": payload.get("graph_summary", {}),
        "code_analysis_summary": payload.get(
            "code_analysis_summary",
            build_default_code_analysis_summary(),
        ),
        "evidence_items": _compact_evidence_items(payload.get("evidence_items")),
    }


def _compact_evidence_items(items: Any, *, limit: int = 5) -> List[Dict[str, Any]]:
    """Keep evidence bounded while preserving stable citations and locators."""
    if not isinstance(items, list):
        return []

    compact_items: List[Dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        compact_items.append(
            {
                "citation_id": item.get("citation_id"),
                "kind": item.get("kind"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "locator": item.get("locator"),
                "support_label": item.get("support_label"),
            }
        )
    return compact_items
