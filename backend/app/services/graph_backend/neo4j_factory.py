"""Neo4j factory and reachability probe for the cutover backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from socket import create_connection
from typing import Any
from urllib.parse import urlparse

from .errors import GraphBackendDependencyError
from .settings import GraphBackendSettings
from .types import GraphDependencyStatus

try:  # pragma: no cover - import presence depends on local env
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - exercised only without dependency
    GraphDatabase = None


@dataclass(frozen=True)
class Neo4jFactoryScaffold:
    """Neo4j driver metadata with lazy runtime construction."""

    distribution_name: str
    driver_builder: str
    dependency_status: GraphDependencyStatus
    connection_kwargs: dict[str, Any] = field(default_factory=dict)

    def build_driver(self) -> Any:
        """Build one synchronous Neo4j driver when the dependency exists."""
        if GraphDatabase is None:
            raise GraphBackendDependencyError(
                self.dependency_status.detail
                or "neo4j Python driver is not installed in the backend environment"
            )
        return GraphDatabase.driver(
            self.connection_kwargs["uri"],
            self.connection_kwargs["auth"],
        )

    def run_healthcheck(self, driver: Any) -> bool:
        """Run a minimal graph healthcheck through the supplied driver."""
        records, _summary, _keys = driver.execute_query("RETURN 1 AS ok")
        if not records:
            return False
        first_record = records[0]
        if hasattr(first_record, "data"):
            first_record = first_record.data()
        if isinstance(first_record, dict):
            return first_record.get("ok") == 1
        return bool(first_record)


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
    """Return lazy Neo4j factory metadata for the cutover backend."""
    dependency_status = detect_neo4j_dependency()
    return Neo4jFactoryScaffold(
        distribution_name=dependency_status.distribution_name,
        driver_builder="graph_database_driver",
        dependency_status=dependency_status,
        connection_kwargs={
            "uri": _settings.neo4j_uri,
            "auth": (_settings.neo4j_user, _settings.neo4j_password),
        },
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
