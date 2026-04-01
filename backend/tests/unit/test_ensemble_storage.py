import csv
import importlib
import json
from pathlib import Path

import pytest


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_ensemble_module():
    return importlib.import_module("app.services.ensemble_manager")


def _load_probabilistic_module():
    return importlib.import_module("app.models.probabilistic")


def _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module=None):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )
    if manager_module is not None:
        monkeypatch.setattr(
            manager_module.SimulationManager,
            "SIMULATION_DATA_DIR",
            str(simulation_data_dir),
        )


def _fake_filtered_entities():
    reader_module = importlib.import_module("app.services.zep_entity_reader")
    return reader_module.FilteredEntities(
        entities=[
            reader_module.EntityNode(
                uuid="entity-1",
                name="Analyst",
                labels=["Entity", "Person"],
                summary="A tracked participant",
                attributes={"role": "analyst"},
            )
        ],
        entity_types={"Person"},
        total_count=1,
        filtered_count=1,
    )


class _FakeProfile:
    def __init__(self, user_id, user_name):
        self.user_id = user_id
        self.user_name = user_name

    def to_reddit_format(self):
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.user_name.title(),
            "bio": "Synthetic profile",
            "persona": "Helpful analyst",
        }

    def to_twitter_format(self):
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.user_name.title(),
            "bio": "Synthetic profile",
            "persona": "Helpful analyst",
        }


class _FakeProfileGenerator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def generate_profiles_from_entities(self, *args, **kwargs):
        return [_FakeProfile(1, "agent_one")]

    def save_profiles(self, profiles, file_path, platform):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if platform == "reddit":
            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    [profile.to_reddit_format() for profile in profiles],
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
            return

        rows = [profile.to_twitter_format() for profile in profiles]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


class _FakeSimulationParameters:
    def __init__(self, simulation_id, project_id, graph_id, simulation_requirement):
        self.generation_reasoning = "Test reasoning"
        self.payload = {
            "simulation_id": simulation_id,
            "project_id": project_id,
            "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "time_config": {
                "total_simulation_hours": 24,
                "minutes_per_round": 60,
            },
            "agent_configs": [
                {
                    "agent_id": 0,
                    "entity_uuid": "entity-1",
                    "entity_name": "Analyst",
                    "entity_type": "Person",
                    "activity_level": 0.5,
                    "posts_per_hour": 1.0,
                    "comments_per_hour": 1.0,
                    "active_hours": [8, 9, 10],
                    "response_delay_min": 5,
                    "response_delay_max": 15,
                    "sentiment_bias": 0.0,
                    "stance": "neutral",
                    "influence_weight": 1.0,
                }
            ],
            "event_config": {
                "initial_posts": [],
                "scheduled_events": [],
                "hot_topics": ["seed"],
                "narrative_direction": "neutral",
            },
            "twitter_config": {
                "platform": "twitter",
                "echo_chamber_strength": 0.5,
            },
            "reddit_config": {
                "platform": "reddit",
                "echo_chamber_strength": 0.5,
            },
            "generated_at": "2026-03-08T12:00:00",
            "generation_reasoning": "Test reasoning",
        }

    def to_dict(self):
        return json.loads(json.dumps(self.payload))


class _FakeSimulationConfigGenerator:
    def generate_config(self, **kwargs):
        return _FakeSimulationParameters(
            simulation_id=kwargs["simulation_id"],
            project_id=kwargs["project_id"],
            graph_id=kwargs["graph_id"],
            simulation_requirement=kwargs["simulation_requirement"],
        )


def _install_prepare_stubs(monkeypatch, manager_module):
    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "GraphEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _FakeSimulationConfigGenerator
    )


def _prepare_simulation(manager, simulation_id, probabilistic_mode):
    return manager.prepare_simulation(
        simulation_id=simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=probabilistic_mode,
        uncertainty_profile="balanced" if probabilistic_mode else None,
        outcome_metrics=["simulation.total_actions"] if probabilistic_mode else None,
    )


def test_create_ensemble_persists_storage_layout(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=2,
            max_concurrency=1,
            root_seed=11,
        ),
    )

    ensemble_dir = Path(created["path"])
    run_dirs = sorted((ensemble_dir / "runs").iterdir())

    assert (ensemble_dir / "ensemble_spec.json").exists()
    assert (ensemble_dir / "ensemble_state.json").exists()
    assert [path.name for path in run_dirs] == ["run_0001", "run_0002"]
    assert (run_dirs[0] / "run_manifest.json").exists()
    assert (run_dirs[0] / "resolved_config.json").exists()

    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))
    resolved_config = json.loads(
        (run_dirs[0] / "resolved_config.json").read_text(encoding="utf-8")
    )

    assert manifest["simulation_id"] == state.simulation_id
    assert manifest["run_id"] == "0001"
    assert manifest["seed_metadata"]["resolution_seed"] == 11
    assert resolved_config["simulation_id"] == state.simulation_id

    runs = ensemble_manager.list_runs(state.simulation_id, created["ensemble_id"])
    loaded = ensemble_manager.load_ensemble(state.simulation_id, created["ensemble_id"])

    assert [run["run_id"] for run in runs] == ["0001", "0002"]
    assert loaded["state"]["source_artifacts"]["base_config"] == "simulation_config.base.json"
    assert loaded["state"]["prepared_run_count"] == 2


def test_create_ensemble_persists_effective_seed_and_run_artifact_metadata(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=1,
            max_concurrency=1,
            root_seed=None,
        ),
    )

    ensemble_dir = Path(created["path"])
    persisted_spec = json.loads(
        (ensemble_dir / "ensemble_spec.json").read_text(encoding="utf-8")
    )
    loaded_run = ensemble_manager.load_run(
        state.simulation_id,
        f"ensemble_{created['ensemble_id']}",
        "run_0001",
    )
    manifest = loaded_run["run_manifest"]
    resolved_config = loaded_run["resolved_config"]

    assert persisted_spec["root_seed"] == 0
    assert persisted_spec["requested_root_seed"] is None
    assert persisted_spec["artifact_type"] == "ensemble_spec"
    assert persisted_spec["created_at"]
    assert persisted_spec["source_simulation_id"] == state.simulation_id

    assert manifest["simulation_id"] == state.simulation_id
    assert manifest["ensemble_id"] == created["ensemble_id"]
    assert manifest["run_id"] == "0001"
    assert manifest["generated_at"]
    assert manifest["artifact_paths"]["resolved_config"] == "resolved_config.json"

    assert resolved_config["simulation_id"] == state.simulation_id
    assert resolved_config["ensemble_id"] == created["ensemble_id"]
    assert resolved_config["run_id"] == "0001"
    assert resolved_config["root_seed"] == 0
    assert resolved_config["sample_seed"] == 0
    assert resolved_config["sampled_values"] == manifest["resolved_values"]
    assert resolved_config["resolved_at"]


def test_create_ensemble_resolves_distinct_run_configs_for_balanced_profile(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=2,
            max_concurrency=1,
            root_seed=11,
        ),
    )

    run_one = ensemble_manager.load_run(state.simulation_id, created["ensemble_id"], "0001")
    run_two = ensemble_manager.load_run(state.simulation_id, created["ensemble_id"], "0002")

    assert run_one["run_manifest"]["resolved_values"]
    assert run_two["run_manifest"]["resolved_values"]
    assert run_one["run_manifest"]["resolved_values"] != run_two["run_manifest"]["resolved_values"]
    assert run_one["resolved_config"]["sampled_values"] == run_one["run_manifest"]["resolved_values"]
    assert run_two["resolved_config"]["sampled_values"] == run_two["run_manifest"]["resolved_values"]


def test_create_ensemble_persists_experiment_design_and_assumption_ledgers(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=True,
        uncertainty_profile="balanced",
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 4, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": ["base_case", "viral_spike"],
        },
    )

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=4,
            max_concurrency=1,
            root_seed=11,
        ),
    )

    ensemble_dir = Path(created["path"])
    experiment_design = json.loads(
        (ensemble_dir / "experiment_design.json").read_text(encoding="utf-8")
    )
    run_one = ensemble_manager.load_run(state.simulation_id, created["ensemble_id"], "0001")
    run_two = ensemble_manager.load_run(state.simulation_id, created["ensemble_id"], "0002")

    assert experiment_design["artifact_type"] == "experiment_design"
    assert experiment_design["method"] == "latin-hypercube"
    assert experiment_design["rows"][0]["run_id"] == "0001"
    assert created["state"]["source_artifacts"]["experiment_design"] == "experiment_design.json"
    assert run_one["run_manifest"]["assumption_ledger"]["design_method"] == "latin-hypercube"
    assert run_one["run_manifest"]["assumption_ledger"]["design_row"]["row_index"] == 0
    assert run_one["resolved_config"]["assumption_ledger"] == run_one["run_manifest"]["assumption_ledger"]
    assert run_one["run_manifest"]["assumption_ledger"]["scenario_template_ids"] == ["base_case"]
    assert run_two["run_manifest"]["assumption_ledger"]["scenario_template_ids"] == ["viral_spike"]
    assert run_one["run_manifest"]["assumption_ledger"]["applied_templates"] == ["base_case"]
    assert run_two["run_manifest"]["assumption_ledger"]["applied_templates"] == ["viral_spike"]
    assert run_one["run_manifest"]["assumption_ledger"]["scenario_override_fields"] == [
        "event_config.narrative_direction"
    ]
    assert run_two["run_manifest"]["assumption_ledger"]["scenario_override_fields"] == [
        "agent_configs[0].activity_level",
        "agent_configs[0].comments_per_hour",
        "agent_configs[0].influence_weight",
        "agent_configs[0].posts_per_hour",
        "event_config.narrative_direction",
        "reddit_config.echo_chamber_strength",
        "twitter_config.echo_chamber_strength",
    ]
    assert run_one["resolved_config"]["event_config"]["narrative_direction"] == "baseline"
    assert run_two["resolved_config"]["event_config"]["narrative_direction"] == "viral_spike"
    assert run_two["resolved_config"]["twitter_config"]["echo_chamber_strength"] == 0.8
    assert run_two["resolved_config"]["reddit_config"]["echo_chamber_strength"] == 0.75
    assert run_one["resolved_config"]["event_config"]["narrative_direction"] != (
        run_two["resolved_config"]["event_config"]["narrative_direction"]
    )


def test_create_ensemble_persists_run_level_structural_handoff_artifacts(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=True,
        uncertainty_profile="balanced",
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 4, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": ["base_case", "viral_spike", "consensus_bridge"],
        },
    )

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=4,
            max_concurrency=1,
            root_seed=17,
        ),
    )

    run_dir = Path(created["path"]) / "runs" / "run_0001"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    resolved_config = json.loads(
        (run_dir / "resolved_config.json").read_text(encoding="utf-8")
    )
    experiment_design_row = json.loads(
        (run_dir / "experiment_design_row.json").read_text(encoding="utf-8")
    )
    assumption_ledger = json.loads(
        (run_dir / "assumption_ledger.json").read_text(encoding="utf-8")
    )

    assert manifest["artifact_paths"]["experiment_design_row"] == "experiment_design_row.json"
    assert manifest["artifact_paths"]["assumption_ledger"] == "assumption_ledger.json"
    assert manifest["structural_resolutions"]
    assert manifest["experiment_design_row"]["structural_assignments"]
    assert experiment_design_row["artifact_type"] == "run_experiment_design"
    assert experiment_design_row["structural_assignments"] == manifest["experiment_design_row"][
        "structural_assignments"
    ]
    assert assumption_ledger["artifact_type"] == "assumption_ledger"
    assert assumption_ledger["assumption_ledger"]["structural_uncertainties"]
    assert assumption_ledger["assumption_ledger"]["assumption_statements"]
    assert resolved_config["structural_resolutions"] == manifest["structural_resolutions"]


def test_load_helpers_normalize_prefixed_public_ids(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=1,
            max_concurrency=1,
            root_seed=7,
        ),
    )

    loaded_ensemble = ensemble_manager.load_ensemble(
        state.simulation_id,
        f"ensemble_{created['ensemble_id']}",
    )
    loaded_run = ensemble_manager.load_run(
        state.simulation_id,
        f"ensemble_{created['ensemble_id']}",
        "run_0001",
    )

    assert loaded_ensemble["ensemble_id"] == created["ensemble_id"]
    assert loaded_run["ensemble_id"] == created["ensemble_id"]
    assert loaded_run["run_id"] == "0001"


def test_create_ensemble_preserves_unseeded_sampling_metadata(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=1,
            max_concurrency=1,
            root_seed=19,
            sampling_mode="unseeded",
        ),
    )

    loaded_run = ensemble_manager.load_run(
        state.simulation_id,
        created["ensemble_id"],
        "0001",
    )

    assert loaded_run["run_manifest"]["seed_metadata"]["root_seed"] == 19
    assert loaded_run["run_manifest"]["seed_metadata"]["resolution_seed"] is None
    assert loaded_run["resolved_config"]["sample_seed"] is None


def test_create_ensemble_rejects_legacy_prepare_inputs(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=False)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    with pytest.raises(ValueError, match="probabilistic prepare artifacts"):
        ensemble_manager.create_ensemble(
            simulation_id=state.simulation_id,
            ensemble_spec=probabilistic_module.EnsembleSpec(
                run_count=2,
                max_concurrency=1,
                root_seed=3,
            ),
        )


def test_delete_run_preserves_sibling_artifacts(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    probabilistic_module = _load_probabilistic_module()

    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    _prepare_simulation(manager, state.simulation_id, probabilistic_mode=True)

    ensemble_module = _load_ensemble_module()
    ensemble_manager = ensemble_module.EnsembleManager(
        simulation_data_dir=str(simulation_data_dir)
    )

    created = ensemble_manager.create_ensemble(
        simulation_id=state.simulation_id,
        ensemble_spec=probabilistic_module.EnsembleSpec(
            run_count=2,
            max_concurrency=1,
            root_seed=5,
        ),
    )

    deleted = ensemble_manager.delete_run(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        run_id="0001",
    )

    assert deleted is True
    remaining_runs = ensemble_manager.list_runs(
        state.simulation_id, created["ensemble_id"]
    )
    assert [run["run_id"] for run in remaining_runs] == ["0002"]

    remaining_dir = Path(created["path"]) / "runs" / "run_0002"
    deleted_dir = Path(created["path"]) / "runs" / "run_0001"
    assert remaining_dir.exists()
    assert not deleted_dir.exists()
