"""
Deterministic aggregation of run-scoped simulation-market artifacts.

This layer converts extracted simulated-market discourse artifacts into one
bounded, inspectable signal bundle for forecast-engine consumption.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional

from ..config import Config
from ..models.forecasting import ForecastWorkspaceRecord
from ..models.simulation_market import (
    SIMULATION_MARKET_ARTIFACT_FILENAMES,
    SIMULATION_MARKET_SUMMARY_ARTIFACT_TYPE,
    SimulationMarketReference,
    SimulationMarketSummary,
)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _mean(values: Iterable[float]) -> Optional[float]:
    normalized = [float(value) for value in values]
    if not normalized:
        return None
    return sum(normalized) / len(normalized)


def _normalize_distribution(weights: Dict[str, Any]) -> Dict[str, float]:
    usable: Dict[str, float] = {}
    for label, value in (weights or {}).items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score < 0:
            continue
        normalized_label = str(label or "").strip()
        if not normalized_label:
            continue
        usable[normalized_label] = usable.get(normalized_label, 0.0) + score
    total = sum(usable.values())
    if total <= 0:
        return {}
    return {
        label: round(score / total, 6)
        for label, score in sorted(usable.items(), key=lambda item: (-item[1], item[0]))
    }


def _top_distribution_label(distribution: Dict[str, float]) -> Optional[str]:
    if not distribution:
        return None
    return max(distribution.items(), key=lambda item: (float(item[1]), item[0]))[0]


def _dedupe_requests(values: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for item in values:
        normalized = str(item or "").strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _reference_signature(reference: Dict[str, Any]) -> tuple[Any, ...]:
    return (
        reference.get("simulation_id"),
        reference.get("ensemble_id"),
        reference.get("run_id"),
        reference.get("source_artifact"),
        reference.get("line_number"),
        reference.get("agent_id"),
        reference.get("timestamp"),
    )


class SimulationMarketAggregator:
    """Derive stable forecast-engine signal summaries from raw market artifacts."""

    def __init__(self, *, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def summarize_workspace(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        evidence_bundle_ids: Optional[list[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        scope = workspace.simulation_scope
        contract = workspace.simulation_worker_contract
        simulation_id = (
            (scope.simulation_id if scope is not None else None)
            or (contract.simulation_id if contract is not None else None)
            or workspace.forecast_question.primary_simulation_id
        )
        ensemble_id = (
            (scope.latest_ensemble_id if scope is not None else None)
            or ((contract.ensemble_ids[-1]) if contract is not None and contract.ensemble_ids else None)
        )
        run_id = (scope.latest_run_id if scope is not None else None) or (
            contract.run_ids[-1] if contract is not None and getattr(contract, "run_ids", None) else None
        )
        if not simulation_id or not ensemble_id or not run_id:
            return None
        return self.summarize_run_market_artifacts(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            evidence_bundle_ids=evidence_bundle_ids,
        )

    def summarize_run_market_artifacts(
        self,
        simulation_id: str,
        *,
        ensemble_id: Optional[str],
        run_id: Optional[str],
        run_dir: Optional[str] = None,
        evidence_bundle_ids: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        if run_dir is None:
            if not ensemble_id or not run_id:
                raise ValueError("simulation-market aggregation requires ensemble_id and run_id")
            run_dir = os.path.join(
                self.simulation_data_dir,
                simulation_id,
                "ensemble",
                f"ensemble_{str(ensemble_id).strip()}",
                "runs",
                f"run_{str(run_id).strip()}",
            )
        manifest = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["simulation_market_manifest"]))
        snapshot = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["market_snapshot"]))
        disagreement = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["disagreement_summary"]))
        beliefs = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["agent_belief_book"]))
        updates = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["belief_update_trace"]))
        argument_map = self._read_json(os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["argument_map"]))
        missing_information = self._read_json(
            os.path.join(run_dir, SIMULATION_MARKET_ARTIFACT_FILENAMES["missing_information_signals"])
        )
        runtime_state = self._read_json(os.path.join(run_dir, "runtime_graph_state.json"))
        assumption_payload = self._read_json(os.path.join(run_dir, "assumption_ledger.json"))
        metrics_payload = self._read_json(os.path.join(run_dir, "metrics.json"))

        question_type = (
            snapshot.get("question_type")
            or manifest.get("question_type")
            or beliefs.get("question_type")
        )
        support_status = (
            snapshot.get("support_status")
            or snapshot.get("extraction_status")
            or manifest.get("extraction_status")
            or "partial"
        )
        forecast_id = manifest.get("forecast_id") or snapshot.get("forecast_id")
        participating_agent_count = int(
            snapshot.get("participating_agent_count")
            or disagreement.get("participant_count")
            or 0
        )
        judgment_count = int(
            disagreement.get("judgment_count")
            or len(updates.get("updates") or [])
            or len(beliefs.get("beliefs") or [])
        )
        synthetic_consensus_probability = snapshot.get("synthetic_consensus_probability")
        if synthetic_consensus_probability is None:
            synthetic_consensus_probability = disagreement.get("consensus_probability")
        synthetic_consensus_probability = (
            round(_clamp(float(synthetic_consensus_probability)), 6)
            if synthetic_consensus_probability is not None
            else None
        )
        disagreement_index = disagreement.get("disagreement_index")
        disagreement_index = (
            round(_clamp(float(disagreement_index)), 6)
            if disagreement_index is not None
            else None
        )

        scenario_split_distribution = self._build_scenario_split_distribution(
            question_type=question_type,
            synthetic_consensus_probability=synthetic_consensus_probability,
            snapshot=snapshot,
            disagreement=disagreement,
        )
        argument_cluster_distribution = self._build_argument_cluster_distribution(argument_map)
        belief_momentum = self._build_belief_momentum(updates)
        belief_trajectory = self._build_belief_trajectory_signal(updates)
        missing_information_signal = self._build_missing_information_signal(missing_information)
        minority_warning_signal = self._build_minority_warning_signal(
            question_type=question_type,
            scenario_split_distribution=scenario_split_distribution,
            disagreement_index=disagreement_index,
        )
        regime_context = self._build_regime_context_signal(
            runtime_state=runtime_state,
            metrics_payload=metrics_payload,
            assumption_payload=assumption_payload,
        )
        assumption_alignment = self._build_assumption_alignment_signal(
            runtime_state=runtime_state,
            assumption_payload=assumption_payload,
            metrics_payload=metrics_payload,
        )

        signal_provenance = self._build_signal_provenance(
            beliefs=beliefs,
            updates=updates,
            missing_information=missing_information,
            scenario_split_distribution=scenario_split_distribution,
        )
        signals = {
            "synthetic_consensus_probability": {
                "status": "ready" if synthetic_consensus_probability is not None else "invalid",
                "value": synthetic_consensus_probability,
            },
            "disagreement_index": {
                "status": "ready" if disagreement_index is not None else "invalid",
                "value": disagreement_index,
            },
            "argument_cluster_distribution": {
                "status": "ready" if argument_cluster_distribution else "partial",
                "value": dict(argument_cluster_distribution),
            },
            "belief_momentum": {
                "status": "ready" if belief_momentum.get("update_count", 0) else "partial",
                "value": dict(belief_momentum),
            },
            "belief_trajectory": {
                "status": "ready" if belief_trajectory.get("update_count", 0) else "partial",
                "value": dict(belief_trajectory),
            },
            "minority_warning_signal": {
                "status": "ready" if minority_warning_signal else "partial",
                "value": dict(minority_warning_signal),
            },
            "missing_information_signal": {
                "status": "ready" if missing_information_signal.get("request_count", 0) else "partial",
                "value": dict(missing_information_signal),
            },
            "scenario_split_distribution": {
                "status": "ready" if scenario_split_distribution else "invalid",
                "value": dict(scenario_split_distribution),
            },
            "regime_context": {
                "status": "ready" if regime_context else "partial",
                "value": dict(regime_context),
            },
            "assumption_alignment": {
                "status": "ready" if assumption_alignment.get("coverage_ratio") is not None else "partial",
                "value": dict(assumption_alignment),
            },
        }

        summary = SimulationMarketSummary(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            forecast_id=forecast_id,
            question_type=question_type,
            support_status=support_status,
            provenance_status="partial",
            participant_count=participating_agent_count,
            judgment_count=judgment_count,
            evidence_bundle_ids=evidence_bundle_ids or [],
            synthetic_consensus_probability=synthetic_consensus_probability,
            disagreement_index=disagreement_index,
            argument_cluster_distribution=argument_cluster_distribution,
            belief_momentum=belief_momentum,
            minority_warning_signal=minority_warning_signal,
            missing_information_signal=missing_information_signal,
            scenario_split_distribution=scenario_split_distribution,
            signals=signals,
            signal_provenance=signal_provenance,
            warnings=list(manifest.get("warnings") or []),
            downgrade_reasons=[],
            boundary_notes=list(snapshot.get("boundary_notes") or manifest.get("boundary_notes") or []),
        )
        return summary.to_dict()

    def _build_scenario_split_distribution(
        self,
        *,
        question_type: Optional[str],
        synthetic_consensus_probability: Optional[float],
        snapshot: Dict[str, Any],
        disagreement: Dict[str, Any],
    ) -> Dict[str, float]:
        if question_type == "binary" and synthetic_consensus_probability is not None:
            yes_share = round(_clamp(float(synthetic_consensus_probability)), 6)
            return {"yes": yes_share, "no": round(1.0 - yes_share, 6)}
        distribution = snapshot.get("categorical_distribution")
        if not isinstance(distribution, dict) or not distribution:
            distribution = disagreement.get("distribution", {})
        return _normalize_distribution(distribution)

    def _build_argument_cluster_distribution(self, argument_map: Dict[str, Any]) -> Dict[str, float]:
        tag_counts = {
            str(item.get("tag") or "").strip(): float(item.get("count") or 0)
            for item in argument_map.get("tags") or []
            if str(item.get("tag") or "").strip()
        }
        return _normalize_distribution(tag_counts)

    def _build_belief_momentum(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        updates_payload = list(updates.get("updates") or [])
        deltas: list[float] = []
        changed_agent_ids: set[int] = set()
        changed_update_count = 0
        for item in updates_payload:
            probability = item.get("probability")
            previous_probability = item.get("previous_probability")
            if probability is None or previous_probability is None:
                continue
            try:
                delta = abs(float(probability) - float(previous_probability))
            except (TypeError, ValueError):
                continue
            deltas.append(delta)
            if item.get("belief_changed"):
                changed_update_count += 1
                try:
                    changed_agent_ids.add(int(item.get("agent_id")))
                except (TypeError, ValueError):
                    pass
        update_count = len(updates_payload)
        return {
            "update_count": update_count,
            "changed_update_count": changed_update_count,
            "changed_update_share": round(changed_update_count / update_count, 6) if update_count else 0.0,
            "changed_agent_count": len(changed_agent_ids),
            "mean_absolute_probability_delta": round(_mean(deltas) or 0.0, 6),
        }

    def _build_belief_trajectory_signal(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        updates_payload = list(updates.get("updates") or [])
        probabilities: list[float] = []
        for item in updates_payload:
            probability = item.get("probability")
            try:
                probabilities.append(float(probability))
            except (TypeError, ValueError):
                continue
        if not probabilities:
            return {
                "update_count": len(updates_payload),
                "opening_probability": None,
                "closing_probability": None,
                "max_swing": 0.0,
                "trend": "unknown",
            }
        opening_probability = round(probabilities[0], 6)
        closing_probability = round(probabilities[-1], 6)
        delta = closing_probability - opening_probability
        if delta <= -0.05:
            trend = "downward"
        elif delta >= 0.05:
            trend = "upward"
        else:
            trend = "flat"
        return {
            "update_count": len(updates_payload),
            "opening_probability": opening_probability,
            "closing_probability": closing_probability,
            "max_swing": round(max(probabilities) - min(probabilities), 6),
            "trend": trend,
        }

    def _build_missing_information_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        requests = [item.get("request") for item in payload.get("signals") or []]
        normalized_requests = _dedupe_requests(requests)
        request_counts: Dict[str, int] = {}
        for request in requests:
            normalized = str(request or "").strip()
            if not normalized:
                continue
            request_counts[normalized] = request_counts.get(normalized, 0) + 1
        top_requests = [
            {"request": request, "count": count}
            for request, count in sorted(request_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        return {
            "request_count": len([item for item in requests if str(item or "").strip()]),
            "unique_request_count": len(normalized_requests),
            "top_requests": top_requests,
            "requests": normalized_requests,
        }

    def _build_minority_warning_signal(
        self,
        *,
        question_type: Optional[str],
        scenario_split_distribution: Dict[str, float],
        disagreement_index: Optional[float],
    ) -> Dict[str, Any]:
        if not scenario_split_distribution:
            return {}
        ordered = sorted(
            scenario_split_distribution.items(),
            key=lambda item: (-float(item[1]), item[0]),
        )
        majority_outcome, majority_share = ordered[0]
        minority_outcome, minority_share = (
            ordered[1] if len(ordered) > 1 else (majority_outcome, 0.0)
        )
        support_gap = round(float(majority_share) - float(minority_share), 6)
        present = bool(
            len(ordered) > 1
            and (
                float(minority_share) >= 0.25
                or float(disagreement_index or 0.0) >= 0.25
            )
        )
        return {
            "present": present,
            "majority_outcome": majority_outcome,
            "minority_outcome": minority_outcome,
            "majority_share": round(float(majority_share), 6),
            "minority_share": round(float(minority_share), 6),
            "support_gap": support_gap,
            "question_type": question_type,
        }

    def _build_regime_context_signal(
        self,
        *,
        runtime_state: Dict[str, Any],
        metrics_payload: Dict[str, Any],
        assumption_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        assumption_ledger = assumption_payload.get("assumption_ledger", {})
        if not isinstance(assumption_ledger, dict):
            assumption_ledger = {}
        regime_summary = metrics_payload.get("regime_summary", {})
        if not isinstance(regime_summary, dict):
            regime_summary = {}
        active_topics = [
            str(topic).strip()
            for topic in runtime_state.get("active_topics", [])
            if str(topic or "").strip()
        ]
        policy_regime = regime_summary.get("policy_regime")
        if not policy_regime:
            for item in assumption_ledger.get("structural_uncertainties", []):
                if str(item.get("kind") or "").strip() == "moderation_policy_change":
                    policy_regime = str(item.get("option_id") or item.get("option_label") or "").strip()
                    break
        narrative_family = regime_summary.get("narrative_family")
        if not narrative_family and active_topics:
            narrative_family = "+".join(active_topics[:2])
        return {
            "policy_regime": policy_regime,
            "narrative_family": narrative_family,
            "primary_regime": regime_summary.get("primary_regime"),
            "active_topics": active_topics,
        }

    def _build_assumption_alignment_signal(
        self,
        *,
        runtime_state: Dict[str, Any],
        assumption_payload: Dict[str, Any],
        metrics_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        alignment = metrics_payload.get("assumption_alignment", {})
        if isinstance(alignment, dict) and alignment:
            return dict(alignment)
        assumption_ledger = assumption_payload.get("assumption_ledger", {})
        if not isinstance(assumption_ledger, dict):
            assumption_ledger = {}
        planned_transition_types = sorted(
            {
                str(item).strip()
                for item in assumption_ledger.get("structural_runtime_transition_types", [])
                if str(item or "").strip()
            }
        )
        observed_transition_types = sorted(
            {
                str(transition_type).strip()
                for transition_type, count in (runtime_state.get("transition_counts") or {}).items()
                if str(transition_type or "").strip()
                and str(transition_type or "").strip() != "round_state"
                and int(count or 0) > 0
            }
        )
        matched = sorted(set(planned_transition_types) & set(observed_transition_types))
        coverage_ratio = None
        if planned_transition_types:
            coverage_ratio = round(len(matched) / len(planned_transition_types), 6)
        return {
            "planned_transition_types": planned_transition_types,
            "observed_transition_types": observed_transition_types,
            "matched_transition_types": matched,
            "missing_transition_types": sorted(
                set(planned_transition_types) - set(observed_transition_types)
            ),
            "coverage_ratio": coverage_ratio,
        }

    def _build_signal_provenance(
        self,
        *,
        beliefs: Dict[str, Any],
        updates: Dict[str, Any],
        missing_information: Dict[str, Any],
        scenario_split_distribution: Dict[str, float],
    ) -> Dict[str, list[Dict[str, Any]]]:
        belief_payload = list(beliefs.get("beliefs") or [])
        update_payload = list(updates.get("updates") or [])
        missing_payload = list(missing_information.get("signals") or [])

        all_belief_refs = self._collect_reference_dicts(
            item.get("reference") for item in belief_payload
        )
        changed_update_refs = self._collect_reference_dicts(
            item.get("reference") for item in update_payload if item.get("belief_changed")
        )
        rationale_refs = self._collect_reference_dicts(
            item.get("reference")
            for item in belief_payload
            if item.get("rationale_tags")
        )
        missing_refs = self._collect_reference_dicts(
            item.get("reference") for item in missing_payload
        )
        minority_refs = []
        if scenario_split_distribution:
            minority_label = _top_distribution_label(
                {
                    label: 1.0 - share if len(scenario_split_distribution) == 1 else share
                    for label, share in scenario_split_distribution.items()
                }
            )
            if minority_label is not None:
                minority_refs = self._collect_reference_dicts(
                    item.get("reference")
                    for item in belief_payload
                    if self._belief_supports_label(item, minority_label)
                )
        return {
            "synthetic_consensus_probability": all_belief_refs,
            "disagreement_index": all_belief_refs,
            "argument_cluster_distribution": rationale_refs or all_belief_refs,
            "belief_momentum": changed_update_refs,
            "belief_trajectory": all_belief_refs,
            "minority_warning_signal": minority_refs or all_belief_refs,
            "missing_information_signal": missing_refs,
            "scenario_split_distribution": all_belief_refs,
            "regime_context": all_belief_refs,
            "assumption_alignment": all_belief_refs,
        }

    def _belief_supports_label(self, belief: Dict[str, Any], label: str) -> bool:
        normalized_label = str(label or "").strip().lower()
        dominant_outcome = str(belief.get("dominant_outcome") or "").strip().lower()
        if dominant_outcome:
            return dominant_outcome == normalized_label
        distribution = belief.get("outcome_distribution")
        if isinstance(distribution, dict):
            top_label = _top_distribution_label(_normalize_distribution(distribution))
            return str(top_label or "").strip().lower() == normalized_label
        probability = belief.get("probability")
        if probability is not None:
            try:
                probability_value = float(probability)
            except (TypeError, ValueError):
                return False
            if normalized_label in {"yes", "true", "positive"}:
                return probability_value >= 0.5
            if normalized_label in {"no", "false", "negative"}:
                return probability_value < 0.5
        return False

    def _collect_reference_dicts(self, references: Iterable[Any]) -> list[Dict[str, Any]]:
        deduped: Dict[tuple[Any, ...], Dict[str, Any]] = {}
        for item in references:
            if item is None:
                continue
            if isinstance(item, SimulationMarketReference):
                reference_dict = item.to_dict()
            elif isinstance(item, dict):
                reference_dict = SimulationMarketReference.from_dict(item).to_dict()
            else:
                continue
            deduped[_reference_signature(reference_dict)] = reference_dict
        return list(deduped.values())

    @staticmethod
    def _read_json(path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
