"""Shared Graphiti + Neo4j backend DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


@dataclass(frozen=True)
class GraphNamespaceDescriptor:
    """Application-managed graph namespace metadata."""

    namespace_id: str
    group_id: str
    graph_scope: str
    display_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "namespace_id": self.namespace_id,
            "group_id": self.group_id,
            "graph_scope": self.graph_scope,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class CompiledOntology:
    """Graphiti-compatible compiled ontology from repo JSON schema."""

    raw_ontology: dict[str, Any]
    entity_types: dict[str, type[BaseModel]]
    edge_types: dict[str, type[BaseModel]]
    edge_type_map: dict[tuple[str, str], list[str]]

    def describe(self) -> dict[str, Any]:
        return {
            "entity_type_names": sorted(self.entity_types),
            "edge_type_names": sorted(self.edge_types),
            "edge_type_map": {
                f"{source}->{target}": list(edge_names)
                for (source, target), edge_names in self.edge_type_map.items()
            },
        }


@dataclass(frozen=True)
class GraphEpisodeRecord:
    """One ingested episode with the application-visible identifier."""

    episode_id: str
    name: str
    namespace_id: str
    content: str
    reference_time: datetime


@dataclass(frozen=True)
class GraphExportSnapshot:
    """Normalized graph export used by build artifacts and preview endpoints."""

    graph_id: str
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [dict(node) for node in self.nodes],
            "edges": [dict(edge) for edge in self.edges],
        }
