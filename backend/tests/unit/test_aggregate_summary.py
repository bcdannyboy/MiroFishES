import importlib
import json
from pathlib import Path


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
    assert "thin_sample" in metric_summary["warnings"]
    assert "degraded_runs_present" in metric_summary["warnings"]
    assert summary["quality_summary"]["partial_runs"] == 1
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

    assert categorical_summary["distribution_kind"] == "categorical"
    assert categorical_summary["sample_count"] == 3
    assert categorical_summary["category_counts"] == {"alpha": 2, "beta": 1}
    assert categorical_summary["category_probabilities"] == {
        "alpha": 2 / 3,
        "beta": 1 / 3,
    }
