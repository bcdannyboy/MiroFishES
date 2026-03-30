"""Helpers for classifying stale forecasting artifacts as read-only history."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


FORECAST_ARCHIVE_FILENAME = "forecast_archive.json"
FORECAST_ARCHIVE_ARTIFACT_TYPE = "forecast_archive"
FORECAST_ARCHIVE_SCHEMA_VERSION = "forecast.archive.v1"
FORECAST_ARCHIVE_CONFORMANCE_SCHEMA_VERSION = "forecast.archive.conformance.v1"
FORECAST_ARCHIVE_SCOPE = "historical_read_only"
DEFAULT_FORECAST_ARCHIVE_REASON = (
    "This saved simulation predates the current forecasting-readiness contract and "
    "is retained for read-only historical access."
)


def get_forecast_archive_path(simulation_dir: str | Path) -> Path:
    return Path(simulation_dir) / FORECAST_ARCHIVE_FILENAME


def load_forecast_archive_metadata(simulation_dir: str | Path) -> Optional[dict[str, Any]]:
    archive_path = get_forecast_archive_path(simulation_dir)
    if not archive_path.exists():
        return None

    try:
        payload = json.loads(archive_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "artifact_type": FORECAST_ARCHIVE_ARTIFACT_TYPE,
            "schema_version": FORECAST_ARCHIVE_SCHEMA_VERSION,
            "archive_scope": FORECAST_ARCHIVE_SCOPE,
            "reason": "Archive marker exists but could not be parsed.",
            "path": str(archive_path),
            "invalid": True,
        }

    if not isinstance(payload, dict):
        return {
            "artifact_type": FORECAST_ARCHIVE_ARTIFACT_TYPE,
            "schema_version": FORECAST_ARCHIVE_SCHEMA_VERSION,
            "archive_scope": FORECAST_ARCHIVE_SCOPE,
            "reason": "Archive marker exists but does not contain a JSON object.",
            "path": str(archive_path),
            "invalid": True,
        }

    return payload


def is_forecast_archived(simulation_dir: str | Path) -> bool:
    return get_forecast_archive_path(simulation_dir).exists()


def build_historical_conformance_metadata(
    *,
    status: str,
    reason: str,
    updated_at: Optional[str] = None,
    updated_by: Optional[str] = None,
    issue_codes: Optional[list[str]] = None,
    quarantined_issue_codes: Optional[list[str]] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": FORECAST_ARCHIVE_CONFORMANCE_SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "updated_at": updated_at or datetime.now().isoformat(),
    }
    if updated_by:
        payload["updated_by"] = updated_by
    if issue_codes:
        payload["issue_codes"] = sorted({str(code).strip() for code in issue_codes if str(code).strip()})
    if quarantined_issue_codes:
        payload["quarantined_issue_codes"] = sorted(
            {str(code).strip() for code in quarantined_issue_codes if str(code).strip()}
        )
    if details:
        payload["details"] = details
    return payload


def build_forecast_archive_metadata(
    *,
    reason: str = DEFAULT_FORECAST_ARCHIVE_REASON,
    archived_at: Optional[str] = None,
    archived_by: Optional[str] = None,
    archive_scope: str = FORECAST_ARCHIVE_SCOPE,
    source: Optional[str] = None,
    issue_count: Optional[int] = None,
    historical_conformance: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_type": FORECAST_ARCHIVE_ARTIFACT_TYPE,
        "schema_version": FORECAST_ARCHIVE_SCHEMA_VERSION,
        "archived_at": archived_at or datetime.now().isoformat(),
        "archive_scope": archive_scope,
        "reason": reason,
    }
    if archived_by:
        payload["archived_by"] = archived_by
    if source:
        payload["source"] = source
    if issue_count is not None:
        payload["issue_count"] = issue_count
    if historical_conformance:
        payload["historical_conformance"] = historical_conformance
    return payload


def write_forecast_archive_metadata(
    simulation_dir: str | Path,
    *,
    reason: str = DEFAULT_FORECAST_ARCHIVE_REASON,
    archived_at: Optional[str] = None,
    archived_by: Optional[str] = None,
    archive_scope: str = FORECAST_ARCHIVE_SCOPE,
    source: Optional[str] = None,
    issue_count: Optional[int] = None,
    historical_conformance: Optional[dict[str, Any]] = None,
) -> Path:
    archive_path = get_forecast_archive_path(simulation_dir)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(
        json.dumps(
            build_forecast_archive_metadata(
                reason=reason,
                archived_at=archived_at,
                archived_by=archived_by,
                archive_scope=archive_scope,
                source=source,
                issue_count=issue_count,
                historical_conformance=historical_conformance,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return archive_path
