"""Graphiti ingestion helpers for live runtime graph events."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .errors import GraphBackendDependencyError


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
class GraphitiRuntimeEventIngestor:
    """Batch structured runtime transitions into Graphiti text episodes."""

    indices_initialized: bool = False

    def ingest_runtime_events(
        self,
        *,
        namespace_id: str,
        events: list[dict[str, Any]],
        batch_size: int,
        graphiti_factory: Any,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> list[str]:
        if not events:
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
        total_batches = (len(events) + resolved_batch_size - 1) // resolved_batch_size
        episode_type = graphiti_factory.get_episode_type("text")
        episode_ids: list[str] = []

        for batch_offset in range(0, len(events), resolved_batch_size):
            batch = events[batch_offset:batch_offset + resolved_batch_size]
            batch_index = batch_offset // resolved_batch_size + 1
            episode_name = f"{namespace_id}-runtime-batch-{batch_index:04d}"
            episode_body = "\n".join(
                json.dumps(dict(event), ensure_ascii=False, sort_keys=True)
                for event in batch
            )
            result = _run_async(
                graphiti.add_episode(
                    name=episode_name,
                    episode_body=episode_body,
                    source=episode_type,
                    source_description="MiroFishES runtime event batch",
                    reference_time=datetime.now(timezone.utc),
                    group_id=namespace_id,
                )
            )
            episode_ids.append(_extract_episode_id(result, fallback=episode_name))

            if progress_callback:
                progress_callback(
                    f"Sent runtime batch {batch_index}/{total_batches} ({len(batch)} events)...",
                    batch_index / total_batches,
                )

        return episode_ids
