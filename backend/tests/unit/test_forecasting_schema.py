from __future__ import annotations

import pytest

from app.models.forecasting import (
    EvidenceBundle,
    EvidenceSourceEntry,
    EvaluationCase,
    ForecastAnswer,
    ForecastQuestion,
    ForecastWorker,
    ForecastWorkspaceRecord,
    PredictionLedger,
    PredictionLedgerEntry,
    ResolutionCriteria,
    SimulationWorkerContract,
    get_forecast_capabilities_domain,
)


QUESTION_ID = "forecast-001"
QUESTION_TEXT = "Will the hybrid system show more than 55% support by June 30, 2026?"
QUESTION_ISSUED_AT = "2026-03-30T09:00:00"
QUESTION_UPDATED_AT = "2026-03-30T09:00:00"
QUESTION_RESOLUTION_DATE = "2026-06-30"
PREDICTION_ONE_ISSUED_AT = "2026-03-30T09:10:00"
PREDICTION_TWO_ISSUED_AT = "2026-03-30T10:20:00"
RESOLVED_AT = "2026-07-01T10:00:00"


def _criteria_payload():
    return {
        "criteria_id": "criteria-1",
        "forecast_id": QUESTION_ID,
        "label": "Support threshold",
        "description": "Resolve yes when measured support exceeds 55%.",
        "resolution_date": QUESTION_RESOLUTION_DATE,
        "criteria_type": "metric_threshold",
        "thresholds": {
            "metric_id": "survey.support_share",
            "operator": "gt",
            "value": 0.55,
        },
        "notes": ["Resolution uses the observed survey series, not simulated run shares."],
    }


def _question_payload():
    question_text = QUESTION_TEXT
    return {
        "forecast_id": QUESTION_ID,
        "project_id": "proj-1",
        "title": "Public response to policy change",
        "question": question_text,
        "question_text": question_text,
        "question_type": "binary",
        "status": "active",
        "horizon": QUESTION_RESOLUTION_DATE,
        "resolution_criteria_ids": ["criteria-1"],
        "owner": "forecasting-team",
        "source": "manual-entry",
        "decomposition_support": [
            {
                "label": "North region split",
                "question_text": "Will north-region support exceed 55%?",
                "resolution_criteria_ids": ["criteria-1"],
            },
            {
                "label": "South region split",
                "question_text": "Will south-region support exceed 55%?",
                "resolution_criteria_ids": ["criteria-1"],
            },
        ],
        "abstention_conditions": [
            "Do not issue if no named resolution source is available.",
        ],
        "primary_simulation_id": "sim-001",
        "issue_timestamp": QUESTION_ISSUED_AT,
        "issued_at": QUESTION_ISSUED_AT,
        "created_at": QUESTION_ISSUED_AT,
        "updated_at": QUESTION_UPDATED_AT,
    }


def _evidence_bundle_payload():
    return {
        "bundle_id": "bundle-1",
        "forecast_id": QUESTION_ID,
        "title": "Initial evidence",
        "summary": "Grounding artifacts plus prepared simulation context.",
        "status": "degraded",
        "artifacts": [
            {
                "artifact_id": "grounding-1",
                "kind": "grounding_bundle",
                "path": "uploads/projects/proj-1/source_manifest.json",
            }
        ],
        "entries": [
            {
                "entry_id": "evidence-source-1",
                "source_type": "uploaded_source",
                "provider_id": "uploaded_local_artifact",
                "provider_kind": "uploaded_local_artifact",
                "title": "Uploaded source excerpt",
                "summary": "Uploaded memo excerpt about support drivers.",
                "captured_at": QUESTION_ISSUED_AT,
                "observed_at": "2026-03-28T12:00:00",
                "citation_id": "[S1]",
                "freshness": {"status": "stale", "reason": "Source predates issue time."},
                "relevance": {"score": 0.95, "reason": "Directly addresses the forecast target."},
                "provenance": {
                    "provider": "uploaded_local_artifact",
                    "artifact_type": "grounding_bundle",
                    "path": "uploads/projects/proj-1/source_manifest.json",
                },
                "quality_score": 0.82,
                "conflict_status": "supports",
                "missing_evidence_markers": [],
            },
            {
                "entry_id": "evidence-graph-1",
                "source_type": "graph_summary",
                "provider_id": "uploaded_local_artifact",
                "provider_kind": "uploaded_local_artifact",
                "title": "Stored graph build summary",
                "summary": "Persisted graph build indicates policy disagreement clusters.",
                "captured_at": QUESTION_ISSUED_AT,
                "citation_id": "[G1]",
                "freshness": {"status": "fresh"},
                "relevance": {"score": 0.78},
                "provenance": {
                    "provider": "uploaded_local_artifact",
                    "artifact_type": "graph_build_summary",
                    "path": "uploads/projects/proj-1/graph_build_summary.json",
                },
                "quality_score": 0.76,
                "conflict_status": "contradicts",
                "conflict_markers": ["support_direction_disagreement"],
                "missing_evidence_markers": [],
            },
            {
                "entry_id": "evidence-live-gap",
                "source_type": "missing_evidence",
                "provider_id": "live_external",
                "provider_kind": "live_external",
                "title": "Live external evidence unavailable",
                "summary": "No live external retrieval adapter is configured in this environment.",
                "captured_at": QUESTION_ISSUED_AT,
                "freshness": {"status": "unknown"},
                "relevance": {"score": 0.4},
                "provenance": {
                    "provider": "live_external",
                    "adapter_status": "unconfigured",
                },
                "quality_score": 0.0,
                "conflict_status": "missing",
                "missing_evidence_markers": ["live_external_provider_unconfigured"],
            },
        ],
        "providers": [
            {
                "provider_id": "uploaded_local_artifact",
                "provider_kind": "uploaded_local_artifact",
                "status": "ready",
                "retrieval_quality": "bounded_local_artifacts",
            },
            {
                "provider_id": "live_external",
                "provider_kind": "live_external",
                "status": "unavailable",
                "retrieval_quality": "not_configured",
            },
        ],
        "question_links": [QUESTION_ID],
        "prediction_links": ["prediction-1", "prediction-2"],
        "boundary_note": "This bundle only covers uploaded project evidence and stored simulation artifacts.",
        "created_at": QUESTION_ISSUED_AT,
    }


def _worker_payloads():
    return [
        {
            "worker_id": "worker-sim",
            "forecast_id": QUESTION_ID,
            "kind": "simulation",
            "label": "Scenario Simulation Worker",
            "status": "ready",
            "capabilities": ["scenario_generation", "ensemble_execution"],
            "primary_output_semantics": "scenario_evidence",
        },
        {
            "worker_id": "worker-analytical",
            "forecast_id": QUESTION_ID,
            "kind": "analytical",
            "label": "Analytical Worker",
            "status": "registered",
            "capabilities": ["synthesis", "comparison"],
            "primary_output_semantics": "qualitative_judgment",
        },
    ]


def _prediction_entry_payload(
    *,
    prediction_id: str,
    issued_at: str,
    prediction: dict,
    revises_prediction_id: str | None = None,
    revision_number: int = 1,
    entry_kind: str = "issue",
):
    return {
        "entry_id": prediction_id,
        "prediction_id": prediction_id,
        "forecast_id": QUESTION_ID,
        "worker_id": "worker-sim",
        "recorded_at": issued_at,
        "issued_at": issued_at,
        "value_type": "scenario_observed_share",
        "value": prediction,
        "prediction": prediction,
        "value_semantics": "observed_run_share",
        "revision_number": revision_number,
        "entry_kind": entry_kind,
        "revises_prediction_id": revises_prediction_id,
        "calibration_state": "not_applicable",
        "evidence_bundle_ids": ["bundle-1"],
        "worker_output_ids": ["worker-output-1"],
        "notes": ["Scenario frequency is descriptive until evaluation earns more."],
        "metadata": {"lineage": "immutable"},
        "evaluation_case_ids": ["case-1"],
        "evaluation_summary": {"status": "available", "case_count": 1},
        "benchmark_summary": {"status": "available", "best_estimate_worker_id": "worker-sim"},
        "backtest_summary_ref": "not_run",
        "calibration_summary_ref": "not_applicable",
        "confidence_basis": {"status": "available", "resolved_case_count": 1},
    }


def _prediction_ledger_payload(final_resolution_state: str = "pending"):
    return {
        "forecast_id": QUESTION_ID,
        "entries": [
            _prediction_entry_payload(
                prediction_id="prediction-1",
                issued_at=PREDICTION_ONE_ISSUED_AT,
                prediction={"support_share": 0.62},
            ),
            _prediction_entry_payload(
                prediction_id="prediction-2",
                issued_at=PREDICTION_TWO_ISSUED_AT,
                prediction={"support_share": 0.67},
                revises_prediction_id="prediction-1",
                entry_kind="revision",
            ),
        ],
        "worker_outputs": [
            {
                "worker_id": "worker-sim",
                "output_id": "worker-output-1",
                "recorded_at": PREDICTION_ONE_ISSUED_AT,
                "summary": "Scenario evidence summarising observed run shares.",
            }
        ],
        "resolution_history": (
            [
                {
                    "status": "resolved",
                    "resolved_at": RESOLVED_AT,
                    "evidence_bundle_ids": ["bundle-1"],
                    "prediction_entry_ids": ["prediction-1", "prediction-2"],
                    "revision_entry_ids": ["prediction-2"],
                    "worker_output_ids": ["worker-output-1"],
                }
            ]
            if final_resolution_state != "pending"
            else []
        ),
        "final_resolution_state": (
            {
                "status": final_resolution_state,
                "resolved_at": RESOLVED_AT if final_resolution_state != "pending" else None,
                "evidence_bundle_ids": ["bundle-1"],
                "prediction_entry_ids": ["prediction-1", "prediction-2"],
                "revision_entry_ids": ["prediction-2"],
                "worker_output_ids": ["worker-output-1"],
            }
            if final_resolution_state != "pending"
            else {"status": "pending"}
        ),
    }


def test_workspace_payload_includes_canonical_lifecycle_metadata_and_simulation_scope():
    workspace = ForecastWorkspaceRecord.from_dict(_workspace_payload())

    payload = workspace.to_dict()

    assert payload["lifecycle_metadata"]["current_stage"] == "forecast_answer"
    assert payload["lifecycle_metadata"]["latest_answer_id"] == "answer-1"
    assert payload["lifecycle_metadata"]["resolution_record_status"] == "pending"
    assert payload["lifecycle_metadata"]["scoring_event_count"] == 0

    assert payload["simulation_scope"]["forecast_id"] == QUESTION_ID
    assert payload["simulation_scope"]["simulation_id"] == "sim-001"
    assert payload["simulation_scope"]["ensemble_ids"] == ["0001"]
    assert payload["simulation_scope"]["latest_ensemble_id"] == "0001"
    assert payload["simulation_scope"]["run_ids"] == []

    assert payload["resolution_record"]["forecast_id"] == QUESTION_ID
    assert payload["resolution_record"]["status"] == "pending"
    assert payload["scoring_events"] == []


def _evaluation_case_payload():
    return {
        "case_id": "case-1",
        "forecast_id": QUESTION_ID,
        "criteria_id": "criteria-1",
        "status": "resolved",
        "issued_at": QUESTION_ISSUED_AT,
        "question_class": "binary_support",
        "comparable_question_class": "binary_support_threshold",
        "source": "manual_registry",
        "prediction_entry_id": "prediction-1",
        "forecast_probability": 0.61,
        "evaluation_split": "historical_holdout",
        "window_id": "rolling-2026Q2",
        "benchmark_id": "benchmark-1",
        "observed_outcome": {"support_share": 0.58},
        "resolved_at": RESOLVED_AT,
        "resolution_note": "Observed measurement exceeded the threshold.",
        "confidence_basis": {"status": "resolved", "evidence": "observed_outcome"},
        "notes": ["Resolved against a stored historical comparison set."],
    }


def _forecast_answer_payload():
    return {
        "answer_id": "answer-1",
        "forecast_id": QUESTION_ID,
        "answer_type": "hybrid_forecast",
        "summary": "Simulation provides scenario coverage; analytical synthesis is still uncalibrated.",
        "worker_ids": ["worker-sim", "worker-analytical"],
        "prediction_entry_ids": ["prediction-1", "prediction-2"],
        "confidence_semantics": "uncalibrated",
        "created_at": "2026-03-30T10:00:00",
        "answer_payload": {"headline": "Support exceeded 55% in most stored scenarios."},
        "evaluation_summary": {"status": "available", "case_count": 1, "resolved_case_count": 1},
        "benchmark_summary": {"status": "available", "best_estimate_worker_id": "worker-analytical"},
        "backtest_summary": {"status": "not_run", "reason": "workspace-level backtest not generated"},
        "calibration_summary": {
            "status": "not_applicable",
            "reason": "workspace evaluation cases are not a calibration claim",
        },
        "confidence_basis": {"status": "available", "resolved_case_count": 1},
    }


def _simulation_worker_contract_payload():
    return {
        "worker_id": "worker-sim",
        "forecast_id": QUESTION_ID,
        "simulation_id": "sim-001",
        "prepare_artifact_paths": [
            "uploads/simulations/sim-001/forecast_brief.json",
            "uploads/simulations/sim-001/prepared_snapshot.json",
        ],
        "ensemble_ids": ["0001"],
        "scenario_diversity_strategy": "weighted_cycle",
        "probability_interpretation": "do_not_treat_as_real_world_probability",
        "notes": [
            "Observed run shares remain descriptive until separate evaluation earns stronger claims.",
        ],
    }


def _workspace_payload():
    return {
        "forecast_question": _question_payload(),
        "resolution_criteria": [_criteria_payload()],
        "evidence_bundle": _evidence_bundle_payload(),
        "forecast_workers": _worker_payloads(),
        "prediction_ledger": _prediction_ledger_payload(),
        "evaluation_cases": [_evaluation_case_payload()],
        "forecast_answers": [_forecast_answer_payload()],
        "simulation_worker_contract": _simulation_worker_contract_payload(),
    }


def test_evidence_bundle_normalizes_quality_uncertainty_and_citation_index():
    bundle = EvidenceBundle.from_dict(_evidence_bundle_payload())

    assert bundle.status == "degraded"
    assert bundle.question_links == [QUESTION_ID]
    assert bundle.prediction_links == ["prediction-1", "prediction-2"]
    assert bundle.timestamps["created_at"] == QUESTION_ISSUED_AT
    assert bundle.timestamps["latest_observed_at"] == "2026-03-28T12:00:00"
    assert bundle.provenance["forecast_id"] == QUESTION_ID
    assert set(bundle.provenance["provider_ids"]) == {
        "uploaded_local_artifact",
        "live_external",
    }
    assert bundle.citation_index["source"][0]["citation_id"] == "[S1]"
    assert bundle.citation_index["graph"][0]["citation_id"] == "[G1]"
    assert bundle.quality_summary["entry_count"] == 3
    assert bundle.quality_summary["conflicting_entry_count"] == 1
    assert bundle.quality_summary["missing_evidence_count"] == 1
    assert bundle.quality_summary["stale_entry_count"] == 1
    assert bundle.conflict_markers[0]["code"] == "support_direction_disagreement"
    assert bundle.uncertainty_summary["status"] == "degraded"
    assert set(bundle.uncertainty_summary["drivers"]) >= {"stale", "conflicting", "missing"}
    assert set(bundle.uncertainty_labels) >= {
        "stale_evidence",
        "conflicting_evidence",
        "missing_evidence",
    }


def test_forecast_question_round_trips_primary_fields():
    question = ForecastQuestion.from_dict(_question_payload())

    serialized = question.to_dict()

    assert serialized["forecast_id"] == QUESTION_ID
    assert serialized["question_text"] == QUESTION_TEXT
    assert serialized["horizon"] == {"label": QUESTION_RESOLUTION_DATE}
    assert serialized["issue_timestamp"] == QUESTION_ISSUED_AT
    assert serialized["issued_at"] == QUESTION_ISSUED_AT
    assert serialized["owner"] == "forecasting-team"
    assert serialized["source"] == "manual-entry"
    assert serialized["decomposition_support"][0]["question_text"] == (
        "Will north-region support exceed 55%?"
    )
    assert serialized["abstention_conditions"] == [
        "Do not issue if no named resolution source is available.",
    ]


def test_forecast_question_round_trips_categorical_question_spec():
    payload = _question_payload()
    payload["question_type"] = "categorical"
    payload["question_text"] = "Which launch posture will be observed by June 30, 2026?"
    payload["question"] = payload["question_text"]
    payload["question_spec"] = {
        "outcome_labels": ["win", "stretch", "miss"],
    }

    question = ForecastQuestion.from_dict(payload)
    serialized = question.to_dict()

    assert serialized["question_type"] == "categorical"
    assert serialized["question_spec"]["outcome_labels"] == ["win", "stretch", "miss"]


def test_forecast_question_round_trips_numeric_question_spec():
    payload = _question_payload()
    payload["question_type"] = "numeric"
    payload["question_text"] = "What value will ARR reach by June 30, 2026?"
    payload["question"] = payload["question_text"]
    payload["question_spec"] = {
        "unit": "usd_millions",
        "lower_bound": 0,
        "upper_bound": 250,
        "interval_levels": [90, 50, 80],
    }

    question = ForecastQuestion.from_dict(payload)
    serialized = question.to_dict()

    assert serialized["question_type"] == "numeric"
    assert serialized["question_spec"] == {
        "unit": "usd_millions",
        "lower_bound": 0.0,
        "upper_bound": 250.0,
        "interval_levels": [50, 80, 90],
    }


def test_prediction_ledger_entry_round_trips_revision_fields():
    entry = PredictionLedgerEntry.from_dict(
        _prediction_entry_payload(
            prediction_id="prediction-1",
            issued_at=PREDICTION_ONE_ISSUED_AT,
            revision_number=1,
            prediction={"support_share": 0.62},
        )
    )

    serialized = entry.to_dict()

    assert serialized["prediction_id"] == "prediction-1"
    assert serialized["issued_at"] == PREDICTION_ONE_ISSUED_AT
    assert serialized["entry_kind"] == "issue"
    assert serialized["revises_prediction_id"] is None
    assert serialized["prediction"] == {"support_share": 0.62}
    assert serialized["worker_output_ids"] == ["worker-output-1"]
    assert serialized["calibration_state"] == "not_applicable"
    assert serialized["evaluation_case_ids"] == ["case-1"]
    assert serialized["evaluation_summary"]["case_count"] == 1
    assert serialized["benchmark_summary"]["best_estimate_worker_id"] == "worker-sim"
    assert serialized["backtest_summary_ref"] == "not_run"
    assert serialized["calibration_summary_ref"] == "not_applicable"
    assert serialized["confidence_basis"]["resolved_case_count"] == 1


def test_evaluation_case_round_trips_typed_prediction_payload_fields():
    payload = _evaluation_case_payload()
    payload.update(
        {
            "question_class": "numeric_arr",
            "prediction_value_type": "numeric_interval",
            "prediction_value_semantics": "numeric_interval_estimate",
            "prediction_payload": {
                "point_estimate": 42.0,
                "intervals": {
                    "50": {"low": 38.0, "high": 46.0},
                    "80": {"low": 31.0, "high": 53.0},
                    "90": {"low": 28.0, "high": 57.0},
                },
                "unit": "usd_millions",
            },
            "observed_outcome": {"value": 44.0},
            "observed_value": {"value": 44.0},
            "observed_unit": "usd_millions",
        }
    )

    case = EvaluationCase.from_dict(payload)
    serialized = case.to_dict()

    assert serialized["prediction_value_type"] == "numeric_interval"
    assert serialized["prediction_value_semantics"] == "numeric_interval_estimate"
    assert serialized["prediction_payload"]["point_estimate"] == 42.0
    assert serialized["prediction_payload"]["intervals"]["80"] == {
        "low": 31.0,
        "high": 53.0,
    }
    assert serialized["observed_unit"] == "usd_millions"


def test_prediction_ledger_tracks_final_resolution_state():
    ledger = PredictionLedger.from_dict(_prediction_ledger_payload(final_resolution_state="resolved"))

    serialized = ledger.to_dict()

    assert serialized["final_resolution_state"]["status"] == "resolved"
    assert serialized["final_resolution_state"]["resolved_at"] == RESOLVED_AT
    assert serialized["resolution_status"] == "resolved"
    assert serialized["issued_predictions"][0]["prediction_id"] == "prediction-1"
    assert serialized["prediction_revisions"][0]["revises_entry_id"] == "prediction-1"
    assert serialized["prediction_revisions"][0]["issued_at"] == PREDICTION_TWO_ISSUED_AT
    assert serialized["worker_outputs"][0]["output_id"] == "worker-output-1"
    assert serialized["resolution_history"][0]["revision_entry_ids"] == ["prediction-2"]


def test_forecast_workspace_record_round_trips_to_dict_and_summary():
    workspace = ForecastWorkspaceRecord.from_dict(_workspace_payload())

    serialized = workspace.to_dict()
    summary = workspace.to_summary_dict()

    assert serialized["forecast_question"]["question_text"] == QUESTION_TEXT
    assert serialized["forecast_question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert serialized["prediction_ledger"]["final_resolution_state"]["status"] == "pending"
    assert serialized["prediction_ledger"]["entries"][1]["revises_entry_id"] == "prediction-1"
    assert serialized["forecast_answers"][0]["evaluation_summary"]["status"] == "available"
    assert summary["question_text"] == QUESTION_TEXT
    assert summary["issue_timestamp"] == QUESTION_ISSUED_AT
    assert summary["resolution_status"] == "pending"
    assert summary["prediction_issue_count"] == 1
    assert summary["prediction_revision_count"] == 1
    assert summary["worker_output_count"] == 1
    assert summary["resolution_history_count"] == 0
    assert summary["evidence_bundle_id"] == "bundle-1"
    assert summary["evidence_entry_count"] == 1
    assert summary["retrieval_quality_status"] == "local_only_external_unavailable"
    assert summary["evaluation_case_status"] == "available"
    assert summary["evaluation_resolved_case_count"] == 1
    assert summary["evaluation_pending_case_count"] == 0


def test_evidence_bundle_derives_entries_from_legacy_artifacts_and_tracks_uncertainty():
    bundle = EvidenceBundle.from_dict(_evidence_bundle_payload())

    serialized = bundle.to_dict()

    assert serialized["source_entries"][0]["source_id"] == "evidence-source-1"
    assert serialized["artifacts"][0]["artifact_id"] == "grounding-1"
    assert serialized["retrieval_quality"]["status"] == "local_only_external_unavailable"
    assert serialized["timestamps"]["latest_captured_at"] == QUESTION_ISSUED_AT
    assert serialized["provenance"]["artifact_ids"] == ["grounding-1"]
    assert serialized["references"]["question_ids"] == [QUESTION_ID]
    assert serialized["references"]["prediction_entry_ids"] == ["prediction-1", "prediction-2"]
    assert "missing_evidence" in serialized["uncertainty_summary"]["causes"]
    assert "missing_evidence" in serialized["uncertainty_labels"]
    assert serialized["provider_snapshots"][0]["provider_id"] == "uploaded_local_artifact"


def test_evidence_bundle_defaults_boundary_note_for_legacy_payloads():
    payload = _evidence_bundle_payload()
    payload.pop("boundary_note", None)

    bundle = EvidenceBundle.from_dict(payload)

    assert bundle.boundary_note.startswith("Evidence remains bounded")


def test_evidence_source_entry_validates_supported_provider_and_conflict_fields():
    entry = EvidenceSourceEntry.from_dict(
        {
            "source_id": "ext-1",
            "provider_id": "fixture_external_provider",
            "provider_kind": "external_live",
            "kind": "external_document",
            "title": "External article",
            "citation_id": "[E1]",
            "locator": "https://example.test/article",
            "timestamps": {"captured_at": QUESTION_ISSUED_AT},
            "freshness": {"status": "fresh", "score": 0.9},
            "relevance": {"score": 0.7},
            "quality": {"score": 0.6},
            "conflict_status": "supports",
        }
    )

    assert entry.provider_kind == "external_live"
    assert entry.citation_id == "[E1]"
    assert entry.freshness_score == 0.9


def test_simulation_worker_rejects_probability_output_semantics():
    with pytest.raises(ValueError, match="Simulation workers cannot declare forecast_probability semantics"):
        ForecastWorker.from_dict(
            {
                "worker_id": "worker-sim",
                "forecast_id": QUESTION_ID,
                "kind": "simulation",
                "label": "Scenario Simulation Worker",
                "primary_output_semantics": "forecast_probability",
            }
        )


def test_resolution_criteria_requires_iso_date():
    with pytest.raises(ValueError, match="resolution_date must be an ISO-8601 date"):
        ResolutionCriteria.from_dict(
            {
                "criteria_id": "criteria-1",
                "forecast_id": QUESTION_ID,
                "label": "Threshold",
                "description": "Resolve yes if support exceeds 55%.",
                "resolution_date": "June 30, 2026",
            }
        )


def test_simulation_worker_contract_rejects_probability_language():
    with pytest.raises(ValueError, match="Unsupported probability interpretation"):
        SimulationWorkerContract.from_dict(
            {
                "worker_id": "worker-sim",
                "forecast_id": QUESTION_ID,
                "probability_interpretation": "empirical_probability",
            }
        )


def test_forecast_capabilities_domain_preserves_simulation_as_worker():
    capabilities = get_forecast_capabilities_domain()

    assert capabilities["required_primitives"][0] == "forecast_question"
    assert capabilities["simulation"]["role"] == "scenario_worker"
    assert capabilities["simulation"]["probability_interpretation"] == (
        "do_not_treat_as_real_world_probability"
    )
