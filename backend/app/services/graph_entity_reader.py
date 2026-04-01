"""Public graph-neutral entity reader entry point."""

from __future__ import annotations

from .zep_entity_reader import (
    EntityNode,
    FilteredEntities,
    ZepEntityReader,
    build_filtered_entities_from_payloads,
)


class GraphEntityReader(ZepEntityReader):
    """Graph-backed entity reader used after the Zep cutover."""


__all__ = [
    "GraphEntityReader",
    "EntityNode",
    "FilteredEntities",
    "build_filtered_entities_from_payloads",
]
