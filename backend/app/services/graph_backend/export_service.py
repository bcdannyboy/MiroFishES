"""Neo4j-backed export helpers for graph build artifacts."""

from __future__ import annotations

from typing import Any

from .types import GraphExportSnapshot


_NODE_CORE_FIELDS = {
    "uuid",
    "name",
    "group_id",
    "created_at",
    "summary",
    "name_embedding",
}
_EDGE_CORE_FIELDS = {
    "uuid",
    "name",
    "group_id",
    "created_at",
    "fact",
    "fact_embedding",
    "episodes",
    "valid_at",
    "invalid_at",
    "expired_at",
}
_NODE_EXPORT_QUERY = """
MATCH (n:Entity)
WHERE n.group_id = $group_id
RETURN
  n.uuid AS uuid,
  n.name AS name,
  labels(n) AS labels,
  n.summary AS summary,
  n.created_at AS created_at,
  properties(n) AS properties
ORDER BY coalesce(n.name, n.uuid)
"""
_EDGE_EXPORT_QUERY = """
MATCH (source:Entity)-[r]->(target:Entity)
WHERE
  source.group_id = $group_id
  AND target.group_id = $group_id
  AND r.group_id = $group_id
WITH source, target, r, properties(r) AS edge_properties
RETURN
  r.uuid AS uuid,
  coalesce(r.name, type(r)) AS name,
  coalesce(r.fact, "") AS fact,
  type(r) AS fact_type,
  source.uuid AS source_node_uuid,
  target.uuid AS target_node_uuid,
  source.name AS source_node_name,
  target.name AS target_node_name,
  r.created_at AS created_at,
  r.valid_at AS valid_at,
  edge_properties['invalid_at'] AS invalid_at,
  edge_properties['expired_at'] AS expired_at,
  coalesce(edge_properties['episodes'], []) AS episodes,
  edge_properties AS properties
ORDER BY coalesce(r.created_at, "")
"""


def _normalize_record(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)
    if hasattr(record, "data"):
        return dict(record.data())
    return dict(record)


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    return str(value)


def _strip_core_fields(payload: dict[str, Any], core_fields: set[str]) -> dict[str, Any]:
    return {
        key: _normalize_value(value)
        for key, value in payload.items()
        if key not in core_fields
    }


class Neo4jGraphExportService:
    """Export normalized nodes and edges directly from Neo4j."""

    def export_graph_snapshot(
        self,
        *,
        namespace_id: str,
        neo4j_factory: Any,
    ) -> dict[str, Any]:
        driver = neo4j_factory.build_driver()
        try:
            node_records, _node_summary, _node_keys = driver.execute_query(
                _NODE_EXPORT_QUERY,
                {"group_id": namespace_id},
            )
            edge_records, _edge_summary, _edge_keys = driver.execute_query(
                _EDGE_EXPORT_QUERY,
                {"group_id": namespace_id},
            )
        finally:
            close = getattr(driver, "close", None)
            if callable(close):
                close()

        nodes = [self._serialize_node(_normalize_record(record)) for record in node_records]
        edges = [self._serialize_edge(_normalize_record(record)) for record in edge_records]
        snapshot = GraphExportSnapshot(
            graph_id=namespace_id,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )
        return snapshot.to_dict()

    def _serialize_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        properties = payload.get("properties", {}) or {}
        return {
            "uuid": payload.get("uuid"),
            "name": payload.get("name") or "",
            "labels": [_normalize_value(label) for label in payload.get("labels", []) or []],
            "summary": payload.get("summary") or "",
            "attributes": _strip_core_fields(dict(properties), _NODE_CORE_FIELDS),
            "created_at": _normalize_value(payload.get("created_at")),
        }

    def _serialize_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        properties = payload.get("properties", {}) or {}
        return {
            "uuid": payload.get("uuid"),
            "name": payload.get("name") or "",
            "fact": payload.get("fact") or "",
            "fact_type": payload.get("fact_type") or payload.get("name") or "",
            "source_node_uuid": payload.get("source_node_uuid"),
            "target_node_uuid": payload.get("target_node_uuid"),
            "source_node_name": payload.get("source_node_name") or "",
            "target_node_name": payload.get("target_node_name") or "",
            "attributes": _strip_core_fields(dict(properties), _EDGE_CORE_FIELDS),
            "created_at": _normalize_value(payload.get("created_at")),
            "valid_at": _normalize_value(payload.get("valid_at")),
            "invalid_at": _normalize_value(payload.get("invalid_at")),
            "expired_at": _normalize_value(payload.get("expired_at")),
            "episodes": [
                str(item) for item in (payload.get("episodes", []) or [])
            ],
        }
