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
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": graph_id,
            "generated_at": "2026-03-29T09:05:00",
            "source_artifacts": {"source_manifest": "source_manifest.json"},
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
                "entity_types": ["Person"],
            },
            "warnings": [],
        },
    )


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
    assert artifact["schema_version"] == "probabilistic.report_context.v3"
    assert artifact["simulation_id"] == state.simulation_id
    assert artifact["ensemble_id"] == created["ensemble_id"]
    assert artifact["run_id"] == "0001"
    assert artifact["probability_semantics"]["summary"] == "empirical"
    assert artifact["probability_semantics"]["sensitivity"] == "observational"
    assert artifact["prepared_artifact_summary"]["probabilistic_mode"] is True
    assert artifact["analytics_semantics"]["aggregate"]["analysis_mode"] == "aggregate"
    assert artifact["analytics_semantics"]["scenario"]["analysis_mode"] == "scenario"
    assert artifact["analytics_semantics"]["sensitivity"]["analysis_mode"] == "sensitivity"
    assert artifact["scope"]["level"] == "run"
    assert artifact["scope"]["source"] == "derived_membership"
    assert artifact["selected_run"]["run_id"] == "0001"
    assert artifact["selected_cluster"]["cluster_id"].startswith("cluster_")
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
    assert artifact["confidence_status"]["status"] == "absent"
    assert artifact["confidence_status"]["boundary_note"].startswith(
        "Calibration in this repo is binary-only"
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


def test_build_context_supports_cluster_scope_and_scope_catalog(
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
        cluster_id="cluster_0001",
    )

    assert artifact["scope"] == {
        "level": "cluster",
        "simulation_id": state.simulation_id,
        "ensemble_id": created["ensemble_id"],
        "cluster_id": "cluster_0001",
        "run_id": None,
        "representative_run_id": artifact["selected_cluster"]["prototype_run_id"],
        "source": "route",
    }
    assert artifact["run_id"] is None
    assert artifact["selected_run"] is None
    assert artifact["selected_cluster"]["cluster_id"] == "cluster_0001"
    assert artifact["selected_cluster"]["family_signature"]["semantics"] == "empirical"
    assert artifact["driver_analysis"]["semantics"] == "observational"
    assert artifact["driver_analysis"]["ranking_basis"] == (
        "support_aware_standardized_effect_sum"
    )
    assert artifact["driver_analysis"]["selected_scope_highlights"]
    assert artifact["scope_catalog"]["ensemble"]["level"] == "ensemble"
    assert artifact["scope_catalog"]["clusters"][0]["level"] == "cluster"
    assert artifact["scope_catalog"]["compare_options"]


def test_build_context_exposes_compare_catalog_with_compact_scope_snapshots(
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

    catalog = artifact["compare_catalog"]
    assert catalog["boundary_note"].startswith(
        "Compare only scopes inside one saved report context"
    )
    assert catalog["options"]

    first_option = catalog["options"][0]
    assert first_option["compare_id"]
    assert first_option["label"]
    assert first_option["reason"]
    assert first_option["left_scope"]["ensemble_id"] == created["ensemble_id"]
    assert first_option["right_scope"]["ensemble_id"] == created["ensemble_id"]
    assert first_option["left_snapshot"]["scope"]["level"] in {"cluster", "run", "ensemble"}
    assert first_option["right_snapshot"]["scope"]["level"] in {"cluster", "run", "ensemble"}
    assert first_option["left_snapshot"]["support_label"]
    assert first_option["right_snapshot"]["support_label"]
    assert first_option["left_snapshot"]["semantics"] in {"empirical", "observed"}
    assert first_option["right_snapshot"]["semantics"] in {"empirical", "observed"}
    assert "comparison_summary" in first_option
    assert first_option["comparison_summary"]["what_differs"]
    assert first_option["comparison_summary"]["boundary_note"]


def test_build_context_exposes_grounding_context_separately_from_downstream_analytics(
    simulation_data_dir, monkeypatch, tmp_path
):
    _write_project_grounding_artifacts(
        monkeypatch,
        tmp_path / "projects",
        project_id="proj-1",
        graph_id="graph-1",
    )
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

    assert artifact["grounding_context"]["status"] == "ready"
    assert artifact["grounding_context"]["boundary_note"].startswith(
        "Uploaded project sources only"
    )
    assert artifact["grounding_context"]["citation_counts"] == {
        "source": 1,
        "graph": 1,
        "code": 0,
    }
    assert artifact["grounding_context"]["evidence_items"][0]["citation_id"] == "[S1]"
    assert artifact["grounding_context"]["evidence_items"][1]["citation_id"] == "[G1]"
    assert artifact["source_artifacts"]["grounding_bundle"] == "grounding_bundle.json"
    assert artifact["probability_semantics"]["summary"] == "empirical"


def test_build_context_surfaces_ready_calibration_summary_when_enabled(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    ensemble_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
    )
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.prepare.v1",
            "generator_version": "probabilistic.prepare.generator.v1",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "metric_calibrations": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "supported_scoring_rules": ["brier_score", "log_score"],
                    "scores": {"brier_score": 0.12, "log_score": 0.41},
                    "reliability_bins": [
                        {
                            "bin_index": 0,
                            "lower_bound": 0.0,
                            "upper_bound": 0.2,
                            "case_count": 2,
                            "mean_forecast_probability": 0.1,
                            "observed_frequency": 0.0,
                            "observed_minus_forecast": -0.1,
                        },
                        {
                            "bin_index": 4,
                            "lower_bound": 0.8,
                            "upper_bound": 1.0,
                            "case_count": 2,
                            "mean_forecast_probability": 0.9,
                            "observed_frequency": 1.0,
                            "observed_minus_forecast": 0.1,
                        },
                    ],
                    "readiness": {
                        "ready": True,
                        "minimum_case_count": 10,
                        "actual_case_count": 10,
                        "non_empty_bin_count": 2,
                        "gating_reasons": [],
                        "confidence_label": "limited",
                    },
                    "warnings": [],
                }
            },
            "quality_summary": {
                "status": "complete",
                "ready_metric_ids": ["simulation.completed"],
                "not_ready_metric_ids": [],
                "warnings": [],
            },
        },
    )
    context_module = _load_context_module()
    monkeypatch.setattr(
        context_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["confidence_status"] == {
        "status": "ready",
        "supported_metric_ids": ["simulation.completed"],
        "ready_metric_ids": ["simulation.completed"],
        "not_ready_metric_ids": [],
        "gating_reasons": [],
        "warnings": [],
        "boundary_note": "Calibration in this repo is binary-only and applies only to named metrics with ready backtest artifacts.",
    }
    assert artifact["calibrated_summary"]["artifact_type"] == "calibration_summary"
    assert artifact["calibrated_summary"]["metrics"][0]["metric_id"] == "simulation.completed"
    assert artifact["calibrated_summary"]["metrics"][0]["readiness"]["ready"] is True


def test_build_context_surfaces_not_ready_confidence_without_calibrated_summary(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    ensemble_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
    )
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.calibration.v2",
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "metric_calibrations": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "supported_scoring_rules": ["brier_score", "log_score"],
                    "scores": {"brier_score": 0.12, "log_score": 0.41},
                    "diagnostics": {
                        "expected_calibration_error": 0.18,
                        "max_calibration_gap": 0.25,
                    },
                    "reliability_bins": [],
                    "readiness": {
                        "ready": False,
                        "minimum_case_count": 10,
                        "actual_case_count": 10,
                        "minimum_positive_case_count": 3,
                        "actual_positive_case_count": 10,
                        "minimum_negative_case_count": 3,
                        "actual_negative_case_count": 0,
                        "non_empty_bin_count": 2,
                        "supported_bin_count": 2,
                        "minimum_supported_bin_count": 2,
                        "gating_reasons": ["insufficient_negative_case_count"],
                        "confidence_label": "insufficient",
                    },
                    "warnings": ["degenerate_base_rate_baseline"],
                }
            },
            "quality_summary": {
                "status": "partial",
                "ready_metric_ids": [],
                "not_ready_metric_ids": ["simulation.completed"],
                "warnings": ["not_ready_metrics_present"],
            },
        },
    )
    context_module = _load_context_module()
    monkeypatch.setattr(
        context_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["confidence_status"] == {
        "status": "not_ready",
        "supported_metric_ids": ["simulation.completed"],
        "ready_metric_ids": [],
        "not_ready_metric_ids": ["simulation.completed"],
        "gating_reasons": ["insufficient_negative_case_count"],
        "warnings": ["not_ready_metrics_present", "degenerate_base_rate_baseline"],
        "boundary_note": "Calibration in this repo is binary-only and applies only to named metrics with ready backtest artifacts.",
    }
    assert "calibrated_summary" not in artifact
    assert "calibration_provenance" not in artifact


def test_build_context_keeps_unsupported_calibration_artifacts_not_ready(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    ensemble_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
    )
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.calibration.v2",
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "metric_calibrations": {
                "platform.leading_platform": {
                    "metric_id": "platform.leading_platform",
                    "value_kind": "categorical",
                    "case_count": 12,
                    "supported_scoring_rules": [],
                    "scores": {},
                    "diagnostics": {},
                    "reliability_bins": [],
                    "readiness": {
                        "ready": True,
                        "minimum_case_count": 10,
                        "actual_case_count": 12,
                        "minimum_positive_case_count": 3,
                        "actual_positive_case_count": 6,
                        "minimum_negative_case_count": 3,
                        "actual_negative_case_count": 6,
                        "non_empty_bin_count": 3,
                        "supported_bin_count": 3,
                        "minimum_supported_bin_count": 2,
                        "gating_reasons": [],
                        "confidence_label": "limited",
                    },
                    "warnings": [],
                }
            },
            "quality_summary": {
                "status": "complete",
                "ready_metric_ids": ["platform.leading_platform"],
                "not_ready_metric_ids": [],
                "warnings": [],
            },
        },
    )
    context_module = _load_context_module()
    monkeypatch.setattr(
        context_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["confidence_status"] == {
        "status": "not_ready",
        "supported_metric_ids": [],
        "ready_metric_ids": [],
        "not_ready_metric_ids": [],
        "gating_reasons": ["no_supported_binary_metrics"],
        "warnings": ["unsupported_confidence_contract"],
        "boundary_note": "Calibration in this repo is binary-only and applies only to named metrics with ready backtest artifacts.",
    }
    assert artifact["source_artifacts"]["calibration_summary"] == "calibration_summary.json"
    assert "calibrated_summary" not in artifact
    assert "calibration_provenance" not in artifact


def test_build_context_exposes_assumption_ledgers_and_calibration_provenance(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    ensemble_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
    )
    for run_id, template_id in (("0001", "baseline-watch"), ("0002", "high-echo")):
        run_dir = ensemble_dir / "runs" / f"run_{run_id}"
        manifest_path = run_dir / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["assumption_ledger"] = {
            "applied_templates": [template_id],
            "notes": [f"Applied template {template_id}"],
        }
        _write_json(manifest_path, manifest)

    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.prepare.v1",
            "generator_version": "probabilistic.prepare.generator.v1",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "metric_calibrations": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "supported_scoring_rules": ["brier_score", "log_score"],
                    "scores": {"brier_score": 0.12, "log_score": 0.41},
                    "reliability_bins": [],
                    "readiness": {
                        "ready": True,
                        "minimum_case_count": 10,
                        "actual_case_count": 10,
                        "non_empty_bin_count": 2,
                        "gating_reasons": [],
                        "confidence_label": "limited",
                    },
                    "warnings": [],
                }
            },
            "quality_summary": {
                "status": "complete",
                "ready_metric_ids": ["simulation.completed"],
                "not_ready_metric_ids": [],
                "warnings": [],
            },
        },
    )

    context_module = _load_context_module()
    monkeypatch.setattr(
        context_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        run_id="0001",
    )

    assert artifact["selected_run"]["assumption_ledger"]["applied_templates"] == [
        "baseline-watch"
    ]
    assert any(
        run["assumption_ledger"]["applied_templates"]
        for run in artifact["representative_runs"]
    )
    assert artifact["confidence_status"]["status"] == "ready"
    assert artifact["calibration_provenance"]["mode"] == "calibrated"
    assert artifact["calibration_provenance"]["ready_metric_ids"] == [
        "simulation.completed"
    ]
