"""
Deterministic scenario clustering for stored probabilistic ensemble runs.

This slice stays intentionally narrow:
- it clusters only on structured run-level metric values,
- it uses prototype runs and warning flags instead of narrative summaries,
- it persists a reproducible `scenario_clusters.json` artifact for stored runs only.

It does not claim calibration, causal attribution, or richer report semantics.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional

from ..config import Config


CLUSTERS_SCHEMA_VERSION = "probabilistic.clusters.v1"
CLUSTERS_GENERATOR_VERSION = "probabilistic.clusters.generator.v1"


class ScenarioClusterer:
    """Build and persist deterministic scenario-family artifacts."""

    ENSEMBLE_ROOT_DIRNAME = "ensemble"
    ENSEMBLE_DIR_PREFIX = "ensemble_"
    RUNS_DIRNAME = "runs"
    RUN_DIR_PREFIX = "run_"
    ENSEMBLE_STATE_FILENAME = "ensemble_state.json"
    RUN_MANIFEST_FILENAME = "run_manifest.json"
    METRICS_FILENAME = "metrics.json"
    CLUSTERS_FILENAME = "scenario_clusters.json"
    THIN_SAMPLE_WARNING_THRESHOLD = 5
    Z_BUCKET_LOW = -0.5
    Z_BUCKET_HIGH = 0.5
    DISTINGUISHING_METRIC_LIMIT = 3

    _RUN_DIR_RE = re.compile(r"^run_(\d{4})$")

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def get_scenario_clusters(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Build and persist one scenario clustering artifact for the ensemble."""
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        state_path = os.path.join(ensemble_dir, self.ENSEMBLE_STATE_FILENAME)
        if not os.path.exists(state_path):
            raise ValueError(
                f"Ensemble does not exist for simulation {simulation_id}: {ensemble_id}"
            )

        ensemble_state = self._read_json(state_path)
        (
            run_payloads,
            total_runs,
            missing_metrics_runs,
            invalid_metrics_runs,
            degraded_metrics_runs,
            invalid_manifest_runs,
        ) = self._load_run_payloads(ensemble_dir)
        metric_ids = self._determine_metric_ids(run_payloads)
        observed_numeric_metric_ids = self._determine_observed_numeric_metric_ids(
            run_payloads
        )
        expected_metric_ids = set(ensemble_state.get("outcome_metric_ids", [])) or set(
            observed_numeric_metric_ids
        )
        partial_feature_space = bool(metric_ids) and (
            set(metric_ids) != expected_metric_ids
        )
        metric_stats = self._compute_metric_stats(run_payloads, metric_ids)
        cluster_map = self._group_runs_into_clusters(run_payloads, metric_ids, metric_stats)
        clustered_runs = sum(len(items) for items in cluster_map.values())
        warnings = self._build_quality_warnings(
            total_runs=total_runs,
            clustered_runs=clustered_runs,
            cluster_count=len(cluster_map),
            missing_metrics_runs=missing_metrics_runs,
            invalid_metrics_runs=invalid_metrics_runs,
            degraded_metrics_runs=degraded_metrics_runs,
            invalid_manifest_runs=invalid_manifest_runs,
            metric_stats=metric_stats,
            metric_ids=metric_ids,
            partial_feature_space=partial_feature_space,
        )

        clusters = self._build_cluster_payloads(
            cluster_map=cluster_map,
            metric_ids=metric_ids,
            metric_stats=metric_stats,
            total_runs=total_runs,
        )

        artifact = {
            "artifact_type": "scenario_clusters",
            "schema_version": CLUSTERS_SCHEMA_VERSION,
            "generator_version": CLUSTERS_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "cluster_count": len(clusters),
            "clusters": clusters,
            "feature_vector_schema": {
                "metric_ids": metric_ids,
                "standardization": "zscore",
                "bucket_thresholds": {
                    "low": self.Z_BUCKET_LOW,
                    "high": self.Z_BUCKET_HIGH,
                },
                "source": "metrics.json",
            },
            "quality_summary": {
                "status": "partial"
                if (
                    missing_metrics_runs
                    or invalid_metrics_runs
                    or degraded_metrics_runs
                    or invalid_manifest_runs
                    or not metric_ids
                    or partial_feature_space
                )
                else "complete",
                "total_runs": total_runs,
                "runs_with_metrics": len(run_payloads),
                "clustered_runs": clustered_runs,
                "missing_metrics_runs": missing_metrics_runs,
                "invalid_metrics_runs": invalid_metrics_runs,
                "degraded_metrics_runs": degraded_metrics_runs,
                "invalid_manifest_runs": invalid_manifest_runs,
                "warnings": warnings,
            },
            "source_artifacts": {
                "metrics_files": [
                    payload["metrics_relpath"] for payload in run_payloads
                ],
                "run_manifest_files": [
                    payload["manifest_relpath"] for payload in run_payloads
                ],
                "outcome_metric_ids": ensemble_state.get("outcome_metric_ids", []),
            },
            "generated_at": self._derive_generated_at(run_payloads),
        }

        self._write_json(os.path.join(ensemble_dir, self.CLUSTERS_FILENAME), artifact)
        return artifact

    def _get_ensemble_dir(self, simulation_id: str, ensemble_id: str) -> str:
        normalized = self._normalize_ensemble_id(ensemble_id)
        return os.path.join(
            self.simulation_data_dir,
            simulation_id,
            self.ENSEMBLE_ROOT_DIRNAME,
            f"{self.ENSEMBLE_DIR_PREFIX}{normalized}",
        )

    def _normalize_ensemble_id(self, ensemble_id: str) -> str:
        normalized = str(ensemble_id).strip()
        if normalized.startswith(self.ENSEMBLE_DIR_PREFIX):
            normalized = normalized[len(self.ENSEMBLE_DIR_PREFIX) :]
        return normalized.zfill(4)

    def _load_run_payloads(
        self,
        ensemble_dir: str,
    ) -> tuple[
        List[Dict[str, Any]],
        int,
        List[str],
        List[str],
        List[str],
        List[str],
    ]:
        runs_dir = os.path.join(ensemble_dir, self.RUNS_DIRNAME)
        if not os.path.isdir(runs_dir):
            return [], 0, [], [], [], []

        run_payloads: List[Dict[str, Any]] = []
        missing_metrics_runs: List[str] = []
        invalid_metrics_runs: List[str] = []
        degraded_metrics_runs: List[str] = []
        invalid_manifest_runs: List[str] = []
        total_runs = 0
        for entry in sorted(os.listdir(runs_dir)):
            match = self._RUN_DIR_RE.match(entry)
            if not match:
                continue
            run_id = match.group(1)
            total_runs += 1
            run_dir = os.path.join(runs_dir, entry)
            metrics_path = os.path.join(run_dir, self.METRICS_FILENAME)
            if not os.path.exists(metrics_path):
                missing_metrics_runs.append(run_id)
                continue

            manifest_path = os.path.join(run_dir, self.RUN_MANIFEST_FILENAME)
            try:
                metrics_payload = self._read_json(metrics_path)
            except (json.JSONDecodeError, OSError):
                invalid_metrics_runs.append(run_id)
                continue
            if not isinstance(metrics_payload, dict):
                invalid_metrics_runs.append(run_id)
                continue
            manifest_payload: Dict[str, Any] = {}
            if os.path.exists(manifest_path):
                try:
                    manifest_payload = self._read_json(manifest_path)
                except (json.JSONDecodeError, OSError):
                    invalid_manifest_runs.append(run_id)
                    manifest_payload = {}
                if not isinstance(manifest_payload, dict):
                    invalid_manifest_runs.append(run_id)
                    manifest_payload = {}
            quality_checks = metrics_payload.get("quality_checks", {})
            if (
                quality_checks.get("status") != "complete"
                or quality_checks.get("run_status") != "completed"
            ):
                degraded_metrics_runs.append(run_id)
                continue
            run_payloads.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "metrics": metrics_payload,
                    "manifest": manifest_payload,
                    "metrics_relpath": os.path.relpath(metrics_path, ensemble_dir),
                    "manifest_relpath": os.path.relpath(manifest_path, ensemble_dir)
                    if os.path.exists(manifest_path)
                    else None,
                }
            )

        return (
            run_payloads,
            total_runs,
            missing_metrics_runs,
            invalid_metrics_runs,
            degraded_metrics_runs,
            invalid_manifest_runs,
        )

    def _determine_metric_ids(self, run_payloads: List[Dict[str, Any]]) -> List[str]:
        metric_sets: List[set[str]] = []
        for payload in run_payloads:
            numeric_ids = {
                metric_id
                for metric_id, raw_entry in payload["metrics"].get("metric_values", {}).items()
                if self._coerce_numeric_value(raw_entry) is not None
            }
            if numeric_ids:
                metric_sets.append(numeric_ids)

        if not metric_sets:
            return []
        return sorted(set.intersection(*metric_sets))

    def _determine_observed_numeric_metric_ids(
        self,
        run_payloads: List[Dict[str, Any]],
    ) -> List[str]:
        observed = set()
        for payload in run_payloads:
            observed.update(
                metric_id
                for metric_id, raw_entry in payload["metrics"].get("metric_values", {}).items()
                if self._coerce_numeric_value(raw_entry) is not None
            )
        return sorted(observed)

    def _compute_metric_stats(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        for metric_id in metric_ids:
            values = [
                self._coerce_numeric_value(
                    payload["metrics"].get("metric_values", {}).get(metric_id)
                )
                for payload in run_payloads
            ]
            numeric_values = [value for value in values if value is not None]
            if not numeric_values:
                continue
            mean = sum(numeric_values) / len(numeric_values)
            variance = sum((value - mean) ** 2 for value in numeric_values) / len(
                numeric_values
            )
            stats[metric_id] = {
                "mean": mean,
                "stddev": math.sqrt(variance),
            }
        return stats

    def _group_runs_into_clusters(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
    ) -> Dict[tuple[str, ...], List[Dict[str, Any]]]:
        if not metric_ids:
            return {}
        cluster_map: Dict[tuple[str, ...], List[Dict[str, Any]]] = {}
        for payload in run_payloads:
            vector: Dict[str, float] = {}
            standardized: Dict[str, float] = {}
            feature_signature: Dict[str, str] = {}
            missing_metric = False
            for metric_id in metric_ids:
                value = self._coerce_numeric_value(
                    payload["metrics"].get("metric_values", {}).get(metric_id)
                )
                if value is None:
                    missing_metric = True
                    break
                vector[metric_id] = value
                z_score = self._compute_z_score(value, metric_stats.get(metric_id, {}))
                standardized[metric_id] = z_score
                feature_signature[metric_id] = self._bucket_z_score(z_score)

            if missing_metric:
                continue

            enriched = dict(payload)
            enriched["feature_vector"] = vector
            enriched["standardized_vector"] = standardized
            enriched["feature_signature"] = feature_signature
            cluster_key = tuple(feature_signature[metric_id] for metric_id in metric_ids)
            cluster_map.setdefault(cluster_key, []).append(enriched)
        return dict(sorted(cluster_map.items(), key=lambda item: item[0]))

    def _build_quality_warnings(
        self,
        *,
        total_runs: int,
        clustered_runs: int,
        cluster_count: int,
        missing_metrics_runs: List[str],
        invalid_metrics_runs: List[str],
        degraded_metrics_runs: List[str],
        invalid_manifest_runs: List[str],
        metric_stats: Dict[str, Dict[str, float]],
        metric_ids: List[str],
        partial_feature_space: bool,
    ) -> List[str]:
        warnings: List[str] = []
        if clustered_runs < self.THIN_SAMPLE_WARNING_THRESHOLD:
            warnings.append("thin_sample")
        if missing_metrics_runs:
            warnings.append("missing_run_metrics")
        if invalid_metrics_runs:
            warnings.append("invalid_run_metrics")
        if degraded_metrics_runs:
            warnings.append("degraded_run_metrics")
        if invalid_manifest_runs:
            warnings.append("invalid_run_manifest")
        if not metric_ids:
            warnings.append("no_shared_numeric_metrics")
        if partial_feature_space:
            warnings.append("partial_feature_space")
        if (
            clustered_runs < self.THIN_SAMPLE_WARNING_THRESHOLD
            or total_runs == 0
            or cluster_count <= 1
            or not metric_ids
            or any(stat.get("stddev", 0.0) == 0.0 for stat in metric_stats.values())
        ):
            warnings.append("low_confidence")
        return warnings

    def _build_cluster_payloads(
        self,
        *,
        cluster_map: Dict[tuple[str, ...], List[Dict[str, Any]]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
        total_runs: int,
    ) -> List[Dict[str, Any]]:
        clusters: List[Dict[str, Any]] = []
        overall_means = {
            metric_id: stat.get("mean")
            for metric_id, stat in metric_stats.items()
        }
        for index, (_, members) in enumerate(cluster_map.items(), start=1):
            centroid = {
                metric_id: sum(
                    member["feature_vector"][metric_id] for member in members
                )
                / len(members)
                for metric_id in metric_ids
            }
            prototype = min(
                members,
                key=lambda member: (
                    self._distance_to_centroid(member["feature_vector"], centroid),
                    member["run_id"],
                ),
            )
            distinguishing_metrics = sorted(
                [
                    {
                        "metric_id": metric_id,
                        "cluster_mean": centroid.get(metric_id),
                        "overall_mean": overall_means.get(metric_id),
                        "mean_delta": (
                            centroid.get(metric_id, 0.0)
                            - overall_means.get(metric_id, 0.0)
                        ),
                        "direction": self._metric_direction(
                            centroid.get(metric_id), overall_means.get(metric_id)
                        ),
                    }
                    for metric_id in metric_ids
                ],
                key=lambda item: (
                    abs(item["mean_delta"]),
                    item["metric_id"],
                ),
                reverse=True,
            )[: self.DISTINGUISHING_METRIC_LIMIT]

            cluster_warnings = []
            if all(metric_stats[metric_id].get("stddev", 0.0) == 0.0 for metric_id in metric_ids):
                cluster_warnings.append("low_metric_variance")

            clusters.append(
                {
                    "cluster_id": f"cluster_{index:04d}",
                    "run_count": len(members),
                    "probability_mass": len(members) / total_runs if total_runs else 0.0,
                    "prototype_run_id": prototype["run_id"],
                    "member_run_ids": [member["run_id"] for member in members],
                    "feature_signature": dict(prototype["feature_signature"]),
                    "centroid": centroid,
                    "distinguishing_metrics": distinguishing_metrics,
                    "prototype_resolved_values": prototype["manifest"].get(
                        "resolved_values", {}
                    ),
                    "prototype_top_topics": prototype["metrics"].get("top_topics", []),
                    "warnings": cluster_warnings,
                }
            )

        return clusters

    def _derive_generated_at(self, run_payloads: List[Dict[str, Any]]) -> str:
        timestamps = []
        for payload in run_payloads:
            metrics_timestamp = payload["metrics"].get("extracted_at")
            manifest_timestamp = payload["manifest"].get("generated_at")
            if metrics_timestamp:
                timestamps.append(metrics_timestamp)
            if manifest_timestamp:
                timestamps.append(manifest_timestamp)
        if timestamps:
            return max(timestamps)
        return "1970-01-01T00:00:00"

    def _compute_z_score(
        self,
        value: float,
        metric_stat: Dict[str, float],
    ) -> float:
        stddev = metric_stat.get("stddev")
        mean = metric_stat.get("mean", 0.0)
        if not stddev:
            return 0.0
        return (value - mean) / stddev

    def _bucket_z_score(self, z_score: float) -> str:
        if z_score <= self.Z_BUCKET_LOW:
            return "low"
        if z_score >= self.Z_BUCKET_HIGH:
            return "high"
        return "mid"

    def _distance_to_centroid(
        self,
        feature_vector: Dict[str, float],
        centroid: Dict[str, float],
    ) -> float:
        return sum(
            (feature_vector[metric_id] - centroid[metric_id]) ** 2
            for metric_id in centroid
        )

    def _metric_direction(
        self,
        cluster_mean: Optional[float],
        overall_mean: Optional[float],
    ) -> str:
        if cluster_mean is None or overall_mean is None:
            return "neutral"
        if cluster_mean > overall_mean:
            return "high"
        if cluster_mean < overall_mean:
            return "low"
        return "neutral"

    def _coerce_numeric_value(self, raw_entry: Any) -> Optional[float]:
        if isinstance(raw_entry, dict):
            value = raw_entry.get("value")
        else:
            value = raw_entry

        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
