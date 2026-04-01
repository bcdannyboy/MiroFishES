"""Graph-native entity reader built on deterministic graph scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..models.project import ProjectManager
from ..utils.logger import get_logger
from .forecast_graph import is_analytical_type
from .graph_backend.scan_service import GraphScanService

logger = get_logger("mirofish.graph_entity_reader")


@dataclass
class EntityNode:
    """Entity node data structure."""

    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection."""

    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [entity.to_dict() for entity in self.entities],
            "entity_types": sorted(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


def build_filtered_entities_from_payloads(
    all_nodes: List[Dict[str, Any]],
    all_edges: Optional[List[Dict[str, Any]]] = None,
    *,
    defined_entity_types: Optional[List[str]] = None,
    enrich_with_edges: bool = True,
) -> FilteredEntities:
    """Build one filtered-entity payload from serialized node and edge collections."""

    total_count = len(all_nodes)
    serialized_edges = all_edges or []
    node_map = {node["uuid"]: node for node in all_nodes if node.get("uuid")}
    filtered_entities: List[EntityNode] = []
    entity_types_found: Set[str] = set()

    for node in all_nodes:
        labels = node.get("labels", [])
        custom_labels = [label for label in labels if label not in ["Entity", "Node"]]
        if not custom_labels:
            continue

        if defined_entity_types:
            matching_labels = [
                label for label in custom_labels if label in defined_entity_types
            ]
            if not matching_labels:
                continue
            entity_type = matching_labels[0]
        else:
            actor_labels = [
                label for label in custom_labels if not is_analytical_type(label)
            ]
            if not actor_labels:
                continue
            entity_type = actor_labels[0]

        entity_types_found.add(entity_type)
        entity = EntityNode(
            uuid=node["uuid"],
            name=node.get("name", ""),
            labels=list(labels),
            summary=node.get("summary", ""),
            attributes=dict(node.get("attributes", {})),
        )

        if enrich_with_edges:
            related_edges = []
            related_node_uuids = set()
            for edge in serialized_edges:
                if edge.get("source_node_uuid") == node["uuid"]:
                    related_edges.append(
                        {
                            "direction": "outgoing",
                            "edge_name": edge.get("name", ""),
                            "fact": edge.get("fact", ""),
                            "target_node_uuid": edge.get("target_node_uuid"),
                        }
                    )
                    related_node_uuids.add(edge.get("target_node_uuid"))
                elif edge.get("target_node_uuid") == node["uuid"]:
                    related_edges.append(
                        {
                            "direction": "incoming",
                            "edge_name": edge.get("name", ""),
                            "fact": edge.get("fact", ""),
                            "source_node_uuid": edge.get("source_node_uuid"),
                        }
                    )
                    related_node_uuids.add(edge.get("source_node_uuid"))

            entity.related_edges = related_edges
            entity.related_nodes = [
                {
                    "uuid": node_map[related_uuid]["uuid"],
                    "name": node_map[related_uuid].get("name", ""),
                    "labels": node_map[related_uuid].get("labels", []),
                    "summary": node_map[related_uuid].get("summary", ""),
                }
                for related_uuid in sorted(related_node_uuids)
                if related_uuid in node_map
            ]

        filtered_entities.append(entity)

    return FilteredEntities(
        entities=filtered_entities,
        entity_types=entity_types_found,
        total_count=total_count,
        filtered_count=len(filtered_entities),
    )


class GraphEntityReader:
    """Graph-backed entity reader for merged base/runtime namespaces."""

    def __init__(
        self,
        *,
        graph_scan_service: Optional[GraphScanService] = None,
    ) -> None:
        self.graph_scan_service = graph_scan_service or GraphScanService()

    def get_all_nodes(
        self,
        graph_id: str,
        *,
        graph_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("Scanning nodes for graph_ids=%s", graph_ids or [graph_id])
        return self.graph_scan_service.scan_nodes(
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_all_edges(
        self,
        graph_id: str,
        *,
        graph_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("Scanning edges for graph_ids=%s", graph_ids or [graph_id])
        return self.graph_scan_service.scan_edges(
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_node_edges(
        self,
        node_uuid: str,
        *,
        graph_id: str,
        graph_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("Scanning node edges for %s", node_uuid)
        return self.graph_scan_service.get_node_edges(
            graph_id=graph_id,
            node_uuid=node_uuid,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
        project_id: Optional[str] = None,
        graph_ids: Optional[List[str]] = None,
    ) -> FilteredEntities:
        logger.info("Starting entity filtering for graph_ids=%s", graph_ids or [graph_id])

        normalized_graph_ids = self.graph_scan_service.normalize_graph_ids(
            graph_id,
            graph_ids,
        )
        if len(normalized_graph_ids) == 1:
            local_entities = self._load_filtered_entities_from_project_index(
                project_id=project_id,
                graph_id=graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=enrich_with_edges,
            )
            if local_entities is not None:
                logger.info(
                    "Loaded entity data from local graph entity index: project_id=%s graph_id=%s matched=%s",
                    project_id,
                    graph_id,
                    local_entities.filtered_count,
                )
                return local_entities

        if graph_ids is None:
            all_nodes = self.get_all_nodes(graph_id)
            all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        else:
            all_nodes = self.get_all_nodes(
                graph_id,
                graph_ids=normalized_graph_ids,
                project_id=project_id,
            )
            all_edges = (
                self.get_all_edges(
                    graph_id,
                    graph_ids=normalized_graph_ids,
                    project_id=project_id,
                )
                if enrich_with_edges
                else []
            )
        filtered = build_filtered_entities_from_payloads(
            all_nodes,
            all_edges,
            defined_entity_types=defined_entity_types,
            enrich_with_edges=enrich_with_edges,
        )
        logger.info(
            "Filtering complete: total nodes %s, matched %s, entity types: %s",
            filtered.total_count,
            filtered.filtered_count,
            filtered.entity_types,
        )
        return filtered

    def _load_filtered_entities_from_project_index(
        self,
        *,
        project_id: Optional[str],
        graph_id: str,
        defined_entity_types: Optional[List[str]],
        enrich_with_edges: bool,
    ) -> Optional[FilteredEntities]:
        if not project_id:
            return None

        payload = ProjectManager.get_graph_entity_index(project_id)
        if not payload:
            return None
        if payload.get("artifact_type") != "graph_entity_index":
            logger.warning(
                "Ignoring incompatible graph entity index artifact for project %s",
                project_id,
            )
            return None
        if payload.get("graph_id") and payload.get("graph_id") != graph_id:
            logger.info(
                "Graph entity index graph_id mismatch for project %s: expected=%s actual=%s",
                project_id,
                graph_id,
                payload.get("graph_id"),
            )
            return None

        raw_entities = payload.get("entities")
        if not isinstance(raw_entities, list):
            logger.warning(
                "Ignoring graph entity index with invalid entities payload for project %s",
                project_id,
            )
            return None

        entities: List[EntityNode] = []
        entity_types_found: Set[str] = set()
        for raw_entity in raw_entities:
            labels = raw_entity.get("labels", [])
            custom_labels = [label for label in labels if label not in ["Entity", "Node"]]
            if not custom_labels:
                continue
            entity_type = custom_labels[0]
            if defined_entity_types and entity_type not in defined_entity_types:
                continue

            entity_types_found.add(entity_type)
            entities.append(
                EntityNode(
                    uuid=raw_entity.get("uuid", ""),
                    name=raw_entity.get("name", ""),
                    labels=list(labels),
                    summary=raw_entity.get("summary", ""),
                    attributes=dict(raw_entity.get("attributes", {})),
                    related_edges=(
                        list(raw_entity.get("related_edges", []))
                        if enrich_with_edges
                        else []
                    ),
                    related_nodes=(
                        list(raw_entity.get("related_nodes", []))
                        if enrich_with_edges
                        else []
                    ),
                )
            )

        total_count = payload.get("total_count")
        if not isinstance(total_count, int):
            total_count = len(raw_entities)

        return FilteredEntities(
            entities=entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str,
        *,
        graph_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> Optional[EntityNode]:
        node = self.graph_scan_service.get_node(
            graph_id=graph_id,
            node_uuid=entity_uuid,
            graph_ids=graph_ids,
            project_id=project_id,
        )
        if not node:
            return None

        edges = self.get_node_edges(
            entity_uuid,
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )
        all_nodes = self.get_all_nodes(
            graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )
        node_map = {item["uuid"]: item for item in all_nodes if item.get("uuid")}

        related_edges = []
        related_node_uuids = set()
        for edge in edges:
            if edge.get("source_node_uuid") == entity_uuid:
                related_edges.append(
                    {
                        "direction": "outgoing",
                        "edge_name": edge.get("name", ""),
                        "fact": edge.get("fact", ""),
                        "target_node_uuid": edge.get("target_node_uuid"),
                    }
                )
                related_node_uuids.add(edge.get("target_node_uuid"))
            else:
                related_edges.append(
                    {
                        "direction": "incoming",
                        "edge_name": edge.get("name", ""),
                        "fact": edge.get("fact", ""),
                        "source_node_uuid": edge.get("source_node_uuid"),
                    }
                )
                related_node_uuids.add(edge.get("source_node_uuid"))

        related_nodes = [
            {
                "uuid": node_map[related_uuid]["uuid"],
                "name": node_map[related_uuid].get("name", ""),
                "labels": node_map[related_uuid].get("labels", []),
                "summary": node_map[related_uuid].get("summary", ""),
            }
            for related_uuid in sorted(related_node_uuids)
            if related_uuid in node_map and related_uuid != entity_uuid
        ]

        return EntityNode(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=list(node.get("labels", [])),
            summary=node.get("summary", ""),
            attributes=dict(node.get("attributes", {})),
            related_edges=related_edges,
            related_nodes=related_nodes,
        )

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
        *,
        graph_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> List[EntityNode]:
        result = self.filter_defined_entities(
            graph_id=graph_id,
            graph_ids=graph_ids,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
            project_id=project_id,
        )
        return result.entities
