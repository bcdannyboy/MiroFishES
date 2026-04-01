"""Compile evidence-grounded world and agent state before simulation prepare."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from ..models.forecasting import EvidenceBundle, ForecastQuestion
from ..models.probabilistic import (
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
)
from ..models.project import ProjectManager
from ..utils.logger import get_logger
from .evidence_bundle_service import EvidenceBundleService
from .grounding_bundle_builder import GroundingBundleBuilder
from .graph_entity_reader import EntityNode

logger = get_logger("mirofish.world_state")


_REGISTRY_KEYS = {
    "topic": "topics",
    "claim": "claims",
    "evidence": "evidence",
    "metric": "metrics",
    "timewindow": "time_windows",
    "scenario": "scenarios",
    "uncertaintyfactor": "uncertainty_factors",
    "event": "events",
}


def _unique(values: Iterable[Any]) -> List[Any]:
    seen = set()
    ordered: List[Any] = []
    for value in values:
        if value is None:
            continue
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(value)
    return ordered


class PreparedWorldStateCompiler:
    """Build deterministic world/agent state from graph artifacts plus retrieval."""

    def __init__(
        self,
        *,
        evidence_bundle_service: Optional[EvidenceBundleService] = None,
        grounding_builder: Optional[GroundingBundleBuilder] = None,
    ) -> None:
        self.evidence_bundle_service = evidence_bundle_service or EvidenceBundleService()
        self.grounding_builder = grounding_builder or GroundingBundleBuilder()

    def compile(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        entities: List[EntityNode],
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        graph_index = ProjectManager.get_graph_entity_index(project_id) or {}
        grounding_bundle = self.grounding_builder.build_bundle(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
        )
        grounding_summary = self.grounding_builder.build_summary(grounding_bundle)
        retrieval_contract = dict(grounding_bundle.get("retrieval_contract") or {})

        evidence_bundle = self._build_evidence_bundle(
            simulation_id=simulation_id,
            project_id=project_id,
            simulation_requirement=simulation_requirement,
            created_at=now,
        )

        analytical_objects = list(graph_index.get("analytical_objects") or [])
        registry_by_uuid, registries = self._build_registries(analytical_objects)
        evidence_signals = self._extract_evidence_signals(evidence_bundle)
        citation_ids = _unique(
            [
                entry.citation_id
                for entry in evidence_bundle.source_entries
                if entry.citation_id
            ]
        )
        source_unit_ids = _unique(
            unit_id
            for entry in evidence_bundle.source_entries
            for unit_id in (entry.provenance.get("source_unit_ids") or [])
        )

        actor_index = {
            str(item.get("uuid") or ""): item
            for item in (graph_index.get("entities") or [])
            if str(item.get("uuid") or "").strip()
        }
        agent_state_records = [
            self._build_agent_state(
                entity=entity,
                actor_record=actor_index.get(entity.uuid, {}),
                registry_by_uuid=registry_by_uuid,
                evidence_bundle=evidence_bundle,
                analytical_objects=analytical_objects,
            )
            for entity in entities
        ]
        agent_states_by_uuid = {
            item["entity_uuid"]: item
            for item in agent_state_records
            if item.get("entity_uuid")
        }

        world_state = {
            "artifact_type": "prepared_world_state",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": now,
            "retrieval_contract": retrieval_contract,
            "grounding_summary": grounding_summary,
            "world_summary": self._build_world_summary(
                registries=registries,
                evidence_signals=evidence_signals,
                missing_markers=evidence_bundle.missing_evidence_markers,
            ),
            "registries": registries,
            "evidence_signals": evidence_signals,
            "citation_ids": citation_ids,
            "source_unit_ids": source_unit_ids,
            "conflict_summary": self._summarize_signal_conflicts(evidence_signals),
            "missing_evidence_markers": list(
                evidence_bundle.missing_evidence_markers or []
            ),
            "provider_snapshots": [dict(item) for item in evidence_bundle.provider_snapshots],
            "evidence_bundle_status": evidence_bundle.status,
        }
        agent_states = {
            "artifact_type": "prepared_agent_states",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": now,
            "agent_state_count": len(agent_state_records),
            "agent_states": agent_state_records,
        }
        return {
            "world_state": world_state,
            "agent_states": agent_states,
            "agent_states_by_uuid": agent_states_by_uuid,
            "grounding_bundle": grounding_bundle,
            "grounding_summary": grounding_summary,
        }

    def _build_evidence_bundle(
        self,
        *,
        simulation_id: str,
        project_id: str,
        simulation_requirement: str,
        created_at: str,
    ) -> EvidenceBundle:
        question = ForecastQuestion(
            forecast_id=f"{simulation_id}-prepare",
            project_id=project_id,
            title="Simulation preparation evidence",
            question=simulation_requirement,
            issue_timestamp=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        try:
            bundle = self.evidence_bundle_service.build_bundle(
                question=question,
                provider_ids=["uploaded_local_artifact"],
            )
            return bundle if isinstance(bundle, EvidenceBundle) else EvidenceBundle.from_dict(bundle)
        except Exception as exc:  # pragma: no cover - defensive fallback for live env
            logger.warning("Falling back to bounded-empty evidence bundle: %s", exc)
            return EvidenceBundle(
                bundle_id=f"{simulation_id}-prepare-bundle",
                forecast_id=question.forecast_id,
                title="Preparation bundle",
                summary="Evidence bundle degraded during prepare-time compilation.",
                source_entries=[],
                provider_snapshots=[
                    {
                        "provider_id": "uploaded_local_artifact",
                        "provider_kind": "uploaded_local_artifact",
                        "status": "unavailable",
                        "collected_at": created_at,
                        "notes": [str(exc)],
                    }
                ],
                missing_evidence_markers=[
                    {
                        "marker_id": f"{simulation_id}-prepare-evidence-unavailable",
                        "provider_id": "uploaded_local_artifact",
                        "provider_kind": "uploaded_local_artifact",
                        "kind": "prepare_evidence_unavailable",
                        "reason": str(exc),
                        "recorded_at": created_at,
                    }
                ],
                boundary_note="Evidence retrieval degraded during prepare-time compilation.",
                created_at=created_at,
                status="unavailable",
            )

    def _build_registries(
        self,
        analytical_objects: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        registries: Dict[str, List[Dict[str, Any]]] = {
            "topics": [],
            "claims": [],
            "evidence": [],
            "metrics": [],
            "time_windows": [],
            "scenarios": [],
            "uncertainty_factors": [],
            "events": [],
        }
        registry_by_uuid: Dict[str, Dict[str, Any]] = {}
        for item in analytical_objects:
            object_type = str(item.get("object_type") or "").strip()
            registry_key = _REGISTRY_KEYS.get(object_type.lower())
            if not registry_key:
                continue
            provenance = dict(item.get("provenance") or {})
            citations = list(provenance.get("citations") or [])
            record = {
                "uuid": item.get("uuid"),
                "name": item.get("name"),
                "summary": item.get("summary") or "",
                "object_type": object_type,
                "source_unit_ids": list(provenance.get("source_unit_ids") or []),
                "citation_ids": _unique(citation.get("citation_id") for citation in citations),
                "linked_actor_uuids": _unique(
                    node.get("uuid")
                    for node in (item.get("related_nodes") or [])
                    if node.get("uuid")
                ),
            }
            registries[registry_key].append(record)
            if record.get("uuid"):
                registry_by_uuid[str(record["uuid"])] = record
        return registry_by_uuid, registries

    def _build_agent_state(
        self,
        *,
        entity: EntityNode,
        actor_record: Dict[str, Any],
        registry_by_uuid: Dict[str, Dict[str, Any]],
        evidence_bundle: EvidenceBundle,
        analytical_objects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        related_object_uuids = _unique(
            [
                node.get("uuid")
                for node in list(actor_record.get("related_nodes") or [])
                if node.get("uuid")
            ]
            + [
                item.get("uuid")
                for item in analytical_objects
                if any(
                    str(node.get("uuid") or "") == entity.uuid
                    for node in (item.get("related_nodes") or [])
                )
            ]
        )
        related_objects = [
            registry_by_uuid[uuid]
            for uuid in related_object_uuids
            if uuid in registry_by_uuid
        ]

        related_source_unit_ids = set(actor_record.get("provenance", {}).get("source_unit_ids") or [])
        for obj in related_objects:
            related_source_unit_ids.update(obj.get("source_unit_ids") or [])

        matched_entries = []
        for entry in evidence_bundle.source_entries:
            entry_source_unit_ids = set(entry.provenance.get("source_unit_ids") or [])
            if entry.source_id in related_object_uuids or entry_source_unit_ids.intersection(related_source_unit_ids):
                matched_entries.append(entry)

        evidence_signals = self._extract_evidence_signals(
            EvidenceBundle(
                bundle_id=f"{entity.uuid}-state",
                forecast_id=evidence_bundle.forecast_id,
                title=f"{entity.name} evidence",
                summary=f"{entity.name} evidence",
                source_entries=matched_entries,
                provider_snapshots=evidence_bundle.provider_snapshots,
                missing_evidence_markers=[],
                boundary_note=evidence_bundle.boundary_note,
                created_at=evidence_bundle.created_at,
                status="ready" if matched_entries else "unavailable",
            )
        )
        topic_names = [item["name"] for item in related_objects if item["object_type"] == "Topic"]
        claim_names = [item["name"] for item in related_objects if item["object_type"] == "Claim"]
        uncertainty_names = [
            item["name"] for item in related_objects if item["object_type"] == "UncertaintyFactor"
        ]

        stance_hint = self._derive_stance_hint(evidence_signals, entity.get_entity_type() or "")
        sentiment_bias_hint = self._derive_sentiment_bias_hint(evidence_signals)

        return {
            "entity_uuid": entity.uuid,
            "entity_name": entity.name,
            "entity_type": entity.get_entity_type() or "Entity",
            "topic_names": topic_names,
            "claim_names": claim_names,
            "evidence_names": [item["name"] for item in related_objects if item["object_type"] == "Evidence"],
            "metric_names": [item["name"] for item in related_objects if item["object_type"] == "Metric"],
            "time_window_names": [
                item["name"] for item in related_objects if item["object_type"] == "TimeWindow"
            ],
            "scenario_names": [item["name"] for item in related_objects if item["object_type"] == "Scenario"],
            "event_names": [item["name"] for item in related_objects if item["object_type"] == "Event"],
            "uncertainty_names": uncertainty_names,
            "citation_ids": _unique(entry.citation_id for entry in matched_entries if entry.citation_id),
            "source_unit_ids": _unique(
                unit_id
                for entry in matched_entries
                for unit_id in (entry.provenance.get("source_unit_ids") or [])
            ),
            "evidence_signals": evidence_signals,
            "stance_hint": stance_hint,
            "sentiment_bias_hint": sentiment_bias_hint,
            "worldview_summary": self._build_worldview_summary(
                topic_names=topic_names,
                claim_names=claim_names,
                uncertainty_names=uncertainty_names,
                stance_hint=stance_hint,
            ),
        }

    def _extract_evidence_signals(self, evidence_bundle: EvidenceBundle) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for entry in evidence_bundle.source_entries:
            metadata = dict(entry.metadata or {})
            forecast_hints = list(metadata.get("forecast_hints") or [])
            if forecast_hints:
                for hint in forecast_hints:
                    normalized = dict(hint)
                    normalized.setdefault(
                        "citation_ids",
                        [entry.citation_id] if entry.citation_id else [],
                    )
                    normalized.setdefault(
                        "source_unit_ids",
                        list(entry.provenance.get("source_unit_ids") or []),
                    )
                    signals.append(normalized)
                continue
            if entry.conflict_status and entry.conflict_status != "none":
                signals.append(
                    {
                        "signal": entry.conflict_status,
                        "citation_ids": [entry.citation_id] if entry.citation_id else [],
                        "source_unit_ids": list(entry.provenance.get("source_unit_ids") or []),
                        "counterevidence": entry.summary or entry.title,
                    }
                )
        return signals

    def _build_world_summary(
        self,
        *,
        registries: Dict[str, List[Dict[str, Any]]],
        evidence_signals: List[Dict[str, Any]],
        missing_markers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        topic_names = [item["name"] for item in registries.get("topics", [])[:2]]
        claim_names = [item["name"] for item in registries.get("claims", [])[:1]]
        uncertainty_names = [
            item["name"] for item in registries.get("uncertainty_factors", [])[:1]
        ]
        headline_parts: List[str] = []
        if claim_names:
            headline_parts.append(f"Evidence centers on {claim_names[0]}")
        elif topic_names:
            headline_parts.append(f"Discussion centers on {topic_names[0]}")
        if uncertainty_names:
            headline_parts.append(f"while {uncertainty_names[0]} keeps the outlook contested")
        headline = ". ".join(part.rstrip(".") for part in headline_parts if part).strip()
        if headline:
            headline += "."
        return {
            "headline": headline or "Evidence-grounded preparation compiled limited world state.",
            "topic_count": len(registries.get("topics", [])),
            "claim_count": len(registries.get("claims", [])),
            "uncertainty_count": len(registries.get("uncertainty_factors", [])),
            "signal_count": len(evidence_signals),
            "missing_marker_count": len(missing_markers or []),
        }

    @staticmethod
    def _summarize_signal_conflicts(evidence_signals: List[Dict[str, Any]]) -> Dict[str, int]:
        summary = {"supports_count": 0, "contradicts_count": 0, "mixed_count": 0}
        for signal in evidence_signals:
            token = str(signal.get("signal") or "").strip()
            if token == "supports":
                summary["supports_count"] += 1
            elif token == "contradicts":
                summary["contradicts_count"] += 1
            elif token == "mixed":
                summary["mixed_count"] += 1
        return summary

    @staticmethod
    def _derive_stance_hint(
        evidence_signals: List[Dict[str, Any]],
        entity_type: str,
    ) -> str:
        support_count = len([item for item in evidence_signals if item.get("signal") == "supports"])
        contradict_count = len(
            [item for item in evidence_signals if item.get("signal") == "contradicts"]
        )
        mixed_count = len([item for item in evidence_signals if item.get("signal") == "mixed"])
        if support_count and mixed_count and contradict_count == 0:
            return "cautious"
        if contradict_count > support_count:
            return "opposing"
        if support_count > contradict_count and mixed_count == 0:
            return "supportive"
        if support_count or contradict_count or mixed_count:
            return "cautious"
        if entity_type.lower() in {"organization", "university", "governmentagency", "mediaoutlet"}:
            return "observer"
        return "neutral"

    @staticmethod
    def _derive_sentiment_bias_hint(evidence_signals: List[Dict[str, Any]]) -> float:
        score = 0.0
        for signal in evidence_signals:
            token = str(signal.get("signal") or "").strip()
            if token == "supports":
                score += 0.15
            elif token == "contradicts":
                score -= 0.2
            elif token == "mixed":
                score -= 0.05
        return round(max(-1.0, min(1.0, score)), 4)

    @staticmethod
    def _build_worldview_summary(
        *,
        topic_names: List[str],
        claim_names: List[str],
        uncertainty_names: List[str],
        stance_hint: str,
    ) -> str:
        parts: List[str] = []
        if claim_names:
            parts.append(f"Evidence emphasizes {claim_names[0]}")
        elif topic_names:
            parts.append(f"Attention centers on {topic_names[0]}")
        if uncertainty_names:
            parts.append(f"but {uncertainty_names[0]} argues for caution")
        if stance_hint and stance_hint not in {"neutral", "observer"}:
            parts.append(f"so the initial stance is {stance_hint}")
        summary = ". ".join(part.rstrip(".") for part in parts if part).strip()
        return f"{summary}." if summary else "Evidence grounding is sparse, so the initial stance remains neutral."
