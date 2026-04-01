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
    BACKTEST_SCHEMA_VERSION,
    BenchmarkComparisonSummary,
    BacktestCaseResult,
    BacktestSummary,
    EvaluationWindowSummary,
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
            simulation_data_dir or Config.get_simulation_data_dir()
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
        payload = self._read_json(summary_path)
        if not isinstance(payload, dict):
            raise ValueError("Backtest summary must be a JSON object")

        summary = BacktestSummary.from_dict(payload)
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        if summary.artifact_type != "backtest_summary":
            raise ValueError("Invalid backtest summary artifact_type")
        if summary.schema_version != BACKTEST_SCHEMA_VERSION:
            raise ValueError("Invalid backtest summary schema_version")
        if summary.simulation_id != simulation_id:
            raise ValueError("Backtest summary simulation_id does not match request")
        if summary.ensemble_id != normalized_ensemble_id:
            raise ValueError("Backtest summary ensemble_id does not match request")
        return summary.to_dict()

    def _build_backtest_summary(
        self,
        registry: ObservedTruthRegistry,
    ) -> BacktestSummary:
        grouped_cases: Dict[str, List[Any]] = defaultdict(list)
        grouped_windows: Dict[str, List[Any]] = defaultdict(list)
        split_counts: Dict[str, int] = defaultdict(int)
        question_class_counts: Dict[str, int] = defaultdict(int)
        comparable_question_class_counts: Dict[str, int] = defaultdict(int)
        for case in registry.cases:
            grouped_cases[case.metric_id].append(case)
            grouped_windows[self._case_window_key(case)].append(case)
            split_counts[self._case_split_key(case)] += 1
            question_class_counts[self._case_question_class_key(case)] += 1
            comparable_question_class_counts[
                self._case_comparable_question_class_key(case)
            ] += 1

        metric_backtests: Dict[str, MetricBacktestSummary] = {}
        benchmark_comparisons: Dict[str, BenchmarkComparisonSummary] = {}
        evaluation_windows: Dict[str, EvaluationWindowSummary] = {}
        warnings: List[str] = []
        scored_case_total = 0
        skipped_case_total = 0
        supported_metric_ids: List[str] = []
        unscored_metric_ids: List[str] = []
        scored_case_ids: set[str] = set()

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
                    benchmark_summaries={},
                    evaluation_slices=[],
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
                scored_case_ids.add(case.case_id)

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
                benchmark_comparisons.update(
                    self._build_benchmark_comparisons(
                        metric_id=metric_id,
                        case_results=case_results,
                        observed_event_rate=observed_event_rate,
                        system_scores=scores,
                    )
                )
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
                benchmark_summaries=self._build_metric_benchmark_summaries(
                    cases=cases,
                    case_results=case_results,
                    observed_event_rate=observed_event_rate,
                    system_scores=scores,
                ),
                evaluation_slices=self._build_metric_evaluation_slices(
                    cases=cases,
                    case_results=case_results,
                ),
                question_classes=sorted(
                    {self._case_question_class_key(case) for case in cases}
                ),
                comparable_question_classes=sorted(
                    {
                        self._case_comparable_question_class_key(case)
                        for case in cases
                    }
                ),
                evaluation_splits=sorted(
                    {self._case_split_key(case) for case in cases}
                ),
                evaluation_window_ids=sorted(
                    {self._case_window_key(case) for case in cases}
                ),
                warnings=metric_warnings,
            )

        for window_id, cases in sorted(grouped_windows.items()):
            issue_timestamps = [
                item.issued_at or item.forecast_issued_at
                for item in cases
                if item.issued_at or item.forecast_issued_at
            ]
            resolved_timestamps = [
                item.resolved_at or item.observed_at
                for item in cases
                if item.resolved_at or item.observed_at
            ]
            split_distribution: Dict[str, int] = defaultdict(int)
            for case in cases:
                split_distribution[self._case_split_key(case)] += 1
            evaluation_windows[window_id] = EvaluationWindowSummary(
                window_id=window_id,
                case_count=len(cases),
                scored_case_count=sum(
                    1 for item in cases if item.case_id in scored_case_ids
                ),
                evaluation_split=self._window_uniform_value(
                    self._case_split_key(item) for item in cases
                ),
                question_class=self._window_uniform_value(
                    self._case_question_class_key(item) for item in cases
                ),
                comparable_question_class=self._window_uniform_value(
                    self._case_comparable_question_class_key(item) for item in cases
                ),
                metric_ids=sorted({item.metric_id for item in cases}),
                question_classes=sorted(
                    {self._case_question_class_key(item) for item in cases}
                ),
                comparable_question_classes=sorted(
                    {
                        self._case_comparable_question_class_key(item)
                        for item in cases
                    }
                ),
                split_counts=dict(split_distribution),
                issue_window={
                    "start": min(issue_timestamps) if issue_timestamps else None,
                    "end": max(issue_timestamps) if issue_timestamps else None,
                },
                resolution_window={
                    "start": min(resolved_timestamps) if resolved_timestamps else None,
                    "end": max(resolved_timestamps) if resolved_timestamps else None,
                },
                warnings=[],
            )

        evaluation_summary = {
            "case_count": len(registry.cases),
            "scored_case_count": scored_case_total,
            "split_counts": dict(split_counts),
            "question_class_counts": dict(question_class_counts),
            "comparable_question_class_counts": dict(
                comparable_question_class_counts
            ),
            "window_count": len(evaluation_windows),
            "window_ids": sorted(evaluation_windows.keys()),
            "question_classes": sorted(question_class_counts.keys()),
            "comparable_question_classes": sorted(
                comparable_question_class_counts.keys()
            ),
            "out_of_sample_case_count": split_counts.get("out_of_sample", 0),
            "in_sample_case_count": split_counts.get("in_sample", 0),
            "rolling_case_count": split_counts.get("rolling", 0),
            "holdout_case_count": split_counts.get("holdout", 0),
            "benchmark_ids": sorted(
                {
                    comparison.benchmark_id
                    for comparison in benchmark_comparisons.values()
                }
            ),
            "coverage_status": (
                "cohort_metadata_present"
                if any(
                    value != "unclassified"
                    for value in list(split_counts.keys())
                    + list(question_class_counts.keys())
                    + list(comparable_question_class_counts.keys())
                )
                else "historical_metadata_missing"
            ),
            "warnings": (
                ["historical_metadata_missing"]
                if all(
                    value == "unclassified"
                    for value in list(split_counts.keys())
                    + list(question_class_counts.keys())
                    + list(comparable_question_class_counts.keys())
                )
                else []
            ),
        }

        return BacktestSummary(
            simulation_id=registry.simulation_id,
            ensemble_id=registry.ensemble_id,
            metric_backtests=metric_backtests,
            evaluation_windows=evaluation_windows,
            benchmark_comparisons=benchmark_comparisons,
            evaluation_summary=evaluation_summary,
            quality_summary={
                "status": "partial" if warnings else "complete",
                "warnings": warnings,
                "total_case_count": len(registry.cases),
                "scored_case_count": scored_case_total,
                "skipped_case_count": skipped_case_total,
                "metric_ids": list(metric_backtests.keys()),
                "supported_metric_ids": supported_metric_ids,
                "unscored_metric_ids": unscored_metric_ids,
                "split_case_counts": dict(split_counts),
                "question_classes": sorted(question_class_counts.keys()),
                "comparable_question_classes": sorted(
                    comparable_question_class_counts.keys()
                ),
                "benchmark_names": sorted(
                    {
                        benchmark_id
                        for benchmark_id in (
                            comparison.benchmark_id
                            for comparison in benchmark_comparisons.values()
                        )
                    }
                    | {
                        benchmark_id
                        for summary in metric_backtests.values()
                        for benchmark_id in summary.benchmark_summaries.keys()
                    }
                ),
                "window_ids": sorted(evaluation_windows.keys()),
            },
        )

    def _build_metric_benchmark_summaries(
        self,
        *,
        cases: List[Any],
        case_results: List[BacktestCaseResult],
        observed_event_rate: float | None,
        system_scores: Dict[str, float],
    ) -> Dict[str, Dict[str, Any]]:
        if not case_results:
            return {}

        summaries: Dict[str, Dict[str, Any]] = {}

        def _score_with_probabilities(probabilities: List[float]) -> Dict[str, float]:
            if not probabilities:
                return {}
            result_scores = {
                "brier_score": 0.0,
                "log_score": 0.0,
            }
            clipped_probability_values = [
                min(
                    max(float(probability), Config.CALIBRATION_LOG_SCORE_EPSILON),
                    1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON,
                )
                for probability in probabilities
            ]
            for case, probability in zip(case_results, clipped_probability_values):
                observed_value = 1.0 if case.observed_value else 0.0
                result_scores["brier_score"] += (probability - observed_value) ** 2
                result_scores["log_score"] += -(
                    (observed_value * math.log(probability))
                    + ((1.0 - observed_value) * math.log(1.0 - probability))
                )
            for key in result_scores:
                result_scores[key] /= len(clipped_probability_values)
            event_rate = sum(
                1.0 if item.observed_value else 0.0 for item in case_results
            ) / len(case_results)
            climatology_brier = event_rate * (1.0 - event_rate)
            if climatology_brier > 0:
                result_scores["brier_skill_score"] = 1.0 - (
                    result_scores["brier_score"] / climatology_brier
                )
            return result_scores

        benchmark_probabilities: Dict[str, List[float]] = defaultdict(list)
        for case in cases:
            if not isinstance(case.benchmark_probabilities, dict):
                continue
            for benchmark_name, probability in case.benchmark_probabilities.items():
                try:
                    benchmark_probabilities[str(benchmark_name)].append(float(probability))
                except (TypeError, ValueError):
                    continue

        benchmark_payloads: Dict[str, tuple[List[float] | float | None, List[str]]] = {
            "uninformed_50": (
                0.5,
                [
                    "Static 50/50 benchmark with no historical conditioning.",
                ],
            ),
            "retrospective_cohort_base_rate": (
                observed_event_rate,
                [
                    "Uses the observed event rate in the scored cohort.",
                ],
            ),
        }
        for benchmark_name, (baseline, notes) in benchmark_payloads.items():
            if baseline is None:
                continue
            scores = self._score_cases_against_probability(case_results, baseline)
            summaries[benchmark_name] = {
                "benchmark_name": benchmark_name,
                "case_count": len(case_results),
                "scores": scores,
                "baseline_probability": baseline,
                "score_deltas": {
                    key: round(
                        float(scores.get(key, 0.0)) - float(system_scores.get(key, 0.0)),
                        12,
                    )
                    for key in ("brier_score", "log_score")
                    if key in scores or key in system_scores
                },
                "notes": notes,
            }

        for benchmark_name, probabilities in sorted(benchmark_probabilities.items()):
            if not probabilities:
                continue
            scores = _score_with_probabilities(probabilities)
            if not scores:
                continue
            summaries[benchmark_name] = {
                "benchmark_name": benchmark_name,
                "case_count": len(probabilities),
                "scores": scores,
                "baseline_probability": None,
                "score_deltas": {
                    key: round(
                        float(scores.get(key, 0.0)) - float(system_scores.get(key, 0.0)),
                        12,
                    )
                    for key in ("brier_score", "log_score")
                    if key in scores or key in system_scores
                },
                "notes": [
                    "Uses per-case benchmark probabilities stored in the registry.",
                ],
            }

        return summaries

    def _build_metric_evaluation_slices(
        self,
        *,
        cases: List[Any],
        case_results: List[BacktestCaseResult],
    ) -> List[Dict[str, Any]]:
        if not cases:
            return []

        case_results_by_id = {item.case_id: item for item in case_results}
        grouped_slices: Dict[tuple[str, str], List[Any]] = defaultdict(list)
        for case in cases:
            split = self._case_split_key(case)
            window_id = self._case_window_key(case)
            grouped_slices[(split, window_id)].append(case)

        slices: List[Dict[str, Any]] = []
        for (split, window_id), grouped_cases in sorted(grouped_slices.items()):
            relevant_results = [
                case_results_by_id[case.case_id]
                for case in grouped_cases
                if case.case_id in case_results_by_id
            ]
            scores = self._aggregate_case_result_scores(relevant_results)
            slices.append(
                {
                    "evaluation_split": split,
                    "window_id": window_id,
                    "case_count": len(grouped_cases),
                    "scored_case_count": len(relevant_results),
                    "scores": scores,
                }
            )
        return slices

    def _build_benchmark_comparisons(
        self,
        *,
        metric_id: str,
        case_results: List[BacktestCaseResult],
        observed_event_rate: float | None,
        system_scores: Dict[str, float],
    ) -> Dict[str, BenchmarkComparisonSummary]:
        if not case_results:
            return {}

        benchmark_payloads: Dict[str, tuple[float | None, List[str]]] = {
            "climatology": (
                observed_event_rate,
                [
                    "Uses the scored-case event rate as a historical baseline.",
                    "Not an out-of-sample benchmark unless the registry explicitly supplies one.",
                ],
            ),
            "uniform_50_50": (
                0.5,
                [
                    "Uses a static 0.50 probability baseline.",
                ],
            ),
        }
        comparisons: Dict[str, BenchmarkComparisonSummary] = {}
        for benchmark_id, (baseline_probability, notes) in benchmark_payloads.items():
            if baseline_probability is None:
                continue
            baseline_scores = self._score_cases_against_probability(
                case_results,
                baseline_probability,
            )
            score_deltas = {
                key: round(
                    float(baseline_scores.get(key, 0.0))
                    - float(system_scores.get(key, 0.0)),
                    12,
                )
                for key in ("brier_score", "log_score")
                if key in baseline_scores or key in system_scores
            }
            skill_scores: Dict[str, float] = {}
            if baseline_scores.get("brier_score") not in (None, 0):
                skill_scores["brier_skill_score"] = round(
                    1.0
                    - (
                        float(system_scores.get("brier_score", 0.0))
                        / float(baseline_scores["brier_score"])
                    ),
                    12,
                )
            if baseline_scores.get("log_score") is not None:
                skill_scores["log_score_improvement"] = round(
                    float(baseline_scores["log_score"])
                    - float(system_scores.get("log_score", 0.0)),
                    12,
                )
            comparisons[f"{metric_id}::{benchmark_id}"] = BenchmarkComparisonSummary(
                benchmark_id=benchmark_id,
                metric_id=metric_id,
                case_count=len(case_results),
                system_scores={
                    key: float(value)
                    for key, value in system_scores.items()
                    if key in {"brier_score", "log_score", "brier_skill_score"}
                },
                baseline_scores=baseline_scores,
                score_deltas=score_deltas,
                skill_scores=skill_scores,
                baseline_probability=baseline_probability,
                notes=notes,
            )
        return comparisons

    def _score_cases_against_probability(
        self,
        case_results: List[BacktestCaseResult],
        probability: float,
    ) -> Dict[str, float]:
        if not case_results:
            return {}
        clipped_probability = min(
            max(float(probability), Config.CALIBRATION_LOG_SCORE_EPSILON),
            1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON,
        )
        brier_scores: List[float] = []
        log_scores: List[float] = []
        for case in case_results:
            observed_value = 1.0 if case.observed_value else 0.0
            brier_scores.append((clipped_probability - observed_value) ** 2)
            log_scores.append(
                -(
                    (observed_value * math.log(clipped_probability))
                    + ((1.0 - observed_value) * math.log(1.0 - clipped_probability))
                )
            )
        scores: Dict[str, float] = {
            "brier_score": sum(brier_scores) / len(brier_scores),
            "log_score": sum(log_scores) / len(log_scores),
        }
        event_rate = sum(
            1.0 if item.observed_value else 0.0 for item in case_results
        ) / len(case_results)
        climatology_brier = event_rate * (1.0 - event_rate)
        if climatology_brier > 0:
            scores["brier_skill_score"] = 1.0 - (
                scores["brier_score"] / climatology_brier
            )
        return scores

    def _score_cases_with_case_probabilities(
        self,
        case_results: List[BacktestCaseResult],
        probabilities: List[float],
    ) -> Dict[str, float]:
        if not case_results or not probabilities or len(case_results) != len(probabilities):
            return {}
        brier_scores: List[float] = []
        log_scores: List[float] = []
        for result, probability in zip(case_results, probabilities):
            clipped_probability = min(
                max(float(probability), Config.CALIBRATION_LOG_SCORE_EPSILON),
                1.0 - Config.CALIBRATION_LOG_SCORE_EPSILON,
            )
            observed_value = 1.0 if result.observed_value else 0.0
            brier_scores.append((float(probability) - observed_value) ** 2)
            log_scores.append(
                -(
                    (observed_value * math.log(clipped_probability))
                    + ((1.0 - observed_value) * math.log(1.0 - clipped_probability))
                )
            )
        scores: Dict[str, float] = {
            "brier_score": sum(brier_scores) / len(brier_scores),
            "log_score": sum(log_scores) / len(log_scores),
        }
        event_rate = sum(
            1.0 if item.observed_value else 0.0 for item in case_results
        ) / len(case_results)
        climatology_brier = event_rate * (1.0 - event_rate)
        if climatology_brier > 0:
            scores["brier_skill_score"] = 1.0 - (
                scores["brier_score"] / climatology_brier
            )
        return scores

    def _aggregate_case_result_scores(
        self,
        case_results: List[BacktestCaseResult],
    ) -> Dict[str, float]:
        if not case_results:
            return {}
        scores: Dict[str, float] = {}
        for score_name in ("brier_score", "log_score"):
            scores[score_name] = sum(
                result.scores.get(score_name, 0.0) for result in case_results
            ) / len(case_results)
        event_rate = sum(1.0 if item.observed_value else 0.0 for item in case_results) / len(case_results)
        climatology_brier = event_rate * (1.0 - event_rate)
        if climatology_brier > 0:
            scores["brier_skill_score"] = 1.0 - (
                scores["brier_score"] / climatology_brier
            )
        return scores

    def _case_split_key(self, case: Any) -> str:
        return self._normalize_metadata_key(
            getattr(case, "evaluation_split", None),
            default="unclassified",
        )

    def _case_question_class_key(self, case: Any) -> str:
        return self._normalize_metadata_key(
            getattr(case, "question_class", None),
            default="unclassified",
        )

    def _case_comparable_question_class_key(self, case: Any) -> str:
        comparable = getattr(case, "comparable_question_class", None)
        if comparable is None:
            comparable = getattr(case, "question_class", None)
        return self._normalize_metadata_key(comparable, default="unclassified")

    def _case_window_key(self, case: Any) -> str:
        explicit = self._normalize_metadata_key(
            getattr(case, "evaluation_window_id", None),
            default="",
        )
        if explicit:
            return explicit
        split = self._case_split_key(case)
        question_class = self._case_question_class_key(case)
        comparable = self._case_comparable_question_class_key(case)
        key = "::".join(
            part
            for part in (split, question_class, comparable)
            if part and part != "unclassified"
        )
        return key or "unclassified"

    def _normalize_metadata_key(self, value: Any, *, default: str) -> str:
        text = str(value).strip() if value is not None else ""
        return text or default

    def _window_uniform_value(self, values: Any) -> str | None:
        normalized = [value for value in values if value and value != "unclassified"]
        if not normalized:
            return None
        if len(set(normalized)) == 1:
            return normalized[0]
        return "mixed"

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
