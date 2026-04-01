import csv
import importlib
import json
from pathlib import Path

from flask import Flask
import pytest


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_simulation_api_module():
    return importlib.import_module("app.api.simulation")


def _load_probabilistic_module():
    return importlib.import_module("app.models.probabilistic")


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


def _configure_project_grounding_dir(monkeypatch, project_root: Path):
    project_module = importlib.import_module("app.models.project")
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(project_root),
        raising=False,
    )
    return project_module


def _write_project_grounding_artifacts(
    monkeypatch,
    project_root: Path,
    *,
    project_id: str,
    graph_id: str = "graph-1",
):
    _configure_project_grounding_dir(monkeypatch, project_root)
    project_dir = project_root / project_id
    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-29T09:00:00",
            "simulation_requirement": "Forecast discussion spread",
            "boundary_note": "Uploaded project sources only; this artifact does not claim live-web coverage.",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "memo.md",
                    "saved_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "size_bytes": 10,
                    "sha256": "abc123",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 42,
                    "combined_text_start": 0,
                    "combined_text_end": 42,
                    "parser_warnings": [],
                    "excerpt": "Workers mention slowdown risk and policy response.",
                }
            ],
        },
    )
    _write_json(
        project_dir / "source_units.json",
        {
            "artifact_type": "source_units",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "generated_at": "2026-03-29T09:02:00",
            "unit_count": 2,
            "units": [
                {
                    "unit_id": "su-1",
                    "source_id": "src-1",
                    "stable_source_id": "memo-md",
                    "original_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "source_order": 1,
                    "unit_order": 1,
                    "unit_type": "paragraph",
                    "char_start": 0,
                    "char_end": 42,
                    "combined_text_start": 0,
                    "combined_text_end": 42,
                    "text": "Workers mention slowdown risk and policy response.",
                    "metadata": {"heading_path": ["Economic outlook"]},
                    "extraction_warnings": [],
                },
                {
                    "unit_id": "su-2",
                    "source_id": "src-1",
                    "stable_source_id": "memo-md",
                    "original_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "source_order": 1,
                    "unit_order": 2,
                    "unit_type": "paragraph",
                    "char_start": 43,
                    "char_end": 88,
                    "combined_text_start": 43,
                    "combined_text_end": 88,
                    "text": "Inflation revisions could delay policy easing.",
                    "metadata": {"heading_path": ["Risks"]},
                    "extraction_warnings": [],
                },
            ],
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {
                "source_manifest": "source_manifest.json",
                "source_units": "source_units.json",
            },
            "ontology_summary": {
                "analysis_summary": "Uploaded evidence emphasizes labor-policy timing.",
                "entity_type_count": 1,
                "edge_type_count": 1,
            },
            "chunk_size": 300,
            "chunk_overlap": 40,
            "chunk_count": 2,
            "graph_counts": {
                "node_count": 7,
                "edge_count": 9,
                "entity_types": ["Person", "Topic", "Claim", "UncertaintyFactor"],
            },
            "warnings": [],
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": "2026-03-29T09:06:00",
            "total_count": 1,
            "filtered_count": 1,
            "entity_types": ["Person"],
            "analytical_object_count": 3,
            "analytical_types": ["Claim", "Topic", "UncertaintyFactor"],
            "entities": [
                {
                    "uuid": "entity-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "A tracked participant",
                    "attributes": {"role": "analyst"},
                    "related_edges": [
                        {
                            "direction": "outgoing",
                            "edge_name": "tracks",
                            "fact": "Analyst tracks labor slowdown.",
                            "target_node_uuid": "topic-1",
                            "provenance": {
                                "source_unit_ids": ["su-1"],
                                "citations": [
                                    {
                                        "unit_id": "su-1",
                                        "source_id": "src-1",
                                        "stable_source_id": "memo-md",
                                        "original_filename": "memo.md",
                                        "relative_path": "files/memo.md",
                                        "unit_type": "paragraph",
                                        "char_start": 0,
                                        "char_end": 42,
                                        "combined_text_start": 0,
                                        "combined_text_end": 42,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "topic-1",
                            "name": "Labor slowdown",
                            "labels": ["Entity", "Topic"],
                            "summary": "Labor conditions are softening.",
                        },
                        {
                            "uuid": "claim-1",
                            "name": "Policy easing likely",
                            "labels": ["Entity", "Claim"],
                            "summary": "Softening labor data supports policy easing.",
                        },
                    ],
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "memo-md",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 42,
                                "combined_text_start": 0,
                                "combined_text_end": 42,
                            }
                        ],
                    },
                }
            ],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Labor slowdown",
                    "labels": ["Entity", "Topic"],
                    "summary": "Labor conditions are softening.",
                    "object_type": "Topic",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "memo-md",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 42,
                                "combined_text_start": 0,
                                "combined_text_end": 42,
                            }
                        ],
                    },
                    "related_edges": [],
                    "related_nodes": [
                        {
                            "uuid": "entity-1",
                            "name": "Analyst",
                            "labels": ["Entity", "Person"],
                            "summary": "A tracked participant",
                        }
                    ],
                },
                {
                    "uuid": "claim-1",
                    "name": "Policy easing likely",
                    "labels": ["Entity", "Claim"],
                    "summary": "Softening labor data supports policy easing.",
                    "object_type": "Claim",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "memo-md",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 42,
                                "combined_text_start": 0,
                                "combined_text_end": 42,
                            }
                        ],
                    },
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "supports",
                            "fact": "Workers mention slowdown risk and policy response.",
                            "source_node_uuid": "topic-1",
                            "provenance": {
                                "source_unit_ids": ["su-1"],
                                "citations": [
                                    {
                                        "unit_id": "su-1",
                                        "source_id": "src-1",
                                        "stable_source_id": "memo-md",
                                        "original_filename": "memo.md",
                                        "relative_path": "files/memo.md",
                                        "unit_type": "paragraph",
                                        "char_start": 0,
                                        "char_end": 42,
                                        "combined_text_start": 0,
                                        "combined_text_end": 42,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "entity-1",
                            "name": "Analyst",
                            "labels": ["Entity", "Person"],
                            "summary": "A tracked participant",
                        }
                    ],
                },
                {
                    "uuid": "unc-1",
                    "name": "Inflation revision risk",
                    "labels": ["Entity", "UncertaintyFactor"],
                    "summary": "Inflation revisions could delay easing.",
                    "object_type": "UncertaintyFactor",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-2"],
                        "citations": [
                            {
                                "unit_id": "su-2",
                                "source_id": "src-1",
                                "stable_source_id": "memo-md",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "char_start": 43,
                                "char_end": 88,
                                "combined_text_start": 43,
                                "combined_text_end": 88,
                            }
                        ],
                    },
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "contradicts",
                            "fact": "Inflation revisions could delay policy easing.",
                            "source_node_uuid": "claim-1",
                            "provenance": {
                                "source_unit_ids": ["su-2"],
                                "citations": [
                                    {
                                        "unit_id": "su-2",
                                        "source_id": "src-1",
                                        "stable_source_id": "memo-md",
                                        "original_filename": "memo.md",
                                        "relative_path": "files/memo.md",
                                        "unit_type": "paragraph",
                                        "char_start": 43,
                                        "char_end": 88,
                                        "combined_text_start": 43,
                                        "combined_text_end": 88,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "entity-1",
                            "name": "Analyst",
                            "labels": ["Entity", "Person"],
                            "summary": "A tracked participant",
                        }
                    ],
                },
            ],
            "citation_coverage": {
                "source_unit_backed_node_count": 4,
                "source_unit_backed_edge_count": 2,
                "edge_episode_link_count": 0,
            },
        },
    )


def _build_test_client(simulation_module):
    app = Flask(__name__)
    app.register_blueprint(simulation_module.simulation_bp, url_prefix="/api/simulation")
    return app.test_client()


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
                json.dump([profile.to_reddit_format() for profile in profiles], handle, ensure_ascii=False, indent=2)
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
            "generated_at": "2026-03-08T12:00:00",
            "generation_reasoning": "Test reasoning",
        }

    def to_json(self, indent=2):
        return json.dumps(self.payload, ensure_ascii=False, indent=indent)

    def to_dict(self):
        return json.loads(json.dumps(self.payload))


class _FakeSimulationConfigGenerator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def generate_config(self, **kwargs):
        return _FakeSimulationParameters(
            simulation_id=kwargs["simulation_id"],
            project_id=kwargs["project_id"],
            graph_id=kwargs["graph_id"],
            simulation_requirement=kwargs["simulation_requirement"],
        )


class _FakeThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        if self.target:
            self.target()


def _install_prepare_stubs(monkeypatch, manager_module):
    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _FakeSimulationConfigGenerator
    )


def test_prepare_simulation_keeps_legacy_artifacts_when_probabilistic_mode_is_false(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")

    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=False,
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    assert (sim_dir / "simulation_config.json").exists()
    assert not (sim_dir / "simulation_config.base.json").exists()
    assert not (sim_dir / "uncertainty_spec.json").exists()
    assert not (sim_dir / "outcome_spec.json").exists()
    assert not (sim_dir / "prepared_snapshot.json").exists()
    assert not (sim_dir / "prepare_phase_timings.json").exists()


def test_prepare_simulation_persists_probabilistic_sidecar_artifacts(
    simulation_data_dir, probabilistic_domain, monkeypatch
):
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
        outcome_metrics=[
            "simulation.total_actions",
            "platform.twitter.total_actions",
        ],
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads((sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8"))
    outcome_spec = json.loads((sim_dir / "outcome_spec.json").read_text(encoding="utf-8"))
    prepared_snapshot = json.loads((sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8"))
    phase_timings = json.loads((sim_dir / "prepare_phase_timings.json").read_text(encoding="utf-8"))
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    assert (sim_dir / "simulation_config.json").exists()
    assert (sim_dir / "simulation_config.base.json").exists()
    assert not (sim_dir / "forecast_brief.json").exists()
    assert uncertainty_spec["schema_version"] == "probabilistic.prepare.v1"
    assert uncertainty_spec["generator_version"] == "probabilistic.prepare.generator.v1"
    assert uncertainty_spec["profile"] == "balanced"
    assert uncertainty_spec["seed_policy"]["strategy"] == probabilistic_domain["seed_policy"]["strategy"]
    field_paths = {
        item["field_path"] for item in uncertainty_spec["random_variables"]
    }
    non_fixed_variables = [
        item for item in uncertainty_spec["random_variables"]
        if item["distribution"] != "fixed"
    ]
    assert field_paths
    assert "agent_configs[0].activity_level" in field_paths
    assert "twitter_config.echo_chamber_strength" in field_paths
    assert non_fixed_variables
    assert outcome_spec["artifact_type"] == "outcome_spec"
    assert outcome_spec["generator_version"] == "probabilistic.prepare.generator.v1"
    assert [item["metric_id"] for item in outcome_spec["metrics"]] == [
        "simulation.total_actions",
        "platform.twitter.total_actions",
    ]
    assert prepared_snapshot["artifact_type"] == "prepared_snapshot"
    assert prepared_snapshot["generator_version"] == "probabilistic.prepare.generator.v1"
    assert prepared_snapshot["mode"] == "probabilistic"
    assert prepared_snapshot["lineage"]["project_id"] == "proj-1"
    assert prepared_snapshot["lineage"]["graph_id"] == "graph-1"
    assert prepared_snapshot["lineage"]["config"]["legacy_config"] == "simulation_config.json"
    assert prepared_snapshot["artifacts"]["base_config"]["filename"] == "simulation_config.base.json"
    assert prepared_snapshot["artifacts"]["grounding_bundle"]["filename"] == "grounding_bundle.json"
    assert prepared_snapshot["grounding_summary"]["status"] == "unavailable"
    assert phase_timings["artifact_type"] == "phase_timings"
    assert set(phase_timings["phases"]) == {
        "config_generation",
        "entity_read",
        "profile_generation",
        "world_state",
    }
    assert summary["schema_version"] == "probabilistic.prepare.v1"
    assert summary["generator_version"] == "probabilistic.prepare.generator.v1"
    assert summary["lineage"]["project_id"] == "proj-1"
    assert summary["artifacts"]["base_config"]["path"].endswith("simulation_config.base.json")
    assert summary["artifacts"]["prepare_phase_timings"]["exists"] is True
    assert summary["artifacts"]["prepare_phase_timings"]["filename"] == "prepare_phase_timings.json"
    assert summary["artifacts"]["forecast_brief"]["filename"] == "forecast_brief.json"
    assert summary["artifacts"]["forecast_brief"]["exists"] is False
    assert summary["forecast_brief"] is None
    assert summary["artifacts"]["grounding_bundle"]["filename"] == "grounding_bundle.json"
    assert summary["artifacts"]["grounding_bundle"]["exists"] is True
    assert summary["grounding_summary"]["status"] == "unavailable"
    assert summary["artifact_completeness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "missing_artifacts": [],
    }
    assert summary["grounding_readiness"] == {
        "ready": False,
        "status": "unavailable",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
    }
    assert summary["forecast_readiness"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
    }
    assert summary["workflow_handoff_status"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
        "semantics": "workflow_handoff_status",
    }
    assert summary["artifacts"]["uncertainty_spec"]["schema_version"] == "probabilistic.prepare.v1"
    assert summary["feature_metadata"]["random_variable_count"] == len(
        uncertainty_spec["random_variables"]
    )
    assert summary["feature_metadata"]["non_fixed_random_variable_count"] == len(
        non_fixed_variables
    )
    assert summary["feature_metadata"]["sampling_enabled"] is True


def test_prepare_simulation_uses_project_entity_index_before_remote_reads(
    simulation_data_dir, monkeypatch, tmp_path
):
    manager_module = _load_manager_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)
    _write_project_grounding_artifacts(
        monkeypatch,
        tmp_path / "projects",
        project_id="proj-1",
        graph_id="graph-1",
    )

    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(config_module.Config, "ZEP_API_KEY", "test-key", raising=False)
    reader_module = importlib.import_module("app.services.zep_entity_reader")
    monkeypatch.setattr(
        reader_module.ZepEntityReader,
        "get_all_nodes",
        lambda self, graph_id: (_ for _ in ()).throw(
            AssertionError("prepare should use the persisted entity index before remote node reads")
        ),
    )
    monkeypatch.setattr(
        reader_module.ZepEntityReader,
        "get_all_edges",
        lambda self, graph_id: (_ for _ in ()).throw(
            AssertionError("prepare should use the persisted entity index before remote edge reads")
        ),
    )
    monkeypatch.setattr(manager_module, "ZepEntityReader", reader_module.ZepEntityReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _FakeProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _FakeSimulationConfigGenerator
    )

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")

    prepared = manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=True,
        uncertainty_profile="balanced",
        outcome_metrics=["simulation.total_actions"],
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    phase_timings = json.loads((sim_dir / "prepare_phase_timings.json").read_text(encoding="utf-8"))

    assert prepared.status == manager_module.SimulationStatus.READY
    assert prepared.entities_count == 1
    assert phase_timings["phases"]["entity_read"]["metadata"]["entity_count"] == 1


def test_prepare_simulation_persists_forecast_brief_artifact_and_summary(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=[
            "simulation.total_actions",
            "platform.twitter.total_actions",
        ],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100 by June 30, 2026?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100.",
                "Resolve no otherwise.",
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {
                "ensemble_size": 24,
                "max_concurrency": 4,
            },
            "uncertainty_plan": {
                "notes": ["Use the selected prepare profile as the first-pass uncertainty plan."],
            },
            "scoring_rule_preferences": ["brier_score", "log_score"],
            "compare_candidates": ["baseline", "policy_variant_a"],
            "scenario_templates": ["base_case", "viral_spike"],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    forecast_brief = json.loads((sim_dir / "forecast_brief.json").read_text(encoding="utf-8"))
    prepared_snapshot = json.loads((sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8"))
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    assert forecast_brief["artifact_type"] == "forecast_brief"
    assert forecast_brief["forecast_question"] == (
        "Will simulated total actions exceed 100 by June 30, 2026?"
    )
    assert forecast_brief["resolution_date"] == "2026-06-30"
    assert forecast_brief["selected_outcome_metrics"] == [
        "simulation.total_actions",
        "platform.twitter.total_actions",
    ]
    assert forecast_brief["run_budget"]["ensemble_size"] == 24
    assert forecast_brief["run_budget"]["max_concurrency"] == 4
    assert forecast_brief["uncertainty_plan"]["profile"] == "balanced"
    assert forecast_brief["scoring_rule_preferences"] == ["brier_score", "log_score"]
    assert forecast_brief["compare_candidates"] == ["baseline", "policy_variant_a"]
    assert forecast_brief["scenario_templates"] == ["base_case", "viral_spike"]
    assert prepared_snapshot["forecast_brief"]["forecast_question"] == (
        forecast_brief["forecast_question"]
    )
    assert prepared_snapshot["feature_metadata"]["forecast_brief_attached"] is True
    assert summary["artifacts"]["forecast_brief"]["exists"] is True
    assert summary["artifacts"]["forecast_brief"]["path"].endswith("forecast_brief.json")
    assert summary["forecast_brief"]["uncertainty_plan"]["profile"] == "balanced"
    assert summary["forecast_brief"]["selected_outcome_metrics"] == [
        "simulation.total_actions",
        "platform.twitter.total_actions",
    ]
    assert summary["feature_metadata"]["forecast_brief_attached"] is True


def test_prepare_simulation_persists_grounding_bundle_and_summary_when_project_artifacts_exist(
    simulation_data_dir, monkeypatch, tmp_path
):
    manager_module = _load_manager_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)
    _write_project_grounding_artifacts(
        monkeypatch,
        tmp_path / "projects",
        project_id="proj-1",
        graph_id="graph-1",
    )

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
            "forecast_question": "Will simulated total actions exceed 100 by June 30, 2026?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100.",
                "Resolve no otherwise.",
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 12, "max_concurrency": 2},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scoring_rule_preferences": ["brier_score"],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    grounding_bundle = json.loads(
        (sim_dir / "grounding_bundle.json").read_text(encoding="utf-8")
    )
    forecast_brief = json.loads(
        (sim_dir / "forecast_brief.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    assert grounding_bundle["artifact_type"] == "grounding_bundle"
    assert grounding_bundle["status"] == "ready"
    assert grounding_bundle["source_artifacts"]["source_manifest"] == "source_manifest.json"
    assert grounding_bundle["source_artifacts"]["graph_build_summary"] == "graph_build_summary.json"
    assert grounding_bundle["citation_index"]["source"][0]["citation_id"] == "[S1]"
    assert grounding_bundle["citation_index"]["graph"][0]["citation_id"] == "[G1]"
    assert grounding_bundle["code_analysis_summary"]["status"] == "not_requested"
    assert forecast_brief["grounding_summary"]["status"] == "ready"
    assert forecast_brief["grounding_summary"]["evidence_count"] == 2
    assert prepared_snapshot["grounding_summary"]["status"] == "ready"
    assert prepared_snapshot["artifacts"]["grounding_bundle"]["exists"] is True
    assert summary["grounding_summary"]["status"] == "ready"
    assert summary["grounding_summary"]["citation_counts"] == {
        "source": 1,
        "graph": 1,
        "code": 0,
    }
    assert summary["artifact_completeness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "missing_artifacts": [],
    }
    assert summary["grounding_readiness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
    }
    assert summary["forecast_readiness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "blocking_stage": None,
    }


def test_prepare_simulation_persists_evidence_grounded_world_state_artifacts(
    simulation_data_dir, monkeypatch, tmp_path
):
    manager_module = _load_manager_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)
    _write_project_grounding_artifacts(
        monkeypatch,
        tmp_path / "projects",
        project_id="proj-1",
        graph_id="graph-1",
    )

    captured_profile_kwargs = {}
    captured_config_kwargs = {}

    class _CapturingProfileGenerator(_FakeProfileGenerator):
        def generate_profiles_from_entities(self, *args, **kwargs):
            captured_profile_kwargs.update(kwargs)
            return super().generate_profiles_from_entities(*args, **kwargs)

    class _CapturingSimulationConfigGenerator(_FakeSimulationConfigGenerator):
        def generate_config(self, **kwargs):
            captured_config_kwargs.update(kwargs)
            return super().generate_config(**kwargs)

    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(manager_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(manager_module, "OasisProfileGenerator", _CapturingProfileGenerator)
    monkeypatch.setattr(
        manager_module, "SimulationConfigGenerator", _CapturingSimulationConfigGenerator
    )

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")

    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="Workers mention slowdown risk and policy response.",
        probabilistic_mode=True,
        uncertainty_profile="balanced",
        outcome_metrics=["simulation.total_actions"],
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    world_state_path = sim_dir / "prepared_world_state.json"
    agent_states_path = sim_dir / "prepared_agent_states.json"
    phase_timings = json.loads((sim_dir / "prepare_phase_timings.json").read_text(encoding="utf-8"))
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    assert world_state_path.exists()
    assert agent_states_path.exists()
    assert "world_state" in phase_timings["phases"]
    assert captured_profile_kwargs["world_state"]["artifact_type"] == "prepared_world_state"
    assert captured_profile_kwargs["agent_states_by_uuid"]["entity-1"]["entity_uuid"] == "entity-1"
    assert captured_config_kwargs["world_state"]["retrieval_contract"]["status"] == "ready"
    assert captured_config_kwargs["agent_states_by_uuid"]["entity-1"]["topic_names"] == ["Labor slowdown"]
    assert summary["artifacts"]["prepared_world_state"]["exists"] is True
    assert summary["artifacts"]["prepared_agent_states"]["exists"] is True


def test_prepare_simulation_uses_fixed_variable_catalog_for_deterministic_baseline(
    simulation_data_dir, monkeypatch
):
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
        uncertainty_profile="deterministic-baseline",
        outcome_metrics=["simulation.total_actions"],
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads((sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8"))
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    assert uncertainty_spec["random_variables"]
    assert all(
        item["distribution"] == "fixed"
        for item in uncertainty_spec["random_variables"]
    )
    assert summary["feature_metadata"]["random_variable_count"] == len(
        uncertainty_spec["random_variables"]
    )
    assert summary["feature_metadata"]["non_fixed_random_variable_count"] == 0
    assert summary["feature_metadata"]["sampling_enabled"] is False


def test_prepare_simulation_emits_structured_uncertainty_metadata(
    simulation_data_dir, monkeypatch
):
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

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads((sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8"))
    prepared_snapshot = json.loads((sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8"))
    summary = manager.get_prepare_artifact_summary(state.simulation_id)
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }

    assert uncertainty_spec["experiment_design"]["method"] == "latin-hypercube"
    assert uncertainty_spec["variable_groups"]
    assert uncertainty_spec["scenario_templates"]
    assert [item["template_id"] for item in uncertainty_spec["scenario_templates"]] == [
        "base_case",
        "viral_spike",
    ]
    assert templates_by_id["base_case"]["field_overrides"] == {
        "event_config.narrative_direction": "baseline"
    }
    assert templates_by_id["viral_spike"]["field_overrides"] == {
        "event_config.narrative_direction": "viral_spike",
        "twitter_config.echo_chamber_strength": 0.8,
        "reddit_config.echo_chamber_strength": 0.75,
        "agent_configs[0].activity_level": 0.8,
        "agent_configs[0].posts_per_hour": 1.5,
        "agent_configs[0].comments_per_hour": 1.5,
        "agent_configs[0].influence_weight": 1.35,
    }
    assert prepared_snapshot["feature_metadata"]["structured_design_enabled"] is True
    assert prepared_snapshot["feature_metadata"]["experiment_design_method"] == "latin-hypercube"
    assert prepared_snapshot["feature_metadata"]["scenario_diversity_enabled"] is True
    assert prepared_snapshot["feature_metadata"]["scenario_worker"] == "simulation"
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"] == [
        {
            "template_id": "base_case",
            "label": "Base Case",
            "override_field_count": 1,
            "override_fields": ["event_config.narrative_direction"],
        },
        {
            "template_id": "viral_spike",
            "label": "Viral Spike",
            "override_field_count": 7,
            "override_fields": [
                "agent_configs[0].activity_level",
                "agent_configs[0].comments_per_hour",
                "agent_configs[0].influence_weight",
                "agent_configs[0].posts_per_hour",
                "event_config.narrative_direction",
                "reddit_config.echo_chamber_strength",
                "twitter_config.echo_chamber_strength",
            ],
        },
    ]
    assert summary["feature_metadata"]["scenario_template_count"] == 2
    assert summary["feature_metadata"]["scenario_diversity_enabled"] is True
    assert summary["feature_metadata"]["scenario_worker"] == "simulation"


def test_prepare_simulation_emits_structural_uncertainty_catalog_metadata(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 6, "max_concurrency": 2},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": ["base_case", "viral_spike", "consensus_bridge"],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    summary = manager.get_prepare_artifact_summary(state.simulation_id)

    structural_kinds = [
        item["kind"] for item in uncertainty_spec["structural_uncertainties"]
    ]

    assert structural_kinds == [
        "event_arrival_process",
        "exposure_path_variation",
        "influencer_activation",
        "credibility_shock",
        "moderation_policy_change",
        "graph_rewiring",
    ]
    assert prepared_snapshot["feature_metadata"]["structural_uncertainty_count"] == 6
    assert prepared_snapshot["feature_metadata"]["structural_uncertainty_kinds"] == (
        structural_kinds
    )
    assert summary["feature_metadata"]["structural_uncertainty_count"] == 6
    assert summary["feature_metadata"]["structural_uncertainty_kinds"] == structural_kinds


def test_prepare_simulation_accepts_structured_scenario_template_payloads(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 8, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": [
                {
                    "template_id": "baseline_watch",
                    "label": "Baseline Watch",
                    "weight": 3.0,
                    "field_overrides": {
                        "event_config.narrative_direction": "baseline",
                    },
                    "notes": ["Keep a heavier baseline allocation."],
                },
                {
                    "template_id": "shock_spike",
                    "label": "Shock Spike",
                    "weight": 1.0,
                    "field_overrides": {
                        "event_config.narrative_direction": "shock",
                        "twitter_config.echo_chamber_strength": 0.9,
                    },
                    "notes": ["Reserve a smaller but explicit shock lane."],
                },
            ],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }

    assert uncertainty_spec["experiment_design"]["scenario_assignment"] == "weighted_cycle"
    assert templates_by_id["baseline_watch"]["label"] == "Baseline Watch"
    assert templates_by_id["baseline_watch"]["weight"] == 3.0
    assert templates_by_id["baseline_watch"]["field_overrides"] == {
        "event_config.narrative_direction": "baseline",
    }
    assert templates_by_id["shock_spike"]["label"] == "Shock Spike"
    assert templates_by_id["shock_spike"]["weight"] == 1.0
    assert templates_by_id["shock_spike"]["field_overrides"] == {
        "event_config.narrative_direction": "shock",
        "twitter_config.echo_chamber_strength": 0.9,
    }


def test_prepare_simulation_expands_scenario_templates_into_substantive_diverse_overrides(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 8, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": [
                "base_case",
                "viral_spike",
                "consensus_bridge",
            ],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }

    assert uncertainty_spec["experiment_design"]["max_templates_per_run"] == 2
    assert "coverage_tags" in templates_by_id["viral_spike"]
    assert "amplification" in templates_by_id["viral_spike"]["coverage_tags"]
    assert templates_by_id["viral_spike"]["field_overrides"][
        "event_config.scheduled_events"
    ]
    assert templates_by_id["viral_spike"]["field_overrides"]["event_config.hot_topics"] != [
        "seed"
    ]
    assert templates_by_id["consensus_bridge"]["field_overrides"][
        "event_config.scheduled_events"
    ]
    assert uncertainty_spec["conditional_variables"]
    preview_by_id = {
        item["template_id"]: item
        for item in prepared_snapshot["feature_metadata"]["scenario_template_preview"]
    }
    assert preview_by_id["viral_spike"]["coverage_tags"]
    assert preview_by_id["viral_spike"]["exogenous_event_count"] >= 1


def test_prepare_simulation_builds_substantive_scenario_diversity_metadata(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 6, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": [
                "base_case",
                "viral_spike",
                "cooldown_recovery",
            ],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }

    assert {
        item["variable"]["field_path"]
        for item in uncertainty_spec["conditional_variables"]
    } >= {
        "twitter_config.recency_weight",
        "reddit_config.relevance_weight",
        "twitter_config.viral_threshold",
        "reddit_config.viral_threshold",
    }
    assert templates_by_id["viral_spike"]["field_overrides"] == {
        "event_config.narrative_direction": "viral_spike",
        "event_config.hot_topics": ["seed", "viral_spike", "attention_surge"],
        "event_config.scheduled_events": [
            {
                "offset_hours": 2,
                "event_type": "exogenous_spike",
                "topic": "viral_spike",
                "intensity": "high",
            },
            {
                "offset_hours": 10,
                "event_type": "reaction_wave",
                "topic": "attention_surge",
                "intensity": "medium",
            },
        ],
        "time_config.peak_activity_multiplier": 1.9,
        "time_config.off_peak_activity_multiplier": 0.15,
        "twitter_config.echo_chamber_strength": 0.8,
        "reddit_config.echo_chamber_strength": 0.75,
        "agent_configs[0].activity_level": 0.8,
        "agent_configs[0].posts_per_hour": 1.5,
        "agent_configs[0].comments_per_hour": 1.5,
        "agent_configs[0].influence_weight": 1.35,
    }
    assert templates_by_id["cooldown_recovery"]["field_overrides"] == {
        "event_config.narrative_direction": "cooldown",
        "event_config.hot_topics": ["seed", "stabilization", "clarification"],
        "event_config.scheduled_events": [
            {
                "offset_hours": 6,
                "event_type": "clarification",
                "topic": "stabilization",
                "intensity": "medium",
            }
        ],
        "time_config.peak_activity_multiplier": 1.1,
        "time_config.work_activity_multiplier": 0.75,
        "twitter_config.echo_chamber_strength": 0.25,
        "reddit_config.echo_chamber_strength": 0.2,
        "agent_configs[0].activity_level": 0.3,
        "agent_configs[0].posts_per_hour": 0.6,
        "agent_configs[0].comments_per_hour": 0.6,
    }
    assert prepared_snapshot["feature_metadata"]["scenario_diversity_axes"] == [
        "agent_behavior",
        "event_process",
        "platform_dynamics",
        "time_profile",
    ]
    assert prepared_snapshot["feature_metadata"]["scenario_template_override_total"] == 22
    assert prepared_snapshot["feature_metadata"]["scenario_template_substantive_count"] == 3
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"] == [
        {
            "template_id": "base_case",
            "label": "Base Case",
            "override_field_count": 1,
            "override_fields": ["event_config.narrative_direction"],
        },
        {
            "template_id": "viral_spike",
            "label": "Viral Spike",
            "override_field_count": 11,
            "override_fields": [
                "agent_configs[0].activity_level",
                "agent_configs[0].comments_per_hour",
                "agent_configs[0].influence_weight",
                "agent_configs[0].posts_per_hour",
                "event_config.hot_topics",
                "event_config.narrative_direction",
                "event_config.scheduled_events",
                "reddit_config.echo_chamber_strength",
                "time_config.off_peak_activity_multiplier",
                "time_config.peak_activity_multiplier",
                "twitter_config.echo_chamber_strength",
            ],
        },
        {
            "template_id": "cooldown_recovery",
            "label": "Cooldown Recovery",
            "override_field_count": 10,
            "override_fields": [
                "agent_configs[0].activity_level",
                "agent_configs[0].comments_per_hour",
                "agent_configs[0].posts_per_hour",
                "event_config.hot_topics",
                "event_config.narrative_direction",
                "event_config.scheduled_events",
                "reddit_config.echo_chamber_strength",
                "time_config.peak_activity_multiplier",
                "time_config.work_activity_multiplier",
                "twitter_config.echo_chamber_strength",
            ],
        },
    ]


def test_prepare_simulation_surfaces_substantive_diversity_template_metadata(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 8, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": [
                {
                    "template_id": "baseline_watch",
                    "label": "Baseline Watch",
                    "field_overrides": {
                        "event_config.narrative_direction": "baseline",
                    },
                    "coverage_tags": ["baseline", "steady-state"],
                    "exogenous_events": [
                        {
                            "event_id": "baseline-checkpoint",
                            "kind": "operator_note",
                            "hour": 4,
                        }
                    ],
                    "correlated_field_paths": [
                        "agent_configs[0].activity_level",
                    ],
                },
                {
                    "template_id": "crisis_spike",
                    "label": "Crisis Spike",
                    "weight": 2.0,
                    "field_overrides": {
                        "event_config.narrative_direction": "crisis",
                    },
                    "coverage_tags": ["shock", "amplification"],
                    "exogenous_events": [
                        {
                            "event_id": "shock-wave",
                            "kind": "breaking_news",
                            "hour": 2,
                        }
                    ],
                    "conditional_overrides": [
                        {
                            "variable": {
                                "field_path": "twitter_config.viral_threshold",
                                "distribution": "fixed",
                                "parameters": {"value": 6},
                            },
                            "condition_field_path": "event_config.narrative_direction",
                            "operator": "eq",
                            "condition_value": "crisis",
                        }
                    ],
                    "correlated_field_paths": [
                        "agent_configs[0].activity_level",
                        "twitter_config.viral_threshold",
                    ],
                },
                {
                    "template_id": "bridge_response",
                    "label": "Bridge Response",
                    "field_overrides": {
                        "event_config.narrative_direction": "bridge",
                    },
                    "coverage_tags": ["bridge", "response"],
                    "exogenous_events": [
                        {
                            "event_id": "bridge-briefing",
                            "kind": "community_response",
                            "hour": 5,
                        }
                    ],
                },
            ],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }

    assert uncertainty_spec["experiment_design"]["max_templates_per_run"] == 2
    assert uncertainty_spec["experiment_design"]["template_combination_policy"] == (
        "pairwise"
    )
    assert templates_by_id["crisis_spike"]["coverage_tags"] == [
        "shock",
        "amplification",
    ]
    assert templates_by_id["crisis_spike"]["exogenous_events"] == [
        {
            "event_id": "shock-wave",
            "kind": "breaking_news",
            "hour": 2,
        }
    ]
    assert templates_by_id["crisis_spike"]["correlated_field_paths"] == [
        "agent_configs[0].activity_level",
        "twitter_config.viral_threshold",
    ]
    assert templates_by_id["crisis_spike"]["conditional_overrides"][0][
        "condition_field_path"
    ] == "event_config.narrative_direction"
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"][1][
        "coverage_tags"
    ] == ["amplification", "shock"]
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"][1][
        "exogenous_event_count"
    ] == 1
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"][1][
        "conditional_override_count"
    ] == 1
    assert prepared_snapshot["feature_metadata"]["scenario_template_preview"][1][
        "correlated_field_count"
    ] == 2


def test_prepare_simulation_builds_substantive_template_metadata_for_auto_templates(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
        forecast_brief={
            "forecast_question": "Will simulated total actions exceed 100?",
            "resolution_criteria": [
                "Resolve yes if simulation.total_actions is greater than 100."
            ],
            "resolution_date": "2026-06-30",
            "run_budget": {"ensemble_size": 4, "max_concurrency": 1},
            "uncertainty_plan": {"notes": ["Use the balanced profile."]},
            "scenario_templates": ["base_case", "viral_spike", "crisis_case"],
        },
    )

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    uncertainty_spec = json.loads(
        (sim_dir / "uncertainty_spec.json").read_text(encoding="utf-8")
    )
    prepared_snapshot = json.loads(
        (sim_dir / "prepared_snapshot.json").read_text(encoding="utf-8")
    )
    templates_by_id = {
        item["template_id"]: item for item in uncertainty_spec["scenario_templates"]
    }
    preview_by_id = {
        item["template_id"]: item
        for item in prepared_snapshot["feature_metadata"]["scenario_template_preview"]
    }

    assert templates_by_id["viral_spike"]["coverage_tags"]
    assert templates_by_id["viral_spike"]["exogenous_events"]
    assert templates_by_id["viral_spike"]["conditional_overrides"]
    assert preview_by_id["viral_spike"]["exogenous_event_count"] >= 1
    assert preview_by_id["viral_spike"]["conditional_override_count"] >= 1
    assert preview_by_id["viral_spike"]["substantive_override_count"] > 7
    assert prepared_snapshot["feature_metadata"]["scenario_diversity_strategy"] == "cyclic"
    assert prepared_snapshot["feature_metadata"]["scenario_coverage_axes"] == [
        "attention",
        "platform",
        "trajectory",
    ]


def test_prepare_simulation_rejects_unknown_outcome_metric(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")

    with pytest.raises(ValueError, match="Unsupported outcome metric"):
        manager.prepare_simulation(
            simulation_id=state.simulation_id,
            simulation_requirement="Forecast discussion spread",
            document_text="seed text",
            probabilistic_mode=True,
            uncertainty_profile="balanced",
            outcome_metrics=["unknown.metric"],
        )


def test_prepare_endpoint_accepts_probabilistic_inputs_and_reports_requested_metadata(
    probabilistic_prepare_enabled,
    monkeypatch,
):
    simulation_module = _load_simulation_api_module()
    captured = {}

    class _FakeManager:
        derive_prepare_readiness = staticmethod(
            _load_manager_module().SimulationManager.derive_prepare_readiness
        )

        def __init__(self):
            self.saved_states = []

        def get_simulation(self, simulation_id):
            return type(
                "State",
                (),
                {
                    "simulation_id": simulation_id,
                    "project_id": "proj-1",
                    "graph_id": "graph-1",
                    "status": "created",
                    "entities_count": 0,
                    "entity_types": [],
                },
            )()

        def _save_simulation_state(self, state):
            self.saved_states.append(state)

        def prepare_simulation(self, **kwargs):
            captured["prepare_kwargs"] = kwargs
            return type(
                "ResultState",
                (),
                {
                    "to_simple_dict": lambda self: {
                        "simulation_id": kwargs["simulation_id"],
                        "status": "ready",
                    }
                },
            )()

        def get_prepare_artifact_summary(self, simulation_id):
            return {
                "simulation_id": simulation_id,
                "mode": "probabilistic",
                "schema_version": "probabilistic.prepare.v1",
                "generator_version": "probabilistic.prepare.generator.v1",
                "forecast_brief": None,
                "artifacts": {
                    "base_config": {
                        "filename": "simulation_config.base.json",
                        "path": f"/tmp/{simulation_id}/simulation_config.base.json",
                    },
                },
            }

    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(simulation_module, "SimulationManager", _FakeManager)
    monkeypatch.setattr(simulation_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(simulation_module.ProjectManager, "get_project", staticmethod(
        lambda _project_id: type("Project", (), {"simulation_requirement": "Forecast discussion spread"})()
    ))
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_extracted_text",
        staticmethod(lambda _project_id: "seed text"),
    )
    monkeypatch.setattr(
        simulation_module,
        "_check_simulation_prepared",
        lambda _simulation_id, require_probabilistic_artifacts=False: (False, {}),
    )
    monkeypatch.setattr(simulation_module, "threading", type("ThreadingModule", (), {"Thread": _FakeThread}))

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
            "uncertainty_profile": "balanced",
            "outcome_metrics": ["simulation.total_actions"],
            "forecast_brief": {
                "forecast_question": "Will simulated total actions exceed 100 by June 30, 2026?",
                "resolution_criteria": [
                    "Resolve yes if simulation.total_actions is greater than 100.",
                    "Resolve no otherwise.",
                ],
                "resolution_date": "2026-06-30",
                "run_budget": {
                    "ensemble_size": 24,
                    "max_concurrency": 4,
                },
                "uncertainty_plan": {
                    "notes": ["Use the selected prepare profile as the first-pass uncertainty plan."],
                },
                "scoring_rule_preferences": ["brier_score"],
                "compare_candidates": ["baseline"],
                "scenario_templates": ["base_case"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["probabilistic_mode"] is True
    assert payload["uncertainty_profile"] == "balanced"
    assert payload["outcome_metrics"] == ["simulation.total_actions"]
    assert payload["prepared_artifact_summary"]["mode"] == "probabilistic"
    assert payload["prepared_artifact_summary"]["schema_version"] == "probabilistic.prepare.v1"
    assert payload["prepared_artifact_summary"]["feature_metadata"]["forecast_brief_attached"] is True
    assert payload["prepared_artifact_summary"]["artifacts"]["forecast_brief"]["filename"] == (
        "forecast_brief.json"
    )
    assert payload["prepared_artifact_summary"]["forecast_brief"]["forecast_question"] == (
        "Will simulated total actions exceed 100 by June 30, 2026?"
    )
    assert payload["prepared_artifact_summary"]["forecast_brief"]["selected_outcome_metrics"] == [
        "simulation.total_actions"
    ]
    assert payload["prepared_artifact_summary"]["forecast_brief"]["uncertainty_plan"]["profile"] == (
        "balanced"
    )
    assert payload["prepared_artifact_summary"]["artifacts"]["base_config"]["filename"] == (
        "simulation_config.base.json"
    )
    assert payload["prepared_artifact_summary"]["artifacts"]["base_config"]["path"].endswith(
        "simulation_config.base.json"
    )
    assert captured["prepare_kwargs"]["forecast_brief"]["forecast_question"] == (
        "Will simulated total actions exceed 100 by June 30, 2026?"
    )
    assert captured["prepare_kwargs"]["forecast_brief"]["uncertainty_plan"]["profile"] == (
        "balanced"
    )
    assert captured["prepare_kwargs"]["forecast_brief"]["selected_outcome_metrics"] == [
        "simulation.total_actions"
    ]


def test_prepare_endpoint_can_create_or_reopen_forecast_workspace_for_inference_ready_path(
    probabilistic_prepare_enabled,
    monkeypatch,
):
    simulation_module = _load_simulation_api_module()
    captured = {"created": [], "attached": []}

    class _FakeWorkspace:
        def __init__(self, forecast_id):
            self.forecast_question = type(
                "Question",
                (),
                {"forecast_id": forecast_id, "primary_simulation_id": "sim-test"},
            )()

        def to_summary_dict(self):
            return {
                "forecast_id": self.forecast_question.forecast_id,
                "primary_simulation_id": self.forecast_question.primary_simulation_id,
                "lifecycle_stage": "forecast_workspace",
                "simulation_scope_status": "linked",
            }

    class _FakeForecastManager:
        workspaces = {}

        def get_workspace(self, forecast_id):
            return self.workspaces.get(forecast_id)

        def create_question(self, question):
            captured["created"].append(question.to_dict())
            workspace = _FakeWorkspace(question.forecast_id)
            self.workspaces[question.forecast_id] = workspace
            return workspace

        def attach_simulation_scope(self, forecast_id, **kwargs):
            captured["attached"].append({"forecast_id": forecast_id, **kwargs})
            workspace = self.workspaces[forecast_id]
            workspace.forecast_question.primary_simulation_id = kwargs.get("simulation_id")
            return workspace

    class _FakeManager:
        derive_prepare_readiness = staticmethod(
            _load_manager_module().SimulationManager.derive_prepare_readiness
        )

        def get_simulation(self, simulation_id):
            return type(
                "State",
                (),
                {
                    "simulation_id": simulation_id,
                    "project_id": "proj-1",
                    "graph_id": "graph-1",
                    "status": "created",
                    "entities_count": 0,
                    "entity_types": [],
                },
            )()

        def _save_simulation_state(self, state):
            return None

        def prepare_simulation(self, **kwargs):
            return type(
                "ResultState",
                (),
                {
                    "to_simple_dict": lambda self: {
                        "simulation_id": kwargs["simulation_id"],
                        "status": "ready",
                    }
                },
            )()

        def get_prepare_artifact_summary(self, simulation_id):
            return {
                "simulation_id": simulation_id,
                "mode": "probabilistic",
                "forecast_brief": None,
                "artifacts": {},
            }

    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(simulation_module, "SimulationManager", _FakeManager)
    monkeypatch.setattr(simulation_module, "ForecastManager", _FakeForecastManager)
    monkeypatch.setattr(simulation_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        staticmethod(lambda _project_id: type("Project", (), {"simulation_requirement": "Forecast discussion spread"})()),
    )
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_extracted_text",
        staticmethod(lambda _project_id: "seed text"),
    )
    monkeypatch.setattr(
        simulation_module,
        "_check_simulation_prepared",
        lambda _simulation_id, require_probabilistic_artifacts=False: (False, {}),
    )
    monkeypatch.setattr(
        simulation_module,
        "threading",
        type("ThreadingModule", (), {"Thread": _FakeThread}),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
            "uncertainty_profile": "balanced",
            "outcome_metrics": ["simulation.total_actions"],
            "forecast_question": {
                "forecast_id": "forecast-inference",
                "project_id": "proj-1",
                "title": "Question-first prepare path",
                "question": "Will the system complete the bounded run?",
                "question_type": "binary",
                "status": "active",
                "horizon": "2026-06-30",
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
                "source": "manual-entry",
                "resolution_criteria_ids": [],
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["forecast_workspace"]["forecast_id"] == "forecast-inference"
    assert captured["created"][0]["forecast_id"] == "forecast-inference"
    assert captured["attached"][0]["forecast_id"] == "forecast-inference"
    assert captured["attached"][0]["simulation_id"] == "sim-test"


def test_prepare_capabilities_endpoint_reports_backend_registry(
    probabilistic_prepare_enabled, monkeypatch
):
    simulation_module = _load_simulation_api_module()
    probabilistic_module = _load_probabilistic_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        False,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.get("/api/simulation/prepare/capabilities")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["probabilistic_prepare_enabled"] is True
    assert data["probabilistic_report_enabled"] is False
    assert data["probabilistic_interaction_enabled"] is False
    assert data["calibrated_probability_enabled"] is False
    assert data["calibration_artifact_support_enabled"] is False
    assert data["calibration_surface_mode"] == "artifact-gated"
    assert data["supported_scoring_rules"] == ["brier_score", "log_score"]
    assert data["calibration_min_case_count"] == 10
    assert data["calibration_bin_count"] == 5
    assert data["supported_uncertainty_profiles"] == sorted(
        probabilistic_module.SUPPORTED_UNCERTAINTY_PROFILES
    )
    assert data["default_uncertainty_profile"] == probabilistic_module.DEFAULT_UNCERTAINTY_PROFILE
    assert data["supported_outcome_metrics"]["simulation.completed"]["confidence_support"] == {
        "backtesting_supported": True,
        "calibration_supported": True,
        "support_tier": "binary-ready",
        "boundary_note": "Binary backtesting and calibration are supported only when explicit observed-truth artifacts exist."
    }
    assert data["supported_outcome_metrics"]["simulation.total_actions"]["confidence_support"] == {
        "backtesting_supported": False,
        "calibration_supported": False,
        "support_tier": "unsupported",
        "boundary_note": "This metric remains empirical or observed only; calibrated language is not supported in-repo."
    }
    assert data["default_outcome_metrics"] == list(probabilistic_module.DEFAULT_OUTCOME_METRICS)
    assert data["schema_version"] == probabilistic_module.PROBABILISTIC_SCHEMA_VERSION
    assert data["generator_version"] == probabilistic_module.PROBABILISTIC_GENERATOR_VERSION


def test_prepare_capabilities_endpoint_reflects_disabled_flag(monkeypatch):
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_PREPARE_ENABLED",
        False,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.get("/api/simulation/prepare/capabilities")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["probabilistic_prepare_enabled"] is False


def test_prepare_capabilities_endpoint_reports_rollout_flags(monkeypatch):
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )
    client = _build_test_client(simulation_module)

    response = client.get("/api/simulation/prepare/capabilities")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["probabilistic_report_enabled"] is True
    assert payload["probabilistic_interaction_enabled"] is True
    assert payload["calibrated_probability_enabled"] is True
    assert payload["calibration_artifact_support_enabled"] is True
    assert payload["calibration_surface_mode"] == "artifact-gated"


def test_prepare_status_respects_probabilistic_mode_for_simulation_lookup(monkeypatch):
    simulation_module = _load_simulation_api_module()
    observed = []

    def _fake_check(_simulation_id, require_probabilistic_artifacts=False):
        observed.append(require_probabilistic_artifacts)
        return False, {}

    monkeypatch.setattr(simulation_module, "_check_simulation_prepared", _fake_check)
    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare/status",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 200
    assert observed == [True]
    assert response.get_json()["data"]["status"] == "not_started"


def test_prepare_status_requires_full_probabilistic_sidecar_set(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
    )

    simulation_dir = Path(simulation_data_dir) / state.simulation_id
    (simulation_dir / "uncertainty_spec.json").unlink()

    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir)
    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare/status",
        json={
            "simulation_id": state.simulation_id,
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_prepared"] is False
    assert payload["status"] == "not_started"


def test_prepare_status_blocks_forecast_handoff_when_grounding_is_unavailable(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
    )

    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir)
    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare/status",
        json={
            "simulation_id": state.simulation_id,
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_prepared"] is False
    assert payload["status"] == "not_started"
    assert (
        payload["prepare_info"]["reason"]
        == "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
    )
    assert payload["prepare_info"]["prepared_artifact_summary"]["artifact_completeness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "missing_artifacts": [],
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["grounding_readiness"] == {
        "ready": False,
        "status": "unavailable",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["forecast_readiness"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["workflow_handoff_status"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
        "semantics": "workflow_handoff_status",
    }


def test_prepare_status_blocks_forecast_handoff_when_grounding_bundle_is_missing(
    simulation_data_dir, monkeypatch
):
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
        outcome_metrics=["simulation.total_actions"],
    )

    simulation_dir = Path(simulation_data_dir) / state.simulation_id
    (simulation_dir / "grounding_bundle.json").unlink()

    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir)
    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare/status",
        json={
            "simulation_id": state.simulation_id,
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_prepared"] is False
    assert payload["status"] == "not_started"
    assert (
        payload["prepare_info"]["reason"]
        == "Stored-run shell handoff is blocked because grounding_bundle.json is missing."
    )
    assert payload["prepare_info"]["prepared_artifact_summary"]["artifact_completeness"] == {
        "ready": False,
        "status": "partial",
        "reason": "Forecast artifacts are incomplete. Missing files: grounding_bundle.json.",
        "missing_artifacts": ["grounding_bundle.json"],
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["grounding_readiness"] == {
        "ready": False,
        "status": "missing",
        "reason": "Stored-run shell handoff is blocked because grounding_bundle.json is missing.",
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["forecast_readiness"] == {
        "ready": False,
        "status": "blocked",
        "reason": "Stored-run shell handoff is blocked because grounding_bundle.json is missing.",
        "blocking_stage": "grounding",
    }
    assert payload["prepare_info"]["prepared_artifact_summary"]["workflow_handoff_status"] == {
        "ready": False,
        "status": "blocked",
        "reason": "Stored-run shell handoff is blocked because grounding_bundle.json is missing.",
        "blocking_stage": "grounding",
        "semantics": "workflow_handoff_status",
    }


def test_prepare_status_respects_probabilistic_mode_when_task_is_missing(monkeypatch):
    simulation_module = _load_simulation_api_module()
    observed = []

    def _fake_check(_simulation_id, require_probabilistic_artifacts=False):
        observed.append(require_probabilistic_artifacts)
        return False, {}

    class _FakeTaskManager:
        def get_task(self, _task_id):
            return None

    task_module = importlib.import_module("app.models.task")

    monkeypatch.setattr(simulation_module, "_check_simulation_prepared", _fake_check)
    monkeypatch.setattr(task_module, "TaskManager", _FakeTaskManager)
    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare/status",
        json={
            "task_id": "task-missing",
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 404
    assert observed == [True, True]
    assert "Task does not exist" in response.get_json()["error"]


def test_prepare_endpoint_rejects_probabilistic_mode_when_flag_is_disabled(monkeypatch):
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(simulation_module.Config, "PROBABILISTIC_PREPARE_ENABLED", False)
    monkeypatch.setattr(
        simulation_module,
        "SimulationManager",
        type(
            "Manager",
            (),
            {
                "__init__": lambda self: None,
                "get_simulation": lambda self, simulation_id: type(
                    "State",
                    (),
                    {
                        "simulation_id": simulation_id,
                        "project_id": "proj-1",
                        "graph_id": "graph-1",
                    },
                )(),
            },
        ),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "disabled" in payload["error"]


def test_prepare_endpoint_rejects_probabilistic_fields_without_mode(monkeypatch):
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(simulation_module.Config, "PROBABILISTIC_PREPARE_ENABLED", True)
    monkeypatch.setattr(
        simulation_module,
        "SimulationManager",
        type(
            "Manager",
            (),
            {
                "__init__": lambda self: None,
                "get_simulation": lambda self, simulation_id: type(
                    "State",
                    (),
                    {
                        "simulation_id": simulation_id,
                        "project_id": "proj-1",
                        "graph_id": "graph-1",
                    },
                )(),
            },
        ),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "uncertainty_profile": "balanced",
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "probabilistic_mode=true" in payload["error"]


def test_prepare_endpoint_rejects_forecast_brief_without_mode(monkeypatch):
    simulation_module = _load_simulation_api_module()
    monkeypatch.setattr(simulation_module.Config, "PROBABILISTIC_PREPARE_ENABLED", True)
    monkeypatch.setattr(
        simulation_module,
        "SimulationManager",
        type(
            "Manager",
            (),
            {
                "__init__": lambda self: None,
                "get_simulation": lambda self, simulation_id: type(
                    "State",
                    (),
                    {
                        "simulation_id": simulation_id,
                        "project_id": "proj-1",
                        "graph_id": "graph-1",
                    },
                )(),
            },
        ),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "forecast_brief": {
                "forecast_question": "Will simulated total actions exceed 100?",
                "resolution_criteria": [
                    "Resolve yes if simulation.total_actions is greater than 100."
                ],
                "resolution_date": "2026-06-30",
                "selected_outcome_metrics": ["simulation.total_actions"],
                "run_budget": {"ensemble_size": 12},
                "uncertainty_plan": {"profile": "balanced"},
                "scoring_rule_preferences": ["brier_score"],
            },
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "forecast_brief" in payload["error"]
    assert "probabilistic_mode=true" in payload["error"]


def test_prepare_endpoint_rejects_unknown_metric_id(
    probabilistic_prepare_enabled, monkeypatch
):
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module,
        "SimulationManager",
        type(
            "Manager",
            (),
            {
                "__init__": lambda self: None,
                "get_simulation": lambda self, simulation_id: type(
                    "State",
                    (),
                    {
                        "simulation_id": simulation_id,
                        "project_id": "proj-1",
                        "graph_id": "graph-1",
                    },
                )(),
            },
        ),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
            "uncertainty_profile": "balanced",
            "outcome_metrics": ["unknown.metric"],
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "Unsupported outcome metric" in payload["error"]


def test_prepare_endpoint_rejects_unknown_uncertainty_profile(
    probabilistic_prepare_enabled, monkeypatch
):
    simulation_module = _load_simulation_api_module()

    monkeypatch.setattr(
        simulation_module,
        "SimulationManager",
        type(
            "Manager",
            (),
            {
                "__init__": lambda self: None,
                "get_simulation": lambda self, simulation_id: type(
                    "State",
                    (),
                    {
                        "simulation_id": simulation_id,
                        "project_id": "proj-1",
                        "graph_id": "graph-1",
                    },
                )(),
            },
        ),
    )

    client = _build_test_client(simulation_module)

    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": "sim-test",
            "probabilistic_mode": True,
            "uncertainty_profile": "unknown-profile",
            "outcome_metrics": ["simulation.total_actions"],
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "Unsupported uncertainty profile" in payload["error"]


def test_prepare_endpoint_reprepares_probabilistic_after_legacy_prepare(
    simulation_data_dir, probabilistic_prepare_enabled, monkeypatch
):
    manager_module = _load_manager_module()
    simulation_module = _load_simulation_api_module()
    _install_prepare_stubs(monkeypatch, manager_module)
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()
    state = manager.create_simulation("proj-1", "graph-1")
    manager.prepare_simulation(
        simulation_id=state.simulation_id,
        simulation_requirement="Forecast discussion spread",
        document_text="seed text",
        probabilistic_mode=False,
    )

    class _FakeReader:
        def filter_defined_entities(self, *args, **kwargs):
            return _fake_filtered_entities()

    monkeypatch.setattr(simulation_module, "ZepEntityReader", _FakeReader)
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        staticmethod(
            lambda _project_id: type(
                "Project",
                (),
                {"simulation_requirement": "Forecast discussion spread"},
            )()
        ),
    )
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_extracted_text",
        staticmethod(lambda _project_id: "seed text"),
    )
    monkeypatch.setattr(simulation_module, "threading", type("ThreadingModule", (), {"Thread": _FakeThread}))

    client = _build_test_client(simulation_module)
    response = client.post(
        "/api/simulation/prepare",
        json={
            "simulation_id": state.simulation_id,
            "probabilistic_mode": True,
            "uncertainty_profile": "balanced",
            "outcome_metrics": ["simulation.total_actions"],
            "force_regenerate": False,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_prepared"] is False

    sim_dir = Path(manager._get_simulation_dir(state.simulation_id))
    assert (sim_dir / "simulation_config.base.json").exists()
    assert (sim_dir / "uncertainty_spec.json").exists()
    assert (sim_dir / "outcome_spec.json").exists()
    assert (sim_dir / "prepared_snapshot.json").exists()
