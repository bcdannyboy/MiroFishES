"""
Deterministic scenario clustering for stored probabilistic ensemble runs.

This slice stays intentionally narrow:
- it clusters only on structured run-level metric values,
- it uses prototype runs and warning flags instead of narrative summaries,
- it persists a reproducible `scenario_clusters.json` artifact for stored runs only.

It does not claim calibration, causal attribution, or richer report semantics.
"""

from __future__ import annotations

from collections import Counter
import json
import math
import os
import re
from typing import Any, Dict, List, Optional

from ..config import Config
from .analytics_policy import AnalyticsPolicy
from .phase_timing import PhaseTimingRecorder


CLUSTERS_SCHEMA_VERSION = "probabilistic.clusters.v2"
CLUSTERS_GENERATOR_VERSION = "probabilistic.clusters.generator.v2"


class _AliasLookupDict(dict):
    """Dictionary with read-only alias support without persisting alias keys."""

    def __init__(self, *args: Any, aliases: Optional[Dict[str, str]] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._aliases = aliases or {}

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(self._aliases.get(key, key))

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(self._aliases.get(key, key), default)


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
    EXPERIMENT_DESIGN_FILENAME = "experiment_design.json"
    PHASE_TIMINGS_FILENAME = "ensemble_phase_timings.json"
    THIN_SAMPLE_WARNING_THRESHOLD = 5
    CLUSTER_RADIUS_THRESHOLD = AnalyticsPolicy.DEFAULT_CLUSTER_RADIUS
    DISTINGUISHING_METRIC_LIMIT = 3

    _RUN_DIR_RE = re.compile(r"^run_(\d{4})$")

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        self.analytics_policy = AnalyticsPolicy()

    def get_scenario_clusters(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        """Build and persist one scenario clustering artifact for the ensemble."""
        normalized_ensemble_id = self._normalize_ensemble_id(ensemble_id)
        ensemble_dir = self._get_ensemble_dir(simulation_id, normalized_ensemble_id)
        phase_timing = PhaseTimingRecorder(
            artifact_path=os.path.join(ensemble_dir, self.PHASE_TIMINGS_FILENAME),
            scope_kind="ensemble",
            scope_id=f"{simulation_id}::{normalized_ensemble_id}",
        )
        with phase_timing.measure_phase("clustering", metadata={}) as phase_metadata:
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
            eligible_run_payloads = []
            excluded_runs = []
            for payload in run_payloads:
                eligibility = self.analytics_policy.assess_run(
                    mode="scenario",
                    run_payload={
                        "run_id": payload["run_id"],
                        "metrics_payload": payload.get("metrics"),
                        "manifest_valid": payload.get("manifest_valid", True),
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
            expected_metric_ids = set(ensemble_state.get("outcome_metric_ids", [])) or set(
                observed_numeric_metric_ids
            )
            partial_feature_space = bool(metric_ids) and (
                set(metric_ids) != expected_metric_ids
            )
            metric_stats = self._compute_metric_stats(eligible_run_payloads, metric_ids)
            clusters_by_members = self._group_runs_into_clusters(
                eligible_run_payloads,
                metric_ids,
                metric_stats,
            )
            clustered_runs = sum(len(items) for items in clusters_by_members)
            warnings = self._build_quality_warnings(
                total_runs=total_runs,
                eligible_run_count=len(eligible_run_payloads),
                clustered_runs=clustered_runs,
                cluster_count=len(clusters_by_members),
                missing_metrics_runs=missing_metrics_runs,
                invalid_metrics_runs=invalid_metrics_runs,
                degraded_metrics_runs=degraded_metrics_runs,
                invalid_manifest_runs=invalid_manifest_runs,
                metric_stats=metric_stats,
                metric_ids=metric_ids,
                partial_feature_space=partial_feature_space,
                clusters=clusters_by_members,
            )
            support_assessment = self._build_cluster_support_assessment(
                warnings=warnings,
            )

            clusters = self._build_cluster_payloads(
                clusters_by_members=clusters_by_members,
                metric_ids=metric_ids,
                metric_stats=metric_stats,
                total_runs=total_runs,
                quality_warnings=warnings,
            )
            self._annotate_cluster_comparison_hints(clusters)
            diversity_diagnostics = self._build_diversity_diagnostics(
                ensemble_dir=ensemble_dir,
                eligible_run_payloads=eligible_run_payloads,
                clusters=clusters,
                metric_ids=metric_ids,
            )
            self._apply_planned_coverage_share_adjustment(
                clusters=clusters,
                diversity_diagnostics=diversity_diagnostics,
            )

            phase_metadata["total_runs"] = total_runs
            phase_metadata["eligible_run_count"] = len(eligible_run_payloads)
            phase_metadata["cluster_count"] = len(clusters)

            artifact = {
                "artifact_type": "scenario_clusters",
                "schema_version": CLUSTERS_SCHEMA_VERSION,
                "generator_version": CLUSTERS_GENERATOR_VERSION,
                "simulation_id": simulation_id,
                "ensemble_id": normalized_ensemble_id,
                "probability_boundary_note": (
                    "Scenario-family share is an observed run share inside this stored ensemble, not a calibrated real-world probability."
                ),
                "cluster_count": len(clusters),
                "clusters": clusters,
                "diversity_diagnostics": diversity_diagnostics,
                "feature_vector_schema": {
                    "metric_ids": metric_ids,
                    "standardization": "zscore",
                    "cluster_method": "medoid_radius",
                    "distance_metric": "euclidean",
                    "radius_threshold": self.CLUSTER_RADIUS_THRESHOLD,
                    "source": "metrics.json",
                },
                "sample_policy": self.analytics_policy.build_sample_policy(
                    mode="scenario",
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
                        or not metric_ids
                        or partial_feature_space
                    )
                    else "complete",
                    "total_runs": total_runs,
                    "runs_with_metrics": len(run_payloads),
                    "eligible_run_count": len(eligible_run_payloads),
                    "clustered_runs": clustered_runs,
                    "missing_metrics_runs": missing_metrics_runs,
                    "invalid_metrics_runs": invalid_metrics_runs,
                    "degraded_metrics_runs": degraded_metrics_runs,
                    "invalid_manifest_runs": invalid_manifest_runs,
                    "warnings": warnings,
                    "support_assessment": support_assessment,
                },
                "source_artifacts": {
                    "metrics_files": [
                        payload["metrics_relpath"] for payload in run_payloads
                        if payload["metrics_relpath"]
                    ],
                    "run_manifest_files": [
                        payload["manifest_relpath"] for payload in run_payloads
                        if payload["manifest_relpath"]
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
            manifest_path = os.path.join(run_dir, self.RUN_MANIFEST_FILENAME)
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

            if metrics_payload is not None:
                quality_checks = metrics_payload.get("quality_checks", {})
                if (
                    quality_checks.get("status") != "complete"
                    or quality_checks.get("run_status") != "completed"
                ):
                    degraded_metrics_runs.append(run_id)

            run_payloads.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "metrics": metrics_payload,
                    "manifest": manifest_payload,
                    "manifest_valid": manifest_valid,
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
            if not isinstance(payload.get("metrics"), dict):
                continue
            numeric_ids = set(payload.get("available_numeric_metric_ids", []))
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
            observed.update(payload.get("available_numeric_metric_ids", []))
        return sorted(observed)

    def _compute_metric_stats(
        self,
        run_payloads: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        for metric_id in metric_ids:
            values = [
                self.analytics_policy.coerce_numeric_value(
                    payload["metrics"].get("metric_values", {}).get(metric_id)
                )
                for payload in run_payloads
                if isinstance(payload.get("metrics"), dict)
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
    ) -> List[List[Dict[str, Any]]]:
        if not metric_ids:
            return []
        enriched_payloads: List[Dict[str, Any]] = []
        for payload in run_payloads:
            vector: Dict[str, float] = {}
            standardized: Dict[str, float] = {}
            missing_metric = False
            for metric_id in metric_ids:
                value = self.analytics_policy.coerce_numeric_value(
                    payload["metrics"].get("metric_values", {}).get(metric_id)
                )
                if value is None:
                    missing_metric = True
                    break
                vector[metric_id] = value
                z_score = self._compute_z_score(value, metric_stats.get(metric_id, {}))
                standardized[metric_id] = z_score

            if missing_metric:
                continue

            enriched = dict(payload)
            enriched["feature_vector"] = vector
            enriched["standardized_vector"] = standardized
            enriched_payloads.append(enriched)

        unassigned = sorted(enriched_payloads, key=lambda item: item["run_id"])
        clusters: List[List[Dict[str, Any]]] = []
        while unassigned:
            best_members: List[Dict[str, Any]] = []
            best_score: tuple[int, float, str] | None = None
            for candidate in unassigned:
                members = [
                    other
                    for other in unassigned
                    if self._distance_to_centroid(
                        other["standardized_vector"],
                        candidate["standardized_vector"],
                    )
                    <= self.CLUSTER_RADIUS_THRESHOLD
                ]
                mean_distance = sum(
                    self._distance_to_centroid(
                        member["standardized_vector"],
                        candidate["standardized_vector"],
                    )
                    for member in members
                ) / len(members)
                score = (-len(members), mean_distance, candidate["run_id"])
                if best_score is None or score < best_score:
                    best_score = score
                    best_members = members
            member_ids = {member["run_id"] for member in best_members}
            clusters.append(sorted(best_members, key=lambda item: item["run_id"]))
            unassigned = [
                payload for payload in unassigned if payload["run_id"] not in member_ids
            ]

        return clusters

    def _build_diversity_diagnostics(
        self,
        *,
        ensemble_dir: str,
        eligible_run_payloads: List[Dict[str, Any]],
        clusters: List[Dict[str, Any]],
        metric_ids: List[str],
    ) -> _AliasLookupDict:
        experiment_design = self._load_experiment_design(ensemble_dir)
        observed = self._collect_observed_scenario_metadata(eligible_run_payloads)
        coverage_metrics = self._build_coverage_metrics(
            observed=observed,
            experiment_design=experiment_design,
            metric_ids=metric_ids,
        )
        scenario_distance_metrics = self._build_scenario_distance_metrics(
            clusters=clusters,
            include_pairwise_aliases=bool(experiment_design) or bool(observed["coverage_tags"]) or bool(observed["exogenous_event_ids"]),
        )
        support_metrics = self._build_diversity_support_metrics(
            clusters=clusters,
            observed=observed,
            include_extended_fields=bool(experiment_design) or bool(observed["coverage_tags"]) or bool(observed["exogenous_event_ids"]),
        )
        diversity_warnings = self._build_diversity_warnings(
            observed=observed,
            experiment_design=experiment_design,
            support_metrics=support_metrics,
        )
        return _AliasLookupDict(
            {
                "coverage_metrics": coverage_metrics,
                "scenario_distance_metrics": scenario_distance_metrics,
                "support_metrics": support_metrics,
                "diversity_warnings": diversity_warnings,
            },
            aliases={
                "warnings": "diversity_warnings",
                "distance_metrics": "scenario_distance_metrics",
            },
        )

    def _load_experiment_design(self, ensemble_dir: str) -> Dict[str, Any]:
        path = os.path.join(ensemble_dir, self.EXPERIMENT_DESIGN_FILENAME)
        if not os.path.exists(path):
            return {}
        try:
            payload = self._read_json(path)
        except (json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _collect_observed_scenario_metadata(
        self,
        run_payloads: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        template_support_counts: Counter[str] = Counter()
        coverage_tags: set[str] = set()
        exogenous_event_ids: set[str] = set()
        run_templates: Dict[str, List[str]] = {}
        run_coverage_tags: Dict[str, List[str]] = {}

        for payload in run_payloads:
            run_id = str(payload.get("run_id") or "").strip()
            assumption_ledger = payload.get("manifest", {}).get("assumption_ledger", {})
            templates = assumption_ledger.get("applied_templates")
            if not isinstance(templates, list) or not templates:
                templates = assumption_ledger.get("scenario_template_ids", [])
            normalized_templates = sorted(
                {
                    str(template_id).strip()
                    for template_id in templates
                    if str(template_id or "").strip()
                }
            )
            for template_id in normalized_templates:
                template_support_counts[template_id] += 1

            normalized_tags = sorted(
                {
                    str(tag).strip()
                    for tag in assumption_ledger.get("scenario_coverage_tags", [])
                    if str(tag or "").strip()
                }
            )
            coverage_tags.update(normalized_tags)

            normalized_event_ids = sorted(
                {
                    str(event_id).strip()
                    for event_id in assumption_ledger.get("applied_exogenous_event_ids", [])
                    if str(event_id or "").strip()
                }
            )
            exogenous_event_ids.update(normalized_event_ids)

            if run_id:
                run_templates[run_id] = normalized_templates
                run_coverage_tags[run_id] = normalized_tags

        return {
            "template_support_counts": {
                template_id: template_support_counts[template_id]
                for template_id in sorted(template_support_counts)
            },
            "coverage_tags": sorted(coverage_tags),
            "exogenous_event_ids": sorted(exogenous_event_ids),
            "run_templates": run_templates,
            "run_coverage_tags": run_coverage_tags,
        }

    def _build_coverage_metrics(
        self,
        *,
        observed: Dict[str, Any],
        experiment_design: Dict[str, Any],
        metric_ids: List[str],
    ) -> _AliasLookupDict:
        observed_template_counts = observed["template_support_counts"]
        observed_template_ids = list(observed_template_counts.keys())
        observed_coverage_tags = observed["coverage_tags"]
        observed_event_ids = observed["exogenous_event_ids"]

        planned_template_ids = self._collect_planned_template_ids(experiment_design)
        planned_coverage_tag_count = self._collect_planned_coverage_tag_count(experiment_design)

        if planned_template_ids:
            metrics: Dict[str, Any] = {
                "planned_template_count": len(planned_template_ids),
                "observed_template_count": len(observed_template_ids),
                "planned_templates_missing_from_observed": [
                    template_id
                    for template_id in planned_template_ids
                    if template_id not in observed_template_counts
                ],
                "template_coverage_ratio": (
                    len([template_id for template_id in planned_template_ids if template_id in observed_template_counts])
                    / len(planned_template_ids)
                )
                if planned_template_ids
                else 0.0,
                "observed_template_counts": observed_template_counts,
            }
            if planned_coverage_tag_count:
                metrics["planned_coverage_tag_count"] = planned_coverage_tag_count
                metrics["observed_coverage_tag_count"] = len(observed_coverage_tags)
                metrics["coverage_tag_coverage_ratio"] = (
                    min(len(observed_coverage_tags), planned_coverage_tag_count)
                    / planned_coverage_tag_count
                )
            if observed_event_ids:
                metrics["observed_exogenous_event_count"] = len(observed_event_ids)
            return _AliasLookupDict(
                metrics,
                aliases={
                    "template_coverage_fraction": "template_coverage_ratio",
                    "coverage_tag_fraction": "coverage_tag_coverage_ratio",
                },
            )

        metrics = {
            "numeric_dimension_coverage_ratio": 1.0 if metric_ids else 0.0,
            "scenario_template_count": len(observed_template_ids),
            "substantive_template_count": len(observed_template_ids),
            "substantive_template_ratio": (
                round(len(observed_template_ids) / len(observed_template_ids), 4)
                if observed_template_ids
                else 0.0
            ),
            "template_coverage_ratio": 1.0 if observed_template_ids else 0.0,
            "template_support_counts": observed_template_counts,
        }
        if observed_coverage_tags or observed_event_ids:
            metrics["observed_template_count"] = len(observed_template_ids)
            metrics["observed_coverage_tag_count"] = len(observed_coverage_tags)
            metrics["observed_exogenous_event_count"] = len(observed_event_ids)
        return _AliasLookupDict(
            metrics,
            aliases={
                "template_coverage_fraction": "template_coverage_ratio",
                "coverage_tag_fraction": "coverage_tag_coverage_ratio",
            },
        )

    def _collect_planned_template_ids(self, experiment_design: Dict[str, Any]) -> List[str]:
        template_ids = [
            str(template_id).strip()
            for template_id in experiment_design.get("scenario_template_ids", [])
            if str(template_id or "").strip()
        ]
        if template_ids:
            return sorted(dict.fromkeys(template_ids))
        discovered: List[str] = []
        for row in experiment_design.get("rows", []):
            if not isinstance(row, dict):
                continue
            for template_id in row.get("scenario_template_ids", []):
                normalized = str(template_id or "").strip()
                if normalized and normalized not in discovered:
                    discovered.append(normalized)
        return discovered

    def _collect_planned_coverage_tag_count(self, experiment_design: Dict[str, Any]) -> int:
        raw_count = experiment_design.get("coverage_metrics", {}).get("planned_coverage_tag_count")
        if isinstance(raw_count, int):
            return raw_count
        coverage_tags: set[str] = set()
        for row in experiment_design.get("rows", []):
            if not isinstance(row, dict):
                continue
            for tag in row.get("scenario_coverage_tags", []):
                normalized = str(tag or "").strip()
                if normalized:
                    coverage_tags.add(normalized)
        return len(coverage_tags)

    def _build_scenario_distance_metrics(
        self,
        *,
        clusters: List[Dict[str, Any]],
        include_pairwise_aliases: bool,
    ) -> _AliasLookupDict:
        distances = []
        for index, cluster in enumerate(clusters):
            for other in clusters[index + 1 :]:
                distances.append(
                    self._cluster_signature_distance(cluster, other)
                )

        if include_pairwise_aliases:
            metrics: Dict[str, Any] = {
                "pairwise_distance_mean": round(sum(distances) / len(distances), 4)
                if distances
                else 0.0,
                "pairwise_distance_max": round(max(distances), 4) if distances else 0.0,
                "pairwise_distance_min": round(min(distances), 4) if distances else 0.0,
                "max_intercluster_distance": round(max(distances), 4) if distances else 0.0,
            }
            return _AliasLookupDict(
                metrics,
                aliases={
                    "mean_pairwise_distance": "pairwise_distance_mean",
                    "max_pairwise_distance": "pairwise_distance_max",
                    "min_pairwise_distance": "pairwise_distance_min",
                },
            )

        metrics = {
            "distance_metric": "cluster_prototype_euclidean",
            "max_cluster_prototype_distance": round(max(distances), 4) if distances else 0.0,
            "mean_cluster_prototype_distance": round(sum(distances) / len(distances), 4)
            if distances
            else 0.0,
            "min_cluster_prototype_distance": round(min(distances), 4) if distances else 0.0,
            "pair_count": len(distances),
        }
        return _AliasLookupDict(metrics)

    def _cluster_signature_distance(
        self,
        cluster: Dict[str, Any],
        other: Dict[str, Any],
    ) -> float:
        differing_metric_directions = 0
        cluster_metric_directions = {
            item.get("metric_id"): item.get("direction")
            for item in cluster.get("distinguishing_metrics", [])
            if item.get("metric_id")
        }
        other_metric_directions = {
            item.get("metric_id"): item.get("direction")
            for item in other.get("distinguishing_metrics", [])
            if item.get("metric_id")
        }
        for metric_id in sorted(set(cluster_metric_directions) | set(other_metric_directions)):
            if cluster_metric_directions.get(metric_id) != other_metric_directions.get(metric_id):
                differing_metric_directions += 1

        cluster_templates = set((cluster.get("assumption_template_counts") or {}).keys())
        other_templates = set((other.get("assumption_template_counts") or {}).keys())
        template_mismatch = 1.0 if cluster_templates != other_templates else 0.0

        metric_component = 2.0 * differing_metric_directions
        template_component = 2.0 * template_mismatch
        return math.sqrt((metric_component ** 2) + (template_component ** 2))

    def _build_diversity_support_metrics(
        self,
        *,
        clusters: List[Dict[str, Any]],
        observed: Dict[str, Any],
        include_extended_fields: bool,
    ) -> _AliasLookupDict:
        cluster_support_counts = {
            cluster["cluster_id"]: cluster.get("support_count", 0)
            for cluster in clusters
        }
        support_counts = list(cluster_support_counts.values())
        if include_extended_fields:
            template_singleton_count = sum(
                1
                for count in observed["template_support_counts"].values()
                if count <= 1
            )
            metrics = {
                "cluster_count": len(clusters),
                "minimum_support_count": min(support_counts) if support_counts else 0,
                "singleton_cluster_count": max(
                    sum(1 for count in support_counts if count <= 1),
                    template_singleton_count,
                ),
            }
            return _AliasLookupDict(
                metrics,
                aliases={
                    "minimum_cluster_support": "minimum_support_count",
                    "low_support_cluster_count": "singleton_cluster_count",
                },
            )

        metrics = {
            "cluster_support_counts": cluster_support_counts,
            "maximum_cluster_support_count": max(support_counts) if support_counts else 0,
            "minimum_cluster_support_count": min(support_counts) if support_counts else 0,
        }
        return _AliasLookupDict(metrics)

    def _build_diversity_warnings(
        self,
        *,
        observed: Dict[str, Any],
        experiment_design: Dict[str, Any],
        support_metrics: Dict[str, Any],
    ) -> List[str]:
        warnings: List[str] = []
        planned_template_ids = self._collect_planned_template_ids(experiment_design)
        observed_template_ids = set(observed["template_support_counts"].keys())
        if planned_template_ids and len(observed_template_ids) < len(planned_template_ids):
            warnings.append("limited_template_coverage")

        planned_coverage_tag_count = self._collect_planned_coverage_tag_count(experiment_design)
        if planned_coverage_tag_count and len(observed["coverage_tags"]) < planned_coverage_tag_count:
            warnings.append("limited_coverage_tag_span")

        if len(observed_template_ids) < 2:
            warnings.append("narrow_template_coverage")

        if support_metrics.get("singleton_cluster_count", 0) > 0:
            warnings.append("low_scenario_support")

        if experiment_design:
            planned_rows = {
                str(row.get("run_id") or "").strip(): {
                    "templates": sorted(
                        {
                            str(template_id).strip()
                            for template_id in row.get("scenario_template_ids", [])
                            if str(template_id or "").strip()
                        }
                    ),
                    "coverage_tags": sorted(
                        {
                            str(tag).strip()
                            for tag in row.get("scenario_coverage_tags", [])
                            if str(tag or "").strip()
                        }
                    ),
                }
                for row in experiment_design.get("rows", [])
                if isinstance(row, dict) and str(row.get("run_id") or "").strip()
            }
            for run_id, planned in planned_rows.items():
                observed_templates = observed["run_templates"].get(run_id, [])
                observed_tags = observed["run_coverage_tags"].get(run_id, [])
                if planned["templates"] and observed_templates and planned["templates"] != observed_templates:
                    warnings.append("planned_diversity_drift")
                    break
                if planned["coverage_tags"] and observed_tags and planned["coverage_tags"] != observed_tags:
                    warnings.append("planned_diversity_drift")
                    break

        return self._dedupe_warnings(warnings)

    def _apply_planned_coverage_share_adjustment(
        self,
        *,
        clusters: List[Dict[str, Any]],
        diversity_diagnostics: Dict[str, Any],
    ) -> None:
        coverage_metrics = diversity_diagnostics.get("coverage_metrics", {})
        if not isinstance(coverage_metrics, dict):
            return
        planned_template_count = coverage_metrics.get("planned_template_count")
        if not isinstance(planned_template_count, int) or planned_template_count <= 0:
            return
        for cluster in clusters:
            support_count = cluster.get("support_count")
            if isinstance(support_count, (int, float)):
                cluster["planned_template_support_ratio"] = (
                    support_count / planned_template_count
                )

    def _build_quality_warnings(
        self,
        *,
        total_runs: int,
        eligible_run_count: int,
        clustered_runs: int,
        cluster_count: int,
        missing_metrics_runs: List[str],
        invalid_metrics_runs: List[str],
        degraded_metrics_runs: List[str],
        invalid_manifest_runs: List[str],
        metric_stats: Dict[str, Dict[str, float]],
        metric_ids: List[str],
        partial_feature_space: bool,
        clusters: List[List[Dict[str, Any]]],
    ) -> List[str]:
        warnings: List[str] = []
        if eligible_run_count < self.THIN_SAMPLE_WARNING_THRESHOLD:
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
            eligible_run_count < self.THIN_SAMPLE_WARNING_THRESHOLD
            or total_runs == 0
            or cluster_count <= 1
            or not metric_ids
            or any(stat.get("stddev", 0.0) == 0.0 for stat in metric_stats.values())
            or any(len(cluster) < self.analytics_policy.MINIMUM_SUPPORT_COUNT for cluster in clusters)
        ):
            warnings.append("low_confidence")
        return warnings

    def _build_cluster_payloads(
        self,
        *,
        clusters_by_members: List[List[Dict[str, Any]]],
        metric_ids: List[str],
        metric_stats: Dict[str, Dict[str, float]],
        total_runs: int,
        quality_warnings: List[str],
    ) -> List[Dict[str, Any]]:
        clusters: List[Dict[str, Any]] = []
        overall_means = {
            metric_id: stat.get("mean")
            for metric_id, stat in metric_stats.items()
        }
        for index, members in enumerate(clusters_by_members, start=1):
            centroid = {
                metric_id: sum(
                    member["feature_vector"][metric_id] for member in members
                )
                / len(members)
                for metric_id in metric_ids
            }
            prototype = self._select_medoid(members)
            support = self.analytics_policy.build_support_metadata(
                support_count=len(members),
                total_count=total_runs,
                include_thin_sample=False,
            )
            member_distances = [
                (
                    member["run_id"],
                    self._distance_to_centroid(
                        member["standardized_vector"],
                        prototype["standardized_vector"],
                    ),
                )
                for member in members
            ]
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
            elif (
                len(members) > 1
                and max((distance for _, distance in member_distances), default=0.0)
                <= (self.CLUSTER_RADIUS_THRESHOLD / 2)
            ):
                cluster_warnings.append("low_metric_variance")
            for warning in support["warnings"]:
                if warning not in cluster_warnings:
                    cluster_warnings.append(warning)
            inherited_warnings = [
                warning
                for warning in quality_warnings
                if warning in {"thin_sample", "low_confidence"}
            ]
            support_assessment = self._build_cluster_support_assessment(
                warnings=[*inherited_warnings, *cluster_warnings],
            )

            assumption_template_counts = self._count_assumption_templates(members)
            representative_run_ids = self._select_representative_run_ids(
                members,
                member_distances,
            )
            family_signature = self._build_family_signature(
                distinguishing_metrics=distinguishing_metrics,
                assumption_template_counts=assumption_template_counts,
                prototype_top_topics=prototype["metrics"].get("top_topics", []),
            )
            family_label = self._build_family_label(
                cluster_id=f"cluster_{index:04d}",
                family_signature=family_signature,
            )
            family_summary = self._build_family_summary(
                family_signature=family_signature,
                family_label=family_label,
                run_count=len(members),
                total_runs=total_runs,
                support_assessment=support_assessment,
            )

            clusters.append(
                {
                    "cluster_id": f"cluster_{index:04d}",
                    "family_label": family_label,
                    "family_summary": family_summary,
                    "run_count": len(members),
                    "support_count": support["support_count"],
                    "support_fraction": support["support_fraction"],
                    "minimum_support_count": support["minimum_support_count"],
                    "minimum_support_met": support["minimum_support_met"],
                    "observed_run_share": len(members) / total_runs if total_runs else 0.0,
                    "share_semantics": "observed_run_share",
                    "prototype_run_id": prototype["run_id"],
                    "representative_run_ids": representative_run_ids,
                    "member_run_ids": [member["run_id"] for member in members],
                    "assumption_template_counts": assumption_template_counts,
                    "family_signature": family_signature,
                    "feature_signature": {
                        metric_id: round(
                            prototype["standardized_vector"].get(metric_id, 0.0),
                            4,
                        )
                        for metric_id in metric_ids
                    },
                    "centroid": centroid,
                    "dispersion": {
                        "mean_distance_to_medoid": (
                            sum(distance for _, distance in member_distances)
                            / len(member_distances)
                            if member_distances
                            else 0.0
                        ),
                        "max_distance_to_medoid": max(
                            (distance for _, distance in member_distances),
                            default=0.0,
                        ),
                    },
                    "distinguishing_metrics": distinguishing_metrics,
                    "prototype_resolved_values": prototype["manifest"].get(
                        "resolved_values", {}
                    ),
                    "prototype_top_topics": prototype["metrics"].get("top_topics", []),
                    "comparison_hints": [],
                    "_centroid": centroid,
                    "warnings": cluster_warnings,
                    "support_assessment": support_assessment,
                }
            )

        return clusters

    def _count_assumption_templates(
        self,
        members: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        counts: Counter[str] = Counter()
        for member in members:
            assumption_ledger = member.get("manifest", {}).get("assumption_ledger", {})
            templates = assumption_ledger.get("applied_templates")
            if not isinstance(templates, list) or not templates:
                templates = assumption_ledger.get("scenario_template_ids", [])
            if not isinstance(templates, list):
                continue
            for template_id in templates:
                normalized = str(template_id or "").strip()
                if normalized:
                    counts[normalized] += 1
        return {
            template_id: counts[template_id]
            for template_id in sorted(counts)
        }

    def _select_representative_run_ids(
        self,
        members: List[Dict[str, Any]],
        member_distances: List[tuple[str, float]],
    ) -> List[str]:
        run_ids_by_distance = [
            run_id
            for run_id, _ in sorted(member_distances, key=lambda item: (item[1], item[0]))
        ]
        if not run_ids_by_distance:
            run_ids_by_distance = sorted(member["run_id"] for member in members)
        return run_ids_by_distance[: min(3, len(run_ids_by_distance))]

    def _build_family_signature(
        self,
        *,
        distinguishing_metrics: List[Dict[str, Any]],
        assumption_template_counts: Dict[str, int],
        prototype_top_topics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metric_deltas = [
            {
                "metric_id": item.get("metric_id"),
                "direction": item.get("direction"),
                "mean_delta": item.get("mean_delta"),
            }
            for item in distinguishing_metrics[:2]
        ]
        topic_markers = [
            str(topic.get("topic")).strip()
            for topic in prototype_top_topics
            if isinstance(topic, dict) and str(topic.get("topic", "")).strip()
        ][:2]
        template_markers = list(assumption_template_counts.keys())[:2]
        return {
            "semantics": "empirical",
            "metric_deltas": metric_deltas,
            "template_markers": template_markers,
            "topic_markers": topic_markers,
        }

    def _build_family_label(
        self,
        *,
        cluster_id: str,
        family_signature: Dict[str, Any],
    ) -> str:
        primary_metric = (
            family_signature.get("metric_deltas") or [{}]
        )[0]
        metric_id = primary_metric.get("metric_id")
        direction = primary_metric.get("direction")
        if metric_id:
            if direction == "high":
                return f"Higher {metric_id}"
            if direction == "low":
                return f"Lower {metric_id}"
            return f"Centered {metric_id}"
        return f"Scenario family {cluster_id}"

    def _build_family_summary(
        self,
        *,
        family_signature: Dict[str, Any],
        family_label: str,
        run_count: int,
        total_runs: int,
        support_assessment: Dict[str, Any],
    ) -> str:
        parts = [f"Observed {run_count} of {total_runs} runs in the {family_label} family"]
        primary_metric = (family_signature.get("metric_deltas") or [{}])[0]
        if primary_metric.get("metric_id"):
            direction = primary_metric.get("direction") or "neutral"
            if direction == "high":
                parts.append(
                    f"{primary_metric['metric_id']} stays above the ensemble mean"
                )
            elif direction == "low":
                parts.append(
                    f"{primary_metric['metric_id']} stays below the ensemble mean"
                )
        template_markers = family_signature.get("template_markers") or []
        if template_markers:
            parts.append(f"templates: {', '.join(template_markers)}")
        topic_markers = family_signature.get("topic_markers") or []
        if topic_markers:
            parts.append(f"topics: {', '.join(topic_markers)}")
        if support_assessment.get("status") == "insufficient_support":
            parts.append("Insufficient support keeps this family descriptive only")
        elif support_assessment.get("status") == "descriptive_only":
            parts.append("Thin-sample or low-confidence warnings keep this family descriptive only")
        return ". ".join(parts) + "."

    def _build_cluster_support_assessment(
        self,
        *,
        warnings: List[str],
    ) -> Dict[str, Any]:
        relevant_warnings = [
            warning
            for warning in self._dedupe_warnings(warnings)
            if warning in {"thin_sample", "low_confidence", "minimum_support_not_met", "low_metric_variance"}
        ]
        if "minimum_support_not_met" in relevant_warnings:
            return {
                "status": "insufficient_support",
                "label": "Insufficient support",
                "downgraded": True,
                "decision_support_ready": False,
                "reason": "Minimum support was not met, so this cluster remains descriptive only.",
                "warnings": ["minimum_support_not_met"],
            }
        if any(
            warning in relevant_warnings
            for warning in ("thin_sample", "low_confidence", "low_metric_variance")
        ):
            return {
                "status": "descriptive_only",
                "label": "Descriptive only",
                "downgraded": True,
                "decision_support_ready": False,
                "reason": "Thin-sample or low-confidence warnings limit observed run share to descriptive use only.",
                "warnings": relevant_warnings,
            }
        return {
            "status": "observed_pattern",
            "label": "Observed cluster pattern",
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

    def _annotate_cluster_comparison_hints(
        self,
        clusters: List[Dict[str, Any]],
    ) -> None:
        for cluster in clusters:
            centroid = cluster.get("_centroid") or {}
            candidates = []
            for other in clusters:
                if other["cluster_id"] == cluster["cluster_id"]:
                    continue
                distance = self._distance_to_centroid(
                    centroid,
                    other.get("_centroid") or {},
                )
                candidates.append((distance, other["cluster_id"], other))

            candidates.sort(key=lambda item: (-item[0], item[1]))
            hints = []
            for _, _, other in candidates[:1]:
                hints.append(
                    {
                        "scope": {
                            "level": "cluster",
                            "cluster_id": other["cluster_id"],
                            "run_id": None,
                        },
                        "prototype_run_id": other.get("prototype_run_id"),
                        "reason": "largest_empirical_centroid_contrast",
                    }
                )
                if other.get("prototype_run_id"):
                    hints.append(
                        {
                            "scope": {
                                "level": "run",
                                "cluster_id": other["cluster_id"],
                                "run_id": other["prototype_run_id"],
                            },
                            "prototype_run_id": other["prototype_run_id"],
                            "reason": "prototype_run_comparison",
                        }
                    )
            cluster["comparison_hints"] = hints
            cluster.pop("_centroid", None)

    def _derive_generated_at(self, run_payloads: List[Dict[str, Any]]) -> str:
        timestamps = []
        for payload in run_payloads:
            metrics_timestamp = payload["metrics"].get("extracted_at") if isinstance(payload.get("metrics"), dict) else None
            manifest_timestamp = payload["manifest"].get("generated_at")
            if metrics_timestamp:
                timestamps.append(metrics_timestamp)
            if manifest_timestamp:
                timestamps.append(manifest_timestamp)
        if timestamps:
            return max(timestamps)
        return "1970-01-01T00:00:00"

    def _select_medoid(self, members: List[Dict[str, Any]]) -> Dict[str, Any]:
        return min(
            members,
            key=lambda candidate: (
                sum(
                    self._distance_to_centroid(
                        member["standardized_vector"],
                        candidate["standardized_vector"],
                    )
                    for member in members
                )
                / len(members),
                candidate["run_id"],
            ),
        )

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

    def _distance_to_centroid(
        self,
        feature_vector: Dict[str, float],
        centroid: Dict[str, float],
    ) -> float:
        return math.sqrt(sum(
            (feature_vector[metric_id] - centroid[metric_id]) ** 2
            for metric_id in centroid
        ))

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
        return self.analytics_policy.coerce_numeric_value(raw_entry)

    def _read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
