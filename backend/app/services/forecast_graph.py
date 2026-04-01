"""Shared helpers for layered forecast graphs, chunk provenance, and local indexes."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..utils.file_parser import split_text_into_chunks


DEFAULT_ACTOR_TYPES = ["Person", "Organization"]
DEFAULT_ANALYTICAL_TYPES = [
    "Event",
    "Claim",
    "Evidence",
    "Topic",
    "Metric",
    "TimeWindow",
    "Scenario",
    "UncertaintyFactor",
]
ANALYTICAL_OBJECT_TYPES = set(DEFAULT_ANALYTICAL_TYPES)
DEFAULT_CUSTOM_LABEL_EXCLUSIONS = {"Entity", "Node"}


FORECAST_REQUIRED_ENTITY_DEFINITIONS = [
    {
        "name": "Event",
        "description": "A concrete development or occurrence relevant to the forecast.",
        "layer": "analytical",
        "attributes": [
            {"name": "event_name", "type": "text", "description": "Event label"},
            {"name": "status", "type": "text", "description": "Current event status"},
        ],
        "examples": ["central bank briefing", "earnings release"],
    },
    {
        "name": "Claim",
        "description": "A forecast-relevant assertion, estimate, or directional statement.",
        "layer": "analytical",
        "attributes": [
            {"name": "claim_text", "type": "text", "description": "Claim wording"},
            {"name": "stance", "type": "text", "description": "Claim direction or stance"},
        ],
        "examples": ["rate cut likely by June", "slowdown risk is rising"],
    },
    {
        "name": "Evidence",
        "description": "A cited source, observation, quote, or artifact supporting analysis.",
        "layer": "analytical",
        "attributes": [
            {"name": "evidence_text", "type": "text", "description": "Evidence summary"},
            {"name": "evidence_kind", "type": "text", "description": "Evidence type"},
        ],
        "examples": ["payroll report", "management guidance"],
    },
    {
        "name": "Topic",
        "description": "A subject area or theme referenced by forecast objects.",
        "layer": "analytical",
        "attributes": [
            {"name": "topic_name", "type": "text", "description": "Topic name"},
        ],
        "examples": ["labor market", "liquidity stress"],
    },
    {
        "name": "Metric",
        "description": "A measurable quantity or tracked indicator used in the forecast.",
        "layer": "analytical",
        "attributes": [
            {"name": "metric_name", "type": "text", "description": "Metric label"},
            {"name": "metric_unit", "type": "text", "description": "Metric unit"},
        ],
        "examples": ["payroll growth", "default rate"],
    },
    {
        "name": "TimeWindow",
        "description": "A relevant time period or forecast horizon.",
        "layer": "analytical",
        "attributes": [
            {"name": "window_label", "type": "text", "description": "Time-window label"},
        ],
        "examples": ["Q3 2026", "next 90 days"],
    },
    {
        "name": "Scenario",
        "description": "A possible future state, path, or conditional case.",
        "layer": "analytical",
        "attributes": [
            {"name": "scenario_name", "type": "text", "description": "Scenario label"},
        ],
        "examples": ["soft landing", "recession case"],
    },
    {
        "name": "UncertaintyFactor",
        "description": "A source of ambiguity, risk, or unresolved variance.",
        "layer": "analytical",
        "attributes": [
            {"name": "factor_name", "type": "text", "description": "Uncertainty label"},
        ],
        "examples": ["data revision risk", "policy timing uncertainty"],
    },
    {
        "name": "Person",
        "description": "Any individual person relevant to the forecast narrative.",
        "layer": "actor",
        "attributes": [
            {"name": "full_name", "type": "text", "description": "Full name of the person"},
            {"name": "role", "type": "text", "description": "Role or occupation"},
        ],
        "examples": ["analyst", "policymaker"],
    },
    {
        "name": "Organization",
        "description": "Any organization relevant to the forecast narrative.",
        "layer": "actor",
        "attributes": [
            {"name": "org_name", "type": "text", "description": "Organization name"},
            {"name": "org_type", "type": "text", "description": "Organization type"},
        ],
        "examples": ["central bank", "labor department"],
    },
]


FORECAST_REQUIRED_EDGE_DEFINITIONS = [
    {
        "name": "INVOLVES_ACTOR",
        "description": "Links an event, claim, or scenario to a relevant actor.",
        "source_targets": [
            {"source": "Event", "target": "Person"},
            {"source": "Event", "target": "Organization"},
            {"source": "Claim", "target": "Person"},
            {"source": "Claim", "target": "Organization"},
            {"source": "Scenario", "target": "Person"},
            {"source": "Scenario", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "MAKES_CLAIM",
        "description": "An actor states or advances a claim.",
        "source_targets": [
            {"source": "Person", "target": "Claim"},
            {"source": "Organization", "target": "Claim"},
        ],
        "attributes": [],
    },
    {
        "name": "SUPPORTED_BY",
        "description": "A claim, scenario, or metric is supported by evidence.",
        "source_targets": [
            {"source": "Claim", "target": "Evidence"},
            {"source": "Scenario", "target": "Evidence"},
            {"source": "Metric", "target": "Evidence"},
        ],
        "attributes": [],
    },
    {
        "name": "REFERS_TO_EVENT",
        "description": "Connects evidence, claims, or scenarios to an event.",
        "source_targets": [
            {"source": "Claim", "target": "Event"},
            {"source": "Evidence", "target": "Event"},
            {"source": "Scenario", "target": "Event"},
        ],
        "attributes": [],
    },
    {
        "name": "ABOUT_TOPIC",
        "description": "Connects analytical objects to a tracked topic.",
        "source_targets": [
            {"source": "Claim", "target": "Topic"},
            {"source": "Evidence", "target": "Topic"},
            {"source": "Event", "target": "Topic"},
            {"source": "Scenario", "target": "Topic"},
            {"source": "Metric", "target": "Topic"},
        ],
        "attributes": [],
    },
    {
        "name": "MEASURES",
        "description": "A metric measures an event, scenario, or topic.",
        "source_targets": [
            {"source": "Metric", "target": "Event"},
            {"source": "Metric", "target": "Scenario"},
            {"source": "Metric", "target": "Topic"},
        ],
        "attributes": [],
    },
    {
        "name": "OCCURS_DURING",
        "description": "Connects analytical objects to a relevant time window.",
        "source_targets": [
            {"source": "Event", "target": "TimeWindow"},
            {"source": "Claim", "target": "TimeWindow"},
            {"source": "Scenario", "target": "TimeWindow"},
            {"source": "Metric", "target": "TimeWindow"},
        ],
        "attributes": [],
    },
    {
        "name": "HAS_UNCERTAINTY",
        "description": "Associates forecast objects with a source of uncertainty.",
        "source_targets": [
            {"source": "Claim", "target": "UncertaintyFactor"},
            {"source": "Event", "target": "UncertaintyFactor"},
            {"source": "Scenario", "target": "UncertaintyFactor"},
            {"source": "Metric", "target": "UncertaintyFactor"},
        ],
        "attributes": [],
    },
    {
        "name": "INFORMS_SCENARIO",
        "description": "Evidence, claims, events, or metrics inform a scenario.",
        "source_targets": [
            {"source": "Claim", "target": "Scenario"},
            {"source": "Evidence", "target": "Scenario"},
            {"source": "Event", "target": "Scenario"},
            {"source": "Metric", "target": "Scenario"},
            {"source": "UncertaintyFactor", "target": "Scenario"},
        ],
        "attributes": [],
    },
]


def _unique_preserving_order(values: Iterable[Any]) -> List[Any]:
    seen = set()
    result = []
    for value in values:
        if value in seen or value is None or value == "":
            continue
        seen.add(value)
        result.append(value)
    return result


def get_custom_labels(labels: Optional[List[str]]) -> List[str]:
    """Return non-default labels from a graph node."""
    return [
        label
        for label in (labels or [])
        if label not in DEFAULT_CUSTOM_LABEL_EXCLUSIONS
    ]


def get_primary_object_type(labels: Optional[List[str]]) -> Optional[str]:
    """Return the first custom graph label when one exists."""
    custom_labels = get_custom_labels(labels)
    return custom_labels[0] if custom_labels else None


def is_analytical_type(label: Optional[str]) -> bool:
    """Return whether one graph label is a forecast analytical object."""
    return str(label or "") in ANALYTICAL_OBJECT_TYPES


def classify_graph_node(labels: Optional[List[str]]) -> Dict[str, Optional[str]]:
    """Classify one node as actor vs analytical from its labels."""
    object_type = get_primary_object_type(labels)
    if not object_type:
        return {"object_type": None, "layer": None}
    return {
        "object_type": object_type,
        "layer": "analytical" if is_analytical_type(object_type) else "actor",
    }


def ensure_layered_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one ontology into the layered forecast schema."""
    normalized = dict(ontology or {})
    existing_entities = {
        str((entity or {}).get("name") or ""): dict(entity or {})
        for entity in normalized.get("entity_types", [])
        if isinstance(entity, dict)
    }
    layered_entities: List[Dict[str, Any]] = []
    for default_entity in FORECAST_REQUIRED_ENTITY_DEFINITIONS:
        merged = dict(default_entity)
        existing = existing_entities.get(default_entity["name"], {})
        if existing.get("description"):
            merged["description"] = existing["description"]
        if isinstance(existing.get("attributes"), list) and existing["attributes"]:
            merged["attributes"] = existing["attributes"]
        if isinstance(existing.get("examples"), list) and existing["examples"]:
            merged["examples"] = existing["examples"]
        layered_entities.append(merged)

    existing_edges = {
        str((edge or {}).get("name") or ""): dict(edge or {})
        for edge in normalized.get("edge_types", [])
        if isinstance(edge, dict)
    }
    layered_edges: List[Dict[str, Any]] = []
    seen_edge_names = set()
    for default_edge in FORECAST_REQUIRED_EDGE_DEFINITIONS:
        merged = dict(default_edge)
        existing = existing_edges.get(default_edge["name"], {})
        if existing.get("description"):
            merged["description"] = existing["description"]
        if isinstance(existing.get("attributes"), list) and existing["attributes"]:
            merged["attributes"] = existing["attributes"]
        if isinstance(existing.get("source_targets"), list) and existing["source_targets"]:
            merged["source_targets"] = _unique_source_targets(
                list(default_edge.get("source_targets", [])) + list(existing["source_targets"])
            )
        layered_edges.append(merged)
        seen_edge_names.add(merged["name"])

    for edge in normalized.get("edge_types", []):
        if not isinstance(edge, dict):
            continue
        edge_name = str(edge.get("name") or "")
        if not edge_name or edge_name in seen_edge_names:
            continue
        layered_edges.append(edge)
        seen_edge_names.add(edge_name)
        if len(layered_edges) >= 10:
            break

    normalized["entity_types"] = layered_entities
    normalized["edge_types"] = layered_edges[:10]
    normalized["schema_mode"] = "forecast_layered"
    normalized["actor_types"] = list(DEFAULT_ACTOR_TYPES)
    normalized["analytical_types"] = list(DEFAULT_ANALYTICAL_TYPES)
    return normalized


def _unique_source_targets(pairs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    seen = set()
    result: List[Dict[str, str]] = []
    for pair in pairs:
        source = str((pair or {}).get("source") or "")
        target = str((pair or {}).get("target") or "")
        if not source or not target:
            continue
        key = (source, target)
        if key in seen:
            continue
        seen.add(key)
        result.append({"source": source, "target": target})
    return result


def build_chunk_records(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    source_units: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build deterministic chunk records with source-unit provenance."""
    if source_units:
        records = _build_chunk_records_from_source_units(
            text=text,
            chunk_size=chunk_size,
            overlap=overlap,
            source_units=source_units,
        )
        if records:
            return records

    plain_chunks = split_text_into_chunks(text, chunk_size, overlap)
    records: List[Dict[str, Any]] = []
    cursor = 0
    for index, chunk in enumerate(plain_chunks, start=1):
        start = text.find(chunk, cursor)
        if start < 0:
            start = cursor
        end = start + len(chunk)
        cursor = max(end - max(overlap, 0), end)
        records.append(
            {
                "chunk_id": f"chunk-{index:04d}",
                "text": chunk,
                "char_start": start,
                "char_end": end,
                "source_unit_ids": [],
                "source_ids": [],
                "stable_source_ids": [],
                "unit_types": [],
            }
        )
    return records


def _build_chunk_records_from_source_units(
    *,
    text: str,
    chunk_size: int,
    overlap: int,
    source_units: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized_units = _normalize_source_units_for_chunking(source_units)
    if not normalized_units:
        return []

    chunk_records: List[Dict[str, Any]] = []
    for unit in normalized_units:
        chunk_start = unit["combined_text_start"]
        chunk_end = unit["combined_text_end"]
        chunk_text = str(unit.get("text") or text[chunk_start:chunk_end]).strip()
        if not chunk_text:
            continue
        chunk_records.append(
            {
                "chunk_id": f"chunk-{len(chunk_records) + 1:04d}",
                "text": chunk_text,
                "char_start": chunk_start,
                "char_end": chunk_end,
                "source_unit_ids": [unit.get("unit_id")] if unit.get("unit_id") else [],
                "source_ids": _unique_preserving_order([unit.get("source_id")]),
                "stable_source_ids": _unique_preserving_order(
                    [unit.get("stable_source_id")]
                ),
                "unit_types": _unique_preserving_order([unit.get("unit_type")]),
            }
        )
    return chunk_records


def _normalize_source_units_for_chunking(
    source_units: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    normalized = []
    for unit in source_units:
        if not isinstance(unit, dict):
            continue
        combined_start = unit.get("combined_text_start")
        combined_end = unit.get("combined_text_end")
        if not isinstance(combined_start, int) or not isinstance(combined_end, int):
            continue
        if combined_end <= combined_start:
            continue
        normalized.append(dict(unit))
    normalized.sort(
        key=lambda item: (
            item.get("combined_text_start", 0),
            item.get("source_order", 0),
            item.get("unit_order", 0),
        )
    )
    return normalized


def build_episode_chunk_map(
    episode_uuids: List[str],
    chunk_records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Map graph episode ids back to the deterministic chunk records."""
    return {
        episode_uuid: dict(chunk_record)
        for episode_uuid, chunk_record in zip(episode_uuids, chunk_records)
        if episode_uuid
    }


def summarize_graph_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Build layered graph counts from a serialized snapshot."""
    nodes = snapshot.get("nodes", []) if isinstance(snapshot, dict) else []
    edges = snapshot.get("edges", []) if isinstance(snapshot, dict) else []

    node_type_counts: Dict[str, int] = {}
    actor_types: List[str] = []
    analytical_types: List[str] = []
    for node in nodes:
        object_type = get_primary_object_type((node or {}).get("labels", []))
        if not object_type:
            continue
        node_type_counts[object_type] = node_type_counts.get(object_type, 0) + 1
        if is_analytical_type(object_type):
            analytical_types.append(object_type)
        else:
            actor_types.append(object_type)

    edge_type_counts: Dict[str, int] = {}
    for edge in edges:
        edge_name = str((edge or {}).get("name") or (edge or {}).get("fact_type") or "")
        if not edge_name:
            continue
        edge_type_counts[edge_name] = edge_type_counts.get(edge_name, 0) + 1

    actor_types = _unique_preserving_order(sorted(actor_types))
    analytical_types = _unique_preserving_order(sorted(analytical_types))
    return {
        "node_count": int(snapshot.get("node_count", len(nodes))),
        "edge_count": int(snapshot.get("edge_count", len(edges))),
        "entity_types": sorted(node_type_counts),
        "actor_count": sum(
            count
            for label, count in node_type_counts.items()
            if not is_analytical_type(label)
        ),
        "analytical_object_count": sum(
            count
            for label, count in node_type_counts.items()
            if is_analytical_type(label)
        ),
        "actor_types": actor_types,
        "analytical_types": analytical_types,
        "node_type_counts": node_type_counts,
        "edge_type_counts": edge_type_counts,
    }


def build_layered_graph_index(
    *,
    snapshot: Dict[str, Any],
    source_units: Optional[List[Dict[str, Any]]],
    episode_chunk_map: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """Build one backward-compatible actor index plus analytical-object records."""
    nodes = snapshot.get("nodes", []) if isinstance(snapshot, dict) else []
    edges = snapshot.get("edges", []) if isinstance(snapshot, dict) else []
    node_map = {node.get("uuid"): node for node in nodes if node.get("uuid")}
    source_unit_map = {
        unit.get("unit_id"): unit
        for unit in (source_units or [])
        if isinstance(unit, dict) and unit.get("unit_id")
    }

    edge_provenance_map = {
        edge.get("uuid"): _build_edge_provenance(
            edge=edge,
            episode_chunk_map=episode_chunk_map or {},
            source_unit_map=source_unit_map,
        )
        for edge in edges
        if edge.get("uuid")
    }

    object_records = []
    actor_entities = []
    analytical_objects = []
    actor_types = set()
    analytical_types = set()

    for node in nodes:
        classification = classify_graph_node(node.get("labels", []))
        object_type = classification["object_type"]
        if not object_type:
            continue

        related_edges, related_nodes = _build_related_graph_context(
            node=node,
            edges=edges,
            node_map=node_map,
            edge_provenance_map=edge_provenance_map,
        )
        provenance = _build_node_provenance(
            node=node,
            incident_edges=related_edges,
            source_unit_map=source_unit_map,
        )
        record = {
            "uuid": node.get("uuid", ""),
            "name": node.get("name", ""),
            "labels": node.get("labels", []),
            "summary": node.get("summary", ""),
            "attributes": node.get("attributes", {}),
            "related_edges": related_edges,
            "related_nodes": related_nodes,
            "object_type": object_type,
            "layer": classification["layer"],
            "provenance": provenance,
        }
        object_records.append(record)
        if classification["layer"] == "analytical":
            analytical_objects.append(record)
            analytical_types.add(object_type)
        else:
            actor_entities.append(record)
            actor_types.add(object_type)

    citation_coverage = {
        "source_unit_backed_node_count": sum(
            1 for record in object_records if record["provenance"]["source_unit_ids"]
        ),
        "source_unit_backed_edge_count": sum(
            1
            for provenance in edge_provenance_map.values()
            if provenance["source_unit_ids"]
        ),
        "edge_episode_link_count": sum(
            1 for provenance in edge_provenance_map.values() if provenance["episode_ids"]
        ),
    }

    return {
        "total_count": len(actor_entities),
        "filtered_count": len(actor_entities),
        "entity_types": sorted(actor_types),
        "entities": actor_entities,
        "analytical_object_count": len(analytical_objects),
        "analytical_types": sorted(analytical_types),
        "analytical_objects": analytical_objects,
        "graph_node_count": len(nodes),
        "graph_edge_count": len(edges),
        "object_count": len(object_records),
        "citation_coverage": citation_coverage,
    }


def _build_related_graph_context(
    *,
    node: Dict[str, Any],
    edges: List[Dict[str, Any]],
    node_map: Dict[str, Dict[str, Any]],
    edge_provenance_map: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    related_edges: List[Dict[str, Any]] = []
    related_node_uuids = set()
    node_uuid = node.get("uuid")

    for edge in edges:
        if edge.get("source_node_uuid") == node_uuid:
            related_edges.append(
                {
                    "direction": "outgoing",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "target_node_uuid": edge.get("target_node_uuid"),
                    "provenance": edge_provenance_map.get(edge.get("uuid"), {}),
                }
            )
            related_node_uuids.add(edge.get("target_node_uuid"))
        elif edge.get("target_node_uuid") == node_uuid:
            related_edges.append(
                {
                    "direction": "incoming",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "source_node_uuid": edge.get("source_node_uuid"),
                    "provenance": edge_provenance_map.get(edge.get("uuid"), {}),
                }
            )
            related_node_uuids.add(edge.get("source_node_uuid"))

    related_nodes = []
    for related_uuid in sorted(related_node_uuids):
        related_node = node_map.get(related_uuid)
        if not related_node:
            continue
        related_nodes.append(
            {
                "uuid": related_node.get("uuid", ""),
                "name": related_node.get("name", ""),
                "labels": related_node.get("labels", []),
                "summary": related_node.get("summary", ""),
            }
        )

    return related_edges, related_nodes


def _build_edge_provenance(
    *,
    edge: Dict[str, Any],
    episode_chunk_map: Dict[str, Dict[str, Any]],
    source_unit_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    episode_ids = _unique_preserving_order(edge.get("episodes", []) or [])
    chunk_records = [
        episode_chunk_map[episode_id]
        for episode_id in episode_ids
        if episode_id in episode_chunk_map
    ]
    chunk_ids = _unique_preserving_order(
        record.get("chunk_id") for record in chunk_records
    )
    source_unit_ids = _unique_preserving_order(
        unit_id
        for record in chunk_records
        for unit_id in record.get("source_unit_ids", [])
    )
    citations = [
        _build_citation_record(source_unit_map[unit_id], reason="episode_linked")
        for unit_id in source_unit_ids
        if unit_id in source_unit_map
    ]
    return {
        "episode_ids": episode_ids,
        "chunk_ids": chunk_ids,
        "source_unit_ids": source_unit_ids,
        "source_ids": _unique_preserving_order(
            citation.get("source_id") for citation in citations
        ),
        "stable_source_ids": _unique_preserving_order(
            citation.get("stable_source_id") for citation in citations
        ),
        "citation_count": len(citations),
        "citations": citations,
    }


def _build_node_provenance(
    *,
    node: Dict[str, Any],
    incident_edges: List[Dict[str, Any]],
    source_unit_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    edge_provenance = [
        (edge or {}).get("provenance", {})
        for edge in incident_edges
        if isinstance(edge, dict)
    ]
    source_unit_ids = _unique_preserving_order(
        unit_id
        for provenance in edge_provenance
        for unit_id in provenance.get("source_unit_ids", [])
    )
    episode_ids = _unique_preserving_order(
        episode_id
        for provenance in edge_provenance
        for episode_id in provenance.get("episode_ids", [])
    )
    chunk_ids = _unique_preserving_order(
        chunk_id
        for provenance in edge_provenance
        for chunk_id in provenance.get("chunk_ids", [])
    )

    match_reason = "edge_episode"
    if not source_unit_ids and source_unit_map:
        node_name = str(node.get("name") or "").strip().lower()
        matched_units = []
        if node_name:
            for unit in source_unit_map.values():
                if node_name and node_name in str(unit.get("text") or "").lower():
                    matched_units.append(unit.get("unit_id"))
        source_unit_ids = _unique_preserving_order(matched_units)
        match_reason = "name_match" if source_unit_ids else "unmapped"

    citations = [
        _build_citation_record(source_unit_map[unit_id], reason=match_reason)
        for unit_id in source_unit_ids
        if unit_id in source_unit_map
    ]
    return {
        "match_reason": match_reason,
        "episode_ids": episode_ids,
        "chunk_ids": chunk_ids,
        "source_unit_ids": source_unit_ids,
        "source_ids": _unique_preserving_order(
            citation.get("source_id") for citation in citations
        ),
        "stable_source_ids": _unique_preserving_order(
            citation.get("stable_source_id") for citation in citations
        ),
        "citation_count": len(citations),
        "citations": citations,
    }


def _build_citation_record(unit: Dict[str, Any], *, reason: str) -> Dict[str, Any]:
    return {
        "unit_id": unit.get("unit_id"),
        "source_id": unit.get("source_id"),
        "stable_source_id": unit.get("stable_source_id"),
        "original_filename": unit.get("original_filename"),
        "relative_path": unit.get("relative_path"),
        "unit_type": unit.get("unit_type"),
        "source_order": unit.get("source_order"),
        "unit_order": unit.get("unit_order"),
        "char_start": unit.get("char_start"),
        "char_end": unit.get("char_end"),
        "combined_text_start": unit.get("combined_text_start"),
        "combined_text_end": unit.get("combined_text_end"),
        "text_excerpt": str(unit.get("text") or "")[:280],
        "reason": reason,
    }
