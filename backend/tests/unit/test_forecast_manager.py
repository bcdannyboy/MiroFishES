from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.models.forecasting import (
    EvaluationCase,
    ForecastQuestion,
    ForecastWorkspaceRecord,
    PredictionLedger,
    PredictionLedgerEntry,
)
from app.services.evidence_bundle_service import (
    EvidenceBundleService,
    UnavailableExternalEvidenceProvider,
    UploadedLocalArtifactEvidenceProvider,
)
from app.services.forecast_interfaces import ForecastPhaseService, ForecastWorkspaceStore
from app.services.forecast_manager import ForecastManager


QUESTION_ID = "forecast-001"
QUESTION_TEXT = "Will the hybrid system show more than 55% support by June 30, 2026?"
QUESTION_ISSUED_AT = "2026-03-30T09:00:00"
QUESTION_UPDATED_AT = "2026-03-30T09:00:00"
QUESTION_RESOLUTION_DATE = "2026-06-30"
INITIAL_PREDICTION_ID = "prediction-1"
REVISION_PREDICTION_ID = "prediction-2"
RESOLVED_AT = "2026-07-01T10:00:00"


def _criteria_payload():
    return {
        "criteria_id": "criteria-1",
        "forecast_id": QUESTION_ID,
        "label": "Support threshold",
        "description": "Resolve yes if support exceeds 55%.",
        "resolution_date": QUESTION_RESOLUTION_DATE,
        "criteria_type": "metric_threshold",
        "thresholds": {
            "metric_id": "survey.support_share",
            "operator": "gt",
            "value": 0.55,
        },
    }


def _question_payload():
    question_text = QUESTION_TEXT
    return {
        "forecast_id": QUESTION_ID,
        "project_id": "proj-1",
        "title": "Policy support outlook",
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
        "summary": "Grounding plus simulation prepare artifacts.",
        "status": "unavailable",
        "artifacts": [
            {
                "artifact_id": "prepared-snapshot",
                "kind": "prepared_snapshot",
                "path": "uploads/simulations/sim-001/prepared_snapshot.json",
            }
        ],
        "entries": [],
        "providers": [],
        "question_links": [QUESTION_ID],
        "prediction_links": [],
        "boundary_note": "No live-web coverage is claimed by this workspace.",
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
            "capabilities": ["scenario_generation"],
            "primary_output_semantics": "scenario_evidence",
        }
    ]


def _prediction_payload(
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
    }


def _ledger_payload(final_resolution_state: str = "pending"):
    return {
        "forecast_id": QUESTION_ID,
        "entries": [
            _prediction_payload(
                prediction_id=INITIAL_PREDICTION_ID,
                issued_at="2026-03-30T09:10:00",
                prediction={"support_share": 0.62},
            ),
            _prediction_payload(
                prediction_id=REVISION_PREDICTION_ID,
                issued_at="2026-03-30T10:20:00",
                prediction={"support_share": 0.67},
                revises_prediction_id=INITIAL_PREDICTION_ID,
                entry_kind="revision",
            ),
        ],
        "worker_outputs": [
            {
                "worker_id": "worker-sim",
                "output_id": "worker-output-1",
                "recorded_at": "2026-03-30T09:10:00",
                "summary": "Scenario evidence summarising observed run shares.",
            }
        ],
        "resolution_history": (
            [
                {
                    "status": "resolved",
                    "resolved_at": RESOLVED_AT,
                    "evidence_bundle_ids": ["bundle-1"],
                    "prediction_entry_ids": [INITIAL_PREDICTION_ID, REVISION_PREDICTION_ID],
                    "revision_entry_ids": [REVISION_PREDICTION_ID],
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
                "prediction_entry_ids": [INITIAL_PREDICTION_ID, REVISION_PREDICTION_ID],
                "revision_entry_ids": [REVISION_PREDICTION_ID],
                "worker_output_ids": ["worker-output-1"],
            }
            if final_resolution_state != "pending"
            else {"status": "pending"}
        ),
    }


def _evaluation_case_payload():
    return {
        "case_id": "case-1",
        "forecast_id": QUESTION_ID,
        "criteria_id": "criteria-1",
        "status": "resolved",
        "observed_outcome": {"support_share": 0.58},
        "resolved_at": RESOLVED_AT,
        "resolution_note": "Threshold met.",
    }


def _forecast_answer_payload():
    return {
        "answer_id": "answer-1",
        "forecast_id": QUESTION_ID,
        "answer_type": "simulation_scenario_summary",
        "summary": "Stored scenarios leaned above the threshold, but this is not a real-world probability claim.",
        "worker_ids": ["worker-sim"],
        "prediction_entry_ids": [INITIAL_PREDICTION_ID],
        "confidence_semantics": "uncalibrated",
        "created_at": "2026-03-30T10:30:00",
    }


def _simulation_worker_contract_payload():
    return {
        "worker_id": "worker-sim",
        "forecast_id": QUESTION_ID,
        "simulation_id": "sim-001",
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "probability_interpretation": "do_not_treat_as_real_world_probability",
    }


def _workspace_payload():
    return {
        "forecast_question": _question_payload(),
        "resolution_criteria": [_criteria_payload()],
        "evidence_bundle": _evidence_bundle_payload(),
        "forecast_workers": _worker_payloads(),
        "prediction_ledger": _ledger_payload(),
        "evaluation_cases": [_evaluation_case_payload()],
        "forecast_answers": [_forecast_answer_payload()],
        "simulation_worker_contract": _simulation_worker_contract_payload(),
    }


def _question_object(result):
    if isinstance(result, ForecastQuestion):
        return result
    return result.forecast_question


def _ledger_object(result):
    if isinstance(result, PredictionLedger):
        return result
    if isinstance(result, ForecastWorkspaceRecord):
        return result.prediction_ledger
    raise TypeError(f"Unexpected prediction ledger result: {type(result)!r}")


def _build_workspace():
    return ForecastWorkspaceRecord.from_dict(_workspace_payload())


def _build_nonbinary_workspace(*, question_type: str, question_spec: dict):
    payload = _workspace_payload()
    payload["forecast_question"] = {
        **payload["forecast_question"],
        "forecast_id": f"forecast-{question_type}",
        "question_type": question_type,
        "question_spec": dict(question_spec),
        "resolution_criteria_ids": ["criteria-1"],
    }
    payload["resolution_criteria"] = [
        {
            **_criteria_payload(),
            "forecast_id": f"forecast-{question_type}",
        }
    ]
    payload["evidence_bundle"] = {
        **payload["evidence_bundle"],
        "forecast_id": f"forecast-{question_type}",
        "question_links": [f"forecast-{question_type}"],
    }
    payload["forecast_workers"] = [
        {
            "worker_id": "worker-base-rate",
            "forecast_id": f"forecast-{question_type}",
            "kind": "base_rate",
            "label": "Base-rate worker",
            "status": "ready",
            "capabilities": ["benchmark_lookup"],
            "primary_output_semantics": (
                "forecast_distribution"
                if question_type == "categorical"
                else "numeric_interval_estimate"
            ),
        },
        {
            "worker_id": "worker-sim",
            "forecast_id": f"forecast-{question_type}",
            "kind": "simulation",
            "label": "Scenario Simulation Worker",
            "status": "ready",
            "capabilities": ["scenario_generation"],
            "primary_output_semantics": "scenario_evidence",
        },
    ]
    payload["prediction_ledger"] = {
        "forecast_id": f"forecast-{question_type}",
        "entries": [],
        "worker_outputs": [],
        "resolution_history": [],
        "final_resolution_state": {"status": "pending"},
    }
    payload["evaluation_cases"] = []
    payload["forecast_answers"] = []
    payload["simulation_worker_contract"] = {
        **_simulation_worker_contract_payload(),
        "forecast_id": f"forecast-{question_type}",
    }
    return ForecastWorkspaceRecord.from_dict(payload)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_ensemble_root(
    simulation_data_dir: Path,
    *,
    simulation_id: str = "sim-001",
    ensemble_id: str = "0001",
    metric_id: str = "survey.support_share",
    values: list[float],
) -> None:
    ensemble_dir = simulation_data_dir / simulation_id / "ensemble" / f"ensemble_{ensemble_id}"
    runs_dir = ensemble_dir / "runs"
    _write_json(
        ensemble_dir / "ensemble_spec.json",
        {
            "artifact_type": "ensemble_spec",
            "simulation_id": simulation_id,
            "run_count": len(values),
            "max_concurrency": 1,
            "root_seed": 11,
            "sampling_mode": "seeded",
        },
    )
    _write_json(
        ensemble_dir / "ensemble_state.json",
        {
            "artifact_type": "ensemble_state",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "status": "prepared",
            "run_count": len(values),
            "prepared_run_count": len(values),
            "run_ids": [f"{index + 1:04d}" for index in range(len(values))],
            "outcome_metric_ids": [metric_id],
        },
    )
    for index, value in enumerate(values, start=1):
        run_id = f"{index:04d}"
        run_dir = runs_dir / f"run_{run_id}"
        _write_json(
            run_dir / "run_manifest.json",
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "root_seed": index,
                "seed_metadata": {"resolution_seed": index},
                "resolved_values": {},
                "config_artifact": "resolved_config.json",
                "artifact_paths": {"resolved_config": "resolved_config.json"},
                "status": "completed",
            },
        )
        _write_json(
            run_dir / "resolved_config.json",
            {
                "artifact_type": "resolved_config",
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
            },
        )
        _write_json(
            run_dir / "metrics.json",
            {
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    metric_id: {
                        "metric_id": metric_id,
                        "label": "Support share",
                        "aggregation": "ratio",
                        "unit": "share",
                        "probability_mode": "empirical",
                        "value": value,
                    }
                },
            },
        )


def _hybrid_workspace():
    payload = _workspace_payload()
    payload["resolution_criteria"] = [_criteria_payload()]
    payload["forecast_workers"] = [
        {
            "worker_id": "worker-base-rate",
            "forecast_id": QUESTION_ID,
            "kind": "base_rate",
            "label": "Base-rate benchmark worker",
            "status": "ready",
            "capabilities": ["benchmark_lookup"],
            "primary_output_semantics": "forecast_probability",
            "metadata": {
                "worker_family": "base_rate",
                "benchmark": {
                    "estimate": 0.41,
                    "sample_count": 24,
                    "assumptions": ["Comparable baseline conditions remain directionally relevant."],
                    "counterevidence": ["The benchmark predates the latest support shift."],
                },
            },
        },
        {
            "worker_id": "worker-reference",
            "forecast_id": QUESTION_ID,
            "kind": "reference_class",
            "label": "Reference-class worker",
            "status": "ready",
            "capabilities": ["case_based_reasoning"],
            "primary_output_semantics": "forecast_probability",
            "metadata": {
                "worker_family": "reference_class",
                "reference_cases": [
                    {"case_id": "case-a", "value": 1, "weight": 1.0},
                    {"case_id": "case-b", "value": 1, "weight": 1.0},
                    {"case_id": "case-c", "value": 0, "weight": 1.0},
                    {"case_id": "case-d", "value": 1, "weight": 1.0},
                    {"case_id": "case-e", "value": 0, "weight": 1.0},
                ],
                "assumptions": ["The chosen cases remain a relevant reference class."],
            },
        },
        {
            "worker_id": "worker-retrieval",
            "forecast_id": QUESTION_ID,
            "kind": "retrieval_synthesis",
            "label": "Retrieval synthesis worker",
            "status": "ready",
            "capabilities": ["bounded_local_retrieval"],
            "primary_output_semantics": "forecast_probability",
            "metadata": {"worker_family": "retrieval_synthesis"},
        },
        {
            "worker_id": "worker-sim",
            "forecast_id": QUESTION_ID,
            "kind": "simulation",
            "label": "Scenario simulation worker",
            "status": "ready",
            "capabilities": ["scenario_generation"],
            "primary_output_semantics": "scenario_evidence",
            "metadata": {"worker_family": "simulation_adapter"},
        },
    ]
    payload["prediction_ledger"] = {
        "forecast_id": QUESTION_ID,
        "entries": [],
        "worker_outputs": [],
        "resolution_history": [],
        "final_resolution_state": {"status": "pending"},
    }
    payload["evaluation_cases"] = [
        {
            "case_id": "case-1",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.61},
            "resolved_at": "2025-11-01T00:00:00",
        },
        {
            "case_id": "case-2",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.57},
            "resolved_at": "2025-12-01T00:00:00",
        },
        {
            "case_id": "case-3",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.49},
            "resolved_at": "2026-01-01T00:00:00",
        },
    ]
    payload["forecast_answers"] = []
    payload["evidence_bundle"] = {
        "bundle_id": "bundle-1",
        "forecast_id": QUESTION_ID,
        "title": "Hybrid evidence",
        "summary": "Uploaded/local evidence and simulation artifacts.",
        "source_entries": [
            {
                "source_id": "src-1",
                "provider_id": "uploaded_local_artifacts",
                "provider_kind": "uploaded_local_artifact",
                "kind": "uploaded_source",
                "title": "Uploaded brief",
                "summary": "The brief leans above the support threshold.",
                "citation_id": "[S1]",
                "locator": "files/brief.md#chars=0-140",
                "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                "freshness": {"status": "fresh", "score": 0.9},
                "relevance": {"status": "high", "score": 0.9},
                "quality": {"status": "strong", "score": 0.8},
                "conflict_status": "supports",
                "metadata": {
                    "forecast_hints": [
                        {
                            "estimate": 0.68,
                            "confidence_weight": 0.9,
                            "assumption": "Support momentum in the uploaded brief remains live.",
                        }
                    ]
                },
            },
            {
                "source_id": "src-2",
                "provider_id": "uploaded_local_artifacts",
                "provider_kind": "uploaded_local_artifact",
                "kind": "uploaded_source",
                "title": "Contrary note",
                "summary": "A contrary note warns the threshold may not hold.",
                "citation_id": "[S2]",
                "locator": "files/contra.md#chars=0-110",
                "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                "freshness": {"status": "fresh", "score": 0.8},
                "relevance": {"status": "medium", "score": 0.6},
                "quality": {"status": "usable", "score": 0.5},
                "conflict_status": "contradicts",
                "metadata": {
                    "forecast_hints": [
                        {
                            "estimate": 0.38,
                            "confidence_weight": 0.4,
                            "counterevidence": "A contrary brief disputes the high-support case.",
                        }
                    ]
                },
            },
        ],
        "provider_snapshots": [
            {
                "provider_id": "uploaded_local_artifacts",
                "provider_kind": "uploaded_local_artifact",
                "status": "ready",
                "collected_at": QUESTION_ISSUED_AT,
                "boundary_note": "Local artifacts only.",
            }
        ],
        "question_ids": [QUESTION_ID],
        "prediction_entry_ids": [],
        "status": "ready",
        "boundary_note": "Evidence remains bounded to stored providers and artifacts.",
        "created_at": QUESTION_ISSUED_AT,
    }
    payload["simulation_worker_contract"] = {
        "worker_id": "worker-sim",
        "forecast_id": QUESTION_ID,
        "simulation_id": "sim-001",
        "ensemble_ids": ["0001"],
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "probability_interpretation": "do_not_treat_as_real_world_probability",
    }
    return ForecastWorkspaceRecord.from_dict(payload)


def _write_simulation_metrics(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    ensemble_id: str = "0001",
    values: list[float],
    metric_id: str = "survey.support_share",
) -> None:
    ensemble_dir = simulation_data_dir / simulation_id / "ensemble" / f"ensemble_{ensemble_id}"
    _write_json(
        ensemble_dir / "ensemble_state.json",
        {
            "artifact_type": "ensemble_state",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "status": "completed",
            "run_count": len(values),
            "prepared_run_count": len(values),
            "run_ids": [f"{index + 1:04d}" for index in range(len(values))],
            "outcome_metric_ids": [metric_id],
        },
    )
    for index, value in enumerate(values, start=1):
        run_id = f"{index:04d}"
        run_dir = ensemble_dir / "runs" / f"run_{run_id}"
        _write_json(
            run_dir / "run_manifest.json",
            {
                "simulation_id": simulation_id,
                "ensemble_id": ensemble_id,
                "run_id": run_id,
                "status": "completed",
            },
        )
        _write_json(
            run_dir / "metrics.json",
            {
                "quality_checks": {"status": "complete", "run_status": "completed"},
                "metric_values": {
                    metric_id: {
                        "metric_id": metric_id,
                        "value": value,
                    }
                },
            },
        )


def test_forecast_manager_persists_question_primary_fields_through_workspace_storage(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()

    created = manager.create_workspace(_build_workspace())

    assert isinstance(manager, ForecastWorkspaceStore)
    assert isinstance(manager, ForecastPhaseService)
    assert created.forecast_question.forecast_id == QUESTION_ID

    workspace_dir = Path(forecast_data_dir) / QUESTION_ID
    assert (workspace_dir / "workspace_manifest.json").exists()
    assert (workspace_dir / "forecast_question.json").exists()
    assert (workspace_dir / "resolution_criteria.json").exists()
    assert (workspace_dir / "evidence_bundle.json").exists()
    assert (workspace_dir / "evidence_bundles.json").exists()
    assert (workspace_dir / "forecast_workers.json").exists()
    assert (workspace_dir / "simulation_worker_contract.json").exists()
    assert (workspace_dir / "prediction_ledger.json").exists()
    assert (workspace_dir / "evaluation_cases.json").exists()
    assert (workspace_dir / "forecast_answers.json").exists()

    loaded = manager.get_workspace(QUESTION_ID)
    listed = manager.list_workspaces()

    assert loaded is not None
    assert loaded == created
    assert [workspace.forecast_question.forecast_id for workspace in listed] == [QUESTION_ID]
    assert loaded.to_dict()["forecast_question"]["question_text"] == QUESTION_TEXT
    assert loaded.to_dict()["forecast_question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert loaded.to_dict()["prediction_ledger"]["final_resolution_state"]["status"] == "pending"
    assert loaded.to_summary_dict()["question_text"] == QUESTION_TEXT
    assert loaded.to_summary_dict()["issue_timestamp"] == QUESTION_ISSUED_AT
    assert loaded.to_summary_dict()["resolution_status"] == "pending"
    assert loaded.to_summary_dict()["prediction_issue_count"] == 1
    assert loaded.to_summary_dict()["prediction_revision_count"] == 1
    assert loaded.to_summary_dict()["worker_output_count"] == 1
    assert loaded.to_summary_dict()["resolution_history_count"] == 0
    assert loaded.to_summary_dict()["evidence_bundle_id"] == "bundle-1"
    assert loaded.to_summary_dict()["evidence_bundle_status"] == "unavailable"
    assert "sparse_evidence" in loaded.to_summary_dict()["evidence_uncertainty_causes"]


def test_forecast_manager_generates_hybrid_answer_and_revises_worker_predictions(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()

    workspace_payload = _workspace_payload()
    workspace_payload["simulation_worker_contract"]["ensemble_ids"] = ["0001"]
    workspace_payload["evidence_bundle"]["entries"] = [
        {
            "entry_id": "evidence-support-1",
            "source_type": "uploaded_source",
            "provider_id": "uploaded_local_artifacts",
            "provider_kind": "uploaded_local_artifact",
            "title": "Supportive memo excerpt",
            "summary": "Stored evidence supports the threshold case.",
            "captured_at": QUESTION_ISSUED_AT,
            "freshness": {"status": "fresh"},
            "relevance": {"score": 0.9},
            "quality_score": 0.8,
            "conflict_status": "supports",
            "provenance": {"provider": "uploaded_local_artifacts"},
        },
        {
            "entry_id": "evidence-contradict-1",
            "source_type": "uploaded_source",
            "provider_id": "uploaded_local_artifacts",
            "provider_kind": "uploaded_local_artifact",
            "title": "Contradictory note",
            "summary": "One source points the other way.",
            "captured_at": QUESTION_ISSUED_AT,
            "freshness": {"status": "fresh"},
            "relevance": {"score": 0.7},
            "quality_score": 0.6,
            "conflict_status": "contradicts",
            "provenance": {"provider": "uploaded_local_artifacts"},
        },
    ]
    workspace_payload["evaluation_cases"] = [
        {
            "case_id": "case-1",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.61},
            "resolved_at": "2025-11-01T00:00:00",
        },
        {
            "case_id": "case-2",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.57},
            "resolved_at": "2025-12-01T00:00:00",
        },
        {
            "case_id": "case-3",
            "forecast_id": QUESTION_ID,
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.49},
            "resolved_at": "2026-01-01T00:00:00",
        },
    ]
    workspace_payload["prediction_ledger"] = {
        "forecast_id": QUESTION_ID,
        "entries": [],
        "worker_outputs": [],
        "resolution_history": [],
        "final_resolution_state": {"status": "pending"},
    }
    workspace_payload["forecast_answers"] = []

    _write_simulation_metrics(simulation_data_dir, "sim-001", values=[0.62, 0.58, 0.51])

    manager.create_workspace(ForecastWorkspaceRecord.from_dict(workspace_payload))
    first = manager.generate_hybrid_forecast_answer(
        QUESTION_ID,
        requested_at="2026-03-30T11:00:00",
    )
    second = manager.generate_hybrid_forecast_answer(
        QUESTION_ID,
        requested_at="2026-03-30T12:00:00",
    )

    assert first.forecast_answers[-1].answer_type == "hybrid_forecast"
    assert len(first.prediction_ledger.worker_outputs) >= 4
    assert any(worker.kind == "base_rate" for worker in first.forecast_workers)
    assert any(worker.kind == "reference_class" for worker in first.forecast_workers)
    assert any(worker.kind == "retrieval_synthesis" for worker in first.forecast_workers)
    assert second.forecast_answers[-1].answer_payload["abstained"] is False
    assert any(
        entry.entry_kind == "revision" and entry.metadata.get("generated_by_engine")
        for entry in second.prediction_ledger.entries
    )


def test_forecast_manager_question_service_create_read_update_list_and_resolve_flow(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()

    created = _question_object(
        manager.create_question(ForecastQuestion.from_dict(_question_payload()))
    )
    listed = [_question_object(item) for item in manager.list_questions()]

    assert created.to_dict()["question_text"] == QUESTION_TEXT
    assert created.to_dict()["issue_timestamp"] == QUESTION_ISSUED_AT
    assert [question.forecast_id for question in listed] == [QUESTION_ID]


def test_forecast_manager_acquires_evidence_bundle_with_provider_fallbacks(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    _write_json(
        simulation_data_dir / "sim-001" / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "generated_at": "2026-03-30T09:05:00",
            "graph_id": "graph-sim-001",
            "citation_index": {
                "source": [
                    {
                        "citation_id": "[S1]",
                        "source_id": "src-1",
                        "title": "Uploaded source excerpt",
                        "locator": "files/memo.md#chars=0-120",
                        "summary": "Uploaded excerpt on support dynamics.",
                        "sha256": "abc123",
                    }
                ],
                "graph": [
                    {
                        "citation_id": "[G1]",
                        "title": "Graph build summary",
                        "locator": "graph:sim-001",
                        "summary": "Stored graph provenance.",
                    }
                ],
            },
        },
    )
    _write_json(
        simulation_data_dir / "sim-001" / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:07:00",
            "summary": "Prepared snapshot for evidence acquisition tests.",
        },
    )

    manager = ForecastManager(
        evidence_bundle_service=EvidenceBundleService(
            providers=[
                UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir)),
                UnavailableExternalEvidenceProvider(),
            ]
        )
    )
    manager.create_workspace(_build_workspace())

    refreshed = manager.acquire_evidence_bundle(
        QUESTION_ID,
        provider_ids=[
            "uploaded_local_artifacts",
            "external_live_unconfigured",
        ],
    )

    bundle = refreshed.evidence_bundle
    assert bundle.status == "degraded"
    assert any(
        provider.get("provider_kind") in {"uploaded_local", "uploaded_local_artifact"}
        and provider.get("status") == "ready"
        for provider in bundle.provider_snapshots
    )
    assert any(
        provider.get("provider_kind") in {"live_external", "external_live"}
        and provider.get("status") == "unavailable"
        for provider in bundle.provider_snapshots
    )
    assert any(
        entry.provider_id in {"uploaded_local_artifacts", "uploaded_local_artifact"}
        and entry.citation_id == "[S1]"
        for entry in bundle.source_entries
    )


def test_forecast_manager_generates_hybrid_answer_and_persists_worker_trace(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    manager.create_workspace(_build_workspace())
    manager.update_evidence_bundle(
        QUESTION_ID,
        "bundle-1",
        {
            "status": "ready",
            "entries": [
                {
                    "source_id": "src-support-1",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "uploaded_source",
                    "title": "Uploaded memo supports threshold crossing.",
                    "summary": "Uploaded memo supports threshold crossing.",
                    "citation_id": "[S1]",
                    "timestamps": {"captured_at": "2026-03-30T09:05:00"},
                    "freshness": {"status": "fresh", "score": 0.9},
                    "relevance": {"status": "high", "score": 0.88},
                    "quality": {"status": "strong", "score": 0.91},
                    "conflict_status": "supports",
                },
                {
                    "source_id": "src-support-2",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "prepared_snapshot",
                    "title": "Prepared artifact supports threshold crossing.",
                    "summary": "Prepared artifact supports threshold crossing.",
                    "citation_id": "[S2]",
                    "timestamps": {"captured_at": "2026-03-30T09:06:00"},
                    "freshness": {"status": "fresh", "score": 0.87},
                    "relevance": {"status": "high", "score": 0.8},
                    "quality": {"status": "strong", "score": 0.83},
                    "conflict_status": "supports",
                },
            ],
        },
    )

    updated = manager.generate_hybrid_answer(
        QUESTION_ID,
        issued_at="2026-03-30T12:00:00",
    )

    latest_answer = updated.forecast_answers[-1]
    assert latest_answer.answer_type == "hybrid_forecast"
    assert latest_answer.answer_payload["abstained"] is False
    assert latest_answer.answer_payload["best_estimate"]["value"] > 0.5
    assert any(
        trace["worker_kind"] == "simulation" and trace["used_in_best_estimate"] is False
        for trace in latest_answer.answer_payload["worker_contribution_trace"]
    )
    assert any(
        output.get("worker_kind") == "retrieval_synthesis"
        for output in updated.prediction_ledger.worker_outputs
    )
    assert any(
        entry.worker_id == "worker-retrieval-synthesis"
        for entry in updated.prediction_ledger.entries
    )


def test_forecast_manager_acquire_evidence_bundle_tracks_prediction_entry_ids_not_prediction_ids(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    _write_json(
        simulation_data_dir / "sim-001" / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "generated_at": "2026-03-30T09:05:00",
            "graph_id": "graph-sim-001",
            "citation_index": {
                "source": [
                    {
                        "citation_id": "[S1]",
                        "source_id": "src-1",
                        "title": "Uploaded source excerpt",
                        "locator": "files/memo.md#chars=0-120",
                        "summary": "Uploaded excerpt on support dynamics.",
                        "sha256": "abc123",
                    }
                ],
                "graph": [],
            },
        },
    )
    _write_json(
        simulation_data_dir / "sim-001" / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:07:00",
            "summary": "Prepared snapshot for evidence acquisition tests.",
        },
    )

    workspace = _build_workspace()
    workspace.prediction_ledger.entries[0].entry_id = "entry-issue-1"
    workspace.prediction_ledger.entries[0].prediction_id = INITIAL_PREDICTION_ID
    workspace.prediction_ledger.entries[1].entry_id = "entry-revision-2"
    workspace.prediction_ledger.entries[1].prediction_id = REVISION_PREDICTION_ID
    workspace.prediction_ledger.entries[1].revises_entry_id = "entry-issue-1"
    workspace.prediction_ledger.entries[1].revises_prediction_id = INITIAL_PREDICTION_ID

    manager = ForecastManager(
        evidence_bundle_service=EvidenceBundleService(
            providers=[
                UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir)),
                UnavailableExternalEvidenceProvider(),
            ]
        )
    )
    manager.create_workspace(workspace)

    refreshed = manager.acquire_evidence_bundle(
        QUESTION_ID,
        provider_ids=[
            "uploaded_local_artifacts",
            "external_live_unconfigured",
        ],
    )

    assert refreshed.evidence_bundle.prediction_entry_ids == [
        "entry-issue-1",
        "entry-revision-2",
    ]


def test_forecast_manager_acquire_bundle_only_links_predictions_that_reference_target_bundle(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    _write_json(
        simulation_data_dir / "sim-001" / "grounding_bundle.json",
        {
            "artifact_type": "grounding_bundle",
            "generated_at": "2026-03-30T09:05:00",
            "graph_id": "graph-sim-001",
            "citation_index": {
                "source": [
                    {
                        "citation_id": "[S1]",
                        "source_id": "src-1",
                        "title": "Uploaded source excerpt",
                        "locator": "files/memo.md#chars=0-120",
                        "summary": "Uploaded excerpt on support dynamics.",
                        "sha256": "abc123",
                    }
                ],
                "graph": [],
            },
        },
    )
    _write_json(
        simulation_data_dir / "sim-001" / "prepared_snapshot.json",
        {
            "artifact_type": "prepared_snapshot",
            "generated_at": "2026-03-30T09:07:00",
            "summary": "Prepared snapshot for evidence acquisition tests.",
        },
    )

    manager = ForecastManager(
        evidence_bundle_service=EvidenceBundleService(
            providers=[UploadedLocalArtifactEvidenceProvider(str(simulation_data_dir))]
        )
    )
    manager.create_workspace(_build_workspace())
    manager.create_evidence_bundle(
        QUESTION_ID,
        {
            "bundle_id": "bundle-2",
            "forecast_id": QUESTION_ID,
            "title": "Alternative evidence bundle",
            "summary": "Secondary evidence scope.",
            "source_entries": [],
            "provider_snapshots": [],
            "question_ids": [QUESTION_ID],
            "prediction_entry_ids": [],
            "status": "draft",
            "boundary_note": "Alternative bounded evidence scope.",
            "created_at": QUESTION_ISSUED_AT,
        },
    )

    refreshed = manager.acquire_evidence_bundle(
        QUESTION_ID,
        bundle_id="bundle-2",
        provider_ids=["uploaded_local_artifacts"],
    )

    assert refreshed.evidence_bundle.bundle_id == "bundle-2"
    assert refreshed.evidence_bundle.prediction_entry_ids == []


def test_forecast_manager_prediction_ledger_tracks_immutable_predictions_revisions_and_resolution(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    manager.create_workspace(_build_workspace())

    initial_entry = PredictionLedgerEntry.from_dict(
        _prediction_payload(
            prediction_id=INITIAL_PREDICTION_ID,
            issued_at="2026-03-30T09:10:00",
            revision_number=1,
            prediction={"support_share": 0.62},
        )
    )
    initial_result = _ledger_object(manager.issue_prediction(QUESTION_ID, initial_entry))
    assert initial_result.to_dict()["entries"][0]["prediction_id"] == INITIAL_PREDICTION_ID
    assert initial_result.to_dict()["entries"][0]["issued_at"] == "2026-03-30T09:10:00"
    assert initial_result.to_dict()["final_resolution_state"]["status"] == "pending"

    revision_entry = PredictionLedgerEntry.from_dict(
        _prediction_payload(
            prediction_id=REVISION_PREDICTION_ID,
            issued_at="2026-03-30T10:20:00",
            prediction={"support_share": 0.67},
            revises_prediction_id=INITIAL_PREDICTION_ID,
            entry_kind="revision",
        )
    )
    revised_result = _ledger_object(manager.revise_prediction(QUESTION_ID, revision_entry))
    serialized_revised = revised_result.to_dict()
    assert serialized_revised["issued_predictions"][0]["prediction_id"] == INITIAL_PREDICTION_ID
    assert serialized_revised["prediction_revisions"][0]["prediction_id"] == REVISION_PREDICTION_ID
    assert serialized_revised["prediction_revisions"][0]["revises_entry_id"] == INITIAL_PREDICTION_ID
    assert serialized_revised["prediction_revisions"][0]["issued_at"] == "2026-03-30T10:20:00"
    assert serialized_revised["issued_predictions"][0]["prediction"] == {"support_share": 0.62}
    assert serialized_revised["prediction_revisions"][0]["prediction"] == {"support_share": 0.67}

    resolved_question = _question_object(
        manager.resolve_question(
            QUESTION_ID,
            {
                "status": "resolved",
                "resolved_at": RESOLVED_AT,
                "resolution_note": "Observed support exceeded the threshold.",
                "prediction_entry_ids": [INITIAL_PREDICTION_ID, REVISION_PREDICTION_ID],
                "revision_entry_ids": [REVISION_PREDICTION_ID],
                "worker_output_ids": ["worker-output-1"],
                "evidence_bundle_ids": ["bundle-1"],
            },
        )
    )
    assert resolved_question.to_dict()["status"] == "resolved"

    resolved_ledger = _ledger_object(manager.get_prediction_ledger(QUESTION_ID))
    assert resolved_ledger.to_dict()["final_resolution_state"]["status"] == "resolved"
    assert resolved_ledger.to_dict()["resolved_at"] == RESOLVED_AT

    with pytest.raises(ValueError, match="resolved forecast questions cannot accept new prediction revisions"):
        manager.revise_prediction(
            QUESTION_ID,
            PredictionLedgerEntry.from_dict(
                _prediction_payload(
                    prediction_id="prediction-3",
                    issued_at="2026-03-30T11:00:00",
                    revision_number=3,
                    prediction={"support_share": 0.71},
                    revises_prediction_id=REVISION_PREDICTION_ID,
                )
            ),
        )


def test_forecast_manager_rejects_unknown_evidence_bundle_links_on_predictions(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    manager.create_workspace(_build_workspace())

    with pytest.raises(
        ValueError,
        match="prediction entry references unknown evidence_bundle_ids",
    ):
        manager.issue_prediction(
            QUESTION_ID,
            PredictionLedgerEntry.from_dict(
                {
                    **_prediction_payload(
                        prediction_id="prediction-x",
                        issued_at="2026-03-30T11:00:00",
                        prediction={"support_share": 0.71},
                    ),
                    "evidence_bundle_ids": ["bundle-missing"],
                }
            ),
        )


def test_forecast_manager_rejects_revision_timestamp_regression(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    manager.create_workspace(_build_workspace())

    manager.issue_prediction(
        QUESTION_ID,
        PredictionLedgerEntry.from_dict(
            _prediction_payload(
                prediction_id=INITIAL_PREDICTION_ID,
                issued_at="2026-03-30T09:10:00",
                revision_number=1,
                prediction={"support_share": 0.62},
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="prediction revision timestamp cannot precede the prediction it revises",
    ):
        manager.revise_prediction(
            QUESTION_ID,
            PredictionLedgerEntry.from_dict(
                _prediction_payload(
                    prediction_id="prediction-3",
                    issued_at="2026-03-30T09:05:00",
                    prediction={"support_share": 0.67},
                    revises_prediction_id=INITIAL_PREDICTION_ID,
                    entry_kind="revision",
                )
            ),
        )


def test_forecast_manager_rejects_binary_probability_predictions_for_categorical_questions(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    workspace = _build_nonbinary_workspace(
        question_type="categorical",
        question_spec={"outcome_labels": ["win", "stretch", "miss"]},
    )
    manager.create_workspace(workspace)

    with pytest.raises(
        ValueError,
        match="categorical forecast questions do not accept prediction value_type 'probability'",
    ):
        manager.issue_prediction(
            workspace.forecast_question.forecast_id,
            PredictionLedgerEntry.from_dict(
                {
                    "entry_id": "entry-categorical-invalid",
                    "prediction_id": "entry-categorical-invalid",
                    "forecast_id": workspace.forecast_question.forecast_id,
                    "worker_id": "worker-base-rate",
                    "recorded_at": "2026-03-30T09:10:00",
                    "value_type": "probability",
                    "value": 0.61,
                    "prediction": 0.61,
                    "value_semantics": "forecast_probability",
                    "entry_kind": "issue",
                    "evidence_bundle_ids": ["bundle-1"],
                }
            ),
        )


def test_forecast_manager_rejects_non_numeric_resolved_outcomes_for_numeric_questions(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    workspace = _build_nonbinary_workspace(
        question_type="numeric",
        question_spec={"unit": "usd_millions", "interval_levels": [50, 80, 90]},
    )
    manager.create_workspace(workspace)

    with pytest.raises(
        ValueError,
        match="resolved numeric evaluation cases must include a numeric observed outcome",
    ):
        manager.append_evaluation_case(
            workspace.forecast_question.forecast_id,
            EvaluationCase.from_dict(
                {
                    "case_id": "case-numeric-invalid",
                    "forecast_id": workspace.forecast_question.forecast_id,
                    "criteria_id": "criteria-1",
                    "status": "resolved",
                    "issued_at": "2026-03-30T09:30:00",
                    "prediction_value_type": "numeric_interval",
                    "prediction_value_semantics": "numeric_interval_estimate",
                    "prediction_payload": {
                        "point_estimate": 42,
                        "intervals": [{"level": 80, "low": 36, "high": 50}],
                    },
                    "observed_outcome": {"label": "forty-two"},
                    "resolved_at": RESOLVED_AT,
                }
            ),
        )


def test_forecast_manager_compose_hybrid_forecast_answer_records_outputs_predictions_and_answer(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    ensemble_module = importlib.import_module("app.services.ensemble_manager")
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    _write_ensemble_root(
        simulation_data_dir,
        values=[0.49, 0.57, 0.61, 0.66, 0.72],
    )
    manager = ForecastManager()
    manager.create_workspace(_hybrid_workspace())

    updated = manager.compose_hybrid_forecast_answer(
        QUESTION_ID,
        recorded_at="2026-03-30T11:00:00",
    )

    latest_answer = updated.forecast_answers[-1]
    trace = latest_answer.answer_payload["worker_contribution_trace"]
    simulation_trace = next(item for item in trace if item["worker_id"] == "worker-sim")

    assert latest_answer.answer_type == "hybrid_forecast"
    assert latest_answer.answer_payload["abstain"] is False
    assert latest_answer.answer_payload["best_estimate"]["value_semantics"] == "forecast_probability"
    assert latest_answer.evaluation_summary["status"] == "available"
    assert latest_answer.benchmark_summary["status"] == "available"
    assert latest_answer.backtest_summary["status"] == "not_run"
    assert latest_answer.calibration_summary["status"] == "not_applicable"
    assert latest_answer.confidence_basis["status"] == "available"
    assert latest_answer.answer_payload["simulation_context"]["observed_run_share"] == pytest.approx(0.8)
    assert simulation_trace["influences_best_estimate"] is False
    assert updated.prediction_ledger.to_dict()["worker_outputs"][0]["worker_id"] == "worker-base-rate"
    assert len(updated.prediction_ledger.entries) == 4
    assert updated.prediction_ledger.entries[0].evaluation_summary["status"] == "available"
    assert updated.prediction_ledger.entries[0].confidence_basis["status"] == "available"
    assert updated.prediction_ledger.entries[0].evaluation_case_ids == ["case-1", "case-2", "case-3"]
    assert updated.to_summary_dict()["forecast_answer_count"] == 1


def test_forecast_manager_evaluation_case_lifecycle_links_prediction_context(
    forecast_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    manager = ForecastManager()
    manager.create_workspace(_build_workspace())

    created = manager.append_evaluation_case(
        QUESTION_ID,
        EvaluationCase.from_dict(
            {
                "case_id": "case-extra",
                "forecast_id": QUESTION_ID,
                "criteria_id": "criteria-1",
                "status": "pending",
                "issued_at": "2026-03-30T09:30:00",
                "question_class": "binary_support",
                "prediction_entry_id": INITIAL_PREDICTION_ID,
                "forecast_probability": 0.63,
                "evaluation_split": "rolling_holdout",
                "window_id": "rolling-2026Q2",
                "source": "manual_registry",
            }
        ),
    )
    workspace = created
    case = manager.get_evaluation_case(QUESTION_ID, "case-extra")
    assert case is not None
    assert case.status == "pending"
    assert manager.list_evaluation_cases(QUESTION_ID)[-1].case_id == "case-extra"

    updated = manager.resolve_evaluation_case(
        QUESTION_ID,
        "case-extra",
        observed_outcome={"support_share": 0.59},
        resolved_at="2026-07-01T11:00:00",
        resolution_note="Historical check resolved true.",
    )
    resolved_case = next(item for item in updated.evaluation_cases if item.case_id == "case-extra")
    assert resolved_case.status == "resolved"
    assert resolved_case.resolved_at == "2026-07-01T11:00:00"
    assert resolved_case.observed_outcome == {"support_share": 0.59}
    linked_entry = next(
        entry
        for entry in updated.prediction_ledger.entries
        if entry.entry_id == INITIAL_PREDICTION_ID
    )
    assert "case-extra" in linked_entry.evaluation_case_ids
    assert linked_entry.evaluation_summary["evaluation_case_count"] == 2
    assert linked_entry.confidence_basis["workspace_forecast_id"] == QUESTION_ID


def test_forecast_manager_compose_hybrid_forecast_answer_creates_revisions_on_rerun(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    monkeypatch.setattr(ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
    ensemble_module = importlib.import_module("app.services.ensemble_manager")
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    _write_ensemble_root(
        simulation_data_dir,
        values=[0.49, 0.57, 0.61, 0.66, 0.72],
    )
    manager = ForecastManager()
    manager.create_workspace(_hybrid_workspace())

    manager.compose_hybrid_forecast_answer(
        QUESTION_ID,
        recorded_at="2026-03-30T11:00:00",
    )
    updated = manager.compose_hybrid_forecast_answer(
        QUESTION_ID,
        recorded_at="2026-03-30T12:00:00",
    )

    assert len(updated.prediction_ledger.issued_predictions) == 4
    assert len(updated.prediction_ledger.prediction_revisions) == 4
    assert len(updated.forecast_answers) == 2
    latest_revision = updated.prediction_ledger.prediction_revisions[-1]
    assert latest_revision.entry_kind == "revision"
    assert latest_revision.revision_number == 2
    assert latest_revision.revises_entry_id is not None
