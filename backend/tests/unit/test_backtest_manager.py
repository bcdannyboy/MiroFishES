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
                    "forecast_source": "aggregate_summary.json",
                    "observed_source": "manual-review.csv",
                },
                {
                    "case_id": "case-2",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 0.3,
                    "observed_value": False,
                },
                {
                    "case_id": "case-3",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": 1.0,
                    "observed_value": True,
                },
                {
                    "case_id": "case-4",
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "forecast_probability": None,
                    "observed_value": False,
                    "warnings": ["missing_probability_at_resolution"],
                },
                {
                    "case_id": "case-5",
                    "metric_id": "simulation.total_actions",
                    "value_kind": "numeric",
                    "forecast_probability": 0.7,
                    "observed_value": 12,
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

    assert summary["schema_version"] == "probabilistic.backtest.v2"
    assert summary["quality_summary"] == {
        "status": "partial",
        "warnings": ["degraded_case_records", "unsupported_metrics_present"],
        "total_case_count": 5,
        "scored_case_count": 3,
        "skipped_case_count": 1,
        "metric_ids": ["simulation.completed", "simulation.total_actions"],
        "supported_metric_ids": ["simulation.completed"],
        "unscored_metric_ids": ["simulation.total_actions"],
    }
    assert (ensemble_dir / "backtest_summary.json").exists()
