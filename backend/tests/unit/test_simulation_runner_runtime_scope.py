import importlib
import json
import sys
from pathlib import Path


def _load_runner_module():
    """Import the real runner module instead of the lightweight API-test stub."""
    sys.modules.pop("app.services.simulation_runner", None)
    return importlib.import_module("app.services.simulation_runner")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_legacy_simulation_root(data_dir: Path, simulation_id: str) -> Path:
    sim_dir = data_dir / simulation_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        sim_dir / "simulation_config.json",
        {
            "simulation_id": simulation_id,
            "time_config": {
                "total_simulation_hours": 24,
                "minutes_per_round": 60,
            },
        },
    )
    (sim_dir / "twitter_profiles.csv").write_text(
        "user_id,username,name,bio,persona\n1,agent_one,Agent One,Bio,Persona\n",
        encoding="utf-8",
    )
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps(
            [
                {
                    "user_id": 1,
                    "username": "agent_one",
                    "name": "Agent One",
                    "bio": "Bio",
                    "persona": "Persona",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return sim_dir


def _write_ensemble_run_root(
    data_dir: Path,
    simulation_id: str,
    ensemble_id: str = "0001",
    run_id: str = "0001",
):
    sim_dir = _write_legacy_simulation_root(data_dir, simulation_id)
    run_dir = (
        sim_dir
        / "ensemble"
        / f"ensemble_{ensemble_id}"
        / "runs"
        / f"run_{run_id}"
    )
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
            "status": "prepared",
        },
    )
    return sim_dir, run_dir


def _configure_runner(monkeypatch, simulation_data_dir):
    runner_module = _load_runner_module()
    runner_class = runner_module.SimulationRunner
    monkeypatch.setattr(
        runner_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    monkeypatch.setattr(runner_class, "RUN_STATE_DIR", str(simulation_data_dir))

    for mapping_name in (
        "_run_states",
        "_processes",
        "_action_queues",
        "_monitor_threads",
        "_stdout_files",
        "_stderr_files",
        "_graph_memory_enabled",
    ):
        mapping = getattr(runner_class, mapping_name)
        if hasattr(mapping, "values"):
            for handle in list(mapping.values()):
                if hasattr(handle, "close"):
                    try:
                        handle.close()
                    except Exception:
                        pass
        mapping.clear()

    runner_class._cleanup_done = False
    runner_module._cleanup_registered = False
    return runner_module


def _patch_runner_launch(monkeypatch, runner_module):
    captures = {}

    class _FakeProcess:
        pid = 4242
        returncode = None

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    class _FakeThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    def _fake_popen(cmd, cwd, stdout, stderr, text, encoding, bufsize, env, start_new_session):
        captures["cmd"] = cmd
        captures["cwd"] = cwd
        captures["stdout_path"] = getattr(stdout, "name", None)
        captures["stderr"] = stderr
        captures["text"] = text
        captures["encoding"] = encoding
        captures["bufsize"] = bufsize
        captures["env"] = env
        captures["start_new_session"] = start_new_session
        return _FakeProcess()

    monkeypatch.setattr(runner_module.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(runner_module.threading, "Thread", _FakeThread)
    return captures


def test_start_simulation_preserves_legacy_runtime_root(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-legacy"
    sim_dir = _write_legacy_simulation_root(simulation_data_dir, simulation_id)
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    captures = _patch_runner_launch(monkeypatch, runner_module)

    state = runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform="twitter",
    )

    assert state.simulation_id == simulation_id
    assert state.ensemble_id is None
    assert state.run_id is None
    assert state.runtime_scope == "legacy"
    assert state.runtime_key == simulation_id
    assert state.runtime_dir == str(sim_dir)
    assert captures["cwd"] == str(sim_dir)
    assert captures["cmd"][1].endswith("run_twitter_simulation.py")
    assert captures["cmd"][-1] == str(sim_dir / "simulation_config.json")
    assert "--run-dir" not in captures["cmd"]
    assert "--run-id" not in captures["cmd"]
    assert "--seed" not in captures["cmd"]
    assert "--no-wait" not in captures["cmd"]
    assert captures["stdout_path"] == str(sim_dir / "simulation.log")
    assert (sim_dir / "run_state.json").exists()
    timing_payload = json.loads(
        (sim_dir / "run_phase_timings.json").read_text(encoding="utf-8")
    )
    assert timing_payload["scope_kind"] == "run"
    assert timing_payload["scope_id"] == simulation_id
    assert "run_startup" in timing_payload["phases"]
    assert simulation_id in runner_module.SimulationRunner._processes


def test_start_simulation_uses_run_local_runtime_root_for_ensemble_member(
    tmp_path, monkeypatch
):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-ensemble"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    captures = _patch_runner_launch(monkeypatch, runner_module)

    state = runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform="parallel",
        close_environment_on_complete=True,
    )

    assert state.simulation_id == simulation_id
    assert state.ensemble_id == ensemble_id
    assert state.run_id == run_id
    assert state.runtime_scope == "ensemble_run"
    assert state.runtime_key == f"{simulation_id}::{ensemble_id}::{run_id}"
    assert state.runtime_dir == str(run_dir)
    assert captures["cwd"] == str(run_dir)
    assert captures["cmd"][1].endswith("run_parallel_simulation.py")
    assert captures["cmd"][3] == str(run_dir / "resolved_config.json")
    assert captures["cmd"][4:10] == [
        "--run-dir",
        str(run_dir),
        "--run-id",
        run_id,
        "--seed",
        "17",
    ]
    assert captures["cmd"][-1] == "--no-wait"
    assert captures["stdout_path"] == str(run_dir / "simulation.log")
    assert (run_dir / "twitter_profiles.csv").exists()
    assert (run_dir / "reddit_profiles.json").exists()
    assert (run_dir / "run_state.json").exists()
    timing_payload = json.loads(
        (run_dir / "run_phase_timings.json").read_text(encoding="utf-8")
    )
    assert timing_payload["scope_kind"] == "run"
    assert timing_payload["scope_id"] == f"{simulation_id}::{ensemble_id}::{run_id}"
    assert "run_startup" in timing_payload["phases"]
    assert state.runtime_key in runner_module.SimulationRunner._processes


def test_start_simulation_uses_runtime_graph_update_manager_for_live_runtime_ingestion(
    tmp_path, monkeypatch
):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-runtime-updater"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    captures = _patch_runner_launch(monkeypatch, runner_module)

    update_manager_calls = {}

    class _FakeRuntimeGraphUpdateManager:
        @classmethod
        def create_updater(cls, run_key, base_graph_id, runtime_graph_id, run_dir):
            update_manager_calls["args"] = (
                run_key,
                base_graph_id,
                runtime_graph_id,
                run_dir,
            )
            return object()

    monkeypatch.setattr(
        runner_module,
        "RuntimeGraphUpdateManager",
        _FakeRuntimeGraphUpdateManager,
    )

    state = runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform="parallel",
        close_environment_on_complete=True,
        enable_graph_memory_update=True,
        base_graph_id="mirofish-base-proj-runtime",
        runtime_graph_id="mirofish-runtime-sim-runtime-updater-0001-0001",
    )

    assert state.runtime_scope == "ensemble_run"
    assert captures["cwd"] == str(run_dir)
    assert update_manager_calls["args"] == (
        f"{simulation_id}::{ensemble_id}::{run_id}",
        "mirofish-base-proj-runtime",
        "mirofish-runtime-sim-runtime-updater-0001-0001",
        str(run_dir),
    )


def test_get_all_actions_reads_only_the_requested_run_root(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-actions"
    ensemble_id = "0001"
    _, run_one_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
    )
    _, run_two_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id="0002",
        run_id="0001",
    )
    (run_one_dir / "twitter").mkdir(parents=True, exist_ok=True)
    (run_two_dir / "twitter").mkdir(parents=True, exist_ok=True)
    (run_one_dir / "twitter" / "actions.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-08T12:00:00",
                "round": 1,
                "agent_id": 7,
                "agent_name": "Run One",
                "action_type": "CREATE_POST",
                "action_args": {"content": "run-one"},
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_two_dir / "twitter" / "actions.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-08T12:05:00",
                "round": 1,
                "agent_id": 9,
                "agent_name": "Run Two",
                "action_type": "CREATE_POST",
                "action_args": {"content": "run-two"},
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)

    actions = runner_module.SimulationRunner.get_all_actions(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
    )

    assert len(actions) == 1
    assert actions[0].agent_name == "Run One"
    assert actions[0].platform == "twitter"


def test_cleanup_simulation_logs_targets_only_one_run_root(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-cleanup"
    ensemble_id = "0001"
    _sim_dir, run_one_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
    )
    _sim_dir, run_two_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id="0002",
    )

    for run_dir in (run_one_dir, run_two_dir):
        (run_dir / "twitter").mkdir(parents=True, exist_ok=True)
        (run_dir / "reddit").mkdir(parents=True, exist_ok=True)
        (run_dir / "twitter" / "actions.jsonl").write_text("{}", encoding="utf-8")
        (run_dir / "reddit" / "actions.jsonl").write_text("{}", encoding="utf-8")
        (run_dir / "simulation.log").write_text("log", encoding="utf-8")
        (run_dir / "run_state.json").write_text("{}", encoding="utf-8")
        (run_dir / "runtime_graph_base_snapshot.json").write_text("{}", encoding="utf-8")
        (run_dir / "runtime_graph_state.json").write_text("{}", encoding="utf-8")
        (run_dir / "runtime_graph_updates.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "metrics.json").write_text("{}", encoding="utf-8")
        (run_dir / "run_phase_timings.json").write_text("{}", encoding="utf-8")
        (run_dir / "env_status.json").write_text("{}", encoding="utf-8")
        (run_dir / "twitter_simulation.db").write_text("", encoding="utf-8")
        (run_dir / "reddit_simulation.db").write_text("", encoding="utf-8")
        (run_dir / "twitter_profiles.csv").write_text("seed", encoding="utf-8")
        (run_dir / "reddit_profiles.json").write_text("[]", encoding="utf-8")

    run_one_manifest = json.loads((run_one_dir / "run_manifest.json").read_text(encoding="utf-8"))
    run_one_manifest["artifact_paths"] = {
        "metrics": "metrics.json",
        "runtime_graph_base_snapshot": "runtime_graph_base_snapshot.json",
        "runtime_graph_state": "runtime_graph_state.json",
        "runtime_graph_updates": "runtime_graph_updates.jsonl",
    }
    _write_json(run_one_dir / "run_manifest.json", run_one_manifest)

    runner_module = _configure_runner(monkeypatch, simulation_data_dir)

    result = runner_module.SimulationRunner.cleanup_simulation_logs(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
    )

    assert result["success"] is True
    assert not (run_one_dir / "run_state.json").exists()
    assert not (run_one_dir / "runtime_graph_base_snapshot.json").exists()
    assert not (run_one_dir / "runtime_graph_state.json").exists()
    assert not (run_one_dir / "runtime_graph_updates.jsonl").exists()
    assert not (run_one_dir / "simulation.log").exists()
    assert not (run_one_dir / "twitter" / "actions.jsonl").exists()
    assert not (run_one_dir / "reddit" / "actions.jsonl").exists()
    assert not (run_one_dir / "metrics.json").exists()
    assert not (run_one_dir / "run_phase_timings.json").exists()
    assert not (run_one_dir / "twitter_simulation.db").exists()
    assert not (run_one_dir / "reddit_simulation.db").exists()
    assert (run_one_dir / "resolved_config.json").exists()
    assert (run_one_dir / "run_manifest.json").exists()
    assert (run_one_dir / "twitter_profiles.csv").exists()
    assert (run_one_dir / "reddit_profiles.json").exists()
    cleaned_manifest = json.loads((run_one_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert cleaned_manifest["artifact_paths"] == {}
    assert (run_two_dir / "run_state.json").exists()
    assert (run_two_dir / "simulation.log").exists()
    assert (run_two_dir / "twitter" / "actions.jsonl").exists()


def test_persist_run_metrics_writes_metrics_json_and_updates_manifest(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-metrics"
    ensemble_id = "0001"
    run_id = "0001"
    sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    _write_json(
        sim_dir / "outcome_spec.json",
        {
            "artifact_type": "outcome_spec",
            "metrics": [
                {"metric_id": "simulation.total_actions"},
                {"metric_id": "platform.twitter.total_actions"},
                {"metric_id": "platform.reddit.total_actions"},
            ],
        },
    )
    (run_dir / "twitter").mkdir(parents=True, exist_ok=True)
    (run_dir / "reddit").mkdir(parents=True, exist_ok=True)
    (run_dir / "twitter" / "actions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-08T12:00:00",
                        "round": 1,
                        "agent_id": 7,
                        "agent_name": "Run One",
                        "action_type": "CREATE_POST",
                        "action_args": {"topic": "inflation"},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-08T12:05:00",
                        "round": 2,
                        "agent_id": 7,
                        "agent_name": "Run One",
                        "action_type": "REPLY",
                        "action_args": {"topics": ["rates"]},
                        "success": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "reddit" / "actions.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-08T12:07:00",
                "round": 2,
                "agent_id": 8,
                "agent_name": "Run Two",
                "action_type": "COMMENT",
                "action_args": {"topic": "inflation"},
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    runner_module = _configure_runner(monkeypatch, simulation_data_dir)

    artifact = runner_module.SimulationRunner._persist_run_metrics_artifact(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        run_status="completed",
    )

    metrics_path = run_dir / "metrics.json"
    assert metrics_path.exists()
    persisted = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert artifact == persisted
    assert persisted["metric_values"]["simulation.total_actions"]["value"] == 3
    assert persisted["metric_values"]["platform.twitter.total_actions"]["value"] == 2
    assert persisted["metric_values"]["platform.reddit.total_actions"]["value"] == 1
    assert persisted["quality_checks"]["log_completeness"] == "complete"
    timing_payload = json.loads(
        (run_dir / "run_phase_timings.json").read_text(encoding="utf-8")
    )
    assert timing_payload["scope_kind"] == "run"
    assert timing_payload["scope_id"] == f"{simulation_id}::{ensemble_id}::{run_id}"
    assert "metrics_extraction" in timing_payload["phases"]

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_paths"]["metrics"] == "metrics.json"


def test_run_manifest_status_tracks_runtime_transitions(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-manifest"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    _patch_runner_launch(monkeypatch, runner_module)
    monkeypatch.setattr(
        runner_module.SimulationRunner,
        "_terminate_process",
        lambda process, simulation_key, timeout=10: None,
    )

    runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform="parallel",
    )

    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "running"
    assert manifest["lifecycle"]["start_count"] == 1
    assert manifest["lifecycle"]["retry_count"] == 0
    assert manifest["lifecycle"]["last_launch_reason"] == "initial_start"
    assert manifest["lineage"]["kind"] == "seeded_member"
    assert manifest["lineage"]["source_run_id"] is None

    runner_module.SimulationRunner.stop_simulation(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "stopped"

    runner_module.SimulationRunner.cleanup_simulation_logs(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared"
    assert manifest["lifecycle"]["cleanup_count"] == 1


def test_second_start_records_retry_in_manifest_lifecycle(tmp_path, monkeypatch):
    simulation_data_dir = tmp_path / "simulations"
    simulation_id = "sim-retry"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    _patch_runner_launch(monkeypatch, runner_module)
    monkeypatch.setattr(
        runner_module.SimulationRunner,
        "_terminate_process",
        lambda process, simulation_key, timeout=10: None,
    )

    runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform="parallel",
    )
    runner_module.SimulationRunner.stop_simulation(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    runner_module.SimulationRunner.cleanup_simulation_logs(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    runner_module.SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform="parallel",
    )

    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "running"
    assert manifest["lifecycle"]["start_count"] == 2
    assert manifest["lifecycle"]["retry_count"] == 1
    assert manifest["lifecycle"]["last_launch_reason"] == "retry"


def test_monitor_completion_does_not_downgrade_status_when_metrics_persistence_fails(
    simulation_data_dir, monkeypatch
):
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    runner = runner_module.SimulationRunner

    simulation_id = "sim-metrics-failure-tolerant"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
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
            "platform_mode": "twitter",
            "runner_status": "running",
        },
    )
    (run_dir / "twitter" / "actions.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "twitter" / "actions.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-08T12:00:00",
                "round": 1,
                "agent_id": 7,
                "agent_name": "Run One",
                "action_type": "POST",
                "action_args": {"content": "seed alert"},
                "success": True,
            }
        )
        + "\n"
        + json.dumps(
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:01:00",
                "platform": "twitter",
                "total_rounds": 1,
                "total_actions": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _ExitedProcess:
        returncode = 0

        def poll(self):
            return 0

    def _boom(*args, **kwargs):
        raise RuntimeError("metrics write failed")

    monkeypatch.setattr(runner_module.OutcomeExtractor, "persist_run_metrics", _boom)

    run_key = f"{simulation_id}::{ensemble_id}::{run_id}"
    state = runner_module.SimulationRunState(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        run_key=run_key,
        run_dir=str(run_dir),
        config_path=str(run_dir / "resolved_config.json"),
        platform_mode="twitter",
        runner_status=runner_module.RunnerStatus.RUNNING,
        twitter_running=True,
    )
    runner._run_states[run_key] = state
    runner._processes[run_key] = _ExitedProcess()

    runner._monitor_simulation(simulation_id, ensemble_id, run_id)

    persisted_state = runner.get_run_state(simulation_id, ensemble_id, run_id)
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert persisted_state.runner_status == runner_module.RunnerStatus.COMPLETED
    assert (run_dir / "metrics.json").exists() is False
    assert manifest.get("artifact_paths", {}).get("metrics") is None


def test_read_action_log_keeps_run_running_until_monitor_finalization(
    simulation_data_dir, monkeypatch
):
    runner_module = _configure_runner(monkeypatch, simulation_data_dir)
    runner = runner_module.SimulationRunner

    simulation_id = "sim-log-ordering"
    ensemble_id = "0001"
    run_id = "0001"
    _sim_dir, run_dir = _write_ensemble_run_root(
        simulation_data_dir,
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    actions_path = run_dir / "twitter" / "actions.jsonl"
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    actions_path.write_text(
        json.dumps(
            {
                "event_type": "simulation_end",
                "timestamp": "2026-03-08T12:01:00",
                "platform": "twitter",
                "total_rounds": 1,
                "total_actions": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    state = runner_module.SimulationRunState(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        run_key=f"{simulation_id}::{ensemble_id}::{run_id}",
        run_dir=str(run_dir),
        config_path=str(run_dir / "resolved_config.json"),
        platform_mode="twitter",
        runner_status=runner_module.RunnerStatus.RUNNING,
        twitter_running=True,
    )

    runner._read_action_log(str(actions_path), 0, state, "twitter")

    assert state.twitter_completed is True
    assert state.twitter_running is False
    assert state.runner_status == runner_module.RunnerStatus.RUNNING
    assert state.completed_at is None
