from __future__ import annotations

import json
from pathlib import Path

from app.models.forecasting import ForecastWorkspaceRecord


def _criteria_payload(forecast_id: str):
    return {
        "criteria_id": f"{forecast_id}-criteria",
        "forecast_id": forecast_id,
        "label": "Support threshold",
        "description": "Resolve yes if support exceeds 55%.",
        "resolution_date": "2026-06-30",
        "criteria_type": "metric_threshold",
        "thresholds": {
            "metric_id": "survey.support_share",
            "operator": "gt",
            "value": 0.55,
        },
    }


def _question_payload(
    forecast_id: str,
    *,
    title: str,
    question_text: str,
    question_type: str = "binary",
    question_spec: dict | None = None,
    status: str = "active",
    tags: list[str] | None = None,
):
    return {
        "forecast_id": forecast_id,
        "project_id": "proj-hybrid",
        "title": title,
        "question": question_text,
        "question_text": question_text,
        "question_type": question_type,
        "question_spec": question_spec or {},
        "status": status,
        "horizon": {"type": "date", "value": "2026-06-30"},
        "resolution_criteria_ids": [f"{forecast_id}-criteria"],
        "owner": "forecasting-team",
        "source": "manual-entry",
        "abstention_conditions": [
            "Abstain if only simulation scenario evidence is available.",
        ],
        "primary_simulation_id": "sim-001",
        "tags": tags or ["policy", "support"],
        "issue_timestamp": "2026-03-30T09:00:00",
        "created_at": "2026-03-30T09:00:00",
        "updated_at": "2026-03-30T09:00:00",
    }


def _directional_entry(
    source_id: str,
    *,
    title: str,
    conflict_status: str,
    quality_score: float,
    relevance_score: float,
    freshness_status: str = "fresh",
    citation_id: str | None = None,
):
    return {
        "source_id": source_id,
        "provider_id": "uploaded_local_artifacts",
        "provider_kind": "uploaded_local_artifact",
        "kind": "uploaded_source",
        "title": title,
        "summary": title,
        "citation_id": citation_id,
        "timestamps": {"captured_at": "2026-03-30T09:05:00"},
        "freshness": {"status": freshness_status, "score": 0.9 if freshness_status == "fresh" else 0.4},
        "relevance": {"status": "high" if relevance_score >= 0.75 else "medium", "score": relevance_score},
        "quality": {"status": "strong" if quality_score >= 0.75 else "usable", "score": quality_score},
        "conflict_status": conflict_status,
        "notes": [],
        "metadata": {},
    }


def _bundle_payload(forecast_id: str, *, sparse: bool = False, conflicting: bool = False):
    entries = []
    if not sparse:
        entries = [
            _directional_entry(
                "src-support-1",
                title="Uploaded memo supports rising support.",
                conflict_status="supports",
                quality_score=0.92,
                relevance_score=0.88,
                citation_id="[S1]",
            ),
            _directional_entry(
                "src-support-2",
                title="Prepared artifact supports threshold crossing.",
                conflict_status="supports",
                quality_score=0.81,
                relevance_score=0.79,
                citation_id="[S2]",
            ),
        ]
        if conflicting:
            entries.append(
                _directional_entry(
                    "src-contra-1",
                    title="Uploaded note contradicts strong support growth.",
                    conflict_status="contradicts",
                    quality_score=0.75,
                    relevance_score=0.72,
                    freshness_status="aging",
                    citation_id="[S3]",
                )
            )
    missing_markers = []
    if sparse:
        missing_markers = [
            {
                "code": "missing_evidence",
                "summary": "No corroborating non-simulation evidence is attached.",
            }
        ]
    return {
        "bundle_id": f"{forecast_id}-bundle",
        "forecast_id": forecast_id,
        "title": "Hybrid evidence bundle",
        "summary": "Local uploaded evidence and simulation artifacts.",
        "status": "ready" if entries else "partial",
        "entries": entries,
        "providers": [
            {
                "provider_id": "uploaded_local_artifacts",
                "provider_kind": "uploaded_local_artifact",
                "status": "ready" if entries else "partial",
                "boundary_note": "Bounded to uploaded/local artifacts.",
            }
        ],
        "question_links": [forecast_id],
        "prediction_links": [],
        "missing_evidence_markers": missing_markers,
        "boundary_note": "Evidence remains bounded to stored local and simulation artifacts.",
        "created_at": "2026-03-30T09:00:00",
    }


def _simulation_worker_payload(forecast_id: str):
    return {
        "worker_id": f"{forecast_id}-sim",
        "forecast_id": forecast_id,
        "kind": "simulation",
        "label": "Scenario Simulation Worker",
        "status": "ready",
        "capabilities": ["scenario_generation", "scenario_analysis"],
        "primary_output_semantics": "scenario_evidence",
        "metadata": {"worker_family": "simulation_adapter"},
    }


def _simulation_contract_payload(forecast_id: str):
    return {
        "worker_id": f"{forecast_id}-sim",
        "forecast_id": forecast_id,
        "simulation_id": "sim-001",
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "ensemble_ids": ["0001"],
        "scenario_diversity_strategy": "weighted_cycle",
        "probability_interpretation": "do_not_treat_as_real_world_probability",
        "notes": ["Simulation remains scenario evidence only."],
    }


def _simulation_market_scope_payload(forecast_id: str):
    return {
        "forecast_id": forecast_id,
        "simulation_id": "sim-001",
        "prepare_artifact_paths": ["uploads/simulations/sim-001/prepared_snapshot.json"],
        "ensemble_ids": ["0001"],
        "run_ids": ["0001"],
        "latest_ensemble_id": "0001",
        "latest_run_id": "0001",
        "prepare_status": "ready",
        "status": "linked",
        "updated_at": "2026-03-30T09:00:00",
        "last_attached_stage": "test_seed",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def _write_simulation_market_artifacts(
    simulation_data_dir: Path,
    *,
    forecast_id: str,
    consensus_probability: float,
    disagreement_index: float,
) -> None:
    run_dir = simulation_data_dir / "sim-001" / "ensemble" / "ensemble_0001" / "runs" / "run_0001"
    _write_jsonl(
        run_dir / "twitter" / "actions.jsonl",
        [
            {"content": "I put this near 74% after the latest brief."},
            {"content": "Revising a bit lower after debate."},
        ],
    )
    _write_jsonl(
        run_dir / "reddit" / "actions.jsonl",
        [{"content": "Closer to 61% with some hesitation."}],
    )
    ref_a = {
        "simulation_id": "sim-001",
        "ensemble_id": "0001",
        "run_id": "0001",
        "platform": "twitter",
        "round_num": 1,
        "line_number": 1,
        "agent_id": 1,
        "agent_name": "Analyst A",
        "timestamp": "2026-03-30T10:00:00",
        "action_type": "CREATE_POST",
        "source_artifact": "twitter/actions.jsonl",
    }
    ref_b = {
        "simulation_id": "sim-001",
        "ensemble_id": "0001",
        "run_id": "0001",
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
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
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
            "signal_counts": {"agent_beliefs": 2, "belief_updates": 3, "missing_information_requests": 1},
            "warnings": [],
            "source_artifacts": {
                "run_manifest": "run_manifest.json",
                "run_state": "run_state.json",
                "action_logs": ["twitter/actions.jsonl", "reddit/actions.jsonl"],
            },
            "boundary_notes": ["Synthetic market outputs are heuristic inference inputs derived from simulated discourse."],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )
    _write_json(
        run_dir / "agent_belief_book.json",
        {
            "artifact_type": "simulation_market_agent_belief_book",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
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
                    "probability": 0.74,
                    "confidence": 0.62,
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.74, "no": 0.26},
                    "rationale_tags": ["briefing"],
                    "reference": ref_a,
                },
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 2,
                    "agent_name": "Analyst B",
                    "judgment_type": "binary_probability",
                    "probability": 0.61,
                    "confidence": 0.46,
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.61, "no": 0.39},
                    "rationale_tags": ["inflation"],
                    "reference": ref_b,
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
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
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
                    "probability": 0.78,
                    "confidence": 0.64,
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.78, "no": 0.22},
                    "rationale_tags": ["briefing"],
                    "reference": ref_a,
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
                    "probability": 0.74,
                    "confidence": 0.62,
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.74, "no": 0.26},
                    "rationale_tags": ["briefing"],
                    "reference": ref_a,
                    "previous_probability": 0.78,
                    "previous_outcome": "yes",
                    "belief_changed": True,
                },
                {
                    "forecast_id": forecast_id,
                    "question_type": "binary",
                    "agent_id": 2,
                    "agent_name": "Analyst B",
                    "judgment_type": "binary_probability",
                    "probability": 0.61,
                    "confidence": 0.46,
                    "dominant_outcome": "yes",
                    "outcome_distribution": {"yes": 0.61, "no": 0.39},
                    "rationale_tags": ["inflation"],
                    "reference": ref_b,
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
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "participant_count": 2,
            "judgment_count": 3,
            "disagreement_index": disagreement_index,
            "consensus_probability": consensus_probability,
            "consensus_outcome": "yes",
            "distribution": {"yes": consensus_probability, "no": round(1 - consensus_probability, 6)},
            "range_low": 0.61,
            "range_high": 0.78,
            "warnings": [],
            "boundary_notes": ["Synthetic market outputs remain observational and non-calibrated."],
        },
    )
    _write_json(
        run_dir / "market_snapshot.json",
        {
            "artifact_type": "simulation_market_snapshot",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
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
            "boundary_notes": ["Synthetic market outputs remain observational and non-calibrated."],
        },
    )
    _write_json(
        run_dir / "argument_map.json",
        {
            "artifact_type": "simulation_market_argument_map",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "tags": [
                {"tag": "briefing", "count": 2, "sample_excerpts": ["latest brief"]},
                {"tag": "inflation", "count": 1, "sample_excerpts": ["hesitation"]},
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
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
            "run_id": "0001",
            "forecast_id": forecast_id,
            "question_type": "binary",
            "support_status": "ready",
            "signals": [
                {
                    "request": "Need labor update",
                    "agent_id": 1,
                    "agent_name": "Analyst A",
                    "question_type": "binary",
                    "reference": ref_a,
                }
            ],
            "extracted_at": "2026-03-30T10:10:00",
        },
    )


def _simulation_prediction_payload(forecast_id: str, *, observed_run_share: float):
    worker_id = f"{forecast_id}-sim"
    return {
        "entry_id": f"{worker_id}-entry-1",
        "prediction_id": f"{worker_id}-prediction",
        "forecast_id": forecast_id,
        "worker_id": worker_id,
        "recorded_at": "2026-03-30T09:20:00",
        "value_type": "scenario_observed_share",
        "value": observed_run_share,
        "prediction": observed_run_share,
        "value_semantics": "observed_run_share",
        "revision_number": 1,
        "entry_kind": "issue",
        "calibration_state": "not_applicable",
        "evidence_bundle_ids": [f"{forecast_id}-bundle"],
        "worker_output_ids": [f"{worker_id}-output-1"],
        "notes": ["Scenario frequency is descriptive only."],
        "metadata": {"worker_family": "simulation_adapter"},
    }


def _workspace_payload(
    forecast_id: str,
    *,
    title: str,
    question_text: str,
    sparse_bundle: bool = False,
    conflicting_bundle: bool = False,
    with_simulation_prediction: bool = True,
):
    entries = []
    worker_outputs = []
    if with_simulation_prediction:
        entries.append(
            _simulation_prediction_payload(
                forecast_id,
                observed_run_share=0.91 if not sparse_bundle else 0.84,
            )
        )
        worker_outputs.append(
            {
                "output_id": f"{forecast_id}-sim-output-1",
                "forecast_id": forecast_id,
                "worker_id": f"{forecast_id}-sim",
                "worker_kind": "simulation",
                "status": "completed",
                "recorded_at": "2026-03-30T09:20:00",
                "summary": "Simulation scenario evidence from the existing subsystem.",
            }
        )
    return {
        "forecast_question": _question_payload(
            forecast_id,
            title=title,
            question_text=question_text,
        ),
        "resolution_criteria": [_criteria_payload(forecast_id)],
        "evidence_bundle": _bundle_payload(
            forecast_id,
            sparse=sparse_bundle,
            conflicting=conflicting_bundle,
        ),
        "forecast_workers": [_simulation_worker_payload(forecast_id)],
        "prediction_ledger": {
            "forecast_id": forecast_id,
            "entries": entries,
            "worker_outputs": worker_outputs,
            "resolution_history": [],
            "final_resolution_state": "pending",
        },
        "evaluation_cases": [],
        "forecast_answers": [],
        "simulation_worker_contract": _simulation_contract_payload(forecast_id),
    }


def _resolved_workspace_payload(
    forecast_id: str,
    *,
    title: str,
    question_text: str,
    resolved_state: str,
    tags: list[str] | None = None,
):
    return {
        "forecast_question": _question_payload(
            forecast_id,
            title=title,
            question_text=question_text,
            status="resolved",
            tags=tags or ["policy", "support"],
        ),
        "resolution_criteria": [_criteria_payload(forecast_id)],
        "evidence_bundle": _bundle_payload(forecast_id),
        "forecast_workers": [],
        "prediction_ledger": {
            "forecast_id": forecast_id,
            "entries": [],
            "worker_outputs": [],
            "resolution_history": [
                {
                    "status": resolved_state,
                    "resolved_at": "2026-07-01T10:00:00",
                    "resolution_note": "Historical resolved benchmark.",
                }
            ],
            "final_resolution_state": {
                "status": resolved_state,
                "resolved_at": "2026-07-01T10:00:00",
                "resolution_note": "Historical resolved benchmark.",
            },
        },
        "evaluation_cases": [
            {
                "case_id": f"{forecast_id}-case",
                "forecast_id": forecast_id,
                "criteria_id": f"{forecast_id}-criteria",
                "status": "resolved",
                "observed_outcome": {"resolved_state": resolved_state},
                "resolved_at": "2026-07-01T10:00:00",
                "resolution_note": "Historical outcome.",
            }
        ],
        "forecast_answers": [],
        "simulation_worker_contract": None,
    }


def _workspace_from_payload(payload: dict) -> ForecastWorkspaceRecord:
    return ForecastWorkspaceRecord.from_dict(payload)


def _typed_workers_payload(
    forecast_id: str,
    *,
    question_type: str,
    unit: str | None = None,
):
    if question_type == "categorical":
        base_rate_benchmark = {
            "distribution": {"win": 0.52, "stretch": 0.33, "miss": 0.15},
            "sample_count": 14,
        }
        reference_cases = [
            {"case_id": "cat-1", "value": "win", "weight": 1.0},
            {"case_id": "cat-2", "value": "win", "weight": 1.0},
            {"case_id": "cat-3", "value": "stretch", "weight": 0.8},
            {"case_id": "cat-4", "value": "miss", "weight": 0.3},
        ]
        retrieval_semantics = "forecast_distribution"
    elif question_type == "numeric":
        base_rate_benchmark = {
            "point_estimate": 42.0,
            "intervals": {
                "50": {"low": 38.0, "high": 45.0},
                "80": {"low": 34.0, "high": 50.0},
                "90": {"low": 31.0, "high": 54.0},
            },
            "sample_count": 14,
            "unit": unit,
        }
        reference_cases = [
            {"case_id": "num-1", "value": 39.0, "weight": 1.0},
            {"case_id": "num-2", "value": 41.0, "weight": 1.0},
            {"case_id": "num-3", "value": 44.0, "weight": 1.2},
            {"case_id": "num-4", "value": 47.0, "weight": 0.8},
        ]
        retrieval_semantics = "numeric_interval_estimate"
    else:
        base_rate_benchmark = {"estimate": 0.62, "sample_count": 14}
        reference_cases = [
            {"case_id": "bin-1", "value": 1, "weight": 1.0},
            {"case_id": "bin-2", "value": 1, "weight": 1.0},
            {"case_id": "bin-3", "value": 0, "weight": 1.0},
        ]
        retrieval_semantics = "forecast_probability"
    return [
        {
            "worker_id": f"{forecast_id}-base",
            "forecast_id": forecast_id,
            "kind": "base_rate",
            "label": "Base-rate benchmark worker",
            "status": "ready",
            "capabilities": ["benchmark_lookup"],
            "primary_output_semantics": (
                "forecast_distribution"
                if question_type == "categorical"
                else "numeric_interval_estimate"
                if question_type == "numeric"
                else "forecast_probability"
            ),
            "metadata": {
                "worker_family": "base_rate",
                "benchmark": base_rate_benchmark,
            },
        },
        {
            "worker_id": f"{forecast_id}-reference",
            "forecast_id": forecast_id,
            "kind": "reference_class",
            "label": "Reference-class worker",
            "status": "ready",
            "capabilities": ["case_based_reasoning"],
            "primary_output_semantics": (
                "forecast_distribution"
                if question_type == "categorical"
                else "numeric_interval_estimate"
                if question_type == "numeric"
                else "forecast_probability"
            ),
            "metadata": {
                "worker_family": "reference_class",
                "reference_cases": reference_cases,
            },
        },
        {
            "worker_id": f"{forecast_id}-retrieval",
            "forecast_id": forecast_id,
            "kind": "retrieval_synthesis",
            "label": "Retrieval synthesis worker",
            "status": "ready",
            "capabilities": ["bounded_local_retrieval"],
            "primary_output_semantics": retrieval_semantics,
            "metadata": {
                "worker_family": "retrieval_synthesis",
            },
        },
        _simulation_worker_payload(forecast_id),
    ]


def _categorical_workspace_payload(forecast_id: str):
    question = _question_payload(
        forecast_id,
        title="Launch posture outlook",
        question_text="Which launch posture will be observed by June 30, 2026?",
        question_type="categorical",
        question_spec={"outcome_labels": ["win", "stretch", "miss"]},
    )
    prediction_entry = {
        "entry_id": f"{forecast_id}-sim-entry-1",
        "prediction_id": f"{forecast_id}-sim-prediction",
        "forecast_id": forecast_id,
        "worker_id": f"{forecast_id}-sim",
        "recorded_at": "2026-03-30T09:20:00",
        "value_type": "categorical_distribution",
        "value": {
            "distribution": {"win": 0.48, "stretch": 0.37, "miss": 0.15},
            "run_count": 12,
        },
        "prediction": {
            "distribution": {"win": 0.48, "stretch": 0.37, "miss": 0.15},
            "run_count": 12,
        },
        "value_semantics": "observed_run_share",
        "revision_number": 1,
        "entry_kind": "issue",
        "calibration_state": "not_applicable",
        "evidence_bundle_ids": [f"{forecast_id}-bundle"],
        "worker_output_ids": [f"{forecast_id}-sim-output-1"],
        "notes": ["Scenario family shares remain descriptive only."],
        "metadata": {"worker_family": "simulation_adapter"},
    }
    evaluation_cases = []
    case_specs = [
        ("case-1", "win", {"win": 0.86, "stretch": 0.09, "miss": 0.05}),
        ("case-2", "win", {"win": 0.81, "stretch": 0.12, "miss": 0.07}),
        ("case-3", "stretch", {"win": 0.62, "stretch": 0.28, "miss": 0.10}),
        ("case-4", "stretch", {"stretch": 0.76, "win": 0.16, "miss": 0.08}),
        ("case-5", "win", {"win": 0.58, "stretch": 0.27, "miss": 0.15}),
        ("case-6", "miss", {"miss": 0.74, "stretch": 0.16, "win": 0.10}),
        ("case-7", "stretch", {"stretch": 0.67, "win": 0.21, "miss": 0.12}),
        ("case-8", "win", {"win": 0.73, "stretch": 0.19, "miss": 0.08}),
        ("case-9", "stretch", {"stretch": 0.57, "win": 0.31, "miss": 0.12}),
        ("case-10", "win", {"win": 0.69, "stretch": 0.20, "miss": 0.11}),
    ]
    for case_id, observed_label, distribution in case_specs:
        evaluation_cases.append(
            {
                "case_id": f"{forecast_id}-{case_id}",
                "forecast_id": forecast_id,
                "criteria_id": f"{forecast_id}-criteria",
                "status": "resolved",
                "issued_at": "2026-03-01T00:00:00",
                "question_class": "launch_posture",
                "comparable_question_class": "launch_posture",
                "prediction_value_type": "categorical_distribution",
                "prediction_value_semantics": "forecast_distribution",
                "prediction_payload": {
                    "distribution": distribution,
                    "top_label": max(distribution, key=distribution.get),
                },
                "observed_outcome": {"label": observed_label},
                "resolved_at": "2026-06-30T00:00:00",
                "evaluation_split": "rolling_holdout",
                "window_id": "2026H1",
                "benchmark_id": "categorical-launch",
            }
        )
    return {
        "forecast_question": question,
        "resolution_criteria": [
            {
                "criteria_id": f"{forecast_id}-criteria",
                "forecast_id": forecast_id,
                "label": "Observed posture",
                "description": "Resolve against the named observed launch posture.",
                "resolution_date": "2026-06-30",
                "criteria_type": "manual",
                "thresholds": {},
            }
        ],
        "evidence_bundle": {
            "bundle_id": f"{forecast_id}-bundle",
            "forecast_id": forecast_id,
            "title": "Categorical evidence bundle",
            "summary": "Bounded evidence for launch posture outcomes.",
            "status": "ready",
            "entries": [
                {
                    "source_id": "cat-source-1",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "uploaded_source",
                    "title": "Launch planning memo",
                    "summary": "The memo favors a win outcome while preserving stretch and miss paths.",
                    "timestamps": {"captured_at": "2026-03-30T09:05:00"},
                    "freshness": {"status": "fresh", "score": 0.9},
                    "relevance": {"status": "high", "score": 0.92},
                    "quality": {"status": "strong", "score": 0.84},
                    "conflict_status": "supports",
                    "metadata": {
                        "forecast_hints": [
                            {
                                "distribution": {"win": 0.62, "stretch": 0.26, "miss": 0.12},
                                "confidence_weight": 0.9,
                                "assumption": "Execution conditions remain stable.",
                            }
                        ]
                    },
                }
            ],
            "providers": [
                {
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "status": "ready",
                }
            ],
            "question_links": [forecast_id],
            "prediction_links": [prediction_entry["entry_id"]],
            "boundary_note": "Evidence remains bounded to uploaded artifacts and stored scenario outputs.",
            "created_at": "2026-03-30T09:00:00",
        },
        "forecast_workers": _typed_workers_payload(forecast_id, question_type="categorical"),
        "prediction_ledger": {
            "forecast_id": forecast_id,
            "entries": [prediction_entry],
            "worker_outputs": [
                {
                    "output_id": f"{forecast_id}-sim-output-1",
                    "forecast_id": forecast_id,
                    "worker_id": f"{forecast_id}-sim",
                    "worker_kind": "simulation",
                    "status": "completed",
                    "recorded_at": "2026-03-30T09:20:00",
                    "summary": "Simulation scenario evidence for categorical outcomes.",
                }
            ],
            "resolution_history": [],
            "final_resolution_state": "pending",
        },
        "evaluation_cases": evaluation_cases,
        "forecast_answers": [],
        "simulation_worker_contract": _simulation_contract_payload(forecast_id),
    }


def _numeric_workspace_payload(forecast_id: str):
    question = _question_payload(
        forecast_id,
        title="ARR outlook",
        question_text="What ARR will be observed by June 30, 2026?",
        question_type="numeric",
        question_spec={
            "unit": "usd_millions",
            "interval_levels": [50, 80, 90],
            "lower_bound": 0,
            "upper_bound": 250,
        },
    )
    prediction_entry = {
        "entry_id": f"{forecast_id}-sim-entry-1",
        "prediction_id": f"{forecast_id}-sim-prediction",
        "forecast_id": forecast_id,
        "worker_id": f"{forecast_id}-sim",
        "recorded_at": "2026-03-30T09:20:00",
        "value_type": "numeric_interval",
        "value": {
            "point_estimate": 44.0,
            "intervals": {
                "50": {"low": 40.0, "high": 47.0},
                "80": {"low": 36.0, "high": 52.0},
                "90": {"low": 33.0, "high": 56.0},
            },
            "unit": "usd_millions",
            "sample_count": 12,
        },
        "prediction": {
            "point_estimate": 44.0,
            "intervals": {
                "50": {"low": 40.0, "high": 47.0},
                "80": {"low": 36.0, "high": 52.0},
                "90": {"low": 33.0, "high": 56.0},
            },
            "unit": "usd_millions",
        },
        "value_semantics": "numeric_interval_estimate",
        "revision_number": 1,
        "entry_kind": "issue",
        "calibration_state": "not_applicable",
        "evidence_bundle_ids": [f"{forecast_id}-bundle"],
        "worker_output_ids": [f"{forecast_id}-sim-output-1"],
        "notes": ["Simulation numeric summaries remain descriptive scenario evidence only."],
        "metadata": {"worker_family": "simulation_adapter"},
    }
    case_specs = [
        ("case-1", 35.0, 34.0),
        ("case-2", 36.0, 38.0),
        ("case-3", 39.0, 40.0),
        ("case-4", 41.0, 42.0),
        ("case-5", 43.0, 44.0),
        ("case-6", 45.0, 46.0),
        ("case-7", 47.0, 48.0),
        ("case-8", 49.0, 50.0),
        ("case-9", 51.0, 52.0),
        ("case-10", 53.0, 54.0),
    ]
    evaluation_cases = []
    for case_id, point_estimate, observed_value in case_specs:
        evaluation_cases.append(
            {
                "case_id": f"{forecast_id}-{case_id}",
                "forecast_id": forecast_id,
                "criteria_id": f"{forecast_id}-criteria",
                "status": "resolved",
                "issued_at": "2026-03-01T00:00:00",
                "question_class": "arr_value",
                "comparable_question_class": "arr_value",
                "prediction_value_type": "numeric_interval",
                "prediction_value_semantics": "numeric_interval_estimate",
                "prediction_payload": {
                    "point_estimate": point_estimate,
                    "intervals": {
                        "50": {"low": point_estimate - 2.0, "high": point_estimate + 2.0},
                        "80": {"low": point_estimate - 5.0, "high": point_estimate + 5.0},
                        "90": {"low": point_estimate - 7.0, "high": point_estimate + 7.0},
                    },
                    "unit": "usd_millions",
                },
                "observed_outcome": {"value": observed_value},
                "observed_value": {"value": observed_value},
                "observed_unit": "usd_millions",
                "resolved_at": "2026-06-30T00:00:00",
                "evaluation_split": "rolling_holdout",
                "window_id": "2026H1",
                "benchmark_id": "numeric-arr",
                "confidence_basis": {"prior_observed_value": point_estimate - 4.0},
            }
        )
    return {
        "forecast_question": question,
        "resolution_criteria": [
            {
                "criteria_id": f"{forecast_id}-criteria",
                "forecast_id": forecast_id,
                "label": "Observed ARR value",
                "description": "Resolve against the observed ARR value.",
                "resolution_date": "2026-06-30",
                "criteria_type": "manual",
                "thresholds": {},
            }
        ],
        "evidence_bundle": {
            "bundle_id": f"{forecast_id}-bundle",
            "forecast_id": forecast_id,
            "title": "Numeric evidence bundle",
            "summary": "Bounded evidence for ARR estimates.",
            "status": "ready",
            "entries": [
                {
                    "source_id": "num-source-1",
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "kind": "uploaded_source",
                    "title": "ARR planning memo",
                    "summary": "The memo suggests ARR in the low-to-mid forties.",
                    "timestamps": {"captured_at": "2026-03-30T09:05:00"},
                    "freshness": {"status": "fresh", "score": 0.9},
                    "relevance": {"status": "high", "score": 0.9},
                    "quality": {"status": "strong", "score": 0.82},
                    "conflict_status": "supports",
                    "metadata": {
                        "forecast_hints": [
                            {
                                "point_estimate": 43.0,
                                "intervals": {
                                    "50": {"low": 40.0, "high": 46.0},
                                    "80": {"low": 36.0, "high": 50.0},
                                    "90": {"low": 34.0, "high": 53.0},
                                },
                                "confidence_weight": 0.9,
                            }
                        ]
                    },
                }
            ],
            "providers": [
                {
                    "provider_id": "uploaded_local_artifacts",
                    "provider_kind": "uploaded_local_artifact",
                    "status": "ready",
                }
            ],
            "question_links": [forecast_id],
            "prediction_links": [prediction_entry["entry_id"]],
            "boundary_note": "Evidence remains bounded to uploaded artifacts and stored scenario outputs.",
            "created_at": "2026-03-30T09:00:00",
        },
        "forecast_workers": _typed_workers_payload(
            forecast_id,
            question_type="numeric",
            unit="usd_millions",
        ),
        "prediction_ledger": {
            "forecast_id": forecast_id,
            "entries": [prediction_entry],
            "worker_outputs": [
                {
                    "output_id": f"{forecast_id}-sim-output-1",
                    "forecast_id": forecast_id,
                    "worker_id": f"{forecast_id}-sim",
                    "worker_kind": "simulation",
                    "status": "completed",
                    "recorded_at": "2026-03-30T09:20:00",
                    "summary": "Simulation scenario evidence for numeric outcomes.",
                }
            ],
            "resolution_history": [],
            "final_resolution_state": "pending",
        },
        "evaluation_cases": evaluation_cases,
        "forecast_answers": [],
        "simulation_worker_contract": _simulation_contract_payload(forecast_id),
    }


def test_hybrid_forecast_service_aggregates_non_simulation_workers_without_let_simulation_dominate():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    workspace = _workspace_from_payload(
        _workspace_payload(
            "forecast-current",
            title="Policy support outlook",
            question_text="Will policy support exceed 55% by June 30, 2026?",
            conflicting_bundle=False,
        )
    )
    comparables = [
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-hist-1",
                title="Policy support outlook",
                question_text="Will policy support exceed 55% by quarter end?",
                resolved_state="resolved_true",
            )
        ),
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-hist-2",
                title="Policy support outlook",
                question_text="Will policy support exceed 55% after rollout?",
                resolved_state="resolved_true",
            )
        ),
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-hist-3",
                title="Policy support outlook",
                question_text="Will policy support exceed 55% after the campaign?",
                resolved_state="resolved_false",
            )
        ),
    ]

    result = service.run(
        workspace=workspace,
        comparable_workspaces=comparables,
        issued_at="2026-03-30T12:00:00",
    )

    payload = result.forecast_answer.answer_payload
    assert result.forecast_answer.answer_type == "hybrid_forecast"
    assert payload["abstained"] is False
    assert 0.55 < payload["best_estimate"]["value"] < 0.8
    assert len(result.worker_results) == 4
    assert {item.worker_kind for item in result.worker_results} == {
        "base_rate",
        "reference_class",
        "retrieval_synthesis",
        "simulation",
    }
    assert {
        entry.worker_id for entry in result.prediction_entries
    } >= {
        "worker-base-rate",
        "worker-reference-class",
        "worker-retrieval-synthesis",
    }
    simulation_trace = next(
        item
        for item in payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation"
    )
    assert simulation_trace["used_in_best_estimate"] is False
    assert simulation_trace["estimate"]["value_semantics"] == "observed_run_share"
    assert "Simulation contributes supporting scenario evidence only." in result.forecast_answer.summary


def test_hybrid_forecast_service_abstains_when_only_simulation_and_sparse_local_evidence_are_available():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    workspace = _workspace_from_payload(
        _workspace_payload(
            "forecast-sparse",
            title="Sparse support outlook",
            question_text="Will support exceed 55% with sparse evidence?",
            sparse_bundle=True,
        )
    )

    result = service.run(
        workspace=workspace,
        comparable_workspaces=[],
        issued_at="2026-03-30T12:00:00",
    )

    payload = result.forecast_answer.answer_payload
    assert payload["abstained"] is True
    assert payload["best_estimate"] is None
    assert payload["abstain_reason"] == "insufficient_non_simulation_evidence"
    assert "worker_disagreement" not in {
        item["code"] for item in payload["uncertainty_decomposition"]["components"]
    }
    simulation_trace = next(
        item
        for item in payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation"
    )
    assert simulation_trace["used_in_best_estimate"] is False
    assert simulation_trace["status"] == "completed"
    assert "supporting scenario evidence only" in result.forecast_answer.summary.lower()


def test_hybrid_forecast_service_abstains_when_non_simulation_workers_disagree_too_widely():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    workspace_payload = _workspace_payload(
        "forecast-conflict",
        title="Conflicted support outlook",
        question_text="Will policy support exceed 55% with conflicting signals?",
        conflicting_bundle=True,
    )
    workspace_payload["forecast_workers"].extend(
        [
            {
                "worker_id": "worker-base-rate",
                "forecast_id": "forecast-conflict",
                "kind": "base_rate",
                "label": "Base-rate benchmark worker",
                "status": "ready",
                "capabilities": ["benchmark_lookup"],
                "primary_output_semantics": "forecast_probability",
                "metadata": {
                    "worker_family": "base_rate",
                    "benchmark": {
                        "estimate": 0.12,
                        "sample_count": 18,
                    },
                },
            },
            {
                "worker_id": "worker-reference-class",
                "forecast_id": "forecast-conflict",
                "kind": "reference_class",
                "label": "Reference-class worker",
                "status": "ready",
                "capabilities": ["case_based_reasoning"],
                "primary_output_semantics": "forecast_probability",
                "metadata": {
                    "worker_family": "reference_class",
                    "reference_cases": [
                        {"case_id": "hi-1", "value": 0.94, "weight": 1.0},
                        {"case_id": "hi-2", "value": 0.9, "weight": 1.0},
                        {"case_id": "hi-3", "value": 0.88, "weight": 1.0},
                    ],
                },
            },
        ]
    )
    workspace = _workspace_from_payload(
        workspace_payload
    )
    comparables = [
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-low-1",
                title="Weak support baseline",
                question_text="Will support exceed 55% in weak baseline conditions?",
                resolved_state="resolved_false",
                tags=["weak", "support"],
            )
        ),
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-low-2",
                title="Weak support baseline",
                question_text="Will support exceed 55% in weak baseline conditions?",
                resolved_state="resolved_false",
                tags=["weak", "support"],
            )
        ),
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-high-1",
                title="Policy support outlook",
                question_text="Will policy support exceed 55% after a strong campaign?",
                resolved_state="resolved_true",
                tags=["policy", "support", "campaign"],
            )
        ),
        _workspace_from_payload(
            _resolved_workspace_payload(
                "forecast-high-2",
                title="Policy support outlook",
                question_text="Will policy support exceed 55% after a strong campaign?",
                resolved_state="resolved_true",
                tags=["policy", "support", "campaign"],
            )
        ),
    ]

    result = service.run(
        workspace=workspace,
        comparable_workspaces=comparables,
        issued_at="2026-03-30T12:00:00",
    )

    payload = result.forecast_answer.answer_payload
    assert payload["abstained"] is True
    assert payload["abstain_reason"] == "worker_disagreement"
    assert any(
        item["code"] == "worker_disagreement"
        for item in payload["uncertainty_decomposition"]["components"]
    )
    assert any(
        item["worker_kind"] == "simulation" and item["used_in_best_estimate"] is False
        for item in payload["worker_contribution_trace"]
    )


def test_hybrid_forecast_service_registers_simulation_market_worker_and_downgrades_for_disagreement(
    simulation_data_dir,
):
    from app.services.hybrid_forecast_service import HybridForecastService

    forecast_id = "forecast-market-service"
    _write_simulation_market_artifacts(
        simulation_data_dir,
        forecast_id=forecast_id,
        consensus_probability=0.71,
        disagreement_index=0.31,
    )

    service = HybridForecastService(simulation_data_dir=str(simulation_data_dir))
    workspace_payload = _workspace_payload(
        forecast_id,
        title="Service market question",
        question_text="Will the service path incorporate synthetic market signals?",
        conflicting_bundle=False,
    )
    workspace_payload["simulation_scope"] = _simulation_market_scope_payload(forecast_id)
    workspace = _workspace_from_payload(workspace_payload)

    result = service.execute(
        workspace,
        requested_at="2026-03-30T12:00:00",
        comparable_workspaces=[],
    )

    assert any(worker.kind == "simulation_market" for worker in result.registered_workers)
    payload = result.forecast_answer.answer_payload
    sim_market_trace = next(
        item
        for item in payload["worker_contribution_trace"]
        if item["worker_kind"] == "simulation_market"
    )

    assert sim_market_trace["used_in_best_estimate"] is True
    assert sim_market_trace["confidence_inputs"]["provenance_status"] == "ready"
    assert sim_market_trace["effective_weight"] < 0.3
    assert payload["simulation_market_context"]["included"] is True
    assert payload["simulation_market_context"]["disagreement_index"] == 0.31


def test_hybrid_forecast_service_registers_typed_default_worker_semantics():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    categorical_workspace = _workspace_from_payload(
        {
            **_workspace_payload(
                "forecast-cat-defaults",
                title="Launch posture outlook",
                question_text="Which launch posture will be observed by June 30, 2026?",
            ),
            "forecast_question": _question_payload(
                "forecast-cat-defaults",
                title="Launch posture outlook",
                question_text="Which launch posture will be observed by June 30, 2026?",
                question_type="categorical",
                question_spec={"outcome_labels": ["win", "stretch", "miss"]},
            ),
        }
    )
    numeric_workspace = _workspace_from_payload(
        {
            **_workspace_payload(
                "forecast-num-defaults",
                title="ARR outlook",
                question_text="What ARR will be observed by June 30, 2026?",
            ),
            "forecast_question": _question_payload(
                "forecast-num-defaults",
                title="ARR outlook",
                question_text="What ARR will be observed by June 30, 2026?",
                question_type="numeric",
                question_spec={"unit": "usd_millions", "interval_levels": [50, 80, 90]},
            ),
        }
    )

    categorical_result = service.execute(categorical_workspace, requested_at="2026-03-30T12:00:00")
    numeric_result = service.execute(numeric_workspace, requested_at="2026-03-30T12:00:00")

    categorical_semantics = {
        worker.worker_id: worker.primary_output_semantics
        for worker in categorical_result.registered_workers
        if worker.kind != "simulation"
    }
    numeric_semantics = {
        worker.worker_id: worker.primary_output_semantics
        for worker in numeric_result.registered_workers
        if worker.kind != "simulation"
    }

    assert set(categorical_semantics.values()) == {"forecast_distribution"}
    assert set(numeric_semantics.values()) == {"numeric_interval_estimate"}


def test_hybrid_forecast_service_can_issue_calibrated_categorical_answer():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    workspace = _workspace_from_payload(_categorical_workspace_payload("forecast-categorical"))

    result = service.run(
        workspace=workspace,
        comparable_workspaces=[],
        issued_at="2026-03-30T12:00:00",
    )

    answer = result.forecast_answer
    payload = answer.answer_payload

    assert payload["question_type"] == "categorical"
    assert payload["best_estimate"]["value_type"] == "categorical_distribution"
    assert payload["best_estimate"]["top_label"] in {"win", "stretch"}
    assert payload["backtest_summary"]["status"] == "available"
    assert payload["calibration_summary"]["status"] == "ready"
    assert answer.confidence_semantics == "calibrated"


def test_hybrid_forecast_service_can_issue_calibrated_numeric_answer():
    from app.services.hybrid_forecast_service import HybridForecastService

    service = HybridForecastService()
    workspace = _workspace_from_payload(_numeric_workspace_payload("forecast-numeric"))

    result = service.run(
        workspace=workspace,
        comparable_workspaces=[],
        issued_at="2026-03-30T12:00:00",
    )

    answer = result.forecast_answer
    payload = answer.answer_payload

    assert payload["question_type"] == "numeric"
    assert payload["best_estimate"]["value_type"] == "numeric_interval"
    assert payload["best_estimate"]["intervals"]["80"]["low"] < payload["best_estimate"]["intervals"]["80"]["high"]
    assert payload["backtest_summary"]["status"] == "available"
    assert payload["calibration_summary"]["status"] == "ready"
    assert answer.confidence_semantics == "calibrated"
