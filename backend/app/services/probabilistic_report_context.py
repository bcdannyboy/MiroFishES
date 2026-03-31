"""
Probabilistic report-context builder.

This service packages the already-persisted ensemble analytics into one
report-context artifact that Step 4 and Step 5 can consume without having to
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
FORECAST_WORKSPACE_CALIBRATION_BOUNDARY_NOTE = (
    "Calibrated confidence is only earned when a forecast answer is explicitly marked "
    "calibrated and carries ready backtest and calibration metadata on a supported "
    "evaluation lane with resolved cases."
)


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

    @staticmethod
    def _get_answer_confidence_semantics(answer: Any) -> str:
        if isinstance(answer, dict):
            return str(answer.get("confidence_semantics") or "").strip()
        return str(getattr(answer, "confidence_semantics", "") or "").strip()

    @classmethod
    def _workspace_calibrated_confidence_earned(
        cls,
        *,
        latest_answer: Any,
        confidence_basis: Dict[str, Any],
        calibration_summary: Dict[str, Any],
    ) -> bool:
        if latest_answer is None:
            return False
        confidence_semantics = cls._get_answer_confidence_semantics(latest_answer)
        confidence_status = str(confidence_basis.get("status") or "").strip()
        resolved_case_count = int(confidence_basis.get("resolved_case_count") or 0)
        calibration_status = str(calibration_summary.get("status") or "").strip()
        benchmark_status = str(confidence_basis.get("benchmark_status") or "").strip()
        backtest_status = str(confidence_basis.get("backtest_status") or "").strip()
        return (
            confidence_semantics == "calibrated"
            and confidence_status == "available"
            and resolved_case_count > 0
            and calibration_status == "ready"
            and benchmark_status in {"available", "ready"}
            and backtest_status in {"available", "ready"}
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
        try:
            from .forecast_manager import ForecastManager

            forecast_manager = ForecastManager()
            linked_forecast_questions = forecast_manager.list_question_summaries_for_simulation(
                simulation_id
            )
        except Exception:
            linked_forecast_questions = []
            forecast_manager = None
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
        confidence_inspection = self._inspect_confidence_artifacts(
            ensemble_dir=ensemble_payload["ensemble_dir"],
            simulation_id=simulation_id,
            ensemble_id=normalized_ensemble_id,
        )
        calibration_summary = confidence_inspection.get("calibration_summary")
        confidence_status = self._build_confidence_status(confidence_inspection)
        calibrated_summary = (
            self._build_ready_calibrated_summary(calibration_summary)
            if confidence_status.get("artifact_readiness", {})
            .get("provenance", {})
            .get("status")
            == "valid"
            else None
        )
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
        forecast_workspace = self._build_forecast_workspace_context(
            forecast_manager=forecast_manager,
            linked_forecast_questions=linked_forecast_questions,
            confidence_status=confidence_status,
        )
        forecast_object = self._build_forecast_object_summary(forecast_workspace)
        selected_run_market = (
            selected_run.get("simulation_market") or {}
            if isinstance(selected_run, dict)
            else {}
        )
        simulation_market_summary = (
            selected_run_market.get("summary")
            if isinstance(selected_run_market, dict)
            else None
        )
        signal_provenance_summary = (
            selected_run_market.get("provenance_validation")
            if isinstance(selected_run_market, dict)
            else None
        )
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
                "cluster_share": "observed_run_share",
                "runs": "observed",
                "sensitivity": "observational",
                **(
                    {"calibration": "backtested"}
                    if confidence_status.get("status") == "ready"
                    else {}
                ),
            },
            "confidence_status": confidence_status,
            "simulation_role": {
                "worker": "simulation",
                "mode": "worker_composed",
                "summary": (
                    "Simulation contributes scenario evidence as one forecast worker. Saved artifacts define scope and evidence boundaries; they do not turn simulation frequencies into earned real-world probabilities."
                ),
            },
            "forecast_workspace": forecast_workspace,
            "forecast_object": forecast_object,
            "simulation_market_summary": simulation_market_summary,
            "signal_provenance_summary": signal_provenance_summary,
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
            "linked_forecast_questions": linked_forecast_questions,
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
                    if confidence_status.get("artifact_readiness", {})
                    .get("calibration_summary", {})
                    .get("status")
                    != "absent"
                    else {}
                ),
                **(
                    {"backtest_summary": self.ensemble_manager.BACKTEST_SUMMARY_FILENAME}
                    if confidence_status.get("artifact_readiness", {})
                    .get("backtest_summary", {})
                    .get("status")
                    != "absent"
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

    @staticmethod
    def _build_empty_forecast_workspace_context() -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "boundary_note": (
                "No linked forecast-question workspace is attached to this simulation scope."
            ),
            "supported_question_types": [],
            "supported_question_templates": [],
            "linked_forecast_count": 0,
            "linked_forecast_questions": [],
            "linked_forecasts": [],
            "selected_forecast_id": None,
            "selected_forecast": None,
            "simulation_role_note": (
                "Simulation remains available as supporting scenario analysis whether or not a linked forecast workspace exists."
            ),
        }

    def _build_forecast_workspace_context(
        self,
        *,
        forecast_manager: Any,
        simulation_id: str,
    ) -> Dict[str, Any]:
        from ..models.forecasting import get_forecast_capabilities_domain

        workspaces = [
            workspace
            for workspace in forecast_manager.list_workspaces()
            if workspace.forecast_question.primary_simulation_id == simulation_id
        ]
        workspaces.sort(
            key=self._forecast_workspace_sort_key,
            reverse=True,
        )
        linked_forecasts = [
            self._build_linked_forecast_summary(workspace) for workspace in workspaces
        ]
        selected_forecast = linked_forecasts[0] if linked_forecasts else None
        capabilities = get_forecast_capabilities_domain()

        return {
            "status": "available" if linked_forecasts else "unavailable",
            "boundary_note": (
                "Linked forecast workspaces summarize bounded question, evidence, ledger, and evaluation state for this simulation. They do not upgrade simulation-only scenario evidence into calibrated confidence."
            ),
            "supported_question_types": list(
                capabilities.get("supported_question_types", [])
            ),
            "supported_question_templates": list(
                capabilities.get("supported_question_templates", [])
            ),
            "linked_forecast_count": len(linked_forecasts),
            "linked_forecast_questions": [
                {
                    "forecast_id": item.get("forecast_id"),
                    "title": item.get("title"),
                    "question_text": item.get("question_text"),
                    "question_status": item.get("question_status"),
                    "issue_timestamp": item.get("issue_timestamp"),
                    "resolution_status": item.get("resolution_status"),
                    "prediction_entry_count": item.get("prediction_ledger", {}).get(
                        "entry_count",
                        0,
                    ),
                    "worker_kinds": item.get("worker_kinds", []),
                }
                for item in linked_forecasts
            ],
            "linked_forecasts": linked_forecasts,
            "selected_forecast_id": (
                selected_forecast.get("forecast_id") if selected_forecast else None
            ),
            "selected_forecast": selected_forecast,
            "forecast_question": (
                {
                    "forecast_id": selected_forecast.get("forecast_id"),
                    "title": selected_forecast.get("title"),
                    "question_text": selected_forecast.get("question_text"),
                    "question_type": selected_forecast.get("question_type"),
                    "horizon": selected_forecast.get("horizon"),
                    "issue_timestamp": selected_forecast.get("issue_timestamp"),
                    "owner": selected_forecast.get("owner"),
                    "source": selected_forecast.get("source"),
                    "question_status": selected_forecast.get("question_status"),
                    "abstention_conditions": selected_forecast.get(
                        "abstention_conditions",
                        [],
                    ),
                    "supported_question_templates": list(
                        capabilities.get("supported_question_templates", [])
                    ),
                }
                if selected_forecast
                else None
            ),
            "evidence_bundle": (
                selected_forecast.get("evidence_bundle") if selected_forecast else None
            ),
            "prediction_ledger": (
                selected_forecast.get("prediction_ledger") if selected_forecast else None
            ),
            "evaluation_results": (
                selected_forecast.get("evaluation") if selected_forecast else None
            ),
            "forecast_answer": (
                {
                    **(selected_forecast.get("latest_answer") or {}),
                    "answer_payload": {
                        "best_estimate": (
                            (selected_forecast.get("latest_answer") or {}).get(
                                "best_estimate"
                            )
                        ),
                        "abstain": (
                            (selected_forecast.get("latest_answer") or {}).get("abstain")
                        ),
                        "abstain_reason": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("abstain_reason")
                        ),
                        "counterevidence": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("counterevidence", [])
                        ),
                        "assumption_summary": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("assumption_summary", {})
                        ),
                        "uncertainty_decomposition": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("uncertainty_decomposition", {})
                        ),
                        "evaluation_summary": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("evaluation_summary", {})
                        ),
                        "confidence_basis": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("confidence_basis", {})
                        ),
                        "simulation_context": (
                            (
                                selected_forecast.get("latest_answer") or {}
                            ).get("simulation_context", {})
                        ),
                    },
                }
                if selected_forecast
                else None
            ),
            "worker_comparison": (
                {
                    "worker_count": len(selected_forecast.get("worker_kinds", [])),
                    "worker_kinds": selected_forecast.get("worker_kinds", []),
                    "worker_contribution_trace": (
                        (
                            selected_forecast.get("latest_answer") or {}
                        ).get("worker_contribution_trace", [])
                    ),
                    "abstain": (
                        (selected_forecast.get("latest_answer") or {}).get("abstain")
                    ),
                    "abstain_reason": (
                        (
                            selected_forecast.get("latest_answer") or {}
                        ).get("abstain_reason")
                    ),
                    "best_estimate": (
                        (
                            selected_forecast.get("latest_answer") or {}
                        ).get("best_estimate")
                    ),
                    "simulation_context": (
                        (
                            selected_forecast.get("latest_answer") or {}
                        ).get("simulation_context")
                    ),
                }
                if selected_forecast
                else None
            ),
            "truthfulness_surface": (
                {
                    "evidence_available": selected_forecast.get("status_matrix", {}).get(
                        "evidence_available",
                        False,
                    ),
                    "evaluation_available": selected_forecast.get("status_matrix", {}).get(
                        "evaluation_available",
                        False,
                    ),
                    "calibrated_confidence_earned": selected_forecast.get(
                        "status_matrix",
                        {},
                    ).get("calibrated_confidence_earned", False),
                    "simulation_only_scenario_exploration": selected_forecast.get(
                        "status_matrix",
                        {},
                    ).get("simulation_only_scenario_exploration", False),
                    "boundary_note": (
                        "Evidence availability, evaluation availability, calibrated confidence, and simulation-only scenario exploration remain distinct surfaces."
                    ),
                }
                if selected_forecast
                else None
            ),
            "simulation_role_note": (
                "Simulation remains visible here as supporting scenario analysis, not the default answer source."
            ),
        }

    @staticmethod
    def _forecast_workspace_sort_key(workspace: Any) -> tuple[str, str, str]:
        latest_answer_at = ""
        if getattr(workspace, "forecast_answers", None):
            latest_answer_at = max(
                [
                    item.created_at
                    for item in workspace.forecast_answers
                    if getattr(item, "created_at", None)
                ],
                default="",
            )

        return (
            latest_answer_at or "",
            getattr(workspace.forecast_question, "updated_at", "") or "",
            getattr(workspace.forecast_question, "issue_timestamp", "") or "",
        )

    def _build_linked_forecast_summary(self, workspace: Any) -> Dict[str, Any]:
        question = workspace.forecast_question
        evidence_bundle = workspace.evidence_bundle
        ledger = workspace.prediction_ledger
        latest_answer = (
            max(
                workspace.forecast_answers,
                key=lambda item: getattr(item, "created_at", "") or "",
            )
            if workspace.forecast_answers
            else None
        )
        latest_answer_payload = (
            dict(latest_answer.answer_payload)
            if latest_answer is not None and isinstance(latest_answer.answer_payload, dict)
            else {}
        )
        worker_trace = latest_answer_payload.get("worker_contribution_trace", [])
        if not isinstance(worker_trace, list):
            worker_trace = []
        influential_non_simulation_workers = [
            item
            for item in worker_trace
            if isinstance(item, dict)
            and item.get("worker_kind") != "simulation"
            and item.get("influences_best_estimate")
        ]
        why_summary = [
            item.get("summary", "")
            for item in influential_non_simulation_workers
            if str(item.get("summary", "")).strip()
        ]
        if not why_summary and latest_answer is not None:
            why_summary = [latest_answer.summary]

        evaluation_summary = (
            dict(latest_answer.evaluation_summary)
            if latest_answer is not None and isinstance(latest_answer.evaluation_summary, dict)
            else {
                "status": (
                    "available"
                    if any(case.status == "resolved" for case in workspace.evaluation_cases)
                    else "partial"
                    if workspace.evaluation_cases
                    else "unavailable"
                ),
                "case_count": len(workspace.evaluation_cases),
                "resolved_case_count": len(
                    [case for case in workspace.evaluation_cases if case.status == "resolved"]
                ),
            }
        )
        confidence_basis = (
            dict(latest_answer.confidence_basis)
            if latest_answer is not None and isinstance(latest_answer.confidence_basis, dict)
            else {}
        )
        calibration_summary = (
            dict(latest_answer.calibration_summary)
            if latest_answer is not None and isinstance(latest_answer.calibration_summary, dict)
            else {}
        )
        prediction_entries = list(getattr(ledger, "entries", []))
        worker_outputs = list(getattr(ledger, "worker_outputs", []))
        resolution_criteria = [
            {
                "criteria_id": item.criteria_id,
                "label": item.label,
                "criteria_type": item.criteria_type,
                "resolution_date": item.resolution_date,
            }
            for item in workspace.resolution_criteria
        ]

        calibrated_confidence_earned = self._workspace_calibrated_confidence_earned(
            latest_answer=latest_answer,
            confidence_basis=confidence_basis,
            calibration_summary=calibration_summary,
        )
        simulation_only_scenario_exploration = bool(
            latest_answer_payload.get("simulation_context", {}).get("included")
        ) and not influential_non_simulation_workers

        latest_prediction_time = max(
            [item.recorded_at for item in prediction_entries if getattr(item, "recorded_at", None)],
            default=None,
        )
        latest_worker_output_time = max(
            [
                str(item.get("recorded_at"))
                for item in worker_outputs
                if isinstance(item, dict) and item.get("recorded_at")
            ],
            default=None,
        )

        return {
            "forecast_id": question.forecast_id,
            "title": question.title,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "horizon": question.horizon,
            "issue_timestamp": question.issue_timestamp,
            "owner": question.owner,
            "source": question.source,
            "question_status": question.status,
            "resolution_status": ledger.resolution_status,
            "decomposition_support_count": len(question.decomposition_support)
            or len(question.decomposition.get("subquestion_ids", [])),
            "abstention_conditions": list(question.abstention_conditions),
            "resolution_criteria": resolution_criteria,
            "worker_kinds": [item.kind for item in workspace.forecast_workers],
            "evidence_bundle": {
                "bundle_id": evidence_bundle.bundle_id,
                "status": evidence_bundle.status,
                "title": evidence_bundle.title,
                "summary": evidence_bundle.summary,
                "source_entry_count": len(evidence_bundle.source_entries),
                "provider_count": len(evidence_bundle.provider_snapshots),
                "retrieval_quality_status": evidence_bundle.retrieval_quality.get("status"),
                "conflict_marker_count": len(evidence_bundle.conflict_markers),
                "missing_evidence_count": len(evidence_bundle.missing_evidence_markers),
                "uncertainty_causes": list(
                    evidence_bundle.uncertainty_summary.get("causes", [])
                ),
                "boundary_note": evidence_bundle.boundary_note,
                "source_entries": [
                    item.to_dict()
                    if hasattr(item, "to_dict")
                    else dict(item)
                    if isinstance(item, dict)
                    else {}
                    for item in evidence_bundle.source_entries[:5]
                ],
                "provider_snapshots": [
                    item.to_dict()
                    if hasattr(item, "to_dict")
                    else dict(item)
                    if isinstance(item, dict)
                    else {}
                    for item in evidence_bundle.provider_snapshots[:5]
                ],
            },
            "prediction_ledger": {
                "entry_count": len(prediction_entries),
                "worker_output_count": len(worker_outputs),
                "resolution_status": ledger.resolution_status,
                "latest_prediction_recorded_at": latest_prediction_time,
                "latest_worker_output_recorded_at": latest_worker_output_time,
                "entries": [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in prediction_entries[:5]
                ],
                "worker_outputs": [
                    dict(item) if isinstance(item, dict) else {}
                    for item in worker_outputs[:5]
                ],
                "resolution_history": [
                    dict(item) if isinstance(item, dict) else {}
                    for item in list(getattr(ledger, "resolution_history", []))[:5]
                ],
            },
            "evaluation": {
                "status": evaluation_summary.get("status", "unavailable"),
                "case_count": evaluation_summary.get("case_count", len(workspace.evaluation_cases)),
                "resolved_case_count": evaluation_summary.get(
                    "resolved_case_count",
                    len([case for case in workspace.evaluation_cases if case.status == "resolved"]),
                ),
                "question_classes": list(evaluation_summary.get("question_classes", [])),
                "split_ids": list(evaluation_summary.get("split_ids", [])),
                "window_ids": list(evaluation_summary.get("window_ids", [])),
                "cases": [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in workspace.evaluation_cases[:5]
                ],
            },
            "status_matrix": {
                "evidence_available": evidence_bundle.status in {"available", "partial"},
                "evaluation_available": bool(
                    (evaluation_summary.get("resolved_case_count", 0) or 0) > 0
                ),
                "calibrated_confidence_earned": calibrated_confidence_earned,
                "simulation_only_scenario_exploration": simulation_only_scenario_exploration,
            },
            "latest_answer": (
                {
                    "answer_id": latest_answer.answer_id,
                    "answer_type": latest_answer.answer_type,
                    "summary": latest_answer.summary,
                    "created_at": latest_answer.created_at,
                    "confidence_semantics": latest_answer.confidence_semantics,
                    "worker_ids": list(latest_answer.worker_ids),
                    "prediction_entry_ids": list(latest_answer.prediction_entry_ids),
                    "best_estimate": latest_answer_payload.get("best_estimate"),
                    "abstain": bool(
                        latest_answer_payload.get("abstain", latest_answer_payload.get("abstained"))
                    ),
                    "abstain_reason": latest_answer_payload.get("abstain_reason"),
                    "why_summary": why_summary,
                    "counterevidence": list(latest_answer_payload.get("counterevidence", [])),
                    "assumption_summary": dict(
                        latest_answer_payload.get("assumption_summary", {})
                    ),
                    "uncertainty_decomposition": dict(
                        latest_answer_payload.get("uncertainty_decomposition", {})
                    ),
                    "worker_contribution_trace": worker_trace,
                    "simulation_context": dict(
                        latest_answer_payload.get("simulation_context", {})
                    ),
                    "confidence_basis": confidence_basis,
                    "evaluation_summary": evaluation_summary,
                    "benchmark_summary": dict(latest_answer.benchmark_summary),
                    "backtest_summary": dict(latest_answer.backtest_summary),
                    "calibration_summary": calibration_summary,
                }
                if latest_answer is not None
                else None
            ),
        }

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
                numeric_sort_value = summary.get(
                    "observed_true_share",
                    summary.get("empirical_probability"),
                )
            if numeric_sort_value is None:
                numeric_sort_value = summary.get(
                    "dominant_observed_share",
                    summary.get("dominant_probability"),
                )
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
                    "observed_run_share": cluster.get(
                        "observed_run_share",
                        cluster.get("probability_mass"),
                    ),
                    "share_semantics": cluster.get(
                        "share_semantics",
                        "observed_run_share",
                    ),
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
                    "support_assessment": cluster.get("support_assessment", {}),
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
            "support_assessment": sensitivity.get("quality_summary", {}).get(
                "support_assessment",
                {},
            ),
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
                "support_assessment": driver.get("support_assessment", {}),
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
            "support_assessment": sensitivity.get("quality_summary", {}).get(
                "support_assessment",
                {},
            ),
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
                            "observed run share, representative runs, distinguishing metrics, "
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
                        "observed run share, representative runs, distinguishing metrics, "
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

    def _build_supported_question_templates(
        self,
        forecast_question: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        templates: List[Dict[str, Any]] = []
        decomposition_support = forecast_question.get("decomposition_support") or []
        abstention_conditions = [
            str(item).strip()
            for item in (forecast_question.get("abstention_conditions") or [])
            if str(item).strip()
        ]

        for index, item in enumerate(decomposition_support):
            if not isinstance(item, dict):
                continue
            question_text = item.get("question_text") or forecast_question.get("question_text")
            templates.append(
                {
                    "template_id": item.get("template_id") or f"{forecast_question.get('forecast_id')}-template-{index + 1}",
                    "label": item.get("label") or f"Template {index + 1}",
                    "question_text": question_text,
                    "question_type": item.get("question_type") or forecast_question.get("question_type"),
                    "resolution_criteria_ids": item.get("resolution_criteria_ids") or list(
                        forecast_question.get("resolution_criteria_ids") or []
                    ),
                    "abstention_conditions": item.get("abstention_conditions") or abstention_conditions,
                    "source": item.get("source") or forecast_question.get("source"),
                    "owner": item.get("owner") or forecast_question.get("owner"),
                }
            )

        if not templates:
            templates.append(
                {
                    "template_id": f"{forecast_question.get('forecast_id')}-primary",
                    "label": forecast_question.get("title") or "Primary forecast question",
                    "question_text": forecast_question.get("question_text"),
                    "question_type": forecast_question.get("question_type"),
                    "resolution_criteria_ids": list(
                        forecast_question.get("resolution_criteria_ids") or []
                    ),
                    "abstention_conditions": abstention_conditions,
                    "source": forecast_question.get("source"),
                    "owner": forecast_question.get("owner"),
                }
            )

        return templates

    def _build_forecast_workspace_context(
        self,
        *,
        forecast_manager,
        linked_forecast_questions: List[Dict[str, Any]],
        confidence_status: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if forecast_manager is None or not linked_forecast_questions:
            return None

        sorted_questions = sorted(
            [
                question
                for question in linked_forecast_questions
                if isinstance(question, dict) and question.get("forecast_id")
            ],
            key=lambda item: (
                item.get("updated_at") or item.get("created_at") or item.get("issue_timestamp") or "",
                item.get("forecast_id") or "",
            ),
            reverse=True,
        )
        if not sorted_questions:
            return None

        primary_forecast_id = sorted_questions[0]["forecast_id"]
        try:
            workspace = forecast_manager.get_workspace(primary_forecast_id)
        except Exception:
            workspace = None
        if workspace is None:
            return None

        workspace_payload = workspace.to_dict()
        forecast_question = dict(workspace_payload.get("forecast_question") or {})
        forecast_question["supported_question_templates"] = self._build_supported_question_templates(
            forecast_question
        )
        forecast_answers = list(workspace_payload.get("forecast_answers") or [])
        latest_answer = forecast_answers[-1] if forecast_answers else None
        latest_answer_payload = dict((latest_answer or {}).get("answer_payload") or {})
        worker_trace = list(latest_answer_payload.get("worker_contribution_trace") or [])
        evidence_bundle = dict(workspace_payload.get("evidence_bundle") or {})
        prediction_ledger = dict(workspace_payload.get("prediction_ledger") or {})
        prediction_ledger = {
            **prediction_ledger,
            "entry_count": len(prediction_ledger.get("entries") or []),
            "worker_output_count": len(prediction_ledger.get("worker_outputs") or []),
            "resolution_history_count": len(
                prediction_ledger.get("resolution_history") or []
            ),
        }
        evaluation_cases = list(workspace_payload.get("evaluation_cases") or [])
        forecast_workers = list(workspace_payload.get("forecast_workers") or [])
        simulation_worker_contract = workspace_payload.get("simulation_worker_contract")
        truthfulness_surface = {
            "evidence_available": bool(
                evidence_bundle.get("status") in {"ready", "partial"}
                or evidence_bundle.get("source_entries")
                or evidence_bundle.get("entries")
            ),
            "evaluation_available": bool(
                evaluation_cases
                or latest_answer_payload.get("evaluation_summary", {}).get("resolved_case_count")
                or latest_answer_payload.get("confidence_basis", {}).get("resolved_case_count")
            ),
            "calibrated_confidence_earned": self._workspace_calibrated_confidence_earned(
                latest_answer=latest_answer,
                confidence_basis=dict(latest_answer_payload.get("confidence_basis", {})),
                calibration_summary=dict(
                    (latest_answer or {}).get("calibration_summary", {})
                ),
            ),
            "simulation_only_scenario_exploration": bool(
                latest_answer_payload.get("abstain")
                or latest_answer_payload.get("abstained")
                or (
                    forecast_workers
                    and all(str(worker.get("kind")) == "simulation" for worker in forecast_workers if isinstance(worker, dict))
                )
            ),
            "boundary_note": FORECAST_WORKSPACE_CALIBRATION_BOUNDARY_NOTE,
        }

        workspace_payload.update(
            {
                "forecast_question": forecast_question,
                "forecast_answer": latest_answer,
                "forecast_workspace_status": "available",
                "supported_question_templates": list(forecast_question.get("supported_question_templates", [])),
                "truthfulness_surface": truthfulness_surface,
                "prediction_ledger": prediction_ledger,
                "worker_comparison": {
                    "worker_count": len(forecast_workers),
                    "worker_kinds": [
                        str(worker.get("kind") or "").strip()
                        for worker in forecast_workers
                        if isinstance(worker, dict) and str(worker.get("kind") or "").strip()
                    ],
                    "worker_contribution_trace": worker_trace,
                    "simulation_worker_contract": simulation_worker_contract,
                    "best_estimate": latest_answer_payload.get("best_estimate"),
                    "abstain": bool(
                        latest_answer_payload.get("abstain")
                        or latest_answer_payload.get("abstained")
                    ),
                    "abstain_reason": latest_answer_payload.get("abstain_reason"),
                    "simulation_context": latest_answer_payload.get("simulation_context"),
                },
                "abstain_state": {
                    "abstain": bool(
                        latest_answer_payload.get("abstain")
                        or latest_answer_payload.get("abstained")
                    ),
                    "abstain_reason": latest_answer_payload.get("abstain_reason"),
                    "summary": latest_answer.get("summary") if isinstance(latest_answer, dict) else "",
                },
                "evaluation_results": {
                    "status": "available" if evaluation_cases else "unavailable",
                    "case_count": len(evaluation_cases),
                    "resolved_case_count": len(
                        [case for case in evaluation_cases if isinstance(case, dict) and case.get("status") == "resolved"]
                    ),
                    "pending_case_count": len(
                        [case for case in evaluation_cases if isinstance(case, dict) and case.get("status") != "resolved"]
                    ),
                    "cases": evaluation_cases,
                },
            }
        )
        return workspace_payload

    @staticmethod
    def _build_forecast_object_summary(
        forecast_workspace: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(forecast_workspace, dict):
            return None

        forecast_question = forecast_workspace.get("forecast_question")
        if not isinstance(forecast_question, dict):
            forecast_question = {}
        forecast_answer = forecast_workspace.get("forecast_answer")
        if not isinstance(forecast_answer, dict):
            forecast_answer = {}
        resolution_record = forecast_workspace.get("resolution_record")
        if not isinstance(resolution_record, dict):
            resolution_record = {}
        scoring_events = [
            item
            for item in (forecast_workspace.get("scoring_events") or [])
            if isinstance(item, dict)
        ]
        latest_scoring = scoring_events[-1] if scoring_events else {}

        return {
            "forecast_id": forecast_question.get("forecast_id"),
            "status": "available",
            "question_text": forecast_question.get("question_text"),
            "latest_answer_id": forecast_answer.get("answer_id"),
            "resolution": {
                "status": resolution_record.get("status", "pending"),
                "resolved_at": resolution_record.get("resolved_at"),
                "resolution_note": resolution_record.get("resolution_note"),
            },
            "scoring": {
                "event_count": len(scoring_events),
                "latest_method": latest_scoring.get("scoring_method"),
                "latest_score_value": latest_scoring.get("score_value"),
            },
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

    def _inspect_confidence_artifacts(
        self,
        *,
        ensemble_dir: str,
        simulation_id: str,
        ensemble_id: str,
    ) -> Dict[str, Any]:
        artifact_readiness = {
            "calibration_summary": {
                "status": "absent",
                "reason": "No calibration summary artifact is attached to this ensemble.",
            },
            "backtest_summary": {
                "status": "absent",
                "reason": "No backtest summary artifact is attached to this ensemble.",
            },
            "provenance": {
                "status": "absent",
                "reason": (
                    "Calibration provenance cannot be verified without a valid "
                    "calibration summary artifact."
                ),
            },
        }
        inspection = {
            "calibration_summary": None,
            "backtest_summary": None,
            "artifact_readiness": artifact_readiness,
            "gating_reasons": [],
            "warnings": [],
        }

        calibration_path = os.path.join(
            ensemble_dir,
            self.ensemble_manager.CALIBRATION_SUMMARY_FILENAME,
        )
        backtest_path = os.path.join(
            ensemble_dir,
            self.ensemble_manager.BACKTEST_SUMMARY_FILENAME,
        )

        if os.path.exists(calibration_path):
            try:
                inspection["calibration_summary"] = self.ensemble_manager.load_calibration_summary(
                    simulation_id,
                    ensemble_id,
                )
            except (ValueError, OSError, json.JSONDecodeError):
                artifact_readiness["calibration_summary"] = {
                    "status": "invalid",
                    "reason": (
                        "Calibration summary failed validation and cannot support "
                        "confidence surfaces."
                    ),
                }
                artifact_readiness["provenance"] = {
                    "status": "invalid",
                    "reason": (
                        "Calibration provenance cannot be trusted until the calibration "
                        "summary validates."
                    ),
                }
                inspection["gating_reasons"].append("invalid_calibration_artifact")
                inspection["warnings"].append("invalid_calibration_artifact")
            else:
                artifact_readiness["calibration_summary"] = {
                    "status": "valid",
                    "reason": "",
                }
        else:
            inspection["gating_reasons"].append("missing_calibration_artifact")

        if os.path.exists(backtest_path):
            try:
                inspection["backtest_summary"] = self.ensemble_manager.load_backtest_summary(
                    simulation_id,
                    ensemble_id,
                )
            except (ValueError, OSError, json.JSONDecodeError):
                artifact_readiness["backtest_summary"] = {
                    "status": "invalid",
                    "reason": (
                        "Backtest summary failed validation and cannot anchor "
                        "confidence provenance."
                    ),
                }
                inspection["warnings"].append("invalid_backtest_artifact")
                if "invalid_calibration_artifact" not in inspection["warnings"]:
                    artifact_readiness["provenance"] = {
                        "status": "invalid",
                        "reason": (
                            "Calibration provenance cannot be trusted until the backtest "
                            "summary validates."
                        ),
                    }
                    inspection["gating_reasons"].append("invalid_backtest_artifact")
            else:
                artifact_readiness["backtest_summary"] = {
                    "status": "valid",
                    "reason": "",
                }
        elif inspection["calibration_summary"] is not None:
            artifact_readiness["provenance"] = {
                "status": "absent",
                "reason": (
                    "Calibration summary cannot support confidence without a valid "
                    "backtest summary artifact."
                ),
            }
            inspection["gating_reasons"].append("missing_backtest_artifact")
            inspection["warnings"].append("missing_backtest_artifact")

        if (
            inspection["calibration_summary"] is not None
            and inspection["backtest_summary"] is not None
        ):
            provenance_issue = self._assess_calibration_provenance(
                calibration_summary=inspection["calibration_summary"],
                backtest_summary=inspection["backtest_summary"],
            )
            if provenance_issue:
                artifact_readiness["provenance"] = provenance_issue
                inspection["gating_reasons"].append(
                    "missing_backtest_provenance"
                    if provenance_issue["status"] == "absent"
                    else "invalid_backtest_provenance"
                )
                inspection["warnings"].append(
                    "missing_backtest_provenance"
                    if provenance_issue["status"] == "absent"
                    else "invalid_backtest_provenance"
                )
            else:
                artifact_readiness["provenance"] = {
                    "status": "valid",
                    "reason": "",
                }

        inspection["gating_reasons"] = self._dedupe_strings(inspection["gating_reasons"])
        inspection["warnings"] = self._dedupe_strings(inspection["warnings"])
        return inspection

    def _assess_calibration_provenance(
        self,
        *,
        calibration_summary: Dict[str, Any],
        backtest_summary: Dict[str, Any],
    ) -> Optional[Dict[str, str]]:
        quality_summary = calibration_summary.get("quality_summary", {})
        source_artifacts = quality_summary.get("source_artifacts", {})
        provenance = quality_summary.get("provenance", {})

        if source_artifacts.get("backtest_summary") != self.ensemble_manager.BACKTEST_SUMMARY_FILENAME:
            return {
                "status": "absent",
                "reason": (
                    "Calibration summary is missing explicit provenance back to "
                    "backtest_summary.json."
                ),
            }

        if not isinstance(provenance, dict):
            return {
                "status": "absent",
                "reason": (
                    "Calibration summary is missing explicit provenance back to "
                    "backtest_summary.json."
                ),
            }

        expected = {
            "backtest_artifact_type": "backtest_summary",
            "backtest_schema_version": backtest_summary.get("schema_version"),
            "backtest_simulation_id": backtest_summary.get("simulation_id"),
            "backtest_ensemble_id": backtest_summary.get("ensemble_id"),
        }
        for key, expected_value in expected.items():
            if provenance.get(key) != expected_value:
                return {
                    "status": "invalid",
                    "reason": (
                        "Calibration summary backtest provenance does not match the "
                        "stored backtest_summary.json artifact."
                    ),
                }
        return None

    def _dedupe_strings(self, values: List[str]) -> List[str]:
        deduped: List[str] = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped

    def _build_confidence_status(
        self,
        confidence_inspection: Dict[str, Any],
    ) -> Dict[str, Any]:
        calibration_summary = confidence_inspection.get("calibration_summary")
        artifact_readiness = confidence_inspection.get("artifact_readiness", {})
        try:
            calibration_status = artifact_readiness.get("calibration_summary", {}).get(
                "status",
                "absent",
            )
        except AttributeError:
            calibration_status = "absent"
        status = {
            "status": "absent" if calibration_status == "absent" else "not_ready",
            "supported_metric_ids": [],
            "ready_metric_ids": [],
            "not_ready_metric_ids": [],
            "gating_reasons": list(confidence_inspection.get("gating_reasons", [])),
            "warnings": list(confidence_inspection.get("warnings", [])),
            "artifact_readiness": artifact_readiness,
            "boundary_note": CALIBRATION_BOUNDARY_NOTE,
        }
        if not calibration_summary:
            return status

        warnings: List[str] = list(status["warnings"])
        gating_reasons: List[str] = list(status["gating_reasons"])
        supported_metric_ids: List[str] = []
        ready_metric_ids: List[str] = []
        not_ready_metric_ids: List[str] = []
        provenance_valid = (
            artifact_readiness.get("provenance", {}).get("status") == "valid"
        )

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
            if readiness.get("ready") is True and provenance_valid:
                ready_metric_ids.append(metric_id)
            else:
                not_ready_metric_ids.append(metric_id)
                for reason in readiness.get("gating_reasons", []):
                    if reason not in gating_reasons:
                        gating_reasons.append(reason)

        if ready_metric_ids and provenance_valid:
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
                "simulation_market": run_payload.get("simulation_market"),
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
            "simulation_market": self._build_run_simulation_market_snapshot(
                run_payload
            ),
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

    def _build_run_simulation_market_snapshot(
        self,
        run_payload: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(run_payload, dict) or not run_payload:
            return None

        simulation_market_payload = run_payload.get("simulation_market")
        if not isinstance(simulation_market_payload, dict) or not simulation_market_payload:
            return None

        manifest = simulation_market_payload.get("simulation_market_manifest")
        market_snapshot = simulation_market_payload.get("market_snapshot")
        disagreement_summary = simulation_market_payload.get("disagreement_summary")
        market_summary = run_payload.get("simulation_market_summary")
        provenance_validation = run_payload.get("simulation_market_provenance")
        if not manifest and not market_snapshot and not disagreement_summary:
            return None

        warnings = []
        if manifest and manifest.get("extraction_status") != "ready":
            warnings.append(
                f"simulation_market:{manifest.get('extraction_status', 'partial')}"
            )

        return {
            "manifest": manifest,
            "market_snapshot": market_snapshot,
            "disagreement_summary": disagreement_summary,
            "summary": market_summary if isinstance(market_summary, dict) else None,
            "provenance_validation": (
                provenance_validation if isinstance(provenance_validation, dict) else None
            ),
            "support": {
                "available": bool(market_snapshot),
                "status": (
                    manifest.get("extraction_status", "partial")
                    if isinstance(manifest, dict)
                    else "partial"
                ),
            },
            "warnings": warnings,
            "provenance": {
                "mode": "observed",
                "label": "Observed synthetic market extraction",
                "artifact_type": (
                    manifest.get("artifact_type")
                    if isinstance(manifest, dict)
                    else "simulation_market_manifest"
                ),
            },
        }

    def _extract_metric_value_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        value_summary: Dict[str, Any] = {}
        for key in [
            "mean",
            "min",
            "max",
            "quantiles",
            "dominant_value",
            "counts",
            "category_counts",
        ]:
            if key in summary:
                value_summary[key] = summary[key]

        observed_true_share = summary.get(
            "observed_true_share",
            summary.get("empirical_probability"),
        )
        if observed_true_share is not None:
            value_summary["observed_true_share"] = observed_true_share

        dominant_observed_share = summary.get(
            "dominant_observed_share",
            summary.get("dominant_probability"),
        )
        if dominant_observed_share is not None:
            value_summary["dominant_observed_share"] = dominant_observed_share

        category_observed_shares = summary.get(
            "category_observed_shares",
            summary.get("category_probabilities"),
        )
        if category_observed_shares is not None:
            value_summary["category_observed_shares"] = category_observed_shares

        return value_summary

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
