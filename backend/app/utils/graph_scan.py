"""Deterministic graph scan helpers for artifact-backed read paths."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable

from ..services.forecast_graph import DEFAULT_ACTOR_TYPES, DEFAULT_ANALYTICAL_TYPES


_KNOWN_LABELS = {
    "".join(str(label).replace("_", " ").split()).lower(): str(label)
    for label in [*DEFAULT_ACTOR_TYPES, *DEFAULT_ANALYTICAL_TYPES, "Entity", "Node"]
}
_KNOWN_LABELS["runtimetransition"] = "RuntimeTransition"


def load_json_if_exists(path: str) -> dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, dict) else {}


def load_jsonl_if_exists(path: str) -> list[dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(dict(payload))
    return rows


def normalize_graph_ids(
    graph_id: str | None = None,
    graph_ids: Iterable[str] | None = None,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in [graph_id, *(graph_ids or [])]:
        token = normalize_text(candidate)
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    if not ordered:
        raise ValueError("graph_id or graph_ids is required")
    return ordered


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        token = normalize_text(value)
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def canonical_label(value: Any) -> str:
    token = normalize_text(value)
    if not token:
        return ""
    normalized = "".join(token.replace("_", " ").split()).lower()
    if normalized in _KNOWN_LABELS:
        return _KNOWN_LABELS[normalized]
    if token.isupper():
        return token.title()
    return token[0].upper() + token[1:]


def normalize_labels(
    labels: Iterable[Any] | None,
    *,
    object_type: Any = None,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _append(label: Any) -> None:
        normalized = canonical_label(label)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    for label in labels or []:
        _append(label)
    if not ordered:
        _append("Entity")
    elif "Entity" not in seen:
        ordered.insert(0, "Entity")
        seen.add("Entity")
    _append(object_type)
    return ordered


def stable_edge_uuid(
    *,
    name: str,
    fact: str,
    source_node_uuid: str,
    target_node_uuid: str,
) -> str:
    token = "|".join(
        [
            normalize_text(name),
            normalize_text(fact),
            normalize_text(source_node_uuid),
            normalize_text(target_node_uuid),
        ]
    )
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:12]
    return f"graph-edge-{digest}"


def stable_node_uuid(prefix: str, token: str) -> str:
    return f"{prefix}:{normalize_text(token)}"


def keyword_score(query: str, *texts: Any) -> int:
    query_text = normalize_text(query).lower()
    if not query_text:
        return 0
    keywords = [
        token
        for token in query_text.replace(",", " ").replace("\uFF0C", " ").split()
        if len(token) > 1
    ]
    score = 0
    for text in texts:
        haystack = normalize_text(text).lower()
        if not haystack:
            continue
        if query_text in haystack:
            score += 100
        for keyword in keywords:
            if keyword in haystack:
                score += 10
    return score


def sort_nodes(nodes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(node) for node in nodes],
        key=lambda item: (
            normalize_text(item.get("name")).lower(),
            normalize_text(item.get("uuid")),
        ),
    )


def sort_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(edge) for edge in edges],
        key=lambda item: (
            normalize_text(item.get("created_at")),
            normalize_text(item.get("name")).lower(),
            normalize_text(item.get("fact")).lower(),
            normalize_text(item.get("source_node_uuid")),
            normalize_text(item.get("target_node_uuid")),
            normalize_text(item.get("uuid")),
        ),
    )
