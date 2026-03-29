"""
Probabilistic report-context builder.

This service packages the already-persisted ensemble analytics into one
report-ready artifact that Step 4 and Step 5 can consume without having to
reconstruct ensemble semantics from raw logs.

The artifact is intentionally conservative:
- ensemble-level facts are labeled empirical,
- run-level facts are labeled observed,
- sensitivity remains observational only,
- degraded or missing inputs stay visible as warnings instead of being filled in.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models.grounding import build_grounding_context
from ..models.probabilistic import (
    CALIBRATION_BOUNDARY_NOTE,
    build_supported_outcome_metric,
)
from .analytics_policy import AnalyticsPolicy
from .ensemble_manager import EnsembleManager
from .grounding_bundle_builder import GroundingBundleBuilder
from .scenario_clusterer import ScenarioClusterer
from .sensitivity_analyzer import SensitivityAnalyzer
from .simulation_manager import SimulationManager


REPORT_CONTEXT_SCHEMA_VERSION = "probabilistic.report_context.v3"
REPORT_CONTEXT_GENERATOR_VERSION = "probabilistic.report_context.generator.v3"


class ProbabilisticReportContextBuilder:
    """Build and persist one ensemble-aware report context artifact."""

    REPORT_CONTEXT_FILENAME = "probabilistic_report_context.json"

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        self.analytics_policy = AnalyticsPolicy()
        self.ensemble_manager = EnsembleManager(simulation_data_dir=self.simulation_data_dir)
        self.clusterer = ScenarioClusterer(simulation_data_dir=self.simulation_data_dir)
        self.sensitivity_analyzer = SensitivityAnalyzer(
            simulation_data_dir=self.simulation_data_dir
        )

    def get_report_context(
        self,
        simulation_id: str,
        ensemble_id: str,
        cluster_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build and persist one deterministic report context for the ensemble."""
        ensemble_payload = self.ensemble_manager.load_ensemble(simulation_id, ensemble_id)
        normalized_ensemble_id = ensemble_payload["ensemble_id"]
        prepared_artifact_summary = SimulationManager().get_prepare_artifact_summary(
            simulation_id
        )
        aggregate_summary = self.ensemble_manager.get_aggregate_summary(
            simulation_id,
            normalized_ensemble_id,
        )
        scenario_clusters = self.clusterer.get_scenario_clusters(
            simulation_id,
            normalized_ensemble_id,
        )
        sensitivity = self.sensitivity_analyzer.get_sensitivity_analysis(
            simulation_id,
            normalized_ensemble_id,
        )
        calibration_summary = self._load_calibration_summary(
            simulation_id,
            normalized_ensemble_id,
        )
        confidence_status = self._build_confidence_status(calibration_summary)
        calibrated_summary = self._build_ready_calibrated_summary(calibration_summary)
        run_lookup = self._build_run_lookup(ensemble_payload)
        selected_run = self._resolve_selected_run(run_lookup, run_id)
        selected_cluster_source = "route" if cluster_id else None
        scenario_families = self._build_scenario_families(
            scenario_clusters=scenario_clusters,
            prepared_run_count=ensemble_payload.get("state", {}).get(
                "prepared_run_count",
                0,
            ),
        )
        selected_cluster = self._resolve_selected_cluster(
            scenario_families=scenario_families,
            requested_cluster_id=cluster_id,
            selected_run=selected_run,
        )
        if selected_cluster and not cluster_id:
            selected_cluster_source = "derived_membership"
        scope = self._build_scope(
            simulation_id=simulation_id,
            ensemble_id=normalized_ensemble_id,
            selected_cluster=selected_cluster,
            selected_run=selected_run,
            source=selected_cluster_source or "route",
        )
        compare_options = self._build_compare_options(
            simulation_id=simulation_id,
            ensemble_id=normalized_ensemble_id,
            scope=scope,
            scenario_families=scenario_families,
            selected_cluster=selected_cluster,
            selected_run=selected_run,
        )
        grounding_bundle = GroundingBundleBuilder(
            simulation_data_dir=self.simulation_data_dir
        ).load_bundle(simulation_id)
        grounding_context = build_grounding_context(grounding_bundle)
        ensemble_facts = self._build_ensemble_facts(
            ensemble_payload=ensemble_payload,
            aggregate_summary=aggregate_summary,
        )
        top_outcomes = self._build_top_outcomes(
            aggregate_summary=aggregate_summary,
            prepared_run_count=ensemble_payload.get("state", {}).get(
                "prepared_run_count",
                0,
            ),
        )
        representative_runs = self._build_representative_runs(
            run_lookup=run_lookup,
            scenario_clusters=scenario_clusters,
            selected_run=selected_run,
        )
        compare_catalog = self._build_compare_catalog(
            simulation_id=simulation_id,
            ensemble_id=normalized_ensemble_id,
            compare_options=compare_options,
            scenario_families=scenario_families,
            run_lookup=run_lookup,
            ensemble_facts=ensemble_facts,
            top_outcomes=top_outcomes,
            representative_runs=representative_runs,
            confidence_status=confidence_status,
            grounding_context=grounding_context,
        )
        driver_analysis = self._build_driver_analysis(
            sensitivity=sensitivity,
            selected_cluster=selected_cluster,
            selected_run=selected_run,
        )

        artifact = {
            "artifact_type": "probabilistic_report_context",
            "schema_version": REPORT_CONTEXT_SCHEMA_VERSION,
            "generator_version": REPORT_CONTEXT_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": normalized_ensemble_id,
            "cluster_id": selected_cluster.get("cluster_id") if selected_cluster else None,
            "run_id": selected_run.get("run_id") if selected_run else None,
            "scope": scope,
            "probability_mode": "empirical",
            "probability_semantics": {
                "summary": "empirical",
                "clusters": "empirical",
                "runs": "observed",
                "sensitivity": "observational",
                **(
                    {"calibration": "backtested"}
                    if confidence_status.get("status") == "ready"
                    else {}
                ),
            },
            "confidence_status": confidence_status,
            **(
                {
                    "calibration_provenance": self._build_calibration_provenance(
                        calibrated_summary
                    )
                }
                if calibrated_summary
                else {}
            ),
            "analytics_semantics": self.analytics_policy.build_report_analytics_semantics(
                aggregate_summary=aggregate_summary,
                scenario_clusters=scenario_clusters,
                sensitivity=sensitivity,
            ),
            "prepared_artifact_summary": prepared_artifact_summary,
            "grounding_context": grounding_context,
            "ensemble_facts": ensemble_facts,
            "top_outcomes": top_outcomes,
            "scenario_families": scenario_families,
            "representative_runs": representative_runs,
            "selected_cluster": selected_cluster,
            "selected_run": selected_run,
            "sensitivity_overview": self._build_sensitivity_overview(sensitivity),
            "driver_analysis": driver_analysis,
            "compare_options": compare_options,
            "compare_catalog": compare_catalog,
            "scope_catalog": self._build_scope_catalog(
                simulation_id=simulation_id,
                ensemble_id=normalized_ensemble_id,
                scenario_families=scenario_families,
                run_lookup=run_lookup,
                compare_options=compare_options,
            ),
            "quality_summary": self._build_quality_summary(
                aggregate_summary=aggregate_summary,
                scenario_clusters=scenario_clusters,
                sensitivity=sensitivity,
                confidence_status=confidence_status,
                calibrated_summary=calibrated_summary,
                selected_run=selected_run,
                requested_run_id=run_id,
            ),
            "aggregate_summary": aggregate_summary,
            **({"calibrated_summary": calibrated_summary} if calibrated_summary else {}),
            "scenario_clusters": scenario_clusters,
            "sensitivity": sensitivity,
            "source_artifacts": {
                "aggregate_summary": self.ensemble_manager.AGGREGATE_SUMMARY_FILENAME,
                "scenario_clusters": self.clusterer.CLUSTERS_FILENAME,
                "sensitivity": self.sensitivity_analyzer.SENSITIVITY_FILENAME,
                "ensemble_state": self.ensemble_manager.ENSEMBLE_STATE_FILENAME,
                "ensemble_spec": self.ensemble_manager.ENSEMBLE_SPEC_FILENAME,
                "grounding_bundle": GroundingBundleBuilder.GROUNDING_BUNDLE_FILENAME,
                **(
                    {"calibration_summary": self.ensemble_manager.CALIBRATION_SUMMARY_FILENAME}
                    if confidence_status.get("status") != "absent"
                    else {}
                ),
            },
            "generated_at": self._derive_generated_at(
                aggregate_summary,
                scenario_clusters,
                sensitivity,
            ),
        }

        self._write_json(
            os.path.join(
                ensemble_payload["ensemble_dir"],
                self.REPORT_CONTEXT_FILENAME,
            ),
            artifact,
        )
        return artifact

    def build_context(
        self,
        simulation_id: str,
        ensemble_id: str,
        cluster_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compatibility alias for the report-context task register wording."""
        return self.get_report_context(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            cluster_id=cluster_id,
            run_id=run_id,
        )

    def _build_scope(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        selected_cluster: Optional[Dict[str, Any]],
        selected_run: Optional[Dict[str, Any]],
        source: str,
    ) -> Dict[str, Any]:
        level = "ensemble"
        if selected_run:
            level = "run"
        elif selected_cluster:
            level = "cluster"

        return {
            "level": level,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "cluster_id": (
                selected_cluster.get("cluster_id") if selected_cluster else None
            ),
            "run_id": selected_run.get("run_id") if selected_run else None,
            "representative_run_id": (
                selected_run.get("run_id")
                if selected_run
                else (
                    selected_cluster.get("prototype_run_id")
                    if selected_cluster
                    else None
                )
            ),
            "source": source,
        }

    def _build_ensemble_facts(
        self,
        *,
        ensemble_payload: Dict[str, Any],
        aggregate_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = ensemble_payload.get("state", {})
        quality_summary = aggregate_summary.get("quality_summary", {})
        return {
            "scope": "ensemble",
            "ensemble_id": ensemble_payload.get("ensemble_id"),
            "status": quality_summary.get("status", "partial"),
            "prepared_run_count": state.get("prepared_run_count", 0),
            "outcome_metric_ids": aggregate_summary.get("source_artifacts", {}).get(
                "outcome_metric_ids",
                [],
            ),
            "provenance": {
                "mode": "empirical",
                "label": "Empirical ensemble summary",
                "artifact_type": aggregate_summary.get("artifact_type"),
            },
            "support": {
                "prepared_run_count": state.get("prepared_run_count", 0),
                "runs_with_metrics": quality_summary.get("runs_with_metrics", 0),
                "complete_runs": quality_summary.get("complete_runs", 0),
                "partial_runs": quality_summary.get("partial_runs", 0),
                "missing_metrics_runs": quality_summary.get("missing_metrics_runs", []),
            },
            "warnings": quality_summary.get("warnings", []),
        }

    def _build_top_outcomes(
        self,
        *,
        aggregate_summary: Dict[str, Any],
        prepared_run_count: int,
    ) -> List[Dict[str, Any]]:
        metric_summaries = aggregate_summary.get("metric_summaries", {})
        outcomes: List[Dict[str, Any]] = []
        for metric_id, summary in metric_summaries.items():
            numeric_sort_value = summary.get("mean")
            if numeric_sort_value is None:
                numeric_sort_value = summary.get("empirical_probability")
            if numeric_sort_value is None:
                numeric_sort_value = summary.get("dominant_probability")
            if numeric_sort_value is None:
                numeric_sort_value = summary.get("sample_count", 0)

            sample_count = summary.get("sample_count", 0)
            outcomes.append(
                {
                    "scope": "ensemble",
                    "metric_id": metric_id,
                    "label": summary.get("label", metric_id),
                    "distribution_kind": summary.get("distribution_kind"),
                    "sample_count": sample_count,
                    "value_summary": self._extract_metric_value_summary(summary),
                    "provenance": {
                        "mode": "empirical",
                        "label": "Empirical aggregate metric",
                        "artifact_type": aggregate_summary.get("artifact_type"),
                    },
                    "support": {
                        "sample_count": sample_count,
                        "prepared_run_count": prepared_run_count,
                        "label": f"Observed in {sample_count} of {prepared_run_count} runs",
                    },
                    "warnings": summary.get("warnings", []),
                    "_sort_value": numeric_sort_value,
                }
            )

        outcomes.sort(
            key=lambda item: (-float(item["_sort_value"]), item["metric_id"])
            if isinstance(item["_sort_value"], (int, float))
            else (0.0, item["metric_id"])
        )
        for outcome in outcomes:
            outcome.pop("_sort_value", None)
        return outcomes

    def _build_scenario_families(
        self,
        *,
        scenario_clusters: Dict[str, Any],
        prepared_run_count: int,
    ) -> List[Dict[str, Any]]:
        families = []
        for cluster in scenario_clusters.get("clusters", []):
            run_count = cluster.get("run_count", 0)
            families.append(
                {
                    "scope": "cluster",
                    "cluster_id": cluster.get("cluster_id"),
                    "family_label": cluster.get("family_label"),
                    "family_summary": cluster.get("family_summary"),
                    "prototype_run_id": cluster.get("prototype_run_id"),
                    "representative_run_ids": cluster.get("representative_run_ids", []),
                    "member_run_ids": cluster.get("member_run_ids", []),
                    "probability_mass": cluster.get("probability_mass"),
                    "assumption_template_counts": cluster.get(
                        "assumption_template_counts",
                        {},
                    ),
                    "family_signature": cluster.get("family_signature", {}),
                    "comparison_hints": cluster.get("comparison_hints", []),
                    "distinguishing_metrics": cluster.get("distinguishing_metrics", []),
                    "prototype_resolved_values": cluster.get(
                        "prototype_resolved_values",
                        {},
                    ),
                    "prototype_top_topics": cluster.get("prototype_top_topics", []),
                    "provenance": {
                        "mode": "empirical",
                        "label": "Empirical scenario family",
                        "artifact_type": scenario_clusters.get("artifact_type"),
                    },
                    "support": {
                        "run_count": run_count,
                        "support_count": cluster.get("support_count", run_count),
                        "support_fraction": cluster.get("support_fraction"),
                        "minimum_support_count": cluster.get("minimum_support_count"),
                        "minimum_support_met": cluster.get("minimum_support_met"),
                        "prepared_run_count": prepared_run_count,
                        "label": f"Observed in {run_count} of {prepared_run_count} runs",
                    },
                    "warnings": cluster.get("warnings", []),
                }
            )
        return families

    def _resolve_selected_cluster(
        self,
        *,
        scenario_families: List[Dict[str, Any]],
        requested_cluster_id: Optional[str],
        selected_run: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if requested_cluster_id:
            for family in scenario_families:
                if family.get("cluster_id") == requested_cluster_id:
                    return family

        if selected_run and selected_run.get("run_id"):
            selected_run_id = selected_run["run_id"]
            for family in scenario_families:
                if selected_run_id in family.get("member_run_ids", []):
                    return family

        return None

    def _build_representative_runs(
        self,
        *,
        run_lookup: Dict[str, Dict[str, Any]],
        scenario_clusters: Dict[str, Any],
        selected_run: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        representative_ids: List[str] = []
        if selected_run and selected_run.get("run_id"):
            representative_ids.append(selected_run["run_id"])

        for cluster in scenario_clusters.get("clusters", []):
            prototype_run_id = cluster.get("prototype_run_id")
            if prototype_run_id and prototype_run_id not in representative_ids:
                representative_ids.append(prototype_run_id)

        if not representative_ids and run_lookup:
            representative_ids.append(sorted(run_lookup.keys())[0])

        return [
            self._build_run_snapshot(run_lookup[run_id])
            for run_id in representative_ids
            if run_id in run_lookup
        ]

    def _build_sensitivity_overview(
        self,
        sensitivity: Dict[str, Any],
    ) -> Dict[str, Any]:
        driver_rankings = sensitivity.get("driver_rankings", [])
        top_drivers = []
        for driver in driver_rankings[:3]:
            top_metric = driver.get("metric_impacts", [{}])[0] if driver.get("metric_impacts") else {}
            top_drivers.append(
                {
                    "driver_id": driver.get("driver_id"),
                    "driver_kind": driver.get("driver_kind"),
                    "overall_effect_score": driver.get("overall_effect_score"),
                    "distinct_value_count": driver.get("distinct_value_count"),
                    "group_count": driver.get("group_count"),
                    "sample_count": driver.get("sample_count"),
                    "minimum_support_count": driver.get("minimum_support_count"),
                    "minimum_support_met": driver.get("minimum_support_met"),
                    "top_metric_id": top_metric.get("metric_id"),
                    "top_metric_effect_size": top_metric.get("effect_size"),
                    "warnings": driver.get("warnings", []),
                }
            )

        return {
            "scope": "ensemble",
            "analysis_mode": sensitivity.get("methodology", {}).get("analysis_mode"),
            "ranking_basis": sensitivity.get("methodology", {}).get("ranking_basis"),
            "top_drivers": top_drivers,
            "warnings": sensitivity.get("quality_summary", {}).get("warnings", []),
            "provenance": {
                "mode": "observational",
                "label": "Observational sensitivity ranking",
                "artifact_type": sensitivity.get("artifact_type"),
            },
        }

    def _build_driver_analysis(
        self,
        *,
        sensitivity: Dict[str, Any],
        selected_cluster: Optional[Dict[str, Any]],
        selected_run: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        driver_rankings = sensitivity.get("driver_rankings", [])
        top_drivers = [
            {
                "driver_id": driver.get("driver_id"),
                "driver_kind": driver.get("driver_kind"),
                "overall_effect_score": driver.get("overall_effect_score"),
                "driver_summary": driver.get("driver_summary"),
                "cluster_alignment_hints": driver.get("cluster_alignment_hints", []),
                "warnings": driver.get("warnings", []),
            }
            for driver in driver_rankings[:5]
        ]
        return {
            "semantics": "observational",
            "ranking_basis": sensitivity.get("methodology", {}).get("ranking_basis"),
            "top_drivers": top_drivers,
            "selected_scope_highlights": self._build_selected_scope_highlights(
                sensitivity=sensitivity,
                selected_cluster=selected_cluster,
                selected_run=selected_run,
            ),
            "warnings": sensitivity.get("quality_summary", {}).get("warnings", []),
            "provenance": {
                "mode": "observational",
                "label": "Observational driver analysis",
                "artifact_type": sensitivity.get("artifact_type"),
            },
        }

    def _build_selected_scope_highlights(
        self,
        *,
        sensitivity: Dict[str, Any],
        selected_cluster: Optional[Dict[str, Any]],
        selected_run: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cluster_id = selected_cluster.get("cluster_id") if selected_cluster else None
        selected_run_id = selected_run.get("run_id") if selected_run else None
        selected_run_values = selected_run.get("resolved_values", {}) if selected_run else {}

        highlights: List[Dict[str, Any]] = []
        for driver in sensitivity.get("driver_rankings", []):
            cluster_hint = next(
                (
                    hint for hint in driver.get("cluster_alignment_hints", [])
                    if hint.get("cluster_id") == cluster_id
                ),
                None,
            )
            if cluster_id and cluster_hint:
                highlight = {
                    "driver_id": driver.get("driver_id"),
                    "cluster_id": cluster_id,
                    "group_value_label": cluster_hint.get("group_value_label"),
                    "alignment_fraction": cluster_hint.get("alignment_fraction"),
                    "summary": driver.get("driver_summary"),
                }
                if selected_run_id and driver.get("driver_id") in selected_run_values:
                    highlight["observed_value"] = selected_run_values.get(
                        driver.get("driver_id")
                    )
                highlights.append(highlight)
                continue

            if selected_run_id and driver.get("driver_id") in selected_run_values:
                highlights.append(
                    {
                        "driver_id": driver.get("driver_id"),
                        "observed_value": selected_run_values.get(driver.get("driver_id")),
                        "summary": driver.get("driver_summary"),
                    }
                )

        if highlights:
            return highlights[:3]

        return [
            {
                "driver_id": driver.get("driver_id"),
                "summary": driver.get("driver_summary"),
            }
            for driver in sensitivity.get("driver_rankings", [])[:3]
        ]

    def _build_scope_catalog(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        scenario_families: List[Dict[str, Any]],
        run_lookup: Dict[str, Dict[str, Any]],
        compare_options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        run_to_cluster = {}
        for family in scenario_families:
            for run_id in family.get("member_run_ids", []):
                run_to_cluster[run_id] = family.get("cluster_id")

        return {
            "ensemble": {
                "level": "ensemble",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cluster_id": None,
                "run_id": None,
                "representative_run_id": None,
                "source": "route",
            },
            "clusters": [
                {
                    "level": "cluster",
                    "simulation_id": simulation_id,
                    "ensemble_id": ensemble_id,
                    "cluster_id": family.get("cluster_id"),
                    "run_id": None,
                    "representative_run_id": family.get("prototype_run_id"),
                    "source": "route",
                    "label": family.get("family_label"),
                }
                for family in scenario_families
            ],
            "runs": [
                {
                    "level": "run",
                    "simulation_id": simulation_id,
                    "ensemble_id": ensemble_id,
                    "cluster_id": run_to_cluster.get(run_id),
                    "run_id": run_id,
                    "representative_run_id": run_id,
                    "source": "derived_membership"
                    if run_to_cluster.get(run_id)
                    else "route",
                }
                for run_id in sorted(run_lookup)
            ],
            "compare_options": compare_options,
        }

    def _build_compare_options(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        scope: Dict[str, Any],
        scenario_families: List[Dict[str, Any]],
        selected_cluster: Optional[Dict[str, Any]],
        selected_run: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        compare_options: List[Dict[str, Any]] = []
        if selected_cluster:
            for hint in selected_cluster.get("comparison_hints", []):
                if hint.get("scope", {}).get("level") != "cluster":
                    continue
                left_scope = {
                    "level": "cluster",
                    "simulation_id": simulation_id,
                    "ensemble_id": ensemble_id,
                    "cluster_id": selected_cluster.get("cluster_id"),
                    "run_id": None,
                }
                right_scope = {
                    "level": "cluster",
                    "simulation_id": simulation_id,
                    "ensemble_id": ensemble_id,
                    "cluster_id": hint["scope"].get("cluster_id"),
                    "run_id": None,
                }
                compare_options.append(
                    {
                        "compare_id": self._build_compare_id(left_scope, right_scope),
                        "label": (
                            f"{selected_cluster.get('cluster_id')} vs "
                            f"{hint['scope'].get('cluster_id')}"
                        ),
                        "reason": "Selected scenario family against a stored peer-family hint.",
                        "left": left_scope,
                        "right": right_scope,
                        "prompt": (
                            f"Compare scenario family {selected_cluster.get('cluster_id')} "
                            f"against {hint['scope'].get('cluster_id')}. Focus on "
                            "probability mass, representative runs, distinguishing metrics, "
                            "support counts, and warnings only."
                        ),
                    }
                )

        if not compare_options and len(scenario_families) >= 2:
            first_family = scenario_families[0]
            second_family = scenario_families[1]
            left_scope = {
                "level": "cluster",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cluster_id": first_family.get("cluster_id"),
                "run_id": None,
            }
            right_scope = {
                "level": "cluster",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cluster_id": second_family.get("cluster_id"),
                "run_id": None,
            }
            compare_options.append(
                {
                    "compare_id": self._build_compare_id(left_scope, right_scope),
                    "label": (
                        f"{first_family.get('cluster_id')} vs "
                        f"{second_family.get('cluster_id')}"
                    ),
                    "reason": "Highest-support scenario families inside the current ensemble.",
                    "left": left_scope,
                    "right": right_scope,
                    "prompt": (
                        f"Compare scenario family {first_family.get('cluster_id')} "
                        f"against {second_family.get('cluster_id')}. Focus on "
                        "probability mass, representative runs, distinguishing metrics, "
                        "support counts, and warnings only."
                    ),
                }
            )

        if selected_run:
            left_scope = {
                "level": "run",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cluster_id": scope.get("cluster_id"),
                "run_id": selected_run.get("run_id"),
            }
            right_scope = {
                "level": "ensemble",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "cluster_id": None,
                "run_id": None,
            }
            compare_options.append(
                {
                    "compare_id": self._build_compare_id(left_scope, right_scope),
                    "label": f"Run {selected_run.get('run_id')} vs ensemble",
                    "reason": "Selected run against the empirical ensemble baseline.",
                    "left": left_scope,
                    "right": right_scope,
                    "prompt": (
                        f"Explain how run {selected_run.get('run_id')} differs from "
                        f"ensemble {ensemble_id}. Use only observed metrics, "
                        "representative runs, support counts, and warnings."
                    ),
                }
            )

        return compare_options[:3]

    def _build_compare_id(
        self,
        left_scope: Dict[str, Any],
        right_scope: Dict[str, Any],
    ) -> str:
        def _scope_token(scope: Dict[str, Any]) -> str:
            level = scope.get("level") or "scope"
            if level == "run":
                identifier = scope.get("run_id")
            elif level == "cluster":
                identifier = scope.get("cluster_id")
            else:
                identifier = scope.get("ensemble_id")
            return f"{level}-{identifier or 'unknown'}"

        return f"{_scope_token(left_scope)}__{_scope_token(right_scope)}"

    def _build_compare_catalog(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        compare_options: List[Dict[str, Any]],
        scenario_families: List[Dict[str, Any]],
        run_lookup: Dict[str, Dict[str, Any]],
        ensemble_facts: Dict[str, Any],
        top_outcomes: List[Dict[str, Any]],
        representative_runs: List[Dict[str, Any]],
        confidence_status: Dict[str, Any],
        grounding_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        options: List[Dict[str, Any]] = []
        for option in compare_options:
            left_scope = self._normalize_compare_scope(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                scope=option.get("left"),
            )
            right_scope = self._normalize_compare_scope(
                simulation_id=simulation_id,
                ensemble_id=ensemble_id,
                scope=option.get("right"),
            )
            left_snapshot = self._build_compare_scope_snapshot(
                scope=left_scope,
                scenario_families=scenario_families,
                run_lookup=run_lookup,
                ensemble_facts=ensemble_facts,
                top_outcomes=top_outcomes,
                representative_runs=representative_runs,
                confidence_status=confidence_status,
                grounding_context=grounding_context,
            )
            right_snapshot = self._build_compare_scope_snapshot(
                scope=right_scope,
                scenario_families=scenario_families,
                run_lookup=run_lookup,
                ensemble_facts=ensemble_facts,
                top_outcomes=top_outcomes,
                representative_runs=representative_runs,
                confidence_status=confidence_status,
                grounding_context=grounding_context,
            )
            options.append(
                {
                    "compare_id": option.get("compare_id")
                    or self._build_compare_id(left_scope, right_scope),
                    "label": option.get("label")
                    or f"{left_snapshot.get('headline')} vs {right_snapshot.get('headline')}",
                    "reason": option.get("reason")
                    or "Bounded comparison inside the current saved report context.",
                    "left_scope": left_scope,
                    "right_scope": right_scope,
                    "left_snapshot": left_snapshot,
                    "right_snapshot": right_snapshot,
                    "comparison_summary": self._build_compare_summary(
                        left_snapshot=left_snapshot,
                        right_snapshot=right_snapshot,
                    ),
                    "warnings": self._merge_compare_warnings(
                        left_snapshot.get("warnings", []),
                        right_snapshot.get("warnings", []),
                        left_snapshot.get("semantics"),
                        right_snapshot.get("semantics"),
                    ),
                    "prompt": option.get("prompt")
                    or "Compare the current probabilistic scopes using only persisted evidence, support counts, warnings, and representative runs.",
                }
            )

        return {
            "boundary_note": (
                "Compare only scopes inside one saved report context and one ensemble. "
                "Treat ensemble and scenario-family summaries as empirical, run facts as observed, "
                "and driver evidence as observational only."
            ),
            "options": options[:3],
        }

    def _normalize_compare_scope(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        scope: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        scope = scope or {}
        return {
            "level": scope.get("level") or "ensemble",
            "simulation_id": scope.get("simulation_id") or simulation_id,
            "ensemble_id": scope.get("ensemble_id") or ensemble_id,
            "cluster_id": scope.get("cluster_id"),
            "run_id": scope.get("run_id"),
        }

    def _build_compare_scope_snapshot(
        self,
        *,
        scope: Dict[str, Any],
        scenario_families: List[Dict[str, Any]],
        run_lookup: Dict[str, Dict[str, Any]],
        ensemble_facts: Dict[str, Any],
        top_outcomes: List[Dict[str, Any]],
        representative_runs: List[Dict[str, Any]],
        confidence_status: Dict[str, Any],
        grounding_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        level = scope.get("level")
        if level == "run":
            run_payload = run_lookup.get(scope.get("run_id"))
            run_snapshot = self._build_run_snapshot(run_payload) if run_payload else None
            key_metrics = (
                [metric.get("metric_id") for metric in run_snapshot.get("key_metrics", [])[:3]]
                if run_snapshot
                else []
            )
            return {
                "scope": scope,
                "headline": f"Run {scope.get('run_id') or '-'}",
                "support_label": (
                    "Observed run metrics available"
                    if run_snapshot and run_snapshot.get("support", {}).get("has_metrics")
                    else "Observed run metrics unavailable"
                ),
                "semantics": "observed",
                "representative_run_ids": [scope.get("run_id")] if scope.get("run_id") else [],
                "warnings": run_snapshot.get("warnings", []) if run_snapshot else ["missing_run_scope"],
                "evidence_highlights": key_metrics,
                "confidence_status": confidence_status.get("status"),
                "grounding_status": grounding_context.get("status", "unavailable"),
            }

        if level == "cluster":
            family = next(
                (
                    entry
                    for entry in scenario_families
                    if entry.get("cluster_id") == scope.get("cluster_id")
                ),
                None,
            )
            return {
                "scope": scope,
                "headline": (
                    family.get("family_label")
                    if family and family.get("family_label")
                    else f"Scenario family {scope.get('cluster_id') or '-'}"
                ),
                "support_label": (
                    family.get("support", {}).get("label")
                    if family
                    else "Scenario-family support unavailable"
                ),
                "semantics": (
                    family.get("family_signature", {}).get("semantics")
                    if family
                    else "empirical"
                ),
                "representative_run_ids": (
                    (family.get("representative_run_ids") or [])[:3]
                    if family
                    else []
                ),
                "warnings": family.get("warnings", []) if family else ["missing_cluster_scope"],
                "evidence_highlights": (
                    [
                        metric.get("metric_id")
                        or metric.get("label")
                        for metric in family.get("distinguishing_metrics", [])[:3]
                    ]
                    if family
                    else []
                ),
                "confidence_status": confidence_status.get("status"),
                "grounding_status": grounding_context.get("status", "unavailable"),
            }

        support = ensemble_facts.get("support", {})
        representative_run_ids = [
            run.get("run_id") for run in representative_runs[:3] if run.get("run_id")
        ]
        support_label = self._build_ensemble_support_label(support)
        return {
            "scope": scope,
            "headline": f"Ensemble {scope.get('ensemble_id') or '-'}",
            "support_label": support_label,
            "semantics": "empirical",
            "representative_run_ids": representative_run_ids,
            "warnings": ensemble_facts.get("warnings", []),
            "evidence_highlights": [
                item.get("metric_id") or item.get("label")
                for item in top_outcomes[:3]
            ],
            "confidence_status": confidence_status.get("status"),
            "grounding_status": grounding_context.get("status", "unavailable"),
        }

    def _build_ensemble_support_label(self, support: Dict[str, Any]) -> str:
        prepared_run_count = support.get("prepared_run_count")
        runs_with_metrics = support.get("runs_with_metrics")
        if isinstance(prepared_run_count, int) and isinstance(runs_with_metrics, int):
            return f"{runs_with_metrics} of {prepared_run_count} runs with metrics"
        if isinstance(prepared_run_count, int):
            return f"{prepared_run_count} prepared runs"
        return "Support counts unavailable"

    def _build_compare_summary(
        self,
        *,
        left_snapshot: Dict[str, Any],
        right_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        what_differs = [
            (
                f"{left_snapshot.get('headline')} uses {left_snapshot.get('semantics')} evidence "
                f"while {right_snapshot.get('headline')} uses {right_snapshot.get('semantics')} evidence."
            )
        ]
        left_highlight = (left_snapshot.get("evidence_highlights") or [None])[0]
        right_highlight = (right_snapshot.get("evidence_highlights") or [None])[0]
        if left_highlight and right_highlight and left_highlight != right_highlight:
            what_differs.append(
                f"Primary evidence highlights differ: {left_highlight} versus {right_highlight}."
            )

        weak_support = [
            warning
            for warning in [
                *(left_snapshot.get("warnings") or []),
                *(right_snapshot.get("warnings") or []),
            ][:3]
        ]
        if not weak_support and (
            left_snapshot.get("semantics") != right_snapshot.get("semantics")
        ):
            weak_support.append(
                "Cross-scope differences are bounded by observed versus empirical evidence modes."
            )

        return {
            "what_differs": what_differs,
            "weak_support": weak_support,
            "boundary_note": (
                "Do not treat this comparison as causal, globally calibrated, or stronger than the saved artifact trail."
            ),
        }

    def _merge_compare_warnings(
        self,
        left_warnings: List[str],
        right_warnings: List[str],
        left_semantics: Optional[str],
        right_semantics: Optional[str],
    ) -> List[str]:
        warnings: List[str] = []
        for warning in [*left_warnings, *right_warnings]:
            if warning and warning not in warnings:
                warnings.append(warning)
        if left_semantics and right_semantics and left_semantics != right_semantics:
            warnings.append("observed_vs_empirical")
        return warnings[:4]

    def _build_quality_summary(
        self,
        *,
        aggregate_summary: Dict[str, Any],
        scenario_clusters: Dict[str, Any],
        sensitivity: Dict[str, Any],
        confidence_status: Dict[str, Any],
        calibrated_summary: Optional[Dict[str, Any]],
        selected_run: Optional[Dict[str, Any]],
        requested_run_id: Optional[str],
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        component_statuses = [
            aggregate_summary.get("quality_summary", {}).get("status"),
            scenario_clusters.get("quality_summary", {}).get("status"),
            sensitivity.get("quality_summary", {}).get("status"),
        ]
        if calibrated_summary:
            component_statuses.append(
                calibrated_summary.get("quality_summary", {}).get("status")
            )
        elif confidence_status.get("status") == "not_ready":
            component_statuses.append("partial")

        for component in (
            aggregate_summary.get("quality_summary", {}),
            scenario_clusters.get("quality_summary", {}),
            sensitivity.get("quality_summary", {}),
        ):
            for warning in component.get("warnings", []):
                if warning not in warnings:
                    warnings.append(warning)

        if calibrated_summary:
            for warning in calibrated_summary.get("quality_summary", {}).get("warnings", []):
                if warning not in warnings:
                    warnings.append(warning)
        else:
            for warning in confidence_status.get("warnings", []):
                if warning not in warnings:
                    warnings.append(warning)

        if requested_run_id and not selected_run:
            warnings.append("missing_selected_run")
            component_statuses.append("partial")

        return {
            "status": "partial"
            if any(status == "partial" for status in component_statuses)
            else "complete",
            "warnings": warnings,
        }

    def _build_calibration_provenance(
        self,
        calibrated_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        ready_metrics = calibrated_summary.get("metrics", [])
        return {
            "mode": "calibrated",
            "artifact_type": calibrated_summary.get("artifact_type"),
            "ready_metric_ids": [
                metric.get("metric_id")
                for metric in ready_metrics
                if metric.get("metric_id")
            ],
            "quality_status": calibrated_summary.get("quality_summary", {}).get(
                "status",
                "complete",
            ),
            "warnings": calibrated_summary.get("quality_summary", {}).get(
                "warnings",
                [],
            ),
        }

    def _load_calibration_summary(
        self,
        simulation_id: str,
        ensemble_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            summary = self.ensemble_manager.load_calibration_summary(
                simulation_id,
                ensemble_id,
            )
        except ValueError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        return summary

    def _build_confidence_status(
        self,
        calibration_summary: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        status = {
            "status": "absent",
            "supported_metric_ids": [],
            "ready_metric_ids": [],
            "not_ready_metric_ids": [],
            "gating_reasons": [],
            "warnings": [],
            "boundary_note": CALIBRATION_BOUNDARY_NOTE,
        }
        if not calibration_summary:
            return status

        status["status"] = "not_ready"
        warnings: List[str] = []
        gating_reasons: List[str] = []
        supported_metric_ids: List[str] = []
        ready_metric_ids: List[str] = []
        not_ready_metric_ids: List[str] = []

        for warning in calibration_summary.get("quality_summary", {}).get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)

        for metric_id, metric_summary in calibration_summary.get(
            "metric_calibrations", {}
        ).items():
            for warning in metric_summary.get("warnings", []):
                if warning not in warnings:
                    warnings.append(warning)
            try:
                metric_definition = build_supported_outcome_metric(metric_id)
            except ValueError:
                if "unknown_confidence_metric_definition" not in warnings:
                    warnings.append("unknown_confidence_metric_definition")
                continue
            if metric_definition.confidence_support.get("calibration_supported") is not True:
                if "unsupported_confidence_contract" not in warnings:
                    warnings.append("unsupported_confidence_contract")
                continue
            supported_metric_ids.append(metric_id)
            readiness = metric_summary.get("readiness", {})
            if readiness.get("ready") is True:
                ready_metric_ids.append(metric_id)
            else:
                not_ready_metric_ids.append(metric_id)
                for reason in readiness.get("gating_reasons", []):
                    if reason not in gating_reasons:
                        gating_reasons.append(reason)

        if ready_metric_ids:
            status["status"] = "ready"
        elif not supported_metric_ids:
            gating_reasons.append("no_supported_binary_metrics")

        status["supported_metric_ids"] = supported_metric_ids
        status["ready_metric_ids"] = ready_metric_ids
        status["not_ready_metric_ids"] = not_ready_metric_ids
        status["gating_reasons"] = gating_reasons
        status["warnings"] = warnings
        return status

    def _build_ready_calibrated_summary(
        self,
        summary: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not summary:
            return None

        ready_metrics = []
        for metric_id, metric_summary in summary.get("metric_calibrations", {}).items():
            readiness = metric_summary.get("readiness", {})
            if readiness.get("ready") is not True:
                continue
            try:
                metric_definition = build_supported_outcome_metric(metric_id)
            except ValueError:
                continue
            if metric_definition.confidence_support.get("calibration_supported") is not True:
                continue
            ready_metrics.append(
                {
                    "metric_id": metric_id,
                    "label": metric_definition.label,
                    "case_count": metric_summary.get("case_count", 0),
                    "supported_scoring_rules": metric_summary.get(
                        "supported_scoring_rules",
                        [],
                    ),
                    "scores": metric_summary.get("scores", {}),
                    "diagnostics": metric_summary.get("diagnostics", {}),
                    "reliability_bins": metric_summary.get("reliability_bins", []),
                    "readiness": readiness,
                    "warnings": metric_summary.get("warnings", []),
                    "provenance": {
                        "mode": "calibrated",
                        "label": "Backtested calibration summary",
                        "artifact_type": summary.get("artifact_type"),
                    },
                }
            )

        if not ready_metrics:
            return None

        return {
            "artifact_type": summary.get("artifact_type", "calibration_summary"),
            "scope": "ensemble",
            "quality_summary": summary.get("quality_summary", {}),
            "metrics": ready_metrics,
            "provenance": {
                "mode": "calibrated",
                "label": "Backtested calibration summary",
                "artifact_type": summary.get("artifact_type", "calibration_summary"),
            },
        }

    def _build_run_lookup(
        self,
        ensemble_payload: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        run_lookup: Dict[str, Dict[str, Any]] = {}
        for run_payload in ensemble_payload.get("runs", []):
            metrics_path = os.path.join(run_payload["run_dir"], "metrics.json")
            metrics_payload = None
            if os.path.exists(metrics_path):
                try:
                    metrics_payload = self._read_json(metrics_path)
                except (json.JSONDecodeError, OSError):
                    metrics_payload = None

            run_lookup[run_payload["run_id"]] = {
                **run_payload,
                "metrics": metrics_payload,
                "metrics_relpath": (
                    os.path.relpath(metrics_path, ensemble_payload["ensemble_dir"])
                    if os.path.exists(metrics_path)
                    else None
                ),
            }
        return run_lookup

    def _resolve_selected_run(
        self,
        run_lookup: Dict[str, Dict[str, Any]],
        requested_run_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if requested_run_id:
            payload = run_lookup.get(str(requested_run_id).strip())
            return self._build_run_snapshot(payload) if payload else None

        return None

    def _build_run_snapshot(self, run_payload: Dict[str, Any]) -> Dict[str, Any]:
        manifest = run_payload.get("run_manifest", {})
        metrics = run_payload.get("metrics") or {}
        quality = metrics.get("quality_checks", {})
        warnings = list(quality.get("warnings", []))
        if not metrics:
            warnings.append("missing_run_metrics")
        elif quality.get("status") != "complete":
            warnings.append("degraded_runs_present")

        metric_values = metrics.get("metric_values", {})
        key_metrics = []
        for metric_id, entry in metric_values.items():
            normalized_entry = (
                dict(entry)
                if isinstance(entry, dict)
                else {"metric_id": metric_id, "value": entry}
            )
            normalized_entry.setdefault("metric_id", metric_id)
            key_metrics.append(normalized_entry)

        key_metrics.sort(
            key=lambda item: (
                -float(item.get("value", 0))
                if isinstance(item.get("value"), (int, float))
                else 0.0,
                item.get("metric_id", ""),
            )
        )

        return {
            "scope": "run",
            "run_id": run_payload.get("run_id"),
            "status": manifest.get("status", "unknown"),
            "resolved_values": manifest.get("resolved_values", {}),
            "assumption_ledger": manifest.get("assumption_ledger", {}),
            "top_topics": metrics.get("top_topics", []),
            "key_metrics": key_metrics,
            "support": {
                "has_metrics": bool(metrics),
                "quality_status": quality.get("status", "missing")
                if metrics
                else "missing",
                "key_metric_count": len(key_metrics),
            },
            "warnings": warnings,
            "provenance": {
                "mode": "observed",
                "label": "Observed single-run outcome",
                "artifact_type": "metrics.json" if metrics else "run_manifest.json",
            },
        }

    def _extract_metric_value_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        keys = [
            "mean",
            "min",
            "max",
            "quantiles",
            "empirical_probability",
            "dominant_value",
            "dominant_probability",
            "counts",
            "category_counts",
            "category_probabilities",
        ]
        return {
            key: summary[key]
            for key in keys
            if key in summary
        }

    def _derive_generated_at(
        self,
        aggregate_summary: Dict[str, Any],
        scenario_clusters: Dict[str, Any],
        sensitivity: Dict[str, Any],
    ) -> str:
        timestamps = [
            aggregate_summary.get("generated_at"),
            scenario_clusters.get("generated_at"),
            sensitivity.get("generated_at"),
        ]
        timestamps = [timestamp for timestamp in timestamps if timestamp]
        if timestamps:
            return max(timestamps)
        return "1970-01-01T00:00:00"

    def _read_json(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, file_path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
