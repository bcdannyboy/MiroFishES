"""
OASIS simulation runner.

Runs simulations in the background, records each agent's actions, and supports
real-time status monitoring.
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
import shutil
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..models.probabilistic import (
    build_default_run_lifecycle,
    build_default_run_lineage,
)
from ..utils.logger import get_logger
from .outcome_extractor import OutcomeExtractor
from .phase_timing import PhaseTimingRecorder
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger('mirofish.simulation_runner')

# Tracks whether the cleanup hook has already been registered.
_cleanup_registered = False

# Platform detection.
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """Runner status."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent action record."""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """Per-round summary."""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """Real-time simulation run state."""
    simulation_id: str
    ensemble_id: Optional[str] = None
    run_id: Optional[str] = None
    run_key: Optional[str] = None
    run_dir: Optional[str] = None
    config_path: Optional[str] = None
    graph_id: Optional[str] = None
    base_graph_id: Optional[str] = None
    runtime_graph_id: Optional[str] = None
    platform_mode: str = "parallel"
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # Progress information.
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # Per-platform round and simulated time values for dual-platform display.
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_inflight_round: Optional[int] = None
    reddit_inflight_round: Optional[int] = None
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    twitter_last_progress_at: Optional[str] = None
    reddit_last_progress_at: Optional[str] = None
    
    # Platform status.
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # Platform completion flags, detected from simulation_end events in actions.jsonl.
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # Per-round summaries.
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # Recent actions for real-time frontend display.
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # Timestamps.
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # Error information.
    error: Optional[str] = None
    
    # Process ID used for stop operations.
    process_pid: Optional[int] = None

    @property
    def runtime_scope(self) -> str:
        """Expose whether this state represents the legacy root or one ensemble run."""
        if self.ensemble_id and self.run_id:
            return "ensemble_run"
        return "legacy"

    @property
    def runtime_key(self) -> Optional[str]:
        """Alias the persisted run key with a clearer public name."""
        return self.run_key

    @property
    def runtime_dir(self) -> Optional[str]:
        """Alias the persisted working directory with a clearer public name."""
        return self.run_dir
    
    def add_action(self, action: AgentAction):
        """Add an action to the recent-action list."""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "runtime_scope": self.runtime_scope,
            "runtime_key": self.runtime_key,
            "runtime_dir": self.runtime_dir,
            "run_key": self.run_key,
            "run_dir": self.run_dir,
            "config_path": self.config_path,
            "graph_id": self.base_graph_id or self.graph_id,
            "base_graph_id": self.base_graph_id or self.graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "platform_mode": self.platform_mode,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # Per-platform round and time values.
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_inflight_round": self.twitter_inflight_round,
            "reddit_inflight_round": self.reddit_inflight_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_last_progress_at": self.twitter_last_progress_at,
            "reddit_last_progress_at": self.reddit_last_progress_at,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """Return detailed state information including recent actions."""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    Simulation runner.

    Responsibilities:
    1. Run OASIS simulations in background processes.
    2. Parse runtime logs and record each agent's actions.
    3. Expose real-time status query interfaces.
    4. Support pause, stop, and resume operations.
    """
    
    # Run-state storage directory.
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # Script directory.
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # In-memory run state.
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # Stores stdout file handles.
    _stderr_files: Dict[str, Any] = {}  # Stores stderr file handles.
    
    # Graph-memory update configuration.
    _graph_memory_enabled: Dict[str, bool] = {}  # run_key -> enabled
    _RUNTIME_INPUTS_BY_PLATFORM = {
        "twitter": ("twitter_profiles.csv",),
        "reddit": ("reddit_profiles.json",),
        "parallel": ("twitter_profiles.csv", "reddit_profiles.json"),
    }

    @classmethod
    def _build_run_key(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        """Build a stable in-memory key for legacy and probabilistic runs."""
        if bool(ensemble_id) != bool(run_id):
            raise ValueError("ensemble_id and run_id must be provided together")
        if not ensemble_id:
            return simulation_id
        return f"{simulation_id}::{ensemble_id}::{run_id}"

    @classmethod
    def _get_simulation_dir(cls, simulation_id: str) -> str:
        """Return the legacy simulation directory root."""
        return os.path.join(cls.RUN_STATE_DIR, simulation_id)

    @classmethod
    def _get_run_dir(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> str:
        """Return the concrete working directory for one run context."""
        if run_dir:
            return run_dir

        sim_dir = cls._get_simulation_dir(simulation_id)
        if not ensemble_id and not run_id:
            return sim_dir

        if bool(ensemble_id) != bool(run_id):
            raise ValueError("ensemble_id and run_id must be provided together")

        return os.path.join(
            sim_dir,
            "ensemble",
            f"ensemble_{ensemble_id}",
            "runs",
            f"run_{run_id}",
        )

    @classmethod
    def _get_config_path(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        config_path: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> str:
        """Return the config artifact path for one run context."""
        if config_path:
            return config_path

        resolved_run_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        if ensemble_id and run_id:
            return os.path.join(resolved_run_dir, "resolved_config.json")
        return os.path.join(resolved_run_dir, "simulation_config.json")

    @classmethod
    def _get_run_state_path(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> str:
        """Return the persisted state path for one run context."""
        return os.path.join(
            cls._get_run_dir(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=run_dir,
            ),
            "run_state.json",
        )

    @classmethod
    def _get_run_manifest_path(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Return the run manifest path when the scope targets one ensemble member."""
        if not ensemble_id or not run_id:
            return None
        return os.path.join(
            cls._get_run_dir(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=run_dir,
            ),
            "run_manifest.json",
        )

    @classmethod
    def _get_run_phase_timings_path(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> str:
        """Return the timing artifact path for one runtime scope."""
        return os.path.join(
            cls._get_run_dir(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=run_dir,
            ),
            "run_phase_timings.json",
        )

    @classmethod
    def _get_run_phase_timing_recorder(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> PhaseTimingRecorder:
        """Build a run-scoped phase timing recorder for the resolved runtime root."""
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        return PhaseTimingRecorder(
            artifact_path=cls._get_run_phase_timings_path(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=context["run_dir"],
            ),
            scope_kind="run",
            scope_id=context["run_key"],
        )

    @classmethod
    def _resolve_run_context(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        config_path: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Normalize run identity and filesystem paths for one execution scope."""
        resolved_run_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        resolved_config_path = cls._get_config_path(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            config_path=config_path,
            run_dir=resolved_run_dir,
        )
        return {
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "run_key": cls._build_run_key(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
            ),
            "run_dir": resolved_run_dir,
            "config_path": resolved_config_path,
            "run_state_path": cls._get_run_state_path(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=resolved_run_dir,
            ),
        }

    @classmethod
    def _materialize_run_runtime_inputs(
        cls,
        simulation_id: str,
        platform: str,
        run_dir: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """
        Copy legacy prepare-time profile inputs into one run directory before launch.

        The runtime scripts still discover their profile inputs relative to the
        config path's directory. Until B2.4 teaches the scripts explicit run-dir
        arguments for every input, the runner stages the required profile files
        into the run root so each member run remains isolated on disk.
        """
        if not ensemble_id and not run_id:
            return

        required_inputs = cls._RUNTIME_INPUTS_BY_PLATFORM.get(platform)
        if not required_inputs:
            raise ValueError(f"Invalid platform type: {platform}")

        simulation_dir = cls._get_simulation_dir(simulation_id)
        missing_inputs = []
        os.makedirs(run_dir, exist_ok=True)

        for filename in required_inputs:
            source_path = os.path.join(simulation_dir, filename)
            target_path = os.path.join(run_dir, filename)
            if not os.path.exists(source_path):
                missing_inputs.append(filename)
                continue
            if not os.path.exists(target_path):
                shutil.copy2(source_path, target_path)

        if missing_inputs:
            raise ValueError(
                "Missing runtime input artifacts for "
                f"{cls._build_run_key(simulation_id, ensemble_id, run_id)}: "
                + ", ".join(missing_inputs)
            )

    @classmethod
    def _load_runtime_seed(
        cls,
        simulation_id: str,
        run_dir: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Read the best-available runtime seed from one stored run manifest.

        Runtime determinism is not complete until B2.4 removes module-global RNG
        usage inside the scripts. This helper still makes the seed explicit at
        the process boundary so the remaining gaps are narrow and documented.
        """
        if not ensemble_id and not run_id:
            return None

        manifest_path = os.path.join(run_dir, "run_manifest.json")
        if not os.path.exists(manifest_path):
            logger.warning(
                "Run manifest missing for runtime seed lookup: %s",
                cls._build_run_key(simulation_id, ensemble_id, run_id),
            )
            return None

        try:
            with open(manifest_path, 'r', encoding='utf-8') as handle:
                manifest = json.load(handle)
        except Exception as exc:
            logger.warning(
                "Failed to read run manifest for runtime seed lookup: %s, error=%s",
                cls._build_run_key(simulation_id, ensemble_id, run_id),
                exc,
            )
            return None

        seed_metadata = manifest.get("seed_metadata", {})
        if seed_metadata.get("resolution_seed") is not None:
            return int(seed_metadata["resolution_seed"])
        if manifest.get("root_seed") is not None:
            return int(manifest["root_seed"])
        return None

    @classmethod
    def _read_run_manifest(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load one persisted run manifest when the storage path exists."""
        manifest_path = cls._get_run_manifest_path(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        if not manifest_path or not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except Exception as e:
            logger.warning(
                "Failed to read run manifest: %s, error=%s",
                manifest_path,
                e,
            )
            return None

        manifest["lifecycle"] = build_default_run_lifecycle(manifest.get("lifecycle"))
        manifest["lineage"] = build_default_run_lineage(
            manifest.get("ensemble_id"),
            manifest.get("lineage"),
        )
        return manifest

    @classmethod
    def _update_run_manifest_status(
        cls,
        simulation_id: str,
        status: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        launch_reason: Optional[str] = None,
        increment_cleanup: bool = False,
    ) -> None:
        """Keep persisted run manifests aligned with runtime state transitions."""
        manifest_path = cls._get_run_manifest_path(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        if not manifest_path or not os.path.exists(manifest_path):
            return

        try:
            manifest = cls._read_run_manifest(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=run_dir,
            )
            if manifest is None:
                return

            manifest["status"] = status
            manifest["updated_at"] = datetime.now().isoformat()
            lifecycle = manifest.setdefault(
                "lifecycle",
                build_default_run_lifecycle(),
            )
            if launch_reason:
                lifecycle["start_count"] = lifecycle.get("start_count", 0) + 1
                if launch_reason == "retry":
                    lifecycle["retry_count"] = lifecycle.get("retry_count", 0) + 1
                lifecycle["last_launch_reason"] = launch_reason
            if increment_cleanup:
                lifecycle["cleanup_count"] = lifecycle.get("cleanup_count", 0) + 1

            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update run manifest status: {manifest_path}, error={e}")

    @classmethod
    def _update_run_manifest_artifact_path(
        cls,
        simulation_id: str,
        artifact_name: str,
        artifact_path: Optional[str],
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> None:
        """Append or remove run-manifest artifact references without replacing the file."""
        manifest_path = cls._get_run_manifest_path(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        if not manifest_path or not os.path.exists(manifest_path):
            return

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            artifact_paths = manifest.setdefault("artifact_paths", {})
            if artifact_path is None:
                artifact_paths.pop(artifact_name, None)
            else:
                artifact_paths[artifact_name] = artifact_path
            manifest["updated_at"] = datetime.now().isoformat()
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(
                "Failed to update run manifest artifact path: %s, error=%s",
                manifest_path,
                e,
            )

    @classmethod
    def _read_json_if_exists(cls, path: str) -> Optional[Dict[str, Any]]:
        """Return one JSON object when present, otherwise None."""
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read JSON artifact: {path}, error={e}")
            return None

    @classmethod
    def _persist_run_metrics_artifact(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        run_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist one run-scoped metrics artifact for probabilistic runtime storage.

        Legacy single-run simulations intentionally skip this path so the new
        analytics artifact layer does not mutate the historical runtime layout.
        """
        if not ensemble_id or not run_id:
            return None

        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
        )
        phase_timing = cls._get_run_phase_timing_recorder(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=context["run_dir"],
        )
        extractor = OutcomeExtractor(simulation_data_dir=cls.RUN_STATE_DIR)
        state = cls.get_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        try:
            with phase_timing.measure_phase(
                "metrics_extraction",
                metadata={"run_status": run_status},
            ) as phase_metadata:
                metrics_artifact = extractor.persist_run_metrics(
                    simulation_id,
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=context["run_dir"],
                    config_path=context["config_path"],
                    run_status=run_status,
                    platform_mode=state.platform_mode if state else None,
                )
                phase_metadata["metric_count"] = len(
                    metrics_artifact.get("metric_values", {})
                )
                phase_metadata["quality_status"] = metrics_artifact.get(
                    "quality_checks",
                    {},
                ).get("status")
        except Exception as e:
            logger.warning(
                "Failed to persist run metrics artifact for %s: %s",
                context["run_key"],
                e,
            )
            return None

        cls._update_run_manifest_artifact_path(
            simulation_id,
            "metrics",
            OutcomeExtractor.METRICS_FILENAME,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=context["run_dir"],
        )
        return metrics_artifact

    @classmethod
    def persist_run_metrics(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        run_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Public helper for targeted metrics extraction and test coverage."""
        return cls._persist_run_metrics_artifact(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
            config_path=config_path,
            run_status=run_status,
        )

    @classmethod
    def get_run_state(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Optional[SimulationRunState]:
        """Get the current run state."""
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        run_key = context["run_key"]
        if run_key in cls._run_states:
            return cls._run_states[run_key]
        
        # Try loading from disk.
        state = cls._load_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=context["run_dir"],
        )
        if state:
            cls._run_states[run_key] = state
        return state
    
    @classmethod
    def _load_run_state(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
    ) -> Optional[SimulationRunState]:
        """Load run state from disk."""
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=run_dir,
        )
        state_file = context["run_state_path"]
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                ensemble_id=data.get("ensemble_id", ensemble_id),
                run_id=data.get("run_id", run_id),
                run_key=data.get("run_key", context["run_key"]),
                run_dir=data.get("run_dir", context["run_dir"]),
                config_path=data.get("config_path", context["config_path"]),
                graph_id=data.get("graph_id"),
                base_graph_id=data.get("base_graph_id", data.get("graph_id")),
                runtime_graph_id=data.get("runtime_graph_id"),
                platform_mode=data.get("platform_mode", "parallel"),
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # Per-platform round and time values.
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_inflight_round=data.get("twitter_inflight_round"),
                reddit_inflight_round=data.get("reddit_inflight_round"),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_last_progress_at=data.get("twitter_last_progress_at"),
                reddit_last_progress_at=data.get("reddit_last_progress_at"),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # Load recent actions.
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))
            
            return state
        except Exception as e:
            logger.error(f"Failed to load run state: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """Persist run state to disk."""
        context = cls._resolve_run_context(
            state.simulation_id,
            ensemble_id=state.ensemble_id,
            run_id=state.run_id,
            config_path=state.config_path,
            run_dir=state.run_dir,
        )
        state.run_key = state.run_key or context["run_key"]
        state.run_dir = state.run_dir or context["run_dir"]
        state.config_path = state.config_path or context["config_path"]
        os.makedirs(state.run_dir, exist_ok=True)
        state_file = context["run_state_path"]
        
        data = state.to_detail_dict()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        cls._run_states[state.run_key] = state
    
    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        config_path: Optional[str] = None,
        run_dir: Optional[str] = None,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # Optional maximum round limit used to truncate long simulations.
        enable_graph_memory_update: bool = False,  # Whether to push activity updates into the Zep graph.
        close_environment_on_complete: bool = False,  # Whether to exit after completion instead of entering command-wait mode.
        graph_id: str = None,  # Compatibility alias for the runtime write graph.
        base_graph_id: Optional[str] = None,
        runtime_graph_id: Optional[str] = None,
    ) -> SimulationRunState:
        """
        Start a simulation.
        
        Args:
            simulation_id: Simulation ID.
            platform: Target platform (`twitter`, `reddit`, or `parallel`).
            max_rounds: Optional maximum number of rounds.
            enable_graph_memory_update: Whether to dynamically update agent activity into the Zep graph.
            close_environment_on_complete: Whether the launched runtime should
                exit on completion instead of staying alive for follow-up
                interview commands.
            graph_id: Compatibility alias for the runtime write graph.
            base_graph_id: Immutable project graph ID used for retrieval/reporting.
            runtime_graph_id: Optional runtime-only graph ID used for write-backs.
            
        Returns:
            SimulationRunState
        """
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            config_path=config_path,
            run_dir=run_dir,
        )
        run_key = context["run_key"]
        phase_timing = cls._get_run_phase_timing_recorder(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=context["run_dir"],
        )

        with phase_timing.measure_phase(
            "run_startup",
            metadata={
                "platform": platform,
                "legacy_scope": not bool(ensemble_id and run_id),
            },
        ) as phase_metadata:
            # Check whether the simulation is already running.
            existing = cls.get_run_state(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
            )
            if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
                raise ValueError(f"Simulation is already running: {run_key}")

            # Load the simulation configuration.
            sim_dir = context["run_dir"]
            config_path = context["config_path"]

            if not os.path.exists(config_path):
                raise ValueError("Simulation configuration does not exist. Call /prepare first.")

            launch_reason = None
            manifest = cls._read_run_manifest(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=sim_dir,
            )
            if manifest is not None:
                lifecycle = manifest.get("lifecycle", {})
                launch_reason = (
                    "retry"
                    if lifecycle.get("start_count", 0) > 0
                    else "initial_start"
                )

            cls._materialize_run_runtime_inputs(
                simulation_id,
                platform=platform,
                run_dir=sim_dir,
                ensemble_id=ensemble_id,
                run_id=run_id,
            )

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            effective_base_graph_id = base_graph_id or config.get("base_graph_id") or graph_id
            effective_runtime_graph_id = (
                runtime_graph_id
                or config.get("runtime_graph_id")
                or graph_id
            )

            # Initialize the runtime state.
            time_config = config.get("time_config", {})
            total_hours = time_config.get("total_simulation_hours", 72)
            minutes_per_round = time_config.get("minutes_per_round", 30)
            total_rounds = int(total_hours * 60 / minutes_per_round)

            # Truncate to the configured maximum round count if requested.
            if max_rounds is not None and max_rounds > 0:
                original_rounds = total_rounds
                total_rounds = min(total_rounds, max_rounds)
                if total_rounds < original_rounds:
                    logger.info(f"Round count truncated: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")

            phase_metadata["total_rounds"] = total_rounds
            phase_metadata["total_simulation_hours"] = total_hours
            phase_metadata["launch_reason"] = launch_reason or "initial_start"

            state = SimulationRunState(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_key=run_key,
                run_dir=sim_dir,
                config_path=config_path,
                graph_id=effective_base_graph_id,
                base_graph_id=effective_base_graph_id,
                runtime_graph_id=effective_runtime_graph_id,
                platform_mode=platform,
                runner_status=RunnerStatus.STARTING,
                total_rounds=total_rounds,
                total_simulation_hours=total_hours,
                started_at=datetime.now().isoformat(),
            )

            cls._save_run_state(state)

            # Create the graph-memory updater if enabled.
            if enable_graph_memory_update:
                if not effective_runtime_graph_id:
                    raise ValueError("graph_id is required when graph-memory updates are enabled")

                try:
                    ZepGraphMemoryManager.create_updater(run_key, effective_runtime_graph_id)
                    cls._graph_memory_enabled[run_key] = True
                    logger.info(
                        "Enabled graph-memory updates: run_key=%s base_graph_id=%s runtime_graph_id=%s",
                        run_key,
                        effective_base_graph_id,
                        effective_runtime_graph_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create graph-memory updater: {e}")
                    cls._graph_memory_enabled[run_key] = False
            else:
                cls._graph_memory_enabled[run_key] = False

            # Select the runner script under backend/scripts/.
            if platform == "twitter":
                script_name = "run_twitter_simulation.py"
                state.twitter_running = True
            elif platform == "reddit":
                script_name = "run_reddit_simulation.py"
                state.reddit_running = True
            else:
                script_name = "run_parallel_simulation.py"
                state.twitter_running = True
                state.reddit_running = True

            script_path = os.path.join(cls.SCRIPTS_DIR, script_name)

            if not os.path.exists(script_path):
                raise ValueError(f"Script does not exist: {script_path}")

            # Create the action queue.
            action_queue = Queue()
            cls._action_queues[run_key] = action_queue

            # Start the simulation subprocess.
            try:
                # Build the command with absolute paths.
                # Log layout:
                #   twitter/actions.jsonl - Twitter action log
                #   reddit/actions.jsonl  - Reddit action log
                #   simulation.log        - Main process log

                cmd = [
                    sys.executable,  # Python interpreter.
                    script_path,
                    "--config", config_path,  # Use the absolute config path.
                ]

                runtime_seed = cls._load_runtime_seed(
                    simulation_id,
                    run_dir=sim_dir,
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                )
                if ensemble_id and run_id:
                    cmd.extend([
                        "--run-dir",
                        sim_dir,
                        "--run-id",
                        run_id,
                    ])
                    if runtime_seed is not None:
                        cmd.extend(["--seed", str(runtime_seed)])

                # Add the round-limit argument when requested.
                if max_rounds is not None and max_rounds > 0:
                    cmd.extend(["--max-rounds", str(max_rounds)])
                if close_environment_on_complete:
                    cmd.append("--no-wait")

                # Use a shared main log file to avoid blocking on full stdout/stderr pipes.
                main_log_path = os.path.join(sim_dir, "simulation.log")
                main_log_file = open(main_log_path, 'w', encoding='utf-8')

                # Force UTF-8 so third-party libraries do not rely on platform defaults.
                env = os.environ.copy()
                env['PYTHONUTF8'] = '1'  # Makes UTF-8 the default text encoding on Python 3.7+.
                env['PYTHONIOENCODING'] = 'utf-8'  # Keeps stdout/stderr on UTF-8.

                # Run in the simulation directory so generated databases and logs land there.
                # start_new_session=True creates a new process group for later termination.
                process = subprocess.Popen(
                    cmd,
                    cwd=sim_dir,
                    stdout=main_log_file,
                    stderr=subprocess.STDOUT,  # Send stderr into the same log file.
                    text=True,
                    encoding='utf-8',  # Explicit text encoding.
                    bufsize=1,
                    env=env,  # Pass the UTF-8 environment overrides.
                    start_new_session=True,  # Create a fresh process group for clean shutdown.
                )

                # Keep file handles so they can be closed during cleanup.
                cls._stdout_files[run_key] = main_log_file
                cls._stderr_files[run_key] = None  # No separate stderr handle is needed.

                state.process_pid = process.pid
                state.runner_status = RunnerStatus.RUNNING
                cls._processes[run_key] = process
                cls._save_run_state(state)
                cls._update_run_manifest_status(
                    simulation_id,
                    "running",
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                    launch_reason=launch_reason,
                )

                # Start the monitor thread.
                monitor_thread = threading.Thread(
                    target=cls._monitor_simulation,
                    args=(simulation_id, ensemble_id, run_id),
                    daemon=True
                )
                monitor_thread.start()
                cls._monitor_threads[run_key] = monitor_thread

                logger.info(f"Simulation started successfully: {run_key}, pid={process.pid}, platform={platform}")

            except Exception as e:
                state.runner_status = RunnerStatus.FAILED
                state.error = str(e)
                cls._save_run_state(state)
                cls._update_run_manifest_status(
                    simulation_id,
                    "failed",
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                )
                raise

            return state
    
    @classmethod
    def _monitor_simulation(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        """Monitor the simulation process and parse action logs."""
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        run_key = context["run_key"]
        sim_dir = context["run_dir"]
        
        # Per-platform action logs in the new log layout.
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(run_key)
        state = cls.get_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None:  # The process is still running.
                # Read the Twitter action log.
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # Read the Reddit action log.
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # Persist state.
                cls._save_run_state(state)
                time.sleep(2)
            
            # Read the logs one final time after the process exits.
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # Finalize process completion.
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                cls._update_run_manifest_status(
                    simulation_id,
                    "completed",
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                )
                logger.info(f"Simulation completed: {run_key}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # Pull the tail of the main log into the error message.
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # Use the last 2000 characters.
                except Exception:
                    pass
                state.error = f"Process exited with code {exit_code}, error: {error_info}"
                cls._update_run_manifest_status(
                    simulation_id,
                    "failed",
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                )
                logger.error(f"Simulation failed: {run_key}, error={state.error}")

            state.twitter_running = False
            state.reddit_running = False
            if state.ensemble_id and state.run_id:
                cls._persist_run_metrics_artifact(
                    simulation_id,
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                    run_status=state.runner_status.value,
                )
            cls._save_run_state(state)
            
        except Exception as e:
            logger.error(f"Monitor thread failed: {run_key}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._update_run_manifest_status(
                simulation_id,
                "failed",
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=sim_dir,
            )
            if state.ensemble_id and state.run_id:
                cls._persist_run_metrics_artifact(
                    simulation_id,
                    ensemble_id=ensemble_id,
                    run_id=run_id,
                    run_dir=sim_dir,
                    run_status=state.runner_status.value,
                )
            cls._save_run_state(state)
        
        finally:
            # Stop the graph-memory updater.
            if cls._graph_memory_enabled.get(run_key, False):
                try:
                    ZepGraphMemoryManager.stop_updater(run_key)
                    logger.info(f"Stopped graph-memory updates: run_key={run_key}")
                except Exception as e:
                    logger.error(f"Failed to stop graph-memory updater: {e}")
                cls._graph_memory_enabled.pop(run_key, None)
            
            # Release process resources.
            cls._processes.pop(run_key, None)
            cls._action_queues.pop(run_key, None)
            
            # Close log file handles.
            if run_key in cls._stdout_files:
                try:
                    cls._stdout_files[run_key].close()
                except Exception:
                    pass
                cls._stdout_files.pop(run_key, None)
            if run_key in cls._stderr_files and cls._stderr_files[run_key]:
                try:
                    cls._stderr_files[run_key].close()
                except Exception:
                    pass
                cls._stderr_files.pop(run_key, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        Read an action log file.
        
        Args:
            log_path: Path to the log file.
            position: Previous read offset.
            state: Runtime state object.
            platform: Platform name (`twitter` or `reddit`).
            
        Returns:
            Updated read offset.
        """
        # Check whether graph-memory updates are enabled.
        run_key = state.run_key or cls._build_run_key(
            state.simulation_id,
            ensemble_id=state.ensemble_id,
            run_id=state.run_id,
        )
        graph_memory_enabled = cls._graph_memory_enabled.get(run_key, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(run_key)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # Handle event-type entries.
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                event_timestamp = action_data.get(
                                    "timestamp",
                                    datetime.now().isoformat(),
                                )
                                
                                # Detect simulation_end events and mark the platform as complete.
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        state.twitter_inflight_round = None
                                        state.twitter_last_progress_at = event_timestamp
                                        logger.info(f"Twitter simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        state.reddit_inflight_round = None
                                        state.reddit_last_progress_at = event_timestamp
                                        logger.info(f"Reddit simulation completed: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # Check whether every enabled platform has completed.
                                    # If only one platform ran, check only that platform.
                                    # If both platforms ran, both must complete.
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"All enabled platform simulations completed: {state.simulation_id}")
                                
                                elif event_type == "round_start":
                                    round_num = action_data.get("round", 0)
                                    if platform == "twitter":
                                        state.twitter_inflight_round = round_num or None
                                        state.twitter_last_progress_at = event_timestamp
                                    elif platform == "reddit":
                                        state.reddit_inflight_round = round_num or None
                                        state.reddit_last_progress_at = event_timestamp
                                
                                # Update round information from round_end events.
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)
                                    
                                    # Update per-platform round and simulated time values.
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        if (
                                            state.twitter_inflight_round is not None
                                            and round_num >= state.twitter_inflight_round
                                        ):
                                            state.twitter_inflight_round = None
                                        state.twitter_simulated_hours = simulated_hours
                                        state.twitter_last_progress_at = event_timestamp
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        if (
                                            state.reddit_inflight_round is not None
                                            and round_num >= state.reddit_inflight_round
                                        ):
                                            state.reddit_inflight_round = None
                                        state.reddit_simulated_hours = simulated_hours
                                        state.reddit_last_progress_at = event_timestamp
                                    
                                    # Use the largest round number as the overall round.
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # Use the largest simulated time as the overall simulated time.
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)
                                
                                state.updated_at = datetime.now().isoformat()
                                
                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)
                            
                            # Update the current round.
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            if platform == "twitter":
                                if action.round_num > state.twitter_current_round:
                                    state.twitter_inflight_round = action.round_num
                                state.twitter_last_progress_at = action.timestamp
                            elif platform == "reddit":
                                if action.round_num > state.reddit_current_round:
                                    state.reddit_inflight_round = action.round_num
                                state.reddit_last_progress_at = action.timestamp
                            
                            # Forward activity to Zep when graph-memory updates are enabled.
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f"Failed to read action log: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        Check whether all enabled platforms have completed.
        
        Platform enablement is inferred from whether the corresponding
        `actions.jsonl` file exists.
        
        Returns:
            True if every enabled platform has completed.
        """
        sim_dir = state.run_dir or cls._get_run_dir(
            state.simulation_id,
            ensemble_id=state.ensemble_id,
            run_id=state.run_id,
        )
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # Determine which platforms were enabled based on file presence.
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # Return False if any enabled platform is still incomplete.
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # At least one platform must have been enabled and completed.
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        Terminate a process and its children across platforms.
        
        Args:
            process: Process to terminate.
            simulation_id: Simulation ID, used for logging.
            timeout: Time to wait before escalating termination.
        """
        if IS_WINDOWS:
            # Windows: use taskkill to stop the full process tree.
            # /F = force kill, /T = include child processes.
            logger.info(f"Terminating process tree (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # Try graceful termination first.
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Escalate to a force kill.
                    logger.warning(f"Process did not respond; forcing termination: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill failed, falling back to terminate(): {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: terminate the entire process group.
            # With start_new_session=True, the process-group ID equals the main PID.
            pgid = os.getpgid(process.pid)
            logger.info(f"Terminating process group (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # Send SIGTERM to the full process group first.
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Fall back to SIGKILL if SIGTERM was not enough.
                logger.warning(f"Process group did not respond to SIGTERM; forcing termination: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> SimulationRunState:
        """Stop a simulation."""
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        run_key = context["run_key"]
        state = cls.get_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not state:
            raise ValueError(f"Simulation does not exist: {run_key}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"Simulation is not running: {run_key}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # Terminate the subprocess.
        process = cls._processes.get(run_key)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, run_key)
            except ProcessLookupError:
                # The process is already gone.
                pass
            except Exception as e:
                logger.error(f"Failed to terminate process group: {run_key}, error={e}")
                # Fall back to terminating the process directly.
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        cls._update_run_manifest_status(
            simulation_id,
            "stopped",
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=context["run_dir"],
        )
        if state.ensemble_id and state.run_id:
            cls._persist_run_metrics_artifact(
                simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_dir=context["run_dir"],
                run_status=state.runner_status.value,
            )
        
        # Stop the graph-memory updater.
        if cls._graph_memory_enabled.get(run_key, False):
            try:
                ZepGraphMemoryManager.stop_updater(run_key)
                logger.info(f"Stopped graph-memory updates: run_key={run_key}")
            except Exception as e:
                logger.error(f"Failed to stop graph-memory updater: {e}")
            cls._graph_memory_enabled.pop(run_key, None)
        
        logger.info(f"Simulation stopped: {run_key}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Read actions from a single action file.
        
        Args:
            file_path: Path to the action log file.
            default_platform: Default platform to use when the record has no platform field.
            platform_filter: Platform filter.
            agent_id: Agent ID filter.
            round_num: Round filter.
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Skip non-action records such as simulation_start and round_end events.
                    if "event_type" in data:
                        continue
                    
                    # Skip records without agent_id values because they are not agent actions.
                    if "agent_id" not in data:
                        continue
                    
                    # Prefer the platform recorded in the event, then fall back to the default.
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # Apply filters.
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get the full action history across all platforms, without pagination.
        
        Args:
            simulation_id: Simulation ID.
            platform: Platform filter (`twitter` or `reddit`).
            agent_id: Agent filter.
            round_num: Round filter.
            
        Returns:
            The complete action list, sorted newest-first by timestamp.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        actions = []
        
        # Read Twitter actions and infer the platform from the file path.
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # Auto-fill the platform field.
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # Read Reddit actions and infer the platform from the file path.
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # Auto-fill the platform field.
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # Fall back to the legacy single-file layout if per-platform files do not exist.
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # Legacy files should already contain platform fields.
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # Sort newest-first by timestamp.
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get paginated action history.
        
        Args:
            simulation_id: Simulation ID.
            limit: Maximum number of results to return.
            offset: Pagination offset.
            platform: Platform filter.
            agent_id: Agent filter.
            round_num: Round filter.
            
        Returns:
            Action list.
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # Apply pagination.
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get the simulation timeline aggregated by round.
        
        Args:
            simulation_id: Simulation ID.
            start_round: First round to include.
            end_round: Last round to include.
            
        Returns:
            Per-round summary information.
        """
        actions = cls.get_actions(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            limit=10000,
        )
        
        # Group actions by round.
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # Convert the grouped structure into a sorted list.
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get per-agent statistics.
        
        Returns:
            A list of agent statistics.
        """
        actions = cls.get_actions(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            limit=10000,
        )
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # Sort by total action count.
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clean simulation runtime logs so the simulation can be restarted from scratch.
        
        This removes:
        - run_state.json
        - metrics.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db (simulation database)
        - reddit_simulation.db (simulation database)
        - env_status.json (environment status)
        
        Note: this does not remove the configuration file (`simulation_config.json`)
        or profile files.
        
        Args:
            simulation_id: Simulation ID.
            
        Returns:
            Cleanup result information.
        """
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        run_key = context["run_key"]
        sim_dir = context["run_dir"]
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "Simulation directory does not exist; nothing to clean."}
        
        cleaned_files = []
        errors = []
        
        # Files to delete, including database files.
        files_to_delete = [
            "run_state.json",
            "metrics.json",
            "run_phase_timings.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter platform database.
            "reddit_simulation.db",   # Reddit platform database.
            "env_status.json",        # Environment status file.
        ]
        
        # Directories to clean, including action logs.
        dirs_to_clean = ["twitter", "reddit"]
        
        # Delete top-level files.
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"Failed to delete {filename}: {str(e)}")
        
        # Delete action logs inside platform directories.
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(f"Failed to delete {dir_name}/actions.jsonl: {str(e)}")
        
        # Remove any in-memory run state.
        if run_key in cls._run_states:
            del cls._run_states[run_key]
        if run_key in cls._processes:
            cls._processes.pop(run_key, None)
        if run_key in cls._action_queues:
            cls._action_queues.pop(run_key, None)
        if run_key in cls._monitor_threads:
            cls._monitor_threads.pop(run_key, None)
        if run_key in cls._graph_memory_enabled:
            cls._graph_memory_enabled.pop(run_key, None)
        if run_key in cls._stdout_files:
            try:
                cls._stdout_files[run_key].close()
            except Exception:
                pass
            cls._stdout_files.pop(run_key, None)
        if run_key in cls._stderr_files:
            try:
                if cls._stderr_files[run_key]:
                    cls._stderr_files[run_key].close()
            except Exception:
                pass
            cls._stderr_files.pop(run_key, None)

        cls._update_run_manifest_status(
            simulation_id,
            "prepared",
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=sim_dir,
            increment_cleanup=True,
        )
        cls._update_run_manifest_artifact_path(
            simulation_id,
            "metrics",
            None,
            ensemble_id=ensemble_id,
            run_id=run_id,
            run_dir=sim_dir,
        )
        
        logger.info(f"Finished cleaning simulation logs: {run_key}, deleted files: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # Prevent duplicate cleanup.
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        Clean up every running simulation process.
        
        Called during server shutdown to ensure all child processes are terminated.
        """
        # Prevent duplicate cleanup.
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # Check whether any cleanup work is actually needed.
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # Nothing to clean, return silently.
        
        logger.info("Cleaning up all simulation processes...")
        
        # Stop all graph-memory updaters first.
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"Failed to stop graph-memory updaters: {e}")
        cls._graph_memory_enabled.clear()
        
        # Copy the mapping to avoid mutating during iteration.
        processes = list(cls._processes.items())
        
        for run_key, process in processes:
            try:
                if process.poll() is None:  # The process is still running.
                    logger.info(f"Terminating simulation process: {run_key}, pid={process.pid}")
                    
                    try:
                        # Use the cross-platform termination helper.
                        cls._terminate_process(process, run_key, timeout=5)
                    except (ProcessLookupError, OSError):
                        # The process may already be gone, so try direct termination.
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # Update run_state.json.
                    state = cls._run_states.get(run_key)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "Server shutdown interrupted the simulation."
                        cls._save_run_state(state)
                        cls._update_run_manifest_status(
                            state.simulation_id,
                            "stopped",
                            ensemble_id=state.ensemble_id,
                            run_id=state.run_id,
                            run_dir=state.run_dir,
                        )
                        if state.ensemble_id and state.run_id:
                            cls._persist_run_metrics_artifact(
                                state.simulation_id,
                                ensemble_id=state.ensemble_id,
                                run_id=state.run_id,
                                run_dir=state.run_dir,
                                run_status=state.runner_status.value,
                            )
                    
                    # Update state.json as well, marking the state as stopped.
                    try:
                        if not state.ensemble_id and not state.run_id:
                            sim_dir = cls._get_simulation_dir(state.simulation_id)
                            state_file = os.path.join(sim_dir, "state.json")
                            logger.info(f"Attempting to update state.json: {state_file}")
                            if os.path.exists(state_file):
                                with open(state_file, 'r', encoding='utf-8') as f:
                                    state_data = json.load(f)
                                state_data['status'] = 'stopped'
                                state_data['updated_at'] = datetime.now().isoformat()
                                with open(state_file, 'w', encoding='utf-8') as f:
                                    json.dump(state_data, f, indent=2, ensure_ascii=False)
                                logger.info(f"Updated state.json to stopped: {state.simulation_id}")
                            else:
                                logger.warning(f"state.json does not exist: {state_file}")
                    except Exception as state_err:
                        logger.warning(f"Failed to update state.json: {run_key}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"Failed to clean process: {run_key}, error={e}")
        
        # Clean up file handles.
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # Clear in-memory state.
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("Simulation process cleanup completed")
    
    @classmethod
    def register_cleanup(cls):
        """
        Register cleanup handlers.
        
        Called when the Flask app starts so shutdown also cleans up simulation processes.
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # In Flask debug mode, only register cleanup in the reloader child process.
        # WERKZEUG_RUN_MAIN=true indicates the active reloader child process.
        # In non-debug mode this variable is absent, and cleanup should still be registered.
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # In debug mode, register only in the reloader child process; otherwise always register.
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # Mark as registered so the parent process does not retry.
            return
        
        # Preserve the original signal handlers.
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP exists only on Unix systems such as macOS and Linux.
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """Signal handler: clean up simulation processes, then call the original handler."""
            # Only log when there is cleanup work to do.
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"Received signal {signum}; starting cleanup...")
            cls.cleanup_all_simulations()
            
            # Call the original handler so Flask can exit normally.
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP is sent when the terminal closes.
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # Fall back to the default behavior: exit cleanly.
                    sys.exit(0)
            else:
                # If the original handler is not callable (for example SIG_DFL), use the default behavior.
                raise KeyboardInterrupt
        
        # Register an atexit handler as a fallback.
        atexit.register(cls.cleanup_all_simulations)
        
        # Register signal handlers, but only from the main thread.
        try:
            # SIGTERM: the default signal sent by kill.
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C.
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: terminal closed (Unix only).
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # Outside the main thread, only the atexit handler can be used.
            logger.warning("Could not register signal handlers outside the main thread; using only atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        Get the list of all currently running simulation IDs.
        """
        running = []
        for run_key, process in cls._processes.items():
            if process.poll() is None:
                running.append(run_key)
        return running
    
    # ============== Interview helpers ==============
    
    @classmethod
    def check_env_alive(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> bool:
        """
        Check whether the simulation environment is alive and can receive Interview commands.

        Args:
            simulation_id: Simulation ID.

        Returns:
            True if the environment is alive, otherwise False.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def get_env_status_detail(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed simulation-environment status information.

        Args:
            simulation_id: Simulation ID.

        Returns:
            A status dictionary containing `status`, `twitter_available`,
            `reddit_available`, and `timestamp`.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        Interview a single agent.

        Args:
            simulation_id: Simulation ID.
            agent_id: Agent ID
            prompt: Interview question.
            platform: Optional platform override.
                - `"twitter"`: interview only on Twitter
                - `"reddit"`: interview only on Reddit
                - `None`: in dual-platform simulations, interview on both and return the merged result
            timeout: Timeout in seconds.

        Returns:
            Interview result dictionary.

        Raises:
            ValueError: Simulation does not exist or the environment is not running.
            TimeoutError: Timed out waiting for a response.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"Simulation environment is not running or has been closed; cannot execute Interview: {simulation_id}")

        logger.info(f"Sending Interview command: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Interview multiple agents in a batch.

        Args:
            simulation_id: Simulation ID.
            interviews: Interview request list, each item containing
                `{"agent_id": int, "prompt": str, "platform": str (optional)}`.
            platform: Optional default platform, overridden by each interview item.
                - `"twitter"`: default to Twitter only
                - `"reddit"`: default to Reddit only
                - `None`: in dual-platform simulations, interview each agent on both platforms
            timeout: Timeout in seconds.

        Returns:
            Batch interview result dictionary.

        Raises:
            ValueError: Simulation does not exist or the environment is not running.
            TimeoutError: Timed out waiting for a response.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"Simulation environment is not running or has been closed; cannot execute Interview: {simulation_id}")

        logger.info(f"Sending batch Interview command: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        *,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        Interview every agent in the simulation.

        Uses the same question for all agents.

        Args:
            simulation_id: Simulation ID.
            prompt: Interview question shared across all agents.
            platform: Optional platform override.
                - `"twitter"`: interview only on Twitter
                - `"reddit"`: interview only on Reddit
                - `None`: in dual-platform simulations, interview on both platforms
            timeout: Timeout in seconds.

        Returns:
            Global interview result dictionary.
        """
        context = cls._resolve_run_context(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        sim_dir = context["run_dir"]
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        # Load all agent information from the simulation configuration.
        config_path = context["config_path"]
        if not os.path.exists(config_path):
            raise ValueError(f"Simulation configuration does not exist: {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"No agents were found in the simulation configuration: {simulation_id}")

        # Build the batch interview payload.
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"Sending global Interview command: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Close the simulation environment without stopping the runner process.
        
        Sends a close-environment command so the simulation can leave wait-for-command mode gracefully.
        
        Args:
            simulation_id: Simulation ID.
            timeout: Timeout in seconds.
            
        Returns:
            Operation result dictionary.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation does not exist: {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": "The environment is already closed."
            }
        
        logger.info(f"Sending close-environment command: simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": "Close-environment command sent.",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # A timeout here may simply mean the environment is in the middle of shutting down.
            return {
                "success": True,
                "message": "Close-environment command sent (response timed out; the environment may already be shutting down)."
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Read Interview history from a single database."""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to read Interview history ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        ensemble_id: Optional[str] = None,
        run_id: Optional[str] = None,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get Interview history from the simulation databases.
        
        Args:
            simulation_id: Simulation ID.
            platform: Platform type (`reddit`, `twitter`, or `None`).
                - `"reddit"`: fetch only Reddit history
                - `"twitter"`: fetch only Twitter history
                - `None`: fetch history from both platforms
            agent_id: Optional agent ID filter.
            limit: Per-platform result limit.
            
        Returns:
            Interview history records.
        """
        sim_dir = cls._get_run_dir(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        
        results = []
        
        # Determine which platforms to query.
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # Query both platforms when no platform is specified.
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # Sort newest-first by timestamp.
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Limit the total number of results when querying multiple platforms.
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results
