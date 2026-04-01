import importlib
import json
from pathlib import Path


def _load_outcome_module():
    return importlib.import_module("app.services.outcome_extractor")


def _load_cluster_module():
    return importlib.import_module("app.services.scenario_clusterer")


def _load_sensitivity_module():
    return importlib.import_module("app.services.sensitivity_analyzer")


def _load_market_extractor_module():
    return importlib.import_module("app.services.simulation_market_extractor")


def _load_market_aggregator_module():
    return importlib.import_module("app.services.simulation_market_aggregator")


def _load_forecasting_module():
    return importlib.import_module("app.models.forecasting")


def _load_forecast_manager_module():
    return importlib.import_module("app.services.forecast_manager")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def _metric_entry(metric_id: str, value: int) -> dict:
    return {
        "metric_id": metric_id,
        "label": metric_id,
        "aggregation": "count",
        "unit": "count",
        "probability_mode": "empirical",
        "value": value,
    }


def _create_workspace(
    forecast_data_dir: Path,
    monkeypatch,
    *,
    forecast_id: str,
    simulation_id: str,
):
    manager_module = _load_forecast_manager_module()
    forecasting_module = _load_forecasting_module()
    monkeypatch.setattr(
        manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )
    manager = manager_module.ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        forecasting_module.ForecastQuestion.from_dict(
            {
                "forecast_id": forecast_id,
                "project_id": "proj-1",
                "title": "Structured analytics forecast",
                "question": "Will support exceed 55%?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-31T09:00:00",
                "created_at": "2026-03-31T09:00:00",
                "updated_at": "2026-03-31T09:00:00",
                "primary_simulation_id": simulation_id,
            }
        )
    )
    manager.attach_simulation_scope(
        forecast_id,
        simulation_id=simulation_id,
        ensemble_ids=["0001"],
        run_ids=["0001", "0002", "0003", "0004"],
        latest_ensemble_id="0001",
        latest_run_id="0001",
        source_stage="test_scope_attach",
    )


def _seed_run(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    run_id: str,
    total_actions: int,
    twitter_actions: int,
    initial_probability: float,
    revised_probability: float,
    structural_option_id: str,
    structural_option_label: str,
    primary_regime: str,
    narrative_family: str,
    topics: list[str],
):
    run_dir = (
        simulation_data_dir
        / simulation_id
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / f"run_{run_id}"
    )
    _write_json(
        run_dir / "resolved_config.json",
        {
            "artifact_type": "resolved_config",
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": run_id,
            "time_config": {"total_simulation_hours": 12, "minutes_per_round": 60},
            "event_config": {"hot_topics": topics},
            "structural_resolutions": [
                {
                    "uncertainty_id": "moderation_policy_change",
                    "kind": "moderation_policy_change",
                    "option_id": structural_option_id,
                    "option_label": structural_option_label,
                }
            ],
        },
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": run_id,
            "status": "completed",
            "generated_at": f"2026-03-31T10:0{run_id[-1]}:00",
            "updated_at": f"2026-03-31T10:0{run_id[-1]}:00",
            "resolved_values": {"twitter_config.echo_chamber_strength": total_actions / 20},
            "config_artifact": "resolved_config.json",
            "artifact_paths": {"resolved_config": "resolved_config.json"},
            "experiment_design_row": {
                "run_id": run_id,
                "structural_assignments": [
                    {
                        "uncertainty_id": "moderation_policy_change",
                        "option_id": structural_option_id,
                        "option_label": structural_option_label,
                    }
                ],
            },
            "structural_resolutions": [
                {
                    "uncertainty_id": "moderation_policy_change",
                    "kind": "moderation_policy_change",
                    "option_id": structural_option_id,
                    "option_label": structural_option_label,
                    "runtime_transition_hints": ["claim"],
                }
            ],
            "assumption_ledger": {
                "applied_templates": [primary_regime],
                "structural_uncertainties": [
                    {
                        "uncertainty_id": "moderation_policy_change",
                        "kind": "moderation_policy_change",
                        "option_id": structural_option_id,
                        "option_label": structural_option_label,
                    }
                ],
                "structural_runtime_transition_types": ["claim"],
                "assumption_statements": [f"Assume {structural_option_label.lower()}."],
            },
        },
    )
    _write_json(
        run_dir / "run_state.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": run_id,
            "run_key": f"{simulation_id}::0001::{run_id}",
            "run_dir": str(run_dir),
            "config_path": str(run_dir / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-31T09:55:00",
            "updated_at": "2026-03-31T10:10:00",
            "completed_at": "2026-03-31T10:10:00",
        },
    )
    _write_json(
        run_dir / "runtime_graph_state.json",
        {
            "artifact_type": "runtime_graph_state",
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "run_id": run_id,
            "project_id": "proj-1",
            "base_graph_id": "graph-1",
            "runtime_graph_id": f"runtime-{run_id}",
            "transition_count": 3,
            "transition_counts": {
                "event": 0,
                "claim": 3,
                "exposure": 0,
                "belief_update": 0,
                "topic_shift": 0,
                "intervention": 0,
                "round_state": 0,
            },
            "current_round": 2,
            "active_topics": topics,
        },
    )
    _write_jsonl(
        run_dir / "runtime_graph_updates.jsonl",
        [
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": f"rts-{run_id}-1",
                "transition_type": "claim",
                "simulation_id": simulation_id,
                "ensemble_id": "0001",
                "run_id": run_id,
                "project_id": "proj-1",
                "base_graph_id": "graph-1",
                "runtime_graph_id": f"runtime-{run_id}",
                "platform": "twitter",
                "round_num": 1,
                "timestamp": "2026-03-31T10:00:00",
                "recorded_at": "2026-03-31T10:00:00",
                "agent": {"agent_id": 1, "agent_name": "Analyst A"},
                "payload": {
                    "action_type": "CREATE_POST",
                    "action_args": {
                        "content": f"Initial view is {int(initial_probability * 100)}%.",
                        "forecast_probability": initial_probability,
                        "rationale_tags": topics,
                    },
                    "topics": topics,
                },
                "provenance": {
                    "citation_ids": [f"cit-{run_id}-1"],
                    "source_unit_ids": [f"unit-{run_id}-1"],
                    "graph_object_uuids": [f"claim-{run_id}-1"],
                },
                "source_artifact": "runtime_graph_updates.jsonl",
                "human_readable": "Initial belief",
            },
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": f"rts-{run_id}-2",
                "transition_type": "claim",
                "simulation_id": simulation_id,
                "ensemble_id": "0001",
                "run_id": run_id,
                "project_id": "proj-1",
                "base_graph_id": "graph-1",
                "runtime_graph_id": f"runtime-{run_id}",
                "platform": "twitter",
                "round_num": 2,
                "timestamp": "2026-03-31T10:05:00",
                "recorded_at": "2026-03-31T10:05:00",
                "agent": {"agent_id": 1, "agent_name": "Analyst A"},
                "payload": {
                    "action_type": "QUOTE_POST",
                    "action_args": {
                        "content": f"Revision to {int(revised_probability * 100)}%.",
                        "forecast_probability": revised_probability,
                        "rationale_tags": topics,
                    },
                    "topics": topics,
                },
                "provenance": {
                    "citation_ids": [f"cit-{run_id}-1"],
                    "source_unit_ids": [f"unit-{run_id}-1"],
                    "graph_object_uuids": [f"claim-{run_id}-1"],
                },
                "source_artifact": "runtime_graph_updates.jsonl",
                "human_readable": "Revision",
            },
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": f"rts-{run_id}-3",
                "transition_type": "claim",
                "simulation_id": simulation_id,
                "ensemble_id": "0001",
                "run_id": run_id,
                "project_id": "proj-1",
                "base_graph_id": "graph-1",
                "runtime_graph_id": f"runtime-{run_id}",
                "platform": "reddit",
                "round_num": 2,
                "timestamp": "2026-03-31T10:06:00",
                "recorded_at": "2026-03-31T10:06:00",
                "agent": {"agent_id": 2, "agent_name": "Analyst B"},
                "payload": {
                    "action_type": "CREATE_POST",
                    "action_args": {
                        "content": "Counterpoint at 40%.",
                        "forecast_probability": 0.4,
                        "rationale_tags": topics,
                    },
                    "topics": topics,
                },
                "provenance": {
                    "citation_ids": [f"cit-{run_id}-2"],
                    "source_unit_ids": [f"unit-{run_id}-2"],
                    "graph_object_uuids": [f"claim-{run_id}-2"],
                },
                "source_artifact": "runtime_graph_updates.jsonl",
                "human_readable": "Counterpoint",
            },
        ],
    )
    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-31T10:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "CREATE_POST",
                "action_args": {"content": "Initial view", "topics": topics},
                "success": True,
            },
            {
                "round": 2,
                "timestamp": "2026-03-31T10:05:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "QUOTE_POST",
                "action_args": {"content": "Revision", "topics": topics},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-31T10:10:00",
                "platform": "twitter",
                "total_rounds": 2,
                "total_actions": twitter_actions,
            },
        ],
    )
    _write_jsonl(
        run_dir / "reddit" / "actions.jsonl",
        [
            {
                "round": 2,
                "timestamp": "2026-03-31T10:06:00",
                "platform": "reddit",
                "agent_id": 2,
                "agent_name": "Analyst B",
                "action_type": "CREATE_POST",
                "action_args": {"content": "Counterpoint", "topics": topics},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-31T10:11:00",
                "platform": "reddit",
                "total_rounds": 2,
                "total_actions": total_actions - twitter_actions,
            },
        ],
    )


def test_structured_analytics_flow_persists_richer_run_and_ensemble_artifacts(
    simulation_data_dir,
    forecast_data_dir,
    monkeypatch,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )

    simulation_id = "sim-analytics-integration"
    forecast_id = "forecast-analytics-integration"
    ensemble_dir = simulation_data_dir / simulation_id / "ensemble" / "ensemble_0001"

    _write_json(
        simulation_data_dir / simulation_id / "state.json",
        {
            "simulation_id": simulation_id,
            "project_id": "proj-1",
            "graph_id": "graph-1",
            "forecast_id": forecast_id,
            "status": "ready",
            "created_at": "2026-03-31T09:00:00",
            "updated_at": "2026-03-31T09:00:00",
        },
    )
    _write_json(
        ensemble_dir / "ensemble_state.json",
        {
            "artifact_type": "ensemble_state",
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "status": "prepared",
            "run_count": 4,
            "prepared_run_count": 4,
            "run_ids": ["0001", "0002", "0003", "0004"],
            "outcome_metric_ids": [
                "simulation.total_actions",
                "platform.twitter.total_actions",
            ],
        },
    )
    _write_json(
        ensemble_dir / "experiment_design.json",
        {
            "artifact_type": "experiment_design",
            "simulation_id": simulation_id,
            "ensemble_id": "0001",
            "structural_uncertainty_catalog": [
                {
                    "uncertainty_id": "moderation_policy_change",
                    "kind": "moderation_policy_change",
                    "option_ids": ["status_quo", "tightened_enforcement"],
                }
            ],
            "rows": [
                {
                    "run_id": "0001",
                    "structural_assignments": [
                        {
                            "uncertainty_id": "moderation_policy_change",
                            "option_id": "status_quo",
                        }
                    ],
                },
                {
                    "run_id": "0002",
                    "structural_assignments": [
                        {
                            "uncertainty_id": "moderation_policy_change",
                            "option_id": "status_quo",
                        }
                    ],
                },
                {
                    "run_id": "0003",
                    "structural_assignments": [
                        {
                            "uncertainty_id": "moderation_policy_change",
                            "option_id": "tightened_enforcement",
                        }
                    ],
                },
                {
                    "run_id": "0004",
                    "structural_assignments": [
                        {
                            "uncertainty_id": "moderation_policy_change",
                            "option_id": "tightened_enforcement",
                        }
                    ],
                },
            ],
        },
    )
    _create_workspace(
        forecast_data_dir,
        monkeypatch,
        forecast_id=forecast_id,
        simulation_id=simulation_id,
    )

    _seed_run(
        simulation_data_dir,
        simulation_id,
        run_id="0001",
        total_actions=3,
        twitter_actions=2,
        initial_probability=0.7,
        revised_probability=0.6,
        structural_option_id="status_quo",
        structural_option_label="Status quo",
        primary_regime="baseline-watch",
        narrative_family="rates+labor",
        topics=["rates", "labor"],
    )
    _seed_run(
        simulation_data_dir,
        simulation_id,
        run_id="0002",
        total_actions=5,
        twitter_actions=3,
        initial_probability=0.68,
        revised_probability=0.58,
        structural_option_id="status_quo",
        structural_option_label="Status quo",
        primary_regime="baseline-watch",
        narrative_family="rates+labor",
        topics=["rates", "labor"],
    )
    _seed_run(
        simulation_data_dir,
        simulation_id,
        run_id="0003",
        total_actions=11,
        twitter_actions=8,
        initial_probability=0.62,
        revised_probability=0.52,
        structural_option_id="tightened_enforcement",
        structural_option_label="Tightened enforcement",
        primary_regime="viral-spike",
        narrative_family="inflation+credibility",
        topics=["inflation", "credibility"],
    )
    _seed_run(
        simulation_data_dir,
        simulation_id,
        run_id="0004",
        total_actions=13,
        twitter_actions=10,
        initial_probability=0.6,
        revised_probability=0.5,
        structural_option_id="tightened_enforcement",
        structural_option_label="Tightened enforcement",
        primary_regime="viral-spike",
        narrative_family="inflation+credibility",
        topics=["inflation", "credibility"],
    )

    outcome_module = _load_outcome_module()
    cluster_module = _load_cluster_module()
    sensitivity_module = _load_sensitivity_module()
    market_extractor_module = _load_market_extractor_module()
    market_aggregator_module = _load_market_aggregator_module()

    extractor = outcome_module.OutcomeExtractor(
        simulation_data_dir=str(simulation_data_dir)
    )
    for run_id in ("0001", "0002", "0003", "0004"):
        extractor.persist_run_metrics(
            simulation_id,
            ensemble_id="0001",
            run_id=run_id,
        )

    clusters = cluster_module.ScenarioClusterer(
        simulation_data_dir=str(simulation_data_dir)
    ).get_scenario_clusters(simulation_id, "0001")
    sensitivity = sensitivity_module.SensitivityAnalyzer(
        simulation_data_dir=str(simulation_data_dir)
    ).get_sensitivity_analysis(simulation_id, "0001")
    market_artifacts = market_extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    ).persist_run_market_artifacts(
        simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )
    market_summary = market_aggregator_module.SimulationMarketAggregator(
        simulation_data_dir=str(simulation_data_dir)
    ).summarize_run_market_artifacts(
        simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )

    run_one_dir = ensemble_dir / "runs" / "run_0001"
    metrics_payload = json.loads((run_one_dir / "metrics.json").read_text(encoding="utf-8"))

    assert metrics_payload["trajectory_summary"]["structured_runtime_used"] is True
    assert metrics_payload["belief_summary"]["belief_regime"]
    assert clusters["clusters"][0]["family_signature"]["regime_markers"]
    assert sensitivity["designed_comparisons"]
    assert market_artifacts["manifest"]["structured_runtime_used"] is True
    assert market_summary["signals"]["belief_trajectory"]["value"]["trend"] == "downward"
