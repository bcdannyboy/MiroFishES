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
from .ensemble_manager import EnsembleManager
from .scenario_clusterer import ScenarioClusterer
from .sensitivity_analyzer import SensitivityAnalyzer
from .simulation_manager import SimulationManager


REPORT_CONTEXT_SCHEMA_VERSION = "probabilistic.report_context.v1"
REPORT_CONTEXT_GENERATOR_VERSION = "probabilistic.report_context.generator.v1"


class ProbabilisticReportContextBuilder:
    """Build and persist one ensemble-aware report context artifact."""

    REPORT_CONTEXT_FILENAME = "probabilistic_report_context.json"

    def __init__(self, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        self.ensemble_manager = EnsembleManager(simulation_data_dir=self.simulation_data_dir)
        self.clusterer = ScenarioClusterer(simulation_data_dir=self.simulation_data_dir)
        self.sensitivity_analyzer = SensitivityAnalyzer(
            simulation_data_dir=self.simulation_data_dir
        )

    def get_report_context(
        self,
        simulation_id: str,
        ensemble_id: str,
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
        run_lookup = self._build_run_lookup(ensemble_payload)
        selected_run = self._resolve_selected_run(run_lookup, run_id)

        artifact = {
            "artifact_type": "probabilistic_report_context",
            "schema_version": REPORT_CONTEXT_SCHEMA_VERSION,
            "generator_version": REPORT_CONTEXT_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": normalized_ensemble_id,
            "run_id": run_id,
            "scope": {
                "level": "run" if run_id and selected_run else "ensemble",
                "ensemble_id": normalized_ensemble_id,
                "run_id": selected_run.get("run_id") if selected_run else None,
            },
            "probability_mode": "empirical",
            "probability_semantics": {
                "summary": "empirical",
                "clusters": "empirical",
                "runs": "observed",
                "sensitivity": "observational",
            },
            "prepared_artifact_summary": prepared_artifact_summary,
            "ensemble_facts": self._build_ensemble_facts(
                ensemble_payload=ensemble_payload,
                aggregate_summary=aggregate_summary,
            ),
            "top_outcomes": self._build_top_outcomes(
                aggregate_summary=aggregate_summary,
                prepared_run_count=ensemble_payload.get("state", {}).get(
                    "prepared_run_count",
                    0,
                ),
            ),
            "scenario_families": self._build_scenario_families(
                scenario_clusters=scenario_clusters,
                prepared_run_count=ensemble_payload.get("state", {}).get(
                    "prepared_run_count",
                    0,
                ),
            ),
            "representative_runs": self._build_representative_runs(
                run_lookup=run_lookup,
                scenario_clusters=scenario_clusters,
                selected_run=selected_run,
            ),
            "selected_run": selected_run,
            "sensitivity_overview": self._build_sensitivity_overview(sensitivity),
            "quality_summary": self._build_quality_summary(
                aggregate_summary=aggregate_summary,
                scenario_clusters=scenario_clusters,
                sensitivity=sensitivity,
                selected_run=selected_run,
                requested_run_id=run_id,
            ),
            "aggregate_summary": aggregate_summary,
            "scenario_clusters": scenario_clusters,
            "sensitivity": sensitivity,
            "source_artifacts": {
                "aggregate_summary": self.ensemble_manager.AGGREGATE_SUMMARY_FILENAME,
                "scenario_clusters": self.clusterer.CLUSTERS_FILENAME,
                "sensitivity": self.sensitivity_analyzer.SENSITIVITY_FILENAME,
                "ensemble_state": self.ensemble_manager.ENSEMBLE_STATE_FILENAME,
                "ensemble_spec": self.ensemble_manager.ENSEMBLE_SPEC_FILENAME,
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
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compatibility alias for the report-context task register wording."""
        return self.get_report_context(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )

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
                    "prototype_run_id": cluster.get("prototype_run_id"),
                    "member_run_ids": cluster.get("member_run_ids", []),
                    "probability_mass": cluster.get("probability_mass"),
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
                        "prepared_run_count": prepared_run_count,
                        "label": f"Observed in {run_count} of {prepared_run_count} runs",
                    },
                    "warnings": cluster.get("warnings", []),
                }
            )
        return families

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
                    "sample_count": driver.get("sample_count"),
                    "top_metric_id": top_metric.get("metric_id"),
                    "top_metric_effect_size": top_metric.get("effect_size"),
                }
            )

        return {
            "scope": "ensemble",
            "analysis_mode": sensitivity.get("methodology", {}).get("analysis_mode"),
            "top_drivers": top_drivers,
            "warnings": sensitivity.get("quality_summary", {}).get("warnings", []),
            "provenance": {
                "mode": "observational",
                "label": "Observational sensitivity ranking",
                "artifact_type": sensitivity.get("artifact_type"),
            },
        }

    def _build_quality_summary(
        self,
        *,
        aggregate_summary: Dict[str, Any],
        scenario_clusters: Dict[str, Any],
        sensitivity: Dict[str, Any],
        selected_run: Optional[Dict[str, Any]],
        requested_run_id: Optional[str],
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        component_statuses = [
            aggregate_summary.get("quality_summary", {}).get("status"),
            scenario_clusters.get("quality_summary", {}).get("status"),
            sensitivity.get("quality_summary", {}).get("status"),
        ]

        for component in (
            aggregate_summary.get("quality_summary", {}),
            scenario_clusters.get("quality_summary", {}),
            sensitivity.get("quality_summary", {}),
        ):
            for warning in component.get("warnings", []):
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
            "top_topics": metrics.get("top_topics", []),
            "key_metrics": key_metrics,
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
