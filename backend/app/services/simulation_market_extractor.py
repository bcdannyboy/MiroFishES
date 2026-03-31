"""
Run-scoped simulation-market extraction.

This layer extracts bounded, structured inference signals from simulated
discourse. It stays explicitly heuristic:
- it only supports binary and categorical forecast questions,
- it derives signals from stored action logs rather than native belief objects,
- it does not claim calibration or causal semantics.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models.simulation_market import (
    SIMULATION_MARKET_ARTIFACT_FILENAMES,
    SUPPORTED_SIMULATION_MARKET_QUESTION_TYPES,
    SimulationMarketAgentBelief,
    SimulationMarketDisagreementSummary,
    SimulationMarketManifest,
    SimulationMarketReference,
    SimulationMarketSnapshot,
)
from .forecast_manager import ForecastManager


_PERCENT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%")
_TEXT_FIELDS = (
    "content",
    "text",
    "body",
    "comment",
    "comment_text",
    "post_content",
    "quote_content",
    "analysis",
    "rationale",
)
_BINARY_BOUNDARY_NOTE = (
    "Synthetic market outputs are heuristic inference inputs derived from simulated discourse. "
    "They remain observational and are not calibrated real-world forecast probabilities."
)


class SimulationMarketExtractor:
    """Persist versioned run-scoped simulation-market artifacts."""

    SUPPORTED_PLATFORMS = ("twitter", "reddit")
    ARTIFACT_FILENAMES = dict(SIMULATION_MARKET_ARTIFACT_FILENAMES)

    def __init__(
        self,
        simulation_data_dir: Optional[str] = None,
        forecast_data_dir: Optional[str] = None,
    ) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        self.forecast_data_dir = forecast_data_dir or Config.FORECAST_DATA_DIR

    def persist_run_market_artifacts(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        forecast_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        artifacts = self.extract_run_market_artifacts(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
            forecast_id=forecast_id,
        )
        context = self._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
        )
        for artifact_name, filename in self.ARTIFACT_FILENAMES.items():
            self._write_json(
                os.path.join(context["run_dir"], filename),
                artifacts[artifact_name],
            )
        return artifacts

    def extract_run_market_artifacts(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        forecast_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = self._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
        )
        run_dir = context["run_dir"]
        extracted_at = self._resolve_extracted_at(run_dir)
        forecast_context = self._resolve_forecast_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_id=forecast_id,
        )
        actions, action_log_paths = self._load_action_records(run_dir)

        question_type = forecast_context["question_type"]
        supported_question_type = question_type in SUPPORTED_SIMULATION_MARKET_QUESTION_TYPES
        warnings: List[str] = []
        extraction_status = "ready"
        if not forecast_context["workspace_linked"]:
            extraction_status = "unlinked_forecast_workspace"
            warnings.append("forecast_workspace_unlinked")
        elif not supported_question_type:
            extraction_status = "unsupported_question_type"
            warnings.append(f"unsupported_question_type:{question_type or 'unknown'}")
        elif not action_log_paths:
            extraction_status = "missing_action_logs"
            warnings.append("missing_action_logs")

        belief_updates: List[Dict[str, Any]] = []
        beliefs_by_agent: Dict[int, Dict[str, Any]] = {}
        argument_tags: Counter[str] = Counter()
        argument_samples: dict[str, list[str]] = defaultdict(list)
        missing_information_signals: List[Dict[str, Any]] = []
        previous_by_agent: Dict[int, Dict[str, Any]] = {}

        if extraction_status not in {"unlinked_forecast_workspace", "unsupported_question_type", "missing_action_logs"}:
            for record in actions:
                extracted = self._extract_belief_from_record(
                    record,
                    simulation_id=simulation_id,
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    forecast_context=forecast_context,
                )
                if extracted is None:
                    continue
                reference = extracted["reference"]
                belief = extracted["belief"]
                prior = previous_by_agent.get(belief.agent_id)
                update_payload = belief.to_dict()
                update_payload["previous_probability"] = (
                    prior.get("probability") if prior is not None else None
                )
                update_payload["previous_outcome"] = (
                    prior.get("dominant_outcome") if prior is not None else None
                )
                update_payload["belief_changed"] = bool(
                    prior
                    and (
                        prior.get("probability") != belief.probability
                        or prior.get("dominant_outcome") != belief.dominant_outcome
                        or prior.get("outcome_distribution") != belief.outcome_distribution
                    )
                )
                belief_updates.append(update_payload)
                beliefs_by_agent[belief.agent_id] = belief.to_dict()
                previous_by_agent[belief.agent_id] = belief.to_dict()

                for tag in belief.rationale_tags:
                    argument_tags[tag] += 1
                    if belief.source_excerpt and belief.source_excerpt not in argument_samples[tag]:
                        argument_samples[tag].append(belief.source_excerpt)

                for request in belief.missing_information_requests:
                    missing_information_signals.append(
                        {
                            "request": request,
                            "agent_id": belief.agent_id,
                            "agent_name": belief.agent_name,
                            "question_type": belief.question_type,
                            "reference": reference.to_dict(),
                        }
                    )

            if not belief_updates:
                extraction_status = "no_signals"
                warnings.append("no_extractable_beliefs")

        sorted_beliefs = sorted(
            beliefs_by_agent.values(),
            key=lambda item: (item.get("agent_name", ""), item.get("agent_id", 0)),
        )
        disagreement = self._build_disagreement_summary(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_context=forecast_context,
            extraction_status=extraction_status,
            sorted_beliefs=sorted_beliefs,
            belief_updates=belief_updates,
            warnings=warnings,
        )
        snapshot = self._build_market_snapshot(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_context=forecast_context,
            extraction_status=extraction_status,
            sorted_beliefs=sorted_beliefs,
            belief_updates=belief_updates,
            disagreement=disagreement,
            missing_information_signals=missing_information_signals,
        )

        belief_book = {
            "artifact_type": "simulation_market_agent_belief_book",
            "schema_version": snapshot["schema_version"],
            "generator_version": snapshot["generator_version"],
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_context["forecast_id"],
            "question_type": question_type,
            "support_status": extraction_status,
            "beliefs": sorted_beliefs,
            "extracted_at": extracted_at,
        }
        belief_update_trace = {
            "artifact_type": "simulation_market_belief_update_trace",
            "schema_version": snapshot["schema_version"],
            "generator_version": snapshot["generator_version"],
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_context["forecast_id"],
            "question_type": question_type,
            "support_status": extraction_status,
            "updates": belief_updates,
            "extracted_at": extracted_at,
        }
        argument_map = {
            "artifact_type": "simulation_market_argument_map",
            "schema_version": snapshot["schema_version"],
            "generator_version": snapshot["generator_version"],
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_context["forecast_id"],
            "question_type": question_type,
            "support_status": extraction_status,
            "tags": [
                {
                    "tag": tag,
                    "count": count,
                    "sample_excerpts": argument_samples.get(tag, [])[:3],
                }
                for tag, count in sorted(argument_tags.items(), key=lambda item: (-item[1], item[0]))
            ],
            "extracted_at": extracted_at,
        }
        missing_information_payload = {
            "artifact_type": "simulation_market_missing_information_signals",
            "schema_version": snapshot["schema_version"],
            "generator_version": snapshot["generator_version"],
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_context["forecast_id"],
            "question_type": question_type,
            "support_status": extraction_status,
            "signals": missing_information_signals,
            "extracted_at": extracted_at,
        }

        manifest = SimulationMarketManifest(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_id=forecast_context["forecast_id"],
            question_type=question_type,
            extraction_status=extraction_status,
            supported_question_type=supported_question_type,
            forecast_workspace_linked=forecast_context["workspace_linked"],
            scope_linked_to_run=forecast_context["scope_linked_to_run"],
            artifact_paths=dict(self.ARTIFACT_FILENAMES),
            signal_counts={
                "agent_beliefs": len(sorted_beliefs),
                "belief_updates": len(belief_updates),
                "missing_information_requests": len(missing_information_signals),
            },
            warnings=warnings,
            source_artifacts={
                "run_manifest": "run_manifest.json",
                "run_state": "run_state.json" if os.path.exists(os.path.join(run_dir, "run_state.json")) else None,
                "action_logs": action_log_paths,
            },
            boundary_notes=[_BINARY_BOUNDARY_NOTE],
            extracted_at=extracted_at,
        ).to_dict()

        return {
            "simulation_market_manifest": manifest,
            "agent_belief_book": belief_book,
            "belief_update_trace": belief_update_trace,
            "disagreement_summary": disagreement,
            "market_snapshot": snapshot,
            "argument_map": argument_map,
            "missing_information_signals": missing_information_payload,
            # aliases for test-friendly access
            "manifest": manifest,
        }

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
        if run_dir is None:
            if not ensemble_id or not run_id:
                raise ValueError("simulation-market extraction requires ensemble_id and run_id")
            run_dir = os.path.join(
                sim_dir,
                "ensemble",
                f"ensemble_{str(ensemble_id).strip()}",
                "runs",
                f"run_{str(run_id).strip()}",
            )
        if config_path is None:
            config_path = os.path.join(run_dir, "resolved_config.json")
        return {
            "sim_dir": sim_dir,
            "run_dir": run_dir,
            "config_path": config_path,
        }

    def _resolve_forecast_context(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        forecast_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state_payload = self._read_json_if_exists(
            os.path.join(self.simulation_data_dir, simulation_id, "state.json")
        ) or {}
        resolved_forecast_id = str(
            forecast_id or state_payload.get("forecast_id", "") or ""
        ).strip() or None
        manager = ForecastManager(forecast_data_dir=self.forecast_data_dir)
        workspace = None
        if resolved_forecast_id:
            try:
                workspace = manager.get_workspace(resolved_forecast_id)
            except Exception:
                workspace = None
        if workspace is None:
            workspace = self._find_workspace_by_simulation_scope(
                manager,
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
            )
            if workspace is not None:
                resolved_forecast_id = workspace.forecast_question.forecast_id
        scope_linked_to_run = False
        question_type = None
        question_spec: Dict[str, Any] = {}
        if workspace is not None:
            question_type = workspace.forecast_question.question_type
            question_spec = dict(workspace.forecast_question.question_spec)
            scope = workspace.simulation_scope
            if scope is not None:
                scope_linked_to_run = (
                    scope.simulation_id == simulation_id
                    and (ensemble_id is None or str(ensemble_id) in scope.ensemble_ids)
                    and (run_id is None or str(run_id) in scope.run_ids)
                )
        return {
            "forecast_id": resolved_forecast_id,
            "workspace_linked": workspace is not None,
            "scope_linked_to_run": scope_linked_to_run,
            "question_type": question_type,
            "question_spec": question_spec,
        }

    def _find_workspace_by_simulation_scope(
        self,
        manager: ForecastManager,
        *,
        simulation_id: str,
        ensemble_id: Optional[str],
        run_id: Optional[str],
    ):
        try:
            workspaces = manager.list_workspaces()
        except Exception:
            return None
        for workspace in workspaces:
            scope = workspace.simulation_scope
            if scope is None or scope.simulation_id != simulation_id:
                continue
            if ensemble_id is not None and str(ensemble_id) not in scope.ensemble_ids:
                continue
            if run_id is not None and str(run_id) not in scope.run_ids:
                continue
            return workspace
        return None

    def _load_action_records(self, run_dir: str) -> tuple[List[Dict[str, Any]], List[str]]:
        actions: List[Dict[str, Any]] = []
        action_log_paths: List[str] = []
        for platform in self.SUPPORTED_PLATFORMS:
            path = os.path.join(run_dir, platform, "actions.jsonl")
            if not os.path.exists(path):
                continue
            action_log_paths.append(os.path.relpath(path, run_dir))
            with open(path, "r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "event_type" in payload or "agent_id" not in payload:
                        continue
                    actions.append(
                        {
                            "platform": payload.get("platform") or platform,
                            "round_num": int(payload.get("round", 0) or 0),
                            "line_number": line_number,
                            "timestamp": payload.get("timestamp") or datetime.now().isoformat(),
                            "agent_id": int(payload.get("agent_id", 0) or 0),
                            "agent_name": payload.get("agent_name") or f"agent-{payload.get('agent_id', 0)}",
                            "action_type": payload.get("action_type") or "UNKNOWN",
                            "action_args": payload.get("action_args", {}),
                            "result": payload.get("result"),
                        }
                    )
        actions.sort(key=lambda item: (item["timestamp"], item["platform"], item["line_number"]))
        return actions, action_log_paths

    def _extract_belief_from_record(
        self,
        record: Dict[str, Any],
        *,
        simulation_id: str,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        forecast_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        question_type = forecast_context["question_type"]
        action_args = record.get("action_args", {}) or {}
        text = self._extract_text(action_args, record.get("result"))
        reference = SimulationMarketReference(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            platform=record["platform"],
            round_num=record["round_num"],
            line_number=record["line_number"],
            agent_id=record["agent_id"],
            agent_name=record["agent_name"],
            timestamp=record["timestamp"],
            action_type=record["action_type"],
            source_artifact=f"{record['platform']}/actions.jsonl",
        )
        rationale_tags = self._extract_rationale_tags(action_args)
        missing_information_requests = self._extract_missing_information_requests(action_args)
        confidence, uncertainty_expression = self._extract_confidence(action_args)

        if question_type == "binary":
            probability, parse_mode = self._extract_probability(action_args, text)
            if probability is None:
                return None
            belief = SimulationMarketAgentBelief(
                forecast_id=forecast_context["forecast_id"],
                question_type=question_type,
                agent_id=record["agent_id"],
                agent_name=record["agent_name"],
                judgment_type="binary_probability",
                probability=probability,
                confidence=confidence,
                uncertainty_expression=uncertainty_expression,
                rationale_tags=rationale_tags,
                missing_information_requests=missing_information_requests,
                reference=reference,
                parse_mode=parse_mode,
                source_excerpt=text,
            )
            return {"belief": belief, "reference": reference}

        if question_type == "categorical":
            distribution, dominant_outcome, parse_mode = self._extract_categorical_distribution(
                action_args,
                text,
                forecast_context.get("question_spec", {}),
            )
            if not distribution and dominant_outcome is None:
                return None
            belief = SimulationMarketAgentBelief(
                forecast_id=forecast_context["forecast_id"],
                question_type=question_type,
                agent_id=record["agent_id"],
                agent_name=record["agent_name"],
                judgment_type="categorical_distribution",
                confidence=confidence,
                uncertainty_expression=uncertainty_expression,
                dominant_outcome=dominant_outcome,
                outcome_distribution=distribution,
                rationale_tags=rationale_tags,
                missing_information_requests=missing_information_requests,
                reference=reference,
                parse_mode=parse_mode,
                source_excerpt=text,
            )
            return {"belief": belief, "reference": reference}

        return None

    def _extract_text(self, action_args: Dict[str, Any], result: Any) -> str:
        parts: List[str] = []
        for field_name in _TEXT_FIELDS:
            value = action_args.get(field_name)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        if isinstance(result, str) and result.strip():
            parts.append(result.strip())
        return " ".join(parts).strip()

    def _extract_rationale_tags(self, action_args: Dict[str, Any]) -> List[str]:
        raw = (
            action_args.get("rationale_tags")
            or action_args.get("argument_tags")
            or action_args.get("topics")
            or []
        )
        if isinstance(raw, str):
            raw = [raw]
        return [
            str(item).strip()
            for item in raw
            if str(item).strip()
        ]

    def _extract_missing_information_requests(self, action_args: Dict[str, Any]) -> List[str]:
        raw = (
            action_args.get("missing_information_requests")
            or action_args.get("missing_information")
            or action_args.get("missing_info")
            or []
        )
        if isinstance(raw, str):
            raw = [raw]
        return [
            str(item).strip()
            for item in raw
            if str(item).strip()
        ]

    def _extract_confidence(self, action_args: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
        raw = action_args.get("confidence_score", action_args.get("confidence"))
        if raw is None or raw == "":
            return None, None
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized.endswith("%"):
                try:
                    return round(float(normalized[:-1]) / 100, 4), normalized
                except ValueError:
                    return None, normalized
            labels = {
                "high": 0.8,
                "medium": 0.55,
                "low": 0.3,
            }
            if normalized in labels:
                return labels[normalized], normalized
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None, str(raw).strip()
        if value > 1:
            value = value / 100
        return round(max(0.0, min(value, 1.0)), 4), None

    def _extract_probability(self, action_args: Dict[str, Any], text: str) -> tuple[Optional[float], str]:
        for key in ("forecast_probability", "probability", "implied_probability"):
            raw = action_args.get(key)
            if raw is None or raw == "":
                continue
            parsed = self._normalize_probability(raw)
            if parsed is not None:
                return parsed, "structured"
        match = _PERCENT_PATTERN.search(text or "")
        if match:
            return round(float(match.group(1)) / 100, 4), "heuristic"
        return None, "heuristic"

    def _extract_categorical_distribution(
        self,
        action_args: Dict[str, Any],
        text: str,
        question_spec: Dict[str, Any],
    ) -> tuple[Dict[str, float], Optional[str], str]:
        labels = [
            str(item).strip()
            for item in question_spec.get("outcome_labels", [])
            if str(item).strip()
        ]
        raw_distribution = action_args.get("outcome_distribution") or action_args.get("distribution")
        if isinstance(raw_distribution, dict):
            distribution: Dict[str, float] = {}
            for label, value in raw_distribution.items():
                normalized_label = str(label).strip()
                if labels and normalized_label not in labels:
                    continue
                probability = self._normalize_probability(value)
                if probability is not None:
                    distribution[normalized_label] = probability
            total = sum(distribution.values())
            if total > 0:
                distribution = {
                    label: round(value / total, 4)
                    for label, value in distribution.items()
                }
                dominant = max(distribution, key=distribution.get)
                return distribution, dominant, "structured"
        raw_outcome = (
            action_args.get("forecast_outcome")
            or action_args.get("outcome_label")
            or action_args.get("dominant_outcome")
        )
        if raw_outcome:
            dominant = str(raw_outcome).strip()
            if not labels or dominant in labels:
                return ({dominant: 1.0}, dominant, "structured")
        lowered_text = (text or "").lower()
        for label in labels:
            if label.lower() in lowered_text:
                return ({label: 1.0}, label, "heuristic")
        return {}, None, "heuristic"

    def _normalize_probability(self, raw: Any) -> Optional[float]:
        if raw is None or raw == "":
            return None
        if isinstance(raw, str):
            text = raw.strip()
            if text.endswith("%"):
                try:
                    return round(float(text[:-1]) / 100, 4)
                except ValueError:
                    return None
            raw = text
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value > 1:
            value = value / 100
        value = max(0.0, min(value, 1.0))
        return round(value, 4)

    def _build_disagreement_summary(
        self,
        *,
        simulation_id: str,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        forecast_context: Dict[str, Any],
        extraction_status: str,
        sorted_beliefs: List[Dict[str, Any]],
        belief_updates: List[Dict[str, Any]],
        warnings: List[str],
    ) -> Dict[str, Any]:
        question_type = forecast_context["question_type"]
        consensus_probability = None
        consensus_outcome = None
        distribution: Dict[str, float] = {}
        disagreement_index = 0.0
        range_low = None
        range_high = None

        if question_type == "binary" and sorted_beliefs:
            probabilities = [
                item["probability"]
                for item in sorted_beliefs
                if item.get("probability") is not None
            ]
            if probabilities:
                consensus_probability = round(sum(probabilities) / len(probabilities), 3)
                range_low = round(min(probabilities), 4)
                range_high = round(max(probabilities), 4)
                disagreement_index = round(range_high - range_low, 4)
                consensus_outcome = "yes" if consensus_probability >= 0.5 else "no"
        elif question_type == "categorical" and sorted_beliefs:
            aggregate: Dict[str, float] = defaultdict(float)
            for belief in sorted_beliefs:
                distribution_payload = belief.get("outcome_distribution") or {}
                if distribution_payload:
                    for label, value in distribution_payload.items():
                        aggregate[label] += float(value)
                elif belief.get("dominant_outcome"):
                    aggregate[belief["dominant_outcome"]] += 1.0
            total = sum(aggregate.values())
            if total > 0:
                distribution = {
                    label: round(value / total, 4)
                    for label, value in sorted(aggregate.items())
                }
                consensus_outcome = max(distribution, key=distribution.get)
                disagreement_index = round(1 - max(distribution.values()), 4)

        summary = SimulationMarketDisagreementSummary(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_id=forecast_context["forecast_id"],
            question_type=question_type,
            support_status=extraction_status,
            participant_count=len(sorted_beliefs),
            judgment_count=len(belief_updates),
            disagreement_index=disagreement_index if sorted_beliefs else 0.0,
            consensus_probability=consensus_probability,
            consensus_outcome=consensus_outcome,
            distribution=distribution,
            range_low=range_low,
            range_high=range_high,
            warnings=warnings,
            boundary_notes=[_BINARY_BOUNDARY_NOTE],
        )
        return summary.to_dict()

    def _build_market_snapshot(
        self,
        *,
        simulation_id: str,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        forecast_context: Dict[str, Any],
        extraction_status: str,
        sorted_beliefs: List[Dict[str, Any]],
        belief_updates: List[Dict[str, Any]],
        disagreement: Dict[str, Any],
        missing_information_signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        summary = SimulationMarketSnapshot(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_id=forecast_context["forecast_id"],
            question_type=forecast_context["question_type"],
            extraction_status=extraction_status,
            participating_agent_count=len(sorted_beliefs),
            extracted_signal_count=len(belief_updates),
            disagreement_index=disagreement.get("disagreement_index"),
            synthetic_consensus_probability=disagreement.get("consensus_probability"),
            dominant_outcome=disagreement.get("consensus_outcome"),
            categorical_distribution=disagreement.get("distribution", {}),
            missing_information_request_count=len(missing_information_signals),
            support_status=extraction_status,
            boundary_notes=[_BINARY_BOUNDARY_NOTE],
        )
        return summary.to_dict()

    def _resolve_extracted_at(self, run_dir: str) -> str:
        run_state_path = os.path.join(run_dir, "run_state.json")
        if os.path.exists(run_state_path):
            try:
                payload = self._read_json(run_state_path)
                return (
                    payload.get("completed_at")
                    or payload.get("updated_at")
                    or payload.get("started_at")
                    or datetime.now().isoformat()
                )
            except Exception:
                pass
        return datetime.now().isoformat()

    def _read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_json_if_exists(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            return self._read_json(path)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
