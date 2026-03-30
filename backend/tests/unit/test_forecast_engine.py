from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.models.forecasting import ForecastWorkspaceRecord


QUESTION_ID = "forecast-001"
QUESTION_ISSUED_AT = "2026-03-30T09:00:00"
QUESTION_RESOLUTION_DATE = "2026-06-30"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_ensemble_root(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
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


def _workspace_payload(*, include_non_simulation_workers: bool = True) -> dict:
    workers = []
    if include_non_simulation_workers:
        workers.extend(
            [
                {
                    "worker_id": "worker-base-rate",
                    "forecast_id": QUESTION_ID,
                    "kind": "analytical",
                    "label": "Base-rate benchmark worker",
                    "status": "ready",
                    "capabilities": ["benchmark_lookup"],
                    "primary_output_semantics": "forecast_probability",
                    "metadata": {
                        "worker_family": "base_rate",
                        "benchmark": {
                            "estimate": 0.41,
                            "sample_count": 24,
                            "assumptions": [
                                "Comparable baseline conditions remain directionally relevant.",
                            ],
                            "counterevidence": [
                                "The benchmark predates the latest support shift.",
                            ],
                        },
                    },
                },
                {
                    "worker_id": "worker-reference",
                    "forecast_id": QUESTION_ID,
                    "kind": "analytical",
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
                        "assumptions": [
                            "The chosen cases remain a relevant reference class.",
                        ],
                    },
                },
                {
                    "worker_id": "worker-retrieval",
                    "forecast_id": QUESTION_ID,
                    "kind": "retrieval",
                    "label": "Retrieval synthesis worker",
                    "status": "ready",
                    "capabilities": ["bounded_local_retrieval"],
                    "primary_output_semantics": "retrieval_evidence",
                    "metadata": {"worker_family": "retrieval_synthesis"},
                },
            ]
        )
    workers.append(
        {
            "worker_id": "worker-sim",
            "forecast_id": QUESTION_ID,
            "kind": "simulation",
            "label": "Scenario simulation worker",
            "status": "ready",
            "capabilities": ["scenario_generation"],
            "primary_output_semantics": "scenario_evidence",
            "metadata": {"worker_family": "simulation_adapter"},
        }
    )
    source_entries = []
    if include_non_simulation_workers:
        source_entries = [
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
        ]
    return {
        "forecast_question": {
            "forecast_id": QUESTION_ID,
            "project_id": "proj-1",
            "title": "Policy support outlook",
            "question": "Will observed support exceed 55% by June 30, 2026?",
            "question_text": "Will observed support exceed 55% by June 30, 2026?",
            "question_type": "binary",
            "status": "active",
            "horizon": {"type": "date", "value": QUESTION_RESOLUTION_DATE},
            "resolution_criteria_ids": ["criteria-1"],
            "owner": "forecasting-team",
            "source": "manual-entry",
            "abstention_conditions": [
                "Do not issue if only simulation scenario evidence is available.",
            ],
            "primary_simulation_id": "sim-001",
            "issue_timestamp": QUESTION_ISSUED_AT,
            "issued_at": QUESTION_ISSUED_AT,
            "created_at": QUESTION_ISSUED_AT,
            "updated_at": QUESTION_ISSUED_AT,
        },
        "resolution_criteria": [
            {
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
        ],
        "evidence_bundle": {
            "bundle_id": "bundle-1",
            "forecast_id": QUESTION_ID,
            "title": "Evidence bundle",
            "summary": "Uploaded/local evidence and simulation artifacts.",
            "source_entries": source_entries,
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
            "status": "ready" if source_entries else "draft",
            "boundary_note": "Evidence remains bounded to stored providers and artifacts.",
            "created_at": QUESTION_ISSUED_AT,
        },
        "forecast_workers": workers,
        "prediction_ledger": {
            "forecast_id": QUESTION_ID,
            "entries": [],
            "worker_outputs": [],
            "resolution_history": [],
            "final_resolution_state": "pending",
        },
        "evaluation_cases": [
            {
                "case_id": "case-1",
                "forecast_id": QUESTION_ID,
                "criteria_id": "criteria-1",
                "status": "resolved",
                "observed_outcome": {"survey.support_share": 0.61},
                "resolved_at": "2025-11-01T00:00:00",
                "question_class": "binary_support",
                "confidence_basis": {"status": "resolved"},
            },
            {
                "case_id": "case-2",
                "forecast_id": QUESTION_ID,
                "criteria_id": "criteria-1",
                "status": "resolved",
                "observed_outcome": {"survey.support_share": 0.57},
                "resolved_at": "2025-12-01T00:00:00",
                "question_class": "binary_support",
                "confidence_basis": {"status": "resolved"},
            },
            {
                "case_id": "case-3",
                "forecast_id": QUESTION_ID,
                "criteria_id": "criteria-1",
                "status": "resolved",
                "observed_outcome": {"survey.support_share": 0.49},
                "resolved_at": "2026-01-01T00:00:00",
                "question_class": "binary_support",
                "confidence_basis": {"status": "resolved"},
            },
        ],
        "forecast_answers": [],
        "simulation_worker_contract": {
            "worker_id": "worker-sim",
            "forecast_id": QUESTION_ID,
            "simulation_id": "sim-001",
            "ensemble_ids": ["0001"],
            "prepare_artifact_paths": [
                "uploads/simulations/sim-001/prepared_snapshot.json",
            ],
            "probability_interpretation": "do_not_treat_as_real_world_probability",
        },
    }


def test_hybrid_engine_assembles_best_estimate_without_let_simulation_dominate(
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.ensemble_manager")
    monkeypatch.setattr(
        manager_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    _write_ensemble_root(
        simulation_data_dir,
        "sim-001",
        values=[0.49, 0.57, 0.61, 0.66, 0.72],
    )

    forecast_engine_module = importlib.import_module("app.services.forecast_engine")
    workspace = ForecastWorkspaceRecord.from_dict(_workspace_payload())

    result = forecast_engine_module.HybridForecastEngine(
        simulation_data_dir=str(simulation_data_dir)
    ).execute(workspace, recorded_at="2026-03-30T11:00:00")

    answer = result.forecast_answer
    payload = answer.answer_payload

    assert answer.answer_type == "hybrid_forecast"
    assert payload["abstain"] is False
    assert payload["best_estimate"]["value_semantics"] == "forecast_probability"
    assert payload["best_estimate"]["estimate"] == pytest.approx(0.52, abs=0.08)
    assert payload["evaluation_summary"]["status"] == "available"
    assert payload["evaluation_summary"]["resolved_case_count"] == 3
    assert payload["benchmark_summary"]["status"] == "available"
    assert payload["confidence_basis"]["status"] == "available"
    assert payload["backtest_summary"]["status"] == "not_run"
    assert payload["calibration_summary"]["status"] == "not_applicable"
    assert "worker_disagreement" in payload["uncertainty_decomposition"]["drivers"]
    assert "conflicting_evidence" in payload["uncertainty_decomposition"]["drivers"]

    trace = {item["worker_id"]: item for item in payload["worker_contribution_trace"]}
    assert trace["worker-sim"]["value_semantics"] == "observed_run_share"
    assert trace["worker-sim"]["contribution_role"] == "scenario_context"
    assert trace["worker-sim"]["influences_best_estimate"] is False
    assert trace["worker-retrieval"]["influences_best_estimate"] is True
    assert trace["worker-reference"]["influences_best_estimate"] is True
    assert trace["worker-base-rate"]["influences_best_estimate"] is True
    assert trace["worker-sim"]["effective_weight"] < trace["worker-retrieval"]["effective_weight"]
    assert payload["simulation_context"]["observed_run_share"] == pytest.approx(0.8)
    assert any("contrary brief" in item.lower() for item in payload["counterevidence"])
    assert len(result.prediction_entries) == 4
    assert result.prediction_entries[0].evaluation_summary["status"] == "available"
    assert result.prediction_entries[0].benchmark_summary["status"] == "available"
    assert result.prediction_entries[0].confidence_basis["status"] == "available"
    assert result.prediction_entries[0].evaluation_case_ids == ["case-1", "case-2", "case-3"]


def test_hybrid_engine_abstains_when_only_simulation_scenario_evidence_is_available(
    simulation_data_dir,
    monkeypatch,
):
    manager_module = importlib.import_module("app.services.ensemble_manager")
    monkeypatch.setattr(
        manager_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    _write_ensemble_root(
        simulation_data_dir,
        "sim-001",
        values=[0.44, 0.56, 0.59, 0.61],
    )

    forecast_engine_module = importlib.import_module("app.services.forecast_engine")
    workspace = ForecastWorkspaceRecord.from_dict(
        _workspace_payload(include_non_simulation_workers=False)
    )

    result = forecast_engine_module.HybridForecastEngine(
        simulation_data_dir=str(simulation_data_dir)
    ).execute(workspace, recorded_at="2026-03-30T11:00:00")

    answer = result.forecast_answer
    payload = answer.answer_payload

    assert answer.answer_type == "hybrid_forecast"
    assert payload["abstain"] is True
    assert payload["best_estimate"] is None
    assert payload["abstain_reason"] == "insufficient_non_simulation_evidence"
    assert payload["evaluation_summary"]["status"] == "available"
    assert payload["confidence_basis"]["status"] == "abstained"
    assert payload["simulation_context"]["observed_run_share"] == pytest.approx(0.75)
    assert payload["worker_contribution_trace"][0]["worker_id"] == "worker-sim"
    assert payload["worker_contribution_trace"][0]["influences_best_estimate"] is False
    assert any(
        "simulation scenario evidence only" in note.lower()
        for note in answer.notes
    )
