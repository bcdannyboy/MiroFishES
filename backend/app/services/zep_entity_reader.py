"""
Zep entity reader and filtering service.
Reads nodes from the Zep graph and filters those that match predefined entity types.
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..models.project import ProjectManager
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .forecast_graph import is_analytical_type

logger = get_logger('mirofish.zep_entity_reader')

# Used for generic return types.
T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # Related edge information.
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # Related node information.
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
        """Get the entity type, excluding the default Entity label."""
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
            "entities": [e.to_dict() for e in self.entities],
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
    node_map = {n["uuid"]: n for n in all_nodes}
    filtered_entities: List[EntityNode] = []
    entity_types_found: Set[str] = set()

    for node in all_nodes:
        labels = node.get("labels", [])
        custom_labels = [label for label in labels if label not in ["Entity", "Node"]]
        if not custom_labels:
            continue

        if defined_entity_types:
            matching_labels = [label for label in custom_labels if label in defined_entity_types]
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
            name=node["name"],
            labels=labels,
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}),
        )

        if enrich_with_edges:
            related_edges = []
            related_node_uuids = set()

            for edge in serialized_edges:
                if edge["source_node_uuid"] == node["uuid"]:
                    related_edges.append(
                        {
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        }
                    )
                    related_node_uuids.add(edge["target_node_uuid"])
                elif edge["target_node_uuid"] == node["uuid"]:
                    related_edges.append(
                        {
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        }
                    )
                    related_node_uuids.add(edge["source_node_uuid"])

            entity.related_edges = related_edges
            entity.related_nodes = [
                {
                    "uuid": node_map[related_uuid]["uuid"],
                    "name": node_map[related_uuid]["name"],
                    "labels": node_map[related_uuid]["labels"],
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


class ZepEntityReader:
    """
    Zep entity reader and filtering service.

    Main capabilities:
    1. Read all nodes from the Zep graph
    2. Filter nodes that match predefined entity types
       (nodes with labels beyond just `Entity`)
    3. Retrieve related edges and connected node information for each entity
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")
        
        self.client = Zep(api_key=self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        Run a Zep API call with retries.

        Args:
            func: Function to execute, such as a no-argument lambda or callable
            operation_name: Operation name used in logs
            max_retries: Maximum retry count, default 3
            initial_delay: Initial delay in seconds

        Returns:
            API call result
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff.
                else:
                    logger.error(f"Zep {operation_name} still failed after {max_retries} attempts: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Get all graph nodes with pagination.

        Args:
            graph_id: Graph ID

        Returns:
            Node list
        """
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"Fetched {len(nodes_data)} nodes in total")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Get all graph edges with pagination.

        Args:
            graph_id: Graph ID

        Returns:
            Edge list
        """
        logger.info(f"Fetching all edges for graph {graph_id}...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"Fetched {len(edges_data)} edges in total")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all related edges for a given node, with retries.

        Args:
            node_uuid: Node UUID

        Returns:
            Edge list
        """
        try:
            # Call the Zep API with retries.
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"get node edges (node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"Failed to fetch edges for node {node_uuid}: {str(e)}")
            return []
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
        project_id: Optional[str] = None,
    ) -> FilteredEntities:
        """
        Filter nodes that match predefined entity types.

        Filtering rules:
        - If a node's labels contain only "Entity", it does not match a predefined type and is skipped
        - If a node's labels contain anything beyond "Entity" and "Node", it matches a predefined type and is kept

        Args:
            graph_id: Graph ID
            defined_entity_types: Optional predefined entity type list; when provided,
                only those types are kept
            enrich_with_edges: Whether to retrieve related edge information for each entity

        Returns:
            FilteredEntities: Filtered entity collection
        """
        logger.info(f"Starting entity filtering for graph {graph_id}...")

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

        # Get all nodes.
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
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
        """Load one filtered-entity collection from the persisted project index."""
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
                    labels=labels,
                    summary=raw_entity.get("summary", ""),
                    attributes=raw_entity.get("attributes", {}),
                    related_edges=raw_entity.get("related_edges", []) if enrich_with_edges else [],
                    related_nodes=raw_entity.get("related_nodes", []) if enrich_with_edges else [],
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
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        Get a single entity with full context, including edges and related nodes, with retries.

        Args:
            graph_id: Graph ID
            entity_uuid: Entity UUID

        Returns:
            EntityNode or None
        """
        try:
            # Fetch the node with retries.
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"get node details (uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # Get node edges.
            edges = self.get_node_edges(entity_uuid)

            # Load all nodes for related-node lookup.
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            # Build related-edge and related-node data.
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # Get related node information.
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch entity {entity_uuid}: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        Get all entities of a given type.

        Args:
            graph_id: Graph ID
            entity_type: Entity type, such as "Student" or "PublicFigure"
            enrich_with_edges: Whether to fetch related edge information

        Returns:
            Entity list
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
