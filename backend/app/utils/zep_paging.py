"""Zep Graph pagination helpers.

The Zep node/edge list APIs use UUID cursor pagination. This module wraps the
page-turning logic, including per-page retries, and returns complete lists to
callers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from zep_cloud import InternalServerError
from zep_cloud.client import Zep

from .logger import get_logger

logger = get_logger('mirofish.zep_paging')

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0  # seconds, doubles each retry


@dataclass
class PageFetchResult:
    """One paginated graph collection fetch plus pagination metadata."""

    items: list[Any]
    page_count: int
    truncated: bool = False
    has_more: bool = False


def _fetch_page_with_retry(
    api_call: Callable[..., list[Any]],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
    **kwargs: Any,
) -> list[Any]:
    """Retry a single page request with exponential backoff on transient I/O errors."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_exception: Exception | None = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            return api_call(*args, **kwargs)
        except (ConnectionError, TimeoutError, OSError, InternalServerError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Zep {page_description} attempt {attempt + 1} failed: {str(e)[:100]}, retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Zep {page_description} failed after {max_retries} attempts: {str(e)}")

    assert last_exception is not None
    raise last_exception


def _fetch_paginated_items(
    api_call: Callable[..., list[Any]],
    graph_id: str,
    *,
    page_size: int,
    max_items: int | None,
    max_retries: int,
    retry_delay: float,
    page_description_prefix: str,
    item_label: str,
) -> PageFetchResult:
    """Fetch one paginated Zep collection while tracking truncation metadata."""
    if max_items is not None and max_items < 0:
        raise ValueError("max_items must be >= 0 when provided")

    all_items: list[Any] = []
    cursor: str | None = None
    page_num = 0
    truncated = False
    has_more = False

    while True:
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor

        page_num += 1
        batch = _fetch_page_with_retry(
            api_call,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=(
                f"{page_description_prefix} page {page_num} (graph={graph_id})"
            ),
            **kwargs,
        )
        if not batch:
            break

        remaining = None if max_items is None else max_items - len(all_items)
        if remaining is not None and remaining <= 0:
            truncated = True
            has_more = True
            break

        if remaining is not None and len(batch) >= remaining:
            all_items.extend(batch[:remaining])
            has_more = len(batch) > remaining or len(batch) == page_size
            truncated = has_more
            if truncated:
                logger.warning(
                    "%s count reached limit (%s), stopping pagination for graph %s",
                    item_label,
                    max_items,
                    graph_id,
                )
            break

        all_items.extend(batch)
        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning(
                "%s missing uuid field, stopping pagination at %s items",
                item_label,
                len(all_items),
            )
            break

    return PageFetchResult(
        items=all_items,
        page_count=page_num,
        truncated=truncated,
        has_more=has_more,
    )


def fetch_node_window(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> PageFetchResult:
    """Fetch graph nodes page by page with explicit truncation metadata."""
    return _fetch_paginated_items(
        client.graph.node.get_by_graph_id,
        graph_id,
        page_size=page_size,
        max_items=max_items,
        max_retries=max_retries,
        retry_delay=retry_delay,
        page_description_prefix="fetch nodes",
        item_label="Node",
    )


def fetch_all_nodes(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int | None = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """Fetch graph nodes page by page, returning at most `max_items` entries."""
    return fetch_node_window(
        client,
        graph_id,
        page_size=page_size,
        max_items=max_items,
        max_retries=max_retries,
        retry_delay=retry_delay,
    ).items


def fetch_edge_window(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> PageFetchResult:
    """Fetch graph edges with optional caps and explicit truncation metadata."""
    return _fetch_paginated_items(
        client.graph.edge.get_by_graph_id,
        graph_id,
        page_size=page_size,
        max_items=max_items,
        max_retries=max_retries,
        retry_delay=retry_delay,
        page_description_prefix="fetch edges",
        item_label="Edge",
    )


def fetch_all_edges(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """Fetch all graph edges through pagination with per-page retries."""
    return fetch_edge_window(
        client,
        graph_id,
        page_size=page_size,
        max_items=max_items,
        max_retries=max_retries,
        retry_delay=retry_delay,
    ).items
