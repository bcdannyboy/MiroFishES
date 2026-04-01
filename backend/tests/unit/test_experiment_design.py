import importlib


def _load_models_module():
    return importlib.import_module("app.models.probabilistic")


def _load_experiment_design_module():
    return importlib.import_module("app.services.experiment_design")


def test_latin_hypercube_plan_is_deterministic_and_assigns_unique_strata():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

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
        variable_groups=[
            models.VariableGroupSpec(
                group_id="engagement-coupling",
                field_paths=[
                    "agent_configs[0].activity_level",
                    "platform.weights.recency",
                ],
            )
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="base_case",
                label="Base Case",
                field_overrides={},
            ),
            models.ScenarioTemplateSpec(
                template_id="viral_spike",
                label="Viral Spike",
                field_overrides={},
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "agent_configs[0].activity_level",
                "platform.weights.recency",
            ],
            scenario_template_ids=["base_case", "viral_spike"],
            scenario_assignment="cyclic",
        ),
    )

    service = design_module.ExperimentDesignService()
    first = service.build_plan(
        simulation_id="sim-structured",
        ensemble_id="0001",
        run_count=4,
        root_seed=17,
        uncertainty_spec=uncertainty_spec,
    )
    second = service.build_plan(
        simulation_id="sim-structured",
        ensemble_id="0001",
        run_count=4,
        root_seed=17,
        uncertainty_spec=uncertainty_spec,
    )

    assert first == second
    assert first["artifact_type"] == "experiment_design"
    assert first["method"] == "latin-hypercube"
    assert [row["run_id"] for row in first["rows"]] == ["0001", "0002", "0003", "0004"]
    assert [row["scenario_template_ids"] for row in first["rows"]] == [
        ["base_case"],
        ["viral_spike"],
        ["base_case"],
        ["viral_spike"],
    ]
    assert sorted(
        row["stratum_indices"]["agent_configs[0].activity_level"]
        for row in first["rows"]
    ) == [0, 1, 2, 3]
    assert [
        row["normalized_coordinates"]["agent_configs[0].activity_level"]
        for row in first["rows"]
    ] == [
        row["normalized_coordinates"]["platform.weights.recency"]
        for row in first["rows"]
    ]


def test_weighted_cycle_plan_respects_template_weights_while_covering_all_templates():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

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
                template_id="baseline_watch",
                label="Baseline Watch",
                field_overrides={"event_config.narrative_direction": "baseline"},
                weight=3.0,
            ),
            models.ScenarioTemplateSpec(
                template_id="shock_spike",
                label="Shock Spike",
                field_overrides={"event_config.narrative_direction": "shock"},
                weight=1.0,
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=["agent_configs[0].activity_level"],
            scenario_template_ids=["baseline_watch", "shock_spike"],
            scenario_assignment="weighted_cycle",
        ),
    )

    service = design_module.ExperimentDesignService()
    artifact = service.build_plan(
        simulation_id="sim-weighted",
        ensemble_id="0001",
        run_count=8,
        root_seed=23,
        uncertainty_spec=uncertainty_spec,
    )

    assignments = [
        row["scenario_template_ids"][0]
        for row in artifact["rows"]
    ]

    assert assignments.count("baseline_watch") == 6
    assert assignments.count("shock_spike") == 2
    assert sorted(set(assignments)) == ["baseline_watch", "shock_spike"]


def test_experiment_design_reports_diversity_diagnostics_and_support_metrics():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
            models.RandomVariableSpec(
                field_path="twitter_config.echo_chamber_strength",
                distribution="uniform",
                parameters={"low": 0.2, "high": 0.8},
            ),
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="baseline_watch",
                label="Baseline Watch",
                field_overrides={"event_config.narrative_direction": "baseline"},
            ),
            models.ScenarioTemplateSpec(
                template_id="viral_spike",
                label="Viral Spike",
                field_overrides={
                    "event_config.narrative_direction": "viral_spike",
                    "event_config.hot_topics": ["seed", "attention_surge"],
                },
            ),
            models.ScenarioTemplateSpec(
                template_id="cooldown_recovery",
                label="Cooldown Recovery",
                field_overrides={
                    "event_config.narrative_direction": "cooldown",
                    "event_config.scheduled_events": [
                        {
                            "offset_hours": 6,
                            "event_type": "clarification",
                            "topic": "stabilization",
                            "intensity": "medium",
                        }
                    ],
                },
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "agent_configs[0].activity_level",
                "twitter_config.echo_chamber_strength",
            ],
            scenario_template_ids=[
                "baseline_watch",
                "viral_spike",
                "cooldown_recovery",
            ],
            scenario_assignment="cyclic",
        ),
    )

    service = design_module.ExperimentDesignService()
    artifact = service.build_plan(
        simulation_id="sim-diversity",
        ensemble_id="0001",
        run_count=6,
        root_seed=41,
        uncertainty_spec=uncertainty_spec,
    )

    assert artifact["coverage_metrics"] == {
        "numeric_dimension_coverage_ratio": 1.0,
        "numeric_dimension_coverage_ratios": {
            "agent_configs[0].activity_level": 1.0,
            "twitter_config.echo_chamber_strength": 1.0,
        },
        "scenario_template_count": 3,
        "substantive_template_count": 3,
        "substantive_template_ratio": 1.0,
        "template_coverage_ratio": 1.0,
        "template_support_counts": {
            "baseline_watch": 2,
            "cooldown_recovery": 2,
            "viral_spike": 2,
        },
    }
    assert artifact["support_metrics"] == {
        "maximum_template_support_count": 2,
        "minimum_template_support_count": 2,
        "singleton_template_count": 0,
        "template_support_counts": {
            "baseline_watch": 2,
            "cooldown_recovery": 2,
            "viral_spike": 2,
        },
    }
    assert artifact["scenario_distance_metrics"]["distance_metric"] == "hybrid_template_numeric"
    assert artifact["scenario_distance_metrics"]["pair_count"] == 15
    assert artifact["scenario_distance_metrics"]["max_pairwise_distance"] > 0.0
    assert artifact["scenario_distance_metrics"]["mean_pairwise_distance"] > 0.0
    assert artifact["scenario_distance_metrics"]["min_pairwise_distance"] > 0.0
    assert artifact["diversity_warnings"] == []
    assert {
        row["coverage_signature"]["template_count"]
        for row in artifact["rows"]
    } == {1}
    assert {
        row["coverage_signature"]["override_field_count"]
        for row in artifact["rows"]
    } == {1, 2}


def test_pairwise_plan_tracks_diversity_coverage_and_template_metadata():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
            models.RandomVariableSpec(
                field_path="twitter_config.viral_threshold",
                distribution="uniform",
                parameters={"low": 6, "high": 14},
            ),
        ],
        variable_groups=[
            models.VariableGroupSpec(
                group_id="amplification-coupling",
                field_paths=[
                    "agent_configs[0].activity_level",
                    "twitter_config.viral_threshold",
                ],
            )
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="baseline_watch",
                label="Baseline Watch",
                field_overrides={"event_config.narrative_direction": "baseline"},
                coverage_tags=["baseline", "steady-state"],
                exogenous_events=[
                    {
                        "event_id": "baseline-checkpoint",
                        "kind": "operator_note",
                        "hour": 4,
                    }
                ],
                correlated_field_paths=["agent_configs[0].activity_level"],
            ),
            models.ScenarioTemplateSpec(
                template_id="crisis_spike",
                label="Crisis Spike",
                field_overrides={"event_config.narrative_direction": "crisis"},
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
                correlated_field_paths=[
                    "agent_configs[0].activity_level",
                    "twitter_config.viral_threshold",
                ],
                weight=2.0,
            ),
            models.ScenarioTemplateSpec(
                template_id="bridge_response",
                label="Bridge Response",
                field_overrides={"event_config.narrative_direction": "bridge"},
                coverage_tags=["bridge", "response"],
                exogenous_events=[
                    {
                        "event_id": "bridge-briefing",
                        "kind": "community_response",
                        "hour": 5,
                    }
                ],
                correlated_field_paths=["twitter_config.viral_threshold"],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "agent_configs[0].activity_level",
                "twitter_config.viral_threshold",
            ],
            scenario_template_ids=[
                "baseline_watch",
                "crisis_spike",
                "bridge_response",
            ],
            scenario_assignment="weighted_cycle",
            max_templates_per_run=2,
            template_combination_policy="pairwise",
        ),
    )

    service = design_module.ExperimentDesignService()
    first = service.build_plan(
        simulation_id="sim-diverse",
        ensemble_id="0001",
        run_count=6,
        root_seed=31,
        uncertainty_spec=uncertainty_spec,
    )
    second = service.build_plan(
        simulation_id="sim-diverse",
        ensemble_id="0001",
        run_count=6,
        root_seed=31,
        uncertainty_spec=uncertainty_spec,
    )

    assert first == second
    assert first["scenario_diversity_plan"]["max_templates_per_run"] == 2
    assert first["scenario_diversity_plan"]["template_combination_policy"] == "pairwise"
    assert first["scenario_diversity_plan"]["coverage_tag_counts"] == {
        "amplification": 1,
        "baseline": 1,
        "bridge": 1,
        "response": 1,
        "shock": 1,
        "steady-state": 1,
    }
    assert first["scenario_diversity_plan"]["exogenous_event_count"] == 3
    assert first["scenario_diversity_plan"]["conditional_override_count"] == 1
    assert first["scenario_diversity_plan"]["correlated_group_count"] == 1
    assert any(len(row["scenario_template_ids"]) == 2 for row in first["rows"])
    assert first["rows"][0]["scenario_coverage"]["template_count"] == len(
        first["rows"][0]["scenario_template_ids"]
    )
    assert first["rows"][0]["scenario_coverage"]["coverage_tags"]
    assert first["rows"][0]["scenario_coverage"]["exogenous_event_ids"]


def test_weighted_cycle_plan_expands_multi_template_coverage_and_diagnostics():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

    uncertainty_spec = models.UncertaintySpec(
        profile="balanced",
        random_variables=[
            models.RandomVariableSpec(
                field_path="agent_configs[0].activity_level",
                distribution="uniform",
                parameters={"low": 0.1, "high": 0.9},
            ),
            models.RandomVariableSpec(
                field_path="time_config.peak_activity_multiplier",
                distribution="uniform",
                parameters={"low": 1.0, "high": 2.0},
            ),
        ],
        scenario_templates=[
            models.ScenarioTemplateSpec(
                template_id="baseline_watch",
                label="Baseline Watch",
                field_overrides={"event_config.narrative_direction": "baseline"},
                weight=2.0,
                coverage_tags=["baseline", "monitoring"],
            ),
            models.ScenarioTemplateSpec(
                template_id="shock_spike",
                label="Shock Spike",
                field_overrides={"event_config.narrative_direction": "shock"},
                weight=1.0,
                coverage_tags=["shock", "amplification"],
            ),
            models.ScenarioTemplateSpec(
                template_id="consensus_bridge",
                label="Consensus Bridge",
                field_overrides={"event_config.narrative_direction": "consensus"},
                weight=1.0,
                coverage_tags=["bridge", "coordination"],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                "agent_configs[0].activity_level",
                "time_config.peak_activity_multiplier",
            ],
            scenario_template_ids=[
                "baseline_watch",
                "shock_spike",
                "consensus_bridge",
            ],
            scenario_assignment="weighted_cycle",
            max_templates_per_run=2,
            diversity_axes=["scenario_template", "coverage_tags"],
        ),
    )

    service = design_module.ExperimentDesignService()
    artifact = service.build_plan(
        simulation_id="sim-expanded",
        ensemble_id="0001",
        run_count=6,
        root_seed=29,
        uncertainty_spec=uncertainty_spec,
    )

    assert artifact["max_templates_per_run"] == 2
    assert artifact["diversity_axes"] == ["scenario_template", "coverage_tags"]
    assert all(len(row["scenario_template_ids"]) == 2 for row in artifact["rows"])
    assert all(row["scenario_coverage_tags"] for row in artifact["rows"])
    assert all(row["scenario_override_fields"] for row in artifact["rows"])
    assert artifact["coverage_metrics"]["template_coverage_fraction"] == 1.0
    assert artifact["coverage_metrics"]["coverage_tag_fraction"] == 1.0
    assert artifact["coverage_metrics"]["multi_template_row_fraction"] == 1.0
    assert artifact["coverage_metrics"]["observed_template_pair_count"] >= 2


def test_weighted_cycle_plan_surfaces_diversity_plan_and_spreads_template_novelty():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

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
                template_id="baseline_watch",
                label="Baseline Watch",
                field_overrides={"event_config.narrative_direction": "baseline"},
                coverage_tags=["trajectory:baseline", "attention:steady"],
                exogenous_events=[{"event_id": "baseline_watch_checkpoint"}],
                weight=3.0,
            ),
            models.ScenarioTemplateSpec(
                template_id="shock_spike",
                label="Shock Spike",
                field_overrides={"event_config.narrative_direction": "shock"},
                coverage_tags=["trajectory:shock", "attention:surge"],
                exogenous_events=[{"event_id": "shock_spike_alert"}],
                weight=2.0,
            ),
            models.ScenarioTemplateSpec(
                template_id="recovery_lane",
                label="Recovery Lane",
                field_overrides={"event_config.narrative_direction": "cooldown"},
                coverage_tags=["trajectory:recovery", "attention:cooling"],
                exogenous_events=[{"event_id": "recovery_lane_guidance"}],
                weight=1.0,
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=["agent_configs[0].activity_level"],
            scenario_template_ids=["baseline_watch", "shock_spike", "recovery_lane"],
            scenario_assignment="weighted_cycle",
            scenario_coverage_axes=["attention", "trajectory"],
            max_template_reuse_streak=1,
        ),
    )

    service = design_module.ExperimentDesignService()
    artifact = service.build_plan(
        simulation_id="sim-diverse",
        ensemble_id="0001",
        run_count=6,
        root_seed=29,
        uncertainty_spec=uncertainty_spec,
    )

    assignments = [row["scenario_template_ids"][0] for row in artifact["rows"]]

    assert artifact["diversity_plan"]["coverage_axes"] == ["attention", "trajectory"]
    assert artifact["diversity_plan"]["max_template_reuse_streak"] == 1
    assert artifact["diversity_plan"]["template_target_counts"] == {
        "baseline_watch": 3,
        "shock_spike": 2,
        "recovery_lane": 1,
    }
    assert assignments.count("baseline_watch") == 3
    assert assignments.count("shock_spike") == 2
    assert assignments.count("recovery_lane") == 1
    assert all(
        left != right for left, right in zip(assignments, assignments[1:])
    )
    assert artifact["rows"][0]["scenario_coverage_tags"]
    assert artifact["rows"][0]["scenario_event_ids"]
    assert artifact["rows"][1]["scenario_distance_from_previous"] is not None


def test_experiment_design_assigns_structural_uncertainty_options_and_reports_coverage():
    models = _load_models_module()
    design_module = _load_experiment_design_module()

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
                        weight=1.0,
                        coverage_tags=["arrival:steady"],
                        runtime_transition_hints=[
                            {"transition_type": "event", "summary": "steady"}
                        ],
                    ),
                    models.StructuralUncertaintyOption(
                        option_id="burst_front_loaded",
                        label="Burst Front Loaded",
                        weight=1.0,
                        coverage_tags=["arrival:burst"],
                        runtime_transition_hints=[
                            {"transition_type": "event", "summary": "burst"}
                        ],
                    ),
                ],
            ),
            models.StructuralUncertaintySpec(
                uncertainty_id="moderation_policy_change",
                kind="moderation_policy_change",
                label="Moderation Policy Change",
                options=[
                    models.StructuralUncertaintyOption(
                        option_id="status_quo",
                        label="Status Quo",
                        weight=1.0,
                        coverage_tags=["moderation:steady"],
                        runtime_transition_hints=[
                            {"transition_type": "intervention", "summary": "steady"}
                        ],
                    ),
                    models.StructuralUncertaintyOption(
                        option_id="tightened_enforcement",
                        label="Tightened Enforcement",
                        weight=1.0,
                        coverage_tags=["moderation:strict"],
                        runtime_transition_hints=[
                            {"transition_type": "intervention", "summary": "strict"}
                        ],
                    ),
                ],
            ),
        ],
        experiment_design=models.ExperimentDesignSpec(
            method="latin-hypercube",
            structural_uncertainty_ids=[
                "event_arrival_process",
                "moderation_policy_change",
            ],
        ),
    )

    service = design_module.ExperimentDesignService()
    first = service.build_plan(
        simulation_id="sim-structural",
        ensemble_id="0001",
        run_count=4,
        root_seed=13,
        uncertainty_spec=uncertainty_spec,
    )
    second = service.build_plan(
        simulation_id="sim-structural",
        ensemble_id="0001",
        run_count=4,
        root_seed=13,
        uncertainty_spec=uncertainty_spec,
    )

    assert first == second
    assert [item["uncertainty_id"] for item in first["structural_uncertainty_catalog"]] == [
        "event_arrival_process",
        "moderation_policy_change",
    ]
    assert first["coverage_metrics"]["structural_uncertainty_coverage_ratio"] == 1.0
    assert first["coverage_metrics"]["structural_option_coverage_ratios"] == {
        "event_arrival_process": 1.0,
        "moderation_policy_change": 1.0,
    }
    assert first["diversity_plan"]["structural_option_target_counts"] == {
        "event_arrival_process": {
            "burst_front_loaded": 2,
            "steady_cadence": 2,
        },
        "moderation_policy_change": {
            "status_quo": 2,
            "tightened_enforcement": 2,
        },
    }
    assert len(first["rows"][0]["structural_assignments"]) == 2
    assert first["rows"][0]["coverage_signature"]["structural_assignment_count"] == 2
    assert first["rows"][0]["structural_coverage_tags"]
    assert first["rows"][0]["structural_runtime_transition_types"] == [
        "event",
        "intervention",
    ]
