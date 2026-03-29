import pytest


def test_random_variable_spec_round_trips_to_dict():
    from app.models.probabilistic import RandomVariableSpec

    spec = RandomVariableSpec(
        field_path="time_config.total_simulation_hours",
        distribution="categorical",
        parameters={"choices": [24, 48, 72], "weights": [0.2, 0.3, 0.5]},
        description="Simulation horizon options",
    )

    restored = RandomVariableSpec.from_dict(spec.to_dict())

    assert restored == spec


def test_random_variable_spec_rejects_unsupported_distribution():
    from app.models.probabilistic import RandomVariableSpec

    with pytest.raises(ValueError, match="Unsupported distribution"):
        RandomVariableSpec(
            field_path="time_config.total_simulation_hours",
            distribution="poisson",
            parameters={"lambda": 3},
        )


def test_uncertainty_spec_rejects_unsupported_profile():
    from app.models.probabilistic import UncertaintySpec

    with pytest.raises(ValueError, match="Unsupported uncertainty profile"):
        UncertaintySpec(profile="unknown-profile")


def test_seed_policy_round_trips_with_uncertainty_spec(probabilistic_domain):
    from app.models.probabilistic import SeedPolicy, UncertaintySpec

    seed_policy = SeedPolicy(
        strategy=probabilistic_domain["seed_policy"]["strategy"],
        root_seed=1234,
        derive_run_seeds=probabilistic_domain["seed_policy"]["derive_run_seeds"],
    )
    uncertainty = UncertaintySpec(
        profile=probabilistic_domain["default_profile"],
        seed_policy=seed_policy,
        notes=["Seed derivation is explicit even before runtime sampling exists."],
    )

    restored = UncertaintySpec.from_dict(uncertainty.to_dict())

    assert restored == uncertainty
    assert restored.seed_policy.root_seed == 1234


def test_uncertainty_and_outcome_specs_round_trip():
    from app.models.probabilistic import (
        OutcomeMetricDefinition,
        RandomVariableSpec,
        UncertaintySpec,
    )

    uncertainty = UncertaintySpec(
        profile="balanced",
        random_variables=[
            RandomVariableSpec(
                field_path="twitter_config.echo_chamber_strength",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.8},
            )
        ],
        notes=["Foundation slice only persists contracts."],
    )
    outcomes = [
        OutcomeMetricDefinition(
            metric_id="simulation.total_actions",
            label="Total Actions",
            description="Count all platform actions in the run family.",
        )
    ]

    restored_uncertainty = UncertaintySpec.from_dict(uncertainty.to_dict())
    restored_outcomes = [
        OutcomeMetricDefinition.from_dict(item.to_dict()) for item in outcomes
    ]

    assert restored_uncertainty == uncertainty
    assert restored_outcomes == outcomes


def test_supported_outcome_metric_registry_is_explicit(probabilistic_domain):
    from app.models.probabilistic import SUPPORTED_OUTCOME_METRICS

    assert set(probabilistic_domain["metrics"]).issubset(SUPPORTED_OUTCOME_METRICS)


def test_supported_outcome_metric_definitions_expose_richer_contract_metadata():
    from app.models.probabilistic import build_supported_outcome_metric

    completion_metric = build_supported_outcome_metric("simulation.completed")
    leading_platform_metric = build_supported_outcome_metric("platform.leading_platform")
    top_topic_share_metric = build_supported_outcome_metric("content.top_topic_share")

    assert completion_metric.aggregation == "flag"
    assert completion_metric.unit == "boolean"
    assert leading_platform_metric.aggregation == "category"
    assert leading_platform_metric.unit == "category"
    assert top_topic_share_metric.aggregation == "ratio"
    assert top_topic_share_metric.unit == "share"


def test_supported_outcome_metric_registry_exposes_richer_grounded_metrics():
    from app.models.probabilistic import SUPPORTED_OUTCOME_METRIC_DEFINITIONS

    expected_metric_ids = {
        "simulation.any_actions",
        "simulation.completed",
        "simulation.unique_active_agents",
        "simulation.rounds_with_actions",
        "simulation.observed_action_window_seconds",
        "simulation.observed_completion_window_seconds",
        "simulation.agent_action_concentration_hhi",
        "platform.twitter.any_actions",
        "platform.reddit.any_actions",
        "platform.twitter.action_share",
        "platform.reddit.action_share",
        "platform.twitter.observed_action_window_seconds",
        "platform.reddit.observed_action_window_seconds",
        "platform.leading_platform",
        "platform.action_balance_gap",
        "cross_platform.first_action_lag_seconds",
        "content.unique_topics_mentioned",
        "content.top_topic_share",
        "content.dominant_topic",
    }

    assert expected_metric_ids.issubset(SUPPORTED_OUTCOME_METRIC_DEFINITIONS)


def test_supported_outcome_metric_metadata_carries_value_shape():
    from app.models.probabilistic import build_supported_outcome_metric

    completed = build_supported_outcome_metric("simulation.completed")
    observed_window = build_supported_outcome_metric(
        "simulation.observed_action_window_seconds"
    )
    dominant_topic = build_supported_outcome_metric("content.dominant_topic")

    assert completed.aggregation == "flag"
    assert completed.unit == "boolean"
    assert completed.value_kind == "binary"

    assert observed_window.aggregation == "duration"
    assert observed_window.unit == "seconds"
    assert observed_window.value_kind == "numeric"

    assert dominant_topic.aggregation == "category"
    assert dominant_topic.unit == "category"
    assert dominant_topic.value_kind == "categorical"


def test_ensemble_spec_round_trips_to_dict():
    from app.models.probabilistic import EnsembleSpec

    spec = EnsembleSpec(
        run_count=12,
        max_concurrency=3,
        root_seed=42,
        sampling_mode="seeded",
    )

    restored = EnsembleSpec.from_dict(spec.to_dict())

    assert restored == spec


def test_ensemble_spec_rejects_negative_root_seed():
    from app.models.probabilistic import EnsembleSpec

    with pytest.raises(ValueError, match="root_seed must be non-negative"):
        EnsembleSpec(
            run_count=2,
            max_concurrency=1,
            root_seed=-1,
        )


def test_run_manifest_round_trips_to_dict():
    from app.models.probabilistic import RunManifest

    manifest = RunManifest(
        simulation_id="sim-test",
        run_id="run_001",
        root_seed=42,
        resolved_values={
            "time_config.total_simulation_hours": 48,
            "twitter_config.echo_chamber_strength": 0.6,
        },
        config_artifact="resolved_config.json",
    )

    restored = RunManifest.from_dict(manifest.to_dict())

    assert restored == manifest
