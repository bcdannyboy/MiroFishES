"""
Simulation-related API routes.

Step 2: Zep entity retrieval and filtering, plus OASIS simulation
preparation and execution (fully automated).
"""

import os
import json
import threading
import traceback
from datetime import datetime
from typing import Any, Optional
from flask import request, jsonify, send_file

from . import simulation_bp
from ..config import Config
from ..models.probabilistic import (
    DEFAULT_OUTCOME_METRICS,
    DEFAULT_UNCERTAINTY_PROFILE,
    EnsembleSpec,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    build_default_run_lifecycle,
    build_default_run_lineage,
    get_prepare_capabilities_domain,
    normalize_uncertainty_profile,
    normalize_forecast_brief,
    validate_outcome_metric_id,
)
from ..services.ensemble_manager import EnsembleManager
from ..services.scenario_clusterer import ScenarioClusterer
from ..services.sensitivity_analyzer import SensitivityAnalyzer
from ..services.zep_entity_reader import ZepEntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.report_agent import ReportManager
from ..services.runtime_graph_manager import RuntimeGraphManager
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..utils.logger import get_logger
from ..models.project import ProjectManager

logger = get_logger('mirofish.api.simulation')


# Optimized interview prompt prefix.
# This prefix helps prevent the agent from calling tools and keeps responses in plain text.
INTERVIEW_PROMPT_PREFIX = (
    "Based on your persona, all past memories, and prior actions, reply directly in plain text "
    "without calling any tools: "
)


def optimize_interview_prompt(prompt: str) -> str:
    """
    Optimize an interview prompt by adding a prefix that discourages tool calls.

    Args:
        prompt: The original prompt.

    Returns:
        The optimized prompt.
    """
    if not prompt:
        return prompt
    # Avoid adding the prefix twice.
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


def _normalize_requested_outcome_metrics(outcome_metrics) -> list:
    """Extract stable metric identifiers from request payloads."""
    if outcome_metrics is None:
        return []
    if not isinstance(outcome_metrics, list):
        raise ValueError("outcome_metrics must be a list when probabilistic_mode=true")

    normalized = []
    seen = set()
    for item in outcome_metrics:
        metric_id = None
        if isinstance(item, str):
            metric_id = item.strip()
        elif isinstance(item, dict):
            metric_id = str(item.get("metric_id", "")).strip()
        else:
            raise ValueError("outcome_metrics entries must be strings or dictionaries")

        if metric_id and metric_id not in seen:
            normalized.append(metric_id)
            seen.add(metric_id)

    return normalized


def _validate_probabilistic_prepare_request(
    probabilistic_mode: bool,
    uncertainty_profile,
    outcome_metrics,
    forecast_brief,
) -> tuple[Optional[str], list, Optional[dict]]:
    """Validate the minimal probabilistic prepare contract before work starts."""
    if not probabilistic_mode:
        if (
            uncertainty_profile is not None
            or outcome_metrics not in (None, [], ())
            or forecast_brief is not None
        ):
            raise ValueError(
                "uncertainty_profile, outcome_metrics, and forecast_brief require probabilistic_mode=true"
            )
        return None, [], None

    if not Config.PROBABILISTIC_PREPARE_ENABLED:
        raise ValueError(
            "Probabilistic prepare is disabled. Set PROBABILISTIC_PREPARE_ENABLED=true to enable it."
        )

    normalized_profile = normalize_uncertainty_profile(uncertainty_profile)
    normalized_outcome_metrics = _normalize_requested_outcome_metrics(outcome_metrics)
    if not normalized_outcome_metrics:
        normalized_outcome_metrics = list(DEFAULT_OUTCOME_METRICS)

    for metric_id in normalized_outcome_metrics:
        validate_outcome_metric_id(metric_id)

    normalized_forecast_brief = normalize_forecast_brief(
        forecast_brief,
        uncertainty_profile=normalized_profile,
        outcome_metric_ids=normalized_outcome_metrics,
    )

    return (
        normalized_profile,
        normalized_outcome_metrics,
        normalized_forecast_brief.to_dict() if normalized_forecast_brief else None,
    )


def _require_probabilistic_ensemble_storage_enabled() -> None:
    """Fail fast when the storage-only ensemble slice is intentionally off."""
    if not _ensemble_storage_enabled():
        raise ValueError(
            "Probabilistic ensemble storage is disabled. "
            "Set PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED=true to enable it "
            "(legacy alias: ENSEMBLE_RUNTIME_ENABLED)."
        )


def _build_ensemble_spec_from_request(data: dict) -> EnsembleSpec:
    """Validate and normalize the storage-layer ensemble request payload."""
    if data.get("run_count") is None:
        raise ValueError("run_count is required")

    root_seed = data.get("root_seed")
    if root_seed is not None:
        root_seed = int(root_seed)

    return EnsembleSpec(
        run_count=int(data["run_count"]),
        max_concurrency=int(data.get("max_concurrency", 1)),
        root_seed=root_seed,
        sampling_mode=data.get("sampling_mode", "seeded"),
    )


def _build_run_summary(run_payload: dict) -> dict:
    """Expose lightweight run metadata without embedding full resolved configs."""
    manifest = run_payload.get("run_manifest", {})
    return {
        "simulation_id": run_payload.get("simulation_id"),
        "ensemble_id": run_payload.get("ensemble_id"),
        "run_id": run_payload.get("run_id"),
        "path": run_payload.get("path"),
        "status": manifest.get("status"),
        "root_seed": manifest.get("root_seed"),
        "seed_metadata": manifest.get("seed_metadata", {}),
        "generated_at": manifest.get("generated_at"),
        "artifact_paths": manifest.get("artifact_paths", {}),
        "config_artifact": manifest.get("config_artifact"),
        "lifecycle": manifest.get("lifecycle", {}),
        "lineage": manifest.get("lineage", {}),
    }


def _build_ensemble_response_payload(ensemble_payload: dict) -> dict:
    """Shape one ensemble response for APIs without over-returning run configs."""
    runs = [
        _build_run_summary(run_payload)
        for run_payload in ensemble_payload.get("runs", [])
    ]
    return {
        "simulation_id": ensemble_payload.get("simulation_id"),
        "ensemble_id": ensemble_payload.get("ensemble_id"),
        "path": ensemble_payload.get("path"),
        "spec": ensemble_payload.get("spec", {}),
        "state": ensemble_payload.get("state", {}),
        "runs": runs,
        "total_runs": len(runs),
    }


def _build_requested_prepare_artifact_summary(
    simulation_id: str,
    probabilistic_mode: bool,
    uncertainty_profile: Optional[str],
    outcome_metric_ids: list,
    forecast_brief: Optional[dict],
    existing_summary: dict,
) -> dict:
    """Expose the requested prepare contract even before async work completes."""
    summary = dict(existing_summary or {})
    if not probabilistic_mode:
        return summary

    default_metric_ids = outcome_metric_ids or list(DEFAULT_OUTCOME_METRICS)
    profile = uncertainty_profile or DEFAULT_UNCERTAINTY_PROFILE
    artifact_filenames = {
        "legacy_config": "simulation_config.json",
        "base_config": "simulation_config.base.json",
        "forecast_brief": "forecast_brief.json",
        "uncertainty_spec": "uncertainty_spec.json",
        "outcome_spec": "outcome_spec.json",
        "prepared_snapshot": "prepared_snapshot.json",
    }

    artifacts = {}
    existing_artifacts = summary.get("artifacts", {})
    for artifact_name, filename in artifact_filenames.items():
        artifact = dict(existing_artifacts.get(artifact_name, {}))
        artifact.setdefault("filename", filename)
        artifact.setdefault(
            "path",
            os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, filename),
        )
        artifact.setdefault("relative_path", filename)
        if artifact_name != "legacy_config" and (
            artifact_name != "forecast_brief" or forecast_brief is not None
        ):
            artifact.setdefault("planned", True)
        artifacts[artifact_name] = artifact

    feature_metadata = dict(summary.get("feature_metadata", {}))
    feature_metadata.update({
        "probabilistic_mode": True,
        "legacy_config_compatible": True,
        "sampling_enabled": False,
        "uncertainty_profile": profile,
        "outcome_metrics": default_metric_ids,
        "forecast_brief_attached": forecast_brief is not None,
    })

    summary.update({
        "schema_version": summary.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
        "generator_version": summary.get(
            "generator_version", PROBABILISTIC_GENERATOR_VERSION
        ),
        "simulation_id": simulation_id,
        "mode": "probabilistic",
        "probabilistic_mode": True,
        "uncertainty_profile": profile,
        "outcome_metrics": default_metric_ids,
        "forecast_brief": forecast_brief,
        "lineage": summary.get("lineage", {}),
        "feature_metadata": feature_metadata,
        "artifacts": artifacts,
    })
    return summary


def _get_simulation_or_404(simulation_id: str):
    """Return the current simulation state or a Flask 404 response tuple."""
    manager = SimulationManager()
    state = manager.get_simulation(simulation_id)
    if state:
        return state, None

    return None, (
        jsonify({
            "success": False,
            "error": f"Simulation does not exist: {simulation_id}"
        }),
        404,
    )


def _get_ensemble_run_or_error(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Return one stored run payload or a Flask error tuple."""
    try:
        return EnsembleManager().load_run(simulation_id, ensemble_id, run_id), None
    except ValueError as e:
        return None, (
            jsonify({
                "success": False,
                "error": str(e),
            }),
            _ensemble_value_error_status_code(str(e)),
        )


def _get_ensemble_or_error(simulation_id: str, ensemble_id: str):
    """Return one stored ensemble payload or a Flask error tuple."""
    try:
        return EnsembleManager().load_ensemble(simulation_id, ensemble_id), None
    except ValueError as e:
        return None, (
            jsonify({
                "success": False,
                "error": str(e),
            }),
            _ensemble_value_error_status_code(str(e)),
        )


def _get_runner_run_state(
    simulation_id: str,
    ensemble_id: Optional[str] = None,
    run_id: Optional[str] = None,
):
    """Call the runner state helper with a fallback for lightweight legacy test stubs."""
    try:
        return SimulationRunner.get_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
    except TypeError:
        return SimulationRunner.get_run_state(simulation_id)


def _ensemble_storage_enabled() -> bool:
    """Prefer the explicit probabilistic storage flag while keeping the alias readable."""
    return bool(
        getattr(
            Config,
            "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
            getattr(Config, "ENSEMBLE_RUNTIME_ENABLED", False),
        )
    )


def _resolve_base_graph_id_for_simulation(state) -> Optional[str]:
    """Resolve the immutable base graph for one simulation."""
    if getattr(state, "base_graph_id", None):
        return state.base_graph_id
    if getattr(state, "graph_id", None):
        return state.graph_id

    project = ProjectManager.get_project(state.project_id)
    if project:
        return project.graph_id
    return None


def _normalize_runtime_start_request(data: dict):
    """Validate shared runtime launch arguments for legacy and ensemble run starts."""
    platform = data.get('platform', 'parallel')
    max_rounds = data.get('max_rounds')
    enable_graph_memory_update = data.get('enable_graph_memory_update', False)
    force = data.get('force', False)
    close_environment_on_complete = data.get('close_environment_on_complete', False)

    if max_rounds is not None:
        try:
            max_rounds = int(max_rounds)
            if max_rounds <= 0:
                raise ValueError("max_rounds must be a positive integer")
        except (ValueError, TypeError):
            raise ValueError("max_rounds must be a valid integer")

    if platform not in ['twitter', 'reddit', 'parallel']:
        raise ValueError(
            f"Invalid platform type: {platform}. Allowed values: twitter/reddit/parallel"
        )

    return (
        platform,
        max_rounds,
        enable_graph_memory_update,
        force,
        close_environment_on_complete,
    )


def _build_idle_ensemble_run_status_payload(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
    storage_status: str,
    base_graph_id: Optional[str] = None,
    runtime_graph_id: Optional[str] = None,
) -> dict:
    """Return a stable idle payload for stored runs that have not launched yet."""
    return {
        "simulation_id": simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": run_id,
        "graph_id": base_graph_id,
        "base_graph_id": base_graph_id,
        "runtime_graph_id": runtime_graph_id,
        "runtime_scope": "ensemble_run",
        "runtime_key": f"{simulation_id}::{ensemble_id}::{run_id}",
        "runner_status": "idle",
        "storage_status": storage_status,
        "current_round": 0,
        "total_rounds": 0,
        "progress_percent": 0,
        "simulated_hours": 0,
        "total_simulation_hours": 0,
        "twitter_actions_count": 0,
        "reddit_actions_count": 0,
        "total_actions_count": 0,
    }


def _resolve_run_graph_ids(run_payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Resolve stored run graph ownership while keeping graph_id as a base-graph alias."""
    run_manifest = run_payload.get("run_manifest", {})
    resolved_config = run_payload.get("resolved_config", {})
    base_graph_id = (
        run_manifest.get("base_graph_id")
        or run_manifest.get("graph_id")
        or resolved_config.get("base_graph_id")
        or resolved_config.get("graph_id")
    )
    runtime_graph_id = (
        run_manifest.get("runtime_graph_id")
        or resolved_config.get("runtime_graph_id")
    )
    return base_graph_id, runtime_graph_id


def _runner_status_name(run_state) -> str:
    """Normalize real enum-backed runner states and lightweight test doubles."""
    status = getattr(run_state, "runner_status", "idle")
    return getattr(status, "value", status)


ACTIVE_RUNNER_STATUSES = frozenset({"starting", "running", "stopping", "paused"})


def _sort_run_payloads_by_run_id(run_payloads: list[dict]) -> list[dict]:
    """Keep batch-start ordering stable regardless of storage or request order."""
    return sorted(
        run_payloads,
        key=lambda run_payload: str(run_payload.get("run_id") or ""),
    )


def _normalize_requested_run_ids(data: dict) -> Optional[list[str]]:
    """Normalize an optional explicit ensemble-run selection."""
    requested_run_ids = data.get("run_ids")
    if requested_run_ids is None:
        return None
    if not isinstance(requested_run_ids, list) or not requested_run_ids:
        raise ValueError("run_ids must be a non-empty list when provided")

    normalized: list[str] = []
    seen = set()
    for item in requested_run_ids:
        run_id = str(item or "").strip()
        if run_id.startswith("run_"):
            run_id = run_id.removeprefix("run_")
        if len(run_id) != 4 or not run_id.isdigit():
            raise ValueError(f"Invalid run_id: {item}")
        if run_id not in seen:
            normalized.append(run_id)
            seen.add(run_id)
    return normalized


def _resolve_requested_ensemble_runs(
    ensemble_payload: dict,
    requested_run_ids: Optional[list[str]],
) -> list[dict]:
    """Resolve one requested run subset in a stable, explicit order."""
    runs = ensemble_payload.get("runs", [])
    if not runs:
        raise ValueError("The ensemble does not contain any stored runs")

    if requested_run_ids is None:
        return _sort_run_payloads_by_run_id(runs)

    run_map = {run_payload.get("run_id"): run_payload for run_payload in runs}
    missing_run_ids = [
        run_id for run_id in requested_run_ids if run_id not in run_map
    ]
    if missing_run_ids:
        raise ValueError(
            "The ensemble does not contain the requested run_ids: "
            + ", ".join(missing_run_ids)
        )
    return _sort_run_payloads_by_run_id(
        [run_map[run_id] for run_id in requested_run_ids]
    )


def _collect_active_requested_ensemble_run_ids(
    simulation_id: str,
    ensemble_id: str,
    requested_runs: list[dict],
) -> list[str]:
    """Report requested runs that still have active in-memory runtime state."""
    active_run_ids: list[str] = []
    for run_payload in _sort_run_payloads_by_run_id(requested_runs):
        existing_state = _get_runner_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_payload["run_id"],
        )
        if existing_state and _runner_status_name(existing_state) in ACTIVE_RUNNER_STATUSES:
            active_run_ids.append(run_payload["run_id"])
    return active_run_ids


def _plan_ensemble_batch_start(
    simulation_id: str,
    ensemble_id: str,
    ensemble_payload: dict,
    requested_runs: list[dict],
    max_concurrency: int,
    force: bool,
) -> dict:
    """Translate one batch-start request into explicit active/start/defer buckets."""
    all_runs = _sort_run_payloads_by_run_id(ensemble_payload.get("runs", []))
    requested_runs = _sort_run_payloads_by_run_id(requested_runs)
    active_run_ids = _collect_active_requested_ensemble_run_ids(
        simulation_id,
        ensemble_id,
        all_runs,
    )
    requested_run_id_set = {
        run_payload["run_id"] for run_payload in requested_runs
    }
    active_requested_run_ids = [
        run_id for run_id in active_run_ids if run_id in requested_run_id_set
    ]
    active_other_run_ids = [
        run_id for run_id in active_run_ids if run_id not in requested_run_id_set
    ]
    active_requested_run_id_set = set(active_requested_run_ids)
    inactive_requested_runs = [
        run_payload
        for run_payload in requested_runs
        if run_payload["run_id"] not in active_requested_run_id_set
    ]
    available_start_slots = max(max_concurrency - len(active_run_ids), 0)
    restart_runs = (
        [
            run_payload
            for run_payload in requested_runs
            if run_payload["run_id"] in active_requested_run_id_set
        ]
        if force
        else []
    )
    start_runs = inactive_requested_runs[:available_start_slots]
    deferred_runs = inactive_requested_runs[available_start_slots:]

    return {
        "requested_runs": requested_runs,
        "restart_runs": restart_runs,
        "start_runs": start_runs,
        "deferred_runs": deferred_runs,
        "active_run_ids": active_run_ids,
        "active_requested_run_ids": active_requested_run_ids,
        "active_other_run_ids": active_other_run_ids,
        "available_start_slots": available_start_slots,
    }


def _build_ensemble_run_capacity_error(
    simulation_id: str,
    ensemble_payload: dict,
    run_id: str,
    *,
    force: bool,
) -> Optional[dict]:
    """Report when a member-run launch would exceed the stored ensemble ceiling."""
    ensemble_id = ensemble_payload.get("ensemble_id")
    max_concurrency = int(
        ensemble_payload.get("spec", {}).get("max_concurrency", 1) or 1
    )
    active_run_ids = _collect_active_requested_ensemble_run_ids(
        simulation_id,
        ensemble_id,
        _sort_run_payloads_by_run_id(ensemble_payload.get("runs", [])),
    )
    active_other_run_ids = [
        active_run_id
        for active_run_id in active_run_ids
        if active_run_id != run_id
    ]

    if run_id in active_run_ids and not force:
        return None

    if len(active_other_run_ids) < max_concurrency:
        return None

    action = "restart" if force and run_id in active_run_ids else "launch"
    active_run_list = ", ".join(active_other_run_ids)
    return {
        "error": (
            f"Cannot {action} ensemble run {run_id} because the ensemble is already at "
            f"max_concurrency={max_concurrency}. Active run IDs: {active_run_list}."
        ),
        "active_run_ids": active_other_run_ids,
        "max_concurrency": max_concurrency,
    }


def _build_ensemble_run_runtime_payload(
    simulation_id: str,
    ensemble_id: str,
    run_payload: dict,
) -> dict:
    """Merge runtime state with stored-manifest metadata for one run."""
    run_id = run_payload.get("run_id")
    manifest = run_payload.get("run_manifest", {})
    base_graph_id, runtime_graph_id = _resolve_run_graph_ids(run_payload)
    runtime_state = _get_runner_run_state(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    if runtime_state:
        payload = runtime_state.to_dict()
        payload["storage_status"] = manifest.get("status", payload.get("runner_status"))
    else:
        payload = _build_idle_ensemble_run_status_payload(
            simulation_id,
            ensemble_id,
            run_id,
            storage_status=manifest.get("status", "prepared"),
            base_graph_id=base_graph_id,
            runtime_graph_id=runtime_graph_id,
        )

    payload["path"] = run_payload.get("path")
    payload["graph_id"] = base_graph_id
    payload["base_graph_id"] = base_graph_id
    payload["runtime_graph_id"] = runtime_graph_id
    payload["root_seed"] = manifest.get("root_seed")
    payload["seed_metadata"] = manifest.get("seed_metadata", {})
    payload["generated_at"] = manifest.get("generated_at")
    payload["config_artifact"] = manifest.get("config_artifact")
    payload["artifact_paths"] = manifest.get("artifact_paths", {})
    return payload


def _cleanup_ensemble_run_storage_fallback(run_payload: dict) -> dict:
    """Provide storage-only cleanup when the lightweight test stub lacks runner cleanup."""
    simulation_id = run_payload.get("simulation_id")
    ensemble_id = run_payload.get("ensemble_id")
    run_id = run_payload.get("run_id")
    run_dir = run_payload.get("run_dir") or run_payload.get("path")
    if not run_dir or not os.path.exists(run_dir):
        _clear_runner_runtime_state_if_present(
            simulation_id,
            ensemble_id,
            run_id,
        )
        return {
            "success": True,
            "cleaned_files": [],
            "errors": None,
        }

    cleaned_files = []
    errors = []
    files_to_delete = [
        "run_state.json",
        "metrics.json",
        "simulation.log",
        "stdout.log",
        "stderr.log",
        "twitter_simulation.db",
        "reddit_simulation.db",
        "env_status.json",
    ]
    for filename in files_to_delete:
        file_path = os.path.join(run_dir, filename)
        if not os.path.exists(file_path):
            continue
        try:
            os.remove(file_path)
            cleaned_files.append(filename)
        except Exception as e:
            errors.append(f"Failed to delete {filename}: {str(e)}")

    for dir_name in ("twitter", "reddit"):
        actions_path = os.path.join(run_dir, dir_name, "actions.jsonl")
        if not os.path.exists(actions_path):
            continue
        try:
            os.remove(actions_path)
            cleaned_files.append(f"{dir_name}/actions.jsonl")
        except Exception as e:
            errors.append(f"Failed to delete {dir_name}/actions.jsonl: {str(e)}")

    manifest_path = os.path.join(run_dir, EnsembleManager.RUN_MANIFEST_FILENAME)
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as handle:
            manifest = json.load(handle)
        base_graph_id = manifest.get("base_graph_id") or manifest.get("graph_id")
        lifecycle = build_default_run_lifecycle(manifest.get("lifecycle"))
        lifecycle["cleanup_count"] += 1
        manifest["lifecycle"] = lifecycle
        manifest["lineage"] = build_default_run_lineage(
            manifest.get("ensemble_id"),
            manifest.get("lineage"),
        )
        manifest["status"] = "prepared"
        manifest["graph_id"] = base_graph_id
        manifest["base_graph_id"] = base_graph_id
        manifest["runtime_graph_id"] = None
        manifest["updated_at"] = datetime.now().isoformat()
        artifact_paths = dict(manifest.get("artifact_paths", {}))
        artifact_paths.pop("metrics", None)
        manifest["artifact_paths"] = artifact_paths
        with open(manifest_path, 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

    resolved_config_path = os.path.join(run_dir, EnsembleManager.RESOLVED_CONFIG_FILENAME)
    if os.path.exists(resolved_config_path):
        with open(resolved_config_path, 'r', encoding='utf-8') as handle:
            resolved_config = json.load(handle)
        base_graph_id = (
            resolved_config.get("base_graph_id")
            or resolved_config.get("graph_id")
        )
        resolved_config["graph_id"] = base_graph_id
        resolved_config["base_graph_id"] = base_graph_id
        resolved_config["runtime_graph_id"] = None
        resolved_config["updated_at"] = datetime.now().isoformat()
        with open(resolved_config_path, 'w', encoding='utf-8') as handle:
            json.dump(resolved_config, handle, ensure_ascii=False, indent=2)

    _clear_runner_runtime_state_if_present(
        simulation_id,
        ensemble_id,
        run_id,
    )

    return {
        "success": len(errors) == 0,
        "cleaned_files": cleaned_files,
        "errors": errors if errors else None,
    }


def _clear_runner_runtime_state_if_present(
    simulation_id: Optional[str],
    ensemble_id: Optional[str],
    run_id: Optional[str],
) -> None:
    """Best-effort cleanup for stale in-memory runner state after storage cleanup."""
    if not simulation_id:
        return

    run_key = (
        f"{simulation_id}::{ensemble_id}::{run_id}"
        if ensemble_id and run_id
        else simulation_id
    )

    for attr_name in (
        "_run_states",
        "_action_queues",
        "_monitor_threads",
        "_graph_memory_enabled",
    ):
        mapping = getattr(SimulationRunner, attr_name, None)
        if isinstance(mapping, dict):
            mapping.pop(run_key, None)

    process_mapping = getattr(SimulationRunner, "_processes", None)
    if isinstance(process_mapping, dict):
        process = process_mapping.get(run_key)
        if process is not None:
            poll = getattr(process, "poll", None)
            if not callable(poll) or poll() is not None:
                process_mapping.pop(run_key, None)

    for attr_name in ("_stdout_files", "_stderr_files"):
        mapping = getattr(SimulationRunner, attr_name, None)
        if not isinstance(mapping, dict):
            continue
        handle = mapping.pop(run_key, None)
        if handle is None:
            continue
        try:
            handle.close()
        except Exception:
            pass


def _effective_ensemble_run_status(payload: dict) -> str:
    """Prefer persisted terminal storage truth when runtime state is unavailable."""
    runner_status = str(payload.get("runner_status", "idle"))
    if runner_status != "idle":
        return runner_status

    storage_status = str(payload.get("storage_status", "prepared"))
    if storage_status in {"prepared", "completed", "failed", "stopped"}:
        return storage_status
    return runner_status


def _derive_ensemble_runtime_status(
    run_status_payloads: list[dict],
) -> tuple[str, dict[str, int], dict[str, int]]:
    """Collapse one run list into a poll-safe ensemble lifecycle summary."""
    runner_status_counts: dict[str, int] = {}
    storage_status_counts: dict[str, int] = {}
    for payload in run_status_payloads:
        runner_status = str(payload.get("runner_status", "idle"))
        storage_status = str(payload.get("storage_status", "unknown"))
        runner_status_counts[runner_status] = runner_status_counts.get(runner_status, 0) + 1
        storage_status_counts[storage_status] = storage_status_counts.get(storage_status, 0) + 1

    total_runs = len(run_status_payloads)
    if total_runs == 0:
        return "empty", runner_status_counts, storage_status_counts

    effective_status_counts: dict[str, int] = {}
    for payload in run_status_payloads:
        effective_status = _effective_ensemble_run_status(payload)
        effective_status_counts[effective_status] = effective_status_counts.get(effective_status, 0) + 1

    active_statuses = {"starting", "running", "stopping", "paused"}
    if any(effective_status_counts.get(status, 0) for status in active_statuses):
        return "running", runner_status_counts, storage_status_counts
    if effective_status_counts.get("failed", 0):
        if effective_status_counts.get("failed", 0) == total_runs:
            return "failed", runner_status_counts, storage_status_counts
        return "mixed", runner_status_counts, storage_status_counts
    if effective_status_counts.get("completed", 0) == total_runs:
        return "completed", runner_status_counts, storage_status_counts
    if effective_status_counts.get("stopped", 0) == total_runs:
        return "stopped", runner_status_counts, storage_status_counts
    if effective_status_counts.get("prepared", 0) == total_runs:
        return "prepared", runner_status_counts, storage_status_counts
    return "mixed", runner_status_counts, storage_status_counts


def _build_ensemble_runtime_status_payload(
    simulation_id: str,
    ensemble_payload: dict,
    run_payloads: list[dict],
    limit: int,
) -> dict:
    """Build one ensemble-level runtime summary on top of run-scoped state."""
    ensemble_id = ensemble_payload.get("ensemble_id")
    run_status_payloads = [
        _build_ensemble_run_runtime_payload(
            simulation_id,
            ensemble_id,
            run_payload,
        )
        for run_payload in run_payloads
    ]
    ensemble_status, runner_status_counts, storage_status_counts = (
        _derive_ensemble_runtime_status(run_status_payloads)
    )
    status_counts: dict[str, int] = {}
    for payload in run_status_payloads:
        user_visible_status = _effective_ensemble_run_status(payload)
        status_counts[user_visible_status] = status_counts.get(user_visible_status, 0) + 1
    total_runs = len(run_status_payloads)
    aggregate_progress = round(
        sum(float(payload.get("progress_percent", 0) or 0) for payload in run_status_payloads)
        / total_runs,
        2,
    ) if total_runs else 0.0
    total_actions_count = sum(
        int(payload.get("total_actions_count", 0) or 0)
        for payload in run_status_payloads
    )

    return {
        "simulation_id": simulation_id,
        "ensemble_id": ensemble_id,
        "ensemble_status": ensemble_status,
        "status": ensemble_status,
        "spec": ensemble_payload.get("spec", {}),
        "state": ensemble_payload.get("state", {}),
        "total_runs": total_runs,
        "limit": limit,
        "truncated": total_runs > limit,
        "progress_percent": aggregate_progress,
        "total_actions_count": total_actions_count,
        "status_counts": status_counts,
        "runner_status_counts": runner_status_counts,
        "storage_status_counts": storage_status_counts,
        "active_run_ids": [
            payload["run_id"]
            for payload in run_status_payloads
            if payload.get("runner_status") in {"starting", "running", "stopping", "paused"}
        ],
        "completed_run_ids": [
            payload["run_id"]
            for payload in run_status_payloads
            if _effective_ensemble_run_status(payload) == "completed"
        ],
        "failed_run_ids": [
            payload["run_id"]
            for payload in run_status_payloads
            if _effective_ensemble_run_status(payload) == "failed"
        ],
        "runs": run_status_payloads[:limit],
    }


def _start_ensemble_run_runtime(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
    platform: str,
    max_rounds: Optional[int],
    enable_graph_memory_update: bool,
    force: bool,
    close_environment_on_complete: bool,
    state,
) -> dict:
    """Reuse the run-scoped launch path for both member-run and ensemble-run starts."""
    existing_state = _get_runner_run_state(
        simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    force_restarted = False
    if existing_state and _runner_status_name(existing_state) in ("running", "starting"):
        if not force:
            raise ValueError(
                "The ensemble run is currently running. Call the run-scoped stop "
                "endpoint first, or use force=true to restart it."
            )

        SimulationRunner.stop_simulation(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )

    if force:
        SimulationRunner.cleanup_simulation_logs(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        force_restarted = True

    base_graph_id = _resolve_base_graph_id_for_simulation(state)
    runtime_graph_id = None
    if enable_graph_memory_update:
        graph_context = RuntimeGraphManager().provision_runtime_graph(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            state=state,
            force_reset=force,
        )
        base_graph_id = graph_context.get("base_graph_id") or base_graph_id
        runtime_graph_id = graph_context.get("runtime_graph_id")

    run_state = SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
        platform=platform,
        max_rounds=max_rounds,
        enable_graph_memory_update=enable_graph_memory_update,
        close_environment_on_complete=close_environment_on_complete,
        graph_id=runtime_graph_id if enable_graph_memory_update else base_graph_id,
        base_graph_id=base_graph_id,
        runtime_graph_id=runtime_graph_id,
    )

    response_data = run_state.to_dict()
    response_data["graph_id"] = base_graph_id
    response_data["base_graph_id"] = base_graph_id
    response_data["runtime_graph_id"] = runtime_graph_id
    response_data["graph_memory_update_enabled"] = enable_graph_memory_update
    response_data["force_restarted"] = force_restarted
    response_data["close_environment_on_complete"] = close_environment_on_complete
    if max_rounds:
        response_data["max_rounds_applied"] = max_rounds
    return response_data


def _ensemble_value_error_status_code(message: str) -> int:
    """Keep ensemble API error semantics explicit and consistent."""
    lowered = message.lower()
    if "disabled" in lowered:
        return 403
    if "does not exist" in lowered:
        return 404
    return 400


# ============== Entity Retrieval Endpoints ==============


@simulation_bp.route('/prepare/capabilities', methods=['GET'])
def get_prepare_capabilities():
    """Expose the live probabilistic prepare capability surface to the frontend."""
    storage_enabled = _ensemble_storage_enabled()
    return jsonify({
        "success": True,
        "data": {
            "probabilistic_prepare_enabled": Config.PROBABILISTIC_PREPARE_ENABLED,
            "probabilistic_ensemble_storage_enabled": storage_enabled,
            "ensemble_runtime_enabled": storage_enabled,
            "probabilistic_report_enabled": Config.PROBABILISTIC_REPORT_ENABLED,
            "probabilistic_interaction_enabled": Config.PROBABILISTIC_INTERACTION_ENABLED,
            "calibrated_probability_enabled": Config.CALIBRATED_PROBABILITY_ENABLED,
            "calibration_artifact_support_enabled": Config.CALIBRATED_PROBABILITY_ENABLED,
            "calibration_surface_mode": "artifact-gated",
            "calibration_min_case_count": Config.CALIBRATION_MIN_CASE_COUNT,
            "calibration_min_positive_case_count": Config.CALIBRATION_MIN_POSITIVE_CASE_COUNT,
            "calibration_min_negative_case_count": Config.CALIBRATION_MIN_NEGATIVE_CASE_COUNT,
            "calibration_min_supported_bin_count": Config.CALIBRATION_MIN_SUPPORTED_BIN_COUNT,
            "calibration_bin_count": Config.CALIBRATION_BIN_COUNT,
            **get_prepare_capabilities_domain(),
        },
    })


@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    Get all filtered entities from the graph.

    Only returns nodes that match the predefined entity types
    (that is, nodes whose labels are more specific than `Entity` alone).

    Query parameters:
        entity_types: Optional comma-separated list of entity types for additional filtering.
        enrich: Whether to include related edge information. Defaults to `true`.
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY is not configured"
            }), 500

        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        logger.info(
            f"Fetching graph entities: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}"
        )

        reader = ZepEntityReader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to fetch graph entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Get detailed information for a single entity."""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY is not configured"
            }), 500

        reader = ZepEntityReader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)

        if not entity:
            return jsonify({
                "success": False,
                "error": f"Entity does not exist: {entity_uuid}"
            }), 404

        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to fetch entity details: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get all entities of a specific type."""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY is not configured"
            }), 500

        enrich = request.args.get('enrich', 'true').lower() == 'true'

        reader = ZepEntityReader()
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )

        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })

    except Exception as e:
        logger.error(f"Failed to fetch entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Management Endpoints ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Create a new simulation.

    Note: parameters such as `max_rounds` are generated intelligently by the LLM
    and do not need to be set manually here.

    Request body (JSON):
        {
            "project_id": "proj_xxxx",      // required
            "graph_id": "mirofish_xxxx",    // optional; pulled from the project if omitted
            "enable_twitter": true,         // optional, defaults to true
            "enable_reddit": true           // optional, defaults to true
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "mirofish_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}

        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project does not exist: {project_id}"
            }), 404

        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "The project graph has not been built yet. Please call /api/graph/build first."
            }), 400

        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )

        return jsonify({
            "success": True,
            "data": state.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to create simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(
    simulation_id: str,
    require_probabilistic_artifacts: bool = False,
) -> tuple:
    """
    Check whether a simulation has already been fully prepared.

    Conditions:
    1. `state.json` exists and the status is `ready`
    2. Required files exist: `reddit_profiles.json`, `twitter_profiles.csv`,
       and `simulation_config.json`

    Note: runtime scripts (`run_*.py`) remain in `backend/scripts/` and are no
    longer copied into the simulation directory.

    Args:
        simulation_id: Simulation ID.

    Returns:
        `(is_prepared: bool, info: dict)`
    """
    import os
    from ..config import Config

    simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

    # Check whether the simulation directory exists.
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulation directory does not exist"}

    # Required files list (scripts live in backend/scripts/ and are excluded here).
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]

    # Check which files are present.
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)

    if missing_files:
        return False, {
            "reason": "Required files are missing",
            "missing_files": missing_files,
            "existing_files": existing_files
        }

    # Check the status stored in state.json.
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)

        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)

        # Detailed logging.
        logger.debug(
            f"Checking simulation preparation state: {simulation_id}, "
            f"status={status}, config_generated={config_generated}"
        )

        # If config_generated=True and the files exist, preparation is considered complete.
        # The following statuses all imply that preparation already finished:
        # - ready: preparation completed, ready to run
        # - preparing: if config_generated=True, preparation has effectively finished
        # - running: preparation must already have completed
        # - completed: the run finished, so preparation had already completed
        # - stopped: the run was stopped after preparation completed
        # - failed: the run failed, but preparation itself completed
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]
        if status in prepared_statuses and config_generated:
            artifact_summary = SimulationManager().get_prepare_artifact_summary(simulation_id)
            if require_probabilistic_artifacts and not artifact_summary.get("probabilistic_mode"):
                missing_probabilistic_artifacts = (
                    artifact_summary.get("missing_probabilistic_artifacts")
                    or artifact_summary.get("feature_metadata", {}).get(
                        "missing_probabilistic_artifacts", []
                    )
                )
                missing_artifact_message = ""
                if missing_probabilistic_artifacts:
                    missing_artifact_message = (
                        "Missing probabilistic prepare artifacts: "
                        + ", ".join(missing_probabilistic_artifacts)
                    )

                return False, {
                    "reason": (
                        missing_artifact_message
                        or "Legacy prepare artifacts exist but probabilistic sidecars are missing"
                    ),
                    "status": status,
                    "config_generated": config_generated,
                    "prepared_artifact_summary": artifact_summary,
                }
            # Gather file statistics.
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")

            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0

            # If the status is preparing but the files are complete, auto-promote to ready.
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Automatically updated simulation state: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"Failed to auto-update simulation state: {e}")

            logger.info(
                f"Simulation {simulation_id} check result: preparation completed "
                f"(status={status}, config_generated={config_generated})"
            )
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files,
                "prepared_artifact_summary": artifact_summary,
            }
        else:
            logger.warning(
                f"Simulation {simulation_id} check result: preparation not completed "
                f"(status={status}, config_generated={config_generated})"
            )
            return False, {
                "reason": (
                    "Status is not in the prepared list or config_generated is false: "
                    f"status={status}, config_generated={config_generated}"
                ),
                "status": status,
                "config_generated": config_generated
            }

    except Exception as e:
        return False, {"reason": f"Failed to read state file: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    Prepare a simulation environment asynchronously with all parameters generated by the LLM.

    This is a long-running operation. The endpoint returns a `task_id`
    immediately, and progress can then be queried through
    `POST /api/simulation/prepare/status`.

    Features:
    - Automatically detects completed preparation work to avoid duplicate generation
    - Returns existing results directly if preparation is already complete
    - Supports forced regeneration via `force_regenerate=true`

    Steps:
    1. Check whether completed preparation work already exists
    2. Read and filter entities from the Zep graph
    3. Generate an OASIS agent profile for each entity, with retries
    4. Use the LLM to generate simulation configuration, with retries
    5. Save configuration files and preparation artifacts

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",                   // required: simulation ID
            "entity_types": ["Student", "PublicFigure"],  // optional: entity types to include
            "use_llm_for_profiles": true,                 // optional: whether to use the LLM for personas
            "parallel_profile_count": 5,                  // optional: parallel persona generation count, default 5
            "force_regenerate": false                     // optional: force regeneration, default false
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // returned for newly started tasks
                "status": "preparing|ready",
                "message": "Preparation task started|Completed preparation already exists",
                "already_prepared": true|false    // whether preparation was already complete
            }
        }
    """
    from ..models.task import TaskManager, TaskStatus

    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        probabilistic_mode = bool(data.get('probabilistic_mode', False))
        uncertainty_profile, outcome_metric_ids, normalized_forecast_brief = _validate_probabilistic_prepare_request(
            probabilistic_mode=probabilistic_mode,
            uncertainty_profile=data.get('uncertainty_profile'),
            outcome_metrics=data.get('outcome_metrics'),
            forecast_brief=data.get('forecast_brief'),
        )

        # Check whether regeneration is being forced.
        force_regenerate = data.get('force_regenerate', False)
        logger.info(
            f"Handling /prepare request: simulation_id={simulation_id}, force_regenerate={force_regenerate}"
        )

        # Check whether preparation is already complete to avoid duplicate generation.
        if not force_regenerate:
            logger.debug(f"Checking whether simulation {simulation_id} is already prepared...")
            is_prepared, prepare_info = _check_simulation_prepared(
                simulation_id,
                require_probabilistic_artifacts=probabilistic_mode,
            )
            if (
                is_prepared
                and probabilistic_mode
                and normalized_forecast_brief is not None
                and (prepare_info or {}).get("forecast_brief") != normalized_forecast_brief
            ):
                is_prepared = False
                prepare_info = manager.get_prepare_artifact_summary(simulation_id)
            logger.debug(f"Preparation check result: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulation {simulation_id} is already prepared, skipping duplicate generation")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": "Completed preparation already exists; no regeneration is needed",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulation {simulation_id} is not prepared; starting a preparation task")

        # Load the required information from the project.
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project does not exist: {state.project_id}"
            }), 404

        # Load the simulation requirement.
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "The project is missing simulation_requirement"
            }), 400

        # Load the project document text.
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""

        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)

        # ========== Fetch entity count synchronously before the background task starts ==========
        # This lets the frontend know the expected agent count immediately after calling /prepare.
        try:
            logger.info(f"Fetching entity count synchronously: graph_id={state.graph_id}")
            reader = ZepEntityReader()
            # Read entities quickly without edge enrichment; only the count is needed here.
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # Skip edge enrichment for speed.
            )
            # Save the entity count to the state so the frontend can read it right away.
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(
                f"Expected entity count: {filtered_preview.filtered_count}, "
                f"types: {filtered_preview.entity_types}"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch entity count synchronously (will retry in the background task): {e}")
            # Failure here does not block the rest of the flow; the background task will retry.

        # Create the asynchronous task.
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )

        # Update the simulation state, including the pre-fetched entity count.
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)

        # Define the background task.
        def run_prepare():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Starting simulation preparation..."
                )

                # Prepare the simulation with a progress callback.
                # Track detailed stage progress.
                stage_details = {}

                def progress_callback(stage, progress, message, **kwargs):
                    # Compute total progress.
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }

                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)

                    # Build detailed progress information.
                    stage_names = {
                        "reading": "Reading graph entities",
                        "generating_profiles": "Generating agent profiles",
                        "generating_config": "Generating simulation configuration",
                        "copying_scripts": "Preparing simulation scripts",
                    }

                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)

                    # Update the stage detail snapshot.
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }

                    # Build structured progress details.
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }

                    # Build a concise progress message.
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"

                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )

                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count,
                    probabilistic_mode=probabilistic_mode,
                    uncertainty_profile=uncertainty_profile,
                    outcome_metrics=data.get('outcome_metrics'),
                    forecast_brief=normalized_forecast_brief,
                )

                result_payload = result_state.to_simple_dict()
                result_payload["probabilistic_mode"] = probabilistic_mode
                result_payload["uncertainty_profile"] = (
                    uncertainty_profile if probabilistic_mode else None
                )
                result_payload["outcome_metrics"] = (
                    outcome_metric_ids if probabilistic_mode else []
                )
                result_payload["prepared_artifact_summary"] = _build_requested_prepare_artifact_summary(
                    simulation_id=simulation_id,
                    probabilistic_mode=probabilistic_mode,
                    uncertainty_profile=uncertainty_profile,
                    outcome_metric_ids=outcome_metric_ids,
                    forecast_brief=normalized_forecast_brief,
                    existing_summary=manager.get_prepare_artifact_summary(simulation_id),
                )

                # Mark the task as complete.
                task_manager.complete_task(
                    task_id,
                    result=result_payload
                )

            except Exception as e:
                logger.error(f"Simulation preparation failed: {str(e)}")
                task_manager.fail_task(task_id, str(e))

                # Update the simulation state to failed.
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)

        # Start the background thread.
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()

        prepared_artifact_summary = _build_requested_prepare_artifact_summary(
            simulation_id=simulation_id,
            probabilistic_mode=probabilistic_mode,
            uncertainty_profile=uncertainty_profile,
            outcome_metric_ids=outcome_metric_ids,
            forecast_brief=normalized_forecast_brief,
            existing_summary=manager.get_prepare_artifact_summary(simulation_id),
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "Preparation task started. Query progress through /api/simulation/prepare/status.",
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # Expected total agent count.
                "entity_types": state.entity_types,  # Entity type list.
                "probabilistic_mode": probabilistic_mode,
                "uncertainty_profile": uncertainty_profile if probabilistic_mode else None,
                "outcome_metrics": outcome_metric_ids if probabilistic_mode else [],
                "prepared_artifact_summary": prepared_artifact_summary,
            }
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to start preparation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Query simulation preparation progress.

    Supports two lookup modes:
    1. Query an in-progress task via `task_id`
    2. Check whether a simulation already has completed preparation via `simulation_id`

    Request body (JSON):
        {
            "task_id": "task_xxxx",          // optional: task_id returned by /prepare
            "simulation_id": "sim_xxxx"      // optional: simulation ID to check for completed preparation
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // whether completed preparation already exists
                "prepare_info": {...}            // detailed info when preparation is already complete
            }
        }
    """
    from ..models.task import TaskManager

    try:
        data = request.get_json() or {}

        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        probabilistic_mode = bool(data.get('probabilistic_mode', False))

        # If simulation_id is provided, check completed preparation first.
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(
                simulation_id,
                require_probabilistic_artifacts=probabilistic_mode,
            )
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": "Completed preparation already exists",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })

        # If no task_id was provided, return an error or a not-started response.
        if not task_id:
            if simulation_id:
                # A simulation_id was provided, but preparation is not complete yet.
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": "Preparation has not started yet. Call /api/simulation/prepare to begin.",
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)

        if not task:
            # The task does not exist. If simulation_id is provided, check completed preparation again.
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(
                    simulation_id,
                    require_probabilistic_artifacts=probabilistic_mode,
                )
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": "Task is complete (existing preparation was found)",
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })

            return jsonify({
                "success": False,
                "error": f"Task does not exist: {task_id}"
            }), 404

        task_dict = task.to_dict()
        task_dict["already_prepared"] = False

        return jsonify({
            "success": True,
            "data": task_dict
        })

    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get simulation status."""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        result = state.to_dict()

        # If the simulation is ready, attach run instructions.
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles', methods=['POST'])
def create_simulation_ensemble(simulation_id: str):
    """Create one storage-only ensemble under a prepared probabilistic simulation."""
    try:
        state, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()

        is_prepared, prepare_info = _check_simulation_prepared(
            simulation_id,
            require_probabilistic_artifacts=True,
        )
        if not is_prepared:
            reason = prepare_info.get("reason", "Probabilistic preparation is incomplete")
            if "probabilistic sidecars are missing" in reason.lower():
                reason = (
                    "Missing probabilistic prepare artifacts: "
                    "legacy prepare artifacts exist but probabilistic sidecars are missing"
                )
            return jsonify({
                "success": False,
                "error": reason,
                "prepare_info": prepare_info,
            }), 400

        ensemble_spec = _build_ensemble_spec_from_request(request.get_json() or {})
        created = EnsembleManager().create_ensemble(
            simulation_id=state.simulation_id,
            ensemble_spec=ensemble_spec,
        )

        return jsonify({
            "success": True,
            "data": _build_ensemble_response_payload(created),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to create simulation ensemble: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles', methods=['GET'])
def list_simulation_ensembles(simulation_id: str):
    """List stored ensembles for one simulation with state-level summaries."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        states = EnsembleManager().list_ensembles(simulation_id)

        return jsonify({
            "success": True,
            "data": states,
            "count": len(states),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to list simulation ensembles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>', methods=['GET'])
def get_simulation_ensemble(simulation_id: str, ensemble_id: str):
    """Load one ensemble plus lightweight run summaries."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        ensemble_payload = EnsembleManager().load_ensemble(simulation_id, ensemble_id)

        return jsonify({
            "success": True,
            "data": _build_ensemble_response_payload(ensemble_payload),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to load simulation ensemble: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/runs', methods=['GET'])
def list_simulation_ensemble_runs(simulation_id: str, ensemble_id: str):
    """List one ensemble's runs without embedding full resolved configs."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        limit = request.args.get('limit', default=100, type=int) or 100
        limit = max(1, min(limit, 200))
        runs = EnsembleManager().list_runs(simulation_id, ensemble_id)
        run_summaries = [_build_run_summary(run_payload) for run_payload in runs]

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "limit": limit,
                "total_runs": len(run_summaries),
                "truncated": len(run_summaries) > limit,
                "runs": run_summaries[:limit],
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to list simulation ensemble runs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>', methods=['GET'])
def get_simulation_ensemble_run(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Load one run's manifest and resolved config from storage."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        run_payload = EnsembleManager().load_run(simulation_id, ensemble_id, run_id)
        result = dict(run_payload)
        result["runtime_status"] = _build_ensemble_run_runtime_payload(
            simulation_id,
            ensemble_id,
            run_payload,
        )

        return jsonify({
            "success": True,
            "data": result,
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to load simulation ensemble run: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/rerun',
    methods=['POST'],
)
def rerun_simulation_ensemble_run(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Create one fresh prepared child run from a stored ensemble member."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, run_error = _get_ensemble_run_or_error(simulation_id, ensemble_id, run_id)
        if run_error:
            return run_error

        created_run = EnsembleManager().clone_run_for_rerun(
            simulation_id,
            ensemble_id,
            run_id,
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "source_run_id": run_id,
                "run": _build_run_summary(created_run),
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to rerun ensemble member: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/cleanup', methods=['POST'])
def cleanup_simulation_ensemble_runs(simulation_id: str, ensemble_id: str):
    """Reset one explicit subset of stored runs back to the prepared state."""
    try:
        data = request.get_json(silent=True) or {}
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        ensemble_payload, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        requested_run_ids = _normalize_requested_run_ids(data)
        requested_runs = _resolve_requested_ensemble_runs(
            ensemble_payload,
            requested_run_ids,
        )
        active_run_ids = _collect_active_requested_ensemble_run_ids(
            simulation_id,
            ensemble_id,
            requested_runs,
        )
        if active_run_ids:
            return jsonify({
                "success": False,
                "error": (
                    "One or more requested runs are still active. "
                    "Stop them before cleanup."
                ),
                "active_run_ids": active_run_ids,
            }), 409

        cleanup_results = []
        cleaned_run_ids = []
        for run_payload in requested_runs:
            runtime_graph_result = RuntimeGraphManager().cleanup_runtime_graph(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_payload["run_id"],
            )
            run_result = _cleanup_ensemble_run_storage_fallback(run_payload)
            cleanup_results.append({
                "run_id": run_payload["run_id"],
                **runtime_graph_result,
                **run_result,
            })
            cleaned_run_ids.append(run_payload["run_id"])

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cleaned_run_ids": cleaned_run_ids,
                "cleaned_run_count": len(cleaned_run_ids),
                "results": cleanup_results,
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to cleanup ensemble runs: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/actions',
    methods=['GET'],
)
def get_simulation_ensemble_run_actions(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Return run-scoped action history for one stored ensemble member."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, run_error = _get_ensemble_run_or_error(simulation_id, ensemble_id, run_id)
        if run_error:
            return run_error

        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)

        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num,
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "count": len(actions),
                "actions": [action.to_dict() for action in actions],
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get ensemble run actions: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/timeline',
    methods=['GET'],
)
def get_simulation_ensemble_run_timeline(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Return one run-scoped round timeline for the ensemble namespace."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, run_error = _get_ensemble_run_or_error(simulation_id, ensemble_id, run_id)
        if run_error:
            return run_error

        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)

        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            start_round=start_round,
            end_round=end_round,
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "count": len(timeline),
                "timeline": timeline,
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get ensemble run timeline: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/start',
    methods=['POST'],
)
def start_simulation_ensemble_run(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Launch one stored ensemble member run without mutating the parent simulation state."""
    try:
        data = request.get_json() or {}
        state, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        ensemble_payload, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error
        _, run_error = _get_ensemble_run_or_error(simulation_id, ensemble_id, run_id)
        if run_error:
            return run_error

        (
            platform,
            max_rounds,
            enable_graph_memory_update,
            force,
            close_environment_on_complete,
        ) = (
            _normalize_runtime_start_request(data)
        )
        capacity_error = _build_ensemble_run_capacity_error(
            simulation_id,
            ensemble_payload,
            run_id,
            force=force,
        )
        if capacity_error:
            return jsonify({
                "success": False,
                **capacity_error,
            }), 400

        response_data = _start_ensemble_run_runtime(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            force=force,
            close_environment_on_complete=close_environment_on_complete,
            state=state,
        )

        return jsonify({
            "success": True,
            "data": response_data,
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to start ensemble run: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/start', methods=['POST'])
def start_simulation_ensemble(simulation_id: str, ensemble_id: str):
    """Launch one explicit batch of stored runs for one ensemble."""
    try:
        data = request.get_json() or {}
        state, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        ensemble_payload, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        (
            platform,
            max_rounds,
            enable_graph_memory_update,
            force,
            close_environment_on_complete,
        ) = (
            _normalize_runtime_start_request(data)
        )
        requested_run_ids = _normalize_requested_run_ids(data)
        requested_runs = _resolve_requested_ensemble_runs(
            ensemble_payload,
            requested_run_ids,
        )
        max_concurrency = int(
            ensemble_payload.get("spec", {}).get("max_concurrency", 1) or 1
        )
        batch_start_plan = _plan_ensemble_batch_start(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            ensemble_payload=ensemble_payload,
            requested_runs=requested_runs,
            max_concurrency=max_concurrency,
            force=force,
        )

        started_runs = []
        for run_payload in (
            batch_start_plan["restart_runs"] + batch_start_plan["start_runs"]
        ):
            started_runs.append(
                _start_ensemble_run_runtime(
                    simulation_id=simulation_id,
                    ensemble_id=ensemble_id,
                    run_id=run_payload["run_id"],
                    platform=platform,
                    max_rounds=max_rounds,
                    enable_graph_memory_update=enable_graph_memory_update,
                    force=force,
                    close_environment_on_complete=close_environment_on_complete,
                    state=state,
                )
            )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "platform": platform,
                "requested_run_ids": [
                    run_payload["run_id"]
                    for run_payload in batch_start_plan["requested_runs"]
                ],
                "requested_run_count": len(batch_start_plan["requested_runs"]),
                "started_run_count": len(started_runs),
                "started_run_ids": [
                    run_payload["run_id"]
                    for run_payload in (
                        batch_start_plan["restart_runs"]
                        + batch_start_plan["start_runs"]
                    )
                ],
                "deferred_run_count": len(batch_start_plan["deferred_runs"]),
                "deferred_run_ids": [
                    run_payload["run_id"]
                    for run_payload in batch_start_plan["deferred_runs"]
                ],
                "active_run_count": len(batch_start_plan["active_run_ids"]),
                "active_run_ids": batch_start_plan["active_run_ids"],
                "active_requested_run_ids": batch_start_plan["active_requested_run_ids"],
                "active_other_run_ids": batch_start_plan["active_other_run_ids"],
                "available_start_slots": batch_start_plan["available_start_slots"],
                "max_concurrency": max_concurrency,
                "graph_memory_update_enabled": enable_graph_memory_update,
                "runs": started_runs,
            },
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to start simulation ensemble: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/stop',
    methods=['POST'],
)
def stop_simulation_ensemble_run(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Stop one ensemble member run via run-scoped runner identity."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, run_error = _get_ensemble_run_or_error(simulation_id, ensemble_id, run_id)
        if run_error:
            return run_error

        run_state = SimulationRunner.stop_simulation(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )

        return jsonify({
            "success": True,
            "data": run_state.to_dict(),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to stop ensemble run: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route(
    '/<simulation_id>/ensembles/<ensemble_id>/runs/<run_id>/run-status',
    methods=['GET'],
)
def get_simulation_ensemble_run_status(
    simulation_id: str,
    ensemble_id: str,
    run_id: str,
):
    """Return run-scoped runtime status for one stored ensemble member."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        run_payload, run_error = _get_ensemble_run_or_error(
            simulation_id,
            ensemble_id,
            run_id,
        )
        if run_error:
            return run_error

        run_state = _get_runner_run_state(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        if not run_state:
            base_graph_id, runtime_graph_id = _resolve_run_graph_ids(run_payload)
            return jsonify({
                "success": True,
                "data": _build_idle_ensemble_run_status_payload(
                    simulation_id,
                    ensemble_id,
                    run_id,
                    storage_status=run_payload["run_manifest"].get("status", "prepared"),
                    base_graph_id=base_graph_id,
                    runtime_graph_id=runtime_graph_id,
                ),
            })

        response_payload = run_state.to_dict()
        base_graph_id, runtime_graph_id = _resolve_run_graph_ids(run_payload)
        response_payload["graph_id"] = base_graph_id
        response_payload["base_graph_id"] = base_graph_id
        response_payload["runtime_graph_id"] = runtime_graph_id

        return jsonify({
            "success": True,
            "data": response_payload,
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get ensemble run status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/status', methods=['GET'])
def get_simulation_ensemble_status(
    simulation_id: str,
    ensemble_id: str,
):
    """Return one runtime-backed ensemble summary that is safe to poll."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        ensemble_payload, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        limit = request.args.get('limit', default=100, type=int) or 100
        limit = max(1, min(limit, 200))
        requested_run_ids = _normalize_requested_run_ids(
            {"run_ids": request.args.getlist("run_id") or None}
        )
        requested_runs = _resolve_requested_ensemble_runs(
            ensemble_payload,
            requested_run_ids,
        )

        return jsonify({
            "success": True,
            "data": _build_ensemble_runtime_status_payload(
                simulation_id,
                ensemble_payload,
                requested_runs,
                limit=limit,
            ),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get simulation ensemble status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/summary', methods=['GET'])
def get_simulation_ensemble_summary(
    simulation_id: str,
    ensemble_id: str,
):
    """Return one persisted-on-demand aggregate summary for the ensemble."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        return jsonify({
            "success": True,
            "data": EnsembleManager().get_aggregate_summary(simulation_id, ensemble_id),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get simulation ensemble summary: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/clusters', methods=['GET'])
def get_simulation_ensemble_clusters(
    simulation_id: str,
    ensemble_id: str,
):
    """Return one persisted-on-demand scenario clustering artifact for the ensemble."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        return jsonify({
            "success": True,
            "data": ScenarioClusterer().get_scenario_clusters(simulation_id, ensemble_id),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get simulation ensemble clusters: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/<simulation_id>/ensembles/<ensemble_id>/sensitivity', methods=['GET'])
def get_simulation_ensemble_sensitivity(
    simulation_id: str,
    ensemble_id: str,
):
    """Return one persisted-on-demand sensitivity artifact for the ensemble."""
    try:
        _, error_response = _get_simulation_or_404(simulation_id)
        if error_response:
            return error_response

        _require_probabilistic_ensemble_storage_enabled()
        _, ensemble_error = _get_ensemble_or_error(simulation_id, ensemble_id)
        if ensemble_error:
            return ensemble_error

        return jsonify({
            "success": True,
            "data": SensitivityAnalyzer().get_sensitivity_analysis(
                simulation_id,
                ensemble_id,
            ),
        })

    except ValueError as e:
        status_code = _ensemble_value_error_status_code(str(e))
        return jsonify({
            "success": False,
            "error": str(e),
        }), status_code

    except Exception as e:
        logger.error(f"Failed to get simulation ensemble sensitivity: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    List all simulations.

    Query parameters:
        project_id: Optional project ID filter.
    """
    try:
        project_id = request.args.get('project_id')

        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)

        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })

    except Exception as e:
        logger.error(f"Failed to list simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_latest_report_summary_for_simulation(simulation_id: str) -> Optional[dict]:
    """Return the latest saved report metadata used for Step 4/Step 5 replay."""
    try:
        reports = ReportManager.list_reports(simulation_id=simulation_id, limit=1)
    except Exception as e:
        logger.warning(f"Failed to locate report for simulation {simulation_id}: {e}")
        return None

    if not reports:
        return None

    latest_report = reports[0]
    return {
        "report_id": latest_report.report_id,
        "created_at": latest_report.created_at,
        "ensemble_id": latest_report.ensemble_id,
        "run_id": latest_report.run_id,
        "has_probabilistic_context": bool(latest_report.probabilistic_context),
    }


def _build_probabilistic_runtime_history_summary(
    simulation_id: str,
    *,
    ensemble_id: Optional[str],
    run_id: Optional[str],
    source: str,
    report_id: Optional[str] = None,
    has_probabilistic_context: bool = False,
) -> Optional[dict]:
    """Build one bounded Step 3 replay pointer for history consumers."""
    if not ensemble_id or not run_id:
        return None

    summary = {
        "source": source,
        "report_id": report_id,
        "ensemble_id": ensemble_id,
        "run_id": run_id,
        "has_probabilistic_context": has_probabilistic_context,
        "run_status": None,
        "run_updated_at": None,
    }

    try:
        run_payload = EnsembleManager().load_run(simulation_id, ensemble_id, run_id)
    except Exception as e:
        logger.warning(
            "Failed to load probabilistic history replay target for %s/%s/%s: %s",
            simulation_id,
            ensemble_id,
            run_id,
            e,
        )
        return summary

    run_manifest = run_payload.get("run_manifest") or {}
    summary["run_status"] = run_manifest.get("status")
    summary["run_updated_at"] = run_manifest.get("updated_at")
    return summary


def _get_latest_probabilistic_report_runtime_summary_for_simulation(
    simulation_id: str,
) -> Optional[dict]:
    """Return the newest saved report that still carries probabilistic Step 3 scope."""
    try:
        reports = ReportManager.list_reports(simulation_id=simulation_id, limit=200)
    except Exception as e:
        logger.warning(
            "Failed to inspect probabilistic report history for simulation %s: %s",
            simulation_id,
            e,
        )
        return None

    for report in reports:
        if report.ensemble_id and report.run_id:
            return _build_probabilistic_runtime_history_summary(
                simulation_id,
                ensemble_id=report.ensemble_id,
                run_id=report.run_id,
                source="report",
                report_id=report.report_id,
                has_probabilistic_context=bool(report.probabilistic_context),
            )

    return None


def _get_latest_probabilistic_storage_runtime_summary_for_simulation(
    simulation_id: str,
) -> Optional[dict]:
    """Return the newest stored probabilistic run when no saved report points to one."""
    try:
        ensembles = EnsembleManager().list_ensembles(simulation_id)
    except Exception as e:
        logger.warning(
            "Failed to inspect probabilistic storage history for simulation %s: %s",
            simulation_id,
            e,
        )
        return None

    if not ensembles:
        return None

    def _ensemble_sort_key(state: dict) -> tuple[str, str]:
        ensemble_id = str(state.get("ensemble_id") or "")
        created_at = str(state.get("created_at") or "")
        return created_at, ensemble_id

    def _run_sort_key(run_payload: dict) -> tuple[str, str]:
        manifest = run_payload.get("run_manifest") or {}
        updated_at = str(manifest.get("updated_at") or manifest.get("generated_at") or "")
        run_id = str(run_payload.get("run_id") or "")
        return updated_at, run_id

    sorted_ensembles = sorted(ensembles, key=_ensemble_sort_key, reverse=True)
    for ensemble_state in sorted_ensembles:
        ensemble_id = ensemble_state.get("ensemble_id")
        if not ensemble_id:
            continue

        try:
            runs = EnsembleManager().list_runs(simulation_id, ensemble_id)
        except Exception as e:
            logger.warning(
                "Failed to inspect runs for probabilistic history replay %s/%s: %s",
                simulation_id,
                ensemble_id,
                e,
            )
            continue

        if not runs:
            continue

        latest_run = max(runs, key=_run_sort_key)
        run_id = latest_run.get("run_id")
        if not run_id:
            continue

        return _build_probabilistic_runtime_history_summary(
            simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            source="storage",
            report_id=None,
            has_probabilistic_context=False,
        )

    return None


def _get_latest_probabilistic_runtime_summary_for_simulation(
    simulation_id: str,
) -> Optional[dict]:
    """Resolve one deterministic Step 3 history replay target for one simulation."""
    return (
        _get_latest_probabilistic_report_runtime_summary_for_simulation(simulation_id)
        or _get_latest_probabilistic_storage_runtime_summary_for_simulation(simulation_id)
    )


def _get_report_id_for_simulation(simulation_id: str) -> Optional[str]:
    """Return the latest saved report id associated with one simulation."""
    latest_report = _get_latest_report_summary_for_simulation(simulation_id)
    if not latest_report:
        return None
    return latest_report.get("report_id")


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Get historical simulations with project details.

    Used by the home page to display historical projects, including rich
    metadata such as project name and description.

    Query parameters:
        limit: Maximum number of results to return. Defaults to 20.

    Returns:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "Wuhan University Public Opinion Analysis",
                    "simulation_requirement": "If Wuhan University publishes...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)

        manager = SimulationManager()
        simulations = sorted(
            manager.list_simulations(),
            key=lambda simulation: simulation.created_at or "",
            reverse=True,
        )[:limit]

        # Enrich the simulation data using only Simulation files.
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()

            # Load simulation configuration (including simulation_requirement) from simulation_config.json.
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Recommended round count (fallback value).
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 /
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0

            # Load run state (including any user-configured actual round count) from run_state.json.
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Use user-configured total_rounds when available; otherwise use the recommended count.
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds

            # Load the associated project's file list, capped at 3 entries.
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "Unknown file")}
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []

            # Load the associated report replay metadata using the latest saved report.
            latest_report = _get_latest_report_summary_for_simulation(sim.simulation_id)
            sim_dict["report_id"] = latest_report.get("report_id") if latest_report else None
            sim_dict["latest_report"] = latest_report
            sim_dict["latest_probabilistic_runtime"] = (
                _get_latest_probabilistic_runtime_summary_for_simulation(sim.simulation_id)
            )

            # Add the version number.
            sim_dict["version"] = "v1.0.2"

            # Format the date.
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""

            enriched_simulations.append(sim_dict)

        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })

    except Exception as e:
        logger.error(f"Failed to get simulation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    Get agent profiles for a simulation.

    Query parameters:
        platform: Platform type (`reddit` or `twitter`), default `reddit`.
    """
    try:
        platform = request.args.get('platform', 'reddit')

        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)

        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404

    except Exception as e:
        logger.error(f"Failed to get profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    Get simulation agent profiles in real time while generation is still in progress.

    Differences from `/profiles`:
    - Reads files directly instead of going through `SimulationManager`
    - Intended for live progress visibility during generation
    - Returns extra metadata such as file modification time and generation state

    Query parameters:
        platform: Platform type (`reddit` or `twitter`), default `reddit`.

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // expected total if available
                "is_generating": true, // whether generation is still in progress
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime

    try:
        platform = request.args.get('platform', 'reddit')

        # Get the simulation directory.
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        # Resolve the profile file path.
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")

        # Check whether the file exists.
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None

        if file_exists:
            # Read the file modification time.
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read profiles file (it may still be being written): {e}")
                profiles = []

        # Determine whether generation is still in progress from state.json.
        is_generating = False
        total_expected = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })

    except Exception as e:
        logger.error(f"Failed to get realtime profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    Get simulation configuration in real time while it is still being generated.

    Differences from `/config`:
    - Reads files directly instead of going through `SimulationManager`
    - Intended for live progress visibility during generation
    - Returns extra metadata such as file modification time and generation state
    - Can return partial information even before generation fully completes

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // whether generation is still in progress
                "generation_stage": "generating_config",  // current generation stage
                "config": {...}  // config content, if available
            }
        }
    """
    import json
    from datetime import datetime

    try:
        # Get the simulation directory.
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        # Resolve the config file path.
        config_file = os.path.join(sim_dir, "simulation_config.json")

        # Check whether the config file exists.
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None

        if file_exists:
            # Read the file modification time.
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read config file (it may still be being written): {e}")
                config = None

        # Determine whether generation is still in progress from state.json.
        is_generating = False
        generation_stage = None
        config_generated = False

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    config_generated = state_data.get("config_generated", False)

                    # Resolve the current generation stage.
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass

        # Build the response payload.
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "config": config
        }

        # If a config exists, derive a few key summary fields.
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }

        return jsonify({
            "success": True,
            "data": response_data
        })

    except Exception as e:
        logger.error(f"Failed to get realtime config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Get the complete simulation configuration generated by the LLM.

    The response includes:
        - `time_config`: time settings such as duration, rounds, and peak/off-peak periods
        - `agent_configs`: per-agent activity settings such as activity level, posting frequency, and stance
        - `event_config`: event settings such as initial posts and hot topics
        - `platform_configs`: platform-specific configuration
        - `generation_reasoning`: the LLM's reasoning for the generated configuration
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)

        if not config:
            return jsonify({
                "success": False,
                "error": "Simulation config does not exist yet. Please call /prepare first."
            }), 404

        return jsonify({
            "success": True,
            "data": config
        })

    except Exception as e:
        logger.error(f"Failed to get config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Download the simulation configuration file."""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": "Config file does not exist yet. Please call /prepare first."
            }), 404

        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )

    except Exception as e:
        logger.error(f"Failed to download config: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Download a simulation runtime script from `backend/scripts/`.

    Supported `script_name` values:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # Scripts are stored in backend/scripts/.
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))

        # Validate the requested script name.
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py",
            "run_parallel_simulation.py",
            "action_logger.py"
        ]

        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": f"Unknown script: {script_name}. Allowed values: {allowed_scripts}"
            }), 400

        script_path = os.path.join(scripts_dir, script_name)

        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": f"Script file does not exist: {script_name}"
            }), 404

        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )

    except Exception as e:
        logger.error(f"Failed to download script: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profile Generation Endpoint (Standalone Use) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    Generate OASIS agent profiles directly from a graph without creating a simulation.

    Request body (JSON):
        {
            "graph_id": "mirofish_xxxx",  // required
            "entity_types": ["Student"],  // optional
            "use_llm": true,              // optional
            "platform": "reddit"          // optional
        }
    """
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id"
            }), 400

        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')

        reader = ZepEntityReader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )

        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": "No entities matching the criteria were found"
            }), 400

        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )

        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]

        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })

    except Exception as e:
        logger.error(f"Failed to generate profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Runtime Control Endpoints ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    Start running a simulation.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",         // required: simulation ID
            "platform": "parallel",              // optional: twitter / reddit / parallel (default)
            "max_rounds": 100,                   // optional: maximum simulation rounds for truncating long runs
            "enable_graph_memory_update": false, // optional: whether to write agent activity back into Zep graph memory
            "force": false,                      // optional: force a restart by stopping a running simulation and cleaning logs
            "close_environment_on_complete": false // optional: exit after completion instead of entering command-wait mode
        }

    About `force`:
        - If enabled and the simulation is already running or completed, the run is stopped first
          and runtime logs are cleaned up
        - Cleanup includes files such as `run_state.json`, `actions.jsonl`, and `simulation.log`
        - Configuration files (`simulation_config.json`) and profile files are preserved
        - This is useful when the simulation must be rerun from the same prepared state

    About `enable_graph_memory_update`:
        - If enabled, all agent activity in the simulation (posts, comments, likes, and so on)
          is written back to the Zep graph in real time
        - This allows the graph to retain memory of the simulation for later analysis or AI chat
        - The simulation's project must have a valid `graph_id`
        - Updates are batched to reduce API call volume

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // whether graph memory updates are enabled
                "force_restarted": true               // whether the run was force-restarted
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # Optional maximum number of simulation rounds.
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # Optional graph memory updates.
        force = data.get('force', False)  # Optional forced restart.
        close_environment_on_complete = data.get('close_environment_on_complete', False)

        # Validate the max_rounds parameter.
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": "max_rounds must be a positive integer"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "max_rounds must be a valid integer"
                }), 400

        if platform not in ['twitter', 'reddit', 'parallel']:
            return jsonify({
                "success": False,
                "error": f"Invalid platform type: {platform}. Allowed values: twitter/reddit/parallel"
            }), 400

        # Check whether the simulation is ready.
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        force_restarted = False

        # Handle state intelligently: if preparation is already complete, allow a restart.
        if state.status != SimulationStatus.READY:
            # Check whether preparation has actually completed.
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # Preparation is complete; check for a currently running process.
                if state.status == SimulationStatus.RUNNING:
                    # Verify that the simulation process is truly still running.
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # The process is indeed still running.
                        if force:
                            # In force mode, stop the running simulation first.
                            logger.info(f"Force mode: stopping running simulation {simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"Warning while stopping simulation: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": (
                                    "The simulation is currently running. Call /stop first, "
                                    "or use force=true to restart it."
                                )
                            }), 400

                # If force mode is enabled, clean up runtime logs.
                if force:
                    logger.info(f"Force mode: cleaning simulation logs for {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"Warnings occurred during log cleanup: {cleanup_result.get('errors')}")
                    force_restarted = True

                # The process does not exist anymore or has already ended. Reset the state to ready.
                logger.info(
                    f"Simulation {simulation_id} preparation is complete; resetting state to ready "
                    f"(previous state: {state.status.value})"
                )
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # Preparation is still incomplete.
                return jsonify({
                    "success": False,
                    "error": (
                        f"Simulation is not ready. Current state: {state.status.value}. "
                        "Please call /prepare first."
                    )
                }), 400

        # Load the graph ID for graph-memory updates.
        base_graph_id = _resolve_base_graph_id_for_simulation(state)
        runtime_graph_id = None
        if enable_graph_memory_update:
            if not base_graph_id:
                return jsonify({
                    "success": False,
                    "error": "A valid graph_id is required to enable graph memory updates. Please make sure the project graph has been built."
                }), 400

            runtime_graph_id = base_graph_id
            logger.info(
                "Enabling graph memory updates: simulation_id=%s base_graph_id=%s runtime_graph_id=%s",
                simulation_id,
                base_graph_id,
                runtime_graph_id,
            )

        # Start the simulation.
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            close_environment_on_complete=close_environment_on_complete,
            graph_id=runtime_graph_id or base_graph_id,
            base_graph_id=base_graph_id,
            runtime_graph_id=runtime_graph_id,
        )

        # Update the simulation state.
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)

        response_data = run_state.to_dict()
        response_data['graph_id'] = base_graph_id
        response_data['base_graph_id'] = base_graph_id
        response_data['runtime_graph_id'] = runtime_graph_id
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        response_data['close_environment_on_complete'] = close_environment_on_complete

        return jsonify({
            "success": True,
            "data": response_data
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    Stop a simulation.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx"  // required: simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        run_state = SimulationRunner.stop_simulation(simulation_id)

        # Update the simulation state.
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)

        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to stop simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Realtime Status Monitoring Endpoints ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    Get realtime simulation run status for frontend polling.

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)

        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })

        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to get run status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    Get detailed simulation run status, including all actions.

    Used by the frontend for realtime activity display.

    Query parameters:
        platform: Optional platform filter (`twitter` or `reddit`).

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # All Twitter actions
                "reddit_actions": [...]    # All Reddit actions
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')

        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })

        # Load the full action list.
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )

        # Load actions per platform.
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []

        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []

        # Load actions for the current round only. recent_actions shows just the latest round.
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []

        # Start from the base state payload.
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions only includes the latest round across both platforms.
        result["recent_actions"] = [a.to_dict() for a in recent_actions]

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Failed to get detailed run status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    Get agent action history for a simulation.

    Query parameters:
        limit: Number of results to return. Defaults to 100.
        offset: Offset. Defaults to 0.
        platform: Platform filter (`twitter` or `reddit`).
        agent_id: Agent ID filter.
        round_num: Round filter.

    Returns:
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)

        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })

    except Exception as e:
        logger.error(f"Failed to get action history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    Get the simulation timeline summarized by round.

    Used by the frontend to render progress bars and timeline views.

    Query parameters:
        start_round: Starting round. Defaults to 0.
        end_round: Ending round. Defaults to all available rounds.

    Returns aggregated information for each round.
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)

        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )

        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })

    except Exception as e:
        logger.error(f"Failed to get timeline: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    Get per-agent statistics.

    Used by the frontend to display agent activity rankings, action distributions, and similar summaries.
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)

        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })

    except Exception as e:
        logger.error(f"Failed to get agent statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Database Query Endpoints ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    Get posts from a simulation.

    Query parameters:
        platform: Platform type (`twitter` or `reddit`)
        limit: Number of results to return. Defaults to 50.
        offset: Offset.

    Returns a post list loaded from the SQLite database.
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)

        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": "Database does not exist yet. The simulation may not have run yet."
                }
            })

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM post
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            posts = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]

        except sqlite3.OperationalError:
            posts = []
            total = 0

        conn.close()

        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })

    except Exception as e:
        logger.error(f"Failed to get posts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_simulation_comments(simulation_id: str):
    """
    Get simulation comments (Reddit only).

    Query parameters:
        post_id: Optional post ID filter.
        limit: Number of results to return.
        offset: Offset.
    """
    try:
        post_id = request.args.get('post_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        db_path = os.path.join(sim_dir, "reddit_simulation.db")

        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "count": 0,
                    "comments": []
                }
            })

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if post_id:
                cursor.execute("""
                    SELECT * FROM comment
                    WHERE post_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (post_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM comment
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            comments = [dict(row) for row in cursor.fetchall()]

        except sqlite3.OperationalError:
            comments = []

        conn.close()

        return jsonify({
            "success": True,
            "data": {
                "count": len(comments),
                "comments": comments
            }
        })

    except Exception as e:
        logger.error(f"Failed to get comments: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview Endpoints ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview a single agent.

    Note: the simulation environment must be running for this feature
    (specifically, it must have finished the simulation loop and entered
    the wait-for-commands mode).

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",       // required: simulation ID
            "agent_id": 0,                     // required: agent ID
            "prompt": "What is your view on this?",  // required: interview question
            "platform": "twitter",             // optional: target platform (twitter/reddit)
                                               // if omitted, both platforms are interviewed
            "timeout": 60                      // optional: timeout in seconds, default 60
        }

    Returns (dual-platform mode when platform is omitted):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What is your view on this?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Returns (single-platform mode):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What is your view on this?",
                "result": {
                    "agent_id": 0,
                    "response": "I think...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 60)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if agent_id is None:
            return jsonify({
                "success": False,
                "error": "Please provide agent_id"
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": "Please provide prompt (the interview question)"
            }), 400

        # Validate the platform parameter.
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform must be either 'twitter' or 'reddit'"
            }), 400

        # Check environment state.
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "The simulation environment is not running or has already been closed. Make sure the simulation has completed and entered wait-for-commands mode."
            }), 400

        # Optimize the prompt by adding a prefix that discourages tool calls.
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out while waiting for interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Interview multiple agents in a batch.

    Note: this feature requires the simulation environment to be running.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",       // required: simulation ID
            "interviews": [                    // required: interview list
                {
                    "agent_id": 0,
                    "prompt": "What is your view on A?",
                    "platform": "twitter"      // optional: platform for this specific agent
                },
                {
                    "agent_id": 1,
                    "prompt": "What is your view on B?"  // uses the default platform if omitted
                }
            ],
            "platform": "reddit",              // optional default platform, overridden per item
                                               // if omitted, each agent is interviewed on both platforms
            "timeout": 120                     // optional: timeout in seconds, default 120
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": "Please provide interviews (the interview list)"
            }), 400

        # Validate the platform parameter.
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform must be either 'twitter' or 'reddit'"
            }), 400

        # Validate each interview entry.
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview entry {i + 1} is missing agent_id"
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview entry {i + 1} is missing prompt"
                }), 400
            # Validate the per-entry platform when present.
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": f"platform in interview entry {i + 1} must be either 'twitter' or 'reddit'"
                }), 400

        # Check environment state.
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "The simulation environment is not running or has already been closed. Make sure the simulation has completed and entered wait-for-commands mode."
            }), 400

        # Optimize each interview prompt by adding the anti-tool-call prefix.
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out while waiting for batch interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Batch interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    Run a global interview using the same question for every agent.

    Note: this feature requires the simulation environment to be running.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",            // required: simulation ID
            "prompt": "What is your overall view of this?",  // required: shared interview question
            "platform": "reddit",                   // optional: target platform (twitter/reddit)
                                                    // if omitted, each agent is interviewed on both platforms
            "timeout": 180                          // optional: timeout in seconds, default 180
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": "Please provide prompt (the interview question)"
            }), 400

        # Validate the platform parameter.
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform must be either 'twitter' or 'reddit'"
            }), 400

        # Check environment state.
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "The simulation environment is not running or has already been closed. Make sure the simulation has completed and entered wait-for-commands mode."
            }), 400

        # Optimize the prompt by adding a prefix that discourages tool calls.
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out while waiting for global interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Global interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    Get interview history.

    Reads all interview records from the simulation database.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",  // required: simulation ID
            "platform": "reddit",         // optional: platform filter (reddit/twitter)
                                          // if omitted, history from both platforms is returned
            "agent_id": 0,                // optional: only return history for this agent
            "limit": 100                  // optional: maximum number of results, default 100
        }

    Returns:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "I think...",
                        "prompt": "What is your view on this?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # If omitted, history from both platforms is returned.
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    Get simulation environment status.

    Checks whether the simulation environment is alive and able to receive interview commands.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx"  // required: simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Environment is running and can accept interview commands"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)

        # Load more detailed status information.
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = "Environment is running and can accept interview commands"
        else:
            message = "Environment is not running or has already been closed"

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Failed to get environment status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    Close the simulation environment.

    Sends a close-environment command to the simulation so it exits wait-for-commands
    mode gracefully.

    Note: this differs from `/stop`, which forcefully terminates the process.
    This endpoint asks the simulation to shut down gracefully and exit on its own.

    Request body (JSON):
        {
            "simulation_id": "sim_xxxx",  // required: simulation ID
            "timeout": 30                 // optional: timeout in seconds, default 30
        }

    Returns:
        {
            "success": true,
            "data": {
                "message": "Environment close command sent",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )

        # Update simulation state.
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Failed to close environment: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
