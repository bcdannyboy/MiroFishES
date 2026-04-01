import csv
import importlib
import json
from pathlib import Path
from typing import List, Optional


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_ensemble_module():
    return importlib.import_module("app.services.ensemble_manager")


def _load_context_module():
    return importlib.import_module("app.services.probabilistic_report_context")


def test_workspace_calibrated_confidence_earned_requires_resolved_backtest_basis():
    context_module = _load_context_module()
    assert (
        context_module.ProbabilisticReportContextBuilder._workspace_calibrated_confidence_earned(
            latest_answer={"confidence_semantics": "calibrated"},
            confidence_basis={
                "status": "available",
                "resolved_case_count": 0,
                "benchmark_status": "available",
                "backtest_status": "not_run",
            },
            calibration_summary={"status": "ready"},
        )
        is False
    )


def test_workspace_answer_confidence_status_surfaces_calibrated_binary_lane():
    context_module = _load_context_module()
    status = (
        context_module.ProbabilisticReportContextBuilder._build_answer_confidence_status(
            {
                "forecast_question": {
                    "question_type": "binary",
                },
                "forecast_answer": {
                    "confidence_semantics": "calibrated",
                    "answer_payload": {
                        "ensemble_policy": {
                            "policy_name": "empirically_tuned_worker_ensemble",
                            "evidence_regime": {"label": "corroborated_local_evidence"},
                        }
                    },
                    "confidence_basis": {
                        "status": "available",
                        "resolved_case_count": 10,
                        "benchmark_status": "available",
                        "backtest_status": "available",
                        "calibration_status": "ready",
                    },
                    "backtest_summary": {
                        "status": "available",
                        "question_type": "binary",
                    },
                    "calibration_summary": {
                        "status": "ready",
                        "calibration_kind": "binary_reliability",
                        "readiness": {"ready": True, "gating_reasons": []},
                    },
                },
            }
        )
    )

    assert status == {
        "status": "ready",
        "confidence_semantics": "calibrated",
        "question_type": "binary",
        "calibration_kind": "binary_reliability",
        "backtest_status": "available",
        "calibration_status": "ready",
        "benchmark_status": "available",
        "resolved_case_count": 10,
        "gating_reasons": [],
        "warnings": [],
        "evidence_regime": "corroborated_local_evidence",
        "policy_name": "empirically_tuned_worker_ensemble",
        "boundary_note": "Answer-level confidence remains scoped to the saved forecast workspace and its resolved evaluation lane.",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_backtest_summary(
    ensemble_dir: Path,
    *,
    simulation_id: str,
    ensemble_id: str,
    metric_id: str = "simulation.completed",
    value_kind: str = "binary",
    warnings: Optional[List[str]] = None,
) -> None:
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.backtest.v2",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "metric_backtests": {
                metric_id: {
                    "metric_id": metric_id,
                    "value_kind": value_kind,
                    "case_count": 10,
                    "positive_case_count": 5,
                    "negative_case_count": 5,
                    "observed_event_rate": 0.5,
                    "mean_forecast_probability": 0.44,
                    "scoring_rules": ["brier_score", "log_score"]
                    if value_kind == "binary"
                    else [],
                    "scores": {
                        "brier_score": 0.12,
                        "log_score": 0.41,
                        "brier_skill_score": 0.52,
                    }
                    if value_kind == "binary"
                    else {},
                    "case_results": [],
                    "warnings": warnings or [],
                }
            },
            "quality_summary": {
                "status": "complete",
                "warnings": [],
                "total_case_count": 10,
                "scored_case_count": 10 if value_kind == "binary" else 0,
                "skipped_case_count": 0,
                "supported_metric_ids": [metric_id] if value_kind == "binary" else [],
                "unscored_metric_ids": [] if value_kind == "binary" else [metric_id],
            },
        },
    )


def _write_calibration_summary(
    ensemble_dir: Path,
    *,
    simulation_id: str,
    ensemble_id: str,
    metric_id: str = "simulation.completed",
    value_kind: str = "binary",
    ready: bool = True,
    schema_version: str = "probabilistic.calibration.v2",
    metric_warnings: Optional[List[str]] = None,
    quality_warnings: Optional[List[str]] = None,
    gating_reasons: Optional[List[str]] = None,
    include_provenance: bool = True,
) -> None:
    quality_summary = {
        "status": "complete" if ready else "partial",
        "ready_metric_ids": [metric_id] if ready else [],
        "not_ready_metric_ids": [] if ready else [metric_id],
        "warnings": list(quality_warnings or []),
    }
    if include_provenance:
        quality_summary["source_artifacts"] = {
            "backtest_summary": "backtest_summary.json"
        }
        quality_summary["provenance"] = {
            "status": "valid",
            "backtest_artifact_type": "backtest_summary",
            "backtest_schema_version": "probabilistic.backtest.v2",
            "backtest_generator_version": "probabilistic.backtest.generator.v2",
            "backtest_simulation_id": simulation_id,
            "backtest_ensemble_id": ensemble_id,
        }

    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": schema_version,
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "metric_calibrations": {
                metric_id: {
                    "metric_id": metric_id,
                    "value_kind": value_kind,
                    "case_count": 10,
                    "supported_scoring_rules": ["brier_score", "log_score"]
                    if value_kind == "binary"
                    else [],
                    "scores": {"brier_score": 0.12, "log_score": 0.41}
                    if value_kind == "binary"
                    else {},
                    "diagnostics": {
                        "expected_calibration_error": 0.18,
                        "max_calibration_gap": 0.25,
                    },
                    "reliability_bins": [],
                    "readiness": {
                        "ready": ready,
                        "minimum_case_count": 10,
                        "actual_case_count": 10,
                        "minimum_positive_case_count": 3,
                        "actual_positive_case_count": 5,
                        "minimum_negative_case_count": 3,
                        "actual_negative_case_count": 5 if ready else 0,
                        "non_empty_bin_count": 2,
                        "supported_bin_count": 2,
                        "minimum_supported_bin_count": 2,
                        "gating_reasons": list(gating_reasons or []),
                        "confidence_label": "limited" if ready else "insufficient",
                    },
                    "warnings": list(metric_warnings or []),
                }
            },
            "quality_summary": quality_summary,
        },
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
    assert artifact["probability_semantics"]["cluster_share"] == "observed_run_share"
    assert artifact["simulation_role"] == {
        "worker": "simulation",
        "mode": "worker_composed",
        "summary": "Simulation contributes scenario evidence as one forecast worker. Saved artifacts define scope and evidence boundaries; they do not turn simulation frequencies into earned real-world probabilities.",
    }
    assert artifact["prepared_artifact_summary"]["probabilistic_mode"] is True
    assert artifact["prepared_artifact_summary"]["artifact_completeness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "missing_artifacts": [],
    }
    assert artifact["prepared_artifact_summary"]["grounding_readiness"] == {
        "ready": False,
        "status": "unavailable",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
    }
    assert artifact["prepared_artifact_summary"]["forecast_readiness"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
    }
    assert artifact["prepared_artifact_summary"]["workflow_handoff_status"] == {
        "ready": False,
        "status": "blocked",
        "reason": (
            "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
        ),
        "blocking_stage": "grounding",
        "semantics": "workflow_handoff_status",
    }
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
    assert artifact["confidence_status"]["artifact_readiness"] == {
        "calibration_summary": {
            "status": "absent",
            "reason": "No calibration summary artifact is attached to this ensemble.",
        },
        "backtest_summary": {
            "status": "absent",
            "reason": "No backtest summary artifact is attached to this ensemble.",
        },
        "provenance": {
            "status": "absent",
            "reason": "Calibration provenance cannot be verified without a valid calibration summary artifact.",
        },
    }
    assert artifact["confidence_status"]["boundary_note"].startswith(
        "Ensemble calibration artifacts apply only to named simulation metrics"
    )
    assert "observational_only" not in artifact["sensitivity"]["quality_summary"]["warnings"]
    assert artifact["sensitivity"]["methodology"]["analysis_mode"] == "hybrid_designed_observational"


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


def test_build_context_exposes_simulation_market_snapshot_for_selected_run(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    run_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
        / "runs"
        / "run_0001"
    )
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_paths"].update(
        {
            "simulation_market_manifest": "simulation_market_manifest.json",
            "market_snapshot": "market_snapshot.json",
            "disagreement_summary": "disagreement_summary.json",
        }
    )
    _write_json(manifest_path, manifest)
    _write_json(
        run_dir / "simulation_market_manifest.json",
        {
            "artifact_type": "simulation_market_manifest",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "forecast_id": "forecast-sim-market",
            "question_type": "binary",
            "extraction_status": "ready",
            "supported_question_type": True,
            "forecast_workspace_linked": True,
            "scope_linked_to_run": True,
            "artifact_paths": {
                "market_snapshot": "market_snapshot.json",
                "disagreement_summary": "disagreement_summary.json",
            },
            "signal_counts": {
                "agent_beliefs": 2,
                "belief_updates": 3,
                "missing_information_requests": 1,
            },
            "warnings": [],
            "source_artifacts": {"run_manifest": "run_manifest.json"},
            "boundary_notes": [
                "Synthetic market outputs remain heuristic and observational."
            ],
            "extracted_at": "2026-03-30T10:15:00",
        },
    )
    _write_json(
        run_dir / "market_snapshot.json",
        {
            "artifact_type": "simulation_market_snapshot",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "forecast_id": "forecast-sim-market",
            "question_type": "binary",
            "extraction_status": "ready",
            "support_status": "ready",
            "participating_agent_count": 2,
            "extracted_signal_count": 3,
            "disagreement_index": 0.24,
            "synthetic_consensus_probability": 0.58,
            "dominant_outcome": None,
            "categorical_distribution": {},
            "missing_information_request_count": 1,
            "boundary_notes": [
                "Synthetic market outputs remain heuristic and observational."
            ],
        },
    )
    _write_json(
        run_dir / "disagreement_summary.json",
        {
            "artifact_type": "simulation_market_disagreement_summary",
            "schema_version": "forecast.simulation_market.v1",
            "generator_version": "forecast.simulation_market.generator.v1",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "forecast_id": "forecast-sim-market",
            "question_type": "binary",
            "support_status": "ready",
            "participant_count": 2,
            "judgment_count": 3,
            "disagreement_index": 0.24,
            "consensus_probability": 0.58,
            "consensus_outcome": None,
            "distribution": {},
            "range_low": 0.4,
            "range_high": 0.65,
            "warnings": [],
            "boundary_notes": [
                "Synthetic market outputs remain heuristic and observational."
            ],
        },
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

    assert artifact["selected_run"]["simulation_market"]["market_snapshot"]["synthetic_consensus_probability"] == 0.58
    assert artifact["selected_run"]["simulation_market"]["manifest"]["extraction_status"] == "ready"
    assert artifact["selected_run"]["simulation_market"]["disagreement_summary"]["disagreement_index"] == 0.24
    assert artifact["aggregate_summary"]["artifact_type"] == "aggregate_summary"
    assert artifact["scenario_families"][0]["share_semantics"] == "observed_run_share"
    assert any(
        "observed run share" in option["prompt"]
        for option in artifact["compare_options"]
        if option["left"]["level"] == "cluster"
    )
    assert any(
        outcome["metric_id"] == "simulation.completed"
        and outcome["value_summary"]["observed_true_share"] == 2 / 3
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
    assert artifact["prepared_artifact_summary"]["grounding_readiness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
    }
    assert artifact["prepared_artifact_summary"]["forecast_readiness"] == {
        "ready": True,
        "status": "ready",
        "reason": "",
        "blocking_stage": None,
    }


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
    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
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
        "artifact_readiness": {
            "calibration_summary": {"status": "valid", "reason": ""},
            "backtest_summary": {"status": "valid", "reason": ""},
            "provenance": {"status": "valid", "reason": ""},
        },
        "boundary_note": "Ensemble calibration artifacts apply only to named simulation metrics with validated backtest artifacts. Forecast-workspace categorical and numeric calibration, when present, is a separate answer-bound lane.",
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
    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        ready=False,
        metric_warnings=["degenerate_base_rate_baseline"],
        quality_warnings=["not_ready_metrics_present"],
        gating_reasons=["insufficient_negative_case_count"],
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
        "artifact_readiness": {
            "calibration_summary": {"status": "valid", "reason": ""},
            "backtest_summary": {"status": "valid", "reason": ""},
            "provenance": {"status": "valid", "reason": ""},
        },
        "boundary_note": "Ensemble calibration artifacts apply only to named simulation metrics with validated backtest artifacts. Forecast-workspace categorical and numeric calibration, when present, is a separate answer-bound lane.",
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
    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        metric_id="platform.leading_platform",
        value_kind="categorical",
        warnings=["unsupported_confidence_contract"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        metric_id="platform.leading_platform",
        value_kind="categorical",
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
        "artifact_readiness": {
            "calibration_summary": {"status": "valid", "reason": ""},
            "backtest_summary": {"status": "valid", "reason": ""},
            "provenance": {"status": "valid", "reason": ""},
        },
        "boundary_note": "Ensemble calibration artifacts apply only to named simulation metrics with validated backtest artifacts. Forecast-workspace categorical and numeric calibration, when present, is a separate answer-bound lane.",
    }
    assert artifact["source_artifacts"]["calibration_summary"] == "calibration_summary.json"
    assert artifact["source_artifacts"]["backtest_summary"] == "backtest_summary.json"
    assert "calibrated_summary" not in artifact
    assert "calibration_provenance" not in artifact


def test_build_context_keeps_invalid_calibration_artifacts_out_of_ready_confidence(
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
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "metric_calibrations": {},
            "quality_summary": {"status": "complete", "warnings": []},
        },
    )

    context_module = _load_context_module()
    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["confidence_status"]["status"] == "not_ready"
    assert artifact["confidence_status"]["gating_reasons"] == [
        "invalid_calibration_artifact"
    ]
    assert artifact["confidence_status"]["artifact_readiness"] == {
        "calibration_summary": {
            "status": "invalid",
            "reason": "Calibration summary failed validation and cannot support confidence surfaces.",
        },
        "backtest_summary": {
            "status": "absent",
            "reason": "No backtest summary artifact is attached to this ensemble.",
        },
        "provenance": {
            "status": "invalid",
            "reason": "Calibration provenance cannot be trusted until the calibration summary validates.",
        },
    }
    assert artifact["source_artifacts"]["calibration_summary"] == "calibration_summary.json"
    assert "calibrated_summary" not in artifact
    assert "calibration_provenance" not in artifact


def test_build_context_requires_backtest_provenance_before_ready_confidence(
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
    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
        include_provenance=False,
    )

    context_module = _load_context_module()
    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    assert artifact["confidence_status"]["status"] == "not_ready"
    assert artifact["confidence_status"]["gating_reasons"] == [
        "missing_backtest_provenance"
    ]
    assert artifact["confidence_status"]["artifact_readiness"] == {
        "calibration_summary": {"status": "valid", "reason": ""},
        "backtest_summary": {"status": "valid", "reason": ""},
        "provenance": {
            "status": "absent",
            "reason": "Calibration summary is missing explicit provenance back to backtest_summary.json.",
        },
    }
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

    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
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


def test_build_context_surfaces_hybrid_forecast_workspace_payload(
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
    _write_backtest_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    _write_calibration_summary(
        ensemble_dir,
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )
    context_module = _load_context_module()
    monkeypatch.setattr(
        context_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )

    forecast_manager_module = importlib.import_module("app.services.forecast_manager")

    class _FakeRecord:
        def __init__(self, payload):
            self.__dict__.update(payload)

        def to_dict(self):
            return json.loads(json.dumps(self.__dict__))

    class _FakeForecastWorkspace:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return json.loads(json.dumps(self.payload))

    class _FakeForecastManager:
            def __init__(self, *args, **kwargs):
                self._workspace = _FakeForecastWorkspace(
                {
                    "forecast_question": {
                        "forecast_id": "forecast-001",
                        "project_id": "proj-1",
                        "title": "Policy support outlook",
                        "question": "Will support exceed 55% by June 30, 2026?",
                        "question_text": "Will support exceed 55% by June 30, 2026?",
                        "question_type": "binary",
                        "status": "active",
                        "horizon": {
                            "type": "date",
                            "value": "2026-06-30",
                        },
                        "issue_timestamp": "2026-03-30T09:00:00",
                        "owner": "forecasting-team",
                        "source": "manual-entry",
                        "decomposition_support": [
                            {
                                "template_id": "north-region",
                                "label": "North region split",
                                "question_text": "Will north-region support exceed 55%?",
                                "resolution_criteria_ids": ["criteria-1"],
                            }
                        ],
                        "abstention_conditions": [
                            "Do not issue if no named resolution source is available.",
                        ],
                        "resolution_criteria_ids": ["criteria-1"],
                        "supported_question_templates": [
                            {
                                "template_id": "north-region",
                                "label": "North region split",
                                "question_text": "Will north-region support exceed 55%?",
                                "resolution_criteria_ids": ["criteria-1"],
                                "abstention_conditions": [
                                    "Do not issue if no named resolution source is available.",
                                ],
                            }
                        ],
                    },
                    "evidence_bundle": {
                        "bundle_id": "bundle-1",
                        "forecast_id": "forecast-001",
                        "title": "Forecast evidence",
                        "summary": "Evidence bundle with local and evaluation-backed support.",
                        "status": "ready",
                        "source_entries": [
                            {
                                "entry_id": "source-1",
                                "provider_id": "uploaded_local_artifact",
                                "provider_kind": "uploaded_local_artifact",
                                "title": "Memo",
                                "summary": "Uploaded grounding notes.",
                            }
                        ],
                        "provider_snapshots": [
                            {
                                "provider_id": "uploaded_local_artifact",
                                "provider_kind": "uploaded_local_artifact",
                                "status": "ready",
                            }
                        ],
                        "quality_summary": {"status": "complete"},
                        "retrieval_quality": {"status": "bounded_local_only"},
                        "freshness_summary": {"status": "fresh"},
                        "relevance_summary": {"status": "relevant"},
                        "conflict_summary": {"status": "clear"},
                        "missing_evidence_markers": [],
                        "uncertainty_summary": {
                            "status": "bounded",
                            "causes": [],
                            "drivers": [],
                        },
                    },
                    "prediction_ledger": {
                        "forecast_id": "forecast-001",
                        "entries": [
                            {
                                "entry_id": "entry-1",
                                "prediction_id": "prediction-1",
                                "worker_id": "worker-base-rate",
                                "recorded_at": "2026-03-30T09:10:00",
                                "value_type": "probability",
                                "value": 0.58,
                                "prediction": 0.58,
                                "value_semantics": "forecast_probability",
                                "entry_kind": "issue",
                                "revision_number": 1,
                                "worker_output_ids": ["worker-output-1"],
                                "calibration_state": "uncalibrated",
                                "evidence_bundle_ids": ["bundle-1"],
                                "notes": ["Base-rate worker issued an initial estimate."],
                                "metadata": {"generated_by_engine": True},
                                "final_resolution_state": "pending",
                            }
                        ],
                        "worker_outputs": [
                            {
                                "worker_id": "worker-base-rate",
                                "output_id": "worker-output-1",
                                "summary": "Base-rate comparison output",
                            }
                        ],
                        "resolution_history": [],
                        "final_resolution_state": "pending",
                        "resolved_at": None,
                        "resolution_note": "",
                    },
                    "evaluation_cases": [
                        {
                            "case_id": "case-1",
                            "forecast_id": "forecast-001",
                            "criteria_id": "criteria-1",
                            "status": "resolved",
                            "issued_at": "2026-03-30T09:30:00",
                            "question_class": "binary",
                            "comparable_question_class": "binary",
                            "source": "manual-entry",
                            "prediction_entry_id": "entry-1",
                            "forecast_probability": 0.58,
                            "observed_value": True,
                            "evaluation_split": "rolling-1",
                            "window_id": "window-1",
                            "benchmark_id": "benchmark-1",
                            "observed_outcome": True,
                            "resolved_at": "2026-07-01T10:00:00",
                            "answer_id": "answer-1",
                            "evidence_bundle_id": "bundle-1",
                            "resolution_note": "Resolved yes.",
                            "confidence_basis": {"status": "resolved"},
                            "notes": ["Comparable binary case."],
                        }
                    ],
                    "forecast_answers": [
                        {
                            "answer_id": "answer-1",
                            "forecast_id": "forecast-001",
                            "answer_type": "hybrid_forecast",
                            "summary": "Hybrid estimate with simulation as supporting scenario analysis.",
                            "worker_ids": ["worker-base-rate", "worker-simulation"],
                            "prediction_entry_ids": ["entry-1"],
                            "confidence_semantics": "uncalibrated",
                            "created_at": "2026-03-30T10:00:00",
                            "answer_payload": {
                                "abstain": False,
                                "abstain_reason": None,
                                "best_estimate": {
                                    "value": 0.63,
                                    "value_semantics": "forecast_probability",
                                    "why": "Base-rate and reference-class support converge.",
                                },
                                "counterevidence": [
                                    "Simulation run share remains descriptive only.",
                                ],
                                "assumption_summary": {
                                    "items": [
                                        "Base-rate worker is weighted more heavily than simulation."
                                    ],
                                    "summary": "Base-rate worker is weighted more heavily than simulation.",
                                },
                                "uncertainty_decomposition": {
                                    "drivers": ["stale_evidence"],
                                    "components": [
                                        {
                                            "code": "stale_evidence",
                                            "summary": "One supporting signal is stale.",
                                        }
                                    ],
                                    "disagreement_range": 0.07,
                                },
                                "worker_contribution_trace": [
                                    {
                                        "worker_id": "worker-base-rate",
                                        "worker_kind": "base_rate",
                                        "status": "completed",
                                        "estimate": 0.61,
                                        "summary": "Base-rate worker contributed the estimate.",
                                    },
                                    {
                                        "worker_id": "worker-simulation",
                                        "worker_kind": "simulation",
                                        "status": "completed",
                                        "estimate": 0.72,
                                        "summary": "Simulation remained supporting scenario analysis.",
                                    },
                                ],
                                "evaluation_summary": {
                                    "status": "available",
                                    "case_count": 1,
                                    "resolved_case_count": 1,
                                    "pending_case_count": 0,
                                },
                                "benchmark_summary": {"status": "available"},
                                "backtest_summary": {"status": "not_run"},
                                "calibration_summary": {"status": "not_applicable"},
                                "confidence_basis": {
                                    "status": "available",
                                    "benchmark_status": "available",
                                    "backtest_status": "not_run",
                                    "calibration_status": "not_applicable",
                                },
                                "simulation_context": {
                                    "included": True,
                                    "observed_run_share": 0.72,
                                    "contribution_role": "supporting_scenario_analysis",
                                },
                            },
                        }
                    ],
                    "forecast_workers": [
                        {
                            "worker_id": "worker-base-rate",
                            "forecast_id": "forecast-001",
                            "kind": "base_rate",
                            "label": "Base-rate worker",
                            "status": "ready",
                            "capabilities": ["historical_reference"],
                            "primary_output_semantics": "forecast_probability",
                        },
                        {
                            "worker_id": "worker-simulation",
                            "forecast_id": "forecast-001",
                            "kind": "simulation",
                            "label": "Simulation worker",
                            "status": "ready",
                            "capabilities": ["scenario_generation"],
                            "primary_output_semantics": "scenario_evidence",
                        },
                    ],
                    "simulation_worker_contract": {
                        "worker_id": "worker-simulation",
                        "forecast_id": "forecast-001",
                        "simulation_id": state.simulation_id,
                        "prepare_artifact_paths": [
                            "uploads/simulations/sim-001/prepared_snapshot.json"
                        ],
                        "probability_interpretation": "do_not_treat_as_real_world_probability",
                    },
                    "resolution_record": {
                        "forecast_id": "forecast-001",
                        "status": "resolved_true",
                        "resolved_at": "2026-07-01T10:00:00",
                        "resolution_note": "Observed yes.",
                        "evidence_bundle_ids": ["bundle-1"],
                        "prediction_entry_ids": ["entry-1"],
                        "revision_entry_ids": [],
                        "worker_output_ids": ["worker-output-1"],
                    },
                    "scoring_events": [
                        {
                            "scoring_event_id": "score-1",
                            "forecast_id": "forecast-001",
                            "status": "scored",
                            "scoring_method": "brier_score",
                            "score_value": 0.1369,
                            "recorded_at": "2026-07-01T10:05:00",
                            "notes": ["Binary answer scored after resolution."],
                        }
                    ],
                    "forecast_workspace_status": "available",
                }
                )
                self._workspace_record = _FakeRecord(
                    {
                        "forecast_question": _FakeRecord(
                            {
                                "forecast_id": "forecast-001",
                                "primary_simulation_id": state.simulation_id,
                                "title": "Policy support outlook",
                                "question_text": "Will support exceed 55% by June 30, 2026?",
                                "question_type": "binary",
                                "status": "active",
                                "horizon": {
                                    "type": "date",
                                    "value": "2026-06-30",
                                },
                                "issue_timestamp": "2026-03-30T09:00:00",
                                "owner": "forecasting-team",
                                "source": "manual-entry",
                                "abstention_conditions": [
                                    "Do not issue if no named resolution source is available.",
                                ],
                                "decomposition_support": [
                                    {
                                        "template_id": "north-region",
                                        "label": "North region split",
                                        "question_text": "Will north-region support exceed 55%?",
                                        "resolution_criteria_ids": ["criteria-1"],
                                    }
                                ],
                                "decomposition": {
                                    "subquestion_ids": ["north-region"],
                                },
                            }
                        ),
                        "title": "Policy support outlook",
                        "question_text": "Will support exceed 55% by June 30, 2026?",
                        "question_status": "active",
                        "issue_timestamp": "2026-03-30T09:00:00",
                        "resolution_status": "pending",
                        "forecast_id": "forecast-001",
                        "worker_kinds": ["base_rate", "simulation"],
                        "evidence_bundle": _FakeRecord(
                            {
                                "bundle_id": "bundle-1",
                                "status": "ready",
                                "title": "Forecast evidence",
                                "summary": "Evidence bundle with local and evaluation-backed support.",
                                "source_entries": [
                                    _FakeRecord(
                                        {
                                            "entry_id": "source-1",
                                            "provider_id": "uploaded_local_artifact",
                                            "provider_kind": "uploaded_local_artifact",
                                            "title": "Memo",
                                            "summary": "Uploaded grounding notes.",
                                        }
                                    )
                                ],
                                "provider_snapshots": [
                                    _FakeRecord(
                                        {
                                            "provider_id": "uploaded_local_artifact",
                                            "provider_kind": "uploaded_local_artifact",
                                            "status": "ready",
                                        }
                                    )
                                ],
                                "retrieval_quality": {"status": "bounded_local_only"},
                                "conflict_markers": [],
                                "missing_evidence_markers": [],
                                "uncertainty_summary": {
                                    "status": "bounded",
                                    "causes": [],
                                },
                                "boundary_note": "Evidence bundle with local and evaluation-backed support.",
                            }
                        ),
                        "prediction_ledger": _FakeRecord(
                            {
                                "resolution_status": "pending",
                                "entries": [
                                    _FakeRecord(
                                        {
                                            "entry_id": "entry-1",
                                            "prediction_id": "prediction-1",
                                            "worker_id": "worker-base-rate",
                                            "recorded_at": "2026-03-30T09:10:00",
                                            "value_type": "probability",
                                            "value": 0.58,
                                            "prediction": 0.58,
                                            "value_semantics": "forecast_probability",
                                            "entry_kind": "issue",
                                            "revision_number": 1,
                                            "worker_output_ids": ["worker-output-1"],
                                            "calibration_state": "uncalibrated",
                                            "evidence_bundle_ids": ["bundle-1"],
                                            "notes": [
                                                "Base-rate worker issued an initial estimate."
                                            ],
                                            "metadata": {"generated_by_engine": True},
                                            "final_resolution_state": "pending",
                                        }
                                    )
                                ],
                                "worker_outputs": [
                                    {
                                        "worker_id": "worker-base-rate",
                                        "output_id": "worker-output-1",
                                        "summary": "Base-rate comparison output",
                                        "recorded_at": "2026-03-30T09:09:00",
                                    }
                                ],
                                "resolution_history": [],
                            }
                        ),
                        "evaluation_cases": [
                            _FakeRecord(
                                {
                                    "case_id": "case-1",
                                    "forecast_id": "forecast-001",
                                    "criteria_id": "criteria-1",
                                    "status": "resolved",
                                    "issued_at": "2026-03-30T09:30:00",
                                    "question_class": "binary",
                                    "comparable_question_class": "binary",
                                    "source": "manual-entry",
                                    "prediction_entry_id": "entry-1",
                                    "forecast_probability": 0.58,
                                    "observed_value": True,
                                    "evaluation_split": "rolling-1",
                                    "window_id": "window-1",
                                    "benchmark_id": "benchmark-1",
                                    "observed_outcome": True,
                                    "resolved_at": "2026-07-01T10:00:00",
                                    "answer_id": "answer-1",
                                    "evidence_bundle_id": "bundle-1",
                                    "resolution_note": "Resolved yes.",
                                    "confidence_basis": {"status": "resolved"},
                                    "notes": ["Comparable binary case."],
                                }
                            )
                        ],
                        "forecast_answers": [
                            _FakeRecord(
                                {
                                    "answer_id": "answer-1",
                                    "forecast_id": "forecast-001",
                                    "answer_type": "hybrid_forecast",
                                    "summary": "Hybrid estimate with simulation as supporting scenario analysis.",
                                    "worker_ids": ["worker-base-rate", "worker-simulation"],
                                    "prediction_entry_ids": ["entry-1"],
                                    "confidence_semantics": "uncalibrated",
                                    "created_at": "2026-03-30T10:00:00",
                                    "answer_payload": {
                                        "abstain": False,
                                        "abstain_reason": None,
                                        "best_estimate": {
                                            "value": 0.63,
                                            "value_semantics": "forecast_probability",
                                            "why": "Base-rate and reference-class support converge.",
                                        },
                                        "counterevidence": [
                                            "Simulation run share remains descriptive only.",
                                        ],
                                        "assumption_summary": {
                                            "items": [
                                                "Base-rate worker is weighted more heavily than simulation."
                                            ],
                                            "summary": "Base-rate worker is weighted more heavily than simulation.",
                                        },
                                        "uncertainty_decomposition": {
                                            "drivers": ["stale_evidence"],
                                            "components": [
                                                {
                                                    "code": "stale_evidence",
                                                    "summary": "One supporting signal is stale.",
                                                }
                                            ],
                                            "disagreement_range": 0.07,
                                        },
                                        "worker_contribution_trace": [
                                            {
                                                "worker_id": "worker-base-rate",
                                                "worker_kind": "base_rate",
                                                "status": "completed",
                                                "estimate": 0.61,
                                                "summary": "Base-rate worker contributed the estimate.",
                                            },
                                            {
                                                "worker_id": "worker-simulation",
                                                "worker_kind": "simulation",
                                                "status": "completed",
                                                "estimate": 0.72,
                                                "summary": "Simulation remained supporting scenario analysis.",
                                            },
                                        ],
                                        "evaluation_summary": {
                                            "status": "available",
                                            "case_count": 1,
                                            "resolved_case_count": 1,
                                            "pending_case_count": 0,
                                        },
                                        "benchmark_summary": {"status": "available"},
                                        "backtest_summary": {"status": "not_run"},
                                        "calibration_summary": {"status": "not_applicable"},
                                        "confidence_basis": {
                                            "status": "available",
                                            "benchmark_status": "available",
                                            "backtest_status": "not_run",
                                            "calibration_status": "not_applicable",
                                        },
                                        "simulation_context": {
                                            "included": True,
                                            "observed_run_share": 0.72,
                                            "contribution_role": "supporting_scenario_analysis",
                                        },
                                    },
                                }
                            )
                        ],
                        "forecast_workers": [
                            _FakeRecord(
                                {
                                    "worker_id": "worker-base-rate",
                                    "forecast_id": "forecast-001",
                                    "kind": "base_rate",
                                    "label": "Base-rate worker",
                                    "status": "ready",
                                    "capabilities": ["historical_reference"],
                                    "primary_output_semantics": "forecast_probability",
                                }
                            ),
                            _FakeRecord(
                                {
                                    "worker_id": "worker-simulation",
                                    "forecast_id": "forecast-001",
                                    "kind": "simulation",
                                    "label": "Simulation worker",
                                    "status": "ready",
                                    "capabilities": ["scenario_generation"],
                                    "primary_output_semantics": "scenario_evidence",
                                }
                            ),
                        ],
                    }
                )

            def list_question_summaries_for_simulation(self, simulation_id):
                return [
                    {
                        "forecast_id": "forecast-001",
                        "title": "Policy support outlook",
                        "question_text": "Will support exceed 55% by June 30, 2026?",
                        "question_status": "active",
                        "issue_timestamp": "2026-03-30T09:00:00",
                        "updated_at": "2026-03-30T09:05:00",
                        "created_at": "2026-03-30T09:00:00",
                        "primary_simulation_id": simulation_id,
                    }
                ]

            def get_workspace(self, forecast_id):
                if forecast_id != "forecast-001":
                    return None
                return self._workspace

            def list_workspaces(self):
                return [self._workspace_record]

    monkeypatch.setattr(forecast_manager_module, "ForecastManager", _FakeForecastManager)

    builder = context_module.ProbabilisticReportContextBuilder(
        simulation_data_dir=str(simulation_data_dir)
    )
    artifact = builder.build_context(
        simulation_id=state.simulation_id,
        ensemble_id=created["ensemble_id"],
    )

    workspace = artifact["forecast_workspace"]
    assert workspace["forecast_question"]["question_text"] == "Will support exceed 55% by June 30, 2026?"
    assert workspace["forecast_question"]["supported_question_templates"][0]["label"] == "North region split"
    assert workspace["evidence_bundle"]["status"] == "ready"
    assert workspace["prediction_ledger"]["entry_count"] == 1
    assert workspace["evaluation_results"]["resolved_case_count"] == 1
    assert workspace["forecast_answer"]["answer_type"] == "hybrid_forecast"
    assert workspace["worker_comparison"]["worker_count"] == 2
    assert workspace["abstain_state"]["abstain"] is False
    assert workspace["resolution_record"]["status"] == "resolved_true"
    assert workspace["scoring_events"][0]["scoring_method"] == "brier_score"
    assert workspace["truthfulness_surface"] == {
        "evidence_available": True,
        "evaluation_available": True,
        "calibrated_confidence_earned": False,
        "simulation_only_scenario_exploration": False,
        "boundary_note": (
            "Calibrated confidence is only earned when a forecast answer is explicitly marked "
            "calibrated and carries ready backtest and calibration metadata on a supported "
            "evaluation lane with resolved cases."
        ),
        "answer_confidence_status": {
            "status": "not_ready",
            "confidence_semantics": "uncalibrated",
            "question_type": "binary",
            "calibration_kind": None,
            "backtest_status": "not_run",
            "calibration_status": "not_applicable",
            "benchmark_status": "available",
            "resolved_case_count": 1,
            "gating_reasons": [],
            "warnings": [],
            "evidence_regime": None,
            "policy_name": None,
            "boundary_note": (
                "Answer-level confidence remains scoped to the saved forecast workspace and its resolved evaluation lane."
            ),
        },
    }
    assert artifact["forecast_object"] == {
        "forecast_id": "forecast-001",
        "status": "available",
        "question_text": "Will support exceed 55% by June 30, 2026?",
        "latest_answer_id": "answer-1",
        "resolution": {
            "status": "resolved_true",
            "resolved_at": "2026-07-01T10:00:00",
            "resolution_note": "Observed yes.",
        },
        "scoring": {
            "event_count": 1,
            "latest_method": "brier_score",
            "latest_score_value": 0.1369,
        },
    }
