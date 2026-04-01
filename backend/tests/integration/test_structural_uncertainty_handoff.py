import importlib
import json
from pathlib import Path


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
            path.write_text(
                json.dumps(
                    [profile.to_reddit_format() for profile in profiles],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return

        rows = [profile.to_twitter_format() for profile in profiles]
        header = ",".join(rows[0].keys())
        values = ",".join(str(value) for value in rows[0].values())
        path.write_text(f"{header}\n{values}\n", encoding="utf-8")


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
    reader_module = importlib.import_module("app.services.graph_entity_reader")

    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
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

    monkeypatch.setattr(manager_module, "GraphEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _FakeSimulationConfigGenerator
    )


def test_structural_uncertainty_prepare_and_ensemble_handoff_persists_run_artifacts(
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
            root_seed=23,
        ),
    )

    ensemble_dir = Path(created["path"])
    run_dir = ensemble_dir / "runs" / "run_0001"
    experiment_design = json.loads(
        (ensemble_dir / "experiment_design.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assumption_ledger = json.loads(
        (run_dir / "assumption_ledger.json").read_text(encoding="utf-8")
    )

    assert experiment_design["structural_uncertainty_catalog"]
    assert (
        experiment_design["coverage_metrics"]["structural_uncertainty_coverage_ratio"]
        == 1.0
    )
    assert manifest["artifact_paths"]["experiment_design_row"] == "experiment_design_row.json"
    assert manifest["artifact_paths"]["assumption_ledger"] == "assumption_ledger.json"
    assert manifest["structural_resolutions"]
    assert assumption_ledger["assumption_ledger"]["structural_uncertainties"]
    assert assumption_ledger["assumption_ledger"]["assumption_statements"]
