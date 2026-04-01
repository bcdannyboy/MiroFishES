"""Deterministic namespace policy for Graphiti group_ids."""

from __future__ import annotations

import re

from .types import GraphNamespaceDescriptor


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str | None) -> str:
    normalized = _NON_ALNUM_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or "graph"


class GraphNamespaceManager:
    """Build stable namespace identifiers for base and runtime graphs."""

    def __init__(self, namespace_prefix: str = "mirofish") -> None:
        self.namespace_prefix = _slugify(namespace_prefix)

    def build_base_namespace(
        self,
        *,
        project_id: str,
        project_name: str | None = None,
    ) -> GraphNamespaceDescriptor:
        namespace_id = f"{self.namespace_prefix}-base-{_slugify(project_id)}"
        display_name = f"{project_name or project_id} base graph"
        return GraphNamespaceDescriptor(
            namespace_id=namespace_id,
            group_id=namespace_id,
            graph_scope="base",
            display_name=display_name,
        )

    def build_runtime_namespace(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
    ) -> GraphNamespaceDescriptor:
        namespace_id = "-".join(
            [
                self.namespace_prefix,
                "runtime",
                _slugify(simulation_id),
                _slugify(ensemble_id),
                _slugify(run_id),
            ]
        )
        return GraphNamespaceDescriptor(
            namespace_id=namespace_id,
            group_id=namespace_id,
            graph_scope="runtime",
            display_name=f"Runtime graph {simulation_id}/{ensemble_id}/{run_id}",
        )

    def build_named_namespace(
        self,
        *,
        graph_name: str,
        graph_scope: str = "base",
    ) -> GraphNamespaceDescriptor:
        normalized_scope = _slugify(graph_scope)
        namespace_id = f"{self.namespace_prefix}-{normalized_scope}-{_slugify(graph_name)}"
        return GraphNamespaceDescriptor(
            namespace_id=namespace_id,
            group_id=namespace_id,
            graph_scope=normalized_scope,
            display_name=graph_name,
        )
