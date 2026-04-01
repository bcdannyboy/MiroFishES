"""Graph backend scaffold errors for the Graphiti cutover."""


class GraphBackendError(RuntimeError):
    """Base graph backend scaffold error."""


class GraphBackendConfigurationError(GraphBackendError):
    """Raised when required Graphiti/Neo4j settings are missing."""


class GraphBackendDependencyError(GraphBackendError):
    """Raised when an optional Graphiti/Neo4j dependency is unavailable."""
