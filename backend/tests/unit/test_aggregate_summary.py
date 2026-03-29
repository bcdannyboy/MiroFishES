import importlib
import json
from pathlib import Path

import pytest


def _load_ensemble_module():
    return importlib.import_module("app.services.ensemble_manager")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_ensemble_root(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    ensemble_id: str = "0001",
    run_payloads: list[dict],
) -> Path:
    ensemble_dir = (
        simulation_data_dir
        / simulation_id
        / "ensemble"
        / f"ensemble_{ensemble_id}"
    )
    runs_dir = ensemble_dir / "runs"
    _write_json(
        ensemble_dir / "ensemble_spec.json",
        {
            "artifact_type": "ensemble_spec",
            "simulation_id": simulation_id,
            "run_count": len(run_payloads),
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    _write_json(
        ensemble_dir / "ensemble_state.json",
        {
            "artifact_type": "ensemble_state",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "status": "prepared",
            "run_count": len(run_payloads),
            "prepared_run_count": len(run_payloads),
            "run_ids": [payload["run_id"] for payload in run_payloads],
            "outcome_metric_ids": sorted(
                {
                    metric_id
                    for payload in run_payloads
                    for metric_id in payload.get("metric_values", {}).keys()
                }
            ),
        },
    )

    for payload in run_payloads:
        run_id = payload["run_id"]
        run_dir = runs_dir / f"run_{run_id}"
        _write_json(
            run_dir / "run_manifest.json",
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "root_seed": payload.get("root_seed", 0),
                "seed_metadata": {"resolution_seed": payload.get("root_seed", 0)},
                "resolved_values": {},
                "config_artifact": "resolved_config.json",
                "artifact_paths": {"resolved_config": "resolved_config.json"},
                "status": payload.get("run_status", "completed"),
            },
        )
        _write_json(
            run_dir / "resolved_config.json",
            {
                "artifact_type": "resolved_config",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
            },
        )
        metrics_payload = payload.get("metrics_payload")
        if metrics_payload is not None:
            _write_json(run_dir / "metrics.json", metrics_payload)

    return ensemble_dir


def test_get_aggregate_summary_persists_quantiles_and_quality_warnings(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "run_status": "completed",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "label": "Simulation Total Actions",
                            "aggregation": "count",
                            "unit": "count",
                            "probability_mode": "empirical",
                            "value": 2,
                        }
                    },
                },
            },
            {
                "run_id": "0002",
                "run_status": "completed",
                "metrics_payload": {
                    "quality_checks": {"status": "partial", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "label": "Simulation Total Actions",
                            "aggregation": "count",
                            "unit": "count",
                            "probability_mode": "empirical",
                            "value": 4,
                        }
                    },
                },
            },
            {
                "run_id": "0003",
                "run_status": "completed",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "label": "Simulation Total Actions",
                            "aggregation": "count",
                            "unit": "count",
                            "probability_mode": "empirical",
                            "value": 6,
                        }
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    metric_summary = summary["metric_summaries"]["simulation.total_actions"]
    assert (ensemble_dir / "aggregate_summary.json").exists()
    assert metric_summary["distribution_kind"] == "continuous"
    assert metric_summary["sample_count"] == 3
    assert metric_summary["mean"] == 4.0
    assert metric_summary["min"] == 2
    assert metric_summary["max"] == 6
    assert metric_summary["quantiles"]["p50"] == 4.0
    assert metric_summary["support_count"] == 3
    assert metric_summary["support_fraction"] == 1.0
    assert metric_summary["minimum_support_count"] == 2
    assert metric_summary["minimum_support_met"] is True
    assert "thin_sample" in metric_summary["warnings"]
    assert "degraded_runs_present" in metric_summary["warnings"]
    assert summary["quality_summary"]["partial_runs"] == 1
    assert summary["sample_policy"]["analysis_mode"] == "aggregate"
    assert summary["sample_policy"]["eligible_run_count"] == 3
    assert "thin_sample" in summary["quality_summary"]["warnings"]
    assert "degraded_runs_present" in summary["quality_summary"]["warnings"]


def test_get_aggregate_summary_supports_binary_and_categorical_metrics(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary-categories"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "outcome.success": {"metric_id": "outcome.success", "value": True},
                        "outcome.label": {"metric_id": "outcome.label", "value": "alpha"},
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "outcome.success": {"metric_id": "outcome.success", "value": False},
                        "outcome.label": {"metric_id": "outcome.label", "value": "beta"},
                    },
                },
            },
            {
                "run_id": "0003",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "outcome.success": {"metric_id": "outcome.success", "value": True},
                        "outcome.label": {"metric_id": "outcome.label", "value": "alpha"},
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    binary_summary = summary["metric_summaries"]["outcome.success"]
    categorical_summary = summary["metric_summaries"]["outcome.label"]

    assert binary_summary["distribution_kind"] == "binary"
    assert binary_summary["sample_count"] == 3
    assert binary_summary["empirical_probability"] == 2 / 3
    assert binary_summary["counts"] == {"false": 1, "true": 2}
    assert binary_summary["dominant_value"] is True
    assert binary_summary["dominant_probability"] == 2 / 3

    assert categorical_summary["distribution_kind"] == "categorical"
    assert categorical_summary["sample_count"] == 3
    assert categorical_summary["category_counts"] == {"alpha": 2, "beta": 1}
    assert categorical_summary["category_probabilities"] == {
        "alpha": 2 / 3,
        "beta": 1 / 3,
    }


def test_get_aggregate_summary_surfaces_minimum_support_for_sparse_metrics(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary-support"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "value": 2,
                        },
                        "rare.metric": {
                            "metric_id": "rare.metric",
                            "value": 9,
                        },
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "value": 4,
                        }
                    },
                },
            },
            {
                "run_id": "0003",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": {
                            "metric_id": "simulation.total_actions",
                            "value": 6,
                        }
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    rare_summary = summary["metric_summaries"]["rare.metric"]
    assert rare_summary["support_count"] == 1
    assert rare_summary["support_fraction"] == 1 / 3
    assert rare_summary["minimum_support_met"] is False
    assert "minimum_support_not_met" in rare_summary["warnings"]


def test_get_aggregate_summary_ignores_missing_numeric_samples_but_preserves_other_distributions(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary-rich"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.completed": {"metric_id": "simulation.completed", "value": True},
                        "platform.leading_platform": {"metric_id": "platform.leading_platform", "value": "twitter"},
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "value": 900,
                        },
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.completed": {"metric_id": "simulation.completed", "value": False},
                        "platform.leading_platform": {"metric_id": "platform.leading_platform", "value": "reddit"},
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "value": None,
                        },
                    },
                },
            },
            {
                "run_id": "0003",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.completed": {"metric_id": "simulation.completed", "value": True},
                        "platform.leading_platform": {"metric_id": "platform.leading_platform", "value": "twitter"},
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "value": 1200,
                        },
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    completion_summary = summary["metric_summaries"]["simulation.completed"]
    platform_summary = summary["metric_summaries"]["platform.leading_platform"]
    completion_window_summary = summary["metric_summaries"]["simulation.observed_completion_window_seconds"]

    assert completion_summary["distribution_kind"] == "binary"
    assert completion_summary["empirical_probability"] == pytest.approx(2 / 3)
    assert platform_summary["distribution_kind"] == "categorical"
    assert platform_summary["category_counts"] == {"reddit": 1, "twitter": 2}
    assert platform_summary["dominant_value"] == "twitter"
    assert platform_summary["dominant_probability"] == pytest.approx(2 / 3)
    assert completion_window_summary["distribution_kind"] == "continuous"
    assert completion_window_summary["sample_count"] == 2
    assert completion_window_summary["missing_sample_count"] == 0
    assert completion_window_summary["mean"] == 1050.0


def test_get_aggregate_summary_ignores_missing_numeric_values_and_preserves_metadata(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary-expanded"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "label": "Observed Completion Window",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": 1200.0,
                        }
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "label": "Observed Completion Window",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": None,
                        }
                    },
                },
            },
            {
                "run_id": "0003",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.observed_completion_window_seconds": {
                            "metric_id": "simulation.observed_completion_window_seconds",
                            "label": "Observed Completion Window",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": 1800.0,
                        }
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    duration_summary = summary["metric_summaries"]["simulation.observed_completion_window_seconds"]

    assert duration_summary["aggregation"] == "duration"
    assert duration_summary["unit"] == "seconds"
    assert duration_summary["value_kind"] == "numeric"
    assert duration_summary["sample_count"] == 2
    assert duration_summary["missing_sample_count"] == 0
    assert duration_summary["mean"] == 1500.0
    assert duration_summary["quantiles"]["p50"] == 1500.0


def test_get_aggregate_summary_preserves_richer_metric_warnings_and_null_samples(
    simulation_data_dir, monkeypatch
):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-summary-outcome-wave"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "cross_platform.topic_transfer_observed": {
                            "metric_id": "cross_platform.topic_transfer_observed",
                            "label": "Cross-Platform Topic Transfer Observed",
                            "aggregation": "flag",
                            "unit": "boolean",
                            "probability_mode": "empirical",
                            "value_kind": "binary",
                            "value": True,
                        },
                        "platform.action_balance_band": {
                            "metric_id": "platform.action_balance_band",
                            "label": "Platform Action Balance Band",
                            "aggregation": "category",
                            "unit": "category",
                            "probability_mode": "empirical",
                            "value_kind": "categorical",
                            "value": "tilted",
                        },
                        "cross_platform.topic_transfer_lag_seconds": {
                            "metric_id": "cross_platform.topic_transfer_lag_seconds",
                            "label": "Cross-Platform Topic Transfer Lag",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": 480.0,
                        },
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "cross_platform.topic_transfer_observed": {
                            "metric_id": "cross_platform.topic_transfer_observed",
                            "label": "Cross-Platform Topic Transfer Observed",
                            "aggregation": "flag",
                            "unit": "boolean",
                            "probability_mode": "empirical",
                            "value_kind": "binary",
                            "value": None,
                            "warnings": [
                                "insufficient_cross_platform_topic_transfer_evidence"
                            ],
                        },
                        "platform.action_balance_band": {
                            "metric_id": "platform.action_balance_band",
                            "value": "dominated",
                        },
                        "cross_platform.topic_transfer_lag_seconds": {
                            "metric_id": "cross_platform.topic_transfer_lag_seconds",
                            "label": "Cross-Platform Topic Transfer Lag",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": None,
                            "warnings": [
                                "insufficient_cross_platform_topic_transfer_evidence"
                            ],
                        },
                    },
                },
            },
            {
                "run_id": "0003",
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "cross_platform.topic_transfer_observed": {
                            "metric_id": "cross_platform.topic_transfer_observed",
                            "label": "Cross-Platform Topic Transfer Observed",
                            "aggregation": "flag",
                            "unit": "boolean",
                            "probability_mode": "empirical",
                            "value_kind": "binary",
                            "value": True,
                        },
                        "platform.action_balance_band": {
                            "metric_id": "platform.action_balance_band",
                            "value": "tilted",
                        },
                        "cross_platform.topic_transfer_lag_seconds": {
                            "metric_id": "cross_platform.topic_transfer_lag_seconds",
                            "label": "Cross-Platform Topic Transfer Lag",
                            "aggregation": "duration",
                            "unit": "seconds",
                            "probability_mode": "empirical",
                            "value_kind": "numeric",
                            "value": 120.0,
                        },
                    },
                },
            },
        ],
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    summary = manager.get_aggregate_summary(simulation_id, ensemble_id)

    transfer_summary = summary["metric_summaries"]["cross_platform.topic_transfer_observed"]
    band_summary = summary["metric_summaries"]["platform.action_balance_band"]
    lag_summary = summary["metric_summaries"]["cross_platform.topic_transfer_lag_seconds"]

    assert transfer_summary["distribution_kind"] == "binary"
    assert transfer_summary["sample_count"] == 2
    assert transfer_summary["null_sample_count"] == 1
    assert transfer_summary["empirical_probability"] == 1.0
    assert "undefined_samples_present" in transfer_summary["warnings"]
    assert "insufficient_cross_platform_topic_transfer_evidence" in transfer_summary["warnings"]

    assert band_summary["distribution_kind"] == "categorical"
    assert band_summary["category_counts"] == {"dominated": 1, "tilted": 2}
    assert band_summary["dominant_value"] == "tilted"

    assert lag_summary["distribution_kind"] == "continuous"
    assert lag_summary["sample_count"] == 2
    assert lag_summary["null_sample_count"] == 1
    assert lag_summary["mean"] == 300.0
    assert "insufficient_cross_platform_topic_transfer_evidence" in lag_summary["warnings"]
