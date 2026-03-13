"""
Deterministic sensitivity ranking for stored probabilistic ensemble runs.

This slice is intentionally conservative:
- it analyzes only stored runs with complete metrics and readable manifests,
- it treats resolved-value variation as observational evidence rather than
  controlled perturbation proof,
- it ranks drivers by observed outcome deltas without claiming calibration or
  causality.

The artifact is still useful for operator triage and future report consumers,
but every payload keeps the weak-evidence caveats explicit.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from ..config import Config


SENSITIVITY_SCHEMA_VERSION = "probabilistic.sensitivity.v1"
SENSITIVITY_GENERATOR_VERSION = "probabilistic.sensitivity.generator.v1"


class SensitivityAnalyzer:
    """Build and persist one observational sensitivity artifact per ensemble."""

    ENSEMBLE_ROOT_DIRNAME = "ensemble"
    ENSEMBLE_DIR_PREFIX = "ensemble_"
    RUNS_DIRNAME = "runs"
    RUN_DIR_PREFIX = "run_"
    ENSEMBLE_STATE_FILENAME = "ensemble_state.json"
    RUN_MANIFEST_FILENAME = "run_manifest.json"
    RESOLVED_CONFIG_FILENAME = "resolved_config.json"
    METRICS_FILENAME = "metrics.json"
    SENSITIVITY_FILENAME = "sensitivity.json"
    THIN_SAMPLE_WARNING_THRESHOLD = 5

    _RUN_DIR_RE = re.compile(r"^run_(\d{4})$")

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def get_sensitivity_analysis(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Build and persist one observational sensitivity artifact."""
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        ensemble_dir = self._get_ensemble_dir(simulation_id, normalized_ensemble_id)
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
            missing_resolved_value_runs,
        ) = self._load_run_payloads(ensemble_dir)
        metric_ids = self._determine_metric_ids(run_payloads)
        driver_rankings = self._build_driver_rankings(run_payloads, metric_ids)
        warnings = self._build_quality_warnings(
            analyzed_runs=len(run_payloads),
            missing_metrics_runs=missing_metrics_runs,
            invalid_metrics_runs=invalid_metrics_runs,
            degraded_metrics_runs=degraded_metrics_runs,
            invalid_manifest_runs=invalid_manifest_runs,
            missing_resolved_value_runs=missing_resolved_value_runs,
            has_numeric_metrics=bool(metric_ids),
            has_ranked_drivers=bool(driver_rankings),
        )

        artifact = {
            "artifact_type": "sensitivity",
            "schema_version": SENSITIVITY_SCHEMA_VERSION,
            "generator_version": SENSITIVITY_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": normalized_ensemble_id,
            "driver_count": len(driver_rankings),
            "driver_rankings": driver_rankings,
            "methodology": {
                "analysis_mode": "observational_resolved_values",
                "driver_source": (
                    "run_manifest.resolved_values with resolved_config.sampled_values "
                    "fallback when available"
                ),
                "outcome_source": "metrics.json numeric metric_values",
                "grouping_policy": "observed identical resolved values",
                "effect_size_definition": "max_group_mean_minus_min_group_mean",
                "causal_interpretation": "not_supported",
            },
            "quality_summary": {
                "status": "partial"
                if (
                    missing_metrics_runs
                    or invalid_metrics_runs
                    or degraded_metrics_runs
                    or invalid_manifest_runs
                    or missing_resolved_value_runs
                    or not metric_ids
                )
                else "complete",
                "total_runs": total_runs,
                "analyzed_runs": len(run_payloads),
                "missing_metrics_runs": missing_metrics_runs,
                "invalid_metrics_runs": invalid_metrics_runs,
                "degraded_metrics_runs": degraded_metrics_runs,
                "invalid_manifest_runs": invalid_manifest_runs,
                "missing_resolved_value_runs": missing_resolved_value_runs,
                "warnings": warnings,
            },
            "source_artifacts": {
                "metrics_files": [
                    payload["metrics_relpath"] for payload in run_payloads
                ],
                "run_manifest_files": [
                    payload["manifest_relpath"] for payload in run_payloads
                ],
                "resolved_config_files": [
                    payload["resolved_config_relpath"]
                    for payload in run_payloads
                    if payload["resolved_config_relpath"]
                ],
                "outcome_metric_ids": ensemble_state.get("outcome_metric_ids", []),
            },
            "generated_at": self._derive_generated_at(run_payloads),
        }

        self._write_json(
            os.path.join(ensemble_dir, self.SENSITIVITY_FILENAME),
            artifact,
        )
        return artifact

    def get_sensitivity(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Compatibility alias for the earlier draft method name."""
        return self.get_sensitivity_analysis(simulation_id, ensemble_id)

    def _get_ensemble_dir(self, simulation_id: str, ensemble_id: str) -> str:
        return os.path.join(
            self.simulation_data_dir,
            simulation_id,
            self.ENSEMBLE_ROOT_DIRNAME,
            f"{self.ENSEMBLE_DIR_PREFIX}{self._normalize_ensemble_id(ensemble_id)}",
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
        List[str],
    ]:
        runs_dir = os.path.join(ensemble_dir, self.RUNS_DIRNAME)
        if not os.path.isdir(runs_dir):
            return [], 0, [], [], [], [], []

        run_payloads: List[Dict[str, Any]] = []
        missing_metrics_runs: List[str] = []
        invalid_metrics_runs: List[str] = []
        degraded_metrics_runs: List[str] = []
        invalid_manifest_runs: List[str] = []
        missing_resolved_value_runs: List[str] = []
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
            resolved_config_path = os.path.join(run_dir, self.RESOLVED_CONFIG_FILENAME)

            try:
                metrics_payload = self._read_json(metrics_path)
            except (json.JSONDecodeError, OSError):
                invalid_metrics_runs.append(run_id)
                continue
            if not isinstance(metrics_payload, dict):
                invalid_metrics_runs.append(run_id)
                continue

            if (
                metrics_payload.get("quality_checks", {}).get("status") != "complete"
                or metrics_payload.get("quality_checks", {}).get("run_status")
                != "completed"
            ):
                degraded_metrics_runs.append(run_id)
                continue

            try:
                manifest_payload = self._read_json(manifest_path)
            except (json.JSONDecodeError, OSError):
                invalid_manifest_runs.append(run_id)
                continue
            if not isinstance(manifest_payload, dict):
                invalid_manifest_runs.append(run_id)
                continue

            resolved_config_payload: Dict[str, Any] = {}
            if os.path.exists(resolved_config_path):
                try:
                    raw_resolved_config = self._read_json(resolved_config_path)
                except (json.JSONDecodeError, OSError):
                    raw_resolved_config = {}
                if isinstance(raw_resolved_config, dict):
                    resolved_config_payload = raw_resolved_config

            # Prefer the manifest because that is the runtime-owned artifact. When
            # older fixtures only persist sampled values in resolved_config, fall
            # back to that read instead of pretending the run has no driver data.
            resolved_values = manifest_payload.get("resolved_values", {})
            if not isinstance(resolved_values, dict) or not resolved_values:
                resolved_values = resolved_config_payload.get("sampled_values", {})
            if not isinstance(resolved_values, dict) or not resolved_values:
                missing_resolved_value_runs.append(run_id)
                continue

            run_payloads.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "metrics": metrics_payload,
                    "manifest": manifest_payload,
                    "resolved_config": resolved_config_payload,
                    "resolved_values": resolved_values,
                    "metrics_relpath": os.path.relpath(metrics_path, ensemble_dir),
                    "manifest_relpath": os.path.relpath(manifest_path, ensemble_dir),
                    "resolved_config_relpath": (
                        os.path.relpath(resolved_config_path, ensemble_dir)
                        if os.path.exists(resolved_config_path)
                        else None
                    ),
                }
            )

        return (
            run_payloads,
            total_runs,
            missing_metrics_runs,
            invalid_metrics_runs,
            degraded_metrics_runs,
            invalid_manifest_runs,
            missing_resolved_value_runs,
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

    def _build_driver_rankings(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not run_payloads or not metric_ids:
            return []

        candidate_fields = sorted(
            {
                field_path
                for payload in run_payloads
                for field_path in payload.get("resolved_values", {})
            }
        )

        rankings: List[Dict[str, Any]] = []
        for field_path in candidate_fields:
            values_by_run = []
            for payload in run_payloads:
                resolved_values = payload.get("resolved_values", {})
                if field_path not in resolved_values:
                    values_by_run = []
                    break
                values_by_run.append((payload, resolved_values[field_path]))

            if not values_by_run:
                continue

            distinct_values = {
                self._stable_value_key(value)
                for _, value in values_by_run
            }
            if len(distinct_values) < 2:
                continue

            group_payloads = self._group_runs_by_driver_value(values_by_run)
            metric_impacts = self._build_metric_impacts(group_payloads, metric_ids)
            if not metric_impacts:
                continue

            overall_effect_score = round(
                sum(
                    impact.get("relative_effect")
                    if impact.get("relative_effect") is not None
                    else impact["effect_size"]
                    for impact in metric_impacts
                ),
                4,
            )
            driver_kind = self._infer_driver_kind([value for _, value in values_by_run])
            rankings.append(
                {
                    "driver_id": field_path,
                    "field_path": field_path,
                    "driver_kind": driver_kind,
                    "sample_count": len(values_by_run),
                    "distinct_value_count": len(group_payloads),
                    "overall_effect_score": overall_effect_score,
                    "metric_impacts": metric_impacts,
                    "metric_effects": metric_impacts,
                }
            )

        rankings.sort(
            key=lambda item: (-item["overall_effect_score"], item["field_path"])
        )
        return rankings

    def _group_runs_by_driver_value(
        self,
        values_by_run: List[tuple[Dict[str, Any], Any]],
    ) -> List[Dict[str, Any]]:
        group_map: Dict[str, Dict[str, Any]] = {}
        for payload, raw_value in values_by_run:
            label = self._format_value_label(raw_value)
            key = self._stable_value_key(raw_value)
            group = group_map.setdefault(
                key,
                {
                    "value": raw_value,
                    "value_label": label,
                    "members": [],
                },
            )
            group["members"].append(payload)

        return sorted(
            group_map.values(),
            key=lambda item: (
                self._sort_value(item["value"]),
                item["value_label"],
            ),
        )

    def _build_metric_impacts(
        self,
        group_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> List[Dict[str, Any]]:
        impacts: List[Dict[str, Any]] = []
        for metric_id in metric_ids:
            group_summaries = []
            for group in group_payloads:
                values = [
                    self._coerce_numeric_value(
                        payload["metrics"].get("metric_values", {}).get(metric_id)
                    )
                    for payload in group["members"]
                ]
                numeric_values = [value for value in values if value is not None]
                if not numeric_values:
                    group_summaries = []
                    break
                group_summaries.append(
                    {
                        "value_label": group["value_label"],
                        "sample_count": len(numeric_values),
                        "mean": round(sum(numeric_values) / len(numeric_values), 4),
                        "min": round(min(numeric_values), 4),
                        "max": round(max(numeric_values), 4),
                    }
                )

            if len(group_summaries) < 2:
                continue

            ordered_means = [group["mean"] for group in group_summaries]
            effect_size = round(max(ordered_means) - min(ordered_means), 4)
            low_group = min(group_summaries, key=lambda item: (item["mean"], item["value_label"]))
            high_group = max(group_summaries, key=lambda item: (item["mean"], item["value_label"]))
            baseline_mean = low_group["mean"]
            relative_effect = None
            if baseline_mean not in (None, 0):
                relative_effect = round(effect_size / abs(baseline_mean), 4)

            impacts.append(
                {
                    "metric_id": metric_id,
                    "effect_size": effect_size,
                    "relative_effect": relative_effect,
                    "strongest_groups": [
                        low_group["value_label"],
                        high_group["value_label"],
                    ],
                    "group_summaries": group_summaries,
                }
            )

        impacts.sort(
            key=lambda item: (-item["effect_size"], item["metric_id"])
        )
        return impacts

    def _build_quality_warnings(
        self,
        *,
        analyzed_runs: int,
        missing_metrics_runs: List[str],
        invalid_metrics_runs: List[str],
        degraded_metrics_runs: List[str],
        invalid_manifest_runs: List[str],
        missing_resolved_value_runs: List[str],
        has_numeric_metrics: bool,
        has_ranked_drivers: bool,
    ) -> List[str]:
        warnings = ["observational_only"]
        if analyzed_runs < self.THIN_SAMPLE_WARNING_THRESHOLD:
            warnings.append("thin_sample")
        if missing_metrics_runs:
            warnings.append("missing_run_metrics")
        if invalid_metrics_runs:
            warnings.append("invalid_run_metrics")
        if degraded_metrics_runs:
            warnings.append("degraded_run_metrics")
        if invalid_manifest_runs:
            warnings.append("invalid_run_manifest")
        if missing_resolved_value_runs:
            warnings.append("missing_resolved_values")
        if not has_numeric_metrics:
            warnings.append("no_shared_numeric_metrics")
        if not has_ranked_drivers:
            warnings.append("no_varying_drivers")
        return warnings

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

    def _infer_driver_kind(self, values: List[Any]) -> str:
        if values and all(isinstance(value, bool) for value in values):
            return "binary"
        if values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            return "numeric"
        return "categorical"

    def _format_value_label(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return format(value, "g")
        return str(value)

    def _stable_value_key(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def _sort_value(self, value: Any) -> tuple[int, Any]:
        if isinstance(value, bool):
            return (0, int(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return (0, float(value))
        return (1, str(value))

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
