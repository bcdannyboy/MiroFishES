import importlib
import json
from pathlib import Path


def _load_forecasting_module():
    return importlib.import_module("app.models.forecasting")


def _load_forecast_manager_module():
    return importlib.import_module("app.services.forecast_manager")


def _load_extractor_module():
    return importlib.import_module("app.services.simulation_market_extractor")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def _write_simulation_state(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    forecast_id: str | None,
) -> None:
    _write_json(
        simulation_data_dir / simulation_id / "state.json",
        {
            "simulation_id": simulation_id,
            "project_id": "proj-1",
            "graph_id": "graph-1",
            "forecast_id": forecast_id,
            "base_graph_id": "graph-1",
            "runtime_graph_id": None,
            "enable_twitter": True,
            "enable_reddit": True,
            "status": "ready",
            "entities_count": 3,
            "profiles_count": 3,
            "entity_types": ["Person"],
            "config_generated": True,
            "config_reasoning": "",
            "current_round": 0,
            "twitter_status": "not_started",
            "reddit_status": "not_started",
            "created_at": "2026-03-30T10:00:00",
            "updated_at": "2026-03-30T10:00:00",
            "error": None,
        },
    )


def _write_run_root(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    ensemble_id: str = "0001",
    run_id: str = "0001",
) -> Path:
    run_dir = simulation_data_dir / simulation_id / "ensemble" / f"ensemble_{ensemble_id}" / "runs" / f"run_{run_id}"
    _write_json(
        run_dir / "resolved_config.json",
        {
            "artifact_type": "resolved_config",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "time_config": {"total_simulation_hours": 12, "minutes_per_round": 60},
            "event_config": {"hot_topics": ["rates", "inflation"]},
        },
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "status": "completed",
            "generated_at": "2026-03-30T10:10:00",
            "updated_at": "2026-03-30T10:10:00",
            "config_artifact": "resolved_config.json",
            "artifact_paths": {"resolved_config": "resolved_config.json"},
        },
    )
    _write_json(
        run_dir / "run_state.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "run_key": f"{simulation_id}::{ensemble_id}::{run_id}",
            "run_dir": str(run_dir),
            "config_path": str(run_dir / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-30T09:55:00",
            "updated_at": "2026-03-30T10:10:00",
            "completed_at": "2026-03-30T10:10:00",
        },
    )
    return run_dir


def _create_workspace(
    forecast_data_dir: Path,
    monkeypatch,
    *,
    forecast_id: str,
    simulation_id: str,
    question_type: str,
    question_spec: dict | None = None,
):
    manager_module = _load_forecast_manager_module()
    forecasting_module = _load_forecasting_module()
    monkeypatch.setattr(
        manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )
    manager = manager_module.ForecastManager(forecast_data_dir=str(forecast_data_dir))
    workspace = manager.create_question(
        forecasting_module.ForecastQuestion.from_dict(
            {
                "forecast_id": forecast_id,
                "project_id": "proj-1",
                "title": f"{question_type.title()} question",
                "question": "Will the policy rate move lower by June?",
                "question_type": question_type,
                "question_spec": question_spec or {},
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
                "primary_simulation_id": simulation_id,
            }
        )
    )
    return manager.attach_simulation_scope(
        forecast_id,
        simulation_id=simulation_id,
        ensemble_ids=["0001"],
        run_ids=["0001"],
        latest_ensemble_id="0001",
        latest_run_id="0001",
        source_stage="test_scope_attach",
    )


def test_persist_run_market_artifacts_extracts_binary_beliefs_and_updates(
    simulation_data_dir, forecast_data_dir, monkeypatch
):
    extractor_module = _load_extractor_module()
    simulation_id = "sim-market-binary"
    forecast_id = "forecast-market-binary"
    run_dir = _write_run_root(simulation_data_dir, simulation_id)
    _write_simulation_state(simulation_data_dir, simulation_id, forecast_id=forecast_id)
    _create_workspace(
        forecast_data_dir,
        monkeypatch,
        forecast_id=forecast_id,
        simulation_id=simulation_id,
        question_type="binary",
    )

    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-30T10:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "CREATE_POST",
                "action_args": {
                    "content": "I put this near 70% after the payroll surprise.",
                    "forecast_probability": 0.7,
                    "confidence": 0.62,
                    "rationale_tags": ["base_rate", "labor"],
                    "missing_information_requests": ["Need CPI print"],
                },
                "success": True,
            },
            {
                "round": 2,
                "timestamp": "2026-03-30T10:05:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "QUOTE_POST",
                "action_args": {
                    "content": "Revising to 65% after the counterargument.",
                    "forecast_probability": 0.65,
                    "confidence": 0.58,
                    "rationale_tags": ["counterargument", "labor"],
                },
                "success": True,
            },
        ],
    )
    _write_jsonl(
        run_dir / "reddit" / "actions.jsonl",
        [
            {
                "round": 2,
                "timestamp": "2026-03-30T10:06:00",
                "platform": "reddit",
                "agent_id": 2,
                "agent_name": "Analyst B",
                "action_type": "CREATE_POST",
                "action_args": {
                    "content": "Closer to 40% given sticky services inflation.",
                    "forecast_probability": "40%",
                    "confidence": "low",
                    "rationale_tags": ["inflation", "services"],
                    "missing_information": ["Need wage-growth revision"],
                },
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-30T10:10:00",
                "platform": "reddit",
                "total_rounds": 2,
                "total_actions": 1,
            },
        ],
    )

    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    artifacts = extractor.persist_run_market_artifacts(
        simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )

    assert artifacts["manifest"]["extraction_status"] == "ready"
    assert artifacts["manifest"]["forecast_id"] == forecast_id
    assert artifacts["manifest"]["supported_question_type"] is True
    assert artifacts["manifest"]["scope_linked_to_run"] is True
    assert artifacts["market_snapshot"]["synthetic_consensus_probability"] == 0.525
    assert artifacts["market_snapshot"]["participating_agent_count"] == 2
    assert artifacts["disagreement_summary"]["judgment_count"] == 3
    assert artifacts["disagreement_summary"]["disagreement_index"] > 0
    assert artifacts["belief_update_trace"]["updates"][1]["agent_id"] == 1
    assert artifacts["belief_update_trace"]["updates"][1]["previous_probability"] == 0.7
    assert artifacts["agent_belief_book"]["beliefs"][0]["agent_name"] == "Analyst A"
    assert artifacts["agent_belief_book"]["beliefs"][0]["probability"] == 0.65
    assert artifacts["missing_information_signals"]["signals"][0]["request"] == "Need CPI print"
    assert any(
        item["tag"] == "labor" and item["count"] == 2
        for item in artifacts["argument_map"]["tags"]
    )

    manifest_path = run_dir / "simulation_market_manifest.json"
    snapshot_path = run_dir / "market_snapshot.json"
    assert manifest_path.exists()
    assert snapshot_path.exists()


def test_persist_run_market_artifacts_marks_numeric_questions_unsupported(
    simulation_data_dir, forecast_data_dir, monkeypatch
):
    extractor_module = _load_extractor_module()
    simulation_id = "sim-market-numeric"
    forecast_id = "forecast-market-numeric"
    run_dir = _write_run_root(simulation_data_dir, simulation_id)
    _write_simulation_state(simulation_data_dir, simulation_id, forecast_id=forecast_id)
    _create_workspace(
        forecast_data_dir,
        monkeypatch,
        forecast_id=forecast_id,
        simulation_id=simulation_id,
        question_type="numeric",
        question_spec={"unit": "index points", "interval_levels": [50, 80]},
    )
    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-30T10:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "CREATE_POST",
                "action_args": {"content": "Maybe 3,800 by June."},
                "success": True,
            }
        ],
    )

    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    artifacts = extractor.persist_run_market_artifacts(
        simulation_id,
        ensemble_id="0001",
        run_id="0001",
    )

    assert artifacts["manifest"]["extraction_status"] == "unsupported_question_type"
    assert artifacts["manifest"]["supported_question_type"] is False
    assert artifacts["market_snapshot"]["support_status"] == "unsupported_question_type"
    assert artifacts["agent_belief_book"]["beliefs"] == []
