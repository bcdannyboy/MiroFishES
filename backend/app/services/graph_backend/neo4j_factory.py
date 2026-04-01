"""Neo4j dependency scaffold and reachability probe for Prompt 1."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from socket import create_connection
from urllib.parse import urlparse

from .settings import GraphBackendSettings
from .types import GraphDependencyStatus


@dataclass(frozen=True)
class Neo4jFactoryScaffold:
    """Deferred Neo4j factory metadata used before the full backend implementation."""

    distribution_name: str
    driver_builder: str
    dependency_status: GraphDependencyStatus


def detect_neo4j_dependency() -> GraphDependencyStatus:
    """Inspect Neo4j driver availability without importing the driver."""
    try:
        version = metadata.version("neo4j")
        return GraphDependencyStatus(
            distribution_name="neo4j",
            available=True,
            version=version,
        )
    except metadata.PackageNotFoundError:
        return GraphDependencyStatus(
            distribution_name="neo4j",
            available=False,
            detail="Install the neo4j Python driver to enable the cutover backend.",
        )


def build_neo4j_factory(_settings: GraphBackendSettings) -> Neo4jFactoryScaffold:
    """Return deferred Neo4j factory metadata for Prompt 1."""
    dependency_status = detect_neo4j_dependency()
    return Neo4jFactoryScaffold(
        distribution_name=dependency_status.distribution_name,
        driver_builder="deferred",
        dependency_status=dependency_status,
    )


def probe_neo4j_endpoint(settings: GraphBackendSettings, timeout_seconds: float = 1.0) -> dict[str, object]:
    """Probe the configured Neo4j endpoint without using secrets."""
    parsed = urlparse(settings.neo4j_uri)
    host = parsed.hostname
    port = parsed.port
    probe = {
        "uri": settings.neo4j_uri,
        "reachable": False,
        "detail": "not_probed",
    }
    if not host or not port:
        probe["detail"] = "NEO4J_URI must include a host and port"
        return probe

    try:
        with create_connection((host, port), timeout=timeout_seconds):
            probe["reachable"] = True
            probe["detail"] = "connected"
    except OSError as exc:
        probe["detail"] = f"{exc.__class__.__name__}: {exc}"
    return probe
