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
