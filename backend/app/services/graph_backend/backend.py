"""Backend-neutral seam for the Graphiti + Neo4j base graph workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .export_service import Neo4jGraphExportService
from .graphiti_factory import GraphitiFactoryScaffold, build_graphiti_factory
from .ingestion_service import GraphitiIngestionService
from .namespace_manager import GraphNamespaceManager
from .neo4j_factory import Neo4jFactoryScaffold, build_neo4j_factory
from .ontology_compiler import GraphOntologyCompiler
from .settings import GraphBackendSettings
from .types import CompiledOntology, GraphNamespaceDescriptor


@dataclass
class _NamespaceState:
    descriptor: GraphNamespaceDescriptor
    raw_ontology: dict[str, Any] = field(default_factory=dict)
    compiled_ontology: CompiledOntology | None = None


class GraphitiGraphBackend:
    """Application-managed backend seam for base graph build and export."""

    def __init__(
        self,
        *,
        settings: GraphBackendSettings,
        graphiti_factory: GraphitiFactoryScaffold | None = None,
        neo4j_factory: Neo4jFactoryScaffold | None = None,
        namespace_manager: GraphNamespaceManager | None = None,
        ontology_compiler: GraphOntologyCompiler | None = None,
        ingestion_service: GraphitiIngestionService | None = None,
        export_service: Neo4jGraphExportService | None = None,
    ) -> None:
        self.settings = settings
        self.graphiti_factory = graphiti_factory or build_graphiti_factory(settings)
        self.neo4j_factory = neo4j_factory or build_neo4j_factory(settings)
        self.namespace_manager = namespace_manager or GraphNamespaceManager()
        self.ontology_compiler = ontology_compiler or GraphOntologyCompiler()
        self.ingestion_service = ingestion_service or GraphitiIngestionService()
        self.export_service = export_service or Neo4jGraphExportService()
        self._namespaces: dict[str, _NamespaceState] = {}

    def create_base_graph(
        self,
        *,
        graph_name: str,
        project_id: str | None = None,
    ) -> GraphNamespaceDescriptor:
        descriptor = (
            self.namespace_manager.build_base_namespace(
                project_id=project_id,
                project_name=graph_name,
            )
            if project_id
            else self.namespace_manager.build_named_namespace(
                graph_name=graph_name,
                graph_scope="base",
            )
        )
        self._namespaces[descriptor.namespace_id] = _NamespaceState(descriptor=descriptor)
        return descriptor

    def register_ontology(self, namespace_id: str, ontology: dict[str, Any]) -> None:
        state = self._get_namespace_state(namespace_id)
        state.raw_ontology = dict(ontology or {})
        state.compiled_ontology = self.ontology_compiler.compile(state.raw_ontology)

    def add_text_batches(
        self,
        namespace_id: str,
        chunks: list[str],
        batch_size: int | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> list[str]:
        state = self._get_namespace_state(namespace_id)
        return self.ingestion_service.ingest_text_batches(
            namespace_id=namespace_id,
            chunks=list(chunks),
            batch_size=batch_size or self.settings.build_batch_size,
            progress_callback=progress_callback,
            graphiti_factory=self.graphiti_factory,
            compiled_ontology=state.compiled_ontology,
        )

    def wait_for_episode_processing(
        self,
        namespace_id: str,
        episode_ids: list[str],
        progress_callback: Callable[[str, float], None] | None = None,
        timeout: int | None = None,
    ) -> None:
        self._get_namespace_state(namespace_id)
        self.ingestion_service.wait_for_episode_processing(
            namespace_id=namespace_id,
            episode_ids=list(episode_ids),
            progress_callback=progress_callback,
            timeout=timeout,
        )

    def export_graph_snapshot(self, namespace_id: str) -> dict[str, Any]:
        self._get_namespace_state(namespace_id)
        return self.export_service.export_graph_snapshot(
            namespace_id=namespace_id,
            neo4j_factory=self.neo4j_factory,
        )

    def delete_graph(self, namespace_id: str) -> None:
        self._namespaces.pop(namespace_id, None)

    def _get_namespace_state(self, namespace_id: str) -> _NamespaceState:
        state = self._namespaces.get(namespace_id)
        if state is not None:
            return state
        descriptor = GraphNamespaceDescriptor(
            namespace_id=namespace_id,
            group_id=namespace_id,
            graph_scope="base",
            display_name=namespace_id,
        )
        state = _NamespaceState(descriptor=descriptor)
        self._namespaces[namespace_id] = state
        return state
