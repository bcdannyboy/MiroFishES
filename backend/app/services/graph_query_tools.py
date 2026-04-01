"""Public graph-neutral query tools entry point."""

from __future__ import annotations

from .zep_tools import (
    EdgeInfo,
    InsightForgeResult,
    InterviewResult,
    NodeInfo,
    PanoramaResult,
    SearchResult,
    ZepToolsService,
)


class GraphQueryToolsService(ZepToolsService):
    """Graph-backed retrieval tools used by report and API consumers."""


__all__ = [
    "GraphQueryToolsService",
    "SearchResult",
    "NodeInfo",
    "EdgeInfo",
    "InsightForgeResult",
    "PanoramaResult",
    "InterviewResult",
]
