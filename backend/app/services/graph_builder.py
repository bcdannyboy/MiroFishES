"""Graph building service routed through the Graphiti + Neo4j backend seam."""

from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from .forecast_graph import build_chunk_records, summarize_graph_snapshot
from .graph_backend import GraphBackendSettings, build_graph_backend_service
from .text_processor import TextProcessor

logger = get_logger("mirofish.graph_builder")


_PREVIEW_CACHE_LOCK = threading.Lock()
_PREVIEW_CACHE: dict[tuple[str, str, int, int], dict[str, Any]] = {}
_PREVIEW_INFLIGHT: dict[tuple[str, str, int, int], dict[str, Any]] = {}


@dataclass
class GraphInfo:
    """Graph information."""

    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


def _extract_namespace_id(namespace_result: Any) -> str:
    if isinstance(namespace_result, str):
        return namespace_result
    if isinstance(namespace_result, dict):
        return str(namespace_result.get("namespace_id") or namespace_result.get("graph_id") or "")
    for attr_name in ("namespace_id", "graph_id", "group_id"):
        value = getattr(namespace_result, attr_name, None)
        if value:
            return str(value)
    raise ValueError(f"Unable to resolve namespace id from {namespace_result!r}")


def _read_value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


class GraphBuilderService:
    """Backend-neutral graph builder used by the base project graph workflow."""

    DEFAULT_FULL_MAX_NODES = 2000
    DEFAULT_FULL_MAX_EDGES = 5000
    DEFAULT_PREVIEW_MAX_NODES = 180
    DEFAULT_PREVIEW_MAX_EDGES = 320
    PREVIEW_CACHE_TTL_SECONDS = 10
    DEFAULT_BATCH_SIZE = 3
    MAX_BATCH_SIZE = 16
    MAX_INFLIGHT_BATCHES = 4
    DEFAULT_WAIT_POLL_INTERVAL_SECONDS = 1.0
    MAX_WAIT_POLL_INTERVAL_SECONDS = 5.0

    def __init__(
        self,
        graph_backend: Any | None = None,
        *,
        project_id: str | None = None,
        settings: GraphBackendSettings | None = None,
    ) -> None:
        self.settings = settings or GraphBackendSettings.from_env()
        self.graph_backend = graph_backend or build_graph_backend_service(self.settings)
        self.project_id = project_id
        self.task_manager = TaskManager()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFishES Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: Optional[int] = None,
    ) -> str:
        """Build a graph asynchronously."""
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
        )
        thread.daemon = True
        thread.start()
        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int | None,
    ) -> None:
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph build...",
            )

            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph namespace created: {graph_id}",
            )

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology configured",
            )

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks",
            )

            episode_ids = self.add_text_batches(
                graph_id,
                chunks,
                batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),
                    message=msg,
                ),
            )

            self.task_manager.update_task(
                task_id,
                progress=60,
                message="Waiting for graph ingestion to settle...",
            )
            self._wait_for_episodes(
                graph_id,
                episode_ids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),
                    message=msg,
                ),
            )

            self.task_manager.update_task(
                task_id,
                progress=90,
                message="Fetching graph information...",
            )
            graph_info = self._get_graph_info(graph_id)
            self.task_manager.complete_task(
                task_id,
                {
                    "graph_id": graph_id,
                    "graph_info": graph_info.to_dict(),
                    "chunks_processed": total_chunks,
                },
            )
        except Exception as exc:  # pragma: no cover - worker errors are API-observable
            import traceback

            error_msg = f"{str(exc)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """Create one base graph namespace."""
        namespace = self.graph_backend.create_base_graph(
            graph_name=name,
            project_id=self.project_id,
        )
        return _extract_namespace_id(namespace)

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        """Register ontology for one graph namespace."""
        self.graph_backend.register_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        max_inflight_batches: Optional[int] = None,
    ) -> List[str]:
        """Add text to the graph in batches and return application-visible episode ids."""
        del max_inflight_batches
        total_chunks = len(chunks)
        if total_chunks == 0:
            return []
        batch_plan = self._resolve_batch_plan(total_chunks, requested_batch_size=batch_size)
        return self.graph_backend.add_text_batches(
            graph_id,
            chunks,
            batch_size=batch_plan["batch_size"],
            progress_callback=progress_callback,
        )

    def _resolve_batch_plan(
        self,
        total_chunks: int,
        *,
        requested_batch_size: Optional[int] = None,
    ) -> Dict[str, int]:
        """Choose one bounded batch plan based on the amount of work."""
        if total_chunks <= 0:
            return {"batch_size": self.DEFAULT_BATCH_SIZE, "max_inflight_batches": 1}

        if requested_batch_size is not None:
            normalized_size = max(1, min(int(requested_batch_size), self.MAX_BATCH_SIZE))
            return {
                "batch_size": normalized_size,
                "max_inflight_batches": min(
                    self.MAX_INFLIGHT_BATCHES,
                    max(1, (total_chunks + normalized_size - 1) // normalized_size),
                ),
            }

        if total_chunks <= 6:
            return {"batch_size": self.DEFAULT_BATCH_SIZE, "max_inflight_batches": 1}
        if total_chunks <= 24:
            return {"batch_size": 6, "max_inflight_batches": 2}
        if total_chunks <= 80:
            return {"batch_size": 10, "max_inflight_batches": 3}
        return {
            "batch_size": self.MAX_BATCH_SIZE,
            "max_inflight_batches": self.MAX_INFLIGHT_BATCHES,
        }

    def _wait_for_episodes(
        self,
        graph_id: str,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """Wait for the backend ingestion layer to settle."""
        self.graph_backend.wait_for_episode_processing(
            graph_id,
            episode_uuids,
            progress_callback=progress_callback,
            timeout=timeout,
        )

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        snapshot = self.get_graph_snapshot(graph_id)
        return GraphInfo(
            graph_id=graph_id,
            node_count=snapshot["node_count"],
            edge_count=snapshot["edge_count"],
            entity_types=snapshot["entity_types"],
        )

    def get_graph_snapshot(self, graph_id: str) -> Dict[str, Any]:
        """Fetch one exact graph snapshot for build summaries and local indexes."""
        snapshot = self.graph_backend.export_graph_snapshot(graph_id)
        graph_counts = (snapshot.get("graph_counts") if isinstance(snapshot, dict) else None) or summarize_graph_snapshot(snapshot)
        normalized = dict(snapshot)
        normalized["graph_counts"] = graph_counts
        normalized["entity_types"] = list(
            normalized.get("entity_types") or graph_counts.get("entity_types") or []
        )
        normalized["node_count"] = int(normalized.get("node_count", len(normalized.get("nodes", []))))
        normalized["edge_count"] = int(normalized.get("edge_count", len(normalized.get("edges", []))))
        return normalized

    def _get_graph_data_with_mode(
        self,
        graph_id: str,
        *,
        mode: str = "full",
        max_nodes: Optional[int] = None,
        max_edges: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized_mode = "preview" if str(mode).lower() == "preview" else "full"
        effective_max_nodes = self._resolve_graph_limit(
            max_nodes,
            default=(
                self.DEFAULT_PREVIEW_MAX_NODES
                if normalized_mode == "preview"
                else self.DEFAULT_FULL_MAX_NODES
            ),
        )
        effective_max_edges = self._resolve_graph_limit(
            max_edges,
            default=(
                self.DEFAULT_PREVIEW_MAX_EDGES
                if normalized_mode == "preview"
                else self.DEFAULT_FULL_MAX_EDGES
            ),
        )

        if normalized_mode == "preview":
            return self._get_preview_graph_data_cached(
                graph_id,
                max_nodes=effective_max_nodes,
                max_edges=effective_max_edges,
            )

        return self._build_graph_data(
            graph_id,
            mode=normalized_mode,
            max_nodes=effective_max_nodes,
            max_edges=effective_max_edges,
        )

    def get_graph_data(
        self,
        graph_id: str,
        *,
        mode: str = "full",
        max_nodes: Optional[int] = None,
        max_edges: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get graph data in either preview or full mode."""
        return self._get_graph_data_with_mode(
            graph_id,
            mode=mode,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    def _resolve_graph_limit(self, raw_value: Optional[int], *, default: int) -> int:
        if raw_value is None:
            return default
        try:
            normalized = int(raw_value)
        except (TypeError, ValueError):
            return default
        return normalized if normalized > 0 else default

    def _get_preview_graph_data_cached(
        self,
        graph_id: str,
        *,
        max_nodes: int,
        max_edges: int,
    ) -> Dict[str, Any]:
        cache_key = (graph_id, "preview", max_nodes, max_edges)
        now = time.time()

        with _PREVIEW_CACHE_LOCK:
            cached_entry = _PREVIEW_CACHE.get(cache_key)
            if cached_entry and cached_entry["expires_at"] > now:
                logger.info(
                    "Graph preview cache hit: graph_id=%s max_nodes=%s max_edges=%s",
                    graph_id,
                    max_nodes,
                    max_edges,
                )
                return copy.deepcopy(cached_entry["data"])

            inflight_entry = _PREVIEW_INFLIGHT.get(cache_key)
            if inflight_entry is None:
                inflight_entry = {
                    "event": threading.Event(),
                    "result": None,
                    "error": None,
                }
                _PREVIEW_INFLIGHT[cache_key] = inflight_entry
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            inflight_entry["event"].wait(timeout=30)
            if inflight_entry["error"] is not None:
                raise inflight_entry["error"]
            if inflight_entry["result"] is not None:
                return copy.deepcopy(inflight_entry["result"])

        try:
            result = self._build_graph_data(
                graph_id,
                mode="preview",
                max_nodes=max_nodes,
                max_edges=max_edges,
            )
            with _PREVIEW_CACHE_LOCK:
                _PREVIEW_CACHE[cache_key] = {
                    "expires_at": time.time() + self.PREVIEW_CACHE_TTL_SECONDS,
                    "data": copy.deepcopy(result),
                }
            inflight_entry["result"] = copy.deepcopy(result)
            return result
        except Exception as exc:
            inflight_entry["error"] = exc
            raise
        finally:
            inflight_entry["event"].set()
            with _PREVIEW_CACHE_LOCK:
                _PREVIEW_INFLIGHT.pop(cache_key, None)

    def _build_graph_data(
        self,
        graph_id: str,
        *,
        mode: str,
        max_nodes: int,
        max_edges: int,
    ) -> Dict[str, Any]:
        started_at = time.time()
        snapshot = self.get_graph_snapshot(graph_id)
        all_nodes = list(snapshot.get("nodes", []))
        all_edges = list(snapshot.get("edges", []))

        preview_mode = mode == "preview"
        nodes_window = all_nodes[:max_nodes]
        edges_window = all_edges[:max_edges]
        node_map = {
            str(node.get("uuid")): str(node.get("name") or "")
            for node in all_nodes
            if isinstance(node, dict) and node.get("uuid")
        }

        nodes_data = [self._serialize_node(node, preview=preview_mode) for node in nodes_window]
        edges_data = [
            self._serialize_edge(edge, node_map=node_map, preview=preview_mode)
            for edge in edges_window
        ]
        truncated = len(nodes_window) < len(all_nodes) or len(edges_window) < len(all_edges)

        payload = {
            "graph_id": graph_id,
            "mode": mode,
            "truncated": truncated,
            "returned_nodes": len(nodes_data),
            "returned_edges": len(edges_data),
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "node_count": len(all_nodes),
            "edge_count": len(all_edges),
            "requested_max_nodes": max_nodes,
            "requested_max_edges": max_edges,
            "node_pages": 1,
            "edge_pages": 1,
            "nodes": nodes_data,
            "edges": edges_data,
        }

        duration_ms = round((time.time() - started_at) * 1000, 2)
        logger.info(
            "Graph data fetched: graph_id=%s mode=%s returned_nodes=%s returned_edges=%s "
            "truncated=%s duration_ms=%s",
            graph_id,
            mode,
            payload["returned_nodes"],
            payload["returned_edges"],
            truncated,
            duration_ms,
        )
        return payload

    def _serialize_node(self, node: Any, *, preview: bool) -> Dict[str, Any]:
        payload = {
            "uuid": _read_value(node, "uuid"),
            "name": _read_value(node, "name", ""),
            "labels": list(_read_value(node, "labels", []) or []),
            "created_at": str(_read_value(node, "created_at")) if _read_value(node, "created_at") else None,
        }
        if not preview:
            payload.update(
                {
                    "summary": _read_value(node, "summary", "") or "",
                    "attributes": dict(_read_value(node, "attributes", {}) or {}),
                }
            )
        return payload

    def _serialize_edge(
        self,
        edge: Any,
        *,
        node_map: Dict[str, str],
        preview: bool,
    ) -> Dict[str, Any]:
        source_node_uuid = _read_value(edge, "source_node_uuid")
        target_node_uuid = _read_value(edge, "target_node_uuid")
        payload = {
            "uuid": _read_value(edge, "uuid"),
            "name": _read_value(edge, "name", "") or "",
            "fact": _read_value(edge, "fact", "") or "",
            "fact_type": _read_value(edge, "fact_type", _read_value(edge, "name", "")) or "",
            "source_node_uuid": source_node_uuid,
            "target_node_uuid": target_node_uuid,
            "source_node_name": _read_value(edge, "source_node_name", node_map.get(str(source_node_uuid), "")) or node_map.get(str(source_node_uuid), ""),
            "target_node_name": _read_value(edge, "target_node_name", node_map.get(str(target_node_uuid), "")) or node_map.get(str(target_node_uuid), ""),
            "created_at": str(_read_value(edge, "created_at")) if _read_value(edge, "created_at") else None,
        }
        if preview:
            return payload

        payload.update(
            {
                "attributes": dict(_read_value(edge, "attributes", {}) or {}),
                "valid_at": str(_read_value(edge, "valid_at")) if _read_value(edge, "valid_at") else None,
                "invalid_at": str(_read_value(edge, "invalid_at")) if _read_value(edge, "invalid_at") else None,
                "expired_at": str(_read_value(edge, "expired_at")) if _read_value(edge, "expired_at") else None,
                "episodes": [str(item) for item in (_read_value(edge, "episodes", []) or [])],
            }
        )
        return payload

    def delete_graph(self, graph_id: str) -> None:
        """Delete one graph namespace."""
        self.graph_backend.delete_graph(graph_id)


__all__ = [
    "GraphBuilderService",
    "GraphInfo",
    "build_chunk_records",
    "summarize_graph_snapshot",
]
