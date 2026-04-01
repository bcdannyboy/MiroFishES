"""Deterministic artifact-backed node and edge scans for Graphiti cutover reads."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...config import Config
from ...models.project import ProjectManager
from ...utils.graph_scan import (
    canonical_label,
    load_json_if_exists,
    load_jsonl_if_exists,
    normalize_graph_ids,
    normalize_labels,
    normalize_text,
    sort_edges,
    sort_nodes,
    stable_edge_uuid,
    stable_node_uuid,
    unique_strings,
)


class GraphScanService:
    """Scan graph artifacts and runtime transitions without vendor SDKs."""

    def __init__(self, *, simulation_data_dir: str | None = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def normalize_graph_ids(
        self,
        graph_id: str | None = None,
        graph_ids: list[str] | None = None,
    ) -> list[str]:
        return normalize_graph_ids(graph_id, graph_ids)

    def scan_nodes(
        self,
        *,
        graph_id: str | None,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for current_graph_id in self.normalize_graph_ids(graph_id, graph_ids):
            snapshot = self._load_graph_snapshot(
                current_graph_id,
                project_id=project_id,
            )
            for node in snapshot["nodes"]:
                key = node.get("uuid") or (
                    node.get("name"),
                    tuple(node.get("labels", [])),
                    node.get("summary"),
                )
                if key in seen:
                    continue
                seen.add(key)
                nodes.append(dict(node))
        return nodes

    def scan_edges(
        self,
        *,
        graph_id: str | None,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for current_graph_id in self.normalize_graph_ids(graph_id, graph_ids):
            snapshot = self._load_graph_snapshot(
                current_graph_id,
                project_id=project_id,
            )
            for edge in snapshot["edges"]:
                key = edge.get("uuid") or (
                    edge.get("name"),
                    edge.get("fact"),
                    edge.get("source_node_uuid"),
                    edge.get("target_node_uuid"),
                )
                if key in seen:
                    continue
                seen.add(key)
                edges.append(dict(edge))
        return edges

    def get_node(
        self,
        *,
        graph_id: str | None,
        node_uuid: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        target_uuid = normalize_text(node_uuid)
        if not target_uuid:
            return None
        for node in self.scan_nodes(
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        ):
            if normalize_text(node.get("uuid")) == target_uuid:
                return dict(node)
        return None

    def get_node_edges(
        self,
        *,
        graph_id: str | None,
        node_uuid: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        target_uuid = normalize_text(node_uuid)
        return [
            edge
            for edge in self.scan_edges(
                graph_id=graph_id,
                graph_ids=graph_ids,
                project_id=project_id,
            )
            if edge.get("source_node_uuid") == target_uuid
            or edge.get("target_node_uuid") == target_uuid
        ]

    def _load_graph_snapshot(
        self,
        graph_id: str,
        *,
        project_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        runtime_snapshot = self._load_runtime_graph_snapshot(graph_id)
        if runtime_snapshot is not None:
            return runtime_snapshot
        project_snapshot = self._load_project_graph_snapshot(
            graph_id,
            project_id=project_id,
        )
        if project_snapshot is not None:
            return project_snapshot
        return {"nodes": [], "edges": []}

    def _load_project_graph_snapshot(
        self,
        graph_id: str,
        *,
        project_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]] | None:
        payload = self._find_project_graph_index(graph_id, project_id=project_id)
        if not payload:
            return None

        raw_nodes = list(payload.get("entities") or []) + list(
            payload.get("analytical_objects") or []
        )
        nodes: list[dict[str, Any]] = []
        node_map: dict[str, dict[str, Any]] = {}
        for raw_node in raw_nodes:
            node_uuid = normalize_text(raw_node.get("uuid"))
            if not node_uuid:
                continue
            node = {
                "uuid": node_uuid,
                "name": normalize_text(raw_node.get("name")),
                "labels": normalize_labels(
                    raw_node.get("labels"),
                    object_type=raw_node.get("object_type"),
                ),
                "summary": normalize_text(raw_node.get("summary")),
                "attributes": dict(raw_node.get("attributes") or {}),
                "created_at": raw_node.get("created_at"),
                "graph_id": graph_id,
                "source_kind": "project_graph_entity_index",
            }
            if raw_node.get("object_type"):
                node["attributes"].setdefault(
                    "object_type",
                    canonical_label(raw_node.get("object_type")),
                )
            if raw_node.get("provenance"):
                node["attributes"].setdefault(
                    "provenance",
                    dict(raw_node.get("provenance") or {}),
                )
            nodes.append(node)
            node_map[node_uuid] = node

        edges: list[dict[str, Any]] = []
        for raw_node in raw_nodes:
            owner_uuid = normalize_text(raw_node.get("uuid"))
            if not owner_uuid:
                continue
            for raw_edge in raw_node.get("related_edges") or []:
                direction = normalize_text(raw_edge.get("direction")).lower()
                if direction == "incoming":
                    source_uuid = normalize_text(raw_edge.get("source_node_uuid")) or owner_uuid
                    target_uuid = owner_uuid
                else:
                    source_uuid = owner_uuid
                    target_uuid = normalize_text(raw_edge.get("target_node_uuid")) or owner_uuid

                name = normalize_text(raw_edge.get("edge_name") or raw_edge.get("name"))
                fact = normalize_text(raw_edge.get("fact"))
                edge_uuid = normalize_text(raw_edge.get("uuid")) or stable_edge_uuid(
                    name=name,
                    fact=fact,
                    source_node_uuid=source_uuid,
                    target_node_uuid=target_uuid,
                )
                attributes = dict(raw_edge.get("attributes") or {})
                if raw_edge.get("provenance"):
                    attributes["provenance"] = dict(raw_edge.get("provenance") or {})
                edges.append(
                    {
                        "uuid": edge_uuid,
                        "name": name,
                        "fact": fact,
                        "source_node_uuid": source_uuid,
                        "target_node_uuid": target_uuid,
                        "source_node_name": node_map.get(source_uuid, {}).get("name", ""),
                        "target_node_name": node_map.get(target_uuid, {}).get("name", ""),
                        "attributes": attributes,
                        "created_at": raw_edge.get("created_at"),
                        "valid_at": raw_edge.get("valid_at"),
                        "invalid_at": raw_edge.get("invalid_at"),
                        "expired_at": raw_edge.get("expired_at"),
                        "episodes": list(raw_edge.get("episodes") or []),
                        "graph_id": graph_id,
                        "source_kind": "project_graph_entity_index",
                    }
                )

        return {
            "nodes": sort_nodes(nodes),
            "edges": sort_edges(edges),
        }

    def _load_runtime_graph_snapshot(
        self,
        graph_id: str,
    ) -> dict[str, list[dict[str, Any]]] | None:
        run_dir = self._find_runtime_run_dir(graph_id)
        if run_dir is None:
            return None

        base_snapshot = load_json_if_exists(
            os.path.join(run_dir, "runtime_graph_base_snapshot.json")
        )
        transitions = load_jsonl_if_exists(
            os.path.join(run_dir, "runtime_graph_updates.jsonl")
        )

        nodes: list[dict[str, Any]] = []
        node_map: dict[str, dict[str, Any]] = {}

        def add_node(payload: dict[str, Any]) -> None:
            node_uuid = normalize_text(payload.get("uuid"))
            if not node_uuid or node_uuid in node_map:
                return
            node = dict(payload)
            nodes.append(node)
            node_map[node_uuid] = node

        for actor in base_snapshot.get("actors") or []:
            add_node(
                {
                    "uuid": normalize_text(actor.get("entity_uuid")),
                    "name": normalize_text(actor.get("entity_name")),
                    "labels": normalize_labels(
                        ["Entity", actor.get("entity_type") or "Person"]
                    ),
                    "summary": normalize_text(
                        actor.get("summary") or actor.get("worldview_summary")
                    ),
                    "attributes": {
                        "citation_ids": unique_strings(actor.get("citation_ids") or []),
                        "source_unit_ids": unique_strings(
                            actor.get("source_unit_ids") or []
                        ),
                        "linked_object_uuids": unique_strings(
                            actor.get("linked_object_uuids") or []
                        ),
                        "stance_hint": normalize_text(actor.get("stance_hint")),
                        "sentiment_bias_hint": normalize_text(
                            actor.get("sentiment_bias_hint")
                        ),
                    },
                    "created_at": None,
                    "graph_id": graph_id,
                    "source_kind": "runtime_graph_base_snapshot",
                }
            )

        for analytical_object in base_snapshot.get("analytical_objects") or []:
            add_node(
                {
                    "uuid": normalize_text(analytical_object.get("uuid")),
                    "name": normalize_text(analytical_object.get("name")),
                    "labels": normalize_labels(
                        analytical_object.get("labels"),
                        object_type=analytical_object.get("object_type"),
                    ),
                    "summary": normalize_text(analytical_object.get("summary")),
                    "attributes": {
                        **dict(analytical_object.get("attributes") or {}),
                        "object_type": canonical_label(
                            analytical_object.get("object_type")
                        ),
                        "provenance": dict(analytical_object.get("provenance") or {}),
                    },
                    "created_at": analytical_object.get("created_at"),
                    "graph_id": graph_id,
                    "source_kind": "runtime_graph_base_snapshot",
                }
            )

        edges: list[dict[str, Any]] = []
        for transition in transitions:
            transition_id = normalize_text(transition.get("transition_id"))
            if not transition_id:
                continue
            agent = dict(transition.get("agent") or {})
            payload = dict(transition.get("payload") or {})
            provenance = dict(transition.get("provenance") or {})

            source_uuid = normalize_text(agent.get("entity_uuid")) or stable_node_uuid(
                "runtime-agent",
                agent.get("agent_name") or transition_id,
            )
            if source_uuid not in node_map:
                add_node(
                    {
                        "uuid": source_uuid,
                        "name": normalize_text(
                            agent.get("agent_name") or agent.get("entity_uuid")
                        ),
                        "labels": normalize_labels(
                            ["Entity", agent.get("entity_type") or "Person"]
                        ),
                        "summary": "",
                        "attributes": {
                            "source_kind": "runtime_transition_agent",
                        },
                        "created_at": None,
                        "graph_id": graph_id,
                        "source_kind": "runtime_transition_agent",
                    }
                )

            target_uuid = unique_strings(provenance.get("graph_object_uuids") or [])
            target_uuid = target_uuid[0] if target_uuid else stable_node_uuid(
                "runtime-transition",
                transition_id,
            )
            if target_uuid not in node_map:
                target_name = normalize_text(
                    payload.get("event_name")
                    or payload.get("intervention_name")
                    or transition.get("human_readable")
                )
                add_node(
                    {
                        "uuid": target_uuid,
                        "name": target_name or target_uuid,
                        "labels": normalize_labels(
                            ["Entity", "RuntimeTransition", transition.get("transition_type")]
                        ),
                        "summary": normalize_text(transition.get("human_readable")),
                        "attributes": {
                            "history_kind": "runtime_transition",
                            "transition_type": normalize_text(
                                transition.get("transition_type")
                            ),
                            "payload": payload,
                        },
                        "created_at": transition.get("timestamp"),
                        "graph_id": graph_id,
                        "source_kind": "runtime_graph_transition",
                    }
                )

            edges.append(
                {
                    "uuid": transition_id,
                    "name": normalize_text(
                        transition.get("transition_type")
                    ).upper(),
                    "fact": normalize_text(transition.get("human_readable")),
                    "source_node_uuid": source_uuid,
                    "target_node_uuid": target_uuid,
                    "source_node_name": node_map.get(source_uuid, {}).get("name", ""),
                    "target_node_name": node_map.get(target_uuid, {}).get("name", ""),
                    "attributes": {
                        "history_kind": "runtime_transition",
                        "platform": normalize_text(transition.get("platform")),
                        "round_num": transition.get("round_num"),
                        "payload": payload,
                        "provenance": provenance,
                        "source_artifact": normalize_text(
                            transition.get("source_artifact")
                        ),
                    },
                    "created_at": transition.get("timestamp"),
                    "valid_at": transition.get("timestamp"),
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": [],
                    "graph_id": graph_id,
                    "source_kind": "runtime_graph_transition",
                }
            )

        return {
            "nodes": sort_nodes(nodes),
            "edges": sort_edges(edges),
        }

    def _find_project_graph_index(
        self,
        graph_id: str,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        candidates: list[Path] = []
        projects_root = Path(ProjectManager.PROJECTS_DIR)
        if project_id:
            candidates.append(projects_root / project_id)
        elif projects_root.exists():
            candidates.extend(
                path for path in projects_root.iterdir() if path.is_dir()
            )

        for project_dir in candidates:
            payload = load_json_if_exists(str(project_dir / "graph_entity_index.json"))
            if payload.get("graph_id") == graph_id:
                return payload
        return {}

    def _find_runtime_run_dir(self, runtime_graph_id: str) -> str | None:
        root = Path(self.simulation_data_dir)
        if not root.exists():
            return None
        for dirpath, _dirnames, filenames in os.walk(root):
            if "run_manifest.json" not in filenames:
                continue
            manifest = load_json_if_exists(os.path.join(dirpath, "run_manifest.json"))
            resolved = load_json_if_exists(os.path.join(dirpath, "resolved_config.json"))
            if (
                manifest.get("runtime_graph_id") == runtime_graph_id
                or resolved.get("runtime_graph_id") == runtime_graph_id
            ):
                return dirpath
        return None
