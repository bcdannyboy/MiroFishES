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
        effective_run_status = (
            (run_status or (run_state or {}).get("runner_status") or run_manifest.get("status", "unknown"))
            if run_manifest
            else run_status or (run_state or {}).get("runner_status") or "unknown"
        )
        topic_analysis = self._build_topic_analysis(
            config_payload=config_payload,
            actions=log_summary["actions"],
        )
        top_topics = self._rank_topics(
            config_payload=config_payload,
            mentions=topic_analysis["mentions"],
        )
        metric_values = self._compute_metric_values(
            requested_metric_ids=requested_metric_ids,
            config_payload=config_payload,
            actions=log_summary["actions"],
            expected_platforms=expected_platforms,
            platform_completion=log_summary["platform_completion"],
            platform_completion_times=log_summary["platform_completion_times"],
            effective_run_status=effective_run_status,
            run_started_at=(run_state or {}).get("started_at"),
            configured_total_rounds=self._determine_configured_total_rounds(
                config_payload,
                run_state=run_state,
            ),
            top_topics=top_topics,
            topic_analysis=topic_analysis,
        )
        timeline_summaries = self._build_timeline_summaries(
            actions=log_summary["actions"],
            observed_rounds=log_summary["observed_rounds"],
        )
        top_agents = self._build_top_agents(log_summary["actions"])

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
        platform_completion_times: Dict[str, str] = {}
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
                    timestamp = entry.get("timestamp")
                    if isinstance(timestamp, str) and timestamp:
                        platform_completion_times[platform] = timestamp
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
                        timestamp = entry.get("timestamp")
                        if isinstance(timestamp, str) and timestamp:
                            platform_completion_times[platform] = timestamp
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
            "platform_completion_times": platform_completion_times,
            "observed_rounds": observed_rounds,
            "observed_platforms": observed_platforms,
            "legacy_layout_fallback_used": legacy_layout_fallback_used,
        }

    def _compute_metric_values(
        self,
        *,
        requested_metric_ids: Iterable[str],
        config_payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
        expected_platforms: Iterable[str],
        platform_completion: Dict[str, bool],
        platform_completion_times: Dict[str, str],
        effective_run_status: str,
        run_started_at: Optional[str],
        configured_total_rounds: Optional[int],
        top_topics: List[Dict[str, Any]],
        topic_analysis: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        metric_values: Dict[str, Dict[str, Any]] = {}
        expected_platforms = list(expected_platforms)
        total_actions = len(actions)
        actions_by_platform = {
            platform: [
                action for action in actions if action.get("platform") == platform
            ]
            for platform in self.SUPPORTED_PLATFORMS
        }
        platform_totals = {
            platform: len(platform_actions)
            for platform, platform_actions in actions_by_platform.items()
        }
        unique_active_agents = len(
            {
                self._normalize_agent_identity(action)
                for action in actions
                if self._normalize_agent_identity(action) is not None
            }
        )
        rounds_with_actions = len(
            {
                int(action.get("round_num", 0))
                for action in actions
                if isinstance(action.get("round_num"), int)
            }
        )
        simulation_first_action_time = self._get_first_action_timestamp(actions)
        simulation_last_action_time = self._get_last_action_timestamp(actions)
        platform_first_action_times = {
            platform: self._get_first_action_timestamp(platform_actions)
            for platform, platform_actions in actions_by_platform.items()
        }
        platform_last_action_times = {
            platform: self._get_last_action_timestamp(platform_actions)
            for platform, platform_actions in actions_by_platform.items()
        }
        completion_timestamp = self._get_latest_timestamp(
            platform_completion_times.get(platform)
            for platform in expected_platforms
        )
        simulation_completed = (
            effective_run_status == "completed"
            and bool(list(expected_platforms))
            and all(platform_completion.get(platform, False) for platform in expected_platforms)
        )
        round_action_counts = Counter(
            int(action.get("round_num", 0))
            for action in actions
            if isinstance(action.get("round_num"), int)
        )
        topic_mentions_total = sum(
            self._get_topic_entry_count(topic)
            for topic in top_topics
            if self._get_topic_entry_count(topic) is not None
        )
        dominant_topic = top_topics[0]["topic"] if top_topics else "none"
        dominant_topic_mentions = (
            self._get_topic_entry_count(top_topics[0])
            if top_topics and self._get_topic_entry_count(top_topics[0]) is not None
            else 0
        )
        twitter_total = platform_totals["twitter"]
        reddit_total = platform_totals["reddit"]
        twitter_share = (twitter_total / total_actions) if total_actions else 0.0
        reddit_share = (reddit_total / total_actions) if total_actions else 0.0
        platform_action_balance_gap = abs(twitter_share - reddit_share)
        agent_identities = [
            identity
            for identity in (
                self._normalize_agent_identity(action)
                for action in actions
            )
            if identity is not None
        ]
        agent_action_counts = sorted(Counter(agent_identities).values(), reverse=True)
        if total_actions <= 0:
            agent_action_concentration_hhi = None
            leading_platform = "none"
        else:
            agent_action_concentration_hhi = sum(
                (count / total_actions) ** 2
                for count in Counter(agent_identities).values()
            )
            if twitter_total > reddit_total:
                leading_platform = "twitter"
            elif reddit_total > twitter_total:
                leading_platform = "reddit"
            else:
                leading_platform = "tie"
        top_agent_action_share = (
            agent_action_counts[0] / total_actions
            if total_actions and agent_action_counts
            else 0.0
        )
        top_2_agent_action_share = (
            sum(agent_action_counts[:2]) / total_actions
            if total_actions and agent_action_counts
            else 0.0
        )
        max_round_action_share = (
            max(round_action_counts.values(), default=0) / total_actions
            if total_actions
            else 0.0
        )
        actions_per_active_round_cv = self._compute_actions_per_active_round_cv(
            round_action_counts.values()
        )
        topic_concentration_hhi = (
            sum(
                (self._get_topic_entry_count(topic) / topic_mentions_total) ** 2
                for topic in top_topics
                if self._get_topic_entry_count(topic) is not None
            )
            if topic_mentions_total > 0
            else None
        )
        dominant_topic_agent_reach = (
            len(topic_analysis["topic_agents"].get(dominant_topic, set()))
            if dominant_topic != "none"
            else 0
        )
        dominant_topic_platform_reach = (
            len(topic_analysis["topic_platforms"].get(dominant_topic, set()))
            if dominant_topic != "none"
            else 0
        )
        dominant_topic_round_reach = (
            len(topic_analysis["topic_rounds"].get(dominant_topic, set()))
            if dominant_topic != "none"
            else 0
        )
        shared_topic_lags = self._compute_shared_topic_lags(topic_analysis)
        topic_transfer_observed = bool(shared_topic_lags)

        for metric_id in requested_metric_ids:
            metric_payload = build_supported_outcome_metric(metric_id).to_dict()
            if metric_id == "simulation.total_actions":
                metric_payload["value"] = total_actions
            elif metric_id == "simulation.any_actions":
                metric_payload["value"] = total_actions > 0
            elif metric_id == "simulation.completed":
                metric_payload["value"] = simulation_completed
            elif metric_id == "simulation.unique_active_agents":
                metric_payload["value"] = unique_active_agents
            elif metric_id == "simulation.rounds_with_actions":
                metric_payload["value"] = rounds_with_actions
            elif metric_id == "simulation.observed_action_window_seconds":
                metric_payload["value"] = self._seconds_between(
                    simulation_first_action_time,
                    simulation_last_action_time,
                )
            elif metric_id == "simulation.observed_completion_window_seconds":
                metric_payload["value"] = self._seconds_between(
                    simulation_first_action_time,
                    completion_timestamp,
                )
            elif metric_id == "simulation.time_to_first_action_seconds":
                metric_payload["value"] = self._seconds_between(
                    run_started_at,
                    simulation_first_action_time,
                )
                if metric_payload["value"] is None:
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_simulation_time_to_first_action_evidence",
                    )
            elif metric_id == "simulation.active_round_share":
                if configured_total_rounds and configured_total_rounds > 0:
                    metric_payload["value"] = rounds_with_actions / configured_total_rounds
                else:
                    metric_payload["value"] = None
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_simulation_round_coverage_evidence",
                    )
            elif metric_id == "simulation.actions_per_active_round_cv":
                metric_payload["value"] = actions_per_active_round_cv
                if metric_payload["value"] is None:
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_simulation_round_distribution_evidence",
                    )
            elif metric_id == "simulation.agent_action_concentration_hhi":
                metric_payload["value"] = agent_action_concentration_hhi
            elif metric_id == "simulation.top_agent_action_share":
                metric_payload["value"] = top_agent_action_share
            elif metric_id == "simulation.top_2_agent_action_share":
                metric_payload["value"] = top_2_agent_action_share
            elif metric_id == "simulation.max_round_action_share":
                metric_payload["value"] = max_round_action_share
            elif metric_id == "simulation.top_agent_action_share_ge_0_5":
                metric_payload["value"] = top_agent_action_share >= 0.5
            elif metric_id == "platform.twitter.total_actions":
                metric_payload["value"] = twitter_total
            elif metric_id == "platform.reddit.total_actions":
                metric_payload["value"] = reddit_total
            elif metric_id == "platform.twitter.any_actions":
                metric_payload["value"] = twitter_total > 0
            elif metric_id == "platform.reddit.any_actions":
                metric_payload["value"] = reddit_total > 0
            elif metric_id == "platform.twitter.action_share":
                metric_payload["value"] = twitter_share
            elif metric_id == "platform.reddit.action_share":
                metric_payload["value"] = reddit_share
            elif metric_id == "platform.twitter.observed_action_window_seconds":
                metric_payload["value"] = self._seconds_between(
                    platform_first_action_times["twitter"],
                    platform_last_action_times["twitter"],
                )
            elif metric_id == "platform.reddit.observed_action_window_seconds":
                metric_payload["value"] = self._seconds_between(
                    platform_first_action_times["reddit"],
                    platform_last_action_times["reddit"],
                )
            elif metric_id == "platform.twitter.time_to_first_action_seconds":
                metric_payload["value"] = self._seconds_between(
                    run_started_at,
                    platform_first_action_times["twitter"],
                )
                if metric_payload["value"] is None:
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_platform_time_to_first_action_evidence",
                    )
            elif metric_id == "platform.reddit.time_to_first_action_seconds":
                metric_payload["value"] = self._seconds_between(
                    run_started_at,
                    platform_first_action_times["reddit"],
                )
                if metric_payload["value"] is None:
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_platform_time_to_first_action_evidence",
                    )
            elif metric_id == "platform.leading_platform":
                metric_payload["value"] = leading_platform
            elif metric_id == "platform.action_balance_gap":
                metric_payload["value"] = platform_action_balance_gap
            elif metric_id == "platform.action_balance_gap_ge_0_5":
                metric_payload["value"] = platform_action_balance_gap >= 0.5
            elif metric_id == "platform.action_balance_band":
                metric_payload["value"] = self._classify_action_balance_band(
                    platform_action_balance_gap,
                    total_actions=total_actions,
                )
            elif metric_id == "cross_platform.first_action_lag_seconds":
                metric_payload["value"] = self._seconds_between(
                    platform_first_action_times["twitter"],
                    platform_first_action_times["reddit"],
                    absolute=True,
                )
            elif metric_id == "cross_platform.completion_lag_seconds":
                metric_payload["value"] = self._seconds_between(
                    platform_completion_times.get("twitter"),
                    platform_completion_times.get("reddit"),
                    absolute=True,
                )
                if metric_payload["value"] is None:
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_cross_platform_completion_evidence",
                    )
            elif metric_id == "cross_platform.topic_transfer_observed":
                if self._has_cross_platform_topic_transfer_evidence(
                    config_payload=config_payload,
                    actions_by_platform=actions_by_platform,
                ):
                    metric_payload["value"] = topic_transfer_observed
                else:
                    metric_payload["value"] = None
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_cross_platform_topic_transfer_evidence",
                    )
            elif metric_id == "cross_platform.topic_transfer_lag_seconds":
                if self._has_cross_platform_topic_transfer_evidence(
                    config_payload=config_payload,
                    actions_by_platform=actions_by_platform,
                ):
                    metric_payload["value"] = min(shared_topic_lags) if shared_topic_lags else None
                else:
                    metric_payload["value"] = None
                    self._append_metric_warning(
                        metric_payload,
                        "insufficient_cross_platform_topic_transfer_evidence",
                    )
            elif metric_id == "content.unique_topics_mentioned":
                metric_payload["value"] = len(top_topics)
            elif metric_id == "content.top_topic_share":
                metric_payload["value"] = (
                    dominant_topic_mentions / topic_mentions_total
                    if topic_mentions_total > 0
                    else 0.0
                )
            elif metric_id == "content.top_topic_share_ge_0_5":
                metric_payload["value"] = (
                    (dominant_topic_mentions / topic_mentions_total) >= 0.5
                    if topic_mentions_total > 0
                    else False
                )
            elif metric_id == "content.dominant_topic":
                metric_payload["value"] = dominant_topic
            elif metric_id == "content.dominant_topic_agent_reach":
                metric_payload["value"] = dominant_topic_agent_reach
            elif metric_id == "content.dominant_topic_platform_reach":
                metric_payload["value"] = dominant_topic_platform_reach
            elif metric_id == "content.dominant_topic_round_reach":
                metric_payload["value"] = dominant_topic_round_reach
            elif metric_id == "content.topic_concentration_hhi":
                metric_payload["value"] = topic_concentration_hhi
            elif metric_id == "content.topic_concentration_band":
                metric_payload["value"] = self._classify_topic_concentration_band(
                    topic_concentration_hhi
                )
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
        return self._rank_topics(
            config_payload=config_payload,
            mentions=self._build_topic_mentions(
                config_payload=config_payload,
                actions=actions,
            ),
        )

    def _rank_topics(
        self,
        *,
        config_payload: Dict[str, Any],
        mentions: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        hot_topics = config_payload.get("event_config", {}).get("hot_topics", [])
        topic_order = {
            topic.strip(): index
            for index, topic in enumerate(hot_topics)
            if isinstance(topic, str) and topic.strip()
        }
        ranked_topics = sorted(
            mentions.items(),
            key=lambda item: (
                -item[1],
                topic_order.get(item[0], len(topic_order)),
                item[0],
            ),
        )
        return [
            {"topic": topic, "mentions": count, "count": count}
            for topic, count in ranked_topics
        ]

    def _build_topic_mentions(
        self,
        *,
        config_payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        return self._build_topic_analysis(
            config_payload=config_payload,
            actions=actions,
        )["mentions"]

    def _build_topic_analysis(
        self,
        *,
        config_payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        hot_topics = config_payload.get("event_config", {}).get("hot_topics", [])
        normalized_hot_topics = [
            topic.strip()
            for topic in hot_topics
            if isinstance(topic, str) and topic.strip()
        ]
        topic_aliases = {
            topic.lower(): topic
            for topic in normalized_hot_topics
        }
        mentions: Dict[str, int] = {}
        topic_agents: Dict[str, set[str]] = defaultdict(set)
        topic_platforms: Dict[str, set[str]] = defaultdict(set)
        topic_rounds: Dict[str, set[int]] = defaultdict(set)
        topic_first_seen_by_platform: Dict[str, Dict[str, str]] = defaultdict(dict)

        for action in actions:
            action_args = action.get("action_args", {})
            text_topic_counts = self._extract_hot_topic_counts(
                action_args,
                normalized_hot_topics,
            )
            explicit_topics = self._extract_explicit_topics(
                action_args,
                topic_aliases=topic_aliases,
            )

            for topic, count in text_topic_counts.items():
                mentions[topic] = mentions.get(topic, 0) + count
            for topic in explicit_topics:
                mentions[topic] = mentions.get(topic, 0) + 1

            action_topics = set(text_topic_counts).union(explicit_topics)
            if not action_topics:
                continue

            agent_identity = self._normalize_agent_identity(action)
            platform = action.get("platform")
            round_num = action.get("round_num")
            timestamp = action.get("timestamp")

            for topic in action_topics:
                if agent_identity is not None:
                    topic_agents[topic].add(agent_identity)
                if isinstance(platform, str) and platform:
                    topic_platforms[topic].add(platform)
                if isinstance(round_num, int):
                    topic_rounds[topic].add(round_num)
                if isinstance(platform, str) and platform and isinstance(timestamp, str):
                    existing = topic_first_seen_by_platform[topic].get(platform)
                    if self._seconds_between(timestamp, existing, absolute=False) is None:
                        topic_first_seen_by_platform[topic][platform] = timestamp
                    elif self._seconds_between(timestamp, existing, absolute=False) < 0:
                        topic_first_seen_by_platform[topic][platform] = timestamp

        return {
            "mentions": mentions,
            "topic_agents": topic_agents,
            "topic_platforms": topic_platforms,
            "topic_rounds": topic_rounds,
            "topic_first_seen_by_platform": topic_first_seen_by_platform,
        }

    def _extract_hot_topic_counts(
        self,
        action_args: Dict[str, Any],
        hot_topics: List[str],
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for topic in hot_topics:
            topic_lower = topic.lower()
            mention_count = 0
            for field_name in self._TEXT_FIELDS:
                content = action_args.get(field_name)
                if isinstance(content, str):
                    mention_count += content.lower().count(topic_lower)
            if mention_count > 0:
                counts[topic] = mention_count
        return counts

    def _extract_explicit_topics(
        self,
        action_args: Dict[str, Any],
        *,
        topic_aliases: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        explicit_topics: List[str] = []
        seen = set()
        for field_name in ("topic", "topics"):
            for topic in self._collect_topic_labels(
                action_args.get(field_name),
                topic_aliases=topic_aliases or {},
            ):
                if topic in seen:
                    continue
                explicit_topics.append(topic)
                seen.add(topic)
        return explicit_topics

    def _collect_topic_labels(
        self,
        raw_topic_value: Any,
        *,
        topic_aliases: Dict[str, str],
    ) -> List[str]:
        if isinstance(raw_topic_value, str):
            canonical = self._canonicalize_topic_label(
                raw_topic_value,
                topic_aliases=topic_aliases,
            )
            return [canonical] if canonical else []
        if isinstance(raw_topic_value, list):
            labels: List[str] = []
            for item in raw_topic_value:
                labels.extend(
                    self._collect_topic_labels(item, topic_aliases=topic_aliases)
                )
            return labels
        if isinstance(raw_topic_value, dict):
            for key in ("topic", "label", "name"):
                if key in raw_topic_value:
                    return self._collect_topic_labels(
                        raw_topic_value.get(key),
                        topic_aliases=topic_aliases,
                    )
        return []

    def _canonicalize_topic_label(
        self,
        raw_topic: Any,
        *,
        topic_aliases: Dict[str, str],
    ) -> Optional[str]:
        if not isinstance(raw_topic, str):
            return None
        normalized = raw_topic.strip()
        if not normalized:
            return None
        return topic_aliases.get(normalized.lower(), normalized)

    def _get_topic_entry_count(self, topic_entry: Dict[str, Any]) -> Optional[int]:
        raw_count = topic_entry.get("mentions", topic_entry.get("count"))
        if not isinstance(raw_count, int):
            return None
        return raw_count

    def _determine_configured_total_rounds(
        self,
        config_payload: Dict[str, Any],
        *,
        run_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        time_config = config_payload.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours")
        minutes_per_round = time_config.get("minutes_per_round")
        if isinstance(total_hours, (int, float)) and isinstance(minutes_per_round, (int, float)):
            if total_hours > 0 and minutes_per_round > 0:
                return max(int(total_hours * 60 / minutes_per_round), 0)
        total_rounds = (run_state or {}).get("total_rounds")
        if isinstance(total_rounds, int) and total_rounds > 0:
            return total_rounds
        return None

    def _compute_actions_per_active_round_cv(
        self,
        round_counts: Iterable[int],
    ) -> Optional[float]:
        normalized_counts = [int(count) for count in round_counts if int(count) > 0]
        if not normalized_counts:
            return None
        mean = sum(normalized_counts) / len(normalized_counts)
        if mean <= 0:
            return None
        variance = sum((count - mean) ** 2 for count in normalized_counts) / len(
            normalized_counts
        )
        return (variance ** 0.5) / mean

    def _append_metric_warning(
        self,
        metric_payload: Dict[str, Any],
        warning: str,
    ) -> None:
        warnings = metric_payload.setdefault("warnings", [])
        if warning not in warnings:
            warnings.append(warning)

    def _classify_action_balance_band(
        self,
        gap: float,
        *,
        total_actions: int,
    ) -> str:
        epsilon = 1e-9
        if total_actions <= 0:
            return "none"
        if gap >= (0.5 - epsilon):
            return "dominated"
        if gap >= (0.2 - epsilon):
            return "tilted"
        return "balanced"

    def _compute_shared_topic_lags(self, topic_analysis: Dict[str, Any]) -> List[float]:
        lags: List[float] = []
        for platform_times in topic_analysis["topic_first_seen_by_platform"].values():
            twitter_time = platform_times.get("twitter")
            reddit_time = platform_times.get("reddit")
            lag = self._seconds_between(twitter_time, reddit_time, absolute=True)
            if lag is not None:
                lags.append(lag)
        return sorted(lags)

    def _has_cross_platform_topic_transfer_evidence(
        self,
        *,
        config_payload: Dict[str, Any],
        actions_by_platform: Dict[str, List[Dict[str, Any]]],
    ) -> bool:
        if not actions_by_platform.get("twitter") or not actions_by_platform.get("reddit"):
            return False
        hot_topics = config_payload.get("event_config", {}).get("hot_topics", [])
        has_configured_topics = any(
            isinstance(topic, str) and topic.strip()
            for topic in hot_topics
        )
        has_explicit_topics = any(
            self._extract_explicit_topics(action.get("action_args", {}))
            for platform_actions in actions_by_platform.values()
            for action in platform_actions
        )
        return has_configured_topics or has_explicit_topics

    def _classify_topic_concentration_band(
        self,
        topic_concentration_hhi: Optional[float],
    ) -> str:
        if topic_concentration_hhi is None:
            return "none"
        if topic_concentration_hhi >= 0.55:
            return "focused"
        if topic_concentration_hhi >= 0.35:
            return "mixed"
        return "diffuse"

    def _normalize_agent_identity(self, action: Dict[str, Any]) -> Optional[str]:
        agent_id = action.get("agent_id")
        if isinstance(agent_id, int):
            return f"id:{agent_id}"
        agent_name = action.get("agent_name")
        if isinstance(agent_name, str) and agent_name.strip():
            return f"name:{agent_name.strip()}"
        return None

    def _get_first_action_timestamp(
        self,
        actions: List[Dict[str, Any]],
    ) -> Optional[str]:
        return self._get_earliest_timestamp(
            action.get("timestamp")
            for action in actions
            if action.get("timestamp")
        )

    def _get_last_action_timestamp(
        self,
        actions: List[Dict[str, Any]],
    ) -> Optional[str]:
        return self._get_latest_timestamp(
            action.get("timestamp")
            for action in actions
            if action.get("timestamp")
        )

    def _get_earliest_timestamp(
        self,
        timestamps: Iterable[Optional[str]],
    ) -> Optional[str]:
        parsed = [
            (self._parse_timestamp(timestamp), timestamp)
            for timestamp in timestamps
            if isinstance(timestamp, str) and self._parse_timestamp(timestamp) is not None
        ]
        if not parsed:
            return None
        return min(parsed, key=lambda item: item[0])[1]

    def _get_latest_timestamp(
        self,
        timestamps: Iterable[Optional[str]],
    ) -> Optional[str]:
        parsed = [
            (self._parse_timestamp(timestamp), timestamp)
            for timestamp in timestamps
            if isinstance(timestamp, str) and self._parse_timestamp(timestamp) is not None
        ]
        if not parsed:
            return None
        return max(parsed, key=lambda item: item[0])[1]

    def _seconds_between(
        self,
        start_timestamp: Optional[str],
        end_timestamp: Optional[str],
        *,
        absolute: bool = False,
    ) -> Optional[float]:
        start_dt = self._parse_timestamp(start_timestamp)
        end_dt = self._parse_timestamp(end_timestamp)
        if start_dt is None or end_dt is None:
            return None
        delta = (end_dt - start_dt).total_seconds()
        return abs(delta) if absolute else delta

    def _parse_timestamp(self, timestamp: Optional[str]) -> Optional[datetime]:
        if not isinstance(timestamp, str) or not timestamp:
            return None
        normalized = timestamp.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

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
