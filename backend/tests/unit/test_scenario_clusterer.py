import importlib
import json
from pathlib import Path


def _load_cluster_module():
    return importlib.import_module("app.services.scenario_clusterer")


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
                "generated_at": payload.get("generated_at", f"2026-03-08T00:00:0{run_id[-1]}"),
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


def test_get_scenario_clusters_persists_deterministic_clusters_and_prototypes(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 11,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.2},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T10:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "top_topics": [{"topic": "quiet", "count": 2}],
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 2
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
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.25},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T10:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "top_topics": [{"topic": "quiet", "count": 1}],
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
                "run_id": "0003",
                "root_seed": 13,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.8},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T10:00:03",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "top_topics": [{"topic": "viral", "count": 4}],
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 18
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 10
                        ),
                    },
                },
            },
            {
                "run_id": "0004",
                "root_seed": 14,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.85},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T10:00:04",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "top_topics": [{"topic": "viral", "count": 3}],
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 20
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 12
                        ),
                    },
                },
            },
        ],
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    first = clusterer.get_scenario_clusters(simulation_id, ensemble_id)
    second = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert first == second
    assert (ensemble_dir / "scenario_clusters.json").exists()
    assert first["cluster_count"] == 2
    assert first["quality_summary"]["status"] == "complete"
    assert "thin_sample" in first["quality_summary"]["warnings"]
    assert first["feature_vector_schema"]["metric_ids"] == [
        "platform.twitter.total_actions",
        "simulation.total_actions",
    ]

    prototypes = {cluster["prototype_run_id"] for cluster in first["clusters"]}
    assert prototypes == {"0001", "0003"}
    assert {
        tuple(cluster["member_run_ids"])
        for cluster in first["clusters"]
    } == {("0001", "0002"), ("0003", "0004")}
    assert {cluster["probability_mass"] for cluster in first["clusters"]} == {0.5}
    assert all(cluster["prototype_resolved_values"] for cluster in first["clusters"])


def test_get_scenario_clusters_surfaces_missing_metrics_and_low_confidence(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-warnings"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 21,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.4},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T11:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 6
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 22,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.4},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T11:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 6
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0003",
                "root_seed": 23,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.9},
            },
        ],
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["cluster_count"] == 1
    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["quality_summary"]["missing_metrics_runs"] == ["0003"]
    assert "missing_run_metrics" in artifact["quality_summary"]["warnings"]
    assert "thin_sample" in artifact["quality_summary"]["warnings"]
    assert "low_confidence" in artifact["quality_summary"]["warnings"]
    assert artifact["clusters"][0]["probability_mass"] == 2 / 3
    assert artifact["clusters"][0]["warnings"] == ["low_metric_variance"]


def test_get_scenario_clusters_excludes_partial_metrics_from_cluster_membership(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-partial"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "root_seed": 31,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.2},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T12:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 2
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 1
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "root_seed": 32,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.8},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T12:00:02",
                    "quality_checks": {"status": "partial", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 18
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 10
                        ),
                    },
                },
            },
            {
                "run_id": "0003",
                "root_seed": 33,
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.9},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T12:00:03",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 20
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 12
                        ),
                    },
                },
            },
        ],
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["quality_summary"]["degraded_metrics_runs"] == ["0002"]
    assert "degraded_run_metrics" in artifact["quality_summary"]["warnings"]
    assert {
        cluster["prototype_run_id"] for cluster in artifact["clusters"]
    } == {"0001", "0003"}
    assert all(cluster["probability_mass"] == 1 / 3 for cluster in artifact["clusters"])


def test_get_scenario_clusters_reports_no_shared_numeric_metrics(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-no-shared-metrics"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T13:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 4
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T13:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 9
                        ),
                    },
                },
            },
        ],
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["cluster_count"] == 0
    assert artifact["feature_vector_schema"]["metric_ids"] == []
    assert artifact["quality_summary"]["status"] == "partial"
    assert "no_shared_numeric_metrics" in artifact["quality_summary"]["warnings"]


def test_get_scenario_clusters_downgrades_malformed_metrics_to_warning(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-malformed"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T14:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 4
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T14:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 8
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 4
                        ),
                    },
                },
            },
        ],
    )

    malformed_path = (
        ensemble_dir / "runs" / "run_0002" / "metrics.json"
    )
    malformed_path.write_text("{not-valid-json", encoding="utf-8")

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["cluster_count"] == 1
    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["quality_summary"]["invalid_metrics_runs"] == ["0002"]
    assert "invalid_run_metrics" in artifact["quality_summary"]["warnings"]


def test_get_scenario_clusters_downgrades_structural_metrics_and_manifest_errors(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-invalid-shapes"
    ensemble_id = "0001"
    ensemble_dir = _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.2},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T15:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 4
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.4},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T15:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 6
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 3
                        ),
                    },
                },
            },
            {
                "run_id": "0003",
                "resolved_values": {"twitter_config.echo_chamber_strength": 0.9},
                "metrics_payload": {
                    "extracted_at": "2026-03-08T15:00:03",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 10
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 8
                        ),
                    },
                },
            },
        ],
    )

    (ensemble_dir / "runs" / "run_0002" / "metrics.json").write_text(
        "[]",
        encoding="utf-8",
    )
    (ensemble_dir / "runs" / "run_0003" / "run_manifest.json").write_text(
        "{broken-manifest",
        encoding="utf-8",
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["quality_summary"]["invalid_metrics_runs"] == ["0002"]
    assert artifact["quality_summary"]["invalid_manifest_runs"] == ["0003"]
    assert "invalid_run_metrics" in artifact["quality_summary"]["warnings"]
    assert "invalid_run_manifest" in artifact["quality_summary"]["warnings"]
    assert artifact["cluster_count"] == 2


def test_get_scenario_clusters_warns_when_feature_space_shrinks(
    simulation_data_dir, monkeypatch
):
    cluster_module = _load_cluster_module()
    monkeypatch.setattr(
        cluster_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    simulation_id = "sim-clusters-shrunk-space"
    ensemble_id = "0001"
    _write_ensemble_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_payloads=[
            {
                "run_id": "0001",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T16:00:01",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 4
                        ),
                        "platform.twitter.total_actions": _metric_entry(
                            "platform.twitter.total_actions", 2
                        ),
                    },
                },
            },
            {
                "run_id": "0002",
                "metrics_payload": {
                    "extracted_at": "2026-03-08T16:00:02",
                    "quality_checks": {"status": "complete", "run_status": "completed"},
                    "metric_values": {
                        "simulation.total_actions": _metric_entry(
                            "simulation.total_actions", 10
                        ),
                    },
                },
            },
        ],
    )

    clusterer = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = clusterer.get_scenario_clusters(simulation_id, ensemble_id)

    assert artifact["quality_summary"]["status"] == "partial"
    assert artifact["feature_vector_schema"]["metric_ids"] == [
        "simulation.total_actions"
    ]
    assert "partial_feature_space" in artifact["quality_summary"]["warnings"]
