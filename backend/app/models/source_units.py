"""Helpers for deterministic source-unit artifacts and stable provenance ids."""

from __future__ import annotations

from typing import Any, Dict, List

from .grounding import (
    GROUNDING_GENERATOR_VERSION,
    GROUNDING_SCHEMA_VERSION,
    SOURCE_BOUNDARY_NOTE,
)


SOURCE_UNITS_ARTIFACT_TYPE = "source_units"


def build_stable_source_id(file_sha256: str) -> str:
    """Build one stable source id from the persisted file hash."""
    return f"src-{(file_sha256 or 'unknown')[:12]}"


def build_source_unit_id(stable_source_id: str, unit_order: int) -> str:
    """Build one stable source-unit id from the stable source id and unit order."""
    stable_suffix = (stable_source_id or "src-unknown").removeprefix("src-")
    return f"su-{stable_suffix}-{unit_order:04d}"


def build_source_units_artifact(
    *,
    project_id: str,
    created_at: str,
    simulation_requirement: str,
    source_records: List[Dict[str, Any]],
    units: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compose the persisted source-units artifact."""
    unit_type_counts: Dict[str, int] = {}
    source_summaries: List[Dict[str, Any]] = []

    for unit in units:
        unit_type = unit.get("unit_type", "unknown")
        unit_type_counts[unit_type] = unit_type_counts.get(unit_type, 0) + 1

    for source in source_records:
        stable_source_id = source.get("stable_source_id")
        source_summaries.append(
            {
                "source_id": source.get("source_id"),
                "stable_source_id": stable_source_id,
                "original_filename": source.get("original_filename"),
                "relative_path": source.get("relative_path"),
                "sha256": source.get("sha256"),
                "unit_count": len(
                    [
                        unit
                        for unit in units
                        if unit.get("stable_source_id") == stable_source_id
                    ]
                ),
                "extraction_warnings": list(source.get("parser_warnings") or []),
            }
        )

    return {
        "artifact_type": SOURCE_UNITS_ARTIFACT_TYPE,
        "schema_version": GROUNDING_SCHEMA_VERSION,
        "generator_version": GROUNDING_GENERATOR_VERSION,
        "project_id": project_id,
        "created_at": created_at,
        "simulation_requirement": simulation_requirement,
        "boundary_note": SOURCE_BOUNDARY_NOTE,
        "source_artifacts": {"source_manifest": "source_manifest.json"},
        "source_count": len(source_records),
        "unit_count": len(units),
        "unit_type_counts": unit_type_counts,
        "sources": source_summaries,
        "units": units,
    }
