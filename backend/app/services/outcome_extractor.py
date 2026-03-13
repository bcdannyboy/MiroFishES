"""
Run-level outcome extraction for probabilistic ensemble members.

This slice intentionally stays narrow:
- read one stored run's raw action logs and contracts,
- compute only the explicit count metrics in the current registry,
- persist a deterministic `metrics.json` artifact with completeness flags.

It does not fabricate richer probability or topic semantics that the backend
does not yet support.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from ..config import Config
from ..models.probabilistic import (
    DEFAULT_OUTCOME_METRICS,
    build_supported_outcome_metric,
    validate_outcome_metric_id,
)


METRICS_SCHEMA_VERSION = "probabilistic.metrics.v1"
METRICS_GENERATOR_VERSION = "probabilistic.metrics.generator.v1"


class OutcomeExtractor:
    """Build and persist deterministic run-level metrics artifacts."""

    METRICS_FILENAME = "metrics.json"
    RUN_MANIFEST_FILENAME = "run_manifest.json"
    OUTCOME_SPEC_FILENAME = "outcome_spec.json"
    TOP_AGENT_LIMIT = 5
    SUPPORTED_PLATFORMS = ("twitter", "reddit")
    _TEXT_FIELDS = (
        "content",
        "post_content",
        "comment_content",
        "original_content",
        "quote_content",
        "prompt",
        "query",
    )

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def extract_run_metrics(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        run_status: Optional[str] = None,
        platform_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return one deterministic metrics artifact for the requested run root."""
        context = self._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
        )
        run_dir = context["run_dir"]
        sim_dir = context["sim_dir"]

        requested_metric_ids, used_default_metric_ids = self._load_requested_metric_ids(
            simulation_id
        )
        config_payload = self._read_json(context["config_path"])
        run_state = self._read_json_if_exists(os.path.join(run_dir, "run_state.json"))
        run_manifest = self._read_json_if_exists(
            os.path.join(run_dir, self.RUN_MANIFEST_FILENAME)
        )

        expected_platforms = self._determine_expected_platforms(
            config_payload,
            platform_mode=platform_mode or (run_state or {}).get("platform_mode"),
        )
        log_summary = self._load_platform_logs(
            run_dir=run_dir,
            expected_platforms=expected_platforms,
        )
        metric_values = self._compute_metric_values(
            requested_metric_ids=requested_metric_ids,
            actions=log_summary["actions"],
        )
        timeline_summaries = self._build_timeline_summaries(
            actions=log_summary["actions"],
            observed_rounds=log_summary["observed_rounds"],
        )
        top_agents = self._build_top_agents(log_summary["actions"])
        top_topics = self._build_top_topics(
            config_payload=config_payload,
            actions=log_summary["actions"],
        )

        missing_platform_logs = [
            platform
            for platform in expected_platforms
            if not log_summary["log_presence"].get(platform, False)
        ]
        missing_simulation_end_platforms = [
            platform
            for platform in expected_platforms
            if not log_summary["platform_completion"].get(platform, False)
        ]
        effective_run_status = (
            (run_status or (run_state or {}).get("runner_status") or run_manifest.get("status", "unknown"))
            if run_manifest
            else run_status or (run_state or {}).get("runner_status") or "unknown"
        )
        missing_artifacts = [
            f"{platform}/actions.jsonl"
            for platform in missing_platform_logs
        ]
        warnings = []
        if effective_run_status != "completed":
            warnings.append(f"run_status:{effective_run_status}")
        warnings.extend(
            f"missing_simulation_end:{platform}"
            for platform in missing_simulation_end_platforms
        )
        total_actions_metric = metric_values.get("simulation.total_actions", {})
        timeline_matches_total_actions = (
            timeline_summaries["total_actions"]
            == total_actions_metric.get("value", len(log_summary["actions"]))
        )

        quality_checks = {
            "is_complete": not missing_platform_logs
            and not missing_simulation_end_platforms
            and effective_run_status == "completed",
            "status": "complete"
            if not missing_artifacts
            and not missing_simulation_end_platforms
            and effective_run_status == "completed"
            else "partial",
            "missing_platform_logs": missing_platform_logs,
            "missing_simulation_end_platforms": missing_simulation_end_platforms,
            "missing_artifacts": missing_artifacts,
            "warnings": warnings,
            "run_status": effective_run_status,
            "log_completeness": "complete" if not missing_platform_logs else "partial",
            "used_default_requested_metric_ids": used_default_metric_ids,
            "requested_metric_ids": requested_metric_ids,
            "observed_platforms": sorted(log_summary["observed_platforms"]),
            "top_topics_available": bool(top_topics),
            "legacy_layout_fallback_used": log_summary["legacy_layout_fallback_used"],
            "has_any_actions_log": bool(log_summary["action_log_paths"]),
            "timeline_matches_total_actions": timeline_matches_total_actions,
        }

        artifact = {
            "artifact_type": "run_metrics",
            "schema_version": METRICS_SCHEMA_VERSION,
            "generator_version": METRICS_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "requested_metric_ids": requested_metric_ids,
            "metric_values": metric_values,
            "event_flags": {
                "simulation_completed": bool(expected_platforms)
                and all(
                    log_summary["platform_completion"].get(platform, False)
                    for platform in expected_platforms
                ),
                "run_completed": effective_run_status == "completed",
                "run_failed": effective_run_status == "failed",
                "run_stopped": effective_run_status == "stopped",
                "platform_completion": {
                    platform: log_summary["platform_completion"].get(platform, False)
                    for platform in expected_platforms
                },
            },
            "timeline_summaries": timeline_summaries,
            "top_agents": top_agents,
            "top_topics": top_topics,
            "quality_checks": quality_checks,
            "source_artifacts": {
                "config": os.path.basename(context["config_path"]),
                "run_manifest": self.RUN_MANIFEST_FILENAME if run_manifest else None,
                "run_state": "run_state.json" if run_state else None,
                "outcome_spec": self.OUTCOME_SPEC_FILENAME
                if os.path.exists(os.path.join(sim_dir, self.OUTCOME_SPEC_FILENAME))
                else None,
                "action_logs": log_summary["action_log_paths"],
            },
            "extracted_at": (
                (run_state or {}).get("completed_at")
                or (run_state or {}).get("updated_at")
                or (run_manifest or {}).get("generated_at")
                or datetime.now().isoformat()
            ),
        }
        return artifact

    def persist_run_metrics(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        run_status: Optional[str] = None,
        platform_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write one `metrics.json` artifact and return the persisted payload."""
        artifact = self.extract_run_metrics(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
            run_status=run_status,
            platform_mode=platform_mode,
        )
        metrics_path = os.path.join(
            run_dir or self._resolve_run_context(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                config_path=config_path,
            )["run_dir"],
            self.METRICS_FILENAME,
        )
        self._write_json(metrics_path, artifact)
        return artifact

    def _resolve_run_context(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> Dict[str, str]:
        sim_dir = os.path.join(self.simulation_data_dir, simulation_id)
        if not run_dir:
            if ensemble_id and run_id:
                run_dir = os.path.join(
                    sim_dir,
                    "ensemble",
                    f"ensemble_{ensemble_id}",
                    "runs",
                    f"run_{run_id}",
                )
            else:
                run_dir = sim_dir
        if not config_path:
            if ensemble_id and run_id:
                config_path = os.path.join(run_dir, "resolved_config.json")
            else:
                config_path = os.path.join(run_dir, "simulation_config.json")
        return {
            "sim_dir": sim_dir,
            "run_dir": run_dir,
            "config_path": config_path,
        }

    def _load_requested_metric_ids(
        self,
        simulation_id: str,
    ) -> tuple[List[str], bool]:
        outcome_spec_path = os.path.join(
            self.simulation_data_dir,
            simulation_id,
            self.OUTCOME_SPEC_FILENAME,
        )
        if not os.path.exists(outcome_spec_path):
            return list(DEFAULT_OUTCOME_METRICS), True

        outcome_spec = self._read_json(outcome_spec_path)
        metric_ids = [
            validate_outcome_metric_id(metric["metric_id"])
            for metric in outcome_spec.get("metrics", [])
            if metric.get("metric_id")
        ]
        if not metric_ids:
            return list(DEFAULT_OUTCOME_METRICS), True
        return metric_ids, False

    def _determine_expected_platforms(
        self,
        config_payload: Dict[str, Any],
        *,
        platform_mode: Optional[str] = None,
    ) -> List[str]:
        if platform_mode in self.SUPPORTED_PLATFORMS:
            return [platform_mode]
        expected_platforms = [
            platform
            for platform in self.SUPPORTED_PLATFORMS
            if isinstance(config_payload.get(f"{platform}_config"), dict)
        ]
        if expected_platforms:
            return expected_platforms
        return list(self.SUPPORTED_PLATFORMS)

    def _load_platform_logs(
        self,
        *,
        run_dir: str,
        expected_platforms: Iterable[str],
    ) -> Dict[str, Any]:
        actions: List[Dict[str, Any]] = []
        action_log_paths: List[str] = []
        observed_rounds = set()
        observed_platforms = set()
        log_presence: Dict[str, bool] = {}
        platform_completion: Dict[str, bool] = {}
        legacy_layout_fallback_used = False

        for platform in self.SUPPORTED_PLATFORMS:
            log_path = os.path.join(run_dir, platform, "actions.jsonl")
            log_presence[platform] = os.path.exists(log_path)
            platform_completion[platform] = False
            if not os.path.exists(log_path):
                continue

            observed_platforms.add(platform)
            action_log_paths.append(os.path.relpath(log_path, run_dir))
            for entry in self._read_jsonl(log_path):
                event_type = entry.get("event_type")
                if event_type == "simulation_end":
                    platform_completion[platform] = True
                round_num = entry.get("round")
                if isinstance(round_num, int):
                    observed_rounds.add(round_num)
                if entry.get("action_type"):
                    actions.append(
                        {
                            "timestamp": entry.get("timestamp", ""),
                            "round_num": entry.get("round", entry.get("round_num", 0)),
                            "platform": platform,
                            "agent_id": entry.get("agent_id", 0),
                            "agent_name": entry.get("agent_name", ""),
                            "action_type": entry.get("action_type", ""),
                            "action_args": entry.get("action_args", {}),
                            "success": bool(entry.get("success", True)),
                        }
                    )

        if not actions and not any(log_presence.values()):
            legacy_log_path = os.path.join(run_dir, "actions.jsonl")
            if os.path.exists(legacy_log_path):
                legacy_layout_fallback_used = True
                action_log_paths.append(os.path.relpath(legacy_log_path, run_dir))
                for entry in self._read_jsonl(legacy_log_path):
                    round_num = entry.get("round", entry.get("round_num"))
                    if isinstance(round_num, int):
                        observed_rounds.add(round_num)
                    if entry.get("event_type") == "simulation_end" and entry.get("platform"):
                        platform = str(entry["platform"])
                        platform_completion[platform] = True
                    if entry.get("action_type"):
                        platform = str(entry.get("platform") or "legacy")
                        observed_platforms.add(platform)
                        actions.append(
                            {
                                "timestamp": entry.get("timestamp", ""),
                                "round_num": entry.get("round", entry.get("round_num", 0)),
                                "platform": platform,
                                "agent_id": entry.get("agent_id", 0),
                                "agent_name": entry.get("agent_name", ""),
                                "action_type": entry.get("action_type", ""),
                                "action_args": entry.get("action_args", {}),
                                "success": bool(entry.get("success", True)),
                            }
                        )

        actions.sort(
            key=lambda action: (
                action.get("timestamp", ""),
                action.get("round_num", 0),
                action.get("platform", ""),
                action.get("agent_id", 0),
                action.get("action_type", ""),
            )
        )

        return {
            "actions": actions,
            "action_log_paths": action_log_paths,
            "expected_platforms": list(expected_platforms),
            "log_presence": log_presence,
            "platform_completion": platform_completion,
            "observed_rounds": observed_rounds,
            "observed_platforms": observed_platforms,
            "legacy_layout_fallback_used": legacy_layout_fallback_used,
        }

    def _compute_metric_values(
        self,
        *,
        requested_metric_ids: Iterable[str],
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        metric_values: Dict[str, Dict[str, Any]] = {}
        twitter_total = sum(1 for action in actions if action["platform"] == "twitter")
        reddit_total = sum(1 for action in actions if action["platform"] == "reddit")
        total_actions = len(actions)

        for metric_id in requested_metric_ids:
            metric_payload = build_supported_outcome_metric(metric_id).to_dict()
            if metric_id == "simulation.total_actions":
                metric_payload["value"] = total_actions
            elif metric_id == "platform.twitter.total_actions":
                metric_payload["value"] = twitter_total
            elif metric_id == "platform.reddit.total_actions":
                metric_payload["value"] = reddit_total
            else:  # pragma: no cover - the allowlist validation should block this.
                raise ValueError(f"Unsupported outcome metric: {metric_id}")
            metric_values[metric_id] = metric_payload
        return metric_values

    def _build_timeline_summaries(
        self,
        *,
        actions: List[Dict[str, Any]],
        observed_rounds: set[int],
    ) -> Dict[str, Any]:
        round_counts: Dict[int, int] = defaultdict(int)
        for action in actions:
            round_num = int(action.get("round_num", 0))
            observed_rounds.add(round_num)
            round_counts[round_num] += 1

        nonzero_rounds = sorted(round_num for round_num in observed_rounds if round_num >= 0)
        timestamps = [action["timestamp"] for action in actions if action.get("timestamp")]

        return {
            "round_count": len(nonzero_rounds),
            "first_round": nonzero_rounds[0] if nonzero_rounds else None,
            "first_round_num": nonzero_rounds[0] if nonzero_rounds else None,
            "last_round": nonzero_rounds[-1] if nonzero_rounds else None,
            "last_round_num": nonzero_rounds[-1] if nonzero_rounds else None,
            "total_actions": len(actions),
            "max_actions_in_round": max(round_counts.values(), default=0),
            "first_action_time": min(timestamps) if timestamps else None,
            "last_action_time": max(timestamps) if timestamps else None,
        }

    def _build_top_agents(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        agent_totals: Dict[int, Dict[str, Any]] = {}
        for action in actions:
            agent_id = int(action.get("agent_id", 0))
            stats = agent_totals.setdefault(
                agent_id,
                {
                    "agent_id": agent_id,
                    "agent_name": action.get("agent_name", ""),
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                },
            )
            stats["total_actions"] += 1
            if action.get("platform") == "twitter":
                stats["twitter_actions"] += 1
            elif action.get("platform") == "reddit":
                stats["reddit_actions"] += 1

        ranked = sorted(
            agent_totals.values(),
            key=lambda stats: (
                -stats["total_actions"],
                stats["agent_name"],
                stats["agent_id"],
            ),
        )
        return ranked[: self.TOP_AGENT_LIMIT]

    def _build_top_topics(
        self,
        *,
        config_payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hot_topics = config_payload.get("event_config", {}).get("hot_topics", [])
        if not isinstance(hot_topics, list):
            return []

        mentions: Dict[str, int] = {}
        for topic in hot_topics:
            if not isinstance(topic, str) or not topic.strip():
                continue
            normalized_topic = topic.strip()
            topic_lower = normalized_topic.lower()
            mention_count = 0
            for action in actions:
                action_args = action.get("action_args", {})
                for field_name in self._TEXT_FIELDS:
                    content = action_args.get(field_name)
                    if isinstance(content, str):
                        mention_count += content.lower().count(topic_lower)
                if action_args.get("topic") == normalized_topic:
                    mention_count += 1
                topics = action_args.get("topics")
                if isinstance(topics, list):
                    mention_count += sum(1 for item in topics if item == normalized_topic)
            if mention_count > 0:
                mentions[normalized_topic] = mention_count

        ranked_topics = sorted(
            mentions.items(),
            key=lambda item: (-item[1], item[0]),
        )
        return [
            {"topic": topic, "mentions": count}
            for topic, count in ranked_topics
        ]

    def _read_json(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_json_if_exists(self, file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return None
        return self._read_json(file_path)

    def _read_jsonl(self, file_path: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        with open(file_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    def _write_json(self, file_path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
