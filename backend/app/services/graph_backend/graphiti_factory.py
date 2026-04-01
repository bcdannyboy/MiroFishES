"""Graphiti dependency scaffold for Prompt 1."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

from .settings import GraphBackendSettings
from .types import GraphDependencyStatus


@dataclass(frozen=True)
class GraphitiFactoryScaffold:
    """Deferred Graphiti factory metadata used before full cutover."""

    distribution_name: str
    client_builder: str
    dependency_status: GraphDependencyStatus


def detect_graphiti_dependency() -> GraphDependencyStatus:
    """Inspect Graphiti availability without importing the runtime package."""
    try:
        version = metadata.version("graphiti-core")
        return GraphDependencyStatus(
            distribution_name="graphiti-core",
            available=True,
            version=version,
        )
    except metadata.PackageNotFoundError:
        return GraphDependencyStatus(
            distribution_name="graphiti-core",
            available=False,
            detail="Install graphiti-core to enable the cutover backend.",
        )


def build_graphiti_factory(_settings: GraphBackendSettings) -> GraphitiFactoryScaffold:
    """Return deferred Graphiti factory metadata for Prompt 1."""
    dependency_status = detect_graphiti_dependency()
    return GraphitiFactoryScaffold(
        distribution_name=dependency_status.distribution_name,
        client_builder="deferred",
        dependency_status=dependency_status,
    )
