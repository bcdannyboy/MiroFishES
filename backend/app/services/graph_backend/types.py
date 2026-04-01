"""Shared Graphiti + Neo4j scaffold DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphDependencyStatus:
    """Status for one optional Graphiti/Neo4j dependency."""

    distribution_name: str
    available: bool
    version: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "distribution_name": self.distribution_name,
            "available": self.available,
            "version": self.version,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class GraphBackendReadiness:
    """Normalized readiness payload for the graph backend scaffold."""

    backend: str
    configured: bool
    ready: bool
    missing_configuration: tuple[str, ...] = ()
    dependency_status: dict[str, GraphDependencyStatus] = field(default_factory=dict)
    neo4j_probe: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "configured": self.configured,
            "ready": self.ready,
            "missing_configuration": list(self.missing_configuration),
            "dependency_status": {
                name: status.to_dict()
                for name, status in self.dependency_status.items()
            },
            "neo4j_probe": dict(self.neo4j_probe),
            "notes": list(self.notes),
        }
