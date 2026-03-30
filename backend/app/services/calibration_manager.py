"""
Calibration manager for backtested binary forecasts.

This slice is additive and conservative:
- it derives calibration only from persisted backtest summaries,
- it gates report-facing calibration on explicit readiness metadata,
- it does not claim recalibration or continuous predictive calibration.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from ..config import Config
from ..models.probabilistic import (
    CALIBRATION_SCHEMA_VERSION,
    BacktestSummary,
    CalibrationReadiness,
    CalibrationSummary,
    MetricCalibrationSummary,
    ReliabilityBin,
)


class CalibrationManager:
    """Persist reliability-style calibration summaries for binary metrics."""

    CALIBRATION_SUMMARY_FILENAME = "calibration_summary.json"
    BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"

    def __init__(self, simulation_data_dir: str | None = None) -> None:
        self.simulation_data_dir = (
            simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        )

    def get_calibration_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        backtest = BacktestSummary.from_dict(
            self.load_backtest_summary(simulation_id, ensemble_id)
        )
        summary = self._build_calibration_summary(backtest)
        payload = summary.to_dict()
        self._write_json(
            os.path.join(
                self._get_ensemble_dir(simulation_id, ensemble_id),
                self.CALIBRATION_SUMMARY_FILENAME,
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

    def load_calibration_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        summary_path = os.path.join(
            self._get_ensemble_dir(simulation_id, ensemble_id),
            self.CALIBRATION_SUMMARY_FILENAME,
        )
        if not os.path.exists(summary_path):
            raise ValueError(
                f"Calibration summary does not exist for simulation {simulation_id}, ensemble {ensemble_id}"
            )
        payload = self._read_json(summary_path)
        if not isinstance(payload, dict):
            raise ValueError("Calibration summary must be a JSON object")

        summary = CalibrationSummary.from_dict(payload)
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        if summary.artifact_type != "calibration_summary":
            raise ValueError("Invalid calibration summary artifact_type")
        if summary.schema_version != CALIBRATION_SCHEMA_VERSION:
            raise ValueError("Invalid calibration summary schema_version")
        if summary.simulation_id != simulation_id:
            raise ValueError("Calibration summary simulation_id does not match request")
        if summary.ensemble_id != normalized_ensemble_id:
            raise ValueError("Calibration summary ensemble_id does not match request")
        return summary.to_dict()

    def _build_calibration_summary(
        self,
        backtest: BacktestSummary,
    ) -> CalibrationSummary:
        metric_calibrations: Dict[str, MetricCalibrationSummary] = {}
        ready_metric_ids: List[str] = []
        not_ready_metric_ids: List[str] = []
        warnings: List[str] = []

        for metric_id, metric_summary in sorted(backtest.metric_backtests.items()):
            metric_warnings = list(metric_summary.warnings)
            reliability_bins = self._build_reliability_bins(metric_summary.to_dict())
            non_empty_bin_count = sum(
                1 for item in reliability_bins if item.case_count > 0
            )
            supported_bin_count = non_empty_bin_count
            gating_reasons: List[str] = []

            if metric_summary.value_kind != "binary":
                gating_reasons.append("unsupported_value_kind")
            if metric_summary.case_count < Config.CALIBRATION_MIN_CASE_COUNT:
                gating_reasons.append("insufficient_case_count")
            if (
                metric_summary.positive_case_count
                < Config.CALIBRATION_MIN_POSITIVE_CASE_COUNT
            ):
                gating_reasons.append("insufficient_positive_case_count")
            if (
                metric_summary.negative_case_count
                < Config.CALIBRATION_MIN_NEGATIVE_CASE_COUNT
            ):
                gating_reasons.append("insufficient_negative_case_count")
            if supported_bin_count < Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT:
                gating_reasons.append("insufficient_supported_bin_count")
            if not metric_summary.scoring_rules:
                gating_reasons.append("missing_supported_scores")

            ready = not gating_reasons
            readiness = CalibrationReadiness(
                ready=ready,
                minimum_case_count=Config.CALIBRATION_MIN_CASE_COUNT,
                actual_case_count=metric_summary.case_count,
                minimum_positive_case_count=Config.CALIBRATION_MIN_POSITIVE_CASE_COUNT,
                actual_positive_case_count=metric_summary.positive_case_count,
                minimum_negative_case_count=Config.CALIBRATION_MIN_NEGATIVE_CASE_COUNT,
                actual_negative_case_count=metric_summary.negative_case_count,
                non_empty_bin_count=non_empty_bin_count,
                supported_bin_count=supported_bin_count,
                minimum_supported_bin_count=Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT,
                gating_reasons=gating_reasons,
                confidence_label=self._determine_confidence_label(
                    ready=ready,
                    case_count=metric_summary.case_count,
                ),
            )

            metric_calibrations[metric_id] = MetricCalibrationSummary(
                metric_id=metric_id,
                value_kind=metric_summary.value_kind,
                case_count=metric_summary.case_count,
                supported_scoring_rules=list(metric_summary.scoring_rules),
                scores=dict(metric_summary.scores),
                reliability_bins=reliability_bins,
                diagnostics=self._build_diagnostics(
                    reliability_bins=reliability_bins,
                    metric_summary=metric_summary,
                ),
                readiness=readiness,
                warnings=metric_warnings,
            )

            if ready:
                ready_metric_ids.append(metric_id)
            else:
                not_ready_metric_ids.append(metric_id)

        if not_ready_metric_ids:
            warnings.append("not_ready_metrics_present")

        return CalibrationSummary(
            simulation_id=backtest.simulation_id,
            ensemble_id=backtest.ensemble_id,
            metric_calibrations=metric_calibrations,
            evaluation_provenance={
                "status": backtest.evaluation_summary.get(
                    "coverage_status", "unknown"
                ),
                "case_count": backtest.evaluation_summary.get("case_count", 0),
                "scored_case_count": backtest.evaluation_summary.get(
                    "scored_case_count", 0
                ),
                "split_counts": dict(
                    backtest.evaluation_summary.get("split_counts", {})
                ),
                "question_classes": list(
                    backtest.evaluation_summary.get("question_classes", [])
                ),
                "comparable_question_classes": list(
                    backtest.evaluation_summary.get(
                        "comparable_question_classes", []
                    )
                ),
                "window_count": backtest.evaluation_summary.get("window_count", 0),
                "window_ids": list(
                    backtest.evaluation_summary.get("window_ids", [])
                ),
                "benchmark_ids": list(
                    backtest.evaluation_summary.get("benchmark_ids", [])
                ),
                "benchmark_count": len(backtest.benchmark_comparisons),
                "source_artifacts": {
                    "backtest_summary": self.BACKTEST_SUMMARY_FILENAME,
                },
            },
            quality_summary={
                "status": "partial" if not_ready_metric_ids else "complete",
                "supported_metric_ids": sorted(metric_calibrations.keys()),
                "ready_metric_ids": ready_metric_ids,
                "not_ready_metric_ids": not_ready_metric_ids,
                "warnings": warnings,
                "source_artifacts": {
                    "backtest_summary": self.BACKTEST_SUMMARY_FILENAME,
                },
                "provenance": {
                    "status": "valid",
                    "backtest_artifact_type": backtest.artifact_type,
                    "backtest_schema_version": backtest.schema_version,
                    "backtest_generator_version": backtest.generator_version,
                    "backtest_simulation_id": backtest.simulation_id,
                    "backtest_ensemble_id": backtest.ensemble_id,
                },
            },
        )

    def _build_reliability_bins(self, metric_summary: Dict[str, Any]) -> List[ReliabilityBin]:
        bin_count = max(int(Config.CALIBRATION_BIN_COUNT), 1)
        case_results = metric_summary.get("case_results", [])
        buckets: List[List[Dict[str, Any]]] = [[] for _ in range(bin_count)]

        for case in case_results:
            probability = float(case["forecast_probability"])
            bucket_index = min(int(probability * bin_count), bin_count - 1)
            buckets[bucket_index].append(case)

        bins: List[ReliabilityBin] = []
        for bin_index, bucket in enumerate(buckets):
            lower_bound = bin_index / bin_count
            upper_bound = (bin_index + 1) / bin_count
            if bucket:
                mean_probability = sum(
                    float(item["forecast_probability"]) for item in bucket
                ) / len(bucket)
                observed_frequency = sum(
                    1.0 if item["observed_value"] else 0.0 for item in bucket
                ) / len(bucket)
                observed_minus_forecast = observed_frequency - mean_probability
            else:
                mean_probability = None
                observed_frequency = None
                observed_minus_forecast = None
            bins.append(
                ReliabilityBin(
                    bin_index=bin_index,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    case_count=len(bucket),
                    mean_forecast_probability=mean_probability,
                    observed_frequency=observed_frequency,
                    observed_minus_forecast=observed_minus_forecast,
                )
            )
        return bins

    def _build_diagnostics(
        self,
        *,
        reliability_bins: List[ReliabilityBin],
        metric_summary: Any,
    ) -> Dict[str, float]:
        weighted_gaps = []
        absolute_gaps = []
        case_count = metric_summary.case_count or 0

        for bin_summary in reliability_bins:
            if (
                bin_summary.case_count <= 0
                or bin_summary.observed_frequency is None
                or bin_summary.mean_forecast_probability is None
            ):
                continue
            gap = abs(
                float(bin_summary.observed_frequency)
                - float(bin_summary.mean_forecast_probability)
            )
            absolute_gaps.append(gap)
            weighted_gaps.append((bin_summary.case_count / case_count) * gap)

        return {
            "expected_calibration_error": round(sum(weighted_gaps), 12)
            if weighted_gaps
            else 0.0,
            "max_calibration_gap": round(max(absolute_gaps), 12)
            if absolute_gaps
            else 0.0,
            "observed_event_rate": float(metric_summary.observed_event_rate)
            if metric_summary.observed_event_rate is not None
            else 0.0,
            "mean_forecast_probability": float(metric_summary.mean_forecast_probability)
            if metric_summary.mean_forecast_probability is not None
            else 0.0,
        }

    def _determine_confidence_label(self, *, ready: bool, case_count: int) -> str:
        if not ready:
            return "insufficient"
        if case_count >= 25:
            return "moderate"
        return "limited"

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
