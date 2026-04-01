"""Graphiti ingestion helpers for base graph construction."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .errors import GraphBackendConfigurationError, GraphBackendDependencyError
from .types import CompiledOntology


def _run_async(coroutine: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def _extract_episode_id(result: Any, fallback: str) -> str:
    if result is None:
        return fallback
    if isinstance(result, dict):
        return str(result.get("uuid") or result.get("uuid_") or fallback)
    for attr_name in ("uuid", "uuid_", "episode_id", "id"):
        value = getattr(result, attr_name, None)
        if value:
            return str(value)
    return fallback


@dataclass
class GraphitiIngestionService:
    """Batch Graphiti episode ingestion with application-level progress callbacks."""

    indices_initialized: bool = False

    def ingest_text_batches(
        self,
        *,
        namespace_id: str,
        chunks: list[str],
        batch_size: int,
        progress_callback: Callable[[str, float], None] | None,
        graphiti_factory: Any,
        compiled_ontology: CompiledOntology | None,
    ) -> list[str]:
        if compiled_ontology is None:
            raise GraphBackendConfigurationError(
                "Ontology must be registered before ingesting graph episodes"
            )
        if not chunks:
            return []

        graphiti = graphiti_factory.build_client()
        if not self.indices_initialized and hasattr(graphiti, "build_indices_and_constraints"):
            _run_async(graphiti.build_indices_and_constraints())
            self.indices_initialized = True

        if not hasattr(graphiti, "add_episode"):
            raise GraphBackendDependencyError(
                "The installed Graphiti runtime does not expose `add_episode`"
            )

        resolved_batch_size = max(1, int(batch_size))
        episode_ids: list[str] = []
        total_batches = (len(chunks) + resolved_batch_size - 1) // resolved_batch_size
        episode_type = graphiti_factory.get_episode_type("text")

        for batch_offset in range(0, len(chunks), resolved_batch_size):
            batch = chunks[batch_offset:batch_offset + resolved_batch_size]
            batch_index = batch_offset // resolved_batch_size + 1
            for chunk in batch:
                episode_number = len(episode_ids) + 1
                episode_name = f"{namespace_id}-episode-{episode_number:04d}"
                result = _run_async(
                    graphiti.add_episode(
                        name=episode_name,
                        episode_body=chunk,
                        source=episode_type,
                        source_description="MiroFishES project chunk",
                        reference_time=datetime.now(timezone.utc),
                        group_id=namespace_id,
                        entity_types=compiled_ontology.entity_types or None,
                        edge_types=compiled_ontology.edge_types or None,
                        edge_type_map=compiled_ontology.edge_type_map or None,
                    )
                )
                episode_ids.append(_extract_episode_id(result, fallback=episode_name))

            if progress_callback:
                progress_callback(
                    f"Sent batch {batch_index}/{total_batches} ({len(batch)} chunks)...",
                    batch_index / total_batches,
                )

        return episode_ids

    def wait_for_episode_processing(
        self,
        *,
        namespace_id: str,
        episode_ids: list[str],
        progress_callback: Callable[[str, float], None] | None,
        timeout: int | None,
    ) -> None:
        del namespace_id, timeout
        if progress_callback:
            if episode_ids:
                progress_callback(
                    f"Graphiti ingestion completed for {len(episode_ids)} episodes.",
                    1.0,
                )
            else:
                progress_callback("No waiting required (no episodes)", 1.0)
