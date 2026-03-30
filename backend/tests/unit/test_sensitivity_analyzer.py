import importlib
import json
from pathlib import Path


def _load_sensitivity_module():
    return importlib.import_module("app.services.sensitivity_analyzer")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _metric_entry(metric_id: str, value: int) -> dict:
    return {
        "metric_id": metric_id,
        "label": metric_id,
        "aggregation": "count",
        "unit": "count",
        "probability_mode": "empirical",
        "value": value,
    }


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
            "outcome_metric_ids": [
                "platform.twitter.total_actions",
                "simulation.total_actions",
            ],
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
                "resolved_values": payload.get("resolved_values", {}),
                "config_artifact": "resolved_config.json",
                "artifact_paths": {"resolved_config": "resolved_config.json"},
                "generated_at": payload.get("generated_at", f"2026-03-09T00:00:0{run_id[-1]}"),
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
                "sampled_values": payload.get("resolved_values", {}),
            },
        )
        metrics_payload = payload.get("metrics_payload")
        if metrics_payload is not None:
            _write_json(run_dir / "metrics.json", metrics_payload)

    return ensemble_dir


def test_get_sensitivity_analysis_persists_ranked_driver_effects(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 11,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.2,
                    "agent_configs[0].activity_level": 0.1,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T10:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 3
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 1
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 12,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.2,
                    "agent_configs[0].activity_level": 0.9,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T10:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 9
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 4
                        ),
                    },
                },
            },
            {
                "run_id": "0003",
                "root_seed": 13,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.8,
                    "agent_configs[0].activity_level": 0.1,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T10:00:03",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 11
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 8
                        ),
                    },
                },
            },
            {
                "run_id": "0004",
                "root_seed": 14,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.8,
                    "agent_configs[0].activity_level": 0.9,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T10:00:04",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 19
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 16
                        ),
                    },
                },
            },
        ],
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    first = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)
    second = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    assert first == second
    assert (ensemble_dir / "sensitivity.json").exists()
    timing_payload = json.loads(
        (ensemble_dir / "ensemble_phase_timings.json").read_text(encoding="utf-8")
    )
    assert timing_payload["scope_kind"] == "ensemble"
    assert timing_payload["scope_id"] == f"{simulation_id}::{ensemble_id}"
    assert "sensitivity" in timing_payload["phases"]
    assert first["artifact_type"] == "sensitivity"
    assert first["methodology"]["analysis_mode"] == "observational_resolved_values"
    assert first["methodology"]["grouping_policy"] == "support_aware_driver_bands"
    assert first["methodology"]["ranking_basis"] == "support_aware_standardized_effect_sum"
    assert first["sample_policy"]["analysis_mode"] == "sensitivity"
    assert first["quality_summary"]["status"] == "complete"
    assert "observational_only" in first["quality_summary"]["warnings"]
    assert "thin_sample" in first["quality_summary"]["warnings"]
    assert [driver["driver_id"] for driver in first["driver_rankings"]] == [
        "twitter_config.echo_chamber_strength",
        "agent_configs[0].activity_level",
    ]
    assert (
        first["driver_rankings"][0]["overall_effect_score"]
        > first["driver_rankings"][1]["overall_effect_score"]
    )
    top_driver = first["driver_rankings"][0]
    assert top_driver["driver_kind"] == "numeric"
    assert top_driver["sample_count"] == 4
    assert top_driver["distinct_value_count"] == 2
    assert top_driver["driver_summary"]["semantics"] == "observational"
    assert top_driver["driver_summary"]["top_metric_id"] == (
        "platform.twitter.total_actions"
    )
    assert top_driver["driver_summary"]["ranking_basis"] == (
        "support_aware_standardized_effect_sum"
    )
    impact = next(
        item
        for item in top_driver["metric_impacts"]
        if item["metric_id"] == "simulation.total_actions"
    )
    assert impact["effect_size"] == 9.0
    assert impact["standardized_effect"] > 0
    assert [group["value_label"] for group in impact["group_summaries"]] == ["0.2", "0.8"]
    assert [group["mean"] for group in impact["group_summaries"]] == [6.0, 15.0]
    assert all(group["support_count"] == 2 for group in impact["group_summaries"])
    assert all(group["minimum_support_met"] is True for group in impact["group_summaries"])


def test_get_sensitivity_analysis_surfaces_missing_metrics_and_non_varying_drivers(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity-warnings"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 21,
                "resolved_values": {"agent_configs[0].activity_level": 0.5},
                "metrics_payload": {
                    "extracted_at": "2026-03-09T11:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 5
                        )
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 22,
                "resolved_values": {"agent_configs[0].activity_level": 0.5},
                "metrics_payload": {
                    "extracted_at": "2026-03-09T11:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 5
                        )
                    },
                },
            },
            {
                "run_id": "0003",
                "root_seed": 23,
                "resolved_values": {"agent_configs[0].activity_level": 0.5},
            },
        ],
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["quality_summary"]["missing_metrics_runs"] == ["0003"]
    assert "missing_run_metrics" in artifact["quality_summary"]["warnings"]


def test_get_sensitivity_analysis_surfaces_scenario_diversity_context(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity-diversity"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 41,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.2,
                    "agent_configs[0].activity_level": 0.1,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T11:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry("simulation.total_actions", 4),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 42,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.8,
                    "agent_configs[0].activity_level": 0.9,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T11:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry("simulation.total_actions", 18),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 12
                        ),
                    },
                },
            },
        ],
    )
    _write_json(
        ensemble_dir / "scenario_clusters.json",
        {
            "artifact_type": "scenario_clusters",
            "clusters": [
                {"cluster_id": "cluster_0001", "member_run_ids": ["0001"]},
                {"cluster_id": "cluster_0002", "member_run_ids": ["0002"]},
            ],
            "diversity_diagnostics": {
                "coverage_metrics": {
                    "template_coverage_fraction": 0.5,
                    "coverage_tag_fraction": 0.5,
                },
                "distance_metrics": {
                    "mean_pairwise_distance": 2.1,
                    "min_pairwise_distance": 2.1,
                    "max_pairwise_distance": 2.1,
                },
                "support_metrics": {
                    "cluster_count": 2,
                    "minimum_cluster_support": 1,
                    "low_support_cluster_count": 2,
                },
                "warnings": ["limited_template_coverage", "low_scenario_support"],
            },
        },
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    assert artifact["scenario_diversity_context"]["coverage_metrics"][
        "template_coverage_fraction"
    ] == 0.5
    assert artifact["scenario_diversity_context"]["warnings"] == [
        "limited_template_coverage",
        "low_scenario_support",
    ]
    assert "limited_scenario_diversity" in artifact["quality_summary"]["warnings"]
    assert "no_varying_drivers" in artifact["quality_summary"]["warnings"]
    assert "thin_sample" in artifact["quality_summary"]["warnings"]
    assert artifact["quality_summary"]["support_assessment"] == {
        "status": "descriptive_only",
        "label": "Descriptive only",
        "downgraded": True,
        "decision_support_ready": False,
        "reason": "Thin-sample warnings limit observational rankings to descriptive use only.",
        "warnings": ["thin_sample"],
    }


def test_get_sensitivity_analysis_surfaces_scenario_diversity_context(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity-diversity"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 41,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.2,
                    "agent_configs[0].activity_level": 0.1,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T14:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 3
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 1
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 42,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.8,
                    "agent_configs[0].activity_level": 0.9,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T14:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 21
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 15
                        ),
                    },
                },
            },
            {
                "run_id": "0003",
                "root_seed": 43,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.85,
                    "agent_configs[0].activity_level": 0.7,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T14:00:03",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 19
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 13
                        ),
                    },
                },
            },
            {
                "run_id": "0004",
                "root_seed": 44,
                "resolved_values": {
                    "twitter_config.echo_chamber_strength": 0.25,
                    "agent_configs[0].activity_level": 0.2,
                },
                "metrics_payload": {
                    "extracted_at": "2026-03-09T14:00:04",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 5
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
        ],
    )
    _write_json(
        ensemble_dir / "scenario_clusters.json",
        {
            "artifact_type": "scenario_clusters",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "diversity_diagnostics": {
                "coverage_metrics": {
                    "planned_template_count": 3,
                    "observed_template_count": 2,
                    "planned_templates_missing_from_observed": ["bridge-response"],
                    "template_coverage_ratio": 2 / 3,
                },
                "scenario_distance_metrics": {
                    "pairwise_distance_mean": 1.5,
                    "pairwise_distance_max": 3.2,
                },
                "support_metrics": {
                    "minimum_support_count": 2,
                    "singleton_cluster_count": 0,
                },
                "warnings": ["limited_template_coverage"],
            },
            "clusters": [],
        },
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    assert artifact["scenario_diversity_context"] == {
        "template_coverage_ratio": 2 / 3,
        "pairwise_distance_mean": 1.5,
        "pairwise_distance_max": 3.2,
        "minimum_support_count": 2,
        "warnings": ["limited_template_coverage"],
    }
    assert artifact["driver_rankings"] == []


def test_get_sensitivity_analysis_bands_continuous_drivers_instead_of_exact_identity(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity-bands"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "resolved_values": {"agent_configs[0].activity_level": 0.10},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 2)}},
            },
            {
                "run_id": "0002",
                "resolved_values": {"agent_configs[0].activity_level": 0.20},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 3)}},
            },
            {
                "run_id": "0003",
                "resolved_values": {"agent_configs[0].activity_level": 0.30},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 4)}},
            },
            {
                "run_id": "0004",
                "resolved_values": {"agent_configs[0].activity_level": 0.70},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 10)}},
            },
            {
                "run_id": "0005",
                "resolved_values": {"agent_configs[0].activity_level": 0.80},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 12)}},
            },
            {
                "run_id": "0006",
                "resolved_values": {"agent_configs[0].activity_level": 0.90},
                "metrics_payload": {"quality_checks": {"status": "complete", "run_status": "completed"}, "metric_values": {"simulation.total_actions": _metric_entry("simulation.total_actions", 14)}},
            },
        ],
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    driver = artifact["driver_rankings"][0]
    impact = next(
        item for item in driver["metric_impacts"] if item["metric_id"] == "simulation.total_actions"
    )
    assert driver["distinct_value_count"] == 6
    assert len(impact["group_summaries"]) == 3
    assert [group["support_count"] for group in impact["group_summaries"]] == [2, 2, 2]


def test_get_sensitivity_analysis_marks_minimum_support_rankings_as_insufficient(
    simulation_data_dir, monkeypatch
):
    sensitivity_module = _load_sensitivity_module()
    monkeypatch.setattr(
        sensitivity_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-sensitivity-min-support"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "resolved_values": {"agent_configs[0].activity_level": "low"},
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry("simulation.total_actions", 2),
                        "platform.twitter.total_actions": _metric_entry("platform.twitter.total_actions", 1),
                    },
                },
            },
            {
                "run_id": "0002",
                "resolved_values": {"agent_configs[0].activity_level": "low"},
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry("simulation.total_actions", 4),
                        "platform.twitter.total_actions": _metric_entry("platform.twitter.total_actions", 2),
                    },
                },
            },
            {
                "run_id": "0003",
                "resolved_values": {"agent_configs[0].activity_level": "high"},
                "metrics_payload": {
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry("simulation.total_actions", 12),
                        "platform.twitter.total_actions": _metric_entry("platform.twitter.total_actions", 8),
                    },
                },
            },
        ],
    )

    analyzer = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = analyzer.get_sensitivity_analysis(simulation_id, ensemble_id)

    driver = artifact["driver_rankings"][0]
    impact = next(
        item for item in driver["metric_impacts"] if item["metric_id"] == "simulation.total_actions"
    )

    assert "minimum_support_not_met" in driver["warnings"]
    assert "minimum_support_not_met" in impact["warnings"]
    assert driver["support_assessment"] == {
        "status": "insufficient_support",
        "label": "Insufficient support",
        "downgraded": True,
        "decision_support_ready": False,
        "reason": "Minimum support was not met, so this observational ranking cannot support strong driver language.",
        "warnings": ["minimum_support_not_met"],
    }
    assert impact["support_assessment"] == {
        "status": "insufficient_support",
        "label": "Insufficient support",
        "downgraded": True,
        "decision_support_ready": False,
        "reason": "Minimum support was not met, so this observational ranking cannot support strong driver language.",
        "warnings": ["minimum_support_not_met"],
    }
