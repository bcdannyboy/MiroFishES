"""Prompt 1 Graphiti + Neo4j settings scaffold."""

from __future__ import annotations

from dataclasses import dataclass

from ...config import Config


@dataclass(frozen=True)
class GraphBackendSettings:
    """Resolved Graphiti + Neo4j settings for the cutover scaffold."""

    backend: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str | None
    graphiti_extraction_model: str
    graphiti_embedding_model: str
    build_batch_size: int
    search_limit: int
    scan_limit: int
    runtime_batch_size: int
    openai_api_key: str | None = None
    openai_base_url: str = ""
    embedding_api_key: str | None = None
    embedding_base_url: str = ""
    embedding_dimensions: int | None = None

    @classmethod
    def from_env(cls) -> "GraphBackendSettings":
        return cls(
            backend=Config.get_graph_backend_name(),
            neo4j_uri=Config.get_neo4j_uri(),
            neo4j_user=Config.get_neo4j_user(),
            neo4j_password=Config.get_neo4j_password(),
            graphiti_extraction_model=Config.get_graphiti_extraction_model(),
            graphiti_embedding_model=Config.get_graphiti_embedding_model(),
            build_batch_size=Config.get_graph_backend_batch_size(),
            search_limit=Config.get_graph_backend_search_limit(),
            scan_limit=Config.get_graph_backend_scan_limit(),
            runtime_batch_size=Config.get_graph_backend_runtime_batch_size(),
            openai_api_key=Config.get_openai_api_key(),
            openai_base_url=Config.get_openai_base_url(),
            embedding_api_key=Config.get_embedding_api_key(),
            embedding_base_url=Config.get_embedding_base_url(),
            embedding_dimensions=Config.get_embedding_dimensions(),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.backend != "graphiti_neo4j":
            return errors
        if not self.neo4j_uri:
            errors.append("NEO4J_URI is not configured")
        if not self.neo4j_user:
            errors.append("NEO4J_USER is not configured")
        if not self.neo4j_password:
            errors.append("NEO4J_PASSWORD is not configured")
        if not self.graphiti_extraction_model:
            errors.append("GRAPHITI_EXTRACTION_MODEL is not configured")
        if not self.graphiti_embedding_model:
            errors.append("GRAPHITI_EMBEDDING_MODEL is not configured")
        return errors
