import importlib

import pytest


def _load_models_module():
    return importlib.import_module("app.models.probabilistic")


def _load_resolver_module():
    return importlib.import_module("app.services.uncertainty_resolver")


def _build_base_config():
    return {
        "time_config": {
            "total_simulation_hours": 24,
            "minutes_per_round": 60,
        },
        "agent_configs": [
            {
                "agent_id": 0,
                "activity_level": 0.5,
                "response_delay_min": 5,
            }
        ],
        "platform": {
            "weights": {
                "recency": 0.4,
            }
        },
    }


def test_same_seed_produces_same_resolved_config_and_manifest():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        root_seed=101,
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
            models.RandomVariableSpec(
                field_path="time_config.total_simulation_hours",
                distribution="categorical",
                parameters={"choices": [24, 48, 72], "weights": [0.1, 0.2, 0.7]},
            ),
        ],
    )

    resolver = resolver_module.UncertaintyResolver()

    first = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=_build_base_config(),
        uncertainty_spec=uncertainty_spec,
        resolution_seed=777,
    )
    second = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=_build_base_config(),
        uncertainty_spec=uncertainty_spec,
        resolution_seed=777,
    )

    assert first["resolved_config"] == second["resolved_config"]
    assert first["run_manifest"] == second["run_manifest"]
    assert first["run_manifest"].seed_metadata["resolution_seed"] == 777


def test_different_seeds_can_change_non_fixed_resolution():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
        ],
    )

    resolver = resolver_module.UncertaintyResolver()

    first = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=_build_base_config(),
        uncertainty_spec=uncertainty_spec,
        resolution_seed=1,
    )
    second = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-002",
        base_config=_build_base_config(),
        uncertainty_spec=uncertainty_spec,
        resolution_seed=2,
    )

    assert (
        first["resolved_config"]["agent_configs"][0]["activity_level"]
        != second["resolved_config"]["agent_configs"][0]["activity_level"]
    )


def test_all_supported_distributions_and_nested_path_patching_work():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="time_config.total_simulation_hours",
                distribution="fixed",
                parameters={"value": 48},
            ),
            models.RandomVariableSpec(
                field_path="agent_configs[0].response_delay_min",
                distribution="categorical",
                parameters={"choices": [5, 10], "weights": [0.0, 1.0]},
            ),
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.2},
            ),
            models.RandomVariableSpec(
                field_path="platform.weights.recency",
                distribution="normal",
                parameters={"mean": 0.55, "stddev": 0.0},
            ),
        ],
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=_build_base_config(),
        uncertainty_spec=uncertainty_spec,
        resolution_seed=99,
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["time_config"]["total_simulation_hours"] == 48
    assert resolved["agent_configs"][0]["response_delay_min"] == 10
    assert resolved["agent_configs"][0]["activity_level"] == 0.2
    assert resolved["platform"]["weights"]["recency"] == 0.55
    assert manifest.resolved_values == {
        "time_config.total_simulation_hours": 48,
        "agent_configs[0].response_delay_min": 10,
        "agent_configs[0].activity_level": 0.2,
        "platform.weights.recency": 0.55,
    }


def test_bad_paths_fail_clearly():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[9].activity_level",
                distribution="fixed",
                parameters={"value": 0.8},
            ),
        ],
    )

    resolver = resolver_module.UncertaintyResolver()

    with pytest.raises(ValueError, match="Invalid config path"):
        resolver.resolve_run_config(
            simulation_id="sim-test",
            run_id="run-001",
            base_config=_build_base_config(),
            uncertainty_spec=uncertainty_spec,
            resolution_seed=10,
        )


def test_malformed_specs_fail_clearly():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="platform.weights.recency",
                distribution="fixed",
                parameters={},
            ),
        ],
    )

    resolver = resolver_module.UncertaintyResolver()

    with pytest.raises(ValueError, match="Malformed distribution parameters"):
        resolver.resolve_run_config(
            simulation_id="sim-test",
            run_id="run-001",
            base_config=_build_base_config(),
            uncertainty_spec=uncertainty_spec,
            resolution_seed=10,
        )


def test_resolver_consumes_design_rows_and_records_assumption_ledger():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["event_config"] = {"narrative_direction": "neutral"}

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
            models.RandomVariableSpec(
                field_path="platform.weights.recency",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.8},
            ),
        ],
        conditional_variables=[
            models.ConditionalVariableSpec(
                variable=models.RandomVariableSpec(
                    field_path="platform.weights.recency",
                    distribution="fixed",
                    parameters={"value": 0.9},
                ),
                condition_field_path="event_config.narrative_direction",
                operator="eq",
                condition_value="crisis",
            )
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="crisis_case",
                label="Crisis Case",
                field_overrides={"event_config.narrative_direction": "crisis"},
            )
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "agent_configs[0].activity_level",
                "platform.weights.recency",
            ],
            scenario_template_ids=["crisis_case"],
        ),
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=77,
        experiment_design_row={
            "row_index": 0,
            "normalized_coordinates": {
                "agent_configs[0].activity_level": 0.25,
                "platform.weights.recency": 0.25,
            },
            "stratum_indices": {
                "agent_configs[0].activity_level": 0,
                "platform.weights.recency": 0,
            },
            "scenario_template_ids": ["crisis_case"],
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["agent_configs"][0]["activity_level"] == pytest.approx(0.3)
    assert resolved["event_config"]["narrative_direction"] == "crisis"
    assert resolved["platform"]["weights"]["recency"] == 0.9
    assert manifest.assumption_ledger["design_method"] == "latin-hypercube"
    assert manifest.assumption_ledger["scenario_template_ids"] == ["crisis_case"]
    assert manifest.assumption_ledger["applied_templates"] == ["crisis_case"]
    assert manifest.assumption_ledger["activated_conditions"] == [
        "platform.weights.recency"
    ]
    assert manifest.assumption_ledger["design_row"]["normalized_coordinates"][
        "agent_configs[0].activity_level"
    ] == pytest.approx(0.25)


def test_resolver_applies_substantive_event_templates_and_conditional_overrides():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["event_config"] = {
        "hot_topics": ["seed"],
        "scheduled_events": [],
        "narrative_direction": "neutral",
    }
    base_config["twitter_config"] = {
        "recency_weight": 0.4,
        "viral_threshold": 10,
        "echo_chamber_strength": 0.5,
    }

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="twitter_config.echo_chamber_strength",
                distribution="fixed",
                parameters={"value": 0.82},
            ),
        ],
        conditional_variables=[
            models.ConditionalVariableSpec(
                variable=models.RandomVariableSpec(
                    field_path="twitter_config.viral_threshold",
                    distribution="fixed",
                    parameters={"value": 7},
                ),
                condition_field_path="twitter_config.echo_chamber_strength",
                operator="gte",
                condition_value=0.75,
            ),
            models.ConditionalVariableSpec(
                variable=models.RandomVariableSpec(
                    field_path="twitter_config.recency_weight",
                    distribution="fixed",
                    parameters={"value": 0.55},
                ),
                condition_field_path="event_config.narrative_direction",
                operator="eq",
                condition_value="viral_spike",
            ),
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="viral_spike",
                label="Viral Spike",
                field_overrides={
                    "event_config.narrative_direction": "viral_spike",
                    "event_config.hot_topics": ["seed", "attention_surge"],
                    "event_config.scheduled_events": [
                        {
                            "offset_hours": 2,
                            "event_type": "exogenous_spike",
                            "topic": "attention_surge",
                            "intensity": "high",
                        }
                    ],
                },
            )
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            scenario_template_ids=["viral_spike"],
        ),
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=91,
        experiment_design_row={
            "row_index": 0,
            "normalized_coordinates": {},
            "stratum_indices": {},
            "scenario_template_ids": ["viral_spike"],
            "coverage_signature": {
                "template_count": 1,
                "override_field_count": 3,
            },
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["event_config"]["narrative_direction"] == "viral_spike"
    assert resolved["event_config"]["hot_topics"] == ["seed", "attention_surge"]
    assert resolved["event_config"]["scheduled_events"] == [
        {
            "offset_hours": 2,
            "event_type": "exogenous_spike",
            "topic": "attention_surge",
            "intensity": "high",
        }
    ]
    assert resolved["twitter_config"]["echo_chamber_strength"] == 0.82
    assert resolved["twitter_config"]["viral_threshold"] == 7
    assert resolved["twitter_config"]["recency_weight"] == 0.55
    assert manifest.assumption_ledger["activated_conditions"] == [
        "twitter_config.viral_threshold",
        "twitter_config.recency_weight",
    ]
    assert manifest.assumption_ledger["design_row"]["coverage_signature"] == {
        "template_count": 1,
        "override_field_count": 3,
    }


def test_resolver_applies_template_exogenous_events_and_template_conditionals():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["event_config"] = {
        "narrative_direction": "neutral",
        "hot_topics": ["seed"],
        "scheduled_events": [],
    }
    base_config["twitter_config"] = {"viral_threshold": 10}
    base_config["reddit_config"] = {"viral_threshold": 10}

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="crisis_spike",
                label="Crisis Spike",
                field_overrides={
                    "event_config.narrative_direction": "crisis",
                    "event_config.hot_topics": ["seed", "shock"],
                },
                coverage_tags=["shock", "amplification"],
                exogenous_events=[
                    {
                        "event_id": "shock-wave",
                        "kind": "breaking_news",
                        "hour": 2,
                    }
                ],
                conditional_overrides=[
                    models.ConditionalVariableSpec(
                        variable=models.RandomVariableSpec(
                            field_path="twitter_config.viral_threshold",
                            distribution="fixed",
                            parameters={"value": 6},
                        ),
                        condition_field_path="event_config.narrative_direction",
                        operator="eq",
                        condition_value="crisis",
                    )
                ],
            ),
            models.ScenarioTemplateSpec(
                template_id="bridge_response",
                label="Bridge Response",
                field_overrides={
                    "reddit_config.viral_threshold": 12,
                },
                coverage_tags=["bridge", "response"],
                exogenous_events=[
                    {
                        "event_id": "bridge-briefing",
                        "kind": "community_response",
                        "hour": 5,
                    }
                ],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=["agent_configs[0].activity_level"],
            scenario_template_ids=["crisis_spike", "bridge_response"],
            max_templates_per_run=2,
            template_combination_policy="pairwise",
        ),
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-002",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=12,
        experiment_design_row={
            "row_index": 1,
            "normalized_coordinates": {
                "agent_configs[0].activity_level": 0.5,
            },
            "stratum_indices": {
                "agent_configs[0].activity_level": 1,
            },
            "scenario_template_ids": ["crisis_spike", "bridge_response"],
            "scenario_coverage": {
                "coverage_tags": ["shock", "bridge", "response"],
                "exogenous_event_ids": ["shock-wave", "bridge-briefing"],
            },
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["event_config"]["narrative_direction"] == "crisis"
    assert resolved["event_config"]["hot_topics"] == ["seed", "shock"]
    assert [item["event_id"] for item in resolved["event_config"]["scheduled_events"]] == [
        "shock-wave",
        "bridge-briefing",
    ]
    assert resolved["twitter_config"]["viral_threshold"] == 6
    assert resolved["reddit_config"]["viral_threshold"] == 12
    assert manifest.assumption_ledger["applied_templates"] == [
        "crisis_spike",
        "bridge_response",
    ]
    assert manifest.assumption_ledger["applied_exogenous_event_ids"] == [
        "shock-wave",
        "bridge-briefing",
    ]
    assert manifest.assumption_ledger["scenario_coverage"]["coverage_tags"] == [
        "shock",
        "bridge",
        "response",
    ]
    assert manifest.assumption_ledger["activated_conditions"] == [
        "twitter_config.viral_threshold"
    ]


def test_resolver_applies_multi_template_event_overrides_and_records_diversity_metadata():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["event_config"] = {
        "narrative_direction": "neutral",
        "hot_topics": ["seed"],
        "scheduled_events": [],
    }
    base_config["time_config"]["peak_activity_multiplier"] = 1.5
    base_config["time_config"]["work_activity_multiplier"] = 0.7

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        conditional_variables=[
            models.ConditionalVariableSpec(
                variable=models.RandomVariableSpec(
                    field_path="time_config.work_activity_multiplier",
                    distribution="fixed",
                    parameters={"value": 0.95},
                ),
                condition_field_path="event_config.narrative_direction",
                operator="eq",
                condition_value="consensus",
            )
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="shock_spike",
                label="Shock Spike",
                field_overrides={
                    "event_config.narrative_direction": "shock",
                    "event_config.hot_topics": ["seed", "shockwave"],
                    "event_config.scheduled_events": [
                        {"hour": 2, "event_type": "amplification_wave", "intensity": "high"}
                    ],
                },
                coverage_tags=["shock", "amplification"],
            ),
            models.ScenarioTemplateSpec(
                template_id="consensus_bridge",
                label="Consensus Bridge",
                field_overrides={
                    "event_config.narrative_direction": "consensus",
                    "time_config.peak_activity_multiplier": 1.9,
                },
                coverage_tags=["bridge", "coordination"],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            scenario_template_ids=["shock_spike", "consensus_bridge"],
            max_templates_per_run=2,
            diversity_axes=["scenario_template", "coverage_tags"],
        ),
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-009",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=42,
        experiment_design_row={
            "row_index": 0,
            "normalized_coordinates": {},
            "stratum_indices": {},
            "scenario_template_ids": ["shock_spike", "consensus_bridge"],
            "scenario_coverage_tags": [
                "amplification",
                "bridge",
                "coordination",
                "shock",
            ],
            "scenario_override_fields": [
                "event_config.hot_topics",
                "event_config.narrative_direction",
                "event_config.scheduled_events",
                "time_config.peak_activity_multiplier",
            ],
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["event_config"]["hot_topics"] == ["seed", "shockwave"]
    assert resolved["event_config"]["scheduled_events"] == [
        {"hour": 2, "event_type": "amplification_wave", "intensity": "high"}
    ]
    assert resolved["time_config"]["peak_activity_multiplier"] == 1.9
    assert resolved["time_config"]["work_activity_multiplier"] == 0.95
    assert manifest.assumption_ledger["scenario_template_ids"] == [
        "shock_spike",
        "consensus_bridge",
    ]
    assert manifest.assumption_ledger["scenario_coverage_tags"] == [
        "amplification",
        "bridge",
        "coordination",
        "shock",
    ]
    assert manifest.assumption_ledger["scenario_template_labels"] == [
        "Consensus Bridge",
        "Shock Spike",
    ]
    assert manifest.assumption_ledger["scenario_signature"]["template_count"] == 2


def test_resolver_applies_template_exogenous_events_and_template_conditionals():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["event_config"] = {
        "narrative_direction": "neutral",
        "hot_topics": ["seed"],
        "scheduled_events": [],
    }
    base_config["twitter_config"] = {"viral_threshold": 10}
    base_config["reddit_config"] = {"viral_threshold": 10}

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="crisis_case",
                label="Crisis Case",
                field_overrides={
                    "event_config.narrative_direction": "crisis",
                    "event_config.hot_topics": ["seed", "crisis"],
                    "event_config.scheduled_events": [
                        {"event_id": "briefing", "kind": "briefing"}
                    ],
                },
                coverage_tags=["trajectory:shock", "attention:elevated"],
                exogenous_events=[
                    {
                        "event_id": "policy_reversal",
                        "kind": "policy_reversal",
                        "timing_window": "mid",
                    }
                ],
                conditional_overrides=[
                    models.ConditionalVariableSpec(
                        variable=models.RandomVariableSpec(
                            field_path="twitter_config.viral_threshold",
                            distribution="fixed",
                            parameters={"value": 6},
                        ),
                        condition_field_path="event_config.narrative_direction",
                        operator="eq",
                        condition_value="crisis",
                    )
                ],
            )
        ],
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-001",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=31,
        experiment_design_row={
            "row_index": 0,
            "normalized_coordinates": {},
            "stratum_indices": {},
            "scenario_template_ids": ["crisis_case"],
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["event_config"]["narrative_direction"] == "crisis"
    assert resolved["twitter_config"]["viral_threshold"] == 6
    assert {
        item["event_id"] for item in resolved["event_config"]["scheduled_events"]
    } == {"briefing", "policy_reversal"}
    assert manifest.assumption_ledger["scenario_coverage_tags"] == [
        "attention:elevated",
        "trajectory:shock",
    ]
    assert manifest.assumption_ledger["applied_exogenous_event_ids"] == [
        "policy_reversal"
    ]
    assert manifest.assumption_ledger["activated_template_conditions"] == [
        "twitter_config.viral_threshold"
    ]


def test_resolver_applies_structural_uncertainty_assignments_and_records_assumptions():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["structural_uncertainty"] = {
        "event_arrival_process": {
            "mode": "steady_cadence",
            "spacing_hours": 6,
        },
        "credibility_shock": {
            "mode": "stable_signal",
            "trust_multiplier": 1.0,
        },
    }

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        structural_uncertainties=[
            models.StructuralUncertaintySpec(
                uncertainty_id="event_arrival_process",
                kind="event_arrival_process",
                label="Event Arrival Process",
                options=[
                    models.StructuralUncertaintyOption(
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
                    models.StructuralUncertaintyOption(
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
            ),
            models.StructuralUncertaintySpec(
                uncertainty_id="credibility_shock",
                kind="credibility_shock",
                label="Credibility Shock",
                options=[
                    models.StructuralUncertaintyOption(
                        option_id="stable_signal",
                        label="Stable Signal",
                        config_overrides={
                            "structural_uncertainty.credibility_shock.mode": "stable_signal",
                            "structural_uncertainty.credibility_shock.trust_multiplier": 1.0,
                        },
                        coverage_tags=["credibility:stable"],
                        runtime_transition_hints=[
                            {
                                "transition_type": "belief_update",
                                "summary": "Credibility remains stable.",
                            }
                        ],
                        assumption_text="Credibility stays stable throughout the run.",
                    ),
                    models.StructuralUncertaintyOption(
                        option_id="trust_drop",
                        label="Trust Drop",
                        config_overrides={
                            "structural_uncertainty.credibility_shock.mode": "trust_drop",
                            "structural_uncertainty.credibility_shock.trust_multiplier": 0.55,
                        },
                        coverage_tags=["credibility:negative"],
                        runtime_transition_hints=[
                            {
                                "transition_type": "belief_update",
                                "summary": "Credibility declines after a shock.",
                            }
                        ],
                        assumption_text="A credibility shock reduces trust in claims.",
                    ),
                ],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            structural_uncertainty_ids=[
                "event_arrival_process",
                "credibility_shock",
            ],
        ),
    )

    resolver = resolver_module.UncertaintyResolver()
    result = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-010",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=12,
        experiment_design_row={
            "row_index": 0,
            "normalized_coordinates": {},
            "stratum_indices": {},
            "structural_assignments": [
                {
                    "uncertainty_id": "event_arrival_process",
                    "option_id": "burst_front_loaded",
                },
                {
                    "uncertainty_id": "credibility_shock",
                    "option_id": "trust_drop",
                },
            ],
        },
    )

    resolved = result["resolved_config"]
    manifest = result["run_manifest"]

    assert resolved["structural_uncertainty"]["event_arrival_process"]["mode"] == (
        "burst_front_loaded"
    )
    assert resolved["structural_uncertainty"]["credibility_shock"]["trust_multiplier"] == (
        0.55
    )
    assert [item["option_id"] for item in manifest.structural_resolutions] == [
        "burst_front_loaded",
        "trust_drop",
    ]
    assert manifest.assumption_ledger["structural_coverage_tags"] == [
        "arrival:burst",
        "credibility:negative",
    ]
    assert manifest.assumption_ledger["structural_runtime_transition_types"] == [
        "belief_update",
        "event",
    ]
    assert manifest.assumption_ledger["assumption_statements"] == [
        "Events cluster early and then decay.",
        "A credibility shock reduces trust in claims.",
    ]
    assert manifest.experiment_design_row["structural_assignments"][0]["option_id"] == (
        "burst_front_loaded"
    )


def test_structural_uncertainty_resolution_is_deterministic_without_design_rows():
    models = _load_models_module()
    resolver_module = _load_resolver_module()

    base_config = _build_base_config()
    base_config["structural_uncertainty"] = {
        "moderation_policy_change": {
            "mode": "status_quo",
            "policy_intensity": 0.0,
        }
    }

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        structural_uncertainties=[
            models.StructuralUncertaintySpec(
                uncertainty_id="moderation_policy_change",
                kind="moderation_policy_change",
                label="Moderation Policy Change",
                options=[
                    models.StructuralUncertaintyOption(
                        option_id="status_quo",
                        label="Status Quo",
                        weight=1.0,
                        config_overrides={
                            "structural_uncertainty.moderation_policy_change.mode": "status_quo",
                            "structural_uncertainty.moderation_policy_change.policy_intensity": 0.0,
                        },
                    ),
                    models.StructuralUncertaintyOption(
                        option_id="tightened_enforcement",
                        label="Tightened Enforcement",
                        weight=2.0,
                        config_overrides={
                            "structural_uncertainty.moderation_policy_change.mode": "tightened_enforcement",
                            "structural_uncertainty.moderation_policy_change.policy_intensity": 0.8,
                        },
                    ),
                ],
            )
        ],
    )

    resolver = resolver_module.UncertaintyResolver()
    first = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-011",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=42,
    )
    second = resolver.resolve_run_config(
        simulation_id="sim-test",
        run_id="run-011",
        base_config=base_config,
        uncertainty_spec=uncertainty_spec,
        resolution_seed=42,
    )

    assert first["resolved_config"] == second["resolved_config"]
    assert first["run_manifest"].structural_resolutions == second["run_manifest"].structural_resolutions
