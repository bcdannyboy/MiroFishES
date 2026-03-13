import importlib
import json
import sys
from pathlib import Path


def _load_probabilistic_module():
    return importlib.import_module("app.models.probabilistic")


def _load_outcome_extractor_module():
    return importlib.import_module("app.services.outcome_extractor")


def _load_runner_module():
    sys.modules.pop("app.services.simulation_runner", None)
    return importlib.import_module("app.services.simulation_runner")


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


def _configure_runtime_roots(monkeypatch, simulation_data_dir):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )


def _write_probabilistic_run_root(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    ensemble_id: str = "0001",
    run_id: str = "0001",
    metric_ids: list[str] | None = None,
    hot_topics: list[str] | None = None,
    run_status: str = "completed",
    platform_mode: str = "parallel",
) -> Path:
    probabilistic_module = _load_probabilistic_module()
    metric_ids = metric_ids or [
        "simulation.total_actions",
        "platform.twitter.total_actions",
        "platform.reddit.total_actions",
    ]
    hot_topics = hot_topics or ["seed"]

    sim_dir = simulation_data_dir / simulation_id
    run_dir = sim_dir / "ensemble" / f"ensemble_{ensemble_id}" / "runs" / f"run_{run_id}"

    outcome_spec = {
        "artifact_type": "outcome_spec",
        "schema_version": probabilistic_module.PROBABILISTIC_SCHEMA_VERSION,
        "generator_version": probabilistic_module.PROBABILISTIC_GENERATOR_VERSION,
        "metrics": [
            probabilistic_module.build_supported_outcome_metric(metric_id).to_dict()
            for metric_id in metric_ids
        ],
        "notes": [],
    }
    _write_json(sim_dir / "outcome_spec.json", outcome_spec)
    _write_json(
        run_dir / "resolved_config.json",
        {
            "artifact_type": "resolved_config",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "time_config": {
                "total_simulation_hours": 12,
                "minutes_per_round": 60,
            },
            "event_config": {
                "hot_topics": hot_topics,
            },
        },
    )
    _write_json(
        run_dir / "run_manifest.json",
        {
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "root_seed": 17,
            "seed_metadata": {"resolution_seed": 17},
            "resolved_values": {},
            "config_artifact": "resolved_config.json",
            "artifact_paths": {"resolved_config": "resolved_config.json"},
            "generated_at": "2026-03-08T12:00:00",
            "status": run_status,
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
            "platform_mode": platform_mode,
            "runner_status": run_status,
            "twitter_running": False,
            "reddit_running": False,
            "updated_at": "2026-03-08T12:00:00",
            "completed_at": "2026-03-08T12:10:00",
        },
    )
    return run_dir


def test_extract_run_metrics_computes_first_pass_catalog_from_run_logs(
    simulation_data_dir, monkeypatch
):
    _configure_runtime_roots(monkeypatch, simulation_data_dir)
    extractor_module = _load_outcome_extractor_module()
    run_dir = _write_probabilistic_run_root(
        simulation_data_dir,
        "sim-metrics-complete",
    )

    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed narrative"},
                "success": True,
            },
            {
                "round": 2,
                "timestamp": "2026-03-08T12:10:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "QUOTE_POST",
                "action_args": {"content": "seed follow-up"},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:30:00",
                "platform": "twitter",
                "total_rounds": 2,
                "total_actions": 2,
            },
        ],
    )
    _write_jsonl(
        run_dir / "reddit" / "actions.jsonl",
        [
            {
                "round": 2,
                "timestamp": "2026-03-08T12:20:00",
                "platform": "reddit",
                "agent_id": 2,
                "agent_name": "beta",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed discussion"},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:31:00",
                "platform": "reddit",
                "total_rounds": 2,
                "total_actions": 1,
            },
        ],
    )

    extractor = extractor_module.OutcomeExtractor(
        simulation_data_dir=str(simulation_data_dir)
    )
    payload = extractor.extract_run_metrics(
        simulation_id="sim-metrics-complete",
        ensemble_id="0001",
        run_id="0001",
    )

    assert payload["metric_values"]["simulation.total_actions"]["value"] == 3
    assert payload["metric_values"]["platform.twitter.total_actions"]["value"] == 2
    assert payload["metric_values"]["platform.reddit.total_actions"]["value"] == 1
    assert payload["event_flags"]["run_completed"] is True
    assert payload["event_flags"]["run_failed"] is False
    assert payload["timeline_summaries"]["round_count"] == 2
    assert payload["timeline_summaries"]["last_round_num"] == 2
    assert payload["top_agents"][0]["agent_name"] == "alpha"
    assert payload["top_agents"][0]["total_actions"] == 2
    assert payload["top_topics"][0] == {"topic": "seed", "mentions": 3}
    assert payload["quality_checks"]["status"] == "complete"
    assert payload["quality_checks"]["missing_artifacts"] == []
    assert payload["quality_checks"]["timeline_matches_total_actions"] is True


def test_extract_run_metrics_marks_missing_requested_platform_logs_as_partial(
    simulation_data_dir, monkeypatch
):
    _configure_runtime_roots(monkeypatch, simulation_data_dir)
    extractor_module = _load_outcome_extractor_module()
    run_dir = _write_probabilistic_run_root(
        simulation_data_dir,
        "sim-metrics-partial",
        metric_ids=[
            "simulation.total_actions",
            "platform.twitter.total_actions",
            "platform.reddit.total_actions",
        ],
        run_status="failed",
    )

    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed alert"},
                "success": True,
            }
        ],
    )

    extractor = extractor_module.OutcomeExtractor(
        simulation_data_dir=str(simulation_data_dir)
    )
    payload = extractor.extract_run_metrics(
        simulation_id="sim-metrics-partial",
        ensemble_id="0001",
        run_id="0001",
    )

    assert payload["metric_values"]["simulation.total_actions"]["value"] == 1
    assert payload["metric_values"]["platform.twitter.total_actions"]["value"] == 1
    assert payload["metric_values"]["platform.reddit.total_actions"]["value"] == 0
    assert payload["event_flags"]["run_completed"] is False
    assert payload["event_flags"]["run_failed"] is True
    assert payload["quality_checks"]["status"] == "partial"
    assert "reddit/actions.jsonl" in payload["quality_checks"]["missing_artifacts"]
    assert "run_status:failed" in payload["quality_checks"]["warnings"]


def test_extract_run_metrics_respects_single_platform_run_state_for_completeness(
    simulation_data_dir, monkeypatch
):
    _configure_runtime_roots(monkeypatch, simulation_data_dir)
    extractor_module = _load_outcome_extractor_module()
    run_dir = _write_probabilistic_run_root(
        simulation_data_dir,
        "sim-metrics-single-platform",
        run_status="completed",
        platform_mode="twitter",
    )

    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed alert"},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:10:00",
                "platform": "twitter",
                "total_rounds": 1,
                "total_actions": 1,
            },
        ],
    )

    extractor = extractor_module.OutcomeExtractor(
        simulation_data_dir=str(simulation_data_dir)
    )
    payload = extractor.extract_run_metrics(
        simulation_id="sim-metrics-single-platform",
        ensemble_id="0001",
        run_id="0001",
    )

    assert payload["quality_checks"]["status"] == "complete"
    assert payload["quality_checks"]["missing_artifacts"] == []
    assert payload["event_flags"]["run_completed"] is True


def test_extract_run_metrics_is_deterministic_for_identical_artifacts(
    simulation_data_dir, monkeypatch
):
    _configure_runtime_roots(monkeypatch, simulation_data_dir)
    extractor_module = _load_outcome_extractor_module()
    run_dir = _write_probabilistic_run_root(
        simulation_data_dir,
        "sim-metrics-repeatable",
    )

    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed alert"},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:10:00",
                "platform": "twitter",
                "total_rounds": 1,
                "total_actions": 1,
            },
        ],
    )

    extractor = extractor_module.OutcomeExtractor(
        simulation_data_dir=str(simulation_data_dir)
    )
    first = extractor.extract_run_metrics(
        simulation_id="sim-metrics-repeatable",
        ensemble_id="0001",
        run_id="0001",
    )
    second = extractor.extract_run_metrics(
        simulation_id="sim-metrics-repeatable",
        ensemble_id="0001",
        run_id="0001",
    )

    assert first == second


def test_monitor_completion_persists_metrics_json_for_run_scope(
    simulation_data_dir, monkeypatch
):
    _configure_runtime_roots(monkeypatch, simulation_data_dir)
    runner_module = _load_runner_module()
    monkeypatch.setattr(
        runner_module.SimulationRunner,
        "RUN_STATE_DIR",
        str(simulation_data_dir),
    )
    run_dir = _write_probabilistic_run_root(
        simulation_data_dir,
        "sim-metrics-persist",
        run_status="prepared",
    )
    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "alpha",
                "action_type": "CREATE_POST",
                "action_args": {"content": "seed alert"},
                "success": True,
            },
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:10:00",
                "platform": "twitter",
                "total_rounds": 1,
                "total_actions": 1,
            },
        ],
    )

    class _ExitedProcess:
        returncode = 0

        def poll(self):
            return 0

    runner = runner_module.SimulationRunner
    run_key = "sim-metrics-persist::0001::0001"
    runner._run_states.clear()
    runner._processes.clear()
    runner._action_queues.clear()
    runner._monitor_threads.clear()
    runner._stdout_files.clear()
    runner._stderr_files.clear()
    runner._graph_memory_enabled.clear()

    state = runner_module.SimulationRunState(
        simulation_id="sim-metrics-persist",
        ensemble_id="0001",
        run_id="0001",
        run_key=run_key,
        run_dir=str(run_dir),
        config_path=str(run_dir / "resolved_config.json"),
        runner_status=runner_module.RunnerStatus.RUNNING,
        twitter_running=True,
    )
    runner._run_states[run_key] = state
    runner._processes[run_key] = _ExitedProcess()

    runner._monitor_simulation("sim-metrics-persist", "0001", "0001")

    metrics_path = run_dir / "metrics.json"
    assert metrics_path.exists()
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["metric_values"]["simulation.total_actions"]["value"] == 1
    assert payload["quality_checks"]["run_status"] == "completed"
