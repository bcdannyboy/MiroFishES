"""Shared phase timing artifact helpers."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, Optional


PHASE_TIMINGS_ARTIFACT_TYPE = "phase_timings"
PHASE_TIMINGS_SCHEMA_VERSION = "mirofish.phase_timings.v1"
PHASE_TIMINGS_GENERATOR_VERSION = "mirofish.phase_timings.generator.v1"


class PhaseTimingRecorder:
    """Persist one additive timing artifact for a single scope."""

    def __init__(
        self,
        *,
        artifact_path: str,
        scope_kind: str,
        scope_id: str,
    ) -> None:
        self.artifact_path = artifact_path
        self.scope_kind = scope_kind
        self.scope_id = scope_id

    def record_completed_phase(
        self,
        phase_name: str,
        *,
        duration_ms: float,
        started_at: str,
        completed_at: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "completed",
    ) -> Dict[str, Any]:
        """Merge one completed phase into the artifact and persist it."""
        payload = self._load_payload()
        payload["phases"][phase_name] = {
            "status": status,
            "duration_ms": round(float(duration_ms), 2),
            "started_at": started_at,
            "completed_at": completed_at,
            "metadata": dict(metadata or {}),
        }
        self._write_payload(payload)
        return payload

    @contextmanager
    def measure_phase(
        self,
        phase_name: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Measure one phase and persist its duration on exit."""
        phase_metadata = dict(metadata or {})
        started_at = datetime.now().isoformat()
        started_perf = time.perf_counter()
        status = "completed"
        try:
            yield phase_metadata
        except Exception:
            status = "failed"
            raise
        finally:
            completed_at = datetime.now().isoformat()
            duration_ms = (time.perf_counter() - started_perf) * 1000
            self.record_completed_phase(
                phase_name,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                metadata=phase_metadata,
                status=status,
            )

    def _base_payload(self) -> Dict[str, Any]:
        return {
            "artifact_type": PHASE_TIMINGS_ARTIFACT_TYPE,
            "schema_version": PHASE_TIMINGS_SCHEMA_VERSION,
            "generator_version": PHASE_TIMINGS_GENERATOR_VERSION,
            "scope_kind": self.scope_kind,
            "scope_id": self.scope_id,
            "phases": {},
        }

    def _load_payload(self) -> Dict[str, Any]:
        if not os.path.exists(self.artifact_path):
            return self._base_payload()

        try:
            with open(self.artifact_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError):
            # Phase timings are auxiliary telemetry only. A malformed historical
            # artifact must not block the primary report/analytics workflows.
            return self._base_payload()

        if not isinstance(payload, dict):
            return self._base_payload()

        payload.setdefault("artifact_type", PHASE_TIMINGS_ARTIFACT_TYPE)
        payload.setdefault("schema_version", PHASE_TIMINGS_SCHEMA_VERSION)
        payload.setdefault("generator_version", PHASE_TIMINGS_GENERATOR_VERSION)
        payload.setdefault("scope_kind", self.scope_kind)
        payload.setdefault("scope_id", self.scope_id)
        payload.setdefault("phases", {})
        return payload

    def _write_payload(self, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.artifact_path), exist_ok=True)
        with open(self.artifact_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
