from __future__ import annotations

from app.models.probabilistic import (
    BacktestSummary,
    CalibrationSummary,
    EvaluationWindowSummary,
    BenchmarkComparisonSummary,
    ObservedTruthCase,
)


def test_observed_truth_case_aliases_issue_and_resolution_timestamps():
    case = ObservedTruthCase.from_dict(
        {
            "case_id": "case-1",
            "metric_id": "simulation.completed",
            "observed_value": True,
            "forecast_probability": 0.7,
            "forecast_issued_at": "2026-03-30T09:00:00",
            "observed_at": "2026-04-01T09:00:00",
            "question_class": "survey-support",
            "evaluation_split": "out_of_sample",
            "evaluation_window_id": "window-1",
            "benchmark_id": "climatology",
        }
    )

    serialized = case.to_dict()

    assert case.issued_at == "2026-03-30T09:00:00"
    assert case.resolved_at == "2026-04-01T09:00:00"
    assert case.comparable_question_class == "survey-support"
    assert serialized["issued_at"] == "2026-03-30T09:00:00"
    assert serialized["resolved_at"] == "2026-04-01T09:00:00"
    assert serialized["question_class"] == "survey-support"
    assert serialized["evaluation_split"] == "out_of_sample"
    assert serialized["evaluation_window_id"] == "window-1"
    assert serialized["benchmark_id"] == "climatology"


def test_backtest_summary_round_trips_window_and_benchmark_evaluation_state():
    summary = BacktestSummary.from_dict(
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.backtest.v2",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_backtests": {},
            "evaluation_windows": {
                "window-1": {
                    "window_id": "window-1",
                    "case_count": 3,
                    "scored_case_count": 2,
                    "evaluation_split": "out_of_sample",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "metric_ids": ["simulation.completed"],
                    "question_classes": ["survey-support"],
                    "comparable_question_classes": ["survey-support"],
                    "split_counts": {"out_of_sample": 3},
                    "issue_window": {
                        "start": "2026-03-30T09:00:00",
                        "end": "2026-03-30T09:30:00",
                    },
                    "resolution_window": {
                        "start": "2026-04-01T09:00:00",
                        "end": "2026-04-01T09:20:00",
                    },
                }
            },
            "benchmark_comparisons": {
                "simulation.completed::climatology": {
                    "benchmark_id": "climatology",
                    "metric_id": "simulation.completed",
                    "case_count": 2,
                    "system_scores": {"brier_score": 0.12, "log_score": 0.41},
                    "baseline_scores": {"brier_score": 0.22, "log_score": 0.55},
                    "score_deltas": {"brier_score": 0.1, "log_score": 0.14},
                    "skill_scores": {
                        "brier_skill_score": 0.454545454545,
                        "log_score_improvement": 0.14,
                    },
                    "baseline_probability": 0.5,
                    "notes": ["Uses a static 0.50 probability baseline."],
                }
            },
            "evaluation_summary": {
                "case_count": 3,
                "scored_case_count": 2,
                "split_counts": {"out_of_sample": 3},
                "question_class_counts": {"survey-support": 3},
                "comparable_question_class_counts": {"survey-support": 3},
                "window_count": 1,
                "window_ids": ["window-1"],
                "question_classes": ["survey-support"],
                "comparable_question_classes": ["survey-support"],
                "out_of_sample_case_count": 3,
                "in_sample_case_count": 0,
                "rolling_case_count": 0,
                "holdout_case_count": 0,
                "benchmark_ids": ["climatology"],
                "coverage_status": "cohort_metadata_present",
                "warnings": [],
            },
            "quality_summary": {
                "status": "complete",
                "warnings": [],
                "total_case_count": 3,
                "scored_case_count": 2,
                "skipped_case_count": 0,
                "metric_ids": ["simulation.completed"],
                "supported_metric_ids": ["simulation.completed"],
                "unscored_metric_ids": [],
            },
        }
    )

    serialized = summary.to_dict()

    assert isinstance(summary.evaluation_windows["window-1"], EvaluationWindowSummary)
    assert isinstance(
        summary.benchmark_comparisons["simulation.completed::climatology"],
        BenchmarkComparisonSummary,
    )
    assert summary.evaluation_summary["window_count"] == 1
    assert serialized["evaluation_windows"]["window-1"]["evaluation_split"] == "out_of_sample"
    assert serialized["benchmark_comparisons"]["simulation.completed::climatology"]["baseline_probability"] == 0.5
    assert serialized["evaluation_summary"]["benchmark_ids"] == ["climatology"]


def test_calibration_summary_round_trips_evaluation_provenance():
    summary = CalibrationSummary.from_dict(
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.calibration.v2",
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_calibrations": {},
            "evaluation_provenance": {
                "status": "cohort_metadata_present",
                "case_count": 3,
                "scored_case_count": 2,
                "split_counts": {"out_of_sample": 3},
                "question_classes": ["survey-support"],
                "comparable_question_classes": ["survey-support"],
                "window_count": 1,
                "window_ids": ["window-1"],
                "benchmark_ids": ["climatology"],
                "benchmark_count": 1,
                "source_artifacts": {"backtest_summary": "backtest_summary.json"},
            },
            "quality_summary": {
                "status": "complete",
                "supported_metric_ids": [],
                "ready_metric_ids": [],
                "not_ready_metric_ids": [],
                "warnings": [],
                "source_artifacts": {"backtest_summary": "backtest_summary.json"},
                "provenance": {
                    "status": "valid",
                    "backtest_artifact_type": "backtest_summary",
                    "backtest_schema_version": "probabilistic.backtest.v2",
                    "backtest_generator_version": "probabilistic.backtest.generator.v2",
                    "backtest_simulation_id": "sim-001",
                    "backtest_ensemble_id": "0001",
                },
            },
        }
    )

    serialized = summary.to_dict()

    assert summary.evaluation_provenance["benchmark_count"] == 1
    assert serialized["evaluation_provenance"]["window_ids"] == ["window-1"]
