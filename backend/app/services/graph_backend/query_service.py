"""Backend-neutral graph query helpers built on deterministic artifact scans."""

from __future__ import annotations

from typing import Any

from ...utils.graph_scan import keyword_score, normalize_graph_ids, normalize_text
from .scan_service import GraphScanService


class GraphQueryService:
    """Search and read graph artifacts across base and runtime namespaces."""

    def __init__(self, *, scan_service: GraphScanService | None = None) -> None:
        self.scan_service = scan_service or GraphScanService()

    def search_graph(
        self,
        *,
        graph_id: str | None,
        query: str,
        limit: int = 10,
        scope: str = "edges",
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_graph_ids = normalize_graph_ids(graph_id, graph_ids)
        facts: list[str] = []
        seen_facts: set[str] = set()
        edge_results: list[dict[str, Any]] = []
        node_results: list[dict[str, Any]] = []

        if scope in {"edges", "both"}:
            scored_edges = []
            for edge in (
                self.get_all_edges(
                    graph_id=normalized_graph_ids[0],
                    graph_ids=normalized_graph_ids,
                    project_id=project_id,
                )
            ):
                score = keyword_score(
                    query,
                    edge.get("fact"),
                    edge.get("name"),
                    edge.get("source_node_name"),
                    edge.get("target_node_name"),
                    (edge.get("attributes") or {}).get("payload", {}),
                )
                if score > 0:
                    scored_edges.append(edge)
            for edge in scored_edges[:limit]:
                edge_results.append(dict(edge))
                fact = normalize_text(edge.get("fact"))
                if fact and fact not in seen_facts:
                    seen_facts.add(fact)
                    facts.append(fact)

        if scope in {"nodes", "both"}:
            scored_nodes = []
            for node in (
                self.get_all_nodes(
                    graph_id=normalized_graph_ids[0],
                    graph_ids=normalized_graph_ids,
                    project_id=project_id,
                )
            ):
                score = keyword_score(
                    query,
                    node.get("name"),
                    node.get("summary"),
                    " ".join(node.get("labels") or []),
                )
                if score > 0:
                    scored_nodes.append(node)
            for node in scored_nodes[:limit]:
                node_results.append(dict(node))
                summary = normalize_text(node.get("summary"))
                if summary:
                    fact = f"[{node.get('name', '')}]: {summary}"
                    if fact not in seen_facts:
                        seen_facts.add(fact)
                        facts.append(fact)

        return {
            "facts": facts[:limit],
            "edges": edge_results[:limit],
            "nodes": node_results[:limit],
            "query": query,
            "total_count": len(facts[:limit]),
        }

    def get_all_nodes(
        self,
        *,
        graph_id: str | None,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.scan_service.scan_nodes(
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_all_edges(
        self,
        *,
        graph_id: str | None,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.scan_service.scan_edges(
            graph_id=graph_id,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_node_detail(
        self,
        *,
        graph_id: str | None,
        node_uuid: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        return self.scan_service.get_node(
            graph_id=graph_id,
            node_uuid=node_uuid,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_node_edges(
        self,
        *,
        graph_id: str | None,
        node_uuid: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.scan_service.get_node_edges(
            graph_id=graph_id,
            node_uuid=node_uuid,
            graph_ids=graph_ids,
            project_id=project_id,
        )

    def get_entities_by_type(
        self,
        *,
        graph_id: str | None,
        entity_type: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        target = normalize_text(entity_type)
        return [
            dict(node)
            for node in self.get_all_nodes(
                graph_id=graph_id,
                graph_ids=graph_ids,
                project_id=project_id,
            )
            if target in (node.get("labels") or [])
        ]

    def get_entity_summary(
        self,
        *,
        graph_id: str | None,
        entity_name: str,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_graph_ids = normalize_graph_ids(graph_id, graph_ids)
        entity_node = None
        for node in self.get_all_nodes(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
        ):
            if normalize_text(node.get("name")).lower() == normalize_text(entity_name).lower():
                entity_node = node
                break
        related_edges = (
            self.get_node_edges(
                graph_id=normalized_graph_ids[0],
                graph_ids=normalized_graph_ids,
                node_uuid=entity_node.get("uuid"),
                project_id=project_id,
            )
            if entity_node
            else []
        )
        search_result = self.search_graph(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
            query=entity_name,
            limit=20,
            scope="edges",
        )
        return {
            "entity_name": entity_name,
            "entity_info": dict(entity_node) if entity_node else None,
            "related_facts": list(search_result["facts"]),
            "related_edges": [dict(edge) for edge in related_edges],
            "total_relations": len(related_edges),
        }

    def get_graph_statistics(
        self,
        *,
        graph_id: str | None,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_graph_ids = normalize_graph_ids(graph_id, graph_ids)
        nodes = self.get_all_nodes(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
        )
        edges = self.get_all_edges(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
        )
        entity_types: dict[str, int] = {}
        relation_types: dict[str, int] = {}
        for node in nodes:
            for label in node.get("labels") or []:
                if label in {"Entity", "Node"}:
                    continue
                entity_types[label] = entity_types.get(label, 0) + 1
        for edge in edges:
            relation_name = normalize_text(edge.get("name"))
            if not relation_name:
                continue
            relation_types[relation_name] = relation_types.get(relation_name, 0) + 1
        return {
            "graph_id": normalized_graph_ids[0],
            "graph_ids": normalized_graph_ids,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }

    def get_simulation_context(
        self,
        *,
        graph_id: str | None,
        simulation_requirement: str,
        limit: int = 30,
        graph_ids: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_graph_ids = normalize_graph_ids(graph_id, graph_ids)
        search_result = self.search_graph(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
            query=simulation_requirement,
            limit=limit,
            scope="edges",
        )
        nodes = self.get_all_nodes(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            project_id=project_id,
        )
        entities = []
        for node in nodes:
            custom_labels = [
                label for label in node.get("labels") or [] if label not in {"Entity", "Node"}
            ]
            if not custom_labels:
                continue
            entities.append(
                {
                    "name": node.get("name", ""),
                    "type": custom_labels[0],
                    "summary": node.get("summary", ""),
                }
            )
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": list(search_result["facts"]),
            "graph_statistics": self.get_graph_statistics(
                graph_id=normalized_graph_ids[0],
                graph_ids=normalized_graph_ids,
                project_id=project_id,
            ),
            "entities": entities[:limit],
            "total_entities": len(entities),
        }
