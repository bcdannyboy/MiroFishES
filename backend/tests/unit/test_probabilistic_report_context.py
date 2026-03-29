import csv
import importlib
import json
from pathlib import Path


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_ensemble_module():
    return importlib.import_module("app.services.ensemble_manager")


def _load_context_module():
    return importlib.import_module("app.services.probabilistic_report_context")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
        pass

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
                "agents_per_hour_min": 1,
                "agents_per_hour_max": 3,
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
                "recency_weight": 0.4,
                "popularity_weight": 0.3,
                "relevance_weight": 0.3,
                "viral_threshold": 10,
                "echo_chamber_strength": 0.5,
            },
            "reddit_config": {
                "platform": "reddit",
                "recency_weight": 0.4,
                "popularity_weight": 0.3,
                "relevance_weight": 0.3,
                "viral_threshold": 10,
                "echo_chamber_strength": 0.5,
            },
            "generated_at": "2026-03-09T10:00:00",
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


def _install_prepare_stubs(monkeypatch, manager_module):
    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module,
        "SimulationConfigGenerator",
        _FakeSimulationConfigGenerator,
    )


def _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch):
    manager_module = _load_manager_module()
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
        outcome_metrics=["simulation.total_actions", "platform.twitter.total_actions"],
    )
    return state


def _write_run_metrics(run_dir: Path, *, total_actions: int, twitter_actions: int, status="complete"):
    _write_json(
        run_dir / "metrics.json",
        {
            "artifact_type": "run_metrics",
            "schema_version": "probabilistic.metrics.v1",
            "generator_version": "probabilistic.metrics.generator.v1",
            "quality_checks": {
                "status": status,
                "run_status": "completed",
                "warnings": ["thin_sample"] if status != "complete" else [],
            },
            "metric_values": {
                "simulation.total_actions": {
                    "metric_id": "simulation.total_actions",
                    "label": "Simulation Total Actions",
                    "aggregation": "count",
                    "unit": "count",
                    "probability_mode": "empirical",
                    "value": total_actions,
                },
                "platform.twitter.total_actions": {
                    "metric_id": "platform.twitter.total_actions",
                    "label": "Twitter Total Actions",
                    "aggregation": "count",
                    "unit": "count",
                    "probability_mode": "empirical",
                    "value": twitter_actions,
                },
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "label": "Simulation Completed",
                    "aggregation": "flag",
                    "unit": "boolean",
                    "probability_mode": "empirical",
                    "value": status == "complete",
                },
                "platform.leading_platform": {
                    "metric_id": "platform.leading_platform",
                    "label": "Leading Platform",
                    "aggregation": "category",
                    "unit": "category",
                    "probability_mode": "empirical",
                    "value": "twitter" if twitter_actions >= max(total_actions - twitter_actions, 0) else "reddit",
                },
            },
            "top_topics": [
                {
                    "topic": "seed",
                    "count": total_actions,
                }
            ],
            "extracted_at": f"2026-03-09T10:00:{total_actions:02d}",
        },
    )


def _create_probabilistic_ensemble(simulation_data_dir, monkeypatch, simulation_id: str):
    ensemble_module = _load_ensemble_module()
    monkeypatch.setattr(
        ensemble_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(simulation_data_dir),
        raising=False,
    )

    manager = ensemble_module.EnsembleManager(simulation_data_dir=str(simulation_data_dir))
    created = manager.create_ensemble(
        simulation_id,
        {
            "run_count": 3,
            "max_concurrency": 1,
            "root_seed": 17,
            "sampling_mode": "seeded",
        },
    )

    run_payloads = {
        "0001": {"driver": 0.1, "total": 4, "twitter": 2, "status": "complete"},
        "0002": {"driver": 0.2, "total": 6, "twitter": 3, "status": "complete"},
        "0003": {"driver": 0.9, "total": 14, "twitter": 11, "status": "partial"},
    }

    for run_id, payload in run_payloads.items():
        run_dir = (
            Path(simulation_data_dir)
            / simulation_id
            / "ensemble"
            / f"ensemble_{created['ensemble_id']}"
            / "runs"
            / f"run_{run_id}"
        )
        manifest_path = run_dir / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "completed"
        manifest["resolved_values"] = {
            "twitter_config.echo_chamber_strength": payload["driver"]
        }
        manifest["generated_at"] = f"2026-03-09T09:00:{run_id[-1]}"
        _write_json(manifest_path, manifest)
        _write_json(
            run_dir / "resolved_config.json",
            {
                "artifact_type": "resolved_config",
                "simulation_id": simulation_id,
                "ensemble_id": created["ensemble_id"],
                "run_id": run_id,
                "sampled_values": manifest["resolved_values"],
            },
        )
        _write_run_metrics(
            run_dir,
            total_actions=payload["total"],
            twitter_actions=payload["twitter"],
            status=payload["status"],
        )

    return created


def test_build_context_assembles_prepare_run_and_empirical_analytics(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    context_module = _load_context_module()

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        run_id="0001",
    )

    assert artifact["artifact_type"] == "probabilistic_report_context"
    assert artifact["simulation_id"] == state.simulation_id
    assert artifact["ensemble_id"] == created["ensemble_id"]
    assert artifact["run_id"] == "0001"
    assert artifact["probability_semantics"]["summary"] == "empirical"
    assert artifact["probability_semantics"]["sensitivity"] == "observational"
    assert artifact["prepared_artifact_summary"]["probabilistic_mode"] is True
    assert artifact["selected_run"]["run_id"] == "0001"
    assert (
        artifact["selected_run"]["resolved_values"]["twitter_config.echo_chamber_strength"]
        == 0.1
    )
    assert (
        artifact["aggregate_summary"]["metric_summaries"]["simulation.total_actions"]["sample_count"]
        == 3
    )
    assert artifact["top_outcomes"][0]["metric_id"] == "simulation.total_actions"
    assert artifact["top_outcomes"][0]["value_summary"]["mean"] == 8.0
    assert artifact["selected_run"]["key_metrics"][0]["metric_id"] == "simulation.total_actions"
    assert any(
        item["metric_id"] == "platform.leading_platform" and item["value"] == "twitter"
        for item in artifact["selected_run"]["key_metrics"]
    )
    assert artifact["scenario_clusters"]["artifact_type"] == "scenario_clusters"
    assert artifact["sensitivity"]["artifact_type"] == "sensitivity"
    assert artifact["sensitivity"]["driver_rankings"][0]["driver_id"] == (
        "twitter_config.echo_chamber_strength"
    )
    assert "observational_only" in artifact["sensitivity"]["quality_summary"]["warnings"]


def test_build_context_allows_ensemble_scope_without_selected_run(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    context_module = _load_context_module()

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["scope"]["level"] == "ensemble"
    assert artifact["selected_run"] is None
    assert artifact["aggregate_summary"]["artifact_type"] == "aggregate_summary"
    assert any(
        outcome["metric_id"] == "simulation.completed"
        and outcome["value_summary"]["empirical_probability"] == 2 / 3
        for outcome in artifact["top_outcomes"]
    )
