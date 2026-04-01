"""
Hybrid forecast worker execution and conservative answer aggregation.

This engine keeps simulation as one scenario worker while preventing it from
becoming the default answer source for the hybrid forecast path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import math
import os
import re
from typing import Any, Iterable, Optional

from ..config import Config
from ..models.forecasting import (
    ForecastAnswer,
    ForecastWorker,
    ForecastWorkspaceRecord,
    PredictionLedgerEntry,
    ResolutionCriteria,
)
from .ensemble_manager import EnsembleManager
from .forecast_signal_provenance import ForecastSignalProvenanceValidator
from .scenario_clusterer import ScenarioClusterer
from .sensitivity_analyzer import SensitivityAnalyzer
from .simulation_market_aggregator import SimulationMarketAggregator


def _iso_datetime(value: Optional[str]) -> str:
    if value is None:
        return datetime.now().isoformat()
    return datetime.fromisoformat(str(value)).isoformat()


def _compact_timestamp(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _mean(values: Iterable[float]) -> Optional[float]:
    normalized = [float(value) for value in values]
    if not normalized:
        return None
    return sum(normalized) / len(normalized)


def _weighted_mean(values: list[tuple[float, float]]) -> Optional[float]:
    usable = [(float(value), max(float(weight), 0.0)) for value, weight in values if weight is not None]
    total_weight = sum(weight for _, weight in usable)
    if not usable or total_weight <= 0:
        return None
    return sum(value * weight for value, weight in usable) / total_weight


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _tokenize(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def _family_for_worker(worker: ForecastWorker) -> str:
    family = str(worker.metadata.get("worker_family") or "").strip()
    if family in {"base_rate", "reference_class", "retrieval_synthesis", "simulation", "simulation_market"}:
        return family
    if worker.kind in {"base_rate", "reference_class", "retrieval_synthesis", "simulation", "simulation_market"}:
        return worker.kind
    if worker.kind == "retrieval":
        return "retrieval_synthesis"
    if worker.kind == "analytical":
        label = str(worker.label or "").lower()
        if "reference" in label or "case" in label:
            return "reference_class"
        return "base_rate"
    return worker.kind


def _first_metric_threshold(criteria: list[ResolutionCriteria]) -> tuple[Optional[str], Optional[str], Optional[float]]:
    for item in criteria:
        if item.criteria_type != "metric_threshold":
            continue
        metric_id = item.thresholds.get("metric_id")
        operator = item.thresholds.get("operator", "gt")
        value = item.thresholds.get("value")
        try:
            return (
                str(metric_id) if metric_id is not None else None,
                str(operator) if operator is not None else None,
                float(value) if value is not None else None,
            )
        except (TypeError, ValueError):
            return (str(metric_id) if metric_id is not None else None, str(operator), None)
    return (None, None, None)


def _compare_threshold(value: float, operator: Optional[str], threshold: Optional[float]) -> Optional[float]:
    if threshold is None:
        return None
    op = str(operator or "gt").lower()
    if op == "gt":
        return 1.0 if value > threshold else 0.0
    if op == "gte":
        return 1.0 if value >= threshold else 0.0
    if op == "lt":
        return 1.0 if value < threshold else 0.0
    if op == "lte":
        return 1.0 if value <= threshold else 0.0
    if op == "eq":
        return 1.0 if value == threshold else 0.0
    return None


def _resolved_binary_value_from_workspace(
    workspace: ForecastWorkspaceRecord,
    metric_id: Optional[str],
    operator: Optional[str],
    threshold: Optional[float],
) -> Optional[float]:
    status = workspace.prediction_ledger.final_resolution_state
    if status == "resolved_true":
        return 1.0
    if status == "resolved_false":
        return 0.0
    for case in workspace.evaluation_cases:
        if case.status != "resolved":
            continue
        outcome = case.observed_outcome
        if isinstance(outcome, dict):
            if metric_id and metric_id in outcome:
                try:
                    return _compare_threshold(float(outcome[metric_id]), operator, threshold)
                except (TypeError, ValueError):
                    continue
            state = outcome.get("resolved_state")
            if state == "resolved_true":
                return 1.0
            if state == "resolved_false":
                return 0.0
        elif isinstance(outcome, bool):
            return 1.0 if outcome else 0.0
    return None


def _evaluation_case_values(
    workspace: ForecastWorkspaceRecord,
    metric_id: Optional[str],
    operator: Optional[str],
    threshold: Optional[float],
) -> list[float]:
    values: list[float] = []
    for case in workspace.evaluation_cases:
        if case.status != "resolved":
            continue
        outcome = case.observed_outcome
        if isinstance(outcome, dict):
            if metric_id and metric_id in outcome:
                try:
                    threshold_value = _compare_threshold(
                        float(outcome[metric_id]),
                        operator,
                        threshold,
                    )
                except (TypeError, ValueError):
                    threshold_value = None
                if threshold_value is not None:
                    values.append(threshold_value)
                    continue
            if "resolved_state" in outcome:
                if outcome["resolved_state"] == "resolved_true":
                    values.append(1.0)
                    continue
                if outcome["resolved_state"] == "resolved_false":
                    values.append(0.0)
                    continue
            numeric_values = [
                float(value)
                for value in outcome.values()
                if isinstance(value, (int, float))
            ]
            if len(numeric_values) == 1 and threshold is not None:
                threshold_value = _compare_threshold(numeric_values[0], operator, threshold)
                if threshold_value is not None:
                    values.append(threshold_value)
        elif isinstance(outcome, bool):
            values.append(1.0 if outcome else 0.0)
    return values


def _workspace_question_type(workspace: ForecastWorkspaceRecord) -> str:
    return str(workspace.forecast_question.question_type or "binary").strip() or "binary"


def _workspace_question_spec(workspace: ForecastWorkspaceRecord) -> dict[str, Any]:
    return dict(workspace.forecast_question.question_spec or {})


def _workspace_interval_levels(workspace: ForecastWorkspaceRecord) -> list[int]:
    levels = _workspace_question_spec(workspace).get("interval_levels") or [50, 80, 90]
    normalized: list[int] = []
    seen: set[int] = set()
    for item in levels:
        try:
            level = int(item)
        except (TypeError, ValueError):
            continue
        if 0 < level < 100 and level not in seen:
            normalized.append(level)
            seen.add(level)
    return sorted(normalized) or [50, 80, 90]


def _workspace_outcome_labels(workspace: ForecastWorkspaceRecord) -> list[str]:
    labels = _workspace_question_spec(workspace).get("outcome_labels") or []
    normalized = _dedupe_strings(labels)
    if normalized:
        return normalized
    decomposition = workspace.forecast_question.decomposition_support or []
    return _dedupe_strings(
        item.get("label") or item.get("question_text")
        for item in decomposition
        if isinstance(item, dict)
    )


def _workspace_numeric_unit(workspace: ForecastWorkspaceRecord) -> Optional[str]:
    unit = _workspace_question_spec(workspace).get("unit")
    if unit is None:
        return None
    normalized = str(unit).strip()
    return normalized or None


def _normalize_distribution(
    weights: dict[str, Any],
    *,
    labels: Optional[list[str]] = None,
) -> dict[str, float]:
    prepared: dict[str, float] = {}
    for label, value in (weights or {}).items():
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight < 0:
            continue
        normalized_label = str(label or "").strip()
        if not normalized_label:
            continue
        prepared[normalized_label] = prepared.get(normalized_label, 0.0) + weight
    if labels:
        for label in labels:
            prepared.setdefault(label, 0.0)
    total = sum(prepared.values())
    if total <= 0:
        return {label: 0.0 for label in labels or []}
    return {
        label: round(weight / total, 6)
        for label, weight in sorted(prepared.items(), key=lambda item: item[0])
    }


def _top_distribution_label(distribution: dict[str, float]) -> Optional[str]:
    if not distribution:
        return None
    return max(
        distribution.items(),
        key=lambda item: (float(item[1]), item[0]),
    )[0]


def _distribution_entropy(distribution: dict[str, float]) -> float:
    entropy = 0.0
    for weight in distribution.values():
        if weight <= 0:
            continue
        entropy -= float(weight) * math.log(float(weight), 2)
    return round(entropy, 6)


def _quantile(values: list[float], probability: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, probability)) * (len(ordered) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return ordered[lower_index]
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    blend = position - lower_index
    return lower_value + ((upper_value - lower_value) * blend)


def _build_numeric_interval_payload(
    values: list[float],
    *,
    unit: Optional[str],
    interval_levels: list[int],
) -> dict[str, Any]:
    if not values:
        return {}
    point_estimate = _mean(values)
    intervals: dict[str, dict[str, float]] = {}
    for level in interval_levels:
        tail = (1.0 - (level / 100.0)) / 2.0
        lower = _quantile(values, tail)
        upper = _quantile(values, 1.0 - tail)
        if lower is None or upper is None:
            continue
        intervals[str(level)] = {
            "low": round(float(lower), 6),
            "high": round(float(upper), 6),
        }
    payload = {
        "point_estimate": round(float(point_estimate), 6) if point_estimate is not None else None,
        "value": round(float(point_estimate), 6) if point_estimate is not None else None,
        "intervals": intervals,
        "samples": len(values),
    }
    if unit:
        payload["unit"] = unit
    return payload


def _extract_categorical_outcome(case: Any, outcome_labels: Optional[list[str]] = None) -> Optional[str]:
    candidates: list[Any] = []
    if getattr(case, "observed_outcome", None) is not None:
        candidates.append(case.observed_outcome)
    if getattr(case, "observed_value", None) is not None:
        candidates.append(case.observed_value)
    normalized_labels = {
        str(label).strip(): str(label).strip() for label in (outcome_labels or []) if str(label).strip()
    }
    lowered_lookup = {label.lower(): label for label in normalized_labels}
    for candidate in candidates:
        if isinstance(candidate, str):
            label = candidate.strip()
            if not label:
                continue
            if not normalized_labels:
                return label
            return normalized_labels.get(label) or lowered_lookup.get(label.lower())
        if isinstance(candidate, dict):
            for key in ("label", "outcome", "category", "observed_label", "value"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    label = value.strip()
                    if not normalized_labels:
                        return label
                    return normalized_labels.get(label) or lowered_lookup.get(label.lower())
    return None


def _extract_numeric_outcome(
    case: Any,
    *,
    metric_id: Optional[str] = None,
) -> Optional[float]:
    candidates: list[Any] = []
    if getattr(case, "observed_outcome", None) is not None:
        candidates.append(case.observed_outcome)
    if getattr(case, "observed_value", None) is not None:
        candidates.append(case.observed_value)
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            return float(candidate)
        if isinstance(candidate, dict):
            if metric_id and candidate.get(metric_id) is not None:
                try:
                    return float(candidate[metric_id])
                except (TypeError, ValueError):
                    pass
            for key in ("value", "point_estimate", "observed_value"):
                value = candidate.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
            numeric_values = [
                float(value)
                for value in candidate.values()
                if isinstance(value, (int, float))
            ]
            if len(numeric_values) == 1:
                return numeric_values[0]
    return None


def _case_prediction_distribution(
    case: Any,
    *,
    outcome_labels: Optional[list[str]] = None,
) -> dict[str, float]:
    payload = dict(getattr(case, "prediction_payload", {}) or {})
    distribution = payload.get("distribution")
    if isinstance(distribution, dict):
        return _normalize_distribution(distribution, labels=outcome_labels)
    top_label = payload.get("top_label")
    if isinstance(top_label, str) and top_label.strip():
        return _normalize_distribution({top_label.strip(): 1.0}, labels=outcome_labels)
    return {}


def _case_prediction_numeric_payload(case: Any) -> dict[str, Any]:
    payload = dict(getattr(case, "prediction_payload", {}) or {})
    if not payload:
        return {}
    normalized: dict[str, Any] = {}
    point_estimate = payload.get("point_estimate", payload.get("value"))
    if point_estimate is not None:
        try:
            normalized["point_estimate"] = float(point_estimate)
        except (TypeError, ValueError):
            pass
    intervals = payload.get("intervals")
    if isinstance(intervals, dict):
        normalized_intervals: dict[str, dict[str, float]] = {}
        for level, bounds in intervals.items():
            if not isinstance(bounds, dict):
                continue
            try:
                lower = float(bounds.get("low"))
                upper = float(bounds.get("high"))
            except (TypeError, ValueError):
                continue
            if lower > upper:
                continue
            normalized_intervals[str(level)] = {
                "low": lower,
                "high": upper,
            }
        if normalized_intervals:
            normalized["intervals"] = normalized_intervals
    unit = payload.get("unit")
    if unit is not None and str(unit).strip():
        normalized["unit"] = str(unit).strip()
    return normalized


def _case_prediction_probability(case: Any) -> Optional[float]:
    forecast_probability = getattr(case, "forecast_probability", None)
    if isinstance(forecast_probability, (int, float)):
        return _clamp(float(forecast_probability))
    payload = dict(getattr(case, "prediction_payload", {}) or {})
    for key in ("forecast_probability", "probability", "estimate", "value"):
        candidate = payload.get(key)
        if isinstance(candidate, (int, float)):
            return _clamp(float(candidate))
    distribution = payload.get("distribution")
    if isinstance(distribution, dict):
        lowered_lookup = {
            str(label).strip().lower(): value
            for label, value in distribution.items()
            if str(label).strip()
        }
        for key in ("yes", "true", "resolved_true", "positive"):
            candidate = lowered_lookup.get(key)
            if isinstance(candidate, (int, float)):
                return _clamp(float(candidate))
    return None


def _extract_binary_outcome(
    case: Any,
    *,
    metric_id: Optional[str],
    operator: Optional[str],
    threshold: Optional[float],
) -> Optional[float]:
    for candidate in (
        getattr(case, "observed_outcome", None),
        getattr(case, "observed_value", None),
    ):
        if isinstance(candidate, bool):
            return 1.0 if candidate else 0.0
        if isinstance(candidate, dict):
            if metric_id and metric_id in candidate:
                try:
                    return _compare_threshold(
                        float(candidate[metric_id]),
                        operator,
                        threshold,
                    )
                except (TypeError, ValueError):
                    pass
            state = candidate.get("resolved_state")
            if state == "resolved_true":
                return 1.0
            if state == "resolved_false":
                return 0.0
            numeric_values = [
                float(value)
                for value in candidate.values()
                if isinstance(value, (int, float))
            ]
            if len(numeric_values) == 1 and threshold is not None:
                return _compare_threshold(numeric_values[0], operator, threshold)
    return None


def _determine_confidence_label(*, ready: bool, case_count: int) -> str:
    if not ready:
        return "insufficient"
    if case_count >= 25:
        return "moderate"
    return "limited"


def _categorical_log_loss(distribution: dict[str, float], observed_label: str) -> Optional[float]:
    if not distribution or not observed_label:
        return None
    probability = float(distribution.get(observed_label, 0.0))
    probability = min(max(probability, Config.CALIBRATION_LOG_SCORE_EPSILON), 1.0)
    return -math.log(probability)


def _categorical_brier_score(distribution: dict[str, float], observed_label: str) -> Optional[float]:
    if not distribution or not observed_label:
        return None
    score = 0.0
    for label, probability in distribution.items():
        observed = 1.0 if label == observed_label else 0.0
        score += (float(probability) - observed) ** 2
    return score


def _numeric_interval_contains(bounds: dict[str, float], observed_value: float) -> bool:
    return float(bounds["low"]) <= float(observed_value) <= float(bounds["high"])


@dataclass
class HybridWorkerResult:
    output_id: str
    forecast_id: str
    worker_id: str
    worker_kind: str
    recorded_at: str
    status: str
    summary: str
    contribution_role: str
    influences_best_estimate: bool
    value_type: str
    value_semantics: str
    estimate: Optional[float] = None
    value: Any = None
    effective_weight: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    confidence_inputs: dict[str, Any] = field(default_factory=dict)
    failure_modes: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    abstain_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def to_trace_item(self) -> dict[str, Any]:
        estimate_payload = None
        if isinstance(self.value, dict):
            estimate_payload = {
                **self.value,
                "value_type": self.value_type,
                "value_semantics": self.value_semantics,
                "semantics": self.value_semantics,
            }
        elif self.value is not None:
            estimate_payload = {
                "value": self.value,
                "value_type": self.value_type,
                "value_semantics": self.value_semantics,
                "semantics": self.value_semantics,
            }
            if self.estimate is not None:
                estimate_payload["estimate"] = round(float(self.estimate), 6)
        elif self.estimate is not None:
            estimate_payload = {
                "estimate": round(float(self.estimate), 6),
                "value": round(float(self.estimate), 6),
                "value_type": self.value_type,
                "value_semantics": self.value_semantics,
                "semantics": self.value_semantics,
            }
        return {
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind,
            "status": self.status,
            "summary": self.summary,
            "contribution_role": self.contribution_role,
            "influences_best_estimate": self.influences_best_estimate,
            "used_in_best_estimate": self.influences_best_estimate,
            "effective_weight": round(float(self.effective_weight), 6),
            "estimate": estimate_payload,
            "value_semantics": self.value_semantics,
            "value_type": self.value_type,
            "abstain_reason": self.abstain_reason,
            "assumptions": list(self.assumptions),
            "counterevidence": list(self.counterevidence),
            "confidence_inputs": dict(self.confidence_inputs),
            "failure_modes": list(self.failure_modes),
            "citations": [dict(item) for item in self.citations],
            "notes": list(self.notes),
        }

    def to_worker_output(self) -> dict[str, Any]:
        trace_item = self.to_trace_item()
        trace_item.update(
            {
                "output_id": self.output_id,
                "forecast_id": self.forecast_id,
                "recorded_at": self.recorded_at,
            }
        )
        return trace_item


@dataclass
class HybridForecastExecutionResult:
    forecast_answer: ForecastAnswer
    prediction_entries: list[PredictionLedgerEntry]
    worker_results: list[HybridWorkerResult]

    @property
    def worker_outputs(self) -> list[dict[str, Any]]:
        return [item.to_worker_output() for item in self.worker_results]


class HybridForecastEngine:
    """Execute additive hybrid workers and assemble one bounded forecast answer."""

    def __init__(self, *, simulation_data_dir: Optional[str] = None):
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        self.ensemble_manager = EnsembleManager(
            simulation_data_dir=self.simulation_data_dir
        )
        self.scenario_clusterer = ScenarioClusterer(
            simulation_data_dir=self.simulation_data_dir
        )
        self.sensitivity_analyzer = SensitivityAnalyzer(
            simulation_data_dir=self.simulation_data_dir
        )
        self.simulation_market_aggregator = SimulationMarketAggregator(
            simulation_data_dir=self.simulation_data_dir
        )
        self.signal_provenance_validator = ForecastSignalProvenanceValidator(
            simulation_data_dir=self.simulation_data_dir
        )

    @staticmethod
    def _derive_confidence_semantics(answer_payload: dict[str, Any]) -> str:
        if answer_payload.get("abstain"):
            return "not_applicable"
        confidence_basis = dict(answer_payload.get("confidence_basis") or {})
        calibration_summary = dict(answer_payload.get("calibration_summary") or {})
        benchmark_summary = dict(answer_payload.get("benchmark_summary") or {})
        backtest_summary = dict(answer_payload.get("backtest_summary") or {})
        resolved_case_count = int(
            confidence_basis.get("resolved_case_count")
            or answer_payload.get("evaluation_summary", {}).get("resolved_case_count")
            or 0
        )
        if (
            confidence_basis.get("status") == "available"
            and calibration_summary.get("status") == "ready"
            and benchmark_summary.get("status") == "available"
            and backtest_summary.get("status") in {"available", "ready"}
            and resolved_case_count > 0
        ):
            return "calibrated"
        return "uncalibrated"

    def execute(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        recorded_at: Optional[str] = None,
        comparable_workspaces: Optional[list[ForecastWorkspaceRecord]] = None,
    ) -> HybridForecastExecutionResult:
        recorded_at = _iso_datetime(recorded_at)
        comparable_workspaces = comparable_workspaces or []
        worker_results: list[HybridWorkerResult] = []
        worker_map = {
            _family_for_worker(worker): worker
            for worker in workspace.forecast_workers
        }
        metric_id, operator, threshold = _first_metric_threshold(workspace.resolution_criteria)

        ordered_families = [
            "base_rate",
            "reference_class",
            "retrieval_synthesis",
            "simulation_market",
            "simulation",
        ]
        for family in ordered_families:
            worker = worker_map.get(family)
            if worker is None:
                continue
            if family == "base_rate":
                worker_results.append(
                    self._run_base_rate_worker(
                        workspace,
                        worker,
                        comparable_workspaces,
                        recorded_at,
                        metric_id,
                        operator,
                        threshold,
                    )
                )
            elif family == "reference_class":
                worker_results.append(
                    self._run_reference_class_worker(
                        workspace,
                        worker,
                        comparable_workspaces,
                        recorded_at,
                        metric_id,
                        operator,
                        threshold,
                    )
                )
            elif family == "retrieval_synthesis":
                worker_results.append(
                    self._run_retrieval_worker(
                        workspace,
                        worker,
                        recorded_at,
                    )
                )
            elif family == "simulation":
                worker_results.append(
                    self._run_simulation_worker(
                        workspace,
                        worker,
                        recorded_at,
                        metric_id,
                        operator,
                        threshold,
                    )
                )
            elif family == "simulation_market":
                worker_results.append(
                    self._run_simulation_market_worker(
                        workspace,
                        worker,
                        recorded_at,
                    )
                )

        analytics_context = self._load_analytics_context(workspace)
        ensemble_policy = self._apply_ensemble_policy(
            workspace=workspace,
            worker_results=worker_results,
            analytics_context=analytics_context,
        )
        answer_payload = self._build_answer_payload(
            workspace,
            worker_results,
            comparable_workspaces=comparable_workspaces,
            analytics_context=analytics_context,
            ensemble_policy=ensemble_policy,
        )
        prediction_entries = self._build_prediction_entries(
            workspace,
            worker_results,
            recorded_at,
            answer_payload=answer_payload,
        )
        answer = ForecastAnswer(
            answer_id=f"answer-hybrid-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            answer_type="hybrid_forecast",
            summary=self._build_answer_summary(answer_payload),
            worker_ids=[result.worker_id for result in worker_results],
            prediction_entry_ids=[entry.entry_id for entry in prediction_entries],
            confidence_semantics=self._derive_confidence_semantics(answer_payload),
            created_at=recorded_at,
            answer_payload=answer_payload,
            evaluation_summary=answer_payload["evaluation_summary"],
            benchmark_summary=answer_payload["benchmark_summary"],
            backtest_summary=answer_payload["backtest_summary"],
            calibration_summary=answer_payload["calibration_summary"],
            confidence_basis=answer_payload["confidence_basis"],
            notes=self._build_answer_notes(answer_payload),
        )
        return HybridForecastExecutionResult(
            forecast_answer=answer,
            prediction_entries=prediction_entries,
            worker_results=worker_results,
        )

    def _load_analytics_context(
        self,
        workspace: ForecastWorkspaceRecord,
    ) -> dict[str, Any]:
        scope = workspace.simulation_scope
        if (
            scope is None
            or not scope.simulation_id
            or not scope.latest_ensemble_id
        ):
            return {}

        simulation_id = str(scope.simulation_id).strip()
        ensemble_id = str(scope.latest_ensemble_id).strip()
        run_id = str(scope.latest_run_id).strip() if scope.latest_run_id else None
        context: dict[str, Any] = {
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
        }

        try:
            aggregate_summary = self.ensemble_manager.get_aggregate_summary(
                simulation_id,
                ensemble_id,
            )
        except Exception:
            aggregate_summary = None
        if isinstance(aggregate_summary, dict):
            context["aggregate_summary"] = {
                "quality_status": aggregate_summary.get("quality_summary", {}).get("status"),
                "belief_summary": aggregate_summary.get("belief_summary"),
                "trajectory_summary": aggregate_summary.get("trajectory_summary"),
                "regime_summary": aggregate_summary.get("regime_summary"),
                "assumption_alignment": aggregate_summary.get("assumption_alignment"),
            }

        try:
            scenario_clusters = self.scenario_clusterer.get_scenario_clusters(
                simulation_id,
                ensemble_id,
            )
        except Exception:
            scenario_clusters = None
        if isinstance(scenario_clusters, dict):
            coverage_metrics = (
                scenario_clusters.get("diversity_diagnostics", {})
                .get("coverage_metrics", {})
            )
            context["scenario_clusters"] = {
                "cluster_count": scenario_clusters.get("cluster_count"),
                "structural_uncertainty_coverage_ratio": coverage_metrics.get(
                    "structural_uncertainty_coverage_ratio"
                ),
            }

        try:
            sensitivity = self.sensitivity_analyzer.get_sensitivity_analysis(
                simulation_id,
                ensemble_id,
            )
        except Exception:
            sensitivity = None
        if isinstance(sensitivity, dict):
            context["sensitivity"] = {
                "analysis_mode": sensitivity.get("analysis_mode"),
                "designed_comparison_count": sensitivity.get(
                    "designed_comparison_count",
                    len(sensitivity.get("designed_comparisons", []) or []),
                ),
                "support_assessment": sensitivity.get("quality_summary", {}).get(
                    "support_assessment"
                ),
            }

        if run_id:
            try:
                run_payload = self.ensemble_manager.load_run(
                    simulation_id,
                    ensemble_id,
                    run_id,
                )
            except Exception:
                run_payload = None
            if isinstance(run_payload, dict):
                context["selected_run"] = {
                    "run_id": run_id,
                    "simulation_market_summary": run_payload.get("simulation_market_summary"),
                    "simulation_market_provenance": run_payload.get(
                        "simulation_market_provenance"
                    ),
                }
        return context

    def _derive_evidence_regime(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        analytics_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        analytics_context = analytics_context or {}
        supportive_count = 0
        contradictory_count = 0
        mixed_count = 0
        hint_count = 0
        for entry in workspace.evidence_bundle.source_entries:
            conflict_status = str(entry.conflict_status or "").strip()
            if conflict_status == "supports":
                supportive_count += 1
            elif conflict_status == "contradicts":
                contradictory_count += 1
            elif conflict_status == "mixed":
                mixed_count += 1
            hints = entry.metadata.get("forecast_hints") if isinstance(entry.metadata, dict) else None
            if isinstance(hints, list):
                hint_count += len([item for item in hints if isinstance(item, dict)])

        missing_count = len(workspace.evidence_bundle.missing_evidence_markers)
        label = "mixed_local_evidence"
        if missing_count and supportive_count == 0 and contradictory_count == 0:
            label = "sparse_evidence"
        elif contradictory_count > 0 and contradictory_count >= supportive_count:
            label = "conflicted_evidence"
        elif supportive_count > 0 and contradictory_count == 0:
            label = "corroborated_local_evidence"

        modifiers: list[str] = []
        scenario_clusters = analytics_context.get("scenario_clusters") or {}
        structural_coverage_ratio = scenario_clusters.get(
            "structural_uncertainty_coverage_ratio"
        )
        sensitivity = analytics_context.get("sensitivity") or {}
        designed_comparison_count = int(
            sensitivity.get("designed_comparison_count") or 0
        )
        if designed_comparison_count > 0 and isinstance(structural_coverage_ratio, (int, float)):
            if float(structural_coverage_ratio) >= 0.5:
                modifiers.append("designed_comparison_informed")

        run_context = analytics_context.get("selected_run") or {}
        simulation_market_provenance = (
            run_context.get("simulation_market_provenance") or {}
        )
        if simulation_market_provenance.get("status") == "ready":
            modifiers.append("simulation_market_ready")

        return {
            "label": label,
            "supportive_entry_count": supportive_count,
            "contradictory_entry_count": contradictory_count,
            "mixed_entry_count": mixed_count,
            "hint_count": hint_count,
            "missing_evidence_count": missing_count,
            "modifiers": modifiers,
            "designed_comparison_count": designed_comparison_count,
            "structural_uncertainty_coverage_ratio": structural_coverage_ratio,
        }

    @staticmethod
    def _family_prior(
        *,
        question_type: str,
        evidence_regime: dict[str, Any],
        family: str,
    ) -> float:
        label = str(evidence_regime.get("label") or "mixed_local_evidence")
        modifiers = set(evidence_regime.get("modifiers") or [])
        family = str(family or "")
        priors: dict[str, dict[str, float]] = {
            "binary": {
                "base_rate": 0.26,
                "reference_class": 0.27,
                "retrieval_synthesis": 0.29,
                "simulation_market": 0.18,
                "simulation": 0.0,
            },
            "categorical": {
                "base_rate": 0.2,
                "reference_class": 0.34,
                "retrieval_synthesis": 0.3,
                "simulation_market": 0.16,
                "simulation": 0.0,
            },
            "numeric": {
                "base_rate": 0.28,
                "reference_class": 0.36,
                "retrieval_synthesis": 0.36,
                "simulation_market": 0.0,
                "simulation": 0.0,
            },
        }
        prior = priors.get(question_type, priors["binary"]).get(family, 0.1)
        if label == "corroborated_local_evidence":
            if family == "retrieval_synthesis":
                prior *= 1.35
            elif family == "base_rate":
                prior *= 0.85
        elif label == "conflicted_evidence":
            if family == "retrieval_synthesis":
                prior *= 0.85
            elif family in {"base_rate", "reference_class"}:
                prior *= 1.15
        elif label == "sparse_evidence":
            if family == "retrieval_synthesis":
                prior *= 0.75
            elif family in {"base_rate", "reference_class"}:
                prior *= 1.2
        if "designed_comparison_informed" in modifiers and family in {
            "reference_class",
            "simulation_market",
        }:
            prior *= 1.1
        if "simulation_market_ready" in modifiers and family == "simulation_market":
            prior *= 1.1
        return max(float(prior), 0.0)

    @staticmethod
    def _local_weight_multiplier(
        result: HybridWorkerResult,
        *,
        evidence_regime: dict[str, Any],
    ) -> float:
        inputs = result.confidence_inputs or {}
        family = str(result.worker_kind or "")
        if family == "base_rate":
            sample_count = int(inputs.get("sample_count") or 0)
            return _clamp(0.85 + min(sample_count, 30) / 100.0, 0.7, 1.25)
        if family == "reference_class":
            case_count = int(inputs.get("case_count") or 0)
            total_case_weight = float(inputs.get("total_case_weight") or 0.0)
            return _clamp(0.8 + min(case_count, 8) * 0.04 + min(total_case_weight, 6.0) * 0.03, 0.7, 1.3)
        if family == "retrieval_synthesis":
            entry_count = int(inputs.get("entry_count") or 0)
            contradiction_count = int(inputs.get("contradiction_count") or 0)
            multiplier = 0.85 + min(entry_count, 6) * 0.06 - min(contradiction_count, 3) * 0.08
            if evidence_regime.get("label") == "corroborated_local_evidence":
                multiplier += 0.08
            return _clamp(multiplier, 0.65, 1.3)
        if family == "simulation_market":
            disagreement_index = float(inputs.get("disagreement_index") or 0.0)
            participant_count = int(inputs.get("participant_count") or 0)
            multiplier = 0.8 + min(participant_count, 4) * 0.05 - min(disagreement_index, 0.5) * 0.5
            if inputs.get("provenance_status") == "ready":
                multiplier += 0.05
            return _clamp(multiplier, 0.5, 1.2)
        return 1.0

    def _apply_ensemble_policy(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        worker_results: list[HybridWorkerResult],
        analytics_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        question_type = _workspace_question_type(workspace)
        evidence_regime = self._derive_evidence_regime(
            workspace,
            analytics_context=analytics_context,
        )
        candidates = [
            result
            for result in worker_results
            if result.status == "completed"
            and result.influences_best_estimate
            and (result.estimate is not None or result.value is not None)
        ]
        if not candidates:
            return {
                "policy_name": "empirically_tuned_worker_ensemble",
                "question_type": question_type,
                "evidence_regime": evidence_regime,
                "normalized_family_weights": {},
                "analytics_context": analytics_context or {},
                "notes": [
                    "No completed best-estimate workers were available for tuned aggregation.",
                ],
            }

        raw_weights: dict[str, float] = {}
        worker_weight_details: dict[str, dict[str, Any]] = {}
        for result in candidates:
            family = str(result.worker_kind or "")
            prior_weight = self._family_prior(
                question_type=question_type,
                evidence_regime=evidence_regime,
                family=family,
            )
            local_multiplier = self._local_weight_multiplier(
                result,
                evidence_regime=evidence_regime,
            )
            raw_weight = max(float(result.effective_weight or 0.0), 0.05) * prior_weight * local_multiplier
            raw_weights[result.worker_id] = raw_weight
            worker_weight_details[result.worker_id] = {
                "family": family,
                "base_worker_weight": round(float(result.effective_weight or 0.0), 6),
                "prior_weight": round(float(prior_weight), 6),
                "local_multiplier": round(float(local_multiplier), 6),
                "raw_weight": round(float(raw_weight), 6),
            }

        total_weight = sum(raw_weights.values())
        normalized_family_weights: dict[str, float] = {}
        for result in candidates:
            normalized_weight = (
                raw_weights.get(result.worker_id, 0.0) / total_weight if total_weight > 0 else 0.0
            )
            result.effective_weight = normalized_weight
            result.confidence_inputs["weight_plan"] = {
                **worker_weight_details[result.worker_id],
                "normalized_weight": round(float(normalized_weight), 6),
                "evidence_regime": evidence_regime.get("label"),
            }
            normalized_family_weights[result.worker_kind] = round(
                float(normalized_family_weights.get(result.worker_kind, 0.0) + normalized_weight),
                6,
            )

        return {
            "policy_name": "empirically_tuned_worker_ensemble",
            "question_type": question_type,
            "evidence_regime": evidence_regime,
            "normalized_family_weights": normalized_family_weights,
            "worker_weights": worker_weight_details,
            "analytics_context": analytics_context or {},
            "notes": [
                "Worker weights are tuned by worker family, question type, and current evidence regime.",
            ],
        }

    def _run_base_rate_worker(
        self,
        workspace: ForecastWorkspaceRecord,
        worker: ForecastWorker,
        comparable_workspaces: list[ForecastWorkspaceRecord],
        recorded_at: str,
        metric_id: Optional[str],
        operator: Optional[str],
        threshold: Optional[float],
    ) -> HybridWorkerResult:
        question_type = _workspace_question_type(workspace)
        benchmark = worker.metadata.get("benchmark") if isinstance(worker.metadata, dict) else None
        assumptions: list[str] = []
        counterevidence: list[str] = []
        values: list[float] = []
        sample_count = 0
        if question_type == "categorical":
            outcome_labels = _workspace_outcome_labels(workspace)
            distribution: dict[str, float] = {}
            if isinstance(benchmark, dict) and isinstance(benchmark.get("distribution"), dict):
                distribution = _normalize_distribution(
                    benchmark.get("distribution", {}),
                    labels=outcome_labels,
                )
                sample_count = int(benchmark.get("sample_count") or 0)
                assumptions = _dedupe_strings(benchmark.get("assumptions", []))
                counterevidence = _dedupe_strings(benchmark.get("counterevidence", []))
            else:
                label_counts: dict[str, float] = {}
                candidate_workspaces = [workspace, *comparable_workspaces]
                for candidate_workspace in candidate_workspaces:
                    if candidate_workspace.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                        cases = candidate_workspace.evaluation_cases
                    else:
                        cases = [
                            case
                            for case in candidate_workspace.evaluation_cases
                            if case.status == "resolved"
                        ]
                    for case in cases:
                        if case.status != "resolved":
                            continue
                        observed_label = _extract_categorical_outcome(
                            case,
                            outcome_labels=outcome_labels,
                        )
                        if observed_label is None:
                            continue
                        label_counts[observed_label] = label_counts.get(observed_label, 0.0) + 1.0
                        sample_count += 1
                distribution = _normalize_distribution(label_counts, labels=outcome_labels)
                assumptions = [
                    "Resolved categorical outcomes from the local registry remain directionally informative.",
                ]
            if not distribution or sample_count <= 0:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="base_rate",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Base-rate worker abstained because no comparable resolved categorical cases were available.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="categorical_distribution",
                    value_semantics="forecast_distribution",
                    abstain_reason="no_comparable_cases",
                    failure_modes=["no_comparable_cases"],
                    assumptions=assumptions,
                )
            top_label = _top_distribution_label(distribution)
            top_share = float(distribution.get(top_label, 0.0)) if top_label else 0.0
            weight = _clamp(0.25 + min(0.65, sample_count / 30.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="base_rate",
                recorded_at=recorded_at,
                status="completed",
                summary="Base-rate benchmark from resolved categorical cases and benchmark metadata.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="categorical_distribution",
                value_semantics="forecast_distribution",
                estimate=top_share,
                value={
                    "distribution": distribution,
                    "top_label": top_label,
                    "top_label_share": round(top_share, 6),
                    "sample_count": sample_count,
                },
                effective_weight=weight,
                assumptions=assumptions,
                counterevidence=counterevidence,
                confidence_inputs={
                    "sample_count": sample_count,
                    "source": "benchmark" if benchmark else "local_registry",
                },
            )
        if question_type == "numeric":
            unit = _workspace_numeric_unit(workspace)
            numeric_values: list[float] = []
            if isinstance(benchmark, dict) and (
                benchmark.get("point_estimate") is not None
                or benchmark.get("estimate") is not None
            ):
                try:
                    point_estimate = float(
                        benchmark.get("point_estimate", benchmark.get("estimate"))
                    )
                except (TypeError, ValueError):
                    point_estimate = None
                sample_count = int(benchmark.get("sample_count") or 0)
                assumptions = _dedupe_strings(benchmark.get("assumptions", []))
                counterevidence = _dedupe_strings(benchmark.get("counterevidence", []))
                payload = {
                    "point_estimate": point_estimate,
                    "value": point_estimate,
                    "intervals": dict(benchmark.get("intervals", {}))
                    if isinstance(benchmark.get("intervals"), dict)
                    else {},
                    "sample_count": sample_count,
                }
                if unit:
                    payload["unit"] = unit
                if point_estimate is None:
                    payload = {}
            else:
                for case in workspace.evaluation_cases:
                    if case.status != "resolved":
                        continue
                    numeric_value = _extract_numeric_outcome(case, metric_id=metric_id)
                    if numeric_value is not None:
                        numeric_values.append(numeric_value)
                for comparable in comparable_workspaces:
                    if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                        continue
                    for case in comparable.evaluation_cases:
                        if case.status != "resolved":
                            continue
                        numeric_value = _extract_numeric_outcome(case, metric_id=metric_id)
                        if numeric_value is not None:
                            numeric_values.append(numeric_value)
                sample_count = len(numeric_values)
                payload = _build_numeric_interval_payload(
                    numeric_values,
                    unit=unit,
                    interval_levels=_workspace_interval_levels(workspace),
                )
                assumptions = [
                    "Resolved numeric cases from the local registry remain directionally informative.",
                ]
            point_estimate = payload.get("point_estimate")
            if point_estimate is None:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="base_rate",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Base-rate worker abstained because no comparable resolved numeric cases were available.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="numeric_interval",
                    value_semantics="numeric_interval_estimate",
                    abstain_reason="no_comparable_cases",
                    failure_modes=["no_comparable_cases"],
                    assumptions=assumptions,
                )
            weight = _clamp(0.25 + min(0.65, sample_count / 30.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="base_rate",
                recorded_at=recorded_at,
                status="completed",
                summary="Base-rate numeric benchmark from resolved cases and benchmark metadata.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="numeric_interval",
                value_semantics="numeric_interval_estimate",
                estimate=float(point_estimate),
                value=payload,
                effective_weight=weight,
                assumptions=assumptions,
                counterevidence=counterevidence,
                confidence_inputs={
                    "sample_count": sample_count,
                    "source": "benchmark" if benchmark else "local_registry",
                },
            )
        if isinstance(benchmark, dict) and benchmark.get("estimate") is not None:
            estimate = _clamp(float(benchmark.get("estimate")))
            sample_count = int(benchmark.get("sample_count") or 0)
            assumptions = _dedupe_strings(benchmark.get("assumptions", []))
            counterevidence = _dedupe_strings(benchmark.get("counterevidence", []))
        else:
            values.extend(_evaluation_case_values(workspace, metric_id, operator, threshold))
            for comparable in comparable_workspaces:
                if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                    continue
                resolved_value = _resolved_binary_value_from_workspace(
                    comparable,
                    metric_id,
                    operator,
                    threshold,
                )
                if resolved_value is not None:
                    values.append(resolved_value)
            estimate = _mean(values)
            sample_count = len(values)
            assumptions = [
                "Resolved cases from the local forecast registry remain directionally informative.",
            ]
            counterevidence = []
        if estimate is None:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="base_rate",
                recorded_at=recorded_at,
                status="abstained",
                summary="Base-rate worker abstained because no comparable resolved cases were available.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="probability",
                value_semantics="forecast_probability",
                abstain_reason="no_comparable_cases",
                failure_modes=["no_comparable_cases"],
                assumptions=assumptions,
            )
        weight = _clamp(0.25 + min(0.65, sample_count / 30.0))
        return HybridWorkerResult(
            output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            worker_id=worker.worker_id,
            worker_kind="base_rate",
            recorded_at=recorded_at,
            status="completed",
            summary="Base-rate benchmark from resolved cases and benchmark metadata.",
            contribution_role="best_estimate",
            influences_best_estimate=True,
            value_type="probability",
            value_semantics="forecast_probability",
            estimate=estimate,
            value=estimate,
            effective_weight=weight,
            assumptions=assumptions,
            counterevidence=counterevidence,
            confidence_inputs={
                "sample_count": sample_count,
                "source": "benchmark" if benchmark else "local_registry",
            },
        )

    def _run_reference_class_worker(
        self,
        workspace: ForecastWorkspaceRecord,
        worker: ForecastWorker,
        comparable_workspaces: list[ForecastWorkspaceRecord],
        recorded_at: str,
        metric_id: Optional[str],
        operator: Optional[str],
        threshold: Optional[float],
    ) -> HybridWorkerResult:
        question_type = _workspace_question_type(workspace)
        reference_cases = worker.metadata.get("reference_cases") if isinstance(worker.metadata, dict) else None
        weighted_cases: list[tuple[float, float]] = []
        assumptions: list[str] = []
        if question_type == "categorical":
            outcome_labels = _workspace_outcome_labels(workspace)
            weighted_labels: dict[str, float] = {}
            if isinstance(reference_cases, list) and reference_cases:
                for item in reference_cases:
                    if not isinstance(item, dict):
                        continue
                    label = _extract_categorical_outcome(
                        type("CaseLike", (), {"observed_outcome": item, "observed_value": item})(),
                        outcome_labels=outcome_labels,
                    )
                    if label is None:
                        label = str(item.get("label") or item.get("outcome") or item.get("category") or "").strip() or None
                    if label is None:
                        continue
                    try:
                        weight = float(item.get("weight", 1.0))
                    except (TypeError, ValueError):
                        continue
                    weighted_labels[label] = weighted_labels.get(label, 0.0) + max(weight, 0.0)
                assumptions = _dedupe_strings(worker.metadata.get("assumptions", []))
            else:
                target_tokens = _tokenize(
                    workspace.forecast_question.title,
                    workspace.forecast_question.question_text,
                    workspace.forecast_question.tags,
                )
                for comparable in comparable_workspaces:
                    if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                        continue
                    comparable_tokens = _tokenize(
                        comparable.forecast_question.title,
                        comparable.forecast_question.question_text,
                        comparable.forecast_question.tags,
                    )
                    overlap = len(target_tokens & comparable_tokens)
                    union = len(target_tokens | comparable_tokens) or 1
                    score = overlap / union
                    if score <= 0:
                        continue
                    for case in comparable.evaluation_cases:
                        if case.status != "resolved":
                            continue
                        label = _extract_categorical_outcome(
                            case,
                            outcome_labels=outcome_labels,
                        )
                        if label is None:
                            continue
                        weighted_labels[label] = weighted_labels.get(label, 0.0) + score
                assumptions = [
                    "The selected categorical cases remain a reasonable reference class for this question.",
                ]
            distribution = _normalize_distribution(weighted_labels, labels=outcome_labels)
            top_label = _top_distribution_label(distribution)
            top_share = float(distribution.get(top_label, 0.0)) if top_label else 0.0
            total_weight = sum(weighted_labels.values())
            if not distribution or total_weight <= 0:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="reference_class",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Reference-class worker abstained because no weighted categorical comparison cases were available.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="categorical_distribution",
                    value_semantics="forecast_distribution",
                    abstain_reason="no_reference_cases",
                    failure_modes=["no_reference_cases"],
                    assumptions=assumptions,
                )
            weight = _clamp(0.25 + min(0.65, total_weight / 5.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="reference_class",
                recorded_at=recorded_at,
                status="completed",
                summary="Reference-class categorical estimate from weighted comparable cases.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="categorical_distribution",
                value_semantics="forecast_distribution",
                estimate=top_share,
                value={
                    "distribution": distribution,
                    "top_label": top_label,
                    "top_label_share": round(top_share, 6),
                    "reference_weight": round(total_weight, 6),
                },
                effective_weight=weight,
                assumptions=assumptions,
                confidence_inputs={
                    "case_count": len(weighted_labels),
                    "total_case_weight": round(total_weight, 6),
                },
            )
        if question_type == "numeric":
            unit = _workspace_numeric_unit(workspace)
            numeric_values: list[float] = []
            numeric_weights: list[float] = []
            if isinstance(reference_cases, list) and reference_cases:
                for item in reference_cases:
                    if not isinstance(item, dict) or item.get("value") is None:
                        continue
                    try:
                        numeric_values.append(float(item["value"]))
                        numeric_weights.append(float(item.get("weight", 1.0)))
                    except (TypeError, ValueError):
                        continue
                assumptions = _dedupe_strings(worker.metadata.get("assumptions", []))
            else:
                target_tokens = _tokenize(
                    workspace.forecast_question.title,
                    workspace.forecast_question.question_text,
                    workspace.forecast_question.tags,
                )
                for comparable in comparable_workspaces:
                    if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                        continue
                    comparable_tokens = _tokenize(
                        comparable.forecast_question.title,
                        comparable.forecast_question.question_text,
                        comparable.forecast_question.tags,
                    )
                    overlap = len(target_tokens & comparable_tokens)
                    union = len(target_tokens | comparable_tokens) or 1
                    score = overlap / union
                    if score <= 0:
                        continue
                    for case in comparable.evaluation_cases:
                        if case.status != "resolved":
                            continue
                        numeric_value = _extract_numeric_outcome(case, metric_id=metric_id)
                        if numeric_value is None:
                            continue
                        numeric_values.append(numeric_value)
                        numeric_weights.append(score)
                assumptions = [
                    "The selected numeric cases remain a reasonable reference class for this question.",
                ]
            if not numeric_values or not numeric_weights:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="reference_class",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Reference-class worker abstained because no weighted numeric comparison cases were available.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="numeric_interval",
                    value_semantics="numeric_interval_estimate",
                    abstain_reason="no_reference_cases",
                    failure_modes=["no_reference_cases"],
                    assumptions=assumptions,
                )
            total_weight = sum(max(weight, 0.0) for weight in numeric_weights)
            weighted_mean = _weighted_mean(list(zip(numeric_values, numeric_weights)))
            payload = _build_numeric_interval_payload(
                numeric_values,
                unit=unit,
                interval_levels=_workspace_interval_levels(workspace),
            )
            payload["reference_weight"] = round(total_weight, 6)
            if weighted_mean is not None:
                payload["point_estimate"] = round(float(weighted_mean), 6)
                payload["value"] = round(float(weighted_mean), 6)
            weight = _clamp(0.25 + min(0.65, total_weight / 5.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="reference_class",
                recorded_at=recorded_at,
                status="completed",
                summary="Reference-class numeric estimate from weighted comparable cases.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="numeric_interval",
                value_semantics="numeric_interval_estimate",
                estimate=float(weighted_mean) if weighted_mean is not None else None,
                value=payload,
                effective_weight=weight,
                assumptions=assumptions,
                confidence_inputs={
                    "case_count": len(numeric_values),
                    "total_case_weight": round(total_weight, 6),
                },
            )
        if isinstance(reference_cases, list) and reference_cases:
            for item in reference_cases:
                if not isinstance(item, dict) or item.get("value") is None:
                    continue
                try:
                    weighted_cases.append((float(item["value"]), float(item.get("weight", 1.0))))
                except (TypeError, ValueError):
                    continue
            assumptions = _dedupe_strings(worker.metadata.get("assumptions", []))
        else:
            target_tokens = _tokenize(
                workspace.forecast_question.title,
                workspace.forecast_question.question_text,
                workspace.forecast_question.tags,
            )
            for comparable in comparable_workspaces:
                if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                    continue
                resolved_value = _resolved_binary_value_from_workspace(
                    comparable,
                    metric_id,
                    operator,
                    threshold,
                )
                if resolved_value is None:
                    continue
                comparable_tokens = _tokenize(
                    comparable.forecast_question.title,
                    comparable.forecast_question.question_text,
                    comparable.forecast_question.tags,
                )
                overlap = len(target_tokens & comparable_tokens)
                union = len(target_tokens | comparable_tokens) or 1
                score = overlap / union
                if score > 0:
                    weighted_cases.append((resolved_value, score))
            if not weighted_cases:
                weighted_cases = [(value, 1.0) for value in _evaluation_case_values(workspace, metric_id, operator, threshold)]
            assumptions = [
                "The selected cases remain a reasonable reference class for this question.",
            ]
        estimate = _weighted_mean(weighted_cases)
        if estimate is None:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="reference_class",
                recorded_at=recorded_at,
                status="abstained",
                summary="Reference-class worker abstained because no weighted comparison cases were available.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="probability",
                value_semantics="forecast_probability",
                abstain_reason="no_reference_cases",
                failure_modes=["no_reference_cases"],
                assumptions=assumptions,
            )
        total_weight = sum(weight for _, weight in weighted_cases)
        weight = _clamp(0.25 + min(0.65, total_weight / 5.0))
        return HybridWorkerResult(
            output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            worker_id=worker.worker_id,
            worker_kind="reference_class",
            recorded_at=recorded_at,
            status="completed",
            summary="Reference-class estimate from weighted comparable cases.",
            contribution_role="best_estimate",
            influences_best_estimate=True,
            value_type="probability",
            value_semantics="forecast_probability",
            estimate=estimate,
            value=estimate,
            effective_weight=weight,
            assumptions=assumptions,
            confidence_inputs={
                "case_count": len(weighted_cases),
                "total_case_weight": round(total_weight, 6),
            },
        )

    def _run_retrieval_worker(
        self,
        workspace: ForecastWorkspaceRecord,
        worker: ForecastWorker,
        recorded_at: str,
    ) -> HybridWorkerResult:
        question_type = _workspace_question_type(workspace)
        weighted_estimates: list[tuple[float, float]] = []
        assumptions: list[str] = []
        counterevidence: list[str] = []
        citations: list[dict[str, Any]] = []
        contradiction_count = 0
        categorical_weights: dict[str, float] = {}
        numeric_points: list[tuple[float, float]] = []
        numeric_interval_bounds: dict[str, list[tuple[float, float]]] = {}
        outcome_labels = _workspace_outcome_labels(workspace)
        unit = _workspace_numeric_unit(workspace)
        for entry in workspace.evidence_bundle.source_entries:
            base_weight = _mean(
                [
                    value
                    for value in (
                        entry.quality_score,
                        entry.relevance_score,
                        entry.freshness_score,
                    )
                    if value is not None
                ]
            ) or 0.45
            hints = entry.metadata.get("forecast_hints") if isinstance(entry.metadata, dict) else None
            if isinstance(hints, list) and hints:
                for hint in hints:
                    if not isinstance(hint, dict):
                        continue
                    try:
                        confidence_weight = float(hint.get("confidence_weight", 1.0))
                    except (TypeError, ValueError):
                        confidence_weight = 1.0
                    effective_weight = base_weight * max(confidence_weight, 0.05)
                    if question_type == "categorical":
                        distribution = {}
                        if isinstance(hint.get("distribution"), dict):
                            distribution = _normalize_distribution(
                                hint.get("distribution", {}),
                                labels=outcome_labels,
                            )
                        else:
                            label = str(
                                hint.get("label")
                                or hint.get("top_label")
                                or hint.get("outcome")
                                or ""
                            ).strip()
                            if label:
                                distribution = _normalize_distribution(
                                    {label: 1.0},
                                    labels=outcome_labels,
                                )
                        for label, weight in distribution.items():
                            categorical_weights[label] = categorical_weights.get(label, 0.0) + (
                                float(weight) * effective_weight
                            )
                    elif question_type == "numeric":
                        point_estimate = hint.get("point_estimate", hint.get("estimate"))
                        if point_estimate is not None:
                            try:
                                numeric_points.append((float(point_estimate), effective_weight))
                            except (TypeError, ValueError):
                                pass
                        intervals = hint.get("intervals")
                        if isinstance(intervals, dict):
                            for level, bounds in intervals.items():
                                if not isinstance(bounds, dict):
                                    continue
                                try:
                                    low = float(bounds.get("low"))
                                    high = float(bounds.get("high"))
                                except (TypeError, ValueError):
                                    continue
                                numeric_interval_bounds.setdefault(str(level), []).append(
                                    ((low + high) / 2.0, effective_weight)
                                )
                        if hint.get("unit") and not unit:
                            unit = str(hint["unit"]).strip() or unit
                    elif hint.get("estimate") is not None:
                        try:
                            estimate = _clamp(float(hint["estimate"]))
                        except (TypeError, ValueError):
                            continue
                        weighted_estimates.append((estimate, effective_weight))
                    assumption = str(hint.get("assumption") or "").strip()
                    if assumption:
                        assumptions.append(assumption)
                    counter = str(hint.get("counterevidence") or "").strip()
                    if counter:
                        counterevidence.append(counter)
            elif question_type == "binary" and entry.conflict_status in {"supports", "contradicts"}:
                weighted_estimates.append(
                    (
                        0.66 if entry.conflict_status == "supports" else 0.34,
                        max(base_weight, 0.1),
                    )
                )
                if entry.conflict_status == "supports":
                    assumptions.append(
                        f"{entry.title} remains directionally supportive evidence."
                    )
                else:
                    contradiction_count += 1
                    counterevidence.append(entry.summary or entry.title)
            if entry.conflict_status == "contradicts":
                contradiction_count += 1
            if entry.citation_id:
                citations.append(
                    {
                        "citation_id": entry.citation_id,
                        "title": entry.title,
                        "locator": entry.locator,
                    }
                )
        if question_type == "categorical":
            distribution = _normalize_distribution(categorical_weights, labels=outcome_labels)
            top_label = _top_distribution_label(distribution)
            top_share = float(distribution.get(top_label, 0.0)) if top_label else 0.0
            if not distribution or not any(value > 0 for value in distribution.values()):
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="retrieval_synthesis",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Retrieval worker abstained because bounded evidence did not support a categorical outcome distribution.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="categorical_distribution",
                    value_semantics="forecast_distribution",
                    abstain_reason="non_directional_evidence",
                    failure_modes=["non_directional_evidence"],
                    assumptions=_dedupe_strings(assumptions),
                    counterevidence=_dedupe_strings(counterevidence),
                )
            total_weight = sum(categorical_weights.values())
            weight = _clamp(0.2 + min(0.7, total_weight / max(len(categorical_weights), 1)))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="retrieval_synthesis",
                recorded_at=recorded_at,
                status="completed",
                summary="Retrieval synthesis from bounded local evidence for categorical outcomes.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="categorical_distribution",
                value_semantics="forecast_distribution",
                estimate=top_share,
                value={
                    "distribution": distribution,
                    "top_label": top_label,
                    "top_label_share": round(top_share, 6),
                },
                effective_weight=weight,
                assumptions=_dedupe_strings(assumptions),
                counterevidence=_dedupe_strings(counterevidence),
                confidence_inputs={
                    "entry_count": len(workspace.evidence_bundle.source_entries),
                    "contradiction_count": contradiction_count,
                },
                citations=citations,
            )
        if question_type == "numeric":
            point_estimate = _weighted_mean(numeric_points)
            if point_estimate is None:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="retrieval_synthesis",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Retrieval worker abstained because bounded evidence did not support a numeric estimate.",
                    contribution_role="best_estimate",
                    influences_best_estimate=False,
                    value_type="numeric_interval",
                    value_semantics="numeric_interval_estimate",
                    abstain_reason="non_directional_evidence",
                    failure_modes=["non_directional_evidence"],
                    assumptions=_dedupe_strings(assumptions),
                    counterevidence=_dedupe_strings(counterevidence),
                )
            payload = {
                "point_estimate": round(float(point_estimate), 6),
                "value": round(float(point_estimate), 6),
                "intervals": {},
            }
            for level, weighted_bounds in numeric_interval_bounds.items():
                midpoint = _weighted_mean(weighted_bounds)
                if midpoint is None:
                    continue
                span = max(
                    0.0,
                    _mean([abs(value - point_estimate) for value, _ in weighted_bounds]) or 0.0,
                )
                payload["intervals"][level] = {
                    "low": round(float(midpoint - span), 6),
                    "high": round(float(midpoint + span), 6),
                }
            if unit:
                payload["unit"] = unit
            total_weight = sum(weight for _, weight in numeric_points)
            weight = _clamp(0.2 + min(0.7, total_weight / max(len(numeric_points), 1)))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="retrieval_synthesis",
                recorded_at=recorded_at,
                status="completed",
                summary="Retrieval synthesis from bounded local evidence for numeric estimates.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="numeric_interval",
                value_semantics="numeric_interval_estimate",
                estimate=float(point_estimate),
                value=payload,
                effective_weight=weight,
                assumptions=_dedupe_strings(assumptions),
                counterevidence=_dedupe_strings(counterevidence),
                confidence_inputs={
                    "entry_count": len(workspace.evidence_bundle.source_entries),
                    "contradiction_count": contradiction_count,
                },
                citations=citations,
            )
        estimate = _weighted_mean(weighted_estimates)
        if estimate is None:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="retrieval_synthesis",
                recorded_at=recorded_at,
                status="abstained",
                summary="Retrieval worker abstained because bounded evidence was non-directional or missing.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="probability",
                value_semantics="forecast_probability",
                abstain_reason="non_directional_evidence",
                failure_modes=["non_directional_evidence"],
                assumptions=_dedupe_strings(assumptions),
                counterevidence=_dedupe_strings(counterevidence),
            )
        total_weight = sum(weight for _, weight in weighted_estimates)
        weight = _clamp(0.2 + min(0.7, total_weight / max(len(weighted_estimates), 1)))
        return HybridWorkerResult(
            output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            worker_id=worker.worker_id,
            worker_kind="retrieval_synthesis",
            recorded_at=recorded_at,
            status="completed",
            summary="Retrieval synthesis from bounded local evidence.",
            contribution_role="best_estimate",
            influences_best_estimate=True,
            value_type="probability",
            value_semantics="forecast_probability",
            estimate=estimate,
            value=estimate,
            effective_weight=weight,
            assumptions=_dedupe_strings(assumptions),
            counterevidence=_dedupe_strings(counterevidence),
            confidence_inputs={
                "entry_count": len(workspace.evidence_bundle.source_entries),
                "contradiction_count": contradiction_count,
            },
            citations=citations,
        )

    def _run_simulation_market_worker(
        self,
        workspace: ForecastWorkspaceRecord,
        worker: ForecastWorker,
        recorded_at: str,
    ) -> HybridWorkerResult:
        question_type = _workspace_question_type(workspace)
        if question_type not in {"binary", "categorical"}:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation_market",
                recorded_at=recorded_at,
                status="abstained",
                summary="Synthetic market worker abstained because the question type is unsupported.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="qualitative",
                value_semantics="qualitative_judgment",
                abstain_reason="unsupported_question_type",
                failure_modes=["unsupported_question_type"],
                notes=[
                    "Simulation-market inference remains bounded to binary and categorical questions.",
                ],
            )

        active_bundle_id = workspace.evidence_bundle.bundle_id
        summary = self.simulation_market_aggregator.summarize_workspace(
            workspace,
            evidence_bundle_ids=[active_bundle_id] if active_bundle_id else [],
        )
        if not summary:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation_market",
                recorded_at=recorded_at,
                status="abstained",
                summary="Synthetic market worker abstained because no run-scoped market artifacts were available.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="qualitative",
                value_semantics="qualitative_judgment",
                abstain_reason="no_simulation_market_outputs",
                failure_modes=["no_simulation_market_outputs"],
            )

        validation = self.signal_provenance_validator.validate_simulation_market_summary(
            summary,
            available_evidence_bundle_ids=[active_bundle_id] if active_bundle_id else [],
        )
        provenance_status = validation["status"]
        disagreement_index = float(summary.get("disagreement_index") or 0.0)
        downgrade_reasons = list(validation.get("downgrade_reasons") or [])
        if provenance_status == "invalid":
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation_market",
                recorded_at=recorded_at,
                status="abstained",
                summary="Synthetic market worker abstained because signal provenance was invalid.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="qualitative",
                value_semantics="qualitative_judgment",
                abstain_reason="invalid_simulation_market_provenance",
                failure_modes=["invalid_simulation_market_provenance"],
                confidence_inputs={
                    "provenance_status": provenance_status,
                    "provenance_report": validation,
                },
                notes=[
                    "Signals without traceable run-scoped provenance cannot influence the best estimate.",
                ],
            )
        if disagreement_index >= 0.45:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation_market",
                recorded_at=recorded_at,
                status="abstained",
                summary="Synthetic market worker abstained because disagreement remained too high for defended inference.",
                contribution_role="best_estimate",
                influences_best_estimate=False,
                value_type="qualitative",
                value_semantics="qualitative_judgment",
                abstain_reason="simulation_market_disagreement",
                failure_modes=["simulation_market_disagreement"],
                confidence_inputs={
                    "provenance_status": provenance_status,
                    "disagreement_index": round(disagreement_index, 6),
                },
                notes=[
                    "High synthetic-market disagreement is treated as a hard gate for best-estimate use.",
                ],
            )

        participant_count = int(summary.get("participant_count") or 0)
        judgment_count = int(summary.get("judgment_count") or 0)
        base_weight = 0.16 + min(0.18, participant_count * 0.03) + min(0.08, judgment_count * 0.015)
        weight = base_weight * float(validation.get("weight_multiplier") or 1.0)
        if disagreement_index >= 0.25:
            weight *= 0.55
            downgrade_reasons.append("downgraded_for_disagreement")
        if int(summary.get("missing_information_signal", {}).get("request_count", 0) or 0) >= 3:
            weight *= 0.85
            downgrade_reasons.append("downgraded_for_missing_information")
        weight = _clamp(weight, 0.05, 0.45)

        signal_payload = {
            "synthetic_consensus_probability": summary.get("synthetic_consensus_probability"),
            "disagreement_index": summary.get("disagreement_index"),
            "argument_cluster_distribution": dict(summary.get("argument_cluster_distribution") or {}),
            "belief_momentum": dict(summary.get("belief_momentum") or {}),
            "minority_warning_signal": dict(summary.get("minority_warning_signal") or {}),
            "missing_information_signal": dict(summary.get("missing_information_signal") or {}),
            "scenario_split_distribution": dict(summary.get("scenario_split_distribution") or {}),
            "provenance_status": provenance_status,
            "provenance_report": validation,
            "signals": dict(summary.get("signals") or {}),
        }
        notes = [
            "Simulation-market signals are heuristic inference inputs derived from simulated discourse.",
            "They remain observational and non-calibrated until later scoring evidence exists.",
        ]
        notes.extend(downgrade_reasons)
        if question_type == "categorical":
            distribution = dict(summary.get("scenario_split_distribution") or {})
            top_label = _top_distribution_label(distribution)
            top_share = float(distribution.get(top_label, 0.0)) if top_label else 0.0
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation_market",
                recorded_at=recorded_at,
                status="completed",
                summary="Synthetic market aggregation from run-scoped belief artifacts.",
                contribution_role="best_estimate",
                influences_best_estimate=True,
                value_type="categorical_distribution",
                value_semantics="forecast_distribution",
                estimate=top_share,
                value={
                    "distribution": distribution,
                    "top_label": top_label,
                    "top_label_share": round(top_share, 6),
                    **signal_payload,
                },
                effective_weight=weight,
                confidence_inputs={
                    "participant_count": participant_count,
                    "judgment_count": judgment_count,
                    "provenance_status": provenance_status,
                    "disagreement_index": round(disagreement_index, 6),
                    "downgraded": bool(downgrade_reasons),
                },
                notes=notes,
            )

        estimate = summary.get("synthetic_consensus_probability")
        return HybridWorkerResult(
            output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            worker_id=worker.worker_id,
            worker_kind="simulation_market",
            recorded_at=recorded_at,
            status="completed",
            summary="Synthetic market aggregation from run-scoped belief artifacts.",
            contribution_role="best_estimate",
            influences_best_estimate=True,
            value_type="probability",
            value_semantics="forecast_probability",
            estimate=float(estimate) if estimate is not None else None,
            value={
                "estimate": round(float(estimate), 6) if estimate is not None else None,
                "value": round(float(estimate), 6) if estimate is not None else None,
                **signal_payload,
            },
            effective_weight=weight,
            confidence_inputs={
                "participant_count": participant_count,
                "judgment_count": judgment_count,
                "provenance_status": provenance_status,
                "disagreement_index": round(disagreement_index, 6),
                "downgraded": bool(downgrade_reasons),
            },
            notes=notes,
        )

    def _run_simulation_worker(
        self,
        workspace: ForecastWorkspaceRecord,
        worker: ForecastWorker,
        recorded_at: str,
        metric_id: Optional[str],
        operator: Optional[str],
        threshold: Optional[float],
    ) -> HybridWorkerResult:
        question_type = _workspace_question_type(workspace)
        if question_type == "numeric":
            numeric_payload, run_count = self._load_simulation_numeric_payload(
                workspace,
                metric_id=metric_id,
            )
            point_estimate = (
                float(numeric_payload.get("point_estimate"))
                if numeric_payload.get("point_estimate") is not None
                else None
            )
            if point_estimate is None:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="simulation",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Simulation worker abstained because no bounded numeric scenario outputs were available.",
                    contribution_role="scenario_context",
                    influences_best_estimate=False,
                    value_type="numeric_interval",
                    value_semantics="numeric_interval_estimate",
                    abstain_reason="no_simulation_outputs",
                    failure_modes=["no_simulation_outputs"],
                    notes=[
                        "Simulation remains scenario evidence only and cannot become the default answer source.",
                    ],
                )
            weight = _clamp(0.05 + min(0.2, run_count / 50.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation",
                recorded_at=recorded_at,
                status="completed",
                summary="Simulation scenario evidence for numeric outcomes from the existing subsystem.",
                contribution_role="scenario_context",
                influences_best_estimate=False,
                value_type="numeric_interval",
                value_semantics="numeric_interval_estimate",
                estimate=point_estimate,
                value=numeric_payload,
                effective_weight=weight,
                assumptions=[
                    "Simulation numeric summaries remain descriptive scenario evidence only.",
                ],
                confidence_inputs={
                    "run_count": run_count,
                    "probability_interpretation": "do_not_treat_as_real_world_probability",
                },
                notes=[
                    "Simulation contributes supporting scenario evidence only and does not determine the best estimate.",
                ],
            )
        if question_type == "categorical":
            distribution, run_count = self._load_simulation_distribution_payload(workspace)
            top_label = _top_distribution_label(distribution)
            top_share = float(distribution.get(top_label, 0.0)) if top_label else 0.0
            if not distribution:
                return HybridWorkerResult(
                    output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                    forecast_id=workspace.forecast_question.forecast_id,
                    worker_id=worker.worker_id,
                    worker_kind="simulation",
                    recorded_at=recorded_at,
                    status="abstained",
                    summary="Simulation worker abstained because no bounded categorical scenario outputs were available.",
                    contribution_role="scenario_context",
                    influences_best_estimate=False,
                    value_type="categorical_distribution",
                    value_semantics="forecast_distribution",
                    abstain_reason="no_simulation_outputs",
                    failure_modes=["no_simulation_outputs"],
                    notes=[
                        "Simulation remains scenario evidence only and cannot become the default answer source.",
                    ],
                )
            weight = _clamp(0.05 + min(0.2, run_count / 50.0))
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation",
                recorded_at=recorded_at,
                status="completed",
                summary="Simulation scenario evidence for categorical outcomes from the existing subsystem.",
                contribution_role="scenario_context",
                influences_best_estimate=False,
                value_type="categorical_distribution",
                value_semantics="forecast_distribution",
                estimate=top_share,
                value={
                    "distribution": distribution,
                    "top_label": top_label,
                    "top_label_share": round(top_share, 6),
                    "run_count": run_count,
                },
                effective_weight=weight,
                assumptions=[
                    "Simulation outcome shares remain descriptive scenario evidence only.",
                ],
                confidence_inputs={
                    "run_count": run_count,
                    "probability_interpretation": "do_not_treat_as_real_world_probability",
                },
                notes=[
                    "Simulation contributes supporting scenario evidence only and does not determine the best estimate.",
                ],
            )
        observed_run_share, run_count = self._load_simulation_observed_run_share(
            workspace,
            metric_id,
            operator,
            threshold,
        )
        if observed_run_share is None:
            return HybridWorkerResult(
                output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=worker.worker_id,
                worker_kind="simulation",
                recorded_at=recorded_at,
                status="abstained",
                summary="Simulation worker abstained because no bounded scenario outputs were available.",
                contribution_role="scenario_context",
                influences_best_estimate=False,
                value_type="scenario_observed_share",
                value_semantics="observed_run_share",
                abstain_reason="no_simulation_outputs",
                failure_modes=["no_simulation_outputs"],
                notes=[
                    "Simulation remains scenario evidence only and cannot become the default answer source.",
                ],
            )
        weight = _clamp(0.05 + min(0.2, run_count / 50.0))
        return HybridWorkerResult(
            output_id=f"{worker.worker_id}-output-{_compact_timestamp(recorded_at)}",
            forecast_id=workspace.forecast_question.forecast_id,
            worker_id=worker.worker_id,
            worker_kind="simulation",
            recorded_at=recorded_at,
            status="completed",
            summary="Simulation scenario evidence from the existing subsystem.",
            contribution_role="scenario_context",
            influences_best_estimate=False,
            value_type="scenario_observed_share",
            value_semantics="observed_run_share",
            estimate=observed_run_share,
            value=observed_run_share,
            effective_weight=weight,
            assumptions=[
                "Simulation run shares are descriptive scenario evidence only.",
            ],
            confidence_inputs={
                "run_count": run_count,
                "probability_interpretation": "do_not_treat_as_real_world_probability",
            },
            notes=[
                "Simulation contributes supporting scenario evidence only and does not determine the best estimate.",
            ],
        )

    def _load_simulation_observed_run_share(
        self,
        workspace: ForecastWorkspaceRecord,
        metric_id: Optional[str],
        operator: Optional[str],
        threshold: Optional[float],
    ) -> tuple[Optional[float], int]:
        contract = workspace.simulation_worker_contract
        simulation_id = (
            (contract.simulation_id if contract is not None else None)
            or workspace.forecast_question.primary_simulation_id
        )
        ensemble_ids = list(contract.ensemble_ids) if contract is not None else []
        if simulation_id and ensemble_ids and metric_id and threshold is not None:
            for ensemble_id in ensemble_ids:
                state_path = os.path.join(
                    self.simulation_data_dir,
                    simulation_id,
                    "ensemble",
                    f"ensemble_{ensemble_id}",
                    "ensemble_state.json",
                )
                if not os.path.exists(state_path):
                    continue
                with open(state_path, "r", encoding="utf-8") as handle:
                    ensemble_state = json.load(handle)
                run_ids = list(ensemble_state.get("run_ids") or [])
                values: list[float] = []
                for run_id in run_ids:
                    metrics_path = os.path.join(
                        self.simulation_data_dir,
                        simulation_id,
                        "ensemble",
                        f"ensemble_{ensemble_id}",
                        "runs",
                        f"run_{run_id}",
                        "metrics.json",
                    )
                    if not os.path.exists(metrics_path):
                        continue
                    with open(metrics_path, "r", encoding="utf-8") as handle:
                        metrics_payload = json.load(handle)
                    metric_payload = (
                        metrics_payload.get("metric_values", {}).get(metric_id) if metric_id else None
                    )
                    if not isinstance(metric_payload, dict) or metric_payload.get("value") is None:
                        continue
                    try:
                        values.append(float(metric_payload["value"]))
                    except (TypeError, ValueError):
                        continue
                if values:
                    passed = [
                        _compare_threshold(value, operator, threshold)
                        for value in values
                    ]
                    normalized = [item for item in passed if item is not None]
                    if normalized:
                        return (_mean(normalized), len(normalized))
        latest_simulation_entry = None
        for entry in workspace.prediction_ledger.entries:
            if entry.worker_id != (contract.worker_id if contract is not None else None):
                continue
            if entry.value_semantics != "observed_run_share":
                continue
            latest_simulation_entry = entry
        if latest_simulation_entry is not None and latest_simulation_entry.value is not None:
            try:
                if isinstance(latest_simulation_entry.value, dict):
                    numeric_values = [
                        float(value)
                        for value in latest_simulation_entry.value.values()
                        if isinstance(value, (int, float))
                    ]
                    if len(numeric_values) == 1:
                        return (numeric_values[0], 1)
                return (float(latest_simulation_entry.value), 1)
            except (TypeError, ValueError):
                return (None, 0)
        return (None, 0)

    def _load_simulation_numeric_payload(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        metric_id: Optional[str],
    ) -> tuple[dict[str, Any], int]:
        contract = workspace.simulation_worker_contract
        simulation_id = (
            (contract.simulation_id if contract is not None else None)
            or workspace.forecast_question.primary_simulation_id
        )
        ensemble_ids = list(contract.ensemble_ids) if contract is not None else []
        unit = _workspace_numeric_unit(workspace)
        if simulation_id and ensemble_ids and metric_id:
            for ensemble_id in ensemble_ids:
                state_path = os.path.join(
                    self.simulation_data_dir,
                    simulation_id,
                    "ensemble",
                    f"ensemble_{ensemble_id}",
                    "ensemble_state.json",
                )
                if not os.path.exists(state_path):
                    continue
                with open(state_path, "r", encoding="utf-8") as handle:
                    ensemble_state = json.load(handle)
                run_ids = list(ensemble_state.get("run_ids") or [])
                values: list[float] = []
                for run_id in run_ids:
                    metrics_path = os.path.join(
                        self.simulation_data_dir,
                        simulation_id,
                        "ensemble",
                        f"ensemble_{ensemble_id}",
                        "runs",
                        f"run_{run_id}",
                        "metrics.json",
                    )
                    if not os.path.exists(metrics_path):
                        continue
                    with open(metrics_path, "r", encoding="utf-8") as handle:
                        metrics_payload = json.load(handle)
                    metric_payload = metrics_payload.get("metric_values", {}).get(metric_id)
                    if not isinstance(metric_payload, dict) or metric_payload.get("value") is None:
                        continue
                    try:
                        values.append(float(metric_payload["value"]))
                    except (TypeError, ValueError):
                        continue
                if values:
                    return (
                        _build_numeric_interval_payload(
                            values,
                            unit=unit or (
                                str(metric_payload.get("unit")).strip()
                                if isinstance(metric_payload, dict) and metric_payload.get("unit")
                                else None
                            ),
                            interval_levels=_workspace_interval_levels(workspace),
                        ),
                        len(values),
                    )
        latest_simulation_entry = next(
            (
                entry
                for entry in reversed(workspace.prediction_ledger.entries)
                if entry.worker_id == (contract.worker_id if contract is not None else None)
            ),
            None,
        )
        if latest_simulation_entry is not None and isinstance(latest_simulation_entry.value, dict):
            payload = dict(latest_simulation_entry.value)
            point_estimate = payload.get("point_estimate", payload.get("value"))
            if point_estimate is not None:
                try:
                    payload["point_estimate"] = float(point_estimate)
                    payload["value"] = float(point_estimate)
                    if unit and "unit" not in payload:
                        payload["unit"] = unit
                    return (payload, 1)
                except (TypeError, ValueError):
                    pass
        return ({}, 0)

    def _load_simulation_distribution_payload(
        self,
        workspace: ForecastWorkspaceRecord,
    ) -> tuple[dict[str, float], int]:
        contract = workspace.simulation_worker_contract
        latest_simulation_entry = next(
            (
                entry
                for entry in reversed(workspace.prediction_ledger.entries)
                if entry.worker_id == (contract.worker_id if contract is not None else None)
            ),
            None,
        )
        if latest_simulation_entry is not None and isinstance(latest_simulation_entry.value, dict):
            value = latest_simulation_entry.value
            distribution = value.get("distribution")
            if isinstance(distribution, dict):
                normalized = _normalize_distribution(
                    distribution,
                    labels=_workspace_outcome_labels(workspace),
                )
                if normalized:
                    run_count = int(value.get("run_count") or value.get("sample_count") or 1)
                    return (normalized, run_count)
        return ({}, 0)

    def _build_answer_payload(
        self,
        workspace: ForecastWorkspaceRecord,
        worker_results: list[HybridWorkerResult],
        *,
        comparable_workspaces: Optional[list[ForecastWorkspaceRecord]] = None,
        analytics_context: Optional[dict[str, Any]] = None,
        ensemble_policy: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        question_type = _workspace_question_type(workspace)
        trace = [item.to_trace_item() for item in worker_results]
        evaluation_summary = self._build_evaluation_summary(
            workspace,
            comparable_workspaces=comparable_workspaces,
        )
        benchmark_summary = self._build_benchmark_summary(worker_results)
        backtest_summary = self._build_backtest_reference(
            workspace,
            evaluation_summary,
        )
        calibration_summary = self._build_calibration_reference(
            workspace,
            evaluation_summary,
            backtest_summary,
        )
        best_estimate_candidates = [
            item
            for item in worker_results
            if item.status == "completed"
            and item.influences_best_estimate
            and item.estimate is not None
        ]
        candidate_values = [
            item.estimate for item in best_estimate_candidates if item.estimate is not None
        ]
        disagreement_range = 0.0
        best_estimate = None
        abstain_reason = None
        drivers = _dedupe_strings(workspace.evidence_bundle.uncertainty_summary.get("drivers", []))
        cause_drivers = []
        for cause in workspace.evidence_bundle.uncertainty_summary.get("causes", []):
            if str(cause).strip() == "conflicting_evidence":
                cause_drivers.append("conflicting_evidence")
        drivers.extend(cause_drivers)
        has_conflicting_evidence = "conflicting_evidence" in drivers
        if question_type == "categorical":
            aggregate_weights: dict[str, float] = {}
            outcome_labels = _workspace_outcome_labels(workspace)
            worker_top_labels: list[str] = []
            winner_support_values: list[float] = []
            for item in best_estimate_candidates:
                if item.value_semantics != "forecast_distribution":
                    continue
                distribution = item.value.get("distribution") if isinstance(item.value, dict) else None
                if not isinstance(distribution, dict):
                    continue
                normalized_distribution = _normalize_distribution(
                    distribution,
                    labels=outcome_labels,
                )
                top_label = _top_distribution_label(normalized_distribution)
                if top_label:
                    worker_top_labels.append(top_label)
                for label, probability in normalized_distribution.items():
                    aggregate_weights[label] = aggregate_weights.get(label, 0.0) + (
                        float(probability) * max(float(item.effective_weight), 0.05)
                    )
            aggregate_distribution = _normalize_distribution(
                aggregate_weights,
                labels=outcome_labels,
            )
            top_label = _top_distribution_label(aggregate_distribution)
            if top_label is not None:
                for item in best_estimate_candidates:
                    if item.value_semantics != "forecast_distribution":
                        continue
                    distribution = item.value.get("distribution") if isinstance(item.value, dict) else None
                    if not isinstance(distribution, dict):
                        continue
                    normalized_distribution = _normalize_distribution(
                        distribution,
                        labels=outcome_labels,
                    )
                    winner_support_values.append(float(normalized_distribution.get(top_label, 0.0)))
            disagreement_range = (
                max(winner_support_values) - min(winner_support_values)
                if len(winner_support_values) > 1
                else 0.0
            )
            if len(set(worker_top_labels)) > 1 or disagreement_range >= 0.15:
                drivers.append("worker_disagreement")
            if not aggregate_distribution or top_label is None:
                abstain_reason = "insufficient_non_simulation_evidence"
            elif (
                disagreement_range > 0.35
                or (has_conflicting_evidence and disagreement_range > 0.25)
                or (
                    len(set(worker_top_labels)) > 1
                    and float(aggregate_distribution.get(top_label, 0.0)) < 0.45
                )
            ):
                abstain_reason = "worker_disagreement"
            if abstain_reason is None:
                sorted_labels = sorted(
                    aggregate_distribution.items(),
                    key=lambda item: (-float(item[1]), item[0]),
                )
                best_estimate = {
                    "value_type": "categorical_distribution",
                    "value_semantics": "forecast_distribution",
                    "semantics": "forecast_distribution",
                    "distribution": aggregate_distribution,
                    "top_label": top_label,
                    "top_label_share": round(float(aggregate_distribution.get(top_label, 0.0)), 6),
                    "rival_labels": [
                        {"label": label, "share": round(float(share), 6)}
                        for label, share in sorted_labels[1:4]
                    ],
                    "entropy": _distribution_entropy(aggregate_distribution),
                }
        elif question_type == "numeric":
            interval_levels = _workspace_interval_levels(workspace)
            unit = _workspace_numeric_unit(workspace)
            weighted_points = [
                (item.estimate, item.effective_weight)
                for item in best_estimate_candidates
                if item.estimate is not None
            ]
            point_estimate = _weighted_mean(weighted_points)
            disagreement_range = (
                max(candidate_values) - min(candidate_values)
                if len(candidate_values) > 1
                else 0.0
            )
            aggregate_intervals: dict[str, dict[str, float]] = {}
            average_interval_width = 0.0
            width_samples: list[float] = []
            for level in interval_levels:
                lower_values: list[tuple[float, float]] = []
                upper_values: list[tuple[float, float]] = []
                for item in best_estimate_candidates:
                    intervals = item.value.get("intervals") if isinstance(item.value, dict) else None
                    if not isinstance(intervals, dict):
                        continue
                    bounds = intervals.get(str(level))
                    if not isinstance(bounds, dict):
                        continue
                    try:
                        lower = float(bounds.get("low"))
                        upper = float(bounds.get("high"))
                    except (TypeError, ValueError):
                        continue
                    lower_values.append((lower, item.effective_weight))
                    upper_values.append((upper, item.effective_weight))
                lower = _weighted_mean(lower_values)
                upper = _weighted_mean(upper_values)
                if lower is None or upper is None:
                    continue
                aggregate_intervals[str(level)] = {
                    "low": round(float(lower), 6),
                    "high": round(float(upper), 6),
                }
                width_samples.append(max(0.0, float(upper) - float(lower)))
            if width_samples:
                average_interval_width = _mean(width_samples) or 0.0
            if len(candidate_values) > 1 and (
                disagreement_range > max(average_interval_width, 0.5)
            ):
                drivers.append("worker_disagreement")
            if point_estimate is None:
                abstain_reason = "insufficient_non_simulation_evidence"
            elif (
                disagreement_range > max(average_interval_width * 1.5, 1.0)
                or (has_conflicting_evidence and disagreement_range > max(average_interval_width, 0.5))
            ):
                abstain_reason = "worker_disagreement"
            if abstain_reason is None:
                best_estimate = {
                    "value_type": "numeric_interval",
                    "value_semantics": "numeric_interval_estimate",
                    "semantics": "numeric_interval_estimate",
                    "point_estimate": round(float(point_estimate), 6),
                    "value": round(float(point_estimate), 6),
                    "intervals": aggregate_intervals,
                    "average_interval_width": round(float(average_interval_width), 6),
                }
                if unit:
                    best_estimate["unit"] = unit
        else:
            disagreement_range = (
                max(candidate_values) - min(candidate_values)
                if len(candidate_values) > 1
                else 0.0
            )
            if len(candidate_values) > 1 and disagreement_range >= 0.1:
                drivers.append("worker_disagreement")
            if not best_estimate_candidates:
                abstain_reason = "insufficient_non_simulation_evidence"
            elif disagreement_range > 0.35 or (
                has_conflicting_evidence and disagreement_range > 0.25
            ):
                abstain_reason = "worker_disagreement"
            if abstain_reason is None:
                weighted = _weighted_mean(
                    [
                        (item.estimate, item.effective_weight)
                        for item in best_estimate_candidates
                        if item.estimate is not None
                    ]
                )
                if weighted is not None:
                    best_estimate = {
                        "estimate": round(float(weighted), 6),
                        "value": round(float(weighted), 6),
                        "value_type": "probability",
                        "value_semantics": "forecast_probability",
                        "semantics": "forecast_probability",
                    }

        drivers = _dedupe_strings(drivers)

        components = []
        for driver in drivers:
            if driver == "worker_disagreement":
                components.append(
                    {
                        "code": driver,
                        "magnitude": round(float(disagreement_range), 6),
                        "summary": (
                            "Non-simulation workers disagree meaningfully about the outcome distribution."
                            if question_type == "categorical"
                            else "Non-simulation workers disagree meaningfully about the numeric estimate."
                            if question_type == "numeric"
                            else "Non-simulation workers disagree meaningfully about the estimate."
                        ),
                    }
                )
            elif driver == "conflicting_evidence":
                components.append(
                    {
                        "code": driver,
                        "magnitude": 1.0,
                        "summary": "The bounded evidence bundle contains contradictory signals.",
                    }
                )
            else:
                components.append(
                    {
                        "code": driver,
                        "magnitude": 1.0,
                        "summary": f"Uncertainty remains elevated because of {driver.replace('_', ' ')}.",
                    }
                )

        abstain = abstain_reason is not None
        counterevidence = _dedupe_strings(
            list(workspace.evidence_bundle.conflict_summary.get("notes", []))
            + [
                marker.get("summary", "")
                for marker in workspace.evidence_bundle.conflict_markers
                if isinstance(marker, dict)
            ]
            + [
                item
                for result in worker_results
                for item in result.counterevidence
            ]
        )
        assumptions = _dedupe_strings(
            item
            for result in worker_results
            for item in result.assumptions
        )
        simulation_result = next(
            (item for item in worker_results if item.worker_kind == "simulation"),
            None,
        )
        simulation_market_result = next(
            (item for item in worker_results if item.worker_kind == "simulation_market"),
            None,
        )
        simulation_context = {
            "included": simulation_result is not None,
            "worker_id": simulation_result.worker_id if simulation_result is not None else None,
            "observed_run_share": (
                round(float(simulation_result.estimate), 6)
                if simulation_result is not None and simulation_result.estimate is not None
                else None
            ),
            "contribution_role": (
                simulation_result.contribution_role if simulation_result is not None else None
            ),
        }
        simulation_market_context = {
            "included": simulation_market_result is not None,
            "worker_id": (
                simulation_market_result.worker_id if simulation_market_result is not None else None
            ),
            "used_in_best_estimate": (
                simulation_market_result.influences_best_estimate
                if simulation_market_result is not None
                else False
            ),
            "provenance_status": (
                simulation_market_result.confidence_inputs.get("provenance_status")
                if simulation_market_result is not None
                else None
            ),
            "synthetic_consensus_probability": (
                simulation_market_result.value.get("synthetic_consensus_probability")
                if simulation_market_result is not None
                and isinstance(simulation_market_result.value, dict)
                else None
            ),
            "disagreement_index": (
                simulation_market_result.value.get("disagreement_index")
                if simulation_market_result is not None
                and isinstance(simulation_market_result.value, dict)
                else None
            ),
            "scenario_split_distribution": (
                simulation_market_result.value.get("scenario_split_distribution")
                if simulation_market_result is not None
                and isinstance(simulation_market_result.value, dict)
                else None
            ),
            "belief_momentum": (
                simulation_market_result.value.get("belief_momentum")
                if simulation_market_result is not None
                and isinstance(simulation_market_result.value, dict)
                else None
            ),
        }
        confidence_basis = self._build_confidence_basis(
            workspace=workspace,
            evaluation_summary=evaluation_summary,
            benchmark_summary=benchmark_summary,
            backtest_summary=backtest_summary,
            calibration_summary=calibration_summary,
            abstain=abstain,
            abstain_reason=abstain_reason,
        )

        return {
            "abstain": abstain,
            "abstained": abstain,
            "abstain_reason": abstain_reason,
            "best_estimate": best_estimate,
            "question_type": question_type,
            "evaluation_summary": evaluation_summary,
            "benchmark_summary": benchmark_summary,
            "backtest_summary": backtest_summary,
            "calibration_summary": calibration_summary,
            "confidence_basis": confidence_basis,
            "ensemble_policy": dict(ensemble_policy or {}),
            "analytics_context": dict(analytics_context or {}),
            "uncertainty_decomposition": {
                "drivers": drivers,
                "components": components,
                "disagreement_range": round(float(disagreement_range), 6),
            },
            "counterevidence": counterevidence,
            "assumption_summary": {
                "items": assumptions,
                "summary": assumptions[0] if assumptions else "",
            },
            "worker_contribution_trace": trace,
            "simulation_context": simulation_context,
            "simulation_market_context": simulation_market_context,
        }

    def _build_evaluation_summary(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        comparable_workspaces: Optional[list[ForecastWorkspaceRecord]] = None,
    ) -> dict[str, Any]:
        cases = list(workspace.evaluation_cases)
        for comparable in comparable_workspaces or []:
            if comparable.forecast_question.forecast_id == workspace.forecast_question.forecast_id:
                continue
            cases.extend(comparable.evaluation_cases)
        resolved_cases = [case for case in cases if case.status == "resolved"]
        pending_cases = [case for case in cases if case.status != "resolved"]
        question_classes = _dedupe_strings(
            item
            for case in cases
            for item in (
                case.question_class,
                case.comparable_question_class,
            )
            if item is not None
        )
        split_ids = _dedupe_strings(
            case.evaluation_split for case in cases if case.evaluation_split
        )
        window_ids = _dedupe_strings(case.window_id for case in cases if case.window_id)
        issued_at_values = [case.issued_at for case in cases if case.issued_at is not None]
        resolved_at_values = [case.resolved_at for case in resolved_cases if case.resolved_at]
        return {
            "status": "available" if resolved_cases else "partial" if cases else "unavailable",
            "case_count": len(cases),
            "resolved_case_count": len(resolved_cases),
            "pending_case_count": len(pending_cases),
            "case_ids": [case.case_id for case in resolved_cases],
            "question_classes": question_classes,
            "split_ids": split_ids,
            "window_ids": window_ids,
            "issue_timestamps": {
                "earliest": min(issued_at_values) if issued_at_values else None,
                "latest": max(issued_at_values) if issued_at_values else None,
            },
            "resolution_timestamps": {
                "earliest": min(resolved_at_values) if resolved_at_values else None,
                "latest": max(resolved_at_values) if resolved_at_values else None,
            },
            "references": {
                "evaluation_case_artifact": "evaluation_cases.json",
                "prediction_ledger_artifact": "prediction_ledger.json",
                "forecast_answer_artifact": "forecast_answers.json",
                "backtest_summary_artifact": None,
                "calibration_summary_artifact": None,
            },
        }

    def _build_benchmark_summary(
        self,
        worker_results: list[HybridWorkerResult],
    ) -> dict[str, Any]:
        completed = [
            item for item in worker_results if item.status == "completed" and item.estimate is not None
        ]
        ranked = sorted(completed, key=lambda item: (-float(item.effective_weight), item.worker_id))
        simulation = next((item for item in worker_results if item.worker_kind == "simulation"), None)
        non_simulation = [item for item in completed if item.worker_kind != "simulation"]
        return {
            "status": "available" if ranked else "unavailable",
            "worker_count": len(worker_results),
            "completed_worker_count": len(completed),
            "non_simulation_worker_count": len(non_simulation),
            "simulation_worker_count": 1 if simulation is not None else 0,
            "ranked_worker_ids": [item.worker_id for item in ranked],
            "best_estimate_worker_id": ranked[0].worker_id if ranked else None,
            "simulation_worker_id": simulation.worker_id if simulation is not None else None,
            "simulation_support_only": (
                simulation is not None and not simulation.influences_best_estimate
            ),
            "worker_estimates": [
                {
                    "worker_id": item.worker_id,
                    "worker_kind": item.worker_kind,
                    "estimate": round(float(item.estimate), 6)
                    if item.estimate is not None
                    else None,
                    "value": dict(item.value)
                    if isinstance(item.value, dict)
                    else item.value,
                    "value_type": item.value_type,
                    "value_semantics": item.value_semantics,
                    "effective_weight": round(float(item.effective_weight), 6),
                    "influences_best_estimate": item.influences_best_estimate,
                }
                for item in ranked
            ],
        }

    def _build_binary_backtest_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
    ) -> dict[str, Any]:
        metric_id, operator, threshold = _first_metric_threshold(workspace.resolution_criteria)
        case_results: list[dict[str, Any]] = []
        question_class_counts: dict[str, int] = {}
        comparable_class_counts: dict[str, int] = {}
        split_counts: dict[str, int] = {}
        warnings: list[str] = []
        positive_case_count = 0
        negative_case_count = 0
        for case in workspace.evaluation_cases:
            if case.status != "resolved":
                continue
            if case.question_class:
                question_class_counts[case.question_class] = question_class_counts.get(case.question_class, 0) + 1
            comparable_class = case.comparable_question_class or case.question_class
            if comparable_class:
                comparable_class_counts[comparable_class] = comparable_class_counts.get(comparable_class, 0) + 1
            if case.evaluation_split:
                split_counts[case.evaluation_split] = split_counts.get(case.evaluation_split, 0) + 1

            forecast_probability = _case_prediction_probability(case)
            observed_value = _extract_binary_outcome(
                case,
                metric_id=metric_id,
                operator=operator,
                threshold=threshold,
            )
            if forecast_probability is None or observed_value is None:
                if "degraded_case_records" not in warnings:
                    warnings.append("degraded_case_records")
                continue
            if observed_value >= 0.5:
                positive_case_count += 1
            else:
                negative_case_count += 1
            clipped_probability = min(
                max(float(forecast_probability), Config.CALIBRATION_LOG_SCORE_EPSILON),
                1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON,
            )
            clipped = clipped_probability != float(forecast_probability)
            case_warnings = []
            if clipped:
                case_warnings.append("probability_clipped_for_log_score")
            brier_score = (float(forecast_probability) - float(observed_value)) ** 2
            log_score = -(
                (float(observed_value) * math.log(clipped_probability))
                + ((1.0 - float(observed_value)) * math.log(1.0 - clipped_probability))
            )
            case_results.append(
                {
                    "case_id": case.case_id,
                    "forecast_probability": round(float(forecast_probability), 12),
                    "observed_value": bool(observed_value >= 0.5),
                    "scores": {
                        "brier_score": round(float(brier_score), 12),
                        "log_score": round(float(log_score), 12),
                    },
                    "score_inputs": {
                        "log_score_probability": round(float(clipped_probability), 12),
                        "probability_clipped": clipped,
                    },
                    "warnings": case_warnings,
                }
            )
        if not case_results:
            return {
                "status": "not_run",
                "reason": "No resolved binary evaluation cases carried explicit forecast probabilities.",
                "evaluation_case_count": evaluation_summary.get("case_count", 0),
                "resolved_case_count": evaluation_summary.get("resolved_case_count", 0),
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "binary",
                "references": evaluation_summary.get("references", {}),
            }
        observed_event_rate = positive_case_count / len(case_results)
        mean_forecast_probability = sum(
            float(item["forecast_probability"]) for item in case_results
        ) / len(case_results)
        mean_brier = _mean([item["scores"]["brier_score"] for item in case_results]) or 0.0
        mean_log = _mean([item["scores"]["log_score"] for item in case_results]) or 0.0
        scores = {
            "brier_score": round(float(mean_brier), 12),
            "log_score": round(float(mean_log), 12),
        }
        climatology_brier = observed_event_rate * (1.0 - observed_event_rate)
        if climatology_brier > 0:
            scores["brier_skill_score"] = round(
                float(1.0 - (mean_brier / climatology_brier)),
                12,
            )
        benchmark_probabilities = {
            "historical_base_rate": observed_event_rate,
            "uniform_50_50": 0.5,
        }
        benchmarks = {}
        for benchmark_id, benchmark_probability in benchmark_probabilities.items():
            benchmark_brier = _mean(
                [
                    (float(benchmark_probability) - (1.0 if item["observed_value"] else 0.0)) ** 2
                    for item in case_results
                ]
            ) or 0.0
            benchmark_log = _mean(
                [
                    -(
                        ((1.0 if item["observed_value"] else 0.0) * math.log(min(max(float(benchmark_probability), Config.CALIBRATION_LOG_SCORE_EPSILON), 1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON)))
                        + ((0.0 if item["observed_value"] else 1.0) * math.log(1.0 - min(max(float(benchmark_probability), Config.CALIBRATION_LOG_SCORE_EPSILON), 1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON)))
                    )
                    for item in case_results
                ]
            ) or 0.0
            benchmarks[benchmark_id] = {
                "forecast_probability": round(float(benchmark_probability), 12),
                "scores": {
                    "brier_score": round(float(benchmark_brier), 12),
                    "log_score": round(float(benchmark_log), 12),
                },
            }
        return {
            "status": "available",
            "question_type": "binary",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": len(case_results),
            "case_count": len(case_results),
            "positive_case_count": positive_case_count,
            "negative_case_count": negative_case_count,
            "observed_event_rate": round(float(observed_event_rate), 12),
            "mean_forecast_probability": round(float(mean_forecast_probability), 12),
            "scoring_rules": ["brier_score", "log_score"],
            "scores": scores,
            "benchmarks": benchmarks,
            "case_results": case_results,
            "question_class_counts": question_class_counts,
            "comparable_question_class_counts": comparable_class_counts,
            "split_counts": split_counts,
            "references": {
                **evaluation_summary.get("references", {}),
                "backtest_summary_artifact": "forecast_answer.backtest_summary",
            },
            "warnings": warnings,
        }

    def _build_categorical_backtest_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
    ) -> dict[str, Any]:
        outcome_labels = _workspace_outcome_labels(workspace)
        scored_cases: list[dict[str, Any]] = []
        observed_counts: dict[str, float] = {}
        question_class_counts: dict[str, int] = {}
        comparable_class_counts: dict[str, int] = {}
        split_counts: dict[str, int] = {}
        warnings: list[str] = []
        for case in workspace.evaluation_cases:
            if case.status != "resolved":
                continue
            observed_label = _extract_categorical_outcome(case, outcome_labels=outcome_labels)
            distribution = _case_prediction_distribution(case, outcome_labels=outcome_labels)
            if case.question_class:
                question_class_counts[case.question_class] = question_class_counts.get(case.question_class, 0) + 1
            comparable_class = case.comparable_question_class or case.question_class
            if comparable_class:
                comparable_class_counts[comparable_class] = comparable_class_counts.get(comparable_class, 0) + 1
            if case.evaluation_split:
                split_counts[case.evaluation_split] = split_counts.get(case.evaluation_split, 0) + 1
            if observed_label is not None:
                observed_counts[observed_label] = observed_counts.get(observed_label, 0.0) + 1.0
            if observed_label is None or not distribution:
                continue
            log_loss = _categorical_log_loss(distribution, observed_label)
            brier_score = _categorical_brier_score(distribution, observed_label)
            top_label = _top_distribution_label(distribution)
            scored_cases.append(
                {
                    "case_id": case.case_id,
                    "observed_label": observed_label,
                    "top_label": top_label,
                    "distribution": distribution,
                    "scores": {
                        "multiclass_log_loss": round(float(log_loss), 12)
                        if log_loss is not None
                        else None,
                        "multiclass_brier_score": round(float(brier_score), 12)
                        if brier_score is not None
                        else None,
                        "top1_accuracy": 1.0 if top_label == observed_label else 0.0,
                    },
                }
            )
        if not scored_cases:
            return {
                "status": "not_run",
                "reason": "No resolved categorical evaluation cases carried forecast distributions.",
                "evaluation_case_count": evaluation_summary.get("case_count", 0),
                "resolved_case_count": evaluation_summary.get("resolved_case_count", 0),
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "categorical",
                "references": evaluation_summary.get("references", {}),
            }
        observed_distribution = _normalize_distribution(observed_counts, labels=outcome_labels)
        mean_log_loss = _mean(
            [item["scores"]["multiclass_log_loss"] for item in scored_cases if item["scores"]["multiclass_log_loss"] is not None]
        )
        mean_brier = _mean(
            [item["scores"]["multiclass_brier_score"] for item in scored_cases if item["scores"]["multiclass_brier_score"] is not None]
        )
        mean_accuracy = _mean([item["scores"]["top1_accuracy"] for item in scored_cases])
        uniform_distribution = (
            _normalize_distribution({label: 1.0 for label in outcome_labels}, labels=outcome_labels)
            if outcome_labels
            else {}
        )
        comparable_label = max(comparable_class_counts, key=comparable_class_counts.get) if comparable_class_counts else None
        historical_baseline = observed_distribution
        benchmarks = {
            "historical_base_rate_distribution": {
                "distribution": historical_baseline,
                "top_label": _top_distribution_label(historical_baseline),
                "case_count": len(scored_cases),
                "scores": {
                    "multiclass_log_loss": round(
                        float(
                            _mean(
                                [
                                    _categorical_log_loss(historical_baseline, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    ),
                    "multiclass_brier_score": round(
                        float(
                            _mean(
                                [
                                    _categorical_brier_score(historical_baseline, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    ),
                },
            },
            "reference_class_distribution": {
                "distribution": historical_baseline,
                "top_label": _top_distribution_label(historical_baseline),
                "reference_class": comparable_label,
                "scores": {
                    "multiclass_log_loss": round(
                        float(
                            _mean(
                                [
                                    _categorical_log_loss(historical_baseline, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    ),
                    "multiclass_brier_score": round(
                        float(
                            _mean(
                                [
                                    _categorical_brier_score(historical_baseline, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    ),
                },
            },
            "uniform_distribution": {
                "distribution": uniform_distribution,
                "scores": {
                    "multiclass_log_loss": round(
                        float(
                            _mean(
                                [
                                    _categorical_log_loss(uniform_distribution, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    )
                    if uniform_distribution
                    else None,
                    "multiclass_brier_score": round(
                        float(
                            _mean(
                                [
                                    _categorical_brier_score(uniform_distribution, item["observed_label"])
                                    for item in scored_cases
                                ]
                            )
                            or 0.0
                        ),
                        12,
                    )
                    if uniform_distribution
                    else None,
                },
            },
        }
        if len(outcome_labels) < 2:
            warnings.append("limited_outcome_label_coverage")
        return {
            "status": "available",
            "question_type": "categorical",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": len(scored_cases),
            "scoring_rules": [
                "multiclass_log_loss",
                "multiclass_brier_score",
                "top1_accuracy",
            ],
            "scores": {
                "multiclass_log_loss": round(float(mean_log_loss), 12) if mean_log_loss is not None else None,
                "multiclass_brier_score": round(float(mean_brier), 12) if mean_brier is not None else None,
                "top1_accuracy": round(float(mean_accuracy), 12) if mean_accuracy is not None else None,
            },
            "benchmarks": benchmarks,
            "case_results": scored_cases,
            "question_class_counts": question_class_counts,
            "comparable_question_class_counts": comparable_class_counts,
            "split_counts": split_counts,
            "observed_distribution": observed_distribution,
            "references": {
                **evaluation_summary.get("references", {}),
                "backtest_summary_artifact": "forecast_answer.backtest_summary",
            },
            "warnings": warnings,
        }

    def _build_numeric_backtest_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
    ) -> dict[str, Any]:
        metric_id, _, _ = _first_metric_threshold(workspace.resolution_criteria)
        interval_levels = _workspace_interval_levels(workspace)
        unit = _workspace_numeric_unit(workspace)
        scored_cases: list[dict[str, Any]] = []
        observed_values: list[float] = []
        question_class_counts: dict[str, int] = {}
        comparable_class_counts: dict[str, int] = {}
        split_counts: dict[str, int] = {}
        persistence_candidates: list[tuple[float, float]] = []
        for case in workspace.evaluation_cases:
            if case.status != "resolved":
                continue
            observed_value = _extract_numeric_outcome(case, metric_id=metric_id)
            prediction_payload = _case_prediction_numeric_payload(case)
            point_estimate = prediction_payload.get("point_estimate")
            if case.question_class:
                question_class_counts[case.question_class] = question_class_counts.get(case.question_class, 0) + 1
            comparable_class = case.comparable_question_class or case.question_class
            if comparable_class:
                comparable_class_counts[comparable_class] = comparable_class_counts.get(comparable_class, 0) + 1
            if case.evaluation_split:
                split_counts[case.evaluation_split] = split_counts.get(case.evaluation_split, 0) + 1
            if observed_value is None or point_estimate is None:
                continue
            observed_values.append(observed_value)
            signed_error = float(point_estimate) - float(observed_value)
            absolute_error = abs(signed_error)
            case_result = {
                "case_id": case.case_id,
                "observed_value": round(float(observed_value), 6),
                "point_estimate": round(float(point_estimate), 6),
                "scores": {
                    "mae": round(float(absolute_error), 12),
                    "rmse": round(float((signed_error ** 2) ** 0.5), 12),
                    "signed_error": round(float(signed_error), 12),
                },
                "intervals": prediction_payload.get("intervals", {}),
            }
            for level in interval_levels:
                bounds = prediction_payload.get("intervals", {}).get(str(level))
                if isinstance(bounds, dict):
                    case_result["scores"][f"interval_coverage_{level}"] = (
                        1.0 if _numeric_interval_contains(bounds, observed_value) else 0.0
                    )
                    case_result["scores"][f"interval_width_{level}"] = round(
                        float(bounds["high"]) - float(bounds["low"]),
                        12,
                    )
            prior_observed_value = case.confidence_basis.get("prior_observed_value")
            if isinstance(prior_observed_value, (int, float)):
                persistence_candidates.append((float(prior_observed_value), observed_value))
            scored_cases.append(case_result)
        if not scored_cases:
            return {
                "status": "not_run",
                "reason": "No resolved numeric evaluation cases carried typed prediction payloads.",
                "evaluation_case_count": evaluation_summary.get("case_count", 0),
                "resolved_case_count": evaluation_summary.get("resolved_case_count", 0),
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "numeric",
                "references": evaluation_summary.get("references", {}),
            }
        scores: dict[str, float] = {
            "mae": round(
                float(_mean([item["scores"]["mae"] for item in scored_cases]) or 0.0),
                12,
            ),
            "rmse": round(
                math.sqrt(
                    float(
                        _mean(
                            [
                                item["scores"]["signed_error"] ** 2
                                for item in scored_cases
                            ]
                        )
                        or 0.0
                    )
                ),
                12,
            ),
            "signed_error": round(
                float(_mean([item["scores"]["signed_error"] for item in scored_cases]) or 0.0),
                12,
            ),
        }
        for level in interval_levels:
            coverage_values = [
                item["scores"][f"interval_coverage_{level}"]
                for item in scored_cases
                if f"interval_coverage_{level}" in item["scores"]
            ]
            width_values = [
                item["scores"][f"interval_width_{level}"]
                for item in scored_cases
                if f"interval_width_{level}" in item["scores"]
            ]
            if coverage_values:
                scores[f"interval_coverage_{level}"] = round(
                    float(_mean(coverage_values) or 0.0),
                    12,
                )
            if width_values:
                scores[f"interval_width_{level}"] = round(
                    float(_mean(width_values) or 0.0),
                    12,
                )
        observed_median = _quantile(observed_values, 0.5) or 0.0
        historical_benchmark_scores = {
            "mae": round(
                float(_mean([abs(observed_median - item["observed_value"]) for item in scored_cases]) or 0.0),
                12,
            ),
            "rmse": round(
                math.sqrt(
                    float(
                        _mean(
                            [
                                (observed_median - item["observed_value"]) ** 2
                                for item in scored_cases
                            ]
                        )
                        or 0.0
                    )
                ),
                12,
            ),
        }
        reference_class = max(comparable_class_counts, key=comparable_class_counts.get) if comparable_class_counts else None
        persistence_scores = {}
        if persistence_candidates:
            persistence_errors = [
                abs(predicted - observed)
                for predicted, observed in persistence_candidates
            ]
            persistence_scores = {
                "mae": round(float(_mean(persistence_errors) or 0.0), 12),
                "rmse": round(
                    math.sqrt(
                        float(
                            _mean(
                                [
                                    (predicted - observed) ** 2
                                    for predicted, observed in persistence_candidates
                                ]
                            )
                            or 0.0
                        )
                    ),
                    12,
                ),
            }
        return {
            "status": "available",
            "question_type": "numeric",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": len(scored_cases),
            "scoring_rules": [
                "mae",
                "rmse",
                "signed_error",
                *[
                    f"interval_coverage_{level}"
                    for level in interval_levels
                ],
                *[
                    f"interval_width_{level}"
                    for level in interval_levels
                ],
            ],
            "scores": scores,
            "benchmarks": {
                "historical_median": {
                    "value": round(float(observed_median), 6),
                    "scores": historical_benchmark_scores,
                },
                "reference_class_baseline": {
                    "value": round(float(observed_median), 6),
                    "reference_class": reference_class,
                    "scores": historical_benchmark_scores,
                },
                "persistence_baseline": {
                    "scores": persistence_scores,
                    "available": bool(persistence_scores),
                },
            },
            "case_results": scored_cases,
            "question_class_counts": question_class_counts,
            "comparable_question_class_counts": comparable_class_counts,
            "split_counts": split_counts,
            "interval_levels": interval_levels,
            "unit": unit,
            "references": {
                **evaluation_summary.get("references", {}),
                "backtest_summary_artifact": "forecast_answer.backtest_summary",
            },
            "warnings": [],
        }

    def _build_binary_calibration_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
        backtest_summary: dict[str, Any],
    ) -> dict[str, Any]:
        if backtest_summary.get("status") not in {"available", "ready"}:
            return {
                "status": "not_applicable",
                "reason": "Binary calibration requires scored workspace backtest results.",
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "binary",
            }
        case_results = list(backtest_summary.get("case_results") or [])
        bin_count = max(int(Config.CALIBRATION_BIN_COUNT), 1)
        buckets: list[list[dict[str, Any]]] = [[] for _ in range(bin_count)]
        for case_result in case_results:
            probability = float(case_result.get("forecast_probability") or 0.0)
            bucket_index = min(int(probability * bin_count), bin_count - 1)
            buckets[bucket_index].append(case_result)
        reliability_bins: list[dict[str, Any]] = []
        weighted_gaps: list[float] = []
        absolute_gaps: list[float] = []
        for index, bucket in enumerate(buckets):
            lower_bound = index / bin_count
            upper_bound = (index + 1) / bin_count
            if bucket:
                mean_probability = _mean(
                    [float(item.get("forecast_probability") or 0.0) for item in bucket]
                )
                observed_frequency = _mean(
                    [1.0 if item.get("observed_value") else 0.0 for item in bucket]
                )
                gap = abs(float(observed_frequency or 0.0) - float(mean_probability or 0.0))
                weighted_gaps.append((len(bucket) / max(len(case_results), 1)) * gap)
                absolute_gaps.append(gap)
            else:
                mean_probability = None
                observed_frequency = None
            reliability_bins.append(
                {
                    "bin_index": index,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "case_count": len(bucket),
                    "mean_forecast_probability": mean_probability,
                    "observed_frequency": observed_frequency,
                    "observed_minus_forecast": (
                        float(observed_frequency) - float(mean_probability)
                        if observed_frequency is not None and mean_probability is not None
                        else None
                    ),
                }
            )
        positive_case_count = int(backtest_summary.get("positive_case_count") or 0)
        negative_case_count = int(backtest_summary.get("negative_case_count") or 0)
        supported_bin_count = sum(1 for item in reliability_bins if item["case_count"] > 0)
        gating_reasons: list[str] = []
        if len(case_results) < Config.CALIBRATION_MIN_CASE_COUNT:
            gating_reasons.append("insufficient_case_count")
        if positive_case_count < Config.CALIBRATION_MIN_POSITIVE_CASE_COUNT:
            gating_reasons.append("insufficient_positive_case_count")
        if negative_case_count < Config.CALIBRATION_MIN_NEGATIVE_CASE_COUNT:
            gating_reasons.append("insufficient_negative_case_count")
        if supported_bin_count < Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT:
            gating_reasons.append("insufficient_supported_bin_count")
        if not backtest_summary.get("scoring_rules"):
            gating_reasons.append("missing_supported_scores")
        ready = not gating_reasons
        return {
            "status": "ready" if ready else "available",
            "question_type": "binary",
            "calibration_kind": "binary_reliability",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": len(case_results),
            "supported_scoring_rules": list(backtest_summary.get("scoring_rules") or []),
            "readiness": {
                "ready": ready,
                "actual_case_count": len(case_results),
                "minimum_case_count": Config.CALIBRATION_MIN_CASE_COUNT,
                "minimum_positive_case_count": Config.CALIBRATION_MIN_POSITIVE_CASE_COUNT,
                "actual_positive_case_count": positive_case_count,
                "minimum_negative_case_count": Config.CALIBRATION_MIN_NEGATIVE_CASE_COUNT,
                "actual_negative_case_count": negative_case_count,
                "supported_bin_count": supported_bin_count,
                "minimum_supported_bin_count": Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT,
                "gating_reasons": gating_reasons,
                "confidence_label": _determine_confidence_label(
                    ready=ready,
                    case_count=len(case_results),
                ),
            },
            "reliability_bins": reliability_bins,
            "diagnostics": {
                "expected_calibration_error": round(float(sum(weighted_gaps)), 12),
                "max_calibration_gap": round(float(max(absolute_gaps or [0.0])), 12),
                "observed_event_rate": backtest_summary.get("observed_event_rate"),
                "mean_forecast_probability": backtest_summary.get("mean_forecast_probability"),
            },
            "boundary_note": (
                "Binary calibration is earned from resolved workspace probabilities and reliability diagnostics."
            ),
            "warnings": list(backtest_summary.get("warnings") or []),
        }

    def _build_categorical_calibration_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
        backtest_summary: dict[str, Any],
    ) -> dict[str, Any]:
        if backtest_summary.get("status") not in {"available", "ready"}:
            return {
                "status": "not_applicable",
                "reason": "Categorical calibration requires scored workspace backtest results.",
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "categorical",
            }
        case_results = list(backtest_summary.get("case_results") or [])
        bins: list[dict[str, Any]] = []
        bin_count = max(int(Config.CALIBRATION_BIN_COUNT), 1)
        buckets: list[list[dict[str, Any]]] = [[] for _ in range(bin_count)]
        observed_labels: set[str] = set()
        for case_result in case_results:
            top_label = str(case_result.get("top_label") or "").strip()
            observed_label = str(case_result.get("observed_label") or "").strip()
            distribution = case_result.get("distribution") or {}
            if not top_label or not isinstance(distribution, dict):
                continue
            top_confidence = float(distribution.get(top_label, 0.0))
            bucket_index = min(int(top_confidence * bin_count), bin_count - 1)
            buckets[bucket_index].append(case_result)
            if observed_label:
                observed_labels.add(observed_label)
        weighted_gaps: list[float] = []
        total_case_count = len(case_results)
        for bin_index, bucket in enumerate(buckets):
            lower_bound = bin_index / bin_count
            upper_bound = (bin_index + 1) / bin_count
            if bucket:
                mean_confidence = _mean(
                    [
                        float(item["distribution"].get(item["top_label"], 0.0))
                        for item in bucket
                    ]
                )
                observed_frequency = _mean(
                    [
                        1.0 if item.get("top_label") == item.get("observed_label") else 0.0
                        for item in bucket
                    ]
                )
                gap = abs(float(observed_frequency or 0.0) - float(mean_confidence or 0.0))
                weighted_gaps.append((len(bucket) / max(total_case_count, 1)) * gap)
            else:
                mean_confidence = None
                observed_frequency = None
                gap = None
            bins.append(
                {
                    "bin_index": bin_index,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                    "case_count": len(bucket),
                    "mean_top_label_confidence": mean_confidence,
                    "observed_top_label_accuracy": observed_frequency,
                    "observed_minus_forecast": (
                        float(observed_frequency) - float(mean_confidence)
                        if observed_frequency is not None and mean_confidence is not None
                        else None
                    ),
                }
            )
        unique_top_labels = {
            str(item.get("top_label") or "").strip()
            for item in case_results
            if str(item.get("top_label") or "").strip()
        }
        gating_reasons: list[str] = []
        if total_case_count < Config.CALIBRATION_MIN_CASE_COUNT:
            gating_reasons.append("insufficient_case_count")
        if len(observed_labels) < 2:
            gating_reasons.append("insufficient_class_coverage")
        if len(unique_top_labels) < 2:
            gating_reasons.append("degenerate_top_label_support")
        non_empty_bin_count = sum(1 for item in bins if item["case_count"] > 0)
        if non_empty_bin_count < Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT:
            gating_reasons.append("insufficient_supported_bin_count")
        ready = not gating_reasons
        classwise_accuracy: dict[str, Any] = {}
        for label in sorted(observed_labels):
            label_cases = [
                item for item in case_results if item.get("observed_label") == label
            ]
            if len(label_cases) < 2:
                continue
            classwise_accuracy[label] = {
                "case_count": len(label_cases),
                "top_label_accuracy": round(
                    float(
                        _mean(
                            [
                                1.0 if item.get("top_label") == label else 0.0
                                for item in label_cases
                            ]
                        )
                        or 0.0
                    ),
                    12,
                ),
            }
        return {
            "status": "ready" if ready else "available",
            "question_type": "categorical",
            "calibration_kind": "categorical_distribution",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": total_case_count,
            "readiness": {
                "ready": ready,
                "actual_case_count": total_case_count,
                "minimum_case_count": Config.CALIBRATION_MIN_CASE_COUNT,
                "observed_class_count": len(observed_labels),
                "top_label_count": len(unique_top_labels),
                "supported_bin_count": non_empty_bin_count,
                "minimum_supported_bin_count": Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT,
                "gating_reasons": gating_reasons,
            },
            "top_label_reliability_bins": bins,
            "diagnostics": {
                "expected_calibration_error": round(float(sum(weighted_gaps)), 12),
                "max_calibration_gap": round(
                    float(max((abs(item["observed_minus_forecast"]) for item in bins if item["observed_minus_forecast"] is not None), default=0.0)),
                    12,
                ),
                "classwise_accuracy": classwise_accuracy,
            },
            "boundary_note": (
                "Categorical calibration is earned from resolved labeled outcomes and top-label reliability, not from binary-only shortcuts."
            ),
            "warnings": [],
        }

    def _build_numeric_calibration_summary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
        backtest_summary: dict[str, Any],
    ) -> dict[str, Any]:
        if backtest_summary.get("status") not in {"available", "ready"}:
            return {
                "status": "not_applicable",
                "reason": "Numeric calibration requires scored workspace backtest results.",
                "workspace_forecast_id": workspace.forecast_question.forecast_id,
                "question_type": "numeric",
            }
        case_results = list(backtest_summary.get("case_results") or [])
        interval_levels = list(backtest_summary.get("interval_levels") or _workspace_interval_levels(workspace))
        coverage_by_level: dict[str, float] = {}
        width_by_level: dict[str, float] = {}
        gating_reasons: list[str] = []
        total_case_count = len(case_results)
        if total_case_count < Config.CALIBRATION_MIN_CASE_COUNT:
            gating_reasons.append("insufficient_case_count")
        if not interval_levels:
            gating_reasons.append("missing_interval_levels")
        for level in interval_levels:
            coverage_values = [
                item["scores"][f"interval_coverage_{level}"]
                for item in case_results
                if f"interval_coverage_{level}" in item.get("scores", {})
            ]
            width_values = [
                item["scores"][f"interval_width_{level}"]
                for item in case_results
                if f"interval_width_{level}" in item.get("scores", {})
            ]
            if not coverage_values:
                gating_reasons.append(f"missing_interval_{level}")
                continue
            coverage_by_level[str(level)] = round(float(_mean(coverage_values) or 0.0), 12)
            width_by_level[str(level)] = round(float(_mean(width_values) or 0.0), 12) if width_values else 0.0
            if width_values and all(float(value) <= 0 for value in width_values):
                gating_reasons.append(f"degenerate_interval_{level}")
        ready = not gating_reasons
        nominal_coverage = {str(level): level / 100.0 for level in interval_levels}
        return {
            "status": "ready" if ready else "available",
            "question_type": "numeric",
            "calibration_kind": "numeric_interval",
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": total_case_count,
            "readiness": {
                "ready": ready,
                "actual_case_count": total_case_count,
                "minimum_case_count": Config.CALIBRATION_MIN_CASE_COUNT,
                "supported_interval_levels": interval_levels,
                "gating_reasons": gating_reasons,
            },
            "interval_calibration": {
                "nominal_coverage": nominal_coverage,
                "observed_coverage": coverage_by_level,
                "average_interval_width": width_by_level,
            },
            "diagnostics": {
                "mean_signed_error": backtest_summary.get("scores", {}).get("signed_error"),
                "mae": backtest_summary.get("scores", {}).get("mae"),
                "rmse": backtest_summary.get("scores", {}).get("rmse"),
            },
            "boundary_note": (
                "Numeric calibration is earned from interval coverage and error diagnostics, not from binary reliability bins."
            ),
            "warnings": [],
        }

    def _build_backtest_reference(
        self,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
    ) -> dict[str, Any]:
        question_type = _workspace_question_type(workspace)
        if question_type == "binary":
            return self._build_binary_backtest_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
            )
        if question_type == "categorical":
            return self._build_categorical_backtest_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
            )
        if question_type == "numeric":
            return self._build_numeric_backtest_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
            )
        return {
            "status": "not_run",
            "reason": "No workspace-level backtest artifact is generated in the forecast engine.",
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": evaluation_summary.get("resolved_case_count", 0),
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
            "references": evaluation_summary.get("references", {}),
        }

    def _build_calibration_reference(
        self,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
        backtest_summary: dict[str, Any],
    ) -> dict[str, Any]:
        question_type = _workspace_question_type(workspace)
        if question_type == "binary":
            return self._build_binary_calibration_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
                backtest_summary=backtest_summary,
            )
        if question_type == "categorical":
            return self._build_categorical_calibration_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
                backtest_summary=backtest_summary,
            )
        if question_type == "numeric":
            return self._build_numeric_calibration_summary(
                workspace=workspace,
                evaluation_summary=evaluation_summary,
                backtest_summary=backtest_summary,
            )
        return {
            "status": "not_applicable",
            "reason": (
                "Forecast-workspace evaluation cases are tracked separately from the binary simulation backtest/calibration lane."
            ),
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": evaluation_summary.get("resolved_case_count", 0),
            "workspace_forecast_id": workspace.forecast_question.forecast_id,
        }

    def _build_confidence_basis(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        evaluation_summary: dict[str, Any],
        benchmark_summary: dict[str, Any],
        backtest_summary: dict[str, Any],
        calibration_summary: dict[str, Any],
        abstain: bool,
        abstain_reason: Optional[str],
    ) -> dict[str, Any]:
        resolved_case_count = int(evaluation_summary.get("resolved_case_count", 0) or 0)
        status = "unavailable"
        if resolved_case_count > 0:
            status = "available"
        if abstain:
            status = "abstained"
        question_type = _workspace_question_type(workspace)
        if (
            not abstain
            and question_type in {"binary", "categorical", "numeric"}
            and calibration_summary.get("status") == "ready"
            and backtest_summary.get("status") in {"available", "ready"}
            and benchmark_summary.get("status") == "available"
            and resolved_case_count > 0
        ):
            status = "available"
        return {
            "status": status,
            "question_type": question_type,
            "evaluation_case_count": evaluation_summary.get("case_count", 0),
            "resolved_case_count": resolved_case_count,
            "benchmark_status": benchmark_summary.get("status", "unavailable"),
            "backtest_status": backtest_summary.get("status", "not_run"),
            "calibration_status": calibration_summary.get("status", "not_applicable"),
            "abstain_reason": abstain_reason,
            "note": (
                "Typed workspace evaluation and calibration metadata support this answer."
                if (
                    question_type in {"binary", "categorical", "numeric"}
                    and calibration_summary.get("status") == "ready"
                    and resolved_case_count > 0
                )
                else "Workspace evaluation is present, but no calibration claim is made."
                if resolved_case_count > 0
                else "No resolved workspace evaluation cases are available."
            ),
        }

    def _build_answer_summary(self, answer_payload: dict[str, Any]) -> str:
        if answer_payload["abstain"]:
            return (
                "Abstained: insufficient non-simulation evidence for a defended hybrid estimate. "
                "Simulation contributes supporting scenario evidence only."
                if answer_payload["abstain_reason"] == "insufficient_non_simulation_evidence"
                else "Abstained: non-simulation workers disagree too widely for a defended hybrid estimate. Simulation contributes supporting scenario evidence only."
            )
        best_estimate = answer_payload["best_estimate"] or {}
        question_type = answer_payload.get("question_type", "binary")
        evaluation_note = ""
        if answer_payload.get("evaluation_summary", {}).get("resolved_case_count", 0):
            evaluation_note = " Workspace evaluation cases are tracked separately."
        if answer_payload.get("calibration_summary", {}).get("status") == "ready":
            evaluation_note += " This answer carries ready backtest and calibration support."
        if question_type == "categorical":
            return (
                f"Hybrid outcome distribution favors {best_estimate.get('top_label') or 'an unresolved label'} "
                "from non-simulation workers. Simulation contributes supporting scenario evidence only."
                f"{evaluation_note}"
            )
        if question_type == "numeric":
            point_estimate = best_estimate.get("point_estimate")
            unit = str(best_estimate.get("unit") or "").strip()
            unit_suffix = f" {unit}" if unit else ""
            return (
                f"Hybrid numeric estimate {point_estimate}{unit_suffix} from non-simulation workers. "
                "Simulation contributes supporting scenario evidence only."
                f"{evaluation_note}"
            )
        estimate = best_estimate["estimate"]
        return (
            f"Hybrid estimate {estimate:.2f} from non-simulation workers. "
            "Simulation contributes supporting scenario evidence only."
            f"{evaluation_note}"
        )

    def _build_answer_notes(self, answer_payload: dict[str, Any]) -> list[str]:
        notes = [
            "Simulation contributes supporting scenario evidence only and does not determine the best estimate.",
        ]
        if answer_payload["abstain"]:
            notes.append(
                "The hybrid path abstained because simulation scenario evidence only or internally inconsistent non-simulation signals were available."
            )
        ensemble_policy = answer_payload.get("ensemble_policy") or {}
        if ensemble_policy.get("policy_name"):
            notes.append(
                "Best-estimate worker weights were tuned by worker family, question type, and current evidence regime."
            )
        if answer_payload.get("question_type") == "categorical":
            notes.append(
                "Categorical forecasts stay explicit about named outcome distributions and do not collapse into one percentage estimate."
            )
        if answer_payload.get("question_type") == "numeric":
            notes.append(
                "Numeric forecasts stay explicit about units and intervals and do not collapse into binary threshold semantics."
            )
        return notes

    def _build_prediction_entries(
        self,
        workspace: ForecastWorkspaceRecord,
        worker_results: list[HybridWorkerResult],
        recorded_at: str,
        *,
        answer_payload: dict[str, Any],
    ) -> list[PredictionLedgerEntry]:
        entries: list[PredictionLedgerEntry] = []
        active_bundle_id = workspace.evidence_bundle.bundle_id
        evaluation_case_ids = list(
            answer_payload.get("evaluation_summary", {}).get("case_ids", [])
        )
        for result in worker_results:
            if result.status != "completed" or (result.estimate is None and result.value is None):
                continue
            latest_entry = next(
                (
                    entry
                    for entry in reversed(workspace.prediction_ledger.entries)
                    if entry.worker_id == result.worker_id
                    and entry.metadata.get("generated_by_engine")
                ),
                None,
            )
            prediction_id = (
                latest_entry.prediction_id
                if latest_entry is not None
                else f"{result.worker_id}-prediction"
            )
            entry_id = f"{result.worker_id}-entry-{_compact_timestamp(recorded_at)}"
            entry = PredictionLedgerEntry(
                entry_id=entry_id,
                forecast_id=workspace.forecast_question.forecast_id,
                worker_id=result.worker_id,
                recorded_at=recorded_at,
                value_type=result.value_type,
                value=result.value if result.value is not None else result.estimate,
                prediction=result.value if result.value is not None else result.estimate,
                value_semantics=result.value_semantics,
                prediction_id=prediction_id,
                revision_number=(latest_entry.revision_number + 1) if latest_entry is not None else 1,
                entry_kind="revision" if latest_entry is not None else "issue",
                revises_prediction_id=latest_entry.entry_id if latest_entry is not None else None,
                revises_entry_id=latest_entry.entry_id if latest_entry is not None else None,
                worker_output_ids=[result.output_id],
                calibration_state="not_applicable" if result.worker_kind == "simulation" else "uncalibrated",
                evaluation_case_ids=evaluation_case_ids,
                evaluation_summary=answer_payload["evaluation_summary"],
                benchmark_summary=answer_payload["benchmark_summary"],
                backtest_summary_ref=answer_payload["backtest_summary"]["status"],
                calibration_summary_ref=answer_payload["calibration_summary"]["status"],
                confidence_basis=answer_payload["confidence_basis"],
                evidence_bundle_ids=[active_bundle_id] if active_bundle_id else [],
                notes=list(result.notes),
                metadata={
                    "generated_by_engine": True,
                    "worker_kind": result.worker_kind,
                    "contribution_role": result.contribution_role,
                    "evaluation_summary": answer_payload["evaluation_summary"],
                    "benchmark_summary": answer_payload["benchmark_summary"],
                    "confidence_basis": answer_payload["confidence_basis"],
                    "generated_value": (
                        dict(result.value) if isinstance(result.value, dict) else result.value
                    ),
                },
                final_resolution_state="pending",
            )
            entries.append(entry)
        return entries
