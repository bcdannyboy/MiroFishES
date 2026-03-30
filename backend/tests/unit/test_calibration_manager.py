import importlib
import json
from pathlib import Path

import pytest


def _load_calibration_module():
    return importlib.import_module("app.services.calibration_manager")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_calibration_manager_builds_reliability_bins_and_readiness(
    simulation_data_dir, monkeypatch
):
    calibration_module = _load_calibration_module()
    monkeypatch.setattr(
        calibration_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_CASE_COUNT",
        10,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_BIN_COUNT",
        5,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_POSITIVE_CASE_COUNT",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_NEGATIVE_CASE_COUNT",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_SUPPORTED_BIN_COUNT",
        3,
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.backtest.v2",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_backtests": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "positive_case_count": 5,
                    "negative_case_count": 5,
                    "observed_event_rate": 0.5,
                    "mean_forecast_probability": 0.44,
                    "scoring_rules": ["brier_score", "log_score"],
                    "scores": {
                        "brier_score": 0.12,
                        "log_score": 0.41,
                        "brier_skill_score": 0.52,
                    },
                    "case_results": [
                        {"case_id": "c1", "metric_id": "simulation.completed", "forecast_probability": 0.1, "observed_value": False, "scores": {"brier_score": 0.01}},
                        {"case_id": "c2", "metric_id": "simulation.completed", "forecast_probability": 0.1, "observed_value": False, "scores": {"brier_score": 0.01}},
                        {"case_id": "c3", "metric_id": "simulation.completed", "forecast_probability": 0.2, "observed_value": False, "scores": {"brier_score": 0.04}},
                        {"case_id": "c4", "metric_id": "simulation.completed", "forecast_probability": 0.2, "observed_value": True, "scores": {"brier_score": 0.64}},
                        {"case_id": "c5", "metric_id": "simulation.completed", "forecast_probability": 0.3, "observed_value": False, "scores": {"brier_score": 0.09}},
                        {"case_id": "c6", "metric_id": "simulation.completed", "forecast_probability": 0.3, "observed_value": True, "scores": {"brier_score": 0.49}},
                        {"case_id": "c7", "metric_id": "simulation.completed", "forecast_probability": 0.7, "observed_value": True, "scores": {"brier_score": 0.09}},
                        {"case_id": "c8", "metric_id": "simulation.completed", "forecast_probability": 0.7, "observed_value": False, "scores": {"brier_score": 0.49}},
                        {"case_id": "c9", "metric_id": "simulation.completed", "forecast_probability": 0.9, "observed_value": True, "scores": {"brier_score": 0.01}},
                        {"case_id": "c10", "metric_id": "simulation.completed", "forecast_probability": 0.9, "observed_value": True, "scores": {"brier_score": 0.01}},
                    ],
                    "warnings": [],
                }
            },
            "evaluation_windows": {
                "window-1": {
                    "window_id": "window-1",
                    "case_count": 10,
                    "scored_case_count": 10,
                    "evaluation_split": "out_of_sample",
                    "question_class": "survey-support",
                    "comparable_question_class": "survey-support",
                    "metric_ids": ["simulation.completed"],
                    "question_classes": ["survey-support"],
                    "comparable_question_classes": ["survey-support"],
                    "split_counts": {"out_of_sample": 10},
                    "issue_window": {
                        "start": "2026-03-30T09:00:00",
                        "end": "2026-03-30T10:00:00",
                    },
                    "resolution_window": {
                        "start": "2026-04-01T09:00:00",
                        "end": "2026-04-01T09:30:00",
                    },
                    "warnings": [],
                }
            },
            "benchmark_comparisons": {
                "simulation.completed::climatology": {
                    "benchmark_id": "climatology",
                    "metric_id": "simulation.completed",
                    "case_count": 10,
                    "system_scores": {
                        "brier_score": 0.12,
                        "log_score": 0.41,
                        "brier_skill_score": 0.52,
                    },
                    "baseline_scores": {
                        "brier_score": 0.18,
                        "log_score": 0.52,
                        "brier_skill_score": 0.0,
                    },
                    "score_deltas": {
                        "brier_score": 0.06,
                        "log_score": 0.11,
                    },
                    "skill_scores": {
                        "brier_skill_score": 0.333333333333,
                        "log_score_improvement": 0.11,
                    },
                    "baseline_probability": 0.5,
                    "notes": ["Uses a static 0.50 probability baseline."],
                }
            },
            "evaluation_summary": {
                "case_count": 10,
                "scored_case_count": 10,
                "split_counts": {"out_of_sample": 10},
                "question_class_counts": {"survey-support": 10},
                "comparable_question_class_counts": {"survey-support": 10},
                "window_count": 1,
                "window_ids": ["window-1"],
                "question_classes": ["survey-support"],
                "comparable_question_classes": ["survey-support"],
                "out_of_sample_case_count": 10,
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
                "total_case_count": 10,
                "scored_case_count": 10,
                "skipped_case_count": 0,
                "supported_metric_ids": ["simulation.completed"],
                "unscored_metric_ids": [],
            },
        },
    )

    manager = calibration_module.CalibrationManager(
        simulation_data_dir=str(simulation_data_dir)
    )
    summary = manager.get_calibration_summary("sim-001", "0001")

    metric_summary = summary["metric_calibrations"]["simulation.completed"]
    assert metric_summary["readiness"]["ready"] is True
    assert metric_summary["readiness"]["minimum_case_count"] == 10
    assert metric_summary["readiness"]["minimum_positive_case_count"] == 3
    assert metric_summary["readiness"]["actual_positive_case_count"] == 5
    assert metric_summary["readiness"]["minimum_negative_case_count"] == 3
    assert metric_summary["readiness"]["actual_negative_case_count"] == 5
    assert metric_summary["readiness"]["minimum_supported_bin_count"] == 3
    assert metric_summary["readiness"]["supported_bin_count"] == 4
    assert metric_summary["readiness"]["confidence_label"] == "limited"
    assert metric_summary["diagnostics"]["expected_calibration_error"] == 0.18
    assert metric_summary["diagnostics"]["max_calibration_gap"] == 0.25
    assert metric_summary["diagnostics"]["observed_event_rate"] == 0.5
    assert metric_summary["diagnostics"]["mean_forecast_probability"] == 0.44
    assert len(metric_summary["reliability_bins"]) == 5
    assert metric_summary["reliability_bins"][0]["observed_frequency"] == 0.0
    assert metric_summary["reliability_bins"][-1]["observed_frequency"] == 1.0
    assert summary["schema_version"] == "probabilistic.calibration.v2"
    assert summary["quality_summary"]["source_artifacts"] == {
        "backtest_summary": "backtest_summary.json"
    }
    assert summary["quality_summary"]["provenance"] == {
        "status": "valid",
        "backtest_artifact_type": "backtest_summary",
        "backtest_schema_version": "probabilistic.backtest.v2",
        "backtest_generator_version": "probabilistic.backtest.generator.v2",
        "backtest_simulation_id": "sim-001",
        "backtest_ensemble_id": "0001",
    }
    assert summary["evaluation_provenance"] == {
        "status": "cohort_metadata_present",
        "case_count": 10,
        "scored_case_count": 10,
        "split_counts": {"out_of_sample": 10},
        "question_classes": ["survey-support"],
        "comparable_question_classes": ["survey-support"],
        "window_count": 1,
        "window_ids": ["window-1"],
        "benchmark_ids": ["climatology"],
        "benchmark_count": 1,
        "source_artifacts": {"backtest_summary": "backtest_summary.json"},
    }
    assert (ensemble_dir / "calibration_summary.json").exists()


def test_calibration_manager_marks_single_class_backtests_not_ready(
    simulation_data_dir, monkeypatch
):
    calibration_module = _load_calibration_module()
    monkeypatch.setattr(
        calibration_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_CASE_COUNT",
        10,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_POSITIVE_CASE_COUNT",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_NEGATIVE_CASE_COUNT",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_MIN_SUPPORTED_BIN_COUNT",
        2,
        raising=False,
    )
    monkeypatch.setattr(
        calibration_module.Config,
        "CALIBRATION_BIN_COUNT",
        5,
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.backtest.v2",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_backtests": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "positive_case_count": 10,
                    "negative_case_count": 0,
                    "observed_event_rate": 1.0,
                    "mean_forecast_probability": 0.86,
                    "scoring_rules": ["brier_score", "log_score"],
                    "scores": {
                        "brier_score": 0.09,
                        "log_score": 0.12,
                    },
                    "case_results": [
                        {
                            "case_id": f"c{index}",
                            "metric_id": "simulation.completed",
                            "forecast_probability": 0.8 if index < 6 else 0.9,
                            "observed_value": True,
                            "scores": {"brier_score": 0.04 if index < 6 else 0.01},
                        }
                        for index in range(1, 11)
                    ],
                    "warnings": ["degenerate_base_rate_baseline"],
                }
            },
            "quality_summary": {
                "status": "complete",
                "warnings": [],
                "total_case_count": 10,
                "scored_case_count": 10,
                "skipped_case_count": 0,
                "supported_metric_ids": ["simulation.completed"],
                "unscored_metric_ids": [],
            },
        },
    )

    manager = calibration_module.CalibrationManager(
        simulation_data_dir=str(simulation_data_dir)
    )
    summary = manager.get_calibration_summary("sim-001", "0001")

    metric_summary = summary["metric_calibrations"]["simulation.completed"]
    assert metric_summary["readiness"]["ready"] is False
    assert metric_summary["readiness"]["gating_reasons"] == [
        "insufficient_negative_case_count",
        "insufficient_supported_bin_count",
    ]
    assert metric_summary["diagnostics"]["expected_calibration_error"] == 0.15
    assert metric_summary["diagnostics"]["max_calibration_gap"] == 0.15
    assert summary["quality_summary"]["status"] == "partial"
    assert summary["quality_summary"]["not_ready_metric_ids"] == ["simulation.completed"]


def test_calibration_manager_load_rejects_invalid_schema_version(
    simulation_data_dir, monkeypatch
):
    calibration_module = _load_calibration_module()
    monkeypatch.setattr(
        calibration_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    ensemble_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001"
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.prepare.v1",
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "metric_calibrations": {},
            "quality_summary": {"status": "complete", "warnings": []},
        },
    )

    manager = calibration_module.CalibrationManager(
        simulation_data_dir=str(simulation_data_dir)
    )
    with pytest.raises(ValueError, match="schema_version"):
        manager.load_calibration_summary("sim-001", "0001")
