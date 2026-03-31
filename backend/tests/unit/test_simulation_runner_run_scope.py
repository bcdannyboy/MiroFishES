import importlib
import json
import sys
from pathlib import Path


def _load_runner_module():
    sys.modules.pop("app.services.simulation_runner", None)
    return importlib.import_module("app.services.simulation_runner")


class _FakeProcess:
    def __init__(self, cmd, cwd, stdout, **kwargs):
        self.cmd = cmd
        self.cwd = cwd
        self.stdout = stdout
        self.kwargs = kwargs
        self.pid = 4242
        self.returncode = None

    def poll(self):
        return None


class _FakeThread:
    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "time_config": {
                    "total_simulation_hours": 24,
                    "minutes_per_round": 60,
                }
            }
        ),
        encoding="utf-8",
    )


def test_start_simulation_persists_run_scoped_state_under_run_directory(
    simulation_data_dir, monkeypatch
):
    runner_module = _load_runner_module()
    runner = runner_module.SimulationRunner
    monkeypatch.setattr(runner, "RUN_STATE_DIR", str(simulation_data_dir))

    sim_dir = simulation_data_dir / "sim-run-scope"
    run_dir = sim_dir / "ensemble" / "ensemble_0001" / "runs" / "run_0002"
    config_path = run_dir / "resolved_config.json"
    _write_config(config_path)
    (sim_dir / "twitter_profiles.csv").write_text(
        "user_id,username,name,bio,persona\n1,agent_one,Agent One,Bio,Persona\n",
        encoding="utf-8",
    )
    (sim_dir / "reddit_profiles.json").write_text("[]", encoding="utf-8")

    fake_processes = []

    def _fake_popen(cmd, cwd, stdout, **kwargs):
        process = _FakeProcess(cmd=cmd, cwd=cwd, stdout=stdout, **kwargs)
        fake_processes.append(process)
        return process

    monkeypatch.setattr(runner_module.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(runner_module.threading, "Thread", _FakeThread)

    state = runner.start_simulation(
        simulation_id="sim-run-scope",
        ensemble_id="0001",
        run_id="0002",
        config_path=str(config_path),
        run_dir=str(run_dir),
    )

    scoped_state_path = run_dir / "run_state.json"
    legacy_state_path = sim_dir / "run_state.json"

    assert state.simulation_id == "sim-run-scope"
    assert state.ensemble_id == "0001"
    assert state.run_id == "0002"
    assert state.run_dir == str(run_dir)
    assert scoped_state_path.exists()
    assert legacy_state_path.exists() is False
    assert fake_processes[0].cwd == str(run_dir)
    assert fake_processes[0].cmd[1].endswith("run_parallel_simulation.py")
    assert fake_processes[0].cmd[3] == str(config_path)
    assert "--run-dir" in fake_processes[0].cmd
    assert "--run-id" in fake_processes[0].cmd
    assert "--seed" not in fake_processes[0].cmd
    assert (run_dir / "twitter_profiles.csv").exists()
    assert (run_dir / "reddit_profiles.json").exists()


def test_get_actions_and_cleanup_are_run_scoped(
    simulation_data_dir, monkeypatch
):
    runner_module = _load_runner_module()
    runner = runner_module.SimulationRunner
    monkeypatch.setattr(runner, "RUN_STATE_DIR", str(simulation_data_dir))

    simulation_id = "sim-run-scope"
    ensemble_id = "0001"
    run_id = "0002"

    sim_dir = simulation_data_dir / simulation_id
    root_actions = sim_dir / "twitter" / "actions.jsonl"
    root_actions.parent.mkdir(parents=True, exist_ok=True)
    root_actions.write_text(
        json.dumps(
            {
                "round": 1,
                "timestamp": "2026-03-08T12:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "legacy",
                "action_type": "CREATE_POST",
                "action_args": {},
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = sim_dir / "ensemble" / "ensemble_0001" / "runs" / "run_0002"
    run_actions = run_dir / "twitter" / "actions.jsonl"
    run_actions.parent.mkdir(parents=True, exist_ok=True)
    run_actions.write_text(
        json.dumps(
            {
                "round": 2,
                "timestamp": "2026-03-08T12:05:00",
                "platform": "twitter",
                "agent_id": 2,
                "agent_name": "run-scoped",
                "action_type": "CREATE_POST",
                "action_args": {},
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "simulation.log").write_text("run log", encoding="utf-8")
    (run_dir / "run_state.json").write_text("{}", encoding="utf-8")
    (run_dir / "metrics.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_phase_timings.json").write_text("{}", encoding="utf-8")
    (run_dir / "simulation_market_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "market_snapshot.json").write_text("{}", encoding="utf-8")
    (run_dir / "argument_map.json").write_text("{}", encoding="utf-8")
    (run_dir / "belief_update_trace.json").write_text("{}", encoding="utf-8")
    (run_dir / "agent_belief_book.json").write_text("{}", encoding="utf-8")
    (run_dir / "disagreement_summary.json").write_text("{}", encoding="utf-8")
    (run_dir / "missing_information_signals.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "status": "completed",
                "artifact_paths": {
                    "metrics": "metrics.json",
                    "simulation_market_manifest": "simulation_market_manifest.json",
                    "market_snapshot": "market_snapshot.json",
                    "argument_map": "argument_map.json",
                    "belief_update_trace": "belief_update_trace.json",
                    "agent_belief_book": "agent_belief_book.json",
                    "disagreement_summary": "disagreement_summary.json",
                    "missing_information_signals": "missing_information_signals.json",
                },
            }
        ),
        encoding="utf-8",
    )

    scoped_actions = runner.get_actions(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    legacy_actions = runner.get_actions(simulation_id=simulation_id)
    cleanup_result = runner.cleanup_simulation_logs(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    assert [action.agent_name for action in scoped_actions] == ["run-scoped"]
    assert [action.agent_name for action in legacy_actions] == ["legacy"]
    assert cleanup_result["success"] is True
    assert run_actions.exists() is False
    assert (run_dir / "metrics.json").exists() is False
    assert (run_dir / "run_phase_timings.json").exists() is False
    assert (run_dir / "simulation_market_manifest.json").exists() is False
    assert (run_dir / "market_snapshot.json").exists() is False
    assert root_actions.exists() is True
    updated_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert "metrics" not in updated_manifest["artifact_paths"]
    assert "simulation_market_manifest" not in updated_manifest["artifact_paths"]
    assert "market_snapshot" not in updated_manifest["artifact_paths"]


def test_read_action_log_tracks_inflight_round_and_last_progress(
    simulation_data_dir, monkeypatch
):
    runner_module = _load_runner_module()
    runner = runner_module.SimulationRunner
    monkeypatch.setattr(runner, "RUN_STATE_DIR", str(simulation_data_dir))

    simulation_id = "sim-run-scope"
    ensemble_id = "0001"
    run_id = "0002"
    run_dir = simulation_data_dir / simulation_id / "ensemble" / "ensemble_0001" / "runs" / "run_0002"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "twitter" / "actions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 3,
                        "timestamp": "2026-03-12T07:19:00",
                        "event_type": "round_start",
                        "simulated_hour": 18,
                    }
                ),
                json.dumps(
                    {
                        "round": 3,
                        "timestamp": "2026-03-12T07:19:01",
                        "agent_id": 7,
                        "agent_name": "Plaza Analyst",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "hello"},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round": 3,
                        "timestamp": "2026-03-12T07:19:02",
                        "event_type": "round_end",
                        "actions_count": 1,
                    }
                ),
                json.dumps(
                    {
                        "round": 4,
                        "timestamp": "2026-03-12T07:19:03",
                        "event_type": "round_start",
                        "simulated_hour": 19,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = runner_module.SimulationRunState(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        run_key=runner._build_run_key(simulation_id, ensemble_id=ensemble_id, run_id=run_id),
        run_dir=str(run_dir),
        config_path=str(run_dir / "resolved_config.json"),
        runner_status=runner_module.RunnerStatus.RUNNING,
        twitter_running=True,
    )

    runner._read_action_log(str(log_path), 0, state, "twitter")
    runner._save_run_state(state)
    loaded = runner._load_run_state(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        run_dir=str(run_dir),
    )

    assert state.twitter_current_round == 3
    assert state.current_round == 3
    assert state.twitter_inflight_round == 4
    assert state.twitter_last_progress_at == "2026-03-12T07:19:03"
    assert state.twitter_actions_count == 1
    assert state.twitter_running is True
    assert loaded is not None
    assert loaded.twitter_inflight_round == 4
    assert loaded.twitter_last_progress_at == "2026-03-12T07:19:03"


def test_read_action_log_tracks_platform_inflight_progress_and_persists_state(
    simulation_data_dir, monkeypatch
):
    runner_module = _load_runner_module()
    runner = runner_module.SimulationRunner
    monkeypatch.setattr(runner, "RUN_STATE_DIR", str(simulation_data_dir))

    simulation_id = "sim-progress"
    ensemble_id = "0001"
    run_id = "0001"
    run_dir = (
        simulation_data_dir
        / simulation_id
        / "ensemble"
        / f"ensemble_{ensemble_id}"
        / "runs"
        / f"run_{run_id}"
    )
    config_path = run_dir / "resolved_config.json"
    _write_config(config_path)

    twitter_log = run_dir / "twitter" / "actions.jsonl"
    twitter_log.parent.mkdir(parents=True, exist_ok=True)
    twitter_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 41,
                        "timestamp": "2026-03-12T07:19:00",
                        "event_type": "round_start",
                        "simulated_hour": 16,
                    }
                ),
                json.dumps(
                    {
                        "round": 41,
                        "timestamp": "2026-03-12T07:19:10",
                        "agent_id": 7,
                        "agent_name": "Plaza Analyst",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "post"},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round": 41,
                        "timestamp": "2026-03-12T07:19:20",
                        "event_type": "round_end",
                        "actions_count": 1,
                    }
                ),
                json.dumps(
                    {
                        "round": 42,
                        "timestamp": "2026-03-12T07:19:25",
                        "event_type": "round_start",
                        "simulated_hour": 17,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    reddit_log = run_dir / "reddit" / "actions.jsonl"
    reddit_log.parent.mkdir(parents=True, exist_ok=True)
    reddit_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 35,
                        "timestamp": "2026-03-12T07:19:05",
                        "event_type": "round_start",
                        "simulated_hour": 10,
                    }
                ),
                json.dumps(
                    {
                        "round": 35,
                        "timestamp": "2026-03-12T07:19:15",
                        "agent_id": 9,
                        "agent_name": "Community Analyst",
                        "action_type": "CREATE_COMMENT",
                        "action_args": {"content": "comment"},
                        "success": True,
                    }
                ),
            ]
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
        config_path=str(config_path),
        platform_mode="parallel",
        current_round=40,
        total_rounds=120,
        twitter_current_round=40,
        reddit_current_round=34,
    )

    twitter_position = runner._read_action_log(
        str(twitter_log),
        0,
        state,
        "twitter",
    )
    reddit_position = runner._read_action_log(
        str(reddit_log),
        0,
        state,
        "reddit",
    )

    assert twitter_position == twitter_log.stat().st_size
    assert reddit_position == reddit_log.stat().st_size
    assert state.current_round == 41
    assert state.twitter_current_round == 41
    assert state.reddit_current_round == 34
    assert state.twitter_inflight_round == 42
    assert state.reddit_inflight_round == 35
    assert state.twitter_last_progress_at == "2026-03-12T07:19:25"
    assert state.reddit_last_progress_at == "2026-03-12T07:19:15"

    runner._save_run_state(state)
    reloaded_state = runner._load_run_state(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )

    assert reloaded_state is not None
    assert reloaded_state.twitter_inflight_round == 42
    assert reloaded_state.reddit_inflight_round == 35
    assert reloaded_state.twitter_last_progress_at == "2026-03-12T07:19:25"
    assert reloaded_state.reddit_last_progress_at == "2026-03-12T07:19:15"
