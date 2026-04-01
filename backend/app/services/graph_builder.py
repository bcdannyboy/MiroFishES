"""
Graph building service.
Endpoint 2: build a standalone graph with the Zep API.
"""

import os
import uuid
import time
import copy
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from zep_cloud.client import Zep
from zep_cloud import EpisodeData, EntityEdgeSourceTarget

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.zep_paging import (
    fetch_all_nodes,
    fetch_all_edges,
    fetch_node_window,
    fetch_edge_window,
)
from .text_processor import TextProcessor
from .forecast_graph import build_chunk_records, summarize_graph_snapshot

logger = get_logger('mirofish.graph_builder')


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


class GraphBuilderService:
    """
    Graph building service.
    Responsible for building the knowledge graph through the Zep API.
    """
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
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")
        
        self.client = Zep(api_key=self.api_key)
        self.task_manager = TaskManager()
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFishES Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: Optional[int] = None
    ) -> str:
        """
        Build a graph asynchronously.
        
        Args:
            text: Input text
            ontology: Ontology definition from endpoint 1
            graph_name: Graph name
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap size
            batch_size: Number of chunks sent per batch
            
        Returns:
            Task ID
        """
        # Create the task
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        # Run the build in a background thread
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
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
        batch_size: int
    ):
        """Worker thread for graph building."""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph build..."
            )
            
            # 1. Create the graph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}"
            )
            
            # 2. Set the ontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology configured"
            )
            
            # 3. Split the text
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks"
            )
            
            # 4. Send data in batches
            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),  # 20-60%
                    message=msg
                )
            )
            
            # 5. Wait for Zep processing to finish
            self.task_manager.update_task(
                task_id,
                progress=60,
                message="Waiting for Zep to process data..."
            )
            
            self._wait_for_episodes(
                graph_id,
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),  # 60-90%
                    message=msg
                )
            )
            
            # 6. Fetch graph information
            self.task_manager.update_task(
                task_id,
                progress=90,
                message="Fetching graph information..."
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            # Complete
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def create_graph(self, name: str) -> str:
        """Create a Zep graph."""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="MiroFishES Social Simulation Graph"
        )
        
        return graph_id
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Set the graph ontology."""
        import warnings
        from typing import Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        
        # Suppress the Pydantic v2 warning about Field(default=None).
        # The Zep SDK requires this pattern; the warning comes from dynamic class creation.
        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        
        # Zep reserved names cannot be used as attribute names
        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}
        
        def safe_attr_name(attr_name: str) -> str:
            """Convert a reserved name into a safe attribute name."""
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name
        
        # Dynamically create entity types
        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            
            # Build the attribute dictionary and type annotations required by Pydantic v2
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # Use a safe attribute name
                attr_desc = attr_def.get("description", attr_name)
                # The Zep API requires Field descriptions
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]  # Type annotation
            
            attrs["__annotations__"] = annotations
            
            # Dynamically create the class
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class
        
        # Dynamically create edge types
        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            
            # Build the attribute dictionary and type annotations
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # Use a safe attribute name
                attr_desc = attr_def.get("description", attr_name)
                # The Zep API requires Field descriptions
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]  # Edge attributes use `str`
            
            attrs["__annotations__"] = annotations
            
            # Dynamically create the class
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description
            
            # Build source_targets
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )
            
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)
        
        # Configure the ontology through the Zep API
        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )
    
    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        max_inflight_batches: Optional[int] = None,
    ) -> List[str]:
        """Add text to the graph in batches and return all episode UUIDs."""
        total_chunks = len(chunks)
        if total_chunks == 0:
            return []

        batch_plan = self._resolve_batch_plan(total_chunks, requested_batch_size=batch_size)
        effective_batch_size = batch_plan["batch_size"]
        effective_max_inflight = min(
            max_inflight_batches or batch_plan["max_inflight_batches"],
            self.MAX_INFLIGHT_BATCHES,
        )
        batches = [
            chunks[index:index + effective_batch_size]
            for index in range(0, total_chunks, effective_batch_size)
        ]
        total_batches = len(batches)
        episode_uuids_by_batch: Dict[int, List[str]] = {}
        completed_batches = 0

        with ThreadPoolExecutor(max_workers=effective_max_inflight) as executor:
            future_map = {
                executor.submit(
                    self._send_text_batch,
                    graph_id=graph_id,
                    batch_index=batch_index,
                    batch_chunks=batch_chunks,
                ): batch_index
                for batch_index, batch_chunks in enumerate(batches, start=1)
            }
            for future in as_completed(future_map):
                batch_index = future_map[future]
                try:
                    episode_uuids_by_batch[batch_index] = future.result()
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Batch {batch_index} failed to send: {str(e)}", 0)
                    raise
                completed_batches += 1
                if progress_callback:
                    progress_callback(
                        (
                            f"Sent batch {batch_index}/{total_batches} "
                            f"({len(batches[batch_index - 1])} chunks)..."
                        ),
                        completed_batches / total_batches,
                    )

        episode_uuids: List[str] = []
        for batch_index in range(1, total_batches + 1):
            episode_uuids.extend(episode_uuids_by_batch.get(batch_index, []))
        return episode_uuids

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
            return {
                "batch_size": max(1, min(int(requested_batch_size), self.MAX_BATCH_SIZE)),
                "max_inflight_batches": min(
                    self.MAX_INFLIGHT_BATCHES,
                    max(1, (total_chunks + max(int(requested_batch_size), 1) - 1) // max(int(requested_batch_size), 1)),
                ),
            }

        if total_chunks <= 6:
            return {"batch_size": self.DEFAULT_BATCH_SIZE, "max_inflight_batches": 1}
        if total_chunks <= 24:
            return {"batch_size": 6, "max_inflight_batches": 2}
        if total_chunks <= 80:
            return {"batch_size": 10, "max_inflight_batches": 3}
        return {"batch_size": self.MAX_BATCH_SIZE, "max_inflight_batches": self.MAX_INFLIGHT_BATCHES}

    def _send_text_batch(
        self,
        *,
        graph_id: str,
        batch_index: int,
        batch_chunks: List[str],
    ) -> List[str]:
        """Send one text batch to Zep and return its episode UUIDs."""
        episodes = [EpisodeData(data=chunk, type="text") for chunk in batch_chunks]
        batch_result = self.client.graph.add_batch(graph_id=graph_id, episodes=episodes)
        episode_uuids = []
        if batch_result and isinstance(batch_result, list):
            for episode in batch_result:
                episode_uuid = getattr(episode, 'uuid_', None) or getattr(episode, 'uuid', None)
                if episode_uuid:
                    episode_uuids.append(episode_uuid)
        return episode_uuids
    
    def _wait_for_episodes(
        self,
        graph_id: str,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: Optional[int] = None
    ):
        """Wait for all episodes to finish processing by polling their processed status."""
        if not episode_uuids:
            if progress_callback:
                progress_callback("No waiting required (no episodes)", 1.0)
            return
        
        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)
        poll_interval = self.DEFAULT_WAIT_POLL_INTERVAL_SECONDS
        
        if progress_callback:
            progress_callback(f"Waiting for {total_episodes} text chunks to be processed...", 0)
        
        while pending_episodes:
            if timeout is not None and time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        f"Some text chunks timed out; completed {completed_count}/{total_episodes}",
                        completed_count / total_episodes
                    )
                raise TimeoutError(
                    "Timed out waiting for Zep to process episodes "
                    f"({completed_count}/{total_episodes} completed)"
                )

            processed_uuids = set()
            try:
                response = self.client.graph.episode.get_by_graph_id(
                    graph_id,
                    lastn=total_episodes,
                )
                response_episodes = getattr(response, "episodes", None) or []
                processed_uuids = {
                    getattr(episode, 'uuid_', None) or getattr(episode, 'uuid', None)
                    for episode in response_episodes
                    if getattr(episode, 'processed', False)
                }
                processed_uuids.discard(None)
            except Exception as e:
                logger.warning(
                    "Graph-level episode polling failed for graph %s: %s",
                    graph_id,
                    e,
                )
                processed_uuids = set()

            before_count = len(pending_episodes)
            pending_episodes -= processed_uuids
            completed_count = total_episodes - len(pending_episodes)
            if len(pending_episodes) < before_count:
                poll_interval = self.DEFAULT_WAIT_POLL_INTERVAL_SECONDS
            else:
                poll_interval = min(
                    poll_interval * 1.5,
                    self.MAX_WAIT_POLL_INTERVAL_SECONDS,
                )
            
            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    f"Zep processing... {completed_count}/{total_episodes} completed, {len(pending_episodes)} pending ({elapsed}s)",
                    completed_count / total_episodes if total_episodes > 0 else 0
                )
            
            if pending_episodes:
                time.sleep(poll_interval)
        
        if progress_callback:
            progress_callback(f"Processing complete: {completed_count}/{total_episodes}", 1.0)
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """Fetch graph information."""
        snapshot = self.get_graph_snapshot(graph_id)
        return GraphInfo(
            graph_id=graph_id,
            node_count=snapshot["node_count"],
            edge_count=snapshot["edge_count"],
            entity_types=snapshot["entity_types"],
        )

    def get_graph_snapshot(self, graph_id: str) -> Dict[str, Any]:
        """Fetch an exact graph snapshot for build summaries and local indexes."""
        nodes = fetch_all_nodes(self.client, graph_id, max_items=None)
        edges = fetch_all_edges(self.client, graph_id, max_items=None)
        node_map = {
            getattr(node, "uuid_", None) or getattr(node, "uuid", None): node.name or ""
            for node in nodes
        }
        snapshot = {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": [self._serialize_node(node, preview=False) for node in nodes],
            "edges": [
                self._serialize_edge(edge, node_map=node_map, preview=False)
                for edge in edges
            ],
        }
        snapshot["graph_counts"] = summarize_graph_snapshot(snapshot)
        snapshot["entity_types"] = snapshot["graph_counts"]["entity_types"]
        return snapshot
    
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
        """Normalize optional graph caps without allowing non-positive values."""
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
        """Serve preview graph payloads via a short-lived single-flight cache."""
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
        """Fetch graph collections with explicit truncation metadata."""
        started_at = time.time()
        node_window = fetch_node_window(
            self.client,
            graph_id,
            max_items=max_nodes,
        )
        edge_window = fetch_edge_window(
            self.client,
            graph_id,
            max_items=max_edges,
        )
        node_map = {
            getattr(node, "uuid_", None) or getattr(node, "uuid", None): node.name or ""
            for node in node_window.items
        }

        preview_mode = mode == "preview"
        nodes_data = [
            self._serialize_node(node, preview=preview_mode)
            for node in node_window.items
        ]
        edges_data = [
            self._serialize_edge(edge, node_map=node_map, preview=preview_mode)
            for edge in edge_window.items
        ]

        truncated = node_window.truncated or edge_window.truncated
        payload = {
            "graph_id": graph_id,
            "mode": mode,
            "truncated": truncated,
            "returned_nodes": len(nodes_data),
            "returned_edges": len(edges_data),
            "total_nodes": len(nodes_data),
            "total_edges": len(edges_data),
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
            "requested_max_nodes": max_nodes,
            "requested_max_edges": max_edges,
            "node_pages": node_window.page_count,
            "edge_pages": edge_window.page_count,
            "nodes": nodes_data,
            "edges": edges_data,
        }

        duration_ms = round((time.time() - started_at) * 1000, 2)
        logger.info(
            "Graph data fetched: graph_id=%s mode=%s returned_nodes=%s returned_edges=%s "
            "truncated=%s node_pages=%s edge_pages=%s duration_ms=%s",
            graph_id,
            mode,
            payload["returned_nodes"],
            payload["returned_edges"],
            truncated,
            node_window.page_count,
            edge_window.page_count,
            duration_ms,
        )
        return payload

    def _serialize_node(self, node: Any, *, preview: bool) -> Dict[str, Any]:
        """Serialize one node, omitting heavyweight fields in preview mode."""
        created_at = getattr(node, 'created_at', None)
        payload = {
            "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', None),
            "name": node.name,
            "labels": node.labels or [],
            "created_at": str(created_at) if created_at else None,
        }
        if not preview:
            payload.update(
                {
                    "summary": node.summary or "",
                    "attributes": node.attributes or {},
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
        """Serialize one edge, omitting heavyweight fields in preview mode."""
        created_at = getattr(edge, 'created_at', None)
        payload = {
            "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None),
            "name": edge.name or "",
            "fact": edge.fact or "",
            "fact_type": getattr(edge, 'fact_type', None) or edge.name or "",
            "source_node_uuid": edge.source_node_uuid,
            "target_node_uuid": edge.target_node_uuid,
            "source_node_name": node_map.get(edge.source_node_uuid, ""),
            "target_node_name": node_map.get(edge.target_node_uuid, ""),
            "created_at": str(created_at) if created_at else None,
        }
        if preview:
            return payload

        valid_at = getattr(edge, 'valid_at', None)
        invalid_at = getattr(edge, 'invalid_at', None)
        expired_at = getattr(edge, 'expired_at', None)
        episodes = getattr(edge, 'episodes', None) or getattr(edge, 'episode_ids', None)
        if episodes and not isinstance(episodes, list):
            episodes = [str(episodes)]
        elif episodes:
            episodes = [str(item) for item in episodes]

        payload.update(
            {
                "attributes": edge.attributes or {},
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            }
        )
        return payload
    
    def delete_graph(self, graph_id: str):
        """Delete a graph."""
        self.client.graph.delete(graph_id=graph_id)
