"""
Storage-only ensemble manager for probabilistic simulation runs.

This layer reads the prepare-time probabilistic artifacts that already exist
under one simulation and materializes isolated ensemble/run directories for
future execution. It does not invoke the runtime runner.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from ..config import Config
from ..models.probabilistic import (
    EnsembleSpec,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    UncertaintySpec,
    build_default_run_lifecycle,
    build_default_run_lineage,
)
from .uncertainty_resolver import UncertaintyResolver


class EnsembleManager:
    """Persist deterministic ensemble/run storage derived from prepare artifacts."""

    SIMULATION_DATA_DIR = Config.OASIS_SIMULATION_DATA_DIR
    PREPARE_ARTIFACT_FILENAMES = {
        "base_config": "simulation_config.base.json",
        "uncertainty_spec": "uncertainty_spec.json",
        "outcome_spec": "outcome_spec.json",
    }
    ENSEMBLE_ROOT_DIRNAME = "ensemble"
    ENSEMBLE_DIR_PREFIX = "ensemble_"
    ENSEMBLE_SPEC_FILENAME = "ensemble_spec.json"
    ENSEMBLE_STATE_FILENAME = "ensemble_state.json"
    AGGREGATE_SUMMARY_FILENAME = "aggregate_summary.json"
    RUNS_DIRNAME = "runs"
    RUN_DIR_PREFIX = "run_"
    RUN_MANIFEST_FILENAME = "run_manifest.json"
    RESOLVED_CONFIG_FILENAME = "resolved_config.json"
    THIN_SAMPLE_WARNING_THRESHOLD = 5

    _ENSEMBLE_DIR_RE = re.compile(r"^ensemble_(\d{4})$")
    _RUN_DIR_RE = re.compile(r"^run_(\d{4})$")

    def __init__(
        self,
        simulation_data_dir: str | None = None,
        uncertainty_resolver: UncertaintyResolver | None = None,
    ) -> None:
        self.simulation_data_dir = (
            simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        )
        self.uncertainty_resolver = uncertainty_resolver or UncertaintyResolver()
        os.makedirs(self.simulation_data_dir, exist_ok=True)

    def create_ensemble(
        self,
        simulation_id: str,
        ensemble_spec: EnsembleSpec | Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create one ensemble directory and persist all resolved run artifacts."""
        if isinstance(ensemble_spec, dict):
            ensemble_spec = EnsembleSpec.from_dict(ensemble_spec)

        sim_dir = self._get_simulation_dir(simulation_id)
        prepare_inputs = self._load_prepare_inputs(simulation_id)
        ensemble_id = self._next_ensemble_id(simulation_id)
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        os.makedirs(ensemble_dir, exist_ok=False)

        effective_root_seed = (
            ensemble_spec.root_seed
            if ensemble_spec.root_seed is not None
            else prepare_inputs["uncertainty_spec"].root_seed
            if prepare_inputs["uncertainty_spec"].root_seed is not None
            else 0
        )
        effective_uncertainty_spec = self._build_effective_uncertainty_spec(
            prepare_inputs["uncertainty_spec"],
            effective_root_seed,
        )

        self._write_json(
            os.path.join(ensemble_dir, self.ENSEMBLE_SPEC_FILENAME),
            self._build_ensemble_spec_artifact(
                simulation_id=simulation_id,
                ensemble_spec=ensemble_spec,
                effective_root_seed=effective_root_seed,
            ),
        )

        run_ids: List[str] = []
        runs_dir = os.path.join(ensemble_dir, self.RUNS_DIRNAME)
        os.makedirs(runs_dir, exist_ok=True)

        for run_index in range(1, ensemble_spec.run_count + 1):
            run_id = f"{run_index:04d}"
            run_ids.append(run_id)
            run_dir = self._get_run_dir(simulation_id, ensemble_id, run_id)
            os.makedirs(run_dir, exist_ok=False)

            resolution_seed = self._derive_resolution_seed(
                root_seed=effective_root_seed,
                run_index=run_index,
                derive_run_seeds=effective_uncertainty_spec.seed_policy.derive_run_seeds,
                sampling_mode=ensemble_spec.sampling_mode,
            )
            resolved = self.uncertainty_resolver.resolve_run_config(
                simulation_id=simulation_id,
                run_id=run_id,
                base_config=prepare_inputs["base_config"],
                uncertainty_spec=effective_uncertainty_spec,
                resolution_seed=resolution_seed,
                ensemble_id=ensemble_id,
                fallback_to_root_seed=ensemble_spec.sampling_mode != "unseeded",
            )
            manifest_payload = resolved["run_manifest"].to_dict()
            manifest_payload["base_graph_id"] = (
                prepare_inputs["base_config"].get("base_graph_id")
                or prepare_inputs["base_config"].get("graph_id")
            )
            manifest_payload["runtime_graph_id"] = None
            manifest_payload["generated_at"] = datetime.now().isoformat()
            resolved_config_artifact = self._build_resolved_config_artifact(
                resolved_config=resolved["resolved_config"],
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                run_id=run_id,
                run_manifest=manifest_payload,
            )

            self._write_json(
                os.path.join(run_dir, self.RESOLVED_CONFIG_FILENAME),
                resolved_config_artifact,
            )
            self._write_json(
                os.path.join(run_dir, self.RUN_MANIFEST_FILENAME),
                manifest_payload,
            )

        ensemble_state = self._build_ensemble_state(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            ensemble_spec=ensemble_spec,
            effective_root_seed=effective_root_seed,
            outcome_spec=prepare_inputs["outcome_spec"],
            run_ids=run_ids,
            sim_dir=sim_dir,
        )
        self._write_json(
            os.path.join(ensemble_dir, self.ENSEMBLE_STATE_FILENAME),
            ensemble_state,
        )

        return self.load_ensemble(simulation_id, ensemble_id)

    def list_ensembles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Return persisted ensemble state entries for one simulation."""
        ensemble_root = self._get_ensemble_root_dir(simulation_id)
        if not os.path.isdir(ensemble_root):
            return []

        ensemble_ids = sorted(
            match.group(1)
            for entry in os.listdir(ensemble_root)
            if os.path.isdir(os.path.join(ensemble_root, entry))
            for match in [self._ENSEMBLE_DIR_RE.match(entry)]
            if match
        )
        return [self.load_ensemble(simulation_id, ensemble_id)["state"] for ensemble_id in ensemble_ids]

    def load_ensemble(self, simulation_id: str, ensemble_id: str) -> Dict[str, Any]:
        """Load one ensemble state/spec plus the currently persisted runs."""
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        spec_path = os.path.join(ensemble_dir, self.ENSEMBLE_SPEC_FILENAME)
        state_path = os.path.join(ensemble_dir, self.ENSEMBLE_STATE_FILENAME)
        if not os.path.exists(spec_path) or not os.path.exists(state_path):
            raise ValueError(
                f"Ensemble does not exist for simulation {simulation_id}: {ensemble_id}"
            )

        return {
            "simulation_id": simulation_id,
            "ensemble_id": normalized_ensemble_id,
            "path": ensemble_dir,
            "ensemble_dir": ensemble_dir,
            "spec": self._read_json(spec_path),
            "state": self._read_json(state_path),
            "runs": self.list_runs(simulation_id, normalized_ensemble_id),
        }

    def list_runs(self, simulation_id: str, ensemble_id: str) -> List[Dict[str, Any]]:
        """Return persisted run payloads for one ensemble."""
        runs_dir = os.path.join(self._get_ensemble_dir(simulation_id, ensemble_id), self.RUNS_DIRNAME)
        if not os.path.isdir(runs_dir):
            return []

        run_ids = sorted(
            match.group(1)
            for entry in os.listdir(runs_dir)
            if os.path.isdir(os.path.join(runs_dir, entry))
            for match in [self._RUN_DIR_RE.match(entry)]
            if match
        )
        return [self.load_run(simulation_id, ensemble_id, run_id) for run_id in run_ids]

    def load_run(
        self,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
    ) -> Dict[str, Any]:
        """Load one run directory and its persisted artifacts."""
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        normalized_run_id = self._normalize_run_id(run_id)
        run_dir = self._get_run_dir(simulation_id, ensemble_id, run_id)
        manifest_path = os.path.join(run_dir, self.RUN_MANIFEST_FILENAME)
        resolved_config_path = os.path.join(run_dir, self.RESOLVED_CONFIG_FILENAME)
        if not os.path.exists(manifest_path) or not os.path.exists(resolved_config_path):
            raise ValueError(
                f"Run does not exist for simulation {simulation_id}, ensemble {ensemble_id}: {run_id}"
            )

        return {
            "simulation_id": simulation_id,
            "ensemble_id": normalized_ensemble_id,
            "run_id": normalized_run_id,
            "path": run_dir,
            "run_dir": run_dir,
            "run_manifest": self._read_json(manifest_path),
            "resolved_config": self._read_json(resolved_config_path),
        }

    def delete_run(self, simulation_id: str, ensemble_id: str, run_id: str) -> bool:
        """Delete one run directory only and refresh the parent ensemble state."""
        run_dir = self._get_run_dir(simulation_id, ensemble_id, run_id)
        if not os.path.isdir(run_dir):
            return False

        shutil.rmtree(run_dir)
        self._refresh_ensemble_state(simulation_id, ensemble_id)
        return True

    def clone_run_for_rerun(
        self,
        simulation_id: str,
        ensemble_id: str,
        source_run_id: str,
    ) -> Dict[str, Any]:
        """Clone one stored run into a new prepared child run with fresh lineage."""
        source_payload = self.load_run(simulation_id, ensemble_id, source_run_id)
        source_manifest = deepcopy(source_payload["run_manifest"])
        new_run_id = self._next_run_id(simulation_id, ensemble_id)
        new_run_dir = self._get_run_dir(simulation_id, ensemble_id, new_run_id)
        os.makedirs(new_run_dir, exist_ok=False)

        manifest_payload = deepcopy(source_manifest)
        manifest_payload["run_id"] = new_run_id
        manifest_payload["status"] = "prepared"
        manifest_payload["runtime_graph_id"] = None
        manifest_payload["generated_at"] = datetime.now().isoformat()
        manifest_payload["updated_at"] = manifest_payload["generated_at"]
        manifest_payload["artifact_paths"] = {
            "resolved_config": self.RESOLVED_CONFIG_FILENAME,
        }
        manifest_payload["lifecycle"] = build_default_run_lifecycle()
        manifest_payload["lineage"] = build_default_run_lineage(
            ensemble_id,
            {
                "kind": "rerun",
                "source_run_id": source_payload["run_id"],
                "parent_run_id": source_payload["run_id"],
            },
            default_kind="rerun",
        )

        resolved_config_artifact = self._build_resolved_config_artifact(
            resolved_config=source_payload["resolved_config"],
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=new_run_id,
            run_manifest=manifest_payload,
        )

        self._write_json(
            os.path.join(new_run_dir, self.RESOLVED_CONFIG_FILENAME),
            resolved_config_artifact,
        )
        self._write_json(
            os.path.join(new_run_dir, self.RUN_MANIFEST_FILENAME),
            manifest_payload,
        )
        self._refresh_ensemble_state(simulation_id, ensemble_id)
        return self.load_run(simulation_id, ensemble_id, new_run_id)

    def get_aggregate_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Build and persist one ensemble-level aggregate summary from run metrics."""
        ensemble_payload = self.load_ensemble(simulation_id, ensemble_id)
        summary = self._build_aggregate_summary(ensemble_payload)
        self._write_json(
            os.path.join(
                ensemble_payload["ensemble_dir"],
                self.AGGREGATE_SUMMARY_FILENAME,
            ),
            summary,
        )
        return summary

    def _load_prepare_inputs(self, simulation_id: str) -> Dict[str, Any]:
        """Load the required probabilistic prepare artifacts or fail clearly."""
        sim_dir = self._get_simulation_dir(simulation_id)
        missing = []
        artifact_paths = {}

        for artifact_name, filename in self.PREPARE_ARTIFACT_FILENAMES.items():
            artifact_path = os.path.join(sim_dir, filename)
            artifact_paths[artifact_name] = artifact_path
            if not os.path.exists(artifact_path):
                missing.append(filename)

        if missing:
            raise ValueError(
                "Missing probabilistic prepare artifacts for "
                f"simulation {simulation_id}: {', '.join(missing)}"
            )

        return {
            "base_config": self._read_json(artifact_paths["base_config"]),
            "uncertainty_spec": UncertaintySpec.from_dict(
                self._read_json(artifact_paths["uncertainty_spec"])
            ),
            "outcome_spec": self._read_json(artifact_paths["outcome_spec"]),
        }

    def _build_effective_uncertainty_spec(
        self,
        uncertainty_spec: UncertaintySpec,
        root_seed: int,
    ) -> UncertaintySpec:
        """Clone the prepare contract so ensemble-level root seed overrides stay local."""
        effective_uncertainty_spec = UncertaintySpec.from_dict(uncertainty_spec.to_dict())
        effective_uncertainty_spec.root_seed = root_seed
        effective_uncertainty_spec.seed_policy.root_seed = root_seed
        return effective_uncertainty_spec

    def _build_ensemble_spec_artifact(
        self,
        simulation_id: str,
        ensemble_spec: EnsembleSpec,
        effective_root_seed: int,
    ) -> Dict[str, Any]:
        """Persist both requested and effective seed choices for auditability."""
        requested_root_seed = ensemble_spec.root_seed
        persisted_spec = ensemble_spec.to_dict()
        persisted_spec.update(
            {
                "artifact_type": "ensemble_spec",
                "created_at": datetime.now().isoformat(),
                "source_simulation_id": simulation_id,
                "requested_root_seed": requested_root_seed,
                "root_seed": effective_root_seed,
            }
        )
        return persisted_spec

    def _derive_resolution_seed(
        self,
        root_seed: int,
        run_index: int,
        derive_run_seeds: bool,
        sampling_mode: str,
    ) -> int | None:
        """Keep seeded runs deterministic while preserving the unseeded escape hatch."""
        if sampling_mode == "unseeded":
            return None
        if not derive_run_seeds:
            return root_seed
        return root_seed + run_index - 1

    def _build_ensemble_state(
        self,
        simulation_id: str,
        ensemble_id: str,
        ensemble_spec: EnsembleSpec,
        effective_root_seed: int,
        outcome_spec: Dict[str, Any],
        run_ids: List[str],
        sim_dir: str,
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "artifact_type": "ensemble_state",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "status": "prepared",
            "created_at": now,
            "updated_at": now,
            "root_seed": effective_root_seed,
            "sampling_mode": ensemble_spec.sampling_mode,
            "run_count": ensemble_spec.run_count,
            "prepared_run_count": len(run_ids),
            "run_ids": run_ids,
            "source_artifacts": {
                name: filename for name, filename in self.PREPARE_ARTIFACT_FILENAMES.items()
            },
            "simulation_relative_path": os.path.relpath(
                self._get_ensemble_dir(simulation_id, ensemble_id),
                sim_dir,
            ),
            "outcome_metric_ids": [
                metric.get("metric_id")
                for metric in outcome_spec.get("metrics", [])
                if metric.get("metric_id")
            ],
        }

    def _build_resolved_config_artifact(
        self,
        resolved_config: Dict[str, Any],
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
        run_manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attach run-scoped provenance without changing the concrete config body."""
        resolved_artifact = deepcopy(resolved_config)
        resolved_artifact.update(
            {
                "artifact_type": "resolved_config",
                "schema_version": PROBABILISTIC_SCHEMA_VERSION,
                "generator_version": PROBABILISTIC_GENERATOR_VERSION,
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "base_graph_id": (
                    run_manifest.get("base_graph_id")
                    or resolved_config.get("base_graph_id")
                    or resolved_config.get("graph_id")
                ),
                "runtime_graph_id": run_manifest.get("runtime_graph_id"),
                "graph_id": (
                    run_manifest.get("base_graph_id")
                    or resolved_config.get("base_graph_id")
                    or resolved_config.get("graph_id")
                ),
                "root_seed": run_manifest.get("root_seed"),
                "sample_seed": run_manifest.get("seed_metadata", {}).get(
                    "resolution_seed"
                ),
                "sampled_values": run_manifest.get("resolved_values", {}),
                "resolved_at": run_manifest.get("generated_at"),
            }
        )
        return resolved_artifact

    def _build_aggregate_summary(self, ensemble_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate persisted run metrics without inventing unsupported probabilities."""
        metric_observations: Dict[str, List[Dict[str, Any]]] = {}
        metrics_files: List[str] = []
        missing_metrics_runs: List[str] = []
        complete_runs = 0
        partial_runs = 0
        total_runs = len(ensemble_payload.get("runs", []))

        for run_payload in ensemble_payload.get("runs", []):
            run_id = run_payload["run_id"]
            run_dir = run_payload["run_dir"]
            metrics_path = os.path.join(run_dir, "metrics.json")
            if not os.path.exists(metrics_path):
                missing_metrics_runs.append(run_id)
                continue

            metrics_files.append(
                os.path.relpath(metrics_path, ensemble_payload["ensemble_dir"])
            )
            metrics_payload = self._read_json(metrics_path)
            quality_status = metrics_payload.get("quality_checks", {}).get("status", "unknown")
            if quality_status == "complete":
                complete_runs += 1
            else:
                partial_runs += 1

            for metric_id, raw_metric_entry in metrics_payload.get("metric_values", {}).items():
                metric_entry = self._normalize_metric_entry(metric_id, raw_metric_entry)
                metric_observations.setdefault(metric_id, []).append(
                    {
                        "run_id": run_id,
                        "quality_status": quality_status,
                        "metric_entry": metric_entry,
                        "value": metric_entry.get("value"),
                    }
                )

        metric_summaries = {
            metric_id: self._build_metric_summary(
                metric_id=metric_id,
                observations=observations,
                total_runs=total_runs,
                degraded_runs_present=partial_runs > 0 or bool(missing_metrics_runs),
            )
            for metric_id, observations in sorted(metric_observations.items())
        }

        warnings = []
        runs_with_metrics = len(metrics_files)
        if runs_with_metrics < self.THIN_SAMPLE_WARNING_THRESHOLD:
            warnings.append("thin_sample")
        if partial_runs > 0:
            warnings.append("degraded_runs_present")
        if missing_metrics_runs:
            warnings.append("missing_run_metrics")

        return {
            "artifact_type": "aggregate_summary",
            "schema_version": "probabilistic.aggregate.v1",
            "generator_version": "probabilistic.aggregate.generator.v1",
            "simulation_id": ensemble_payload["simulation_id"],
            "ensemble_id": ensemble_payload["ensemble_id"],
            "metric_summaries": metric_summaries,
            "quality_summary": {
                "status": "partial" if partial_runs > 0 or missing_metrics_runs else "complete",
                "total_runs": total_runs,
                "runs_with_metrics": runs_with_metrics,
                "complete_runs": complete_runs,
                "partial_runs": partial_runs,
                "missing_metrics_runs": missing_metrics_runs,
                "warnings": warnings,
            },
            "source_artifacts": {
                "metrics_files": metrics_files,
                "outcome_metric_ids": ensemble_payload.get("state", {}).get(
                    "outcome_metric_ids",
                    [],
                ),
            },
            "generated_at": datetime.now().isoformat(),
        }

    def _build_metric_summary(
        self,
        *,
        metric_id: str,
        observations: List[Dict[str, Any]],
        total_runs: int,
        degraded_runs_present: bool,
    ) -> Dict[str, Any]:
        metric_entry = observations[0]["metric_entry"] if observations else {"metric_id": metric_id}
        usable_observations = [
            item for item in observations if item.get("value") is not None
        ]
        values = [item["value"] for item in usable_observations]
        complete_sample_count = sum(
            1 for item in usable_observations if item.get("quality_status") == "complete"
        )
        partial_sample_count = len(usable_observations) - complete_sample_count
        warnings = []
        if len(values) < self.THIN_SAMPLE_WARNING_THRESHOLD:
            warnings.append("thin_sample")
        if degraded_runs_present:
            warnings.append("degraded_runs_present")

        summary = {
            key: value
            for key, value in metric_entry.items()
            if key != "value"
        }
        summary.update(
            {
                "metric_id": metric_id,
                "sample_count": len(values),
                "observed_sample_count": len(observations),
                "complete_sample_count": complete_sample_count,
                "partial_sample_count": partial_sample_count,
                "missing_sample_count": max(total_runs - len(observations), 0),
                "warnings": warnings,
            }
        )

        if values and all(isinstance(value, bool) for value in values):
            true_count = sum(1 for value in values if value)
            false_count = len(values) - true_count
            dominant_value = true_count >= false_count
            dominant_probability = max(true_count, false_count) / len(values)
            summary.update(
                {
                    "distribution_kind": "binary",
                    "empirical_probability": true_count / len(values),
                    "dominant_value": dominant_value,
                    "dominant_probability": dominant_probability,
                    "counts": {
                        "false": false_count,
                        "true": true_count,
                    },
                }
            )
            return summary

        if values and all(isinstance(value, str) for value in values):
            category_counts: Dict[str, int] = {}
            for value in values:
                category_counts[value] = category_counts.get(value, 0) + 1
            dominant_category, dominant_count = sorted(
                category_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            summary.update(
                {
                    "distribution_kind": "categorical",
                    "dominant_value": dominant_category,
                    "dominant_probability": dominant_count / len(values),
                    "category_counts": category_counts,
                    "category_probabilities": {
                        category: count / len(values)
                        for category, count in category_counts.items()
                    },
                }
            )
            return summary

        numeric_values = [
            float(value)
            for value in values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        summary.update(
            {
                "distribution_kind": "continuous",
                "min": min(numeric_values) if numeric_values else None,
                "max": max(numeric_values) if numeric_values else None,
                "mean": (
                    sum(numeric_values) / len(numeric_values)
                    if numeric_values
                    else None
                ),
                "quantiles": {
                    "p10": self._compute_quantile(numeric_values, 0.10),
                    "p50": self._compute_quantile(numeric_values, 0.50),
                    "p90": self._compute_quantile(numeric_values, 0.90),
                },
            }
        )
        return summary

    def _normalize_metric_entry(self, metric_id: str, raw_metric_entry: Any) -> Dict[str, Any]:
        if isinstance(raw_metric_entry, dict):
            entry = dict(raw_metric_entry)
            entry.setdefault("metric_id", metric_id)
            return entry
        return {"metric_id": metric_id, "value": raw_metric_entry}

    def _compute_quantile(self, values: List[float], percentile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile
        lower_index = math.floor(position)
        upper_index = math.ceil(position)
        if lower_index == upper_index:
            return ordered[lower_index]
        lower_value = ordered[lower_index]
        upper_value = ordered[upper_index]
        weight = position - lower_index
        return lower_value + ((upper_value - lower_value) * weight)

    def _refresh_ensemble_state(self, simulation_id: str, ensemble_id: str) -> None:
        """Update derived run counts after a run-level delete."""
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        state_path = os.path.join(ensemble_dir, self.ENSEMBLE_STATE_FILENAME)
        if not os.path.exists(state_path):
            return

        state = self._read_json(state_path)
        run_ids = self._list_run_ids(simulation_id, ensemble_id)
        state["run_ids"] = run_ids
        state["prepared_run_count"] = len(run_ids)
        state["updated_at"] = datetime.now().isoformat()
        self._write_json(state_path, state)

    def _next_ensemble_id(self, simulation_id: str) -> str:
        """Choose the next deterministic, zero-padded ensemble identifier."""
        ensemble_root = self._get_ensemble_root_dir(simulation_id)
        os.makedirs(ensemble_root, exist_ok=True)
        existing_ids = [
            int(match.group(1))
            for entry in os.listdir(ensemble_root)
            if os.path.isdir(os.path.join(ensemble_root, entry))
            for match in [self._ENSEMBLE_DIR_RE.match(entry)]
            if match
        ]
        next_id = max(existing_ids, default=0) + 1
        return f"{next_id:04d}"

    def _list_run_ids(self, simulation_id: str, ensemble_id: str) -> List[str]:
        runs_dir = os.path.join(self._get_ensemble_dir(simulation_id, ensemble_id), self.RUNS_DIRNAME)
        if not os.path.isdir(runs_dir):
            return []
        return sorted(
            match.group(1)
            for entry in os.listdir(runs_dir)
            if os.path.isdir(os.path.join(runs_dir, entry))
            for match in [self._RUN_DIR_RE.match(entry)]
            if match
        )

    def _next_run_id(self, simulation_id: str, ensemble_id: str) -> str:
        existing_ids = [
            int(run_id)
            for run_id in self._list_run_ids(simulation_id, ensemble_id)
        ]
        return f"{(max(existing_ids, default=0) + 1):04d}"

    def _get_simulation_dir(self, simulation_id: str) -> str:
        return os.path.join(self.simulation_data_dir, simulation_id)

    def _get_ensemble_root_dir(self, simulation_id: str) -> str:
        return os.path.join(self._get_simulation_dir(simulation_id), self.ENSEMBLE_ROOT_DIRNAME)

    def _get_ensemble_dir(self, simulation_id: str, ensemble_id: str) -> str:
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        return os.path.join(
            self._get_ensemble_root_dir(simulation_id),
            f"{self.ENSEMBLE_DIR_PREFIX}{normalized_ensemble_id}",
        )

    def _get_run_dir(self, simulation_id: str, ensemble_id: str, run_id: str) -> str:
        normalized_run_id = self._normalize_run_id(run_id)
        return os.path.join(
            self._get_ensemble_dir(simulation_id, ensemble_id),
            self.RUNS_DIRNAME,
            f"{self.RUN_DIR_PREFIX}{normalized_run_id}",
        )

    def _normalize_ensemble_id(self, ensemble_id: str) -> str:
        if not isinstance(ensemble_id, str) or not ensemble_id:
            raise ValueError("ensemble_id is required")
        if self._ENSEMBLE_DIR_RE.fullmatch(ensemble_id):
            return ensemble_id.removeprefix(self.ENSEMBLE_DIR_PREFIX)
        if re.fullmatch(r"\d{4}", ensemble_id):
            return ensemble_id
        raise ValueError(f"Invalid ensemble_id: {ensemble_id}")

    def _normalize_run_id(self, run_id: str) -> str:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id is required")
        if self._RUN_DIR_RE.fullmatch(run_id):
            return run_id.removeprefix(self.RUN_DIR_PREFIX)
        if re.fullmatch(r"\d{4}", run_id):
            return run_id
        raise ValueError(f"Invalid run_id: {run_id}")

    def _read_json(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, file_path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
