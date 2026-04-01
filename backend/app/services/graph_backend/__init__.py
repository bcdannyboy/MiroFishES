"""Graphiti + Neo4j backend runtime and readiness helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .backend import GraphitiGraphBackend
from .graphiti_factory import GraphitiFactoryScaffold, build_graphiti_factory
from .namespace_manager import GraphNamespaceManager
from .neo4j_factory import Neo4jFactoryScaffold, build_neo4j_factory, probe_neo4j_endpoint
from .ontology_compiler import GraphOntologyCompiler
from .query_service import GraphQueryService
from .runtime_event_ingestor import GraphitiRuntimeEventIngestor
from .scan_service import GraphScanService
from .settings import GraphBackendSettings
from .types import GraphBackendReadiness


@dataclass(frozen=True)
class GraphBackendRuntime:
    """Deferred backend runtime metadata for the Graphiti cutover harness."""

    backend: str
    settings: GraphBackendSettings
    graphiti_factory: GraphitiFactoryScaffold
    neo4j_factory: Neo4jFactoryScaffold


def build_graph_backend_runtime(
    settings: GraphBackendSettings | None = None,
) -> GraphBackendRuntime:
    """Build the Graphiti + Neo4j runtime metadata without instantiating vendor clients."""
    resolved_settings = settings or GraphBackendSettings.from_env()
    return GraphBackendRuntime(
        backend=resolved_settings.backend,
        settings=resolved_settings,
        graphiti_factory=build_graphiti_factory(resolved_settings),
        neo4j_factory=build_neo4j_factory(resolved_settings),
    )


def build_graph_backend_service(
    settings: GraphBackendSettings | None = None,
) -> GraphitiGraphBackend:
    """Build the concrete backend seam used by the base graph build path."""
    resolved_settings = settings or GraphBackendSettings.from_env()
    return GraphitiGraphBackend(
        settings=resolved_settings,
        graphiti_factory=build_graphiti_factory(resolved_settings),
        neo4j_factory=build_neo4j_factory(resolved_settings),
        namespace_manager=GraphNamespaceManager(),
        ontology_compiler=GraphOntologyCompiler(),
    )


def describe_graph_backend_readiness(
    settings: GraphBackendSettings | None = None,
) -> dict[str, object]:
    """Describe current Graphiti + Neo4j backend readiness."""
    runtime = build_graph_backend_runtime(settings)
    missing_configuration = tuple(runtime.settings.validate())
    dependency_status = {
        runtime.graphiti_factory.distribution_name: runtime.graphiti_factory.dependency_status,
        runtime.neo4j_factory.distribution_name: runtime.neo4j_factory.dependency_status,
    }
    neo4j_probe = probe_neo4j_endpoint(runtime.settings)
    configured = not missing_configuration
    dependencies_ready = all(status.available for status in dependency_status.values())
    ready = configured and dependencies_ready and bool(neo4j_probe.get("reachable"))
    notes: list[str] = []
    if not dependencies_ready:
        notes.append(
            "Prompt 2 wires the base graph build path through Graphiti + Neo4j, "
            "but the runtime still needs installed backend dependencies."
        )
    if not configured:
        notes.append(
            "The readiness surface reports configuration gaps before Graphiti-backed "
            "build attempts run."
        )
    readiness = GraphBackendReadiness(
        backend=runtime.backend,
        configured=configured,
        ready=ready,
        missing_configuration=missing_configuration,
        dependency_status=dependency_status,
        neo4j_probe=neo4j_probe,
        notes=tuple(notes),
    )
    return readiness.to_dict()


def describe_graph_backend_capabilities(
    settings: GraphBackendSettings | None = None,
) -> dict[str, object]:
    """Describe the stable operator-facing Graphiti + Neo4j contract."""
    runtime = build_graph_backend_runtime(settings)
    return {
        "backend": runtime.backend,
        "namespace_policy": {
            "base_graph_id": "application-managed namespace id",
            "runtime_graph_id": "application-managed namespace id",
            "merged_reads": True,
            "artifact_first_reads": True,
            "runtime_event_ingestion": True,
        },
        "build_path": {
            "base_graph_build": True,
            "runtime_namespace_provisioning": True,
            "runtime_event_updates": True,
        },
        "verification_commands": {
            "unit": "npm run verify:graphiti:unit",
            "integration": "npm run verify:graphiti:integration",
            "smoke": "npm run verify:graphiti:smoke",
            "live": "npm run verify:graphiti:live",
            "all": "npm run verify:graphiti:all",
        },
        "readiness_endpoint": "/api/graph/backend/readiness",
        "live_probe_command": "npm run verify:graphiti:live",
    }


__all__ = [
    "GraphNamespaceManager",
    "GraphOntologyCompiler",
    "GraphQueryService",
    "GraphitiRuntimeEventIngestor",
    "GraphScanService",
    "GraphitiGraphBackend",
    "GraphBackendRuntime",
    "GraphBackendSettings",
    "build_graph_backend_service",
    "build_graph_backend_runtime",
    "describe_graph_backend_capabilities",
    "describe_graph_backend_readiness",
]
