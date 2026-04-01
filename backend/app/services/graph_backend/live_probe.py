"""Live Graphiti + Neo4j probe for local verification wrappers."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from ...models.project import ProjectManager
from ..graph_entity_reader import GraphEntityReader
from ..graph_query_tools import GraphQueryToolsService
from .backend import GraphitiGraphBackend
from .graphiti_factory import build_graphiti_factory
from .namespace_manager import GraphNamespaceManager
from .neo4j_factory import build_neo4j_factory
from .ontology_compiler import GraphOntologyCompiler
from .query_service import GraphQueryService
from .scan_service import GraphScanService
from .settings import GraphBackendSettings


_SAMPLE_BASE_FACT = "Analyst says hiring is slowing."
_SAMPLE_RUNTIME_FACT = "Analyst posts runtime update about hiring pressure."


def apply_managed_local_graph_defaults(env: dict[str, str] | None = None) -> dict[str, str]:
    """Apply the managed-local Neo4j helper defaults for smoke/live verification."""
    target = env if env is not None else os.environ
    defaults = {
        "GRAPH_BACKEND": "graphiti_neo4j",
        "NEO4J_URI": f"bolt://127.0.0.1:{target.get('GRAPHITI_LIVE_NEO4J_BOLT_PORT', '17687')}",
        "NEO4J_USER": target.get("GRAPHITI_LIVE_NEO4J_USER", "neo4j"),
        "NEO4J_PASSWORD": target.get(
            "GRAPHITI_LIVE_NEO4J_PASSWORD",
            "mirofish-graphiti-live",
        ),
        "OPENAI_API_KEY": target.get(
            "OPENAI_API_KEY",
            target.get("LLM_API_KEY", "smoke-local-key"),
        ),
        "LLM_API_KEY": target.get(
            "LLM_API_KEY",
            target.get("OPENAI_API_KEY", "smoke-local-key"),
        ),
    }
    for key, value in defaults.items():
        target.setdefault(key, value)
    return defaults


@contextmanager
def _temporary_project_root(projects_dir: Path) -> Iterator[None]:
    original_projects_dir = ProjectManager.PROJECTS_DIR
    ProjectManager.PROJECTS_DIR = str(projects_dir)
    try:
        yield
    finally:
        ProjectManager.PROJECTS_DIR = original_projects_dir


def _seed_namespace(driver: Any, namespace_id: str) -> None:
    driver.execute_query(
        """
        MATCH (n)
        WHERE n.group_id = $group_id
        DETACH DELETE n
        """,
        {"group_id": namespace_id},
    )
    driver.execute_query(
        """
        MERGE (actor:Entity:Person {uuid: $actor_uuid})
        SET actor.group_id = $group_id,
            actor.name = $actor_name,
            actor.summary = $actor_summary,
            actor.created_at = $created_at
        MERGE (topic:Entity:Topic {uuid: $topic_uuid})
        SET topic.group_id = $group_id,
            topic.name = $topic_name,
            topic.summary = $topic_summary,
            topic.created_at = $created_at
        MERGE (actor)-[edge:MENTIONS {uuid: $edge_uuid}]->(topic)
        SET edge.group_id = $group_id,
            edge.name = 'MENTIONS',
            edge.fact = $fact,
            edge.created_at = $created_at,
            edge.valid_at = $created_at
        """,
        {
            "group_id": namespace_id,
            "actor_uuid": "actor-1",
            "actor_name": "Analyst",
            "actor_summary": "Tracks labor-market conditions.",
            "topic_uuid": "topic-1",
            "topic_name": "Labor slowdown",
            "topic_summary": "Employment is cooling.",
            "edge_uuid": "edge-1",
            "fact": _SAMPLE_BASE_FACT,
            "created_at": "2026-03-31T09:00:00Z",
        },
    )


def _build_graph_entity_index(
    *,
    project_id: str,
    graph_id: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    node_map = {
        str(node.get("uuid")): node
        for node in snapshot.get("nodes", [])
        if node.get("uuid")
    }
    edges_by_node: dict[str, list[dict[str, Any]]] = {}
    for edge in snapshot.get("edges", []):
        source_uuid = str(edge.get("source_node_uuid") or "")
        target_uuid = str(edge.get("target_node_uuid") or "")
        if source_uuid:
            edges_by_node.setdefault(source_uuid, []).append(
                {
                    "direction": "outgoing",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "target_node_uuid": target_uuid,
                    "created_at": edge.get("created_at"),
                    "valid_at": edge.get("valid_at"),
                    "invalid_at": edge.get("invalid_at"),
                    "expired_at": edge.get("expired_at"),
                }
            )
        if target_uuid:
            edges_by_node.setdefault(target_uuid, []).append(
                {
                    "direction": "incoming",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "source_node_uuid": source_uuid,
                    "created_at": edge.get("created_at"),
                    "valid_at": edge.get("valid_at"),
                    "invalid_at": edge.get("invalid_at"),
                    "expired_at": edge.get("expired_at"),
                }
            )

    entities: list[dict[str, Any]] = []
    analytical_objects: list[dict[str, Any]] = []
    analytical_labels = {"Topic", "Claim", "Signal", "Scenario", "Event"}

    for node_uuid, node in node_map.items():
        labels = list(node.get("labels") or [])
        custom_labels = [label for label in labels if label not in {"Entity", "Node"}]
        related_edges = list(edges_by_node.get(node_uuid, []))
        related_node_ids = {
            edge.get("target_node_uuid") or edge.get("source_node_uuid")
            for edge in related_edges
        }
        related_nodes = [
            {
                "uuid": related_uuid,
                "name": node_map[related_uuid].get("name", ""),
                "labels": node_map[related_uuid].get("labels", []),
                "summary": node_map[related_uuid].get("summary", ""),
            }
            for related_uuid in sorted(related_node_ids)
            if related_uuid in node_map and related_uuid != node_uuid
        ]
        payload = {
            "uuid": node_uuid,
            "name": node.get("name", ""),
            "labels": labels,
            "summary": node.get("summary", ""),
            "attributes": dict(node.get("attributes") or {}),
            "related_edges": related_edges,
            "related_nodes": related_nodes,
            "created_at": node.get("created_at"),
        }
        if any(label in analytical_labels for label in custom_labels):
            payload["object_type"] = next(
                label for label in custom_labels if label in analytical_labels
            )
            analytical_objects.append(payload)
        else:
            entities.append(payload)

    return {
        "artifact_type": "graph_entity_index",
        "schema_version": "forecast.grounding.v1",
        "generator_version": "graphiti.live.probe.v1",
        "project_id": project_id,
        "graph_id": graph_id,
        "generated_at": "2026-03-31T09:05:00Z",
        "total_count": len(entities),
        "filtered_count": len(entities),
        "entity_types": sorted(
            {
                label
                for entity in entities
                for label in entity.get("labels", [])
                if label not in {"Entity", "Node"}
            }
        ),
        "entities": entities,
        "analytical_object_count": len(analytical_objects),
        "analytical_types": sorted(
            {
                str(item.get("object_type"))
                for item in analytical_objects
                if item.get("object_type")
            }
        ),
        "analytical_objects": analytical_objects,
    }


def _write_runtime_artifacts(
    *,
    simulation_root: Path,
    project_id: str,
    base_graph_id: str,
    runtime_graph_id: str,
) -> None:
    run_dir = (
        simulation_root
        / "sim-live-probe"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "simulation_id": "sim-live-probe",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": project_id,
                "base_graph_id": base_graph_id,
                "runtime_graph_id": runtime_graph_id,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "runtime_graph_base_snapshot.json").write_text(
        json.dumps(
            {
                "artifact_type": "runtime_graph_base_snapshot",
                "simulation_id": "sim-live-probe",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": project_id,
                "base_graph_id": base_graph_id,
                "runtime_graph_id": runtime_graph_id,
                "actors": [
                    {
                        "entity_uuid": "actor-1",
                        "entity_name": "Analyst",
                        "entity_type": "Person",
                        "summary": "Tracks labor-market conditions.",
                        "linked_object_uuids": ["topic-1"],
                    }
                ],
                "analytical_objects": [
                    {
                        "uuid": "topic-1",
                        "name": "Labor slowdown",
                        "object_type": "Topic",
                        "summary": "Employment is cooling.",
                    }
                ],
                "registries": {
                    "topics": [
                        {
                            "uuid": "topic-1",
                            "name": "Labor slowdown",
                            "linked_actor_uuids": ["actor-1"],
                        }
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "runtime_graph_updates.jsonl").write_text(
        json.dumps(
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "runtime-transition-1",
                "transition_type": "claim",
                "simulation_id": "sim-live-probe",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": project_id,
                "base_graph_id": base_graph_id,
                "runtime_graph_id": runtime_graph_id,
                "platform": "twitter",
                "round_num": 1,
                "timestamp": "2026-03-31T09:10:00Z",
                "recorded_at": "2026-03-31T09:10:01Z",
                "agent": {
                    "agent_name": "Analyst",
                    "entity_uuid": "actor-1",
                    "entity_type": "Person",
                },
                "payload": {
                    "action_type": "CREATE_POST",
                    "action_args": {
                        "content": "Hiring pressure is building.",
                    },
                },
                "provenance": {
                    "run_scope": "sim-live-probe::0001::0001",
                    "graph_object_uuids": ["topic-1"],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": _SAMPLE_RUNTIME_FACT,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def run_live_graphiti_probe(
    settings: GraphBackendSettings | None = None,
) -> dict[str, Any]:
    """Exercise local startup, export, search, and runtime-history readiness."""
    resolved_settings = settings or GraphBackendSettings.from_env()
    graphiti_factory = build_graphiti_factory(resolved_settings)
    neo4j_factory = build_neo4j_factory(resolved_settings)
    backend = GraphitiGraphBackend(
        settings=resolved_settings,
        graphiti_factory=graphiti_factory,
        neo4j_factory=neo4j_factory,
        namespace_manager=GraphNamespaceManager(),
        ontology_compiler=GraphOntologyCompiler(),
    )
    namespace_id = f"graphiti-live-{uuid4().hex[:8]}"
    runtime_graph_id = f"{namespace_id}-runtime"

    payload: dict[str, Any] = {
        "resolved_backend": resolved_settings.backend,
        "resolved_neo4j_uri": resolved_settings.neo4j_uri,
        "graphiti_dependency": graphiti_factory.dependency_status.to_dict(),
        "neo4j_dependency": neo4j_factory.dependency_status.to_dict(),
        "namespace_id": namespace_id,
        "runtime_graph_id": runtime_graph_id,
    }

    graphiti_client = None
    try:
        graphiti_client = graphiti_factory.build_client()
        payload["graphiti_client_built"] = True
        payload["graphiti_client_type"] = type(graphiti_client).__name__
    except Exception as exc:
        payload["graphiti_client_built"] = False
        payload["graphiti_client_error"] = f"{exc.__class__.__name__}: {exc}"

    driver = neo4j_factory.build_driver()
    try:
        payload["neo4j_healthcheck"] = neo4j_factory.run_healthcheck(driver)
        _seed_namespace(driver, namespace_id)
        snapshot = backend.export_graph_snapshot(namespace_id)
        payload["export_snapshot"] = {
            "node_count": snapshot.get("node_count", 0),
            "edge_count": snapshot.get("edge_count", 0),
        }

        with tempfile.TemporaryDirectory(prefix="graphiti-live-probe-") as temp_dir:
            temp_root = Path(temp_dir)
            projects_root = temp_root / "projects"
            simulation_root = temp_root / "simulations"
            project_id = "proj-live-probe"
            project_dir = projects_root / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "project.json").write_text(
                json.dumps(
                    {
                        "project_id": project_id,
                        "name": "Graphiti Live Probe",
                        "status": "graph_completed",
                        "created_at": "2026-03-31T09:00:00Z",
                        "updated_at": "2026-03-31T09:05:00Z",
                        "files": [],
                        "graph_id": namespace_id,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (project_dir / "graph_entity_index.json").write_text(
                json.dumps(
                    _build_graph_entity_index(
                        project_id=project_id,
                        graph_id=namespace_id,
                        snapshot=snapshot,
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            _write_runtime_artifacts(
                simulation_root=simulation_root,
                project_id=project_id,
                base_graph_id=namespace_id,
                runtime_graph_id=runtime_graph_id,
            )

            with _temporary_project_root(projects_root):
                scan_service = GraphScanService(
                    simulation_data_dir=str(simulation_root),
                )
                query_service = GraphQueryService(scan_service=scan_service)
                query_tools = GraphQueryToolsService(query_service=query_service)
                entity_reader = GraphEntityReader(graph_scan_service=scan_service)
                quick_search = query_tools.quick_search(
                    graph_id=namespace_id,
                    graph_ids=[namespace_id, runtime_graph_id],
                    query="hiring",
                    limit=10,
                )
                panorama = query_tools.panorama_search(
                    graph_id=namespace_id,
                    graph_ids=[namespace_id, runtime_graph_id],
                    query="hiring",
                    include_expired=True,
                    limit=10,
                )
                filtered_entities = entity_reader.filter_defined_entities(
                    graph_id=namespace_id,
                    graph_ids=[namespace_id, runtime_graph_id],
                    defined_entity_types=["Person"],
                    enrich_with_edges=True,
                    project_id=project_id,
                )
                entity_detail = entity_reader.get_entity_with_context(
                    graph_id=namespace_id,
                    entity_uuid="actor-1",
                    graph_ids=[namespace_id, runtime_graph_id],
                    project_id=project_id,
                )

        payload["search_probe"] = {
            "facts": list(quick_search.facts),
            "total_count": quick_search.total_count,
        }
        payload["panorama_probe"] = {
            "active_count": panorama.active_count,
            "historical_count": panorama.historical_count,
        }
        payload["entity_probe"] = {
            "filtered_count": filtered_entities.filtered_count,
            "entity_names": [entity.name for entity in filtered_entities.entities],
            "context_edges": len(entity_detail.related_edges) if entity_detail else 0,
        }
        payload["status"] = (
            "passed"
            if (
                payload.get("graphiti_client_built")
                and payload.get("neo4j_healthcheck")
                and payload["export_snapshot"]["node_count"] >= 2
                and payload["search_probe"]["total_count"] >= 2
                and payload["panorama_probe"]["historical_count"] >= 1
                and payload["entity_probe"]["filtered_count"] >= 1
            )
            else "failed"
        )
    finally:
        try:
            driver.execute_query(
                """
                MATCH (n)
                WHERE n.group_id = $group_id
                DETACH DELETE n
                """,
                {"group_id": namespace_id},
            )
        finally:
            close = getattr(driver, "close", None)
            if callable(close):
                close()

    return payload


__all__ = ["apply_managed_local_graph_defaults", "run_live_graphiti_probe"]
