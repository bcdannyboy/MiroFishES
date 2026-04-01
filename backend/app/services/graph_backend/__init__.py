"""Prompt 1 Graphiti + Neo4j backend scaffold."""

from __future__ import annotations

from dataclasses import dataclass

from .graphiti_factory import GraphitiFactoryScaffold, build_graphiti_factory
from .neo4j_factory import Neo4jFactoryScaffold, build_neo4j_factory, probe_neo4j_endpoint
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
    """Build the Prompt 1 runtime scaffold without instantiating vendor clients."""
    resolved_settings = settings or GraphBackendSettings.from_env()
    return GraphBackendRuntime(
        backend=resolved_settings.backend,
        settings=resolved_settings,
        graphiti_factory=build_graphiti_factory(resolved_settings),
        neo4j_factory=build_neo4j_factory(resolved_settings),
    )


def describe_graph_backend_readiness(
    settings: GraphBackendSettings | None = None,
) -> dict[str, object]:
    """Describe current Graphiti + Neo4j scaffold readiness."""
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
        notes.append("Prompt 1 exposes deferred factories until Graphiti + Neo4j dependencies are installed.")
    if not configured:
        notes.append("Prompt 1 keeps the readiness surface honest when Graphiti + Neo4j env vars are incomplete.")
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


__all__ = [
    "GraphBackendRuntime",
    "GraphBackendSettings",
    "build_graph_backend_runtime",
    "describe_graph_backend_readiness",
]
