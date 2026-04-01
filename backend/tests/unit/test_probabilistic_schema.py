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
        ConditionalVariableSpec,
        ExperimentDesignSpec,
        OutcomeMetricDefinition,
        ForecastBrief,
        ForecastRunBudget,
        ForecastUncertaintyPlan,
        RandomVariableSpec,
        ScenarioTemplateSpec,
        UncertaintySpec,
        VariableGroupSpec,
        RunManifest,
    )

    uncertainty = UncertaintySpec(
        profile="balanced",
        random_variables=[
            RandomVariableSpec(
                field_path="twitter_config.echo_chamber_strength",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.8},
            ),
            RandomVariableSpec(
                field_path="reddit_config.echo_chamber_strength",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.8},
            ),
        ],
        variable_groups=[
            VariableGroupSpec(
                group_id="platform-coupling",
                field_paths=[
                    "twitter_config.echo_chamber_strength",
                    "reddit_config.echo_chamber_strength",
                ],
            )
        ],
        conditional_variables=[
            ConditionalVariableSpec(
                variable=RandomVariableSpec(
                    field_path="twitter_config.echo_chamber_strength",
                    distribution="fixed",
                    parameters={"value": 0.75},
                ),
                condition_field_path="event_config.narrative_direction",
                operator="eq",
                condition_value="crisis",
            )
        ],
        scenario_templates=[
            ScenarioTemplateSpec(
                template_id="base_case",
                label="Base Case",
                field_overrides={"event_config.narrative_direction": "neutral"},
                coverage_tags=["baseline", "monitoring"],
            )
        ],
        experiment_design=ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "twitter_config.echo_chamber_strength",
                "reddit_config.echo_chamber_strength",
            ],
            scenario_template_ids=["base_case"],
            max_templates_per_run=2,
            diversity_axes=["scenario_template", "coverage_tags"],
        ),
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

    brief = ForecastBrief(
        forecast_question="Will simulated total actions exceed 100 by June 30, 2026?",
        resolution_criteria=[
            "Resolve yes if simulation.total_actions is greater than 100.",
            "Resolve no otherwise.",
        ],
        resolution_date="2026-06-30",
        selected_outcome_metrics=[
            "simulation.total_actions",
            "platform.twitter.total_actions",
        ],
        run_budget=ForecastRunBudget(ensemble_size=24, max_concurrency=4),
        uncertainty_plan=ForecastUncertaintyPlan(
            profile="balanced",
            notes=["Use the balanced profile as the first-pass uncertainty sweep."],
        ),
        scoring_rule_preferences=["brier_score", "log_score"],
        compare_candidates=["baseline", "policy_variant_a"],
        scenario_templates=["base_case", "viral_spike"],
    )

    restored_brief = ForecastBrief.from_dict(brief.to_dict())
    manifest = RunManifest(
        simulation_id="sim-001",
        run_id="0001",
        ensemble_id="0001",
        seed_metadata={"root_seed": 11, "resolution_seed": 11},
        resolved_values={"twitter_config.echo_chamber_strength": 0.42},
        assumption_ledger={
            "design_method": "latin-hypercube",
            "scenario_template_ids": ["base_case"],
            "activated_conditions": [],
        },
    )
    restored_manifest = RunManifest.from_dict(manifest.to_dict())

    assert restored_brief == brief
    assert restored_manifest == manifest


def test_structured_uncertainty_contracts_reject_unsupported_design_metadata():
    from app.models.probabilistic import ExperimentDesignSpec, VariableGroupSpec

    with pytest.raises(ValueError, match="Unsupported experiment design method"):
        ExperimentDesignSpec(method="monte-carlo")

    with pytest.raises(ValueError, match="field_paths must contain at least two"):
        VariableGroupSpec(group_id="too-small", field_paths=["only.one"])


def test_scenario_template_and_experiment_design_round_trip_diversity_metadata():
    from app.models.probabilistic import (
        ConditionalVariableSpec,
        ExperimentDesignSpec,
        RandomVariableSpec,
        ScenarioTemplateSpec,
    )

    template = ScenarioTemplateSpec(
        template_id="crisis_case",
        label="Crisis Case",
        field_overrides={
            "event_config.narrative_direction": "crisis",
            "event_config.hot_topics": ["crisis", "labor"],
        },
        coverage_tags=["trajectory:shock", "attention:elevated", "platform:cross"],
        exogenous_events=[
            {
                "event_id": "crisis_case_briefing",
                "kind": "breaking_update",
                "timing_window": "early",
            }
        ],
        conditional_overrides=[
            ConditionalVariableSpec(
                variable=RandomVariableSpec(
                    field_path="twitter_config.viral_threshold",
                    distribution="fixed",
                    parameters={"value": 6},
                ),
                condition_field_path="event_config.narrative_direction",
                operator="eq",
                condition_value="crisis",
            )
        ],
        notes=["Use a substantive crisis lane rather than a label-only template."],
    )
    design = ExperimentDesignSpec(
        method="latin-hypercube",
        numeric_dimensions=[
            "twitter_config.echo_chamber_strength",
            "reddit_config.echo_chamber_strength",
        ],
        scenario_template_ids=["crisis_case"],
        scenario_assignment="weighted_cycle",
        scenario_coverage_axes=["attention", "platform", "trajectory"],
        max_template_reuse_streak=1,
        notes=["Broaden event-space coverage across explicit scenario axes."],
    )

    assert ScenarioTemplateSpec.from_dict(template.to_dict()) == template
    assert ExperimentDesignSpec.from_dict(design.to_dict()) == design


def test_structural_uncertainty_specs_round_trip_and_validate_supported_kinds():
    from app.models.probabilistic import (
        ExperimentDesignSpec,
        StructuralUncertaintyOption,
        StructuralUncertaintySpec,
        UncertaintySpec,
    )

    structural_spec = StructuralUncertaintySpec(
        uncertainty_id="event_arrival_process",
        kind="event_arrival_process",
        label="Event Arrival Process",
        options=[
            StructuralUncertaintyOption(
                option_id="steady_cadence",
                label="Steady Cadence",
                config_overrides={
                    "structural_uncertainty.event_arrival_process.mode": "steady_cadence",
                    "structural_uncertainty.event_arrival_process.spacing_hours": 6,
                },
                coverage_tags=["arrival:steady"],
                runtime_transition_hints=[
                    {
                        "transition_type": "event",
                        "summary": "Events arrive on an even cadence.",
                    }
                ],
                assumption_text="Events arrive on an even cadence with no early burst.",
            ),
            StructuralUncertaintyOption(
                option_id="burst_front_loaded",
                label="Burst Front Loaded",
                config_overrides={
                    "structural_uncertainty.event_arrival_process.mode": "burst_front_loaded",
                    "structural_uncertainty.event_arrival_process.spacing_hours": 2,
                },
                coverage_tags=["arrival:burst"],
                runtime_transition_hints=[
                    {
                        "transition_type": "event",
                        "summary": "Events cluster early in the run.",
                    }
                ],
                assumption_text="Events cluster early and then decay.",
            ),
        ],
        coverage_tags=["axis:event_arrival"],
    )
    uncertainty = UncertaintySpec(
        profile="balanced",
        structural_uncertainties=[structural_spec],
        experiment_design=ExperimentDesignSpec(
            method="latin-hypercube",
            structural_uncertainty_ids=["event_arrival_process"],
        ),
    )

    restored = UncertaintySpec.from_dict(uncertainty.to_dict())

    assert restored == uncertainty
    assert restored.structural_uncertainties[0].options[1].option_id == "burst_front_loaded"
    assert restored.experiment_design.structural_uncertainty_ids == [
        "event_arrival_process"
    ]

    with pytest.raises(ValueError, match="Unsupported structural uncertainty kind"):
        StructuralUncertaintySpec(
            uncertainty_id="unsupported_axis",
            kind="unsupported_axis",
            label="Unsupported Axis",
            options=[
                StructuralUncertaintyOption(
                    option_id="baseline",
                    label="Baseline",
                )
            ],
        )


def test_forecast_brief_rejects_invalid_resolution_date():
    from app.models.probabilistic import (
        ForecastBrief,
        ForecastRunBudget,
        ForecastUncertaintyPlan,
    )

    with pytest.raises(ValueError, match="resolution_date"):
        ForecastBrief(
            forecast_question="Will simulated total actions exceed 100?",
            resolution_criteria=["Resolve yes if simulation.total_actions is greater than 100."],
            resolution_date="June 30th, 2026",
            selected_outcome_metrics=["simulation.total_actions"],
            run_budget=ForecastRunBudget(ensemble_size=12, max_concurrency=3),
            uncertainty_plan=ForecastUncertaintyPlan(profile="balanced"),
            scoring_rule_preferences=["brier_score"],
        )


def test_calibration_and_backtest_artifacts_round_trip():
    from app.models.probabilistic import (
        BacktestCaseResult,
        BacktestSummary,
        CalibrationReadiness,
        CalibrationSummary,
        MetricBacktestSummary,
        MetricCalibrationSummary,
        ObservedTruthCase,
        ObservedTruthRegistry,
        ReliabilityBin,
        SUPPORTED_SCORING_RULES,
    )

    registry = ObservedTruthRegistry(
        simulation_id="sim-001",
        ensemble_id="0001",
        registry_scope={
            "level": "ensemble",
            "simulation_id": "sim-001",
            "ensemble_id": "0001",
        },
        cases=[
            ObservedTruthCase(
                case_id="case-1",
                metric_id="simulation.completed",
                value_kind="binary",
                forecast_probability=0.8,
                observed_value=True,
                forecast_source="aggregate_summary.json",
                forecast_issued_at="2026-03-29T10:00:00",
                forecast_scope={"level": "ensemble", "ensemble_id": "0001"},
                observed_source="manual-review.csv",
                observed_at="2026-03-29T12:00:00",
                source_run_id="0001",
                resolution_note="Recorded as completed after explicit run review.",
            )
        ],
        quality_summary={
            "status": "complete",
            "total_case_count": 1,
            "metric_ids": ["simulation.completed"],
            "warnings": [],
        },
    )
    restored_registry = ObservedTruthRegistry.from_dict(registry.to_dict())

    backtest = BacktestSummary(
        simulation_id="sim-001",
        ensemble_id="0001",
        metric_backtests={
            "simulation.completed": MetricBacktestSummary(
                metric_id="simulation.completed",
                value_kind="binary",
                case_count=2,
                positive_case_count=1,
                negative_case_count=1,
                observed_event_rate=0.5,
                mean_forecast_probability=0.55,
                scoring_rules=["brier_score", "log_score"],
                case_results=[
                    BacktestCaseResult(
                        case_id="case-1",
                        metric_id="simulation.completed",
                        forecast_probability=0.8,
                        observed_value=True,
                        scores={"brier_score": 0.04, "log_score": 0.2231435513},
                    ),
                    BacktestCaseResult(
                        case_id="case-2",
                        metric_id="simulation.completed",
                        forecast_probability=0.3,
                        observed_value=False,
                        scores={"brier_score": 0.09, "log_score": 0.3566749439},
                    )
                ],
                scores={
                    "brier_score": 0.065,
                    "log_score": 0.2899092476,
                    "brier_skill_score": 0.74,
                },
            )
        },
        quality_summary={
            "status": "complete",
            "total_case_count": 2,
            "scored_case_count": 2,
            "skipped_case_count": 0,
            "supported_metric_ids": ["simulation.completed"],
            "unscored_metric_ids": [],
            "warnings": [],
        },
    )
    restored_backtest = BacktestSummary.from_dict(backtest.to_dict())

    calibration = CalibrationSummary(
        simulation_id="sim-001",
        ensemble_id="0001",
        metric_calibrations={
            "simulation.completed": MetricCalibrationSummary(
                metric_id="simulation.completed",
                value_kind="binary",
                case_count=10,
                supported_scoring_rules=["brier_score", "log_score"],
                scores={
                    "brier_score": 0.12,
                    "log_score": 0.41,
                    "brier_skill_score": 0.52,
                },
                reliability_bins=[
                    ReliabilityBin(
                        bin_index=0,
                        lower_bound=0.0,
                        upper_bound=0.2,
                        case_count=2,
                        mean_forecast_probability=0.1,
                        observed_frequency=0.0,
                        observed_minus_forecast=-0.1,
                    )
                ],
                diagnostics={
                    "expected_calibration_error": 0.12,
                    "max_calibration_gap": 0.2,
                    "observed_event_rate": 0.4,
                    "mean_forecast_probability": 0.36,
                },
                readiness=CalibrationReadiness(
                    ready=True,
                    minimum_case_count=10,
                    actual_case_count=10,
                    minimum_positive_case_count=3,
                    actual_positive_case_count=4,
                    minimum_negative_case_count=3,
                    actual_negative_case_count=6,
                    non_empty_bin_count=2,
                    supported_bin_count=2,
                    minimum_supported_bin_count=2,
                    gating_reasons=[],
                    confidence_label="limited",
                ),
            )
        },
        quality_summary={
            "status": "complete",
            "ready_metric_ids": ["simulation.completed"],
            "not_ready_metric_ids": [],
        },
    )
    restored_calibration = CalibrationSummary.from_dict(calibration.to_dict())

    assert restored_registry == registry
    assert restored_backtest == backtest
    assert restored_calibration == calibration
    assert SUPPORTED_SCORING_RULES == {"brier_score", "log_score"}
    assert restored_registry.schema_version == "probabilistic.observed_truth.v2"
    assert restored_backtest.schema_version == "probabilistic.backtest.v2"
    assert restored_calibration.schema_version == "probabilistic.calibration.v2"


def test_observed_truth_case_rejects_invalid_probability():
    from app.models.probabilistic import ObservedTruthCase

    with pytest.raises(ValueError, match="forecast_probability"):
        ObservedTruthCase(
            case_id="case-1",
            metric_id="simulation.completed",
            forecast_probability=1.2,
            observed_value=True,
        )


def test_supported_outcome_metric_registry_is_explicit(probabilistic_domain):
    from app.models.probabilistic import SUPPORTED_OUTCOME_METRICS

    assert set(probabilistic_domain["metrics"]).issubset(SUPPORTED_OUTCOME_METRICS)


def test_supported_outcome_metric_definitions_expose_richer_contract_metadata():
    from app.models.probabilistic import build_supported_outcome_metric

    completion_metric = build_supported_outcome_metric("simulation.completed")
    leading_platform_metric = build_supported_outcome_metric("platform.leading_platform")
    top_topic_share_metric = build_supported_outcome_metric("content.top_topic_share")
    transfer_metric = build_supported_outcome_metric(
        "cross_platform.topic_transfer_observed"
    )
    balance_band_metric = build_supported_outcome_metric("platform.action_balance_band")
    volatility_metric = build_supported_outcome_metric(
        "simulation.actions_per_active_round_cv"
    )

    assert completion_metric.aggregation == "flag"
    assert completion_metric.unit == "boolean"
    assert leading_platform_metric.aggregation == "category"
    assert leading_platform_metric.unit == "category"
    assert top_topic_share_metric.aggregation == "ratio"
    assert top_topic_share_metric.unit == "share"
    assert transfer_metric.aggregation == "flag"
    assert transfer_metric.value_kind == "binary"
    assert completion_metric.confidence_support["backtesting_supported"] is True
    assert completion_metric.confidence_support["calibration_supported"] is True
    assert transfer_metric.confidence_support["support_tier"] == "binary-ready"
    assert balance_band_metric.aggregation == "category"
    assert balance_band_metric.value_kind == "categorical"
    assert balance_band_metric.confidence_support["backtesting_supported"] is False
    assert volatility_metric.aggregation == "dispersion"
    assert volatility_metric.unit == "cv"
    assert volatility_metric.confidence_support["support_tier"] == "unsupported"


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
        "simulation.time_to_first_action_seconds",
        "simulation.active_round_share",
        "simulation.actions_per_active_round_cv",
        "simulation.top_agent_action_share",
        "simulation.top_2_agent_action_share",
        "simulation.max_round_action_share",
        "simulation.top_agent_action_share_ge_0_5",
        "platform.twitter.any_actions",
        "platform.reddit.any_actions",
        "platform.twitter.action_share",
        "platform.reddit.action_share",
        "platform.twitter.observed_action_window_seconds",
        "platform.reddit.observed_action_window_seconds",
        "platform.twitter.time_to_first_action_seconds",
        "platform.reddit.time_to_first_action_seconds",
        "platform.leading_platform",
        "platform.action_balance_gap",
        "platform.action_balance_gap_ge_0_5",
        "platform.action_balance_band",
        "cross_platform.first_action_lag_seconds",
        "cross_platform.completion_lag_seconds",
        "cross_platform.topic_transfer_observed",
        "cross_platform.topic_transfer_lag_seconds",
        "content.unique_topics_mentioned",
        "content.top_topic_share",
        "content.top_topic_share_ge_0_5",
        "content.dominant_topic",
        "content.dominant_topic_agent_reach",
        "content.dominant_topic_platform_reach",
        "content.dominant_topic_round_reach",
        "content.topic_concentration_hhi",
        "content.topic_concentration_band",
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
