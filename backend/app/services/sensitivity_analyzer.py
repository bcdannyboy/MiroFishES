"""
Deterministic sensitivity ranking for stored probabilistic ensemble runs.

This slice is intentionally conservative:
- it analyzes only stored runs with inspectable metrics and resolved values,
- it treats resolved-value variation as observational evidence rather than
  controlled perturbation proof,
- it groups numeric drivers into explicit support-aware bands instead of exact
  value identity when enough evidence exists.

The artifact stays useful for operator triage and report consumers without
claiming calibration or causality.
"""

from __future__ import annotations

from collections import Counter
import json
import os
import re
from typing import Any, Dict, List, Optional

from ..config import Config
from .analytics_policy import AnalyticsPolicy
from .phase_timing import PhaseTimingRecorder


SENSITIVITY_SCHEMA_VERSION = "probabilistic.sensitivity.v2"
SENSITIVITY_GENERATOR_VERSION = "probabilistic.sensitivity.generator.v2"


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
    PHASE_TIMINGS_FILENAME = "ensemble_phase_timings.json"
    THIN_SAMPLE_WARNING_THRESHOLD = 5

    _RUN_DIR_RE = re.compile(r"^run_(\d{4})$")

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.get_simulation_data_dir()
        self.analytics_policy = AnalyticsPolicy()

    def get_sensitivity_analysis(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Build and persist one observational sensitivity artifact."""
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        ensemble_dir = self._get_ensemble_dir(simulation_id, normalized_ensemble_id)
        phase_timing = PhaseTimingRecorder(
            artifact_path=os.path.join(ensemble_dir, self.PHASE_TIMINGS_FILENAME),
            scope_kind="ensemble",
            scope_id=f"{simulation_id}::{normalized_ensemble_id}",
        )
        with phase_timing.measure_phase("sensitivity", metadata={}) as phase_metadata:
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

            eligible_run_payloads = []
            excluded_runs = []
            for payload in run_payloads:
                eligibility = self.analytics_policy.assess_run(
                    mode="sensitivity",
                    run_payload={
                        "run_id": payload["run_id"],
                        "metrics_payload": payload.get("metrics"),
                        "manifest_valid": payload.get("manifest_valid", True),
                        "resolved_values": payload.get("resolved_values"),
                        "available_numeric_metric_ids": payload.get(
                            "available_numeric_metric_ids",
                            [],
                        ),
                    },
                    required_metric_ids=metric_ids,
                )
                if eligibility["eligible"]:
                    eligible_run_payloads.append(payload)
                else:
                    excluded_runs.append(
                        {"run_id": payload["run_id"], "reasons": eligibility["reasons"]}
                    )

            metric_stats = self._compute_metric_stats(eligible_run_payloads, metric_ids)
            cluster_membership = self._load_cluster_membership(simulation_id, normalized_ensemble_id)
            scenario_diversity_context = self._load_scenario_diversity_context(
                simulation_id,
                normalized_ensemble_id,
            )
            designed_comparisons = self._build_designed_comparisons(
                eligible_run_payloads,
                metric_ids,
                metric_stats,
            )
            driver_rankings = self._build_driver_rankings(
                eligible_run_payloads,
                metric_ids,
                metric_stats,
                cluster_membership,
            )
            if self._should_withhold_rankings(
                cluster_membership=cluster_membership,
                scenario_diversity_context=scenario_diversity_context,
            ):
                driver_rankings = []
            warnings = self._build_quality_warnings(
                analyzed_runs=len(eligible_run_payloads),
                missing_metrics_runs=missing_metrics_runs,
                invalid_metrics_runs=invalid_metrics_runs,
                degraded_metrics_runs=degraded_metrics_runs,
                invalid_manifest_runs=invalid_manifest_runs,
                missing_resolved_value_runs=missing_resolved_value_runs,
                has_numeric_metrics=bool(metric_ids),
                has_ranked_drivers=bool(driver_rankings),
                has_designed_comparisons=bool(designed_comparisons),
                scenario_diversity_context=scenario_diversity_context,
            )
            driver_rankings = self._annotate_driver_rankings(
                driver_rankings=driver_rankings,
                quality_warnings=warnings,
            )
            support_assessment = self._build_support_assessment(
                warnings=warnings,
            )

            phase_metadata["total_runs"] = total_runs
            phase_metadata["analyzed_runs"] = len(eligible_run_payloads)
            phase_metadata["driver_count"] = len(driver_rankings)

            artifact = {
                "artifact_type": "sensitivity",
                "schema_version": SENSITIVITY_SCHEMA_VERSION,
                "generator_version": SENSITIVITY_GENERATOR_VERSION,
                "simulation_id": simulation_id,
                "ensemble_id": normalized_ensemble_id,
                "driver_count": len(driver_rankings),
                "driver_rankings": driver_rankings,
                "designed_comparison_count": len(designed_comparisons),
                "designed_comparisons": designed_comparisons,
                "scenario_diversity_context": scenario_diversity_context,
                "methodology": {
                    "analysis_mode": (
                        "hybrid_designed_observational"
                        if designed_comparisons
                        else "observational_resolved_values"
                    ),
                    "driver_source": (
                        "run_manifest.resolved_values with resolved_config.sampled_values "
                        "fallback when available"
                    ),
                    "outcome_source": "metrics.json numeric metric_values",
                    "grouping_policy": "support_aware_driver_bands",
                    "ranking_basis": "support_aware_standardized_effect_sum",
                    "effect_size_definition": "max_group_mean_minus_min_group_mean",
                    "minimum_support_count": self.analytics_policy.MINIMUM_SUPPORT_COUNT,
                    "causal_interpretation": "not_supported",
                    "designed_comparison_source": (
                        "run_manifest.experiment_design_row + run_manifest.structural_resolutions"
                        if designed_comparisons
                        else None
                    ),
                },
                "sample_policy": self.analytics_policy.build_sample_policy(
                    mode="sensitivity",
                    total_runs=total_runs,
                    eligible_run_ids=[payload["run_id"] for payload in eligible_run_payloads],
                    excluded_runs=excluded_runs,
                ),
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
                    "analyzed_runs": len(eligible_run_payloads),
                    "eligible_run_count": len(eligible_run_payloads),
                    "missing_metrics_runs": missing_metrics_runs,
                    "invalid_metrics_runs": invalid_metrics_runs,
                    "degraded_metrics_runs": degraded_metrics_runs,
                    "invalid_manifest_runs": invalid_manifest_runs,
                    "missing_resolved_value_runs": missing_resolved_value_runs,
                    "warnings": warnings,
                    "support_assessment": support_assessment,
                },
                "source_artifacts": {
                    "metrics_files": [
                        payload["metrics_relpath"]
                        for payload in run_payloads
                        if payload["metrics_relpath"]
                    ],
                    "run_manifest_files": [
                        payload["manifest_relpath"]
                        for payload in run_payloads
                        if payload["manifest_relpath"]
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
            manifest_path = os.path.join(run_dir, self.RUN_MANIFEST_FILENAME)
            resolved_config_path = os.path.join(run_dir, self.RESOLVED_CONFIG_FILENAME)

            metrics_payload: Dict[str, Any] | None = None
            if not os.path.exists(metrics_path):
                missing_metrics_runs.append(run_id)
            else:
                try:
                    raw_metrics = self._read_json(metrics_path)
                except (json.JSONDecodeError, OSError):
                    invalid_metrics_runs.append(run_id)
                    raw_metrics = None
                if isinstance(raw_metrics, dict):
                    metrics_payload = raw_metrics
                elif raw_metrics is not None:
                    invalid_metrics_runs.append(run_id)

            manifest_payload: Dict[str, Any] = {}
            manifest_valid = True
            if os.path.exists(manifest_path):
                try:
                    raw_manifest = self._read_json(manifest_path)
                except (json.JSONDecodeError, OSError):
                    invalid_manifest_runs.append(run_id)
                    raw_manifest = None
                if isinstance(raw_manifest, dict):
                    manifest_payload = raw_manifest
                else:
                    manifest_valid = False
                    if raw_manifest is not None:
                        invalid_manifest_runs.append(run_id)
            elif metrics_payload is not None:
                manifest_valid = False
                invalid_manifest_runs.append(run_id)

            resolved_config_payload: Dict[str, Any] = {}
            if os.path.exists(resolved_config_path):
                try:
                    raw_resolved_config = self._read_json(resolved_config_path)
                except (json.JSONDecodeError, OSError):
                    raw_resolved_config = {}
                if isinstance(raw_resolved_config, dict):
                    resolved_config_payload = raw_resolved_config

            if metrics_payload is not None:
                quality_checks = metrics_payload.get("quality_checks", {})
                if (
                    quality_checks.get("status") != "complete"
                    or quality_checks.get("run_status") != "completed"
                ):
                    degraded_metrics_runs.append(run_id)

            experiment_design_row_payload = manifest_payload.get("experiment_design_row", {})
            if not isinstance(experiment_design_row_payload, dict) or not experiment_design_row_payload:
                experiment_design_row_payload = self._read_json_if_exists(
                    os.path.join(run_dir, "experiment_design_row.json")
                ) or {}

            assumption_ledger_payload = manifest_payload.get("assumption_ledger", {})
            if not isinstance(assumption_ledger_payload, dict) or not assumption_ledger_payload:
                raw_assumption_ledger = self._read_json_if_exists(
                    os.path.join(run_dir, "assumption_ledger.json")
                ) or {}
                assumption_ledger_payload = raw_assumption_ledger.get("assumption_ledger", {})
                if not isinstance(assumption_ledger_payload, dict):
                    assumption_ledger_payload = {}

            structural_resolutions = manifest_payload.get("structural_resolutions", [])
            if not isinstance(structural_resolutions, list) or not structural_resolutions:
                structural_resolutions = resolved_config_payload.get("structural_resolutions", [])
            if not isinstance(structural_resolutions, list):
                structural_resolutions = []

            resolved_values: Dict[str, Any] = {}
            if manifest_valid:
                raw_resolved_values = manifest_payload.get("resolved_values", {})
                if not isinstance(raw_resolved_values, dict) or not raw_resolved_values:
                    raw_resolved_values = resolved_config_payload.get("sampled_values", {})
                if isinstance(raw_resolved_values, dict) and raw_resolved_values:
                    resolved_values = raw_resolved_values
                elif metrics_payload is not None:
                    missing_resolved_value_runs.append(run_id)

            run_payloads.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "metrics": metrics_payload,
                    "manifest": manifest_payload,
                    "manifest_valid": manifest_valid,
                    "resolved_config": resolved_config_payload,
                    "resolved_values": resolved_values,
                    "experiment_design_row": experiment_design_row_payload,
                    "assumption_ledger": assumption_ledger_payload,
                    "structural_resolutions": structural_resolutions,
                    "available_numeric_metric_ids": (
                        self.analytics_policy.extract_available_numeric_metric_ids(
                            metrics_payload
                        )
                        if metrics_payload is not None
                        else []
                    ),
                    "metrics_relpath": (
                        os.path.relpath(metrics_path, ensemble_dir)
                        if os.path.exists(metrics_path)
                        else None
                    ),
                    "manifest_relpath": (
                        os.path.relpath(manifest_path, ensemble_dir)
                        if os.path.exists(manifest_path)
                        else None
                    ),
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
            if not isinstance(payload.get("metrics"), dict):
                continue
            numeric_ids = set(payload.get("available_numeric_metric_ids", []))
            if numeric_ids:
                metric_sets.append(numeric_ids)

        if not metric_sets:
            return []
        return sorted(set.intersection(*metric_sets))

    def _compute_metric_stats(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        for metric_id in metric_ids:
            numeric_values = [
                value
                for value in (
                    self.analytics_policy.coerce_numeric_value(
                        payload["metrics"].get("metric_values", {}).get(metric_id)
                    )
                    for payload in run_payloads
                    if isinstance(payload.get("metrics"), dict)
                )
                if value is not None
            ]
            if not numeric_values:
                continue
            mean = sum(numeric_values) / len(numeric_values)
            variance = sum((value - mean) ** 2 for value in numeric_values) / len(
                numeric_values
            )
            stats[metric_id] = {
                "mean": mean,
                "stddev": variance ** 0.5,
            }
        return stats

    def _load_cluster_membership(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Dict[str, str]]:
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        clusters_path = os.path.join(ensemble_dir, "scenario_clusters.json")
        if not os.path.exists(clusters_path):
            return {"run_to_cluster": {}, "cluster_to_runs": {}}
        try:
            payload = self._read_json(clusters_path)
        except (json.JSONDecodeError, OSError):
            return {"run_to_cluster": {}, "cluster_to_runs": {}}

        run_to_cluster: Dict[str, str] = {}
        cluster_to_runs: Dict[str, List[str]] = {}
        for cluster in payload.get("clusters", []):
            cluster_id = str(cluster.get("cluster_id") or "").strip()
            member_run_ids = [
                str(run_id).strip()
                for run_id in cluster.get("member_run_ids", [])
                if str(run_id).strip()
            ]
            if not cluster_id:
                continue
            cluster_to_runs[cluster_id] = member_run_ids
            for run_id in member_run_ids:
                run_to_cluster[run_id] = cluster_id
        return {
            "run_to_cluster": run_to_cluster,
            "cluster_to_runs": cluster_to_runs,
        }

    def _should_withhold_rankings(
        self,
        *,
        cluster_membership: Dict[str, Dict[str, str]],
        scenario_diversity_context: Dict[str, Any],
    ) -> bool:
        warnings = scenario_diversity_context.get("warnings", [])
        if not isinstance(warnings, list):
            return False
        return (
            "limited_template_coverage" in warnings
            and not cluster_membership.get("cluster_to_runs")
        )

    def _load_scenario_diversity_context(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        ensemble_dir = self._get_ensemble_dir(simulation_id, ensemble_id)
        clusters_path = os.path.join(ensemble_dir, "scenario_clusters.json")
        if not os.path.exists(clusters_path):
            return {}
        try:
            payload = self._read_json(clusters_path)
        except (json.JSONDecodeError, OSError):
            return {}

        diagnostics = payload.get("diversity_diagnostics", {})
        if not isinstance(diagnostics, dict) or not diagnostics:
            return {}

        warnings = diagnostics.get("warnings")
        if not isinstance(warnings, list):
            warnings = diagnostics.get("diversity_warnings", [])
        if not isinstance(warnings, list):
            warnings = []

        coverage_metrics = diagnostics.get("coverage_metrics", {})
        if not isinstance(coverage_metrics, dict):
            coverage_metrics = {}

        distance_metrics = diagnostics.get("scenario_distance_metrics")
        if not isinstance(distance_metrics, dict):
            distance_metrics = diagnostics.get("distance_metrics", {})
        if not isinstance(distance_metrics, dict):
            distance_metrics = {}

        support_metrics = diagnostics.get("support_metrics", {})
        if not isinstance(support_metrics, dict):
            support_metrics = {}

        pairwise_distance_mean = distance_metrics.get("pairwise_distance_mean")
        if pairwise_distance_mean is None:
            pairwise_distance_mean = distance_metrics.get("mean_pairwise_distance")

        pairwise_distance_max = distance_metrics.get("pairwise_distance_max")
        if pairwise_distance_max is None:
            pairwise_distance_max = distance_metrics.get("max_pairwise_distance")
        if pairwise_distance_max is None:
            pairwise_distance_max = distance_metrics.get("max_intercluster_distance")

        minimum_support_count = support_metrics.get("minimum_support_count")
        if minimum_support_count is None:
            minimum_support_count = support_metrics.get("minimum_cluster_support")
        if minimum_support_count is None:
            minimum_support_count = support_metrics.get("minimum_cluster_support_count")

        template_coverage_ratio = coverage_metrics.get("template_coverage_ratio")
        if template_coverage_ratio is None:
            template_coverage_ratio = coverage_metrics.get("template_coverage_fraction")

        if (
            template_coverage_ratio is not None
            or pairwise_distance_mean is not None
            or pairwise_distance_max is not None
            or minimum_support_count is not None
        ):
            context: Dict[str, Any] = {
                "warnings": warnings,
            }
            if template_coverage_ratio is not None:
                context["template_coverage_ratio"] = template_coverage_ratio
            if pairwise_distance_mean is not None:
                context["pairwise_distance_mean"] = pairwise_distance_mean
            if pairwise_distance_max is not None:
                context["pairwise_distance_max"] = pairwise_distance_max
            if minimum_support_count is not None:
                context["minimum_support_count"] = minimum_support_count
            return context

        return {
            "coverage_metrics": coverage_metrics,
            "warnings": warnings,
        }

    def _build_driver_rankings(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
        cluster_membership: Dict[str, Dict[str, str]],
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

            driver_kind = self._infer_driver_kind([value for _, value in values_by_run])
            group_payloads = self._group_runs_by_driver_value(values_by_run, driver_kind)
            if len(group_payloads) < 2:
                continue

            metric_impacts = self._build_metric_impacts(
                group_payloads,
                metric_ids,
                metric_stats,
            )
            if not metric_impacts:
                continue

            warnings = []
            if any(not group["minimum_support_met"] for group in group_payloads):
                warnings.append("minimum_support_not_met")

            overall_effect_score = round(
                sum(
                    (
                        impact.get("standardized_effect")
                        if impact.get("standardized_effect") is not None
                        else impact["effect_size"]
                    )
                    * impact.get("support_weight", 1.0)
                    for impact in metric_impacts
                ),
                4,
            )
            top_impact = metric_impacts[0]
            rankings.append(
                {
                    "driver_id": field_path,
                    "field_path": field_path,
                    "driver_kind": driver_kind,
                    "sample_count": len(values_by_run),
                    "distinct_value_count": len(distinct_values),
                    "group_count": len(group_payloads),
                    "minimum_support_count": self.analytics_policy.MINIMUM_SUPPORT_COUNT,
                    "minimum_support_met": all(
                        group["minimum_support_met"] for group in group_payloads
                    ),
                    "overall_effect_score": overall_effect_score,
                    "metric_impacts": metric_impacts,
                    "metric_effects": metric_impacts,
                    "driver_summary": {
                        "semantics": "observational",
                        "ranking_basis": "support_aware_standardized_effect_sum",
                        "top_metric_id": top_impact.get("metric_id"),
                        "top_metric_effect_size": top_impact.get("effect_size"),
                        "top_metric_standardized_effect": top_impact.get(
                            "standardized_effect"
                        ),
                        "support_label": (
                            f"{len(values_by_run)} runs across {len(group_payloads)} groups"
                        ),
                    },
                    "cluster_alignment_hints": self._build_cluster_alignment_hints(
                        group_payloads,
                        cluster_membership,
                    ),
                    "warnings": warnings,
                }
            )

        rankings.sort(
            key=lambda item: (-item["overall_effect_score"], item["field_path"])
        )
        return rankings

    def _annotate_driver_rankings(
        self,
        *,
        driver_rankings: List[Dict[str, Any]],
        quality_warnings: List[str],
    ) -> List[Dict[str, Any]]:
        inherited_warnings = [
            warning
            for warning in quality_warnings
            if warning in {"thin_sample"}
        ]
        for driver in driver_rankings:
            support_assessment = self._build_support_assessment(
                warnings=[*inherited_warnings, *(driver.get("warnings") or [])],
            )
            driver["support_assessment"] = support_assessment
            driver_summary = driver.get("driver_summary", {})
            if isinstance(driver_summary, dict):
                driver_summary["support_assessment"] = support_assessment
            for impact in driver.get("metric_impacts", []):
                impact["support_assessment"] = self._build_support_assessment(
                    warnings=impact.get("warnings") or [],
                )
        return driver_rankings

    def _group_runs_by_driver_value(
        self,
        values_by_run: List[tuple[Dict[str, Any], Any]],
        driver_kind: str,
    ) -> List[Dict[str, Any]]:
        if driver_kind == "numeric":
            numeric_values_by_run = [
                (payload, float(raw_value))
                for payload, raw_value in values_by_run
                if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool)
            ]
            if len(numeric_values_by_run) == len(values_by_run):
                groups = self.analytics_policy.build_numeric_driver_groups(
                    numeric_values_by_run
                )
                if len(groups) >= 2:
                    return groups

        return self.analytics_policy.build_identity_groups(
            values_by_run,
            format_value=self._format_value_label,
            stable_key=self._stable_value_key,
            sort_value=self._sort_value,
        )

    def _build_metric_impacts(
        self,
        group_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        impacts: List[Dict[str, Any]] = []
        for metric_id in metric_ids:
            group_summaries = []
            for group in group_payloads:
                values = [
                    self.analytics_policy.coerce_numeric_value(
                        payload["metrics"].get("metric_values", {}).get(metric_id)
                    )
                    for payload in group["members"]
                ]
                numeric_values = [value for value in values if value is not None]
                if not numeric_values:
                    group_summaries = []
                    break

                group_summary = {
                    "value_label": group["value_label"],
                    "sample_count": len(numeric_values),
                    "support_count": group["support_count"],
                    "support_fraction": group["support_fraction"],
                    "minimum_support_count": group["minimum_support_count"],
                    "minimum_support_met": group["minimum_support_met"],
                    "warnings": list(group.get("warnings", [])),
                    "mean": round(sum(numeric_values) / len(numeric_values), 4),
                    "min": round(min(numeric_values), 4),
                    "max": round(max(numeric_values), 4),
                }
                if group.get("group_kind") == "numeric_band":
                    group_summary["range_min"] = group.get("range_min")
                    group_summary["range_max"] = group.get("range_max")
                group_summaries.append(group_summary)

            if len(group_summaries) < 2:
                continue

            ordered_means = [group["mean"] for group in group_summaries]
            effect_size = round(max(ordered_means) - min(ordered_means), 4)
            low_group = min(
                group_summaries,
                key=lambda item: (item["mean"], item["value_label"]),
            )
            high_group = max(
                group_summaries,
                key=lambda item: (item["mean"], item["value_label"]),
            )
            baseline_mean = low_group["mean"]
            relative_effect = None
            if baseline_mean not in (None, 0):
                relative_effect = round(effect_size / abs(baseline_mean), 4)
            metric_stddev = metric_stats.get(metric_id, {}).get("stddev")
            standardized_effect = None
            if metric_stddev not in (None, 0):
                standardized_effect = round(effect_size / metric_stddev, 4)
            support_weight = round(
                min(
                    (
                        group.get("support_fraction")
                        for group in group_summaries
                        if isinstance(group.get("support_fraction"), (int, float))
                    ),
                    default=1.0,
                ),
                4,
            )

            impact_warnings = []
            if any(not group["minimum_support_met"] for group in group_summaries):
                impact_warnings.append("minimum_support_not_met")

            impacts.append(
                {
                    "metric_id": metric_id,
                    "effect_size": effect_size,
                    "relative_effect": relative_effect,
                    "standardized_effect": standardized_effect,
                    "support_weight": support_weight,
                    "strongest_groups": [
                        low_group["value_label"],
                        high_group["value_label"],
                    ],
                    "group_summaries": group_summaries,
                    "warnings": impact_warnings,
                }
            )

        impacts.sort(
            key=lambda item: (-item["effect_size"], item["metric_id"])
        )
        return impacts

    def _build_cluster_alignment_hints(
        self,
        group_payloads: List[Dict[str, Any]],
        cluster_membership: Dict[str, Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        run_to_cluster = cluster_membership.get("run_to_cluster", {})
        cluster_to_runs = cluster_membership.get("cluster_to_runs", {})
        if not run_to_cluster or not cluster_to_runs:
            return []

        hints: List[Dict[str, Any]] = []
        for group in group_payloads:
            group_run_ids = [
                str(member.get("run_id")).strip()
                for member in group.get("members", [])
                if str(member.get("run_id") or "").strip()
            ]
            if not group_run_ids:
                continue
            counts: Counter[str] = Counter(
                run_to_cluster[run_id]
                for run_id in group_run_ids
                if run_id in run_to_cluster
            )
            if not counts:
                continue
            cluster_id, matched_run_count = sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            alignment_fraction = matched_run_count / len(group_run_ids)
            if alignment_fraction < 0.75:
                continue
            hints.append(
                {
                    "cluster_id": cluster_id,
                    "group_value_label": group.get("value_label"),
                    "matched_run_count": matched_run_count,
                    "alignment_fraction": round(alignment_fraction, 4),
                    "cluster_run_count": len(cluster_to_runs.get(cluster_id, [])),
                }
            )

        return hints

    def _build_designed_comparisons(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        if not run_payloads or not metric_ids:
            return []

        assignments: Dict[str, Dict[str, Any]] = {}
        for payload in run_payloads:
            structural_items = payload.get("structural_resolutions") or []
            if not structural_items:
                structural_items = (payload.get("assumption_ledger") or {}).get(
                    "structural_uncertainties", []
                )
            if not isinstance(structural_items, list):
                continue
            for item in structural_items:
                if not isinstance(item, dict):
                    continue
                uncertainty_id = str(item.get("uncertainty_id") or "").strip()
                option_id = str(item.get("option_id") or "").strip()
                option_label = str(item.get("option_label") or option_id).strip()
                if not uncertainty_id or not option_id:
                    continue
                bucket = assignments.setdefault(
                    uncertainty_id,
                    {
                        "label": str(item.get("label") or uncertainty_id).strip() or uncertainty_id,
                        "groups": {},
                    },
                )
                bucket["groups"].setdefault(
                    option_id,
                    {
                        "option_id": option_id,
                        "option_label": option_label,
                        "members": [],
                    },
                )["members"].append(payload)

        comparisons: List[Dict[str, Any]] = []
        for uncertainty_id, bucket in sorted(assignments.items()):
            groups = bucket["groups"]
            if len(groups) < 2:
                continue
            total_members = sum(len(group["members"]) for group in groups.values())
            group_payloads = []
            for option_id, group in sorted(groups.items()):
                support = self.analytics_policy.build_support_metadata(
                    support_count=len(group["members"]),
                    total_count=total_members,
                    include_thin_sample=False,
                )
                group_payloads.append(
                    {
                        "group_kind": "structural_option",
                        "value_label": group["option_label"],
                        "option_id": option_id,
                        "option_label": group["option_label"],
                        "members": list(group["members"]),
                        "support_count": support["support_count"],
                        "support_fraction": support["support_fraction"],
                        "minimum_support_count": support["minimum_support_count"],
                        "minimum_support_met": support["minimum_support_met"],
                        "warnings": support["warnings"],
                    }
                )
            metric_impacts = self._build_metric_impacts(
                group_payloads,
                metric_ids,
                metric_stats,
            )
            if not metric_impacts:
                continue
            warnings = []
            if any(not group["minimum_support_met"] for group in group_payloads):
                warnings.append("minimum_support_not_met")
            overall_effect_score = round(
                sum(
                    (
                        impact.get("standardized_effect")
                        if impact.get("standardized_effect") is not None
                        else impact["effect_size"]
                    )
                    * impact.get("support_weight", 1.0)
                    for impact in metric_impacts
                ),
                4,
            )
            comparison = {
                "comparison_id": f"structural_uncertainty:{uncertainty_id}",
                "comparison_kind": "structural_uncertainty",
                "uncertainty_id": uncertainty_id,
                "comparison_label": bucket["label"],
                "sample_count": total_members,
                "group_count": len(group_payloads),
                "overall_effect_score": overall_effect_score,
                "group_summaries": [
                    {
                        "option_id": group["option_id"],
                        "option_label": group["option_label"],
                        "support_count": group["support_count"],
                        "support_fraction": group["support_fraction"],
                        "minimum_support_count": group["minimum_support_count"],
                        "minimum_support_met": group["minimum_support_met"],
                        "warnings": list(group.get("warnings", [])),
                    }
                    for group in group_payloads
                ],
                "metric_impacts": metric_impacts,
                "comparison_summary": {
                    "semantics": "designed_comparison",
                    "design_source": "structural_assignment",
                    "top_metric_id": metric_impacts[0].get("metric_id"),
                    "top_metric_effect_size": metric_impacts[0].get("effect_size"),
                    "top_metric_standardized_effect": metric_impacts[0].get(
                        "standardized_effect"
                    ),
                },
                "warnings": warnings,
                "support_assessment": self._build_support_assessment(warnings=warnings),
            }
            comparisons.append(comparison)

        comparisons.sort(
            key=lambda item: (-item["overall_effect_score"], item["uncertainty_id"])
        )
        return comparisons

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
        has_designed_comparisons: bool,
        scenario_diversity_context: Dict[str, Any],
    ) -> List[str]:
        warnings = [] if has_designed_comparisons else ["observational_only"]
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
        if scenario_diversity_context.get("warnings"):
            warnings.append("limited_scenario_diversity")
        return warnings

    def _build_support_assessment(
        self,
        *,
        warnings: List[str],
    ) -> Dict[str, Any]:
        relevant_warnings = [
            warning
            for warning in self._dedupe_warnings(warnings)
            if warning in {"thin_sample", "minimum_support_not_met"}
        ]
        if "minimum_support_not_met" in relevant_warnings:
            return {
                "status": "insufficient_support",
                "label": "Insufficient support",
                "downgraded": True,
                "decision_support_ready": False,
                "reason": "Minimum support was not met, so this observational ranking cannot support strong driver language.",
                "warnings": ["minimum_support_not_met"],
            }
        if "thin_sample" in relevant_warnings:
            return {
                "status": "descriptive_only",
                "label": "Descriptive only",
                "downgraded": True,
                "decision_support_ready": False,
                "reason": "Thin-sample warnings limit observational rankings to descriptive use only.",
                "warnings": ["thin_sample"],
            }
        return {
            "status": "observational_only",
            "label": "Observational only",
            "downgraded": False,
            "decision_support_ready": False,
            "reason": "",
            "warnings": [],
        }

    def _dedupe_warnings(self, warnings: List[str]) -> List[str]:
        deduped: List[str] = []
        for warning in warnings:
            if warning and warning not in deduped:
                deduped.append(warning)
        return deduped

    def _derive_generated_at(self, run_payloads: List[Dict[str, Any]]) -> str:
        timestamps = []
        for payload in run_payloads:
            metrics_timestamp = (
                payload["metrics"].get("extracted_at")
                if isinstance(payload.get("metrics"), dict)
                else None
            )
            manifest_timestamp = payload.get("manifest", {}).get("generated_at")
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
        if values and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in values
        ):
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

    def _read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_json_if_exists(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            payload = self._read_json(path)
        except (json.JSONDecodeError, OSError):
            return None
        return payload if isinstance(payload, dict) else None

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
