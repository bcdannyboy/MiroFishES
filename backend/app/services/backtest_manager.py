"""
Backtesting manager for persisted calibration case registries.

This slice is intentionally conservative:
- it only scores explicit observed-truth cases already on disk,
- it supports proper scoring for binary metrics only,
- it persists raw empirical scoring separately from any calibration summary.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from typing import Any, Dict, List

from ..config import Config
from ..models.probabilistic import (
    BacktestCaseResult,
    BacktestSummary,
    MetricBacktestSummary,
    ObservedTruthRegistry,
    build_supported_outcome_metric,
)


class BacktestManager:
    """Persist and score explicit historical-case registries."""

    OBSERVED_TRUTH_REGISTRY_FILENAME = "observed_truth_registry.json"
    BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"

    def __init__(self, simulation_data_dir: str | None = None) -> None:
        self.simulation_data_dir = (
            simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        )

    def persist_observed_truth_registry(
        self,
        simulation_id: str,
        ensemble_id: str,
        registry: ObservedTruthRegistry | Dict[str, Any],
    ) -> Dict[str, Any]:
        if isinstance(registry, dict):
            registry = ObservedTruthRegistry.from_dict(registry)
        payload = registry.to_dict()
        self._write_json(
            os.path.join(
                self._get_ensemble_dir(simulation_id, ensemble_id),
                self.OBSERVED_TRUTH_REGISTRY_FILENAME,
            ),
            payload,
        )
        return payload

    def load_observed_truth_registry(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        registry_path = os.path.join(
            self._get_ensemble_dir(simulation_id, ensemble_id),
            self.OBSERVED_TRUTH_REGISTRY_FILENAME,
        )
        if not os.path.exists(registry_path):
            raise ValueError(
                f"Observed truth registry does not exist for simulation {simulation_id}, ensemble {ensemble_id}"
            )
        return self._read_json(registry_path)

    def get_backtest_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        registry = ObservedTruthRegistry.from_dict(
            self.load_observed_truth_registry(simulation_id, ensemble_id)
        )
        summary = self._build_backtest_summary(registry)
        payload = summary.to_dict()
        self._write_json(
            os.path.join(
                self._get_ensemble_dir(simulation_id, ensemble_id),
                self.BACKTEST_SUMMARY_FILENAME,
            ),
            payload,
        )
        return payload

    def load_backtest_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        summary_path = os.path.join(
            self._get_ensemble_dir(simulation_id, ensemble_id),
            self.BACKTEST_SUMMARY_FILENAME,
        )
        if not os.path.exists(summary_path):
            raise ValueError(
                f"Backtest summary does not exist for simulation {simulation_id}, ensemble {ensemble_id}"
            )
        return self._read_json(summary_path)

    def _build_backtest_summary(
        self,
        registry: ObservedTruthRegistry,
    ) -> BacktestSummary:
        grouped_cases: Dict[str, List[Any]] = defaultdict(list)
        for case in registry.cases:
            grouped_cases[case.metric_id].append(case)

        metric_backtests: Dict[str, MetricBacktestSummary] = {}
        warnings: List[str] = []
        scored_case_total = 0
        skipped_case_total = 0
        supported_metric_ids: List[str] = []
        unscored_metric_ids: List[str] = []

        for metric_id, cases in sorted(grouped_cases.items()):
            metric = build_supported_outcome_metric(metric_id)
            metric_warnings: List[str] = []

            if (
                metric.value_kind != "binary"
                or metric.confidence_support.get("backtesting_supported") is not True
            ):
                metric_warnings.append("unsupported_confidence_contract")
                if "unsupported_metrics_present" not in warnings:
                    warnings.append("unsupported_metrics_present")
                unscored_metric_ids.append(metric_id)
                metric_backtests[metric_id] = MetricBacktestSummary(
                    metric_id=metric_id,
                    value_kind=metric.value_kind,
                    case_count=0,
                    positive_case_count=0,
                    negative_case_count=0,
                    observed_event_rate=None,
                    mean_forecast_probability=None,
                    scoring_rules=[],
                    case_results=[],
                    scores={},
                    warnings=metric_warnings,
                )
                continue

            supported_metric_ids.append(metric_id)
            case_results: List[BacktestCaseResult] = []
            positive_case_count = 0
            negative_case_count = 0
            for case in cases:
                if case.forecast_probability is None:
                    if "missing_forecast_probability" not in metric_warnings:
                        metric_warnings.append("missing_forecast_probability")
                    skipped_case_total += 1
                    continue

                observed_value = 1.0 if case.observed_value else 0.0
                if case.observed_value:
                    positive_case_count += 1
                else:
                    negative_case_count += 1
                probability = float(case.forecast_probability)
                brier_score = (probability - observed_value) ** 2
                clipped_probability = min(
                    max(probability, Config.CALIBRATION_LOG_SCORE_EPSILON),
                    1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON,
                )
                clipped = clipped_probability != probability
                log_score = -(
                    (observed_value * math.log(clipped_probability))
                    + ((1.0 - observed_value) * math.log(1.0 - clipped_probability))
                )

                case_warnings = []
                if clipped:
                    case_warnings.append("probability_clipped_for_log_score")

                case_results.append(
                    BacktestCaseResult(
                        case_id=case.case_id,
                        metric_id=metric_id,
                        forecast_probability=probability,
                        observed_value=bool(case.observed_value),
                        scores={
                            "brier_score": brier_score,
                            "log_score": log_score,
                        },
                        score_inputs={
                            "log_score_probability": clipped_probability,
                            "probability_clipped": clipped,
                        },
                        warnings=case_warnings,
                    )
                )

            if len(case_results) < len(cases):
                if "degraded_case_records" not in warnings:
                    warnings.append("degraded_case_records")

            scores: Dict[str, float] = {}
            observed_event_rate = None
            mean_forecast_probability = None
            if case_results:
                scored_case_total += len(case_results)
                for score_name in ("brier_score", "log_score"):
                    scores[score_name] = sum(
                        result.scores[score_name] for result in case_results
                    ) / len(case_results)
                observed_event_rate = positive_case_count / len(case_results)
                mean_forecast_probability = sum(
                    result.forecast_probability for result in case_results
                ) / len(case_results)
                climatology_brier = observed_event_rate * (1.0 - observed_event_rate)
                if climatology_brier > 0:
                    scores["brier_skill_score"] = 1.0 - (
                        scores["brier_score"] / climatology_brier
                    )
                else:
                    if "degenerate_base_rate_baseline" not in metric_warnings:
                        metric_warnings.append("degenerate_base_rate_baseline")
            else:
                unscored_metric_ids.append(metric_id)

            metric_backtests[metric_id] = MetricBacktestSummary(
                metric_id=metric_id,
                value_kind=metric.value_kind,
                case_count=len(case_results),
                positive_case_count=positive_case_count,
                negative_case_count=negative_case_count,
                observed_event_rate=observed_event_rate,
                mean_forecast_probability=mean_forecast_probability,
                scoring_rules=["brier_score", "log_score"] if case_results else [],
                case_results=case_results,
                scores=scores,
                warnings=metric_warnings,
            )

        return BacktestSummary(
            simulation_id=registry.simulation_id,
            ensemble_id=registry.ensemble_id,
            metric_backtests=metric_backtests,
            quality_summary={
                "status": "partial" if warnings else "complete",
                "warnings": warnings,
                "total_case_count": len(registry.cases),
                "scored_case_count": scored_case_total,
                "skipped_case_count": skipped_case_total,
                "metric_ids": list(metric_backtests.keys()),
                "supported_metric_ids": supported_metric_ids,
                "unscored_metric_ids": unscored_metric_ids,
            },
        )

    def _get_ensemble_dir(self, simulation_id: str, ensemble_id: str) -> str:
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        return os.path.join(
            self.simulation_data_dir,
            simulation_id,
            "ensemble",
            f"ensemble_{normalized_ensemble_id}",
        )

    def _normalize_ensemble_id(self, ensemble_id: str) -> str:
        normalized = str(ensemble_id).strip()
        if normalized.startswith("ensemble_"):
            normalized = normalized.split("_", 1)[1]
        if not normalized.isdigit():
            raise ValueError(f"Invalid ensemble_id: {ensemble_id}")
        return f"{int(normalized):04d}"

    def _read_json(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, file_path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
