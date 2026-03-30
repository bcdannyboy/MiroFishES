import importlib
import json
from pathlib import Path

import pytest


def _load_backtest_module():
    return importlib.import_module("app.services.backtest_manager")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_backtest_manager_scores_binary_cases_and_persists_summary(
    simulation_data_dir, monkeypatch
):
    backtest_module = _load_backtest_module()
    monkeypatch.setattr(
        backtest_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    monkeypatch.setattr(
        backtest_module.Config,
        "CALIBRATION_LOG_SCORE_EPSILON",
        1e-6,
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "observed_truth_registry.json",
        {
            "artifact_type": "observed_truth_registry",
            "schema_version": "probabilistic.observed_truth.v2",
            "generator_version": "probabilistic.observed_truth.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "registry_scope": {
                "level": "ensemble",
                "simulation_id": "sim-001",
                "ensemble_id": "0001",
            },
            "cases": [
                {
                    "case_id": "case-1",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.8,
                    "observed_value": True,
                    "issued_at": "2026-03-30T09:05:00",
                    "resolved_at": "2026-04-01T09:00:00",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "evaluation_split": "out_of_sample",
                    "evaluation_window_id": "window-1",
                    "forecast_source": "aggregate_summary.json",
                    "observed_source": "manual-review.csv",
                },
                {
                    "case_id": "case-2",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.3,
                    "observed_value": False,
                    "issued_at": "2026-03-30T09:06:00",
                    "resolved_at": "2026-04-01T09:00:00",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "evaluation_split": "out_of_sample",
                    "evaluation_window_id": "window-1",
                },
                {
                    "case_id": "case-3",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 1.0,
                    "observed_value": True,
                    "issued_at": "2026-03-31T11:00:00",
                    "resolved_at": "2026-04-05T10:00:00",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "evaluation_split": "rolling",
                    "evaluation_window_id": "window-2",
                },
                {
                    "case_id": "case-4",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": None,
                    "observed_value": False,
                    "issued_at": "2026-03-30T09:07:00",
                    "resolved_at": "2026-04-01T09:00:00",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "evaluation_split": "out_of_sample",
                    "evaluation_window_id": "window-1",
                    "warnings": ["missing_probability_at_resolution"],
                },
                {
                    "case_id": "case-5",
                    "metric_id": "simulation.total_actions",
                    "value_kind": "numeric",
                    "forecast_probability": 0.7,
                    "observed_value": 12,
                    "issued_at": "2026-03-30T09:08:00",
                    "resolved_at": "2026-04-01T09:00:00",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "evaluation_split": "out_of_sample",
                    "evaluation_window_id": "window-1",
                },
            ],
            "quality_summary": {
                "status": "complete",
                "total_case_count": 5,
                "metric_ids": [
                    "simulation.completed",
                    "simulation.total_actions",
                ],
                "warnings": [],
            },
        },
    )

    manager = backtest_module.BacktestManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_backtest_summary("sim-001", "0001")

    metric_summary = summary["metric_backtests"]["simulation.completed"]
    assert metric_summary["case_count"] == 3
    assert metric_summary["positive_case_count"] == 2
    assert metric_summary["negative_case_count"] == 1
    assert metric_summary["observed_event_rate"] == pytest.approx(2 / 3)
    assert metric_summary["mean_forecast_probability"] == pytest.approx((0.8 + 0.3 + 1.0) / 3)
    assert metric_summary["scores"]["brier_score"] == pytest.approx(
        (0.04 + 0.09 + 0.0) / 3
    )
    assert metric_summary["scores"]["log_score"] == pytest.approx(
        (0.2231435513 + 0.3566749439 + 1.000000500029089e-06) / 3
    )
    assert metric_summary["scores"]["brier_skill_score"] == pytest.approx(0.805)
    assert metric_summary["scoring_rules"] == ["brier_score", "log_score"]
    assert metric_summary["case_results"][2]["score_inputs"]["probability_clipped"] is True
    assert "probability_clipped_for_log_score" in metric_summary["case_results"][2]["warnings"]
    assert metric_summary["mean_scores"] == metric_summary["scores"]

    unsupported_metric = summary["metric_backtests"]["simulation.total_actions"]
    assert unsupported_metric["case_count"] == 0
    assert unsupported_metric["warnings"] == ["unsupported_confidence_contract"]

    assert summary["evaluation_summary"] == {
        "case_count": 5,
        "scored_case_count": 3,
        "split_counts": {
            "out_of_sample": 4,
            "rolling": 1,
        },
        "question_class_counts": {
            "survey-support": 5,
        },
        "comparable_question_class_counts": {
            "survey-support": 5,
        },
        "window_count": 2,
        "window_ids": ["window-1", "window-2"],
        "question_classes": ["survey-support"],
        "comparable_question_classes": ["survey-support"],
        "out_of_sample_case_count": 4,
        "in_sample_case_count": 0,
        "rolling_case_count": 1,
        "holdout_case_count": 0,
        "benchmark_ids": ["climatology", "uniform_50_50"],
        "coverage_status": "cohort_metadata_present",
        "warnings": [],
    }

    assert summary["evaluation_windows"]["window-1"] == {
        "window_id": "window-1",
        "case_count": 4,
        "scored_case_count": 2,
        "evaluation_split": "out_of_sample",
        "question_class": "survey-support",
        "comparable_question_class": "survey-support",
        "metric_ids": ["simulation.completed", "simulation.total_actions"],
        "question_classes": ["survey-support"],
        "comparable_question_classes": ["survey-support"],
        "split_counts": {"out_of_sample": 4},
        "issue_window": {
            "start": "2026-03-30T09:05:00",
            "end": "2026-03-30T09:08:00",
        },
        "resolution_window": {
            "start": "2026-04-01T09:00:00",
            "end": "2026-04-01T09:00:00",
        },
        "warnings": [],
    }
    assert summary["evaluation_windows"]["window-2"]["evaluation_split"] == "rolling"
    assert summary["benchmark_comparisons"]["simulation.completed::climatology"][
        "benchmark_id"
    ] == "climatology"
    assert summary["benchmark_comparisons"]["simulation.completed::climatology"][
        "baseline_probability"
    ] == pytest.approx(2 / 3)
    assert summary["benchmark_comparisons"]["simulation.completed::climatology"][
        "score_deltas"
    ]["brier_score"] > 0
    assert summary["benchmark_comparisons"]["simulation.completed::uniform_50_50"][
        "benchmark_id"
    ] == "uniform_50_50"
    assert summary["schema_version"] == "probabilistic.backtest.v2"
    assert summary["quality_summary"]["status"] == "partial"
    assert summary["quality_summary"]["warnings"] == [
        "degraded_case_records",
        "unsupported_metrics_present",
    ]
    assert summary["quality_summary"]["total_case_count"] == 5
    assert summary["quality_summary"]["scored_case_count"] == 3
    assert summary["quality_summary"]["skipped_case_count"] == 1
    assert summary["quality_summary"]["metric_ids"] == [
        "simulation.completed",
        "simulation.total_actions",
    ]
    assert summary["quality_summary"]["supported_metric_ids"] == [
        "simulation.completed"
    ]
    assert summary["quality_summary"]["unscored_metric_ids"] == [
        "simulation.total_actions"
    ]
    assert (ensemble_dir / "backtest_summary.json").exists()


def test_backtest_manager_builds_benchmarks_and_evaluation_slices(
    simulation_data_dir, monkeypatch
):
    backtest_module = _load_backtest_module()
    monkeypatch.setattr(
        backtest_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-002" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "observed_truth_registry.json",
        {
            "artifact_type": "observed_truth_registry",
            "schema_version": "probabilistic.observed_truth.v2",
            "generator_version": "probabilistic.observed_truth.generator.v2",
            "simulation_id": "sim-002",
            "ensemble_id": "0001",
            "registry_scope": {
                "level": "ensemble",
                "simulation_id": "sim-002",
                "ensemble_id": "0001",
            },
            "cases": [
                {
                    "case_id": "case-1",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.72,
                    "observed_value": True,
                    "issued_at": "2026-01-01T09:00:00",
                    "resolved_at": "2026-01-08T09:00:00",
                    "question_class": "policy_support_binary",
                    "comparable_question_class": "policy_support_binary",
                    "evaluation_split": "in_sample",
                    "evaluation_lane": "benchmark_registry",
                    "window_id": "window-1",
                    "benchmark_probabilities": {
                        "reference_class": 0.61,
                        "simulation_only": 0.79,
                    },
                },
                {
                    "case_id": "case-2",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.66,
                    "observed_value": True,
                    "issued_at": "2026-01-02T09:00:00",
                    "resolved_at": "2026-01-09T09:00:00",
                    "question_class": "policy_support_binary",
                    "comparable_question_class": "policy_support_binary",
                    "evaluation_split": "out_of_sample",
                    "evaluation_lane": "benchmark_registry",
                    "window_id": "window-2",
                    "benchmark_probabilities": {
                        "reference_class": 0.58,
                        "simulation_only": 0.76,
                    },
                },
                {
                    "case_id": "case-3",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.28,
                    "observed_value": False,
                    "issued_at": "2026-01-03T09:00:00",
                    "resolved_at": "2026-01-10T09:00:00",
                    "question_class": "policy_support_binary",
                    "comparable_question_class": "policy_support_binary",
                    "evaluation_split": "rolling_window",
                    "evaluation_lane": "benchmark_registry",
                    "window_id": "window-2",
                    "benchmark_probabilities": {
                        "reference_class": 0.45,
                        "simulation_only": 0.52,
                    },
                },
            ],
            "quality_summary": {
                "status": "complete",
                "total_case_count": 3,
                "metric_ids": ["simulation.completed"],
                "warnings": [],
            },
        },
    )

    manager = backtest_module.BacktestManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_backtest_summary("sim-002", "0001")

    metric_summary = summary["metric_backtests"]["simulation.completed"]
    benchmark_summaries = metric_summary["benchmark_summaries"]
    evaluation_slices = metric_summary["evaluation_slices"]

    assert set(benchmark_summaries) >= {
        "uninformed_50",
        "retrospective_cohort_base_rate",
        "reference_class",
        "simulation_only",
    }
    assert benchmark_summaries["uninformed_50"]["case_count"] == 3
    assert benchmark_summaries["retrospective_cohort_base_rate"]["scores"]["brier_score"] == pytest.approx(
        2 / 9
    )
    assert benchmark_summaries["reference_class"]["scores"]["brier_score"] == pytest.approx(
        (0.1521 + 0.1764 + 0.2025) / 3
    )
    assert len(evaluation_slices) == 3
    assert {
        (item["evaluation_split"], item["window_id"])
        for item in evaluation_slices
    } == {
        ("in_sample", "window-1"),
        ("out_of_sample", "window-2"),
        ("rolling_window", "window-2"),
    }
    out_of_sample_slice = next(
        item for item in evaluation_slices if item["evaluation_split"] == "out_of_sample"
    )
    assert out_of_sample_slice["case_count"] == 1
    assert out_of_sample_slice["scores"]["brier_score"] == pytest.approx((1 - 0.66) ** 2)
    assert summary["evaluation_summary"]["split_counts"] == {
        "in_sample": 1,
        "out_of_sample": 1,
        "rolling_window": 1,
    }
    assert summary["evaluation_summary"]["question_classes"] == ["policy_support_binary"]
    assert summary["evaluation_summary"]["comparable_question_classes"] == [
        "policy_support_binary"
    ]
    assert summary["evaluation_summary"]["benchmark_ids"] == [
        "climatology",
        "uniform_50_50",
    ]
    assert summary["evaluation_summary"]["window_ids"] == ["window-1", "window-2"]


def test_backtest_manager_load_rejects_invalid_schema_version(
    simulation_data_dir, monkeypatch
):
    backtest_module = _load_backtest_module()
    monkeypatch.setattr(
        backtest_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.prepare.v1",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_backtests": {},
            "quality_summary": {"status": "complete", "warnings": []},
        },
    )

    manager = backtest_module.BacktestManager(simulation_data_dir=str(simulation_data_dir))
    with pytest.raises(ValueError, match="schema_version"):
        manager.load_backtest_summary("sim-001", "0001")
