"""Run-scoped runtime graph state hydration and typed transition persistence."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from ..models.probabilistic import (
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
)


RUNTIME_GRAPH_ARTIFACT_FILENAMES = {
    "base_snapshot": "runtime_graph_base_snapshot.json",
    "state": "runtime_graph_state.json",
    "updates": "runtime_graph_updates.jsonl",
}

RUNTIME_TRANSITION_TYPES = (
    "event",
    "claim",
    "exposure",
    "belief_update",
    "topic_shift",
    "intervention",
    "round_state",
)

_POSITIVE_BELIEF_ACTIONS = {
    "LIKE_POST",
    "LIKE_COMMENT",
    "REPOST",
    "FOLLOW",
}
_NEGATIVE_BELIEF_ACTIONS = {
    "DISLIKE_POST",
    "DISLIKE_COMMENT",
    "MUTE",
}
_TOPIC_SHIFT_ACTIONS = {
    "SEARCH_POSTS",
    "SEARCH_USER",
    "TREND",
    "REFRESH",
}

_LOCK_GUARD = threading.Lock()
_LOCKS: Dict[str, threading.Lock] = {}


def _get_lock(path: str) -> threading.Lock:
    with _LOCK_GUARD:
        if path not in _LOCKS:
            _LOCKS[path] = threading.Lock()
        return _LOCKS[path]


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_token(value: Any) -> str:
    return str(value or "").strip()


def _unique_strings(values: Iterable[Any]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        token = _normalize_token(value)
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _basename(path: str) -> str:
    return os.path.basename(path.rstrip("/"))


def _safe_iso_now() -> str:
    return datetime.now().isoformat()


class RuntimeGraphStateStore:
    """Persist one hydrated runtime base snapshot plus typed transition artifacts."""

    def __init__(self, run_dir: str) -> None:
        self.run_dir = os.path.abspath(run_dir)
        self.base_snapshot_path = os.path.join(
            self.run_dir,
            RUNTIME_GRAPH_ARTIFACT_FILENAMES["base_snapshot"],
        )
        self.state_path = os.path.join(
            self.run_dir,
            RUNTIME_GRAPH_ARTIFACT_FILENAMES["state"],
        )
        self.updates_path = os.path.join(
            self.run_dir,
            RUNTIME_GRAPH_ARTIFACT_FILENAMES["updates"],
        )
        self._lock = _get_lock(self.state_path)

    def initialize(
        self,
        *,
        simulation_id: str,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        project_id: Optional[str],
        base_graph_id: str,
        runtime_graph_id: str,
        prepared_world_state: Optional[Dict[str, Any]] = None,
        prepared_agent_states: Optional[Dict[str, Any]] = None,
        graph_index_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        os.makedirs(self.run_dir, exist_ok=True)

        world_state = _as_dict(prepared_world_state)
        agent_states_payload = _as_dict(prepared_agent_states)
        graph_index = _as_dict(graph_index_payload)
        registries = _as_dict(world_state.get("registries"))
        agent_records = _as_list(agent_states_payload.get("agent_states"))
        agent_by_uuid = {
            _normalize_token(record.get("entity_uuid")): dict(record)
            for record in agent_records
            if _normalize_token(record.get("entity_uuid"))
        }

        actors = []
        for entity in _as_list(graph_index.get("entities")):
            entity_uuid = _normalize_token(entity.get("uuid"))
            agent_state = agent_by_uuid.get(entity_uuid, {})
            actor_record = {
                "entity_uuid": entity_uuid,
                "entity_name": _normalize_token(entity.get("name") or agent_state.get("entity_name")),
                "entity_type": self._resolve_entity_type(entity, agent_state),
                "summary": _normalize_token(entity.get("summary") or agent_state.get("worldview_summary")),
                "topic_names": _unique_strings(agent_state.get("topic_names") or []),
                "claim_names": _unique_strings(agent_state.get("claim_names") or []),
                "evidence_names": _unique_strings(agent_state.get("evidence_names") or []),
                "metric_names": _unique_strings(agent_state.get("metric_names") or []),
                "time_window_names": _unique_strings(agent_state.get("time_window_names") or []),
                "scenario_names": _unique_strings(agent_state.get("scenario_names") or []),
                "event_names": _unique_strings(agent_state.get("event_names") or []),
                "uncertainty_names": _unique_strings(agent_state.get("uncertainty_names") or []),
                "citation_ids": _unique_strings(agent_state.get("citation_ids") or []),
                "source_unit_ids": _unique_strings(agent_state.get("source_unit_ids") or []),
                "stance_hint": _normalize_token(agent_state.get("stance_hint")),
                "sentiment_bias_hint": _normalize_token(agent_state.get("sentiment_bias_hint")),
                "worldview_summary": _normalize_token(agent_state.get("worldview_summary")),
                "linked_object_uuids": _unique_strings(
                    node.get("uuid")
                    for node in _as_list(entity.get("related_nodes"))
                    if node.get("uuid")
                ),
            }
            actors.append(actor_record)

        if not actors:
            for agent_state in agent_records:
                actors.append(
                    {
                        "entity_uuid": _normalize_token(agent_state.get("entity_uuid")),
                        "entity_name": _normalize_token(agent_state.get("entity_name")),
                        "entity_type": _normalize_token(agent_state.get("entity_type")),
                        "summary": _normalize_token(agent_state.get("worldview_summary")),
                        "topic_names": _unique_strings(agent_state.get("topic_names") or []),
                        "claim_names": _unique_strings(agent_state.get("claim_names") or []),
                        "evidence_names": _unique_strings(agent_state.get("evidence_names") or []),
                        "metric_names": _unique_strings(agent_state.get("metric_names") or []),
                        "time_window_names": _unique_strings(agent_state.get("time_window_names") or []),
                        "scenario_names": _unique_strings(agent_state.get("scenario_names") or []),
                        "event_names": _unique_strings(agent_state.get("event_names") or []),
                        "uncertainty_names": _unique_strings(agent_state.get("uncertainty_names") or []),
                        "citation_ids": _unique_strings(agent_state.get("citation_ids") or []),
                        "source_unit_ids": _unique_strings(agent_state.get("source_unit_ids") or []),
                        "stance_hint": _normalize_token(agent_state.get("stance_hint")),
                        "sentiment_bias_hint": _normalize_token(agent_state.get("sentiment_bias_hint")),
                        "worldview_summary": _normalize_token(agent_state.get("worldview_summary")),
                        "linked_object_uuids": [],
                    }
                )

        analytical_objects = [dict(item) for item in _as_list(graph_index.get("analytical_objects"))]
        now = _safe_iso_now()
        base_snapshot = {
            "artifact_type": "runtime_graph_base_snapshot",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "project_id": project_id,
            "base_graph_id": base_graph_id,
            "runtime_graph_id": runtime_graph_id,
            "hydrated_at": now,
            "source_artifacts": {
                "prepared_world_state": "prepared_world_state.json",
                "prepared_agent_states": "prepared_agent_states.json",
                "graph_entity_index": "graph_entity_index.json",
            },
            "graph_summary": {
                "entity_count": int(graph_index.get("entity_count") or len(_as_list(graph_index.get("entities")))),
                "analytical_object_count": int(
                    graph_index.get("analytical_object_count")
                    or len(analytical_objects)
                ),
                "citation_coverage": graph_index.get("citation_coverage"),
            },
            "actor_count": len(actors),
            "analytical_object_count": len(analytical_objects),
            "world_summary": dict(world_state.get("world_summary") or {}),
            "retrieval_contract": dict(world_state.get("retrieval_contract") or {}),
            "grounding_summary": dict(world_state.get("grounding_summary") or {}),
            "registries": dict(registries),
            "citation_ids": _unique_strings(world_state.get("citation_ids") or []),
            "source_unit_ids": _unique_strings(world_state.get("source_unit_ids") or []),
            "actors": actors,
            "analytical_objects": analytical_objects,
        }
        runtime_state = {
            "artifact_type": "runtime_graph_state",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "project_id": project_id,
            "base_graph_id": base_graph_id,
            "runtime_graph_id": runtime_graph_id,
            "initialized_at": now,
            "updated_at": now,
            "base_snapshot_artifact": _basename(self.base_snapshot_path),
            "transition_log_artifact": _basename(self.updates_path),
            "world_summary": dict(world_state.get("world_summary") or {}),
            "retrieval_contract": dict(world_state.get("retrieval_contract") or {}),
            "grounding_summary": dict(world_state.get("grounding_summary") or {}),
            "citation_ids": _unique_strings(world_state.get("citation_ids") or []),
            "source_unit_ids": _unique_strings(world_state.get("source_unit_ids") or []),
            "missing_evidence_markers": list(world_state.get("missing_evidence_markers") or []),
            "transition_count": 0,
            "transition_counts": {
                transition_type: 0 for transition_type in RUNTIME_TRANSITION_TYPES
            },
            "current_round": 0,
            "current_simulated_hour": None,
            "platform_status": {
                "twitter": "pending",
                "reddit": "pending",
            },
            "active_topics": _unique_strings(
                item.get("name")
                for item in _as_list(registries.get("topics"))
                if item.get("name")
            ),
            "recent_transitions": [],
            "recent_claims": [],
            "recent_exposures": [],
            "belief_updates": [],
            "recent_events": [],
            "interventions": [],
            "round_history": [],
        }

        with self._lock:
            self._write_json(self.base_snapshot_path, base_snapshot)
            self._write_json(self.state_path, runtime_state)
            with open(self.updates_path, "w", encoding="utf-8") as handle:
                handle.write("")

        return {
            "base_snapshot": base_snapshot,
            "runtime_state": runtime_state,
        }

    def exists(self) -> bool:
        return os.path.exists(self.state_path) and os.path.exists(self.base_snapshot_path)

    def record_round_state(
        self,
        *,
        platform: str,
        round_num: int,
        phase: str,
        timestamp: Optional[str] = None,
        simulated_hour: Optional[int] = None,
        total_rounds: Optional[int] = None,
        total_actions: Optional[int] = None,
        agents_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        transition = self._build_transition(
            transition_type="round_state",
            platform=platform,
            round_num=round_num,
            timestamp=timestamp,
            payload={
                "phase": phase,
                "simulated_hour": simulated_hour,
                "total_rounds": total_rounds,
                "total_actions": total_actions,
                "agents_count": agents_count,
            },
            human_readable=f"{platform} {phase.replace('_', ' ')}",
        )
        self.append_transition(transition)
        return [transition]

    def record_event(
        self,
        *,
        platform: str,
        round_num: int,
        event_name: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        transition = self._build_transition(
            transition_type="event",
            platform=platform,
            round_num=round_num,
            timestamp=timestamp,
            payload={
                "event_name": event_name,
                "details": dict(details or {}),
            },
            human_readable=f"{platform} event: {event_name}",
        )
        self.append_transition(transition)
        return [transition]

    def record_intervention(
        self,
        *,
        platform: str,
        round_num: int,
        intervention_name: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        transition = self._build_transition(
            transition_type="intervention",
            platform=platform,
            round_num=round_num,
            timestamp=timestamp,
            payload={
                "intervention_name": intervention_name,
                "details": dict(details or {}),
            },
            human_readable=f"{platform} intervention: {intervention_name}",
        )
        self.append_transition(transition)
        return [transition]

    def record_action(
        self,
        *,
        platform: str,
        round_num: int,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True,
        timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.exists():
            return []

        action_args = dict(action_args or {})
        transition_time = timestamp or _safe_iso_now()
        transitions = []
        primary_type = (
            "claim"
            if action_type in {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"}
            else "exposure"
        )
        transitions.append(
            self._build_transition(
                transition_type=primary_type,
                platform=platform,
                round_num=round_num,
                timestamp=transition_time,
                agent_id=agent_id,
                agent_name=agent_name,
                payload={
                    "action_type": action_type,
                    "action_args": action_args,
                    "result": result,
                    "success": success,
                    "topics": self._extract_topic_names(action_args),
                },
                human_readable=self._humanize_action(agent_name, action_type, action_args),
            )
        )

        if action_type in _POSITIVE_BELIEF_ACTIONS | _NEGATIVE_BELIEF_ACTIONS:
            direction = "reinforce" if action_type in _POSITIVE_BELIEF_ACTIONS else "challenge"
            transitions.append(
                self._build_transition(
                    transition_type="belief_update",
                    platform=platform,
                    round_num=round_num,
                    timestamp=transition_time,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    payload={
                        "action_type": action_type,
                        "direction": direction,
                        "action_args": action_args,
                    },
                    human_readable=f"{agent_name} belief update via {action_type.lower()}",
                )
            )

        if action_type in _TOPIC_SHIFT_ACTIONS:
            transitions.append(
                self._build_transition(
                    transition_type="topic_shift",
                    platform=platform,
                    round_num=round_num,
                    timestamp=transition_time,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    payload={
                        "action_type": action_type,
                        "topic_names": self._extract_topic_names(action_args),
                        "action_args": action_args,
                    },
                    human_readable=f"{agent_name} shifted attention to {', '.join(self._extract_topic_names(action_args) or ['new topics'])}",
                )
            )

        for transition in transitions:
            self.append_transition(transition)
        return transitions

    def append_transition(self, transition: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._read_json(self.state_path)
            if not state:
                return transition

            transition_count = int(state.get("transition_count") or 0) + 1
            transition_type = _normalize_token(transition.get("transition_type"))
            transition["transition_index"] = transition_count
            transition["recorded_at"] = transition.get("recorded_at") or _safe_iso_now()

            with open(self.updates_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(transition, ensure_ascii=False) + "\n")

            state["transition_count"] = transition_count
            state["updated_at"] = transition["recorded_at"]
            counts = _as_dict(state.get("transition_counts"))
            counts[transition_type] = int(counts.get(transition_type) or 0) + 1
            state["transition_counts"] = counts
            state["current_round"] = max(
                int(state.get("current_round") or 0),
                int(transition.get("round_num") or 0),
            )

            topics = _unique_strings(
                list(state.get("active_topics") or [])
                + list(_as_dict(transition.get("payload")).get("topics") or [])
                + list(_as_dict(transition.get("payload")).get("topic_names") or [])
            )
            state["active_topics"] = topics
            state["recent_transitions"] = self._append_recent(
                _as_list(state.get("recent_transitions")),
                dict(transition),
            )

            if transition_type == "round_state":
                payload = _as_dict(transition.get("payload"))
                simulated_hour = payload.get("simulated_hour")
                if simulated_hour is not None:
                    state["current_simulated_hour"] = simulated_hour
                platform_status = _as_dict(state.get("platform_status"))
                platform_status[transition["platform"]] = self._phase_to_platform_status(
                    _normalize_token(payload.get("phase")),
                    platform_status.get(transition["platform"]),
                )
                state["platform_status"] = platform_status
                state["round_history"] = self._append_recent(
                    _as_list(state.get("round_history")),
                    dict(transition),
                )
            elif transition_type == "claim":
                state["recent_claims"] = self._append_recent(
                    _as_list(state.get("recent_claims")),
                    dict(transition),
                )
            elif transition_type == "exposure":
                state["recent_exposures"] = self._append_recent(
                    _as_list(state.get("recent_exposures")),
                    dict(transition),
                )
            elif transition_type == "belief_update":
                state["belief_updates"] = self._append_recent(
                    _as_list(state.get("belief_updates")),
                    dict(transition),
                )
            elif transition_type == "event":
                state["recent_events"] = self._append_recent(
                    _as_list(state.get("recent_events")),
                    dict(transition),
                )
            elif transition_type == "intervention":
                state["interventions"] = self._append_recent(
                    _as_list(state.get("interventions")),
                    dict(transition),
                )

            self._write_json(self.state_path, state)

        return transition

    def delete_artifacts(self) -> None:
        with self._lock:
            for path in (self.base_snapshot_path, self.state_path, self.updates_path):
                if os.path.exists(path):
                    os.remove(path)

    def artifact_paths(self) -> Dict[str, str]:
        return {
            "runtime_graph_base_snapshot": _basename(self.base_snapshot_path),
            "runtime_graph_state": _basename(self.state_path),
            "runtime_graph_updates": _basename(self.updates_path),
        }

    def _build_transition(
        self,
        *,
        transition_type: str,
        platform: str,
        round_num: int,
        timestamp: Optional[str] = None,
        agent_id: Optional[int] = None,
        agent_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        human_readable: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = self._read_json(self.base_snapshot_path) or {}
        actor_context = self._lookup_actor(agent_name)
        payload = dict(payload or {})
        topics = self._extract_topic_names(payload.get("action_args") or payload)
        matched_topics = self._match_topics(topics)
        citation_ids = _unique_strings(
            list(actor_context.get("citation_ids") or [])
            + [item.get("citation_id") for item in matched_topics["citations"]]
        )
        source_unit_ids = _unique_strings(
            list(actor_context.get("source_unit_ids") or [])
            + matched_topics["source_unit_ids"]
        )

        if topics and "topics" not in payload:
            payload["topics"] = topics

        return {
            "artifact_type": "runtime_state_transition",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "transition_id": f"rts_{uuid.uuid4().hex[:16]}",
            "transition_type": transition_type,
            "simulation_id": snapshot.get("simulation_id"),
            "ensemble_id": snapshot.get("ensemble_id"),
            "run_id": snapshot.get("run_id"),
            "project_id": snapshot.get("project_id"),
            "base_graph_id": snapshot.get("base_graph_id"),
            "runtime_graph_id": snapshot.get("runtime_graph_id"),
            "platform": platform,
            "round_num": int(round_num or 0),
            "timestamp": timestamp or _safe_iso_now(),
            "recorded_at": _safe_iso_now(),
            "agent": {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "entity_uuid": actor_context.get("entity_uuid"),
                "entity_type": actor_context.get("entity_type"),
                "stance_hint": actor_context.get("stance_hint"),
                "sentiment_bias_hint": actor_context.get("sentiment_bias_hint"),
            },
            "payload": payload,
            "provenance": {
                "run_scope": self._run_scope_token(snapshot),
                "citation_ids": citation_ids,
                "source_unit_ids": source_unit_ids,
                "graph_object_uuids": _unique_strings(
                    list(actor_context.get("linked_object_uuids") or [])
                    + matched_topics["object_uuids"]
                ),
            },
            "source_artifact": f"{platform}/actions.jsonl",
            "human_readable": human_readable or f"{platform} {transition_type}",
        }

    def _lookup_actor(self, agent_name: Optional[str]) -> Dict[str, Any]:
        snapshot = self._read_json(self.base_snapshot_path) or {}
        target_name = _normalize_token(agent_name).lower()
        for actor in _as_list(snapshot.get("actors")):
            if _normalize_token(actor.get("entity_name")).lower() == target_name:
                return dict(actor)
        return {}

    def _match_topics(self, topic_names: Iterable[Any]) -> Dict[str, Any]:
        snapshot = self._read_json(self.base_snapshot_path) or {}
        topics_by_name = {
            _normalize_token(item.get("name")).lower(): item
            for item in _as_list(_as_dict(snapshot.get("registries")).get("topics"))
            if _normalize_token(item.get("name"))
        }

        matched_objects = []
        citations = []
        source_unit_ids = []
        for topic_name in topic_names:
            match = topics_by_name.get(_normalize_token(topic_name).lower())
            if not match:
                continue
            matched_objects.append(match)
            source_unit_ids.extend(match.get("source_unit_ids") or [])
            citations.extend(
                {"citation_id": citation_id}
                for citation_id in _as_list(match.get("citation_ids"))
            )
        return {
            "object_uuids": _unique_strings(item.get("uuid") for item in matched_objects),
            "citations": citations,
            "source_unit_ids": _unique_strings(source_unit_ids),
        }

    def _extract_topic_names(self, payload: Optional[Dict[str, Any]]) -> List[str]:
        payload = _as_dict(payload)
        topic_names = []
        if payload.get("topic"):
            topic_names.append(payload.get("topic"))
        topic_names.extend(_as_list(payload.get("topics")))
        if payload.get("query"):
            topic_names.append(payload.get("query"))
        return _unique_strings(topic_names)

    def _humanize_action(
        self,
        agent_name: str,
        action_type: str,
        action_args: Dict[str, Any],
    ) -> str:
        text = _normalize_token(
            action_args.get("content")
            or action_args.get("quote_content")
            or action_args.get("query")
            or action_args.get("post_content")
            or action_args.get("comment_content")
        )
        if text:
            return f"{agent_name} {action_type.lower()} :: {text}"
        return f"{agent_name} {action_type.lower()}"

    def _phase_to_platform_status(
        self,
        phase: str,
        current_status: Optional[str],
    ) -> str:
        if phase in {"simulation_start", "round_start", "round_end"}:
            return "running"
        if phase == "simulation_end":
            return "completed"
        if phase == "simulation_failed":
            return "failed"
        if phase == "simulation_stopped":
            return "stopped"
        return _normalize_token(current_status) or "pending"

    def _run_scope_token(self, snapshot: Dict[str, Any]) -> str:
        if snapshot.get("ensemble_id") and snapshot.get("run_id"):
            return (
                f"{snapshot.get('simulation_id')}::"
                f"{snapshot.get('ensemble_id')}::"
                f"{snapshot.get('run_id')}"
            )
        return _normalize_token(snapshot.get("simulation_id"))

    def _resolve_entity_type(
        self,
        entity: Dict[str, Any],
        agent_state: Dict[str, Any],
    ) -> str:
        state_type = _normalize_token(agent_state.get("entity_type"))
        if state_type:
            return state_type
        for label in _as_list(entity.get("labels")):
            if label not in {"Entity", "Node"}:
                return _normalize_token(label)
        return ""

    def _append_recent(
        self,
        collection: List[Dict[str, Any]],
        item: Dict[str, Any],
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        collection.append(item)
        if len(collection) > limit:
            return collection[-limit:]
        return collection

    def _read_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
