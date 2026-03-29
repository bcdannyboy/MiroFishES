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
    assert manifest.assumption_ledger["activated_conditions"] == [
        "platform.weights.recency"
    ]
    assert manifest.assumption_ledger["design_row"]["normalized_coordinates"][
        "agent_configs[0].activity_level"
    ] == pytest.approx(0.25)
