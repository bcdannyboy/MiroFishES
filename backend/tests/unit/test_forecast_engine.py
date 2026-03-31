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


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


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


def _simulation_market_worker_payload() -> dict:
    return {
        "worker_id": "worker-sim-market",
        "forecast_id": QUESTION_ID,
        "kind": "simulation_market",
        "label": "Synthetic market aggregation worker",
        "status": "ready",
        "capabilities": ["belief_aggregation", "disagreement_analysis"],
        "primary_output_semantics": "forecast_probability",
        "metadata": {"worker_family": "simulation_market"},
    }


def _simulation_scope_payload() -> dict:
    return {
        "forecast_id": QUESTION_ID,
        "simulation_id": "sim-001",
        "prepare_artifact_paths": [
            "uploads/simulations/sim-001/prepared_snapshot.json",
        ],
        "ensemble_ids": ["0001"],
        "run_ids": ["0001"],
        "latest_ensemble_id": "0001",
        "latest_run_id": "0001",
        "prepare_status": "ready",
        "status": "linked",
        "updated_at": QUESTION_ISSUED_AT,
        "last_attached_stage": "test_seed",
    }


def _write_simulation_market_artifacts(
    simulation_data_dir: Path,
    simulation_id: str,
    *,
    forecast_id: str = QUESTION_ID,
    ensemble_id: str = "0001",
    run_id: str = "0001",
    consensus_probability: float = 0.82,
    disagreement_index: float = 0.16,
    invalid_reference: bool = False,
) -> None:
    run_dir = (
        simulation_data_dir
        / simulation_id
        / "ensemble"
        / f"ensemble_{ensemble_id}"
        / "runs"
        / f"run_{run_id}"
    )
    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {
                "round": 1,
                "timestamp": "2026-03-30T10:00:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "CREATE_POST",
                "action_args": {
                    "content": "I put this near 86% after the latest brief.",
                },
                "success": True,
            },
            {
                "round": 2,
                "timestamp": "2026-03-30T10:05:00",
                "platform": "twitter",
                "agent_id": 1,
                "agent_name": "Analyst A",
                "action_type": "QUOTE_POST",
                "action_args": {
                    "content": "Revising a bit lower after the counterargument.",
                },
                "success": True,
            },
        ],
    )
    _write_jsonl(
        run_dir / "reddit" / "actions.jsonl",
        [
            {
                "round": 2,
                "timestamp": "2026-03-30T10:06:00",
                "platform": "reddit",
                "agent_id": 2,
                "agent_name": "Analyst B",
                "action_type": "CREATE_POST",
                "action_args": {
                    "content": "Closer to 60% with some hesitation.",
                },
                "success": True,
            }
        ],
    )
    source_artifact = "twitter/missing_actions.jsonl" if invalid_reference else "twitter/actions.jsonl"
    reference_a = {
        "simulation_id": simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": run_id,
        "platform": "twitter",
        "round_num": 1,
        "line_number": 1,
        "agent_id": 1,
        "agent_name": "Analyst A",
        "timestamp": "2026-03-30T10:00:00",
        "action_type": "CREATE_POST",
        "source_artifact": source_artifact,
    }
    reference_a2 = {
        "simulation_id": simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": run_id,
        "platform": "twitter",
        "round_num": 2,
        "line_number": 2,
        "agent_id": 1,
        "agent_name": "Analyst A",
        "timestamp": "2026-03-30T10:05:00",
        "action_type": "QUOTE_POST",
        "source_artifact": source_artifact,
    }
    reference_b = {
        "simulation_id": simulation_id,
        "ensemble_id": ensemble_id,
        "run_id": run_id,
        "platform": "reddit",
        "round_num": 2,
        "line_number": 1,
        "agent_id": 2,
        "agent_name": "Analyst B",
        "timestamp": "2026-03-30T10:06:00",
        "action_type": "CREATE_POST",
        "source_artifact": "reddit/actions.jsonl",
    }
    _write_json(
        run_dir / "simulation_market_manifest.json",
        {
            "artifact_type": "simulation_market_manifest",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "extraction_status": "ready",
            "supported_question_type": True,
            "forecast_workspace_linked": True,
            "scope_linked_to_run": True,
            "artifact_paths": {
                "market_snapshot": "market_snapshot.json",
                "agent_belief_book": "agent_belief_book.json",
                "belief_update_trace": "belief_update_trace.json",
                "disagreement_summary": "disagreement_summary.json",
                "argument_map": "argument_map.json",
                "missing_information_signals": "missing_information_signals.json",
            },
            "signal_counts": {
                "agent_beliefs": 2,
                "belief_updates": 3,
                "missing_information_requests": 1,
            },
            "warnings": [],
            "source_artifacts": {
                "run_manifest": "run_manifest.json",
                "run_state": "run_state.json",
                "action_logs": ["twitter/actions.jsonl", "reddit/actions.jsonl"],
            },
            "boundary_notes": [
                "Synthetic market outputs are heuristic inference inputs derived from simulated discourse."
            ],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_dir / "agent_belief_book.json",
        {
            "artifact_type": "simulation_market_agent_belief_book",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "beliefs": [
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 1,
                    "agent_name": "Analyst A",
                    "judgment_type": "binary_probability",
                    "probability": 0.82,
                    "confidence": 0.66,
                    "uncertainty_expression": "medium",
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.82, "no": 0.18},
                    "rationale_tags": ["base_rate", "briefing"],
                    "missing_information_requests": ["Need labor update"],
                    "reference": reference_a2,
                    "parse_mode": "heuristic",
                    "source_excerpt": "Revising a bit lower after the counterargument.",
                },
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 2,
                    "agent_name": "Analyst B",
                    "judgment_type": "binary_probability",
                    "probability": 0.6,
                    "confidence": 0.44,
                    "uncertainty_expression": "low",
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.6, "no": 0.4},
                    "rationale_tags": ["inflation"],
                    "missing_information_requests": [],
                    "reference": reference_b,
                    "parse_mode": "heuristic",
                    "source_excerpt": "Closer to 60% with some hesitation.",
                },
            ],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_dir / "belief_update_trace.json",
        {
            "artifact_type": "simulation_market_belief_update_trace",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "updates": [
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 1,
                    "agent_name": "Analyst A",
                    "judgment_type": "binary_probability",
                    "probability": 0.86,
                    "confidence": 0.68,
                    "uncertainty_expression": "medium",
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.86, "no": 0.14},
                    "rationale_tags": ["base_rate", "briefing"],
                    "missing_information_requests": [],
                    "reference": reference_a,
                    "parse_mode": "heuristic",
                    "source_excerpt": "I put this near 86% after the latest brief.",
                    "previous_probability": None,
                    "previous_outcome": None,
                    "belief_changed": False,
                },
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 1,
                    "agent_name": "Analyst A",
                    "judgment_type": "binary_probability",
                    "probability": 0.82,
                    "confidence": 0.66,
                    "uncertainty_expression": "medium",
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.82, "no": 0.18},
                    "rationale_tags": ["base_rate", "briefing"],
                    "missing_information_requests": ["Need labor update"],
                    "reference": reference_a2,
                    "parse_mode": "heuristic",
                    "source_excerpt": "Revising a bit lower after the counterargument.",
                    "previous_probability": 0.86,
                    "previous_outcome": "yes",
                    "belief_changed": True,
                },
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 2,
                    "agent_name": "Analyst B",
                    "judgment_type": "binary_probability",
                    "probability": 0.6,
                    "confidence": 0.44,
                    "uncertainty_expression": "low",
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.6, "no": 0.4},
                    "rationale_tags": ["inflation"],
                    "missing_information_requests": [],
                    "reference": reference_b,
                    "parse_mode": "heuristic",
                    "source_excerpt": "Closer to 60% with some hesitation.",
                    "previous_probability": None,
                    "previous_outcome": None,
                    "belief_changed": False,
                },
            ],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_dir / "disagreement_summary.json",
        {
            "artifact_type": "simulation_market_disagreement_summary",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "participant_count": 2,
            "judgment_count": 3,
            "disagreement_index": disagreement_index,
            "consensus_probability": consensus_probability,
            "consensus_outcome": "yes",
            "distribution": {"yes": consensus_probability, "no": round(1 - consensus_probability, 6)},
            "range_low": 0.6,
            "range_high": 0.86,
            "warnings": [],
            "boundary_notes": [
                "Synthetic market outputs remain observational and non-calibrated.",
            ],
        },
    )
    _write_json(
        run_dir / "market_snapshot.json",
        {
            "artifact_type": "simulation_market_snapshot",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "extraction_status": "ready",
            "support_status": "ready",
            "participating_agent_count": 2,
            "extracted_signal_count": 3,
            "disagreement_index": disagreement_index,
            "synthetic_consensus_probability": consensus_probability,
            "dominant_outcome": "yes",
            "categorical_distribution": {},
            "missing_information_request_count": 1,
            "boundary_notes": [
                "Synthetic market outputs remain observational and non-calibrated.",
            ],
        },
    )
    _write_json(
        run_dir / "argument_map.json",
        {
            "artifact_type": "simulation_market_argument_map",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "tags": [
                {"tag": "briefing", "count": 2, "sample_excerpts": ["latest brief"]},
                {"tag": "base_rate", "count": 2, "sample_excerpts": ["86% after the latest brief"]},
                {"tag": "inflation", "count": 1, "sample_excerpts": ["Closer to 60% with some hesitation."]},
            ],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_dir / "missing_information_signals.json",
        {
            "artifact_type": "simulation_market_missing_information_signals",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": run_id,
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "signals": [
                {
                    "request": "Need labor update",
                    "agent_id": 1,
                    "agent_name": "Analyst A",
                    "question_type": "binary",
                    "reference": reference_a2,
                }
            ],
            "extracted_at": "2026-03-30T10:10:00",
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


def test_hybrid_engine_uses_simulation_market_signals_with_contribution_trace(
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
    _write_simulation_market_artifacts(
        simulation_data_dir,
        "sim-001",
        consensus_probability=0.65,
        disagreement_index=0.16,
    )

    forecast_engine_module = importlib.import_module("app.services.forecast_engine")
    baseline_workspace = ForecastWorkspaceRecord.from_dict(_workspace_payload())
    baseline_result = forecast_engine_module.HybridForecastEngine(
        simulation_data_dir=str(simulation_data_dir)
    ).execute(baseline_workspace, recorded_at="2026-03-30T11:00:00")

    payload = _workspace_payload()
    payload["forecast_workers"].append(_simulation_market_worker_payload())
    payload["simulation_scope"] = _simulation_scope_payload()
    workspace = ForecastWorkspaceRecord.from_dict(payload)
    result = forecast_engine_module.HybridForecastEngine(
        simulation_data_dir=str(simulation_data_dir)
    ).execute(workspace, recorded_at="2026-03-30T11:00:00")

    answer_payload = result.forecast_answer.answer_payload
    trace = {item["worker_id"]: item for item in answer_payload["worker_contribution_trace"]}
    baseline_estimate = baseline_result.forecast_answer.answer_payload["best_estimate"]["estimate"]

    assert trace["worker-sim-market"]["used_in_best_estimate"] is True
    assert trace["worker-sim-market"]["status"] == "completed"
    assert trace["worker-sim-market"]["confidence_inputs"]["provenance_status"] == "ready"
    assert answer_payload["simulation_market_context"]["included"] is True
    assert answer_payload["simulation_market_context"]["synthetic_consensus_probability"] == pytest.approx(0.65)
    assert answer_payload["best_estimate"]["estimate"] > baseline_estimate


def test_hybrid_engine_rejects_simulation_market_with_invalid_provenance(
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
    _write_simulation_market_artifacts(
        simulation_data_dir,
        "sim-001",
        consensus_probability=0.84,
        disagreement_index=0.14,
        invalid_reference=True,
    )

    forecast_engine_module = importlib.import_module("app.services.forecast_engine")
    payload = _workspace_payload(include_non_simulation_workers=False)
    payload["forecast_workers"].append(_simulation_market_worker_payload())
    payload["simulation_scope"] = _simulation_scope_payload()
    workspace = ForecastWorkspaceRecord.from_dict(payload)
    result = forecast_engine_module.HybridForecastEngine(
        simulation_data_dir=str(simulation_data_dir)
    ).execute(workspace, recorded_at="2026-03-30T11:00:00")

    answer_payload = result.forecast_answer.answer_payload
    sim_market_trace = next(
        item
        for item in answer_payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation_market"
    )

    assert sim_market_trace["status"] == "abstained"
    assert sim_market_trace["used_in_best_estimate"] is False
    assert sim_market_trace["abstain_reason"] == "invalid_simulation_market_provenance"
    assert answer_payload["abstain"] is True
    assert answer_payload["abstain_reason"] == "insufficient_non_simulation_evidence"
