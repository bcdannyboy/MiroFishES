"""Compile repo ontology JSON into Graphiti-compatible Pydantic models."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, create_model

from .types import CompiledOntology


_ENTITY_RESERVED_ATTRS = {
    "uuid",
    "name",
    "group_id",
    "name_embedding",
    "summary",
    "created_at",
}
_EDGE_RESERVED_ATTRS = {
    "uuid",
    "name",
    "group_id",
    "fact",
    "fact_embedding",
    "episodes",
    "created_at",
    "valid_at",
    "invalid_at",
    "expired_at",
}
_INVALID_ATTR_CHARS = re.compile(r"[^0-9a-zA-Z_]+")


def _safe_attr_name(name: str, *, prefix: str, reserved: set[str]) -> str:
    normalized = _INVALID_ATTR_CHARS.sub("_", str(name or "").strip()).strip("_")
    normalized = normalized or prefix.rstrip("_")
    normalized = normalized.lower()
    if normalized in reserved:
        return f"{prefix}{normalized}"
    return normalized


def _canonical_name(name: str, known_names: dict[str, str]) -> str:
    raw_name = str(name or "").strip()
    if not raw_name:
        return raw_name
    return known_names.get(raw_name.lower(), raw_name)


class GraphOntologyCompiler:
    """Turn the current ontology JSON structure into Graphiti model classes."""

    def compile(self, ontology: dict[str, Any]) -> CompiledOntology:
        raw_ontology = dict(ontology or {})
        entity_defs = [
            entity
            for entity in raw_ontology.get("entity_types", [])
            if isinstance(entity, dict) and entity.get("name")
        ]
        edge_defs = [
            edge
            for edge in raw_ontology.get("edge_types", [])
            if isinstance(edge, dict) and edge.get("name")
        ]

        entity_name_lookup = {
            str(entity["name"]).lower(): str(entity["name"])
            for entity in entity_defs
        }
        entity_types = {
            str(entity["name"]): self._build_entity_model(entity)
            for entity in entity_defs
        }
        edge_types = {
            str(edge["name"]): self._build_edge_model(edge)
            for edge in edge_defs
        }
        edge_type_map: dict[tuple[str, str], list[str]] = {}
        for edge in edge_defs:
            edge_name = str(edge["name"])
            for source_target in edge.get("source_targets", []) or []:
                if not isinstance(source_target, dict):
                    continue
                source = _canonical_name(source_target.get("source", ""), entity_name_lookup)
                target = _canonical_name(source_target.get("target", ""), entity_name_lookup)
                if not source or not target:
                    continue
                edge_type_map.setdefault((source, target), []).append(edge_name)

        return CompiledOntology(
            raw_ontology=raw_ontology,
            entity_types=entity_types,
            edge_types=edge_types,
            edge_type_map=edge_type_map,
        )

    def _build_entity_model(self, entity: dict[str, Any]) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        for attribute in entity.get("attributes", []) or []:
            if not isinstance(attribute, dict):
                continue
            attr_name = _safe_attr_name(
                str(attribute.get("name", "")),
                prefix="entity_",
                reserved=_ENTITY_RESERVED_ATTRS,
            )
            description = attribute.get("description") or attr_name
            fields[attr_name] = (
                str | None,
                Field(default=None, description=description),
            )
        return create_model(str(entity["name"]), __base__=BaseModel, **fields)

    def _build_edge_model(self, edge: dict[str, Any]) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        for attribute in edge.get("attributes", []) or []:
            if not isinstance(attribute, dict):
                continue
            attr_name = _safe_attr_name(
                str(attribute.get("name", "")),
                prefix="edge_",
                reserved=_EDGE_RESERVED_ATTRS,
            )
            description = attribute.get("description") or attr_name
            fields[attr_name] = (
                str | None,
                Field(default=None, description=description),
            )
        model_name = f"{edge['name']}Edge"
        return create_model(model_name, __base__=BaseModel, **fields)
