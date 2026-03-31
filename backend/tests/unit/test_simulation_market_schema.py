import importlib

import pytest


def _load_module():
    return importlib.import_module("app.models.simulation_market")


def test_simulation_market_artifacts_round_trip():
    module = _load_module()

    reference = module.SimulationMarketReference(
        simulation_id="sim-1",
        ensemble_id="0001",
        run_id="0002",
        platform="twitter",
        round_num=3,
        line_number=8,
        agent_id=17,
        agent_name="Analyst A",
        timestamp="2026-03-30T12:00:00",
        action_type="CREATE_POST",
        source_artifact="twitter/actions.jsonl",
    )
    belief = module.SimulationMarketAgentBelief(
        forecast_id="forecast-1",
        question_type="binary",
        agent_id=17,
        agent_name="Analyst A",
        judgment_type="binary_probability",
        probability=0.64,
        confidence=0.58,
        uncertainty_expression="medium",
        rationale_tags=["base_rate", "policy_delay"],
        missing_information_requests=["Need labor-market update"],
        reference=reference,
        parse_mode="structured",
        source_excerpt="I put this near 64% after the latest labor prints.",
    )
    snapshot = module.SimulationMarketSnapshot(
        simulation_id="sim-1",
        ensemble_id="0001",
        run_id="0002",
        forecast_id="forecast-1",
        question_type="binary",
        extraction_status="ready",
        participating_agent_count=2,
        extracted_signal_count=3,
        disagreement_index=0.24,
        synthetic_consensus_probability=0.57,
        dominant_outcome=None,
        categorical_distribution={},
        missing_information_request_count=1,
        boundary_notes=[
            "Synthetic market outputs are heuristic inference inputs, not calibrated forecasts."
        ],
    )
    manifest = module.SimulationMarketManifest(
        simulation_id="sim-1",
        ensemble_id="0001",
        run_id="0002",
        forecast_id="forecast-1",
        question_type="binary",
        extraction_status="ready",
        supported_question_type=True,
        forecast_workspace_linked=True,
        scope_linked_to_run=True,
        artifact_paths={
            "market_snapshot": "market_snapshot.json",
            "agent_belief_book": "agent_belief_book.json",
        },
        signal_counts={
            "agent_beliefs": 2,
            "belief_updates": 3,
            "missing_information_requests": 1,
        },
        warnings=[],
        source_artifacts={
            "run_manifest": "run_manifest.json",
            "action_logs": ["twitter/actions.jsonl"],
        },
        boundary_notes=snapshot.boundary_notes,
        extracted_at="2026-03-30T12:05:00",
    )

    assert module.SimulationMarketReference.from_dict(reference.to_dict()).to_dict() == reference.to_dict()
    assert module.SimulationMarketAgentBelief.from_dict(belief.to_dict()).to_dict() == belief.to_dict()
    assert module.SimulationMarketSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()
    assert module.SimulationMarketManifest.from_dict(manifest.to_dict()).to_dict() == manifest.to_dict()


def test_simulation_market_manifest_rejects_unknown_status():
    module = _load_module()

    with pytest.raises(ValueError):
        module.SimulationMarketManifest(
            simulation_id="sim-1",
            ensemble_id="0001",
            run_id="0001",
            forecast_id="forecast-1",
            question_type="binary",
            extraction_status="invented_status",
            supported_question_type=True,
            forecast_workspace_linked=True,
            scope_linked_to_run=True,
            artifact_paths={},
            signal_counts={},
            warnings=[],
            source_artifacts={},
            boundary_notes=[],
            extracted_at="2026-03-30T12:05:00",
        )
