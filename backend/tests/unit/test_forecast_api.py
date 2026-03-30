from __future__ import annotations

import importlib
import json
import sys

from flask import Blueprint
from flask import Flask


QUESTION_ID = "forecast-001"
QUESTION_TEXT = "Will the hybrid system show more than 55% support by June 30, 2026?"
QUESTION_ISSUED_AT = "2026-03-30T09:00:00"
QUESTION_RESOLUTION_DATE = "2026-06-30"
PREDICTION_ONE_ISSUED_AT = "2026-03-30T09:10:00"
PREDICTION_TWO_ISSUED_AT = "2026-03-30T10:20:00"
RESOLVED_AT = "2026-07-01T10:00:00"


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
        "updated_at": QUESTION_ISSUED_AT,
    }


def _criteria_payload():
    return {
        "criteria_id": "criteria-1",
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


def _evidence_bundle_payload():
    return {
        "bundle_id": "bundle-1",
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
    }


def _worker_payload():
    return {
        "worker_id": "worker-sim",
        "kind": "simulation",
        "label": "Scenario Simulation Worker",
        "status": "ready",
        "capabilities": ["scenario_generation"],
        "primary_output_semantics": "scenario_evidence",
    }


def _prediction_payload(
    *,
    prediction_id: str,
    issued_at: str,
    prediction: dict,
    revises_prediction_id: str | None = None,
    entry_kind: str = "issue",
    revision_number: int = 1,
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
                prediction_id="prediction-1",
                issued_at=PREDICTION_ONE_ISSUED_AT,
                prediction={"support_share": 0.62},
            ),
            _prediction_payload(
                prediction_id="prediction-2",
                issued_at=PREDICTION_TWO_ISSUED_AT,
                prediction={"support_share": 0.67},
                revises_prediction_id="prediction-1",
                entry_kind="revision",
                revision_number=2,
            ),
        ],
        "final_resolution_state": final_resolution_state,
        "resolved_at": RESOLVED_AT if final_resolution_state != "pending" else None,
        "resolution_note": "Observed support exceeded the threshold."
        if final_resolution_state != "pending"
        else "",
    }


def _evaluation_case_payload():
    return {
        "case_id": "case-1",
        "criteria_id": "criteria-1",
        "status": "resolved",
        "observed_outcome": {"support_share": 0.58},
        "resolved_at": RESOLVED_AT,
        "resolution_note": "Threshold met.",
    }


def _forecast_answer_payload():
    return {
        "answer_id": "answer-1",
        "answer_type": "simulation_scenario_summary",
        "summary": "Stored scenarios leaned above the threshold, but this is not a real-world probability claim.",
        "worker_ids": ["worker-sim"],
        "prediction_entry_ids": ["prediction-1"],
        "confidence_semantics": "uncalibrated",
    }


def _simulation_worker_contract_payload():
    return {
        "worker_id": "worker-sim",
        "simulation_id": "sim-001",
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "probability_interpretation": "do_not_treat_as_real_world_probability",
    }


def _workspace_payload():
    return {
        "forecast_question": _question_payload(),
        "resolution_criteria": [_criteria_payload()],
        "evidence_bundle": _evidence_bundle_payload(),
        "forecast_workers": [_worker_payload()],
        "prediction_ledger": _ledger_payload(),
        "evaluation_cases": [_evaluation_case_payload()],
        "forecast_answers": [_forecast_answer_payload()],
        "simulation_worker_contract": _simulation_worker_contract_payload(),
    }


def _question_request_payload():
    payload = _workspace_payload()
    payload["question"] = payload.pop("forecast_question")
    return payload


def _load_forecast_api_module():
    api_package = importlib.import_module("app.api")
    api_package.forecast_bp = Blueprint("forecast", __name__)
    sys.modules.pop("app.api.forecast", None)
    return importlib.import_module("app.api.forecast")


def _build_test_client(forecast_module):
    app = Flask(__name__)
    app.register_blueprint(forecast_module.forecast_bp, url_prefix="/api/forecast")
    return app.test_client()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_ensemble_root(
    simulation_data_dir,
    *,
    simulation_id="sim-001",
    ensemble_id="0001",
    metric_id="survey.support_share",
    values,
):
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


def _hybrid_question_request_payload():
    payload = _question_request_payload()
    payload["forecast_workers"] = [
        {
            "worker_id": "worker-base-rate",
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
                },
            },
        },
        {
            "worker_id": "worker-reference",
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
            },
        },
        {
            "worker_id": "worker-retrieval",
            "kind": "retrieval_synthesis",
            "label": "Retrieval synthesis worker",
            "status": "ready",
            "capabilities": ["bounded_local_retrieval"],
            "primary_output_semantics": "forecast_probability",
            "metadata": {"worker_family": "retrieval_synthesis"},
        },
        {
            "worker_id": "worker-sim",
            "kind": "simulation",
            "label": "Scenario simulation worker",
            "status": "ready",
            "capabilities": ["scenario_generation"],
            "primary_output_semantics": "scenario_evidence",
            "metadata": {"worker_family": "simulation_adapter"},
        },
    ]
    payload["evidence_bundle"] = {
        **_evidence_bundle_payload(),
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
        "providers": [
            {
                "provider_id": "uploaded_local_artifacts",
                "provider_kind": "uploaded_local_artifact",
                "status": "ready",
                "collected_at": QUESTION_ISSUED_AT,
                "boundary_note": "Local artifacts only.",
            }
        ],
    }
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
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.61},
            "resolved_at": "2025-11-01T00:00:00",
        },
        {
            "case_id": "case-2",
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.57},
            "resolved_at": "2025-12-01T00:00:00",
        },
        {
            "case_id": "case-3",
            "criteria_id": "criteria-1",
            "status": "resolved",
            "observed_outcome": {"survey.support_share": 0.49},
            "resolved_at": "2026-01-01T00:00:00",
        },
    ]
    payload["forecast_answers"] = []
    payload["simulation_worker_contract"] = {
        "worker_id": "worker-sim",
        "simulation_id": "sim-001",
        "ensemble_ids": ["0001"],
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "probability_interpretation": "do_not_treat_as_real_world_probability",
    }
    return payload


def _write_simulation_metrics(
    simulation_data_dir,
    simulation_id: str,
    *,
    ensemble_id: str = "0001",
    values: list[float],
    metric_id: str = "survey.support_share",
):
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


def test_forecast_capabilities_expose_simulation_worker_semantics():
    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    response = client.get("/api/forecast/capabilities")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["capabilities"]["simulation"]["role"] == "scenario_worker"
    assert payload["capabilities"]["simulation"]["probability_interpretation"] == (
        "do_not_treat_as_real_world_probability"
    )
    assert payload["capabilities"]["evidence_bundle"]["primary_semantics"] == (
        "retrieval_quality_bounded"
    )


def test_generate_hybrid_forecast_answer_route_returns_hybrid_answer(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    workspace_payload = _workspace_payload()
    workspace_payload["simulation_worker_contract"]["ensemble_ids"] = ["0001"]
    workspace_payload["prediction_ledger"] = {
        "forecast_id": QUESTION_ID,
        "entries": [],
        "worker_outputs": [],
        "resolution_history": [],
        "final_resolution_state": {"status": "pending"},
    }
    workspace_payload["forecast_answers"] = []
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
            "observed_outcome": {"survey.support_share": 0.49},
            "resolved_at": "2025-12-01T00:00:00",
        },
    ]
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
        }
    ]

    _write_simulation_metrics(simulation_data_dir, "sim-001", values=[0.62, 0.58, 0.51])

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post("/api/forecast/workspaces", json=workspace_payload)
    assert create_response.status_code == 201

    generate_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/forecast-answers/generate",
        json={"requested_at": "2026-03-30T11:00:00"},
    )

    assert generate_response.status_code == 200
    payload = generate_response.get_json()
    workspace = payload["workspace"]
    latest_answer = workspace["forecast_answers"][-1]
    assert latest_answer["answer_type"] == "hybrid_forecast"
    assert latest_answer["answer_payload"]["abstained"] is False
    assert latest_answer["answer_payload"]["best_estimate"]["semantics"] == "forecast_probability"
    assert latest_answer["evaluation_summary"]["status"] == "available"
    assert latest_answer["benchmark_summary"]["status"] == "available"
    assert latest_answer["backtest_summary"]["status"] == "not_run"
    assert latest_answer["calibration_summary"]["status"] == "not_applicable"
    assert latest_answer["confidence_basis"]["status"] == "available"
    assert any(
        item["worker_kind"] == "simulation"
        for item in latest_answer["answer_payload"]["worker_contribution_trace"]
    )


def test_evaluation_case_routes_support_read_update_and_resolve(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post("/api/forecast/workspaces", json=_workspace_payload())
    assert create_response.status_code == 201

    create_case_response = client.post(
        f"/api/forecast/workspaces/{QUESTION_ID}/evaluation-cases",
        json={
            "evaluation_case": {
                "case_id": "case-extra",
                "criteria_id": "criteria-1",
                "status": "pending",
                "issued_at": QUESTION_ISSUED_AT,
                "question_class": "binary_support",
                "prediction_entry_id": "prediction-1",
                "forecast_probability": 0.63,
                "evaluation_split": "rolling_holdout",
                "window_id": "rolling-2026Q2",
                "source": "manual_registry",
            }
        },
    )
    assert create_case_response.status_code == 200

    list_response = client.get(f"/api/forecast/workspaces/{QUESTION_ID}/evaluation-cases")
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert [item["case_id"] for item in list_payload["evaluation_cases"]] == ["case-1", "case-extra"]

    update_response = client.patch(
        f"/api/forecast/workspaces/{QUESTION_ID}/evaluation-cases/case-extra",
        json={
            "evaluation_case": {
                "case_id": "case-extra",
                "criteria_id": "criteria-1",
                "status": "pending",
                "issued_at": QUESTION_ISSUED_AT,
                "question_class": "binary_support",
                "prediction_entry_id": "prediction-1",
                "forecast_probability": 0.63,
                "evaluation_split": "rolling_holdout",
                "window_id": "rolling-2026Q2",
                "source": "manual_registry",
                "notes": ["Updated via API route."],
            }
        },
    )
    assert update_response.status_code == 200

    resolve_response = client.post(
        f"/api/forecast/workspaces/{QUESTION_ID}/evaluation-cases/case-extra/resolve",
        json={
            "observed_outcome": {"survey.support_share": 0.59},
            "resolved_at": "2026-07-01T11:00:00",
            "resolution_note": "Historical comparison resolved true.",
        },
    )
    assert resolve_response.status_code == 200
    resolve_payload = resolve_response.get_json()
    resolved_case = next(
        item for item in resolve_payload["workspace"]["evaluation_cases"] if item["case_id"] == "case-extra"
    )
    assert resolved_case["status"] == "resolved"
    assert resolved_case["resolved_at"] == "2026-07-01T11:00:00"
    assert resolved_case["confidence_basis"]["status"] == "resolved"


def test_forecast_question_routes_round_trip_question_primary_object(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post(
        "/api/forecast/questions",
        json=_question_request_payload(),
    )

    assert create_response.status_code == 201
    created_payload = create_response.get_json()
    assert created_payload["success"] is True
    assert created_payload["question"]["question_text"] == QUESTION_TEXT
    assert created_payload["question"]["issue_timestamp"] == QUESTION_ISSUED_AT

    list_response = client.get("/api/forecast/questions")
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload["success"] is True
    assert list_payload["questions"][0]["question_text"] == QUESTION_TEXT
    assert list_payload["questions"][0]["issue_timestamp"] == QUESTION_ISSUED_AT

    get_response = client.get(f"/api/forecast/questions/{QUESTION_ID}")
    assert get_response.status_code == 200
    get_payload = get_response.get_json()
    assert get_payload["question"]["question_text"] == QUESTION_TEXT
    assert get_payload["question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert get_payload["prediction_ledger"]["final_resolution_state"] == "pending"

    update_response = client.patch(
        f"/api/forecast/questions/{QUESTION_ID}",
        json={
            "question": {
                "question_text": "Will the hybrid system show more than 60% support by June 30, 2026?",
                "abstention_conditions": [
                    "Do not issue if no named resolution source is available.",
                    "Do not update the issue timestamp when editing the text.",
                ],
            }
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.get_json()
    assert updated_payload["question"]["question_text"] == (
        "Will the hybrid system show more than 60% support by June 30, 2026?"
    )
    assert updated_payload["question"]["issue_timestamp"] == QUESTION_ISSUED_AT

    resolve_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/resolve",
        json={
            "status": "resolved",
            "resolved_at": RESOLVED_AT,
            "resolution_note": "Observed support exceeded the threshold.",
            "prediction_entry_ids": ["prediction-1", "prediction-2"],
            "revision_entry_ids": ["prediction-2"],
            "worker_output_ids": ["worker-output-1"],
            "evidence_bundle_ids": ["bundle-1"],
        },
    )
    assert resolve_response.status_code == 200
    resolved_payload = resolve_response.get_json()
    assert resolved_payload["question"]["status"] == "resolved"
    assert resolved_payload["question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert resolved_payload["prediction_ledger"]["final_resolution_state"] == "resolved"
    assert resolved_payload["prediction_ledger"]["resolved_at"] == RESOLVED_AT


def test_forecast_question_routes_accept_non_binary_question_specs_and_typed_evaluation_cases(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post(
        "/api/forecast/questions",
        json={
            "question": {
                **_question_payload(),
                "forecast_id": "forecast-nonbinary",
                "question_text": "Which launch posture will be observed by June 30, 2026?",
                "question": "Which launch posture will be observed by June 30, 2026?",
                "question_type": "categorical",
                "resolution_criteria_ids": ["criteria-launch"],
                "question_spec": {
                    "outcome_labels": ["win", "stretch", "miss"],
                },
            },
            "resolution_criteria": [
                {
                    "criteria_id": "criteria-launch",
                    "label": "Observed launch posture",
                    "description": "Resolve against the named observed posture.",
                    "resolution_date": QUESTION_RESOLUTION_DATE,
                    "criteria_type": "manual",
                    "thresholds": {},
                }
            ],
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.get_json()
    assert created_payload["question"]["question_type"] == "categorical"
    assert created_payload["question"]["question_spec"]["outcome_labels"] == [
        "win",
        "stretch",
        "miss",
    ]

    case_response = client.post(
        "/api/forecast/workspaces/forecast-nonbinary/evaluation-cases",
        json={
            "evaluation_case": {
                "case_id": "case-nonbinary",
                "criteria_id": "criteria-launch",
                "status": "resolved",
                "issued_at": QUESTION_ISSUED_AT,
                "question_class": "launch_posture",
                "prediction_value_type": "categorical_distribution",
                "prediction_value_semantics": "forecast_distribution",
                "prediction_payload": {
                    "distribution": {"win": 0.62, "stretch": 0.24, "miss": 0.14},
                    "top_label": "win",
                },
                "observed_outcome": {"label": "win"},
                "resolved_at": RESOLVED_AT,
            }
        },
    )

    assert case_response.status_code == 200
    case_payload = case_response.get_json()
    appended_case = next(
        item
        for item in case_payload["workspace"]["evaluation_cases"]
        if item["case_id"] == "case-nonbinary"
    )
    assert appended_case["prediction_value_type"] == "categorical_distribution"
    assert appended_case["prediction_value_semantics"] == "forecast_distribution"
    assert appended_case["prediction_payload"]["top_label"] == "win"


def test_forecast_prediction_routes_reject_binary_probability_payloads_for_categorical_questions(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post(
        "/api/forecast/questions",
        json={
            "question": {
                **_question_payload(),
                "forecast_id": "forecast-categorical-invalid",
                "question_text": "Which launch posture will be observed by June 30, 2026?",
                "question": "Which launch posture will be observed by June 30, 2026?",
                "question_type": "categorical",
                "resolution_criteria_ids": ["criteria-launch"],
                "question_spec": {"outcome_labels": ["win", "stretch", "miss"]},
            },
            "resolution_criteria": [
                {
                    "criteria_id": "criteria-launch",
                    "label": "Observed launch posture",
                    "description": "Resolve against the named observed posture.",
                    "resolution_date": QUESTION_RESOLUTION_DATE,
                    "criteria_type": "manual",
                    "thresholds": {},
                }
            ],
            "forecast_workers": [
                {
                    "worker_id": "worker-base-rate",
                    "kind": "base_rate",
                    "label": "Base-rate worker",
                    "status": "ready",
                    "capabilities": ["benchmark_lookup"],
                    "primary_output_semantics": "forecast_distribution",
                }
            ],
        },
    )
    assert create_response.status_code == 201

    issue_response = client.post(
        "/api/forecast/questions/forecast-categorical-invalid/predictions",
        json={
            "prediction": {
                "entry_id": "entry-invalid",
                "prediction_id": "entry-invalid",
                "forecast_id": "forecast-categorical-invalid",
                "worker_id": "worker-base-rate",
                "recorded_at": PREDICTION_ONE_ISSUED_AT,
                "issued_at": PREDICTION_ONE_ISSUED_AT,
                "value_type": "probability",
                "value": 0.61,
                "prediction": 0.61,
                "value_semantics": "forecast_probability",
                "entry_kind": "issue",
            }
        },
    )

    assert issue_response.status_code == 400
    assert "categorical forecast questions do not accept prediction value_type" in issue_response.get_json()["error"]


def test_forecast_evaluation_case_routes_reject_non_numeric_observed_outcomes_for_numeric_questions(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post(
        "/api/forecast/questions",
        json={
            "question": {
                **_question_payload(),
                "forecast_id": "forecast-numeric-invalid",
                "question_text": "What ARR value will be observed by June 30, 2026?",
                "question": "What ARR value will be observed by June 30, 2026?",
                "question_type": "numeric",
                "resolution_criteria_ids": ["criteria-arr"],
                "question_spec": {
                    "unit": "usd_millions",
                    "interval_levels": [50, 80, 90],
                },
            },
            "resolution_criteria": [
                {
                    "criteria_id": "criteria-arr",
                    "label": "Observed ARR",
                    "description": "Resolve against the observed ARR value.",
                    "resolution_date": QUESTION_RESOLUTION_DATE,
                    "criteria_type": "manual",
                    "thresholds": {},
                }
            ],
        },
    )
    assert create_response.status_code == 201

    case_response = client.post(
        "/api/forecast/workspaces/forecast-numeric-invalid/evaluation-cases",
        json={
            "evaluation_case": {
                "case_id": "case-numeric-invalid",
                "criteria_id": "criteria-arr",
                "status": "resolved",
                "issued_at": QUESTION_ISSUED_AT,
                "prediction_value_type": "numeric_interval",
                "prediction_value_semantics": "numeric_interval_estimate",
                "prediction_payload": {
                    "point_estimate": 42,
                    "intervals": [{"level": 80, "low": 36, "high": 50}],
                },
                "observed_outcome": {"label": "forty-two"},
                "resolved_at": RESOLVED_AT,
            }
        },
    )

    assert case_response.status_code == 400
    assert "resolved numeric evaluation cases must include a numeric observed outcome" in case_response.get_json()["error"]


def test_forecast_prediction_ledger_issue_and_revision_routes_round_trip_history(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    client.post("/api/forecast/questions", json=_question_request_payload())

    issue_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/predictions",
        json={
            "prediction": _prediction_payload(
                prediction_id="prediction-1",
                issued_at=PREDICTION_ONE_ISSUED_AT,
                prediction={"support_share": 0.62},
            )
        },
    )
    assert issue_response.status_code == 200
    issue_payload = issue_response.get_json()
    assert issue_payload["prediction_ledger"]["entries"][0]["prediction_id"] == "prediction-1"
    assert issue_payload["prediction_ledger"]["entries"][0]["issued_at"] == PREDICTION_ONE_ISSUED_AT

    revision_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/predictions/prediction-1/revisions",
        json={
            "prediction": _prediction_payload(
                prediction_id="prediction-2",
                issued_at=PREDICTION_TWO_ISSUED_AT,
                prediction={"support_share": 0.67},
                revises_prediction_id="prediction-1",
                entry_kind="revision",
                revision_number=2,
            )
        },
    )
    assert revision_response.status_code == 200
    revision_payload = revision_response.get_json()
    assert revision_payload["prediction_ledger"]["entries"][1]["prediction_id"] == "prediction-2"
    assert revision_payload["prediction_ledger"]["entries"][1]["revises_prediction_id"] == "prediction-1"
    assert revision_payload["prediction_ledger"]["entries"][1]["issued_at"] == PREDICTION_TWO_ISSUED_AT

    ledger_response = client.get(f"/api/forecast/questions/{QUESTION_ID}/ledger")
    assert ledger_response.status_code == 200
    ledger_payload = ledger_response.get_json()
    assert ledger_payload["prediction_ledger"]["entries"][0]["prediction_id"] == "prediction-1"
    assert ledger_payload["prediction_ledger"]["entries"][1]["prediction_id"] == "prediction-2"


def test_forecast_evidence_routes_support_read_update_refresh_and_provider_status(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
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
            "summary": "Prepared snapshot for API evidence tests.",
        },
    )

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)
    client.post("/api/forecast/questions", json=_question_request_payload())

    get_response = client.get(f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles")
    assert get_response.status_code == 200
    get_payload = get_response.get_json()
    assert get_payload["success"] is True
    assert get_payload["active_bundle_id"] == "bundle-1"
    assert get_payload["evidence_bundles"][0]["question_ids"] == [QUESTION_ID]

    update_response = client.patch(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1",
        json={
            "evidence_bundle": {
                "summary": "Updated evidence summary with explicit bounded semantics.",
                "source_entries": [
                    {
                        "source_id": "manual-gap",
                        "provider_id": "manual_review",
                        "provider_kind": "manual",
                        "kind": "missing_evidence",
                        "title": "Missing live corroboration",
                        "summary": "Operator noted that no live corroboration was attached.",
                        "timestamps": {"captured_at": QUESTION_ISSUED_AT},
                        "freshness": {"status": "unknown", "score": 0.1},
                        "relevance": {"score": 0.4},
                        "provenance": {"provider": "manual_review"},
                        "quality": {"score": 0.0},
                        "conflict_status": "unknown",
                        "missing_evidence_markers": [
                            {
                                "kind": "live_corroboration_missing",
                                "reason": "Operator noted that no live corroboration was attached.",
                            }
                        ],
                    }
                ],
            }
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.get_json()
    assert update_payload["workspace"]["evidence_bundle"]["summary"].startswith("Updated evidence summary")
    marker = update_payload["workspace"]["evidence_bundle"]["source_entries"][0]["missing_evidence_markers"][0]
    marker_code = (
        marker
        if isinstance(marker, str)
        else marker.get("code") or marker.get("kind")
    )
    assert marker_code == "live_corroboration_missing"

    provider_response = client.get("/api/forecast/evidence-providers")
    assert provider_response.status_code == 200
    provider_payload = provider_response.get_json()
    assert provider_payload["providers"][0]["provider_id"] == "uploaded_local_artifacts"

    question_provider_response = client.get(
        f"/api/forecast/questions/{QUESTION_ID}/evidence/providers"
    )
    assert question_provider_response.status_code == 200
    question_provider_payload = question_provider_response.get_json()
    question_provider_ids = {
        provider["provider_id"] for provider in question_provider_payload["providers"]
    }
    assert "uploaded_local_artifacts" in question_provider_ids
    assert "external_live_unconfigured" in question_provider_ids

    refresh_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1/acquire",
        json={"provider_ids": ["uploaded_local_artifacts", "external_live_unconfigured"]},
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.get_json()
    assert refresh_payload["workspace"]["evidence_bundle"]["status"] == "partial"
    provider_status = {
        provider["provider_id"]: provider["status"]
        for provider in refresh_payload["workspace"]["evidence_bundle"]["provider_snapshots"]
    }
    assert (
        provider_status.get("uploaded_local_artifacts")
        or provider_status.get("uploaded_local_artifact")
    ) == "ready"
    assert (
        provider_status.get("external_live_unconfigured")
        or provider_status.get("live_external")
    ) == "unavailable"
    assert "provider_unavailable" in refresh_payload["workspace"]["evidence_bundle"]["uncertainty_summary"]["causes"]


def test_forecast_evidence_bundle_round_trip_with_public_aliases_does_not_duplicate_provider_entries(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
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
            "summary": "Prepared snapshot for API evidence tests.",
        },
    )

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)
    client.post("/api/forecast/questions", json=_question_request_payload())

    get_response = client.get(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1"
    )
    assert get_response.status_code == 200
    round_trip_bundle = get_response.get_json()["evidence_bundle"]
    round_trip_bundle["summary"] = "Round-tripped through public aliases."

    patch_response = client.patch(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1",
        json={"evidence_bundle": round_trip_bundle},
    )
    assert patch_response.status_code == 200

    refresh_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1/acquire",
        json={"provider_ids": ["uploaded_local_artifacts", "external_live_unconfigured"]},
    )
    assert refresh_response.status_code == 200
    refreshed_bundle = refresh_response.get_json()["workspace"]["evidence_bundle"]

    assert (
        len(
            [
                entry for entry in refreshed_bundle["source_entries"]
                if entry.get("citation_id") == "[S1]"
            ]
        )
        == 1
    )
    assert (
        len(
            [
                provider for provider in refreshed_bundle["provider_snapshots"]
                if provider.get("provider_id") == "uploaded_local_artifacts"
            ]
        )
        == 1
    )
    assert (
        len(
            [
                provider for provider in refreshed_bundle["provider_snapshots"]
                if provider.get("provider_id") == "external_live_unconfigured"
            ]
        )
        == 1
    )


def test_forecast_acquire_route_defaults_match_legacy_local_only_refresh(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
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
            "summary": "Prepared snapshot for API evidence tests.",
        },
    )

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)
    client.post("/api/forecast/questions", json=_question_request_payload())

    legacy_refresh_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/evidence/refresh",
        json={},
    )
    assert legacy_refresh_response.status_code == 200
    legacy_bundle = legacy_refresh_response.get_json()["evidence_bundle"]
    legacy_provider_ids = {
        provider["provider_id"] for provider in legacy_bundle["provider_snapshots"]
    }

    acquire_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1/acquire",
        json={},
    )
    assert acquire_response.status_code == 200
    acquired_bundle = acquire_response.get_json()["workspace"]["evidence_bundle"]
    acquired_provider_ids = {
        provider["provider_id"] for provider in acquired_bundle["provider_snapshots"]
    }

    assert acquired_provider_ids == legacy_provider_ids
    assert acquired_bundle["status"] == legacy_bundle["status"]
    assert "external_live_unconfigured" not in acquired_provider_ids
    assert "provider_unavailable" not in acquired_bundle["uncertainty_summary"]["causes"]


def test_forecast_bundle_specific_acquire_route_rejects_non_list_provider_ids(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)
    client.post("/api/forecast/questions", json=_question_request_payload())

    response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/evidence-bundles/bundle-1/acquire",
        json={"provider_ids": "uploaded_local_artifacts"},
    )

    assert response.status_code == 400
    assert "provider_ids must be a list" in response.get_json()["error"]


def test_forecast_answer_compose_route_returns_hybrid_trace_and_listable_answers(
    forecast_data_dir,
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))
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

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)
    create_response = client.post(
        "/api/forecast/questions",
        json=_hybrid_question_request_payload(),
    )
    assert create_response.status_code == 201

    compose_response = client.post(
        f"/api/forecast/questions/{QUESTION_ID}/forecast-answers/compose",
        json={"recorded_at": "2026-03-30T11:00:00"},
    )
    assert compose_response.status_code == 200
    compose_payload = compose_response.get_json()
    assert compose_payload["forecast_answer"]["answer_type"] == "hybrid_forecast"
    assert compose_payload["forecast_answer"]["answer_payload"]["abstain"] is False
    assert compose_payload["forecast_answer"]["answer_payload"]["best_estimate"]["value_semantics"] == (
        "forecast_probability"
    )
    simulation_trace = next(
        item
        for item in compose_payload["forecast_answer"]["answer_payload"]["worker_contribution_trace"]
        if item["worker_id"] == "worker-sim"
    )
    assert simulation_trace["influences_best_estimate"] is False
    assert len(compose_payload["workspace"]["prediction_ledger"]["entries"]) == 4

    list_response = client.get(f"/api/forecast/questions/{QUESTION_ID}/forecast-answers")
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert len(list_payload["forecast_answers"]) == 1
    assert list_payload["forecast_answers"][0]["answer_type"] == "hybrid_forecast"


def test_forecast_legacy_workspace_endpoints_still_accept_question_primary_payload(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    create_response = client.post(
        "/api/forecast/workspaces",
        json=_workspace_payload(),
    )

    assert create_response.status_code == 201
    created_payload = create_response.get_json()
    assert created_payload["success"] is True
    assert created_payload["workspace"]["forecast_question"]["question_text"] == QUESTION_TEXT
    assert created_payload["workspace"]["forecast_question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert created_payload["workspace"]["prediction_ledger"]["final_resolution_state"] == "pending"

    list_response = client.get("/api/forecast/workspaces")
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload["workspaces"][0]["worker_kinds"] == ["simulation"]

    get_response = client.get(f"/api/forecast/workspaces/{QUESTION_ID}")
    assert get_response.status_code == 200
    workspace_payload = get_response.get_json()["workspace"]
    assert len(workspace_payload["prediction_ledger"]["entries"]) == 2
    assert len(workspace_payload["forecast_answers"]) == 1
    assert len(workspace_payload["evaluation_cases"]) == 1
    assert workspace_payload["forecast_question"]["question_text"] == QUESTION_TEXT
    assert workspace_payload["forecast_question"]["issue_timestamp"] == QUESTION_ISSUED_AT
    assert workspace_payload["simulation_worker_contract"]["simulation_id"] == "sim-001"


def test_hybrid_answer_route_returns_aggregated_answer_with_worker_trace(
    forecast_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(manager_module.ForecastManager, "FORECAST_DATA_DIR", str(forecast_data_dir))

    forecast_module = _load_forecast_api_module()
    client = _build_test_client(forecast_module)

    workspace_payload = _workspace_payload()
    workspace_payload["evidence_bundle"]["status"] = "ready"
    workspace_payload["evidence_bundle"]["entries"] = [
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
    ]

    create_response = client.post("/api/forecast/workspaces", json=workspace_payload)

    assert create_response.status_code == 201

    run_response = client.post(
        f"/api/forecast/workspaces/{QUESTION_ID}/hybrid-answer",
        json={"issued_at": "2026-03-30T12:00:00"},
    )

    assert run_response.status_code == 200
    payload = run_response.get_json()
    assert payload["success"] is True
    answer = payload["forecast_answer"]
    assert answer["answer_type"] == "hybrid_forecast"
    assert answer["answer_payload"]["best_estimate"]["value"] > 0.5
    assert any(
        trace["worker_kind"] == "simulation" and trace["used_in_best_estimate"] is False
        for trace in answer["answer_payload"]["worker_contribution_trace"]
    )
