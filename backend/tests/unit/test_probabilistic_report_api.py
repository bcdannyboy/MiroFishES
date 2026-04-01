import csv
import inspect
import importlib
import json
import sys
from pathlib import Path

from flask import Flask


def _load_manager_module():
    return importlib.import_module("app.services.simulation_manager")


def _load_report_agent_module():
    return importlib.import_module("app.services.report_agent")


def _load_report_api_module():
    sys.modules.pop("app.api.report", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.report")


def _load_simulation_api_module():
    sys.modules.pop("app.api.simulation", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.simulation")


def _load_ensemble_module():
    return importlib.import_module("app.services.ensemble_manager")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_forecast_archive(simulation_dir: Path, *, reason: str = "Historical only") -> None:
    _write_json(
        simulation_dir / "forecast_archive.json",
        {
            "artifact_type": "forecast_archive",
            "schema_version": "forecast.archive.v1",
            "archived_at": "2026-03-29T12:00:00",
            "archive_scope": "historical_read_only",
            "reason": reason,
        },
    )


def _write_backtest_summary(ensemble_dir: Path, *, simulation_id: str, ensemble_id: str) -> None:
    _write_json(
        ensemble_dir / "backtest_summary.json",
        {
            "artifact_type": "backtest_summary",
            "schema_version": "probabilistic.backtest.v2",
            "generator_version": "probabilistic.backtest.generator.v2",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "metric_backtests": {
                "simulation.completed": {
                    "metric_id": "simulation.completed",
                    "value_kind": "binary",
                    "case_count": 10,
                    "positive_case_count": 5,
                    "negative_case_count": 5,
                    "observed_event_rate": 0.5,
                    "mean_forecast_probability": 0.44,
                    "scoring_rules": ["brier_score", "log_score"],
                    "scores": {
                        "brier_score": 0.12,
                        "log_score": 0.41,
                        "brier_skill_score": 0.52,
                    },
                    "case_results": [],
                    "warnings": [],
                }
            },
            "quality_summary": {
                "status": "complete",
                "warnings": [],
                "total_case_count": 10,
                "scored_case_count": 10,
                "skipped_case_count": 0,
                "supported_metric_ids": ["simulation.completed"],
                "unscored_metric_ids": [],
            },
        },
    )


def _write_calibration_summary(
    ensemble_dir: Path,
    *,
    simulation_id: str,
    ensemble_id: str,
    ready: bool = True,
    metric_warnings=None,
    quality_warnings=None,
    gating_reasons=None,
) -> None:
    _write_json(
        ensemble_dir / "calibration_summary.json",
        {
            "artifact_type": "calibration_summary",
            "schema_version": "probabilistic.calibration.v2",
            "generator_version": "probabilistic.calibration.generator.v2",
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
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
            "quality_summary": {
                "status": "complete" if ready else "partial",
                "ready_metric_ids": ["simulation.completed"] if ready else [],
                "not_ready_metric_ids": [] if ready else ["simulation.completed"],
                "warnings": list(quality_warnings or []),
                "source_artifacts": {
                    "backtest_summary": "backtest_summary.json",
                },
                "provenance": {
                    "status": "valid",
                    "backtest_artifact_type": "backtest_summary",
                    "backtest_schema_version": "probabilistic.backtest.v2",
                    "backtest_generator_version": "probabilistic.backtest.generator.v2",
                    "backtest_simulation_id": simulation_id,
                    "backtest_ensemble_id": ensemble_id,
                },
            },
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


def test_report_agent_prompts_use_bounded_simulation_language():
    report_agent_module = _load_report_agent_module()

    assert "preview of the future" not in report_agent_module.PLAN_SYSTEM_PROMPT
    assert "predictions of future human behavior" not in report_agent_module.PLAN_SYSTEM_PROMPT
    assert "preview of the future" not in report_agent_module.PLAN_USER_PROMPT_TEMPLATE
    assert "predictions of future human behavior" not in report_agent_module.SECTION_SYSTEM_PROMPT_TEMPLATE
    assert "simulation report assistant" in report_agent_module.CHAT_SYSTEM_PROMPT_TEMPLATE
    assert "bounded simulated scenario" in report_agent_module.PLAN_SYSTEM_PROMPT
    assert "not direct evidence of real human behavior" in report_agent_module.PLAN_SYSTEM_PROMPT
    assert "Use bounded language" in report_agent_module.SECTION_SYSTEM_PROMPT_TEMPLATE

    plan_outline_source = inspect.getsource(report_agent_module.ReportAgent.plan_outline)
    assert "Future Forecast Report" not in plan_outline_source
    assert "Simulation Scenario Report" in plan_outline_source


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
                "echo_chamber_strength": 0.5,
            },
            "reddit_config": {
                "platform": "reddit",
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
    reader_module = importlib.import_module("app.services.graph_entity_reader")
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

    monkeypatch.setattr(manager_module, "GraphEntityReader", _FakeReader)
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
            },
            "top_topics": [{"topic": "seed", "count": total_actions}],
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
            "run_count": 2,
            "max_concurrency": 1,
            "root_seed": 17,
            "sampling_mode": "seeded",
        },
    )

    run_payloads = {
        "0001": {"driver": 0.1, "total": 4, "twitter": 2},
        "0002": {"driver": 0.9, "total": 10, "twitter": 7},
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
        )

    return created


def _build_test_client(report_module):
    app = Flask(__name__)
    app.register_blueprint(report_module.report_bp, url_prefix="/api/report")
    return app.test_client()


def _build_simulation_test_client(simulation_module):
    app = Flask(__name__)
    app.register_blueprint(simulation_module.simulation_bp, url_prefix="/api/simulation")
    return app.test_client()


class _FakeThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        if self.target:
            self.target()


def test_report_generate_and_get_persist_probabilistic_scope(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
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
    resolved_config_path = run_dir / "resolved_config.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved_payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    manifest_payload["base_graph_id"] = "graph-1"
    manifest_payload["runtime_graph_id"] = "runtime-graph-1"
    manifest_payload["graph_id"] = "graph-1"
    resolved_payload["base_graph_id"] = "graph-1"
    resolved_payload["runtime_graph_id"] = "runtime-graph-1"
    resolved_payload["graph_id"] = "graph-1"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    resolved_config_path.write_text(
        json.dumps(resolved_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    captures = {}

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            **kwargs,
        ):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.base_graph_id = kwargs.get("base_graph_id")
            self.runtime_graph_id = kwargs.get("runtime_graph_id")
            self.graph_ids = kwargs.get("graph_ids")
            captures["graph_id"] = graph_id
            captures["base_graph_id"] = self.base_graph_id
            captures["runtime_graph_id"] = self.runtime_graph_id
            captures["graph_ids"] = self.graph_ids

        def generate_report(self, progress_callback=None, report_id=None):
            if progress_callback:
                progress_callback("planning", 25, "Planning report")
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                base_graph_id=self.base_graph_id,
                runtime_graph_id=self.runtime_graph_id,
                graph_ids=self.graph_ids or [],
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                outline=report_agent_module.ReportOutline(
                    title="Forecast report",
                    summary="Legacy report body with probabilistic context",
                    sections=[
                        report_agent_module.ReportSection(
                            title="Summary",
                            content="Generated content",
                        )
                    ],
                ),
                markdown_content="# Forecast report\n\nGenerated content\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    report_id = payload["report_id"]

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.get_json()["data"]
    assert report_payload["simulation_id"] == state.simulation_id
    assert report_payload["ensemble_id"] == created["ensemble_id"]
    assert captures["graph_id"] == "graph-1"
    assert captures["base_graph_id"] == "graph-1"
    assert captures["runtime_graph_id"] == "runtime-graph-1"
    assert captures["graph_ids"] == ["graph-1", "runtime-graph-1"]
    assert report_payload["graph_id"] == "graph-1"
    assert report_payload["base_graph_id"] == "graph-1"
    assert report_payload["runtime_graph_id"] == "runtime-graph-1"
    assert report_payload["graph_ids"] == ["graph-1", "runtime-graph-1"]
    assert report_payload["run_id"] == "0001"
    assert report_payload["probabilistic_context"]["artifact_type"] == (
        "probabilistic_report_context"
    )
    assert report_payload["probabilistic_context"]["selected_run"]["run_id"] == "0001"
    assert report_payload["probabilistic_context"]["aggregate_summary"]["artifact_type"] == (
        "aggregate_summary"
    )


def test_report_generate_builds_probabilistic_context_before_agent_execution(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    event_log = []
    expected_context = {
        "artifact_type": "probabilistic_report_context",
        "ensemble_id": created["ensemble_id"],
        "cluster_id": "cluster_0001",
        "run_id": "0001",
        "quality_summary": {"warnings": ["thin_sample"]},
        "forecast_workspace": {
            "forecast_question": {
                "question_text": "Will the hybrid system surface honest summaries?",
                "supported_question_templates": [
                    {
                        "template_id": "binary-resolution",
                        "label": "Binary resolution",
                        "question_type": "binary",
                        "prompt_template": "Will {subject} happen by {horizon}?",
                        "required_fields": ["question_text", "horizon"],
                        "abstain_guidance": "Abstain if evidence remains sparse.",
                        "notes": ["Supported as an explicit bounded question."],
                    }
                ],
            },
            "truthfulness_surface": {
                "evidence_available": True,
                "evaluation_available": True,
                "calibrated_confidence_earned": False,
                "simulation_only_scenario_exploration": False,
            },
            "abstain_state": {
                "abstain": False,
                "abstain_reason": "",
                "summary": "Hybrid answer available",
            },
        },
    }

    class _FakeContextBuilder:
        def build_context(
            self,
            simulation_id,
            ensemble_id,
            cluster_id=None,
            run_id=None,
        ):
            event_log.append(
                ("context", simulation_id, ensemble_id, cluster_id, run_id)
            )
            return expected_context

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            probabilistic_context=None,
            **kwargs,
        ):
            event_log.append(("agent_init", probabilistic_context))
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.probabilistic_context = probabilistic_context

        def generate_report(self, progress_callback=None, report_id=None):
            event_log.append(("generate", self.probabilistic_context))
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                probabilistic_context=self.probabilistic_context,
                outline=report_agent_module.ReportOutline(
                    title="Forecast report",
                    summary="Probabilistic-native report body",
                    sections=[],
                ),
                markdown_content="# Forecast report\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(
        report_module,
        "ProbabilisticReportContextBuilder",
        _FakeContextBuilder,
    )
    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "cluster_id": "cluster_0001",
            "run_id": "0001",
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    assert event_log[0] == (
        "context",
        state.simulation_id,
        created["ensemble_id"],
        "cluster_0001",
        "0001",
    )
    assert event_log[1] == ("agent_init", expected_context)
    assert event_log[2] == ("generate", expected_context)


def test_report_generate_and_get_exposes_ready_calibration_summary(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
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
    resolved_config_path = run_dir / "resolved_config.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved_payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    manifest_payload["base_graph_id"] = "graph-1"
    manifest_payload["runtime_graph_id"] = "runtime-graph-1"
    manifest_payload["graph_id"] = "graph-1"
    resolved_payload["base_graph_id"] = "graph-1"
    resolved_payload["runtime_graph_id"] = "runtime-graph-1"
    resolved_payload["graph_id"] = "graph-1"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    resolved_config_path.write_text(
        json.dumps(resolved_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
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

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            probabilistic_context=None,
            **kwargs,
        ):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.probabilistic_context = probabilistic_context
            self.base_graph_id = kwargs.get("base_graph_id")
            self.runtime_graph_id = kwargs.get("runtime_graph_id")
            self.graph_ids = kwargs.get("graph_ids")

        def generate_report(self, progress_callback=None, report_id=None):
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                base_graph_id=self.base_graph_id,
                runtime_graph_id=self.runtime_graph_id,
                graph_ids=self.graph_ids or [],
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                probabilistic_context=self.probabilistic_context,
                outline=report_agent_module.ReportOutline(
                    title="Forecast report",
                    summary="Probabilistic report body with calibration context",
                    sections=[],
                ),
                markdown_content="# Forecast report\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    report_id = payload["report_id"]

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.get_json()["data"]
    assert report_payload["probabilistic_context"]["confidence_status"]["status"] == "ready"
    assert report_payload["probabilistic_context"]["calibrated_summary"]["metrics"][0]["metric_id"] == (
        "simulation.completed"
    )


def test_report_generate_and_get_exposes_not_ready_confidence_without_calibrated_summary(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
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

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            probabilistic_context=None,
            **kwargs,
        ):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.probabilistic_context = probabilistic_context

        def generate_report(self, progress_callback=None, report_id=None):
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                probabilistic_context=self.probabilistic_context,
                outline=report_agent_module.ReportOutline(
                    title="Forecast report",
                    summary="Probabilistic report body with bounded confidence context",
                    sections=[],
                ),
                markdown_content="# Forecast report\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    report_id = response.get_json()["data"]["report_id"]

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.get_json()["data"]
    assert report_payload["probabilistic_context"]["confidence_status"] == {
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
    assert "calibrated_summary" not in report_payload["probabilistic_context"]


def test_report_generate_and_get_preserve_probabilistic_provenance_fields(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "CALIBRATED_PROBABILITY_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
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
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["base_graph_id"] = "graph-1"
    manifest_payload["runtime_graph_id"] = "runtime-graph-1"
    manifest_payload["graph_id"] = "graph-1"
    manifest_payload["assumption_ledger"] = {
        "applied_templates": ["baseline-watch"],
        "notes": ["Applied template baseline-watch"],
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    resolved_config_path = run_dir / "resolved_config.json"
    resolved_payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    resolved_payload["base_graph_id"] = "graph-1"
    resolved_payload["runtime_graph_id"] = "runtime-graph-1"
    resolved_payload["graph_id"] = "graph-1"
    resolved_config_path.write_text(
        json.dumps(resolved_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
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

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            probabilistic_context=None,
            **kwargs,
        ):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.probabilistic_context = probabilistic_context
            self.base_graph_id = kwargs.get("base_graph_id")
            self.runtime_graph_id = kwargs.get("runtime_graph_id")
            self.graph_ids = kwargs.get("graph_ids")

        def generate_report(self, progress_callback=None, report_id=None):
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                base_graph_id=self.base_graph_id,
                runtime_graph_id=self.runtime_graph_id,
                graph_ids=self.graph_ids or [],
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                probabilistic_context=self.probabilistic_context,
                outline=report_agent_module.ReportOutline(
                    title="Forecast report",
                    summary="Probabilistic report body with persisted provenance",
                    sections=[],
                ),
                markdown_content="# Forecast report\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    report_id = response.get_json()["data"]["report_id"]

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.get_json()["data"]
    assert report_payload["probabilistic_context"]["confidence_status"]["status"] == "ready"
    assert report_payload["probabilistic_context"]["calibration_provenance"] == {
        "mode": "calibrated",
        "artifact_type": "calibration_summary",
        "ready_metric_ids": ["simulation.completed"],
        "quality_status": "complete",
        "warnings": [],
    }
    assert report_payload["probabilistic_context"]["selected_run"]["assumption_ledger"] == {
        "applied_templates": ["baseline-watch"],
        "notes": ["Applied template baseline-watch"],
    }


def test_report_chat_passes_grounding_context_from_saved_bundle(
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
    report_module = _load_report_api_module()
    captures = {}

    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            report_id=None,
            probabilistic_context=None,
            **kwargs,
        ):
            captures["probabilistic_context"] = probabilistic_context

        def chat(self, message, chat_history=None):
            return {
                "response": "Scoped probabilistic chat reply",
                "tool_calls": [],
                "sources": [],
            }

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "message": "What upstream evidence grounds this report?",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    assert captures["probabilistic_context"]["grounding_context"]["status"] == "ready"
    assert captures["probabilistic_context"]["grounding_context"]["citation_counts"] == {
        "source": 1,
        "graph": 1,
        "code": 0,
    }
    assert captures["probabilistic_context"]["grounding_context"]["evidence_items"][0][
        "citation_id"
    ] == "[S1]"


def test_probabilistic_report_generation_requires_report_flag(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_module = _load_report_api_module()
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.SimulationManager,
        "get_simulation",
        lambda _self, _simulation_id: type(
            "State",
            (),
            {
                "simulation_id": state.simulation_id,
                "project_id": "proj-1",
                "graph_id": "graph-1",
            },
        )(),
        raising=False,
    )
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
        },
    )

    assert response.status_code == 409
    assert "Probabilistic report generation is disabled" in response.get_json()["error"]


def test_legacy_report_generation_stays_available_when_probabilistic_report_flag_is_off(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    class _FakeReportAgent:
        def __init__(self, graph_id, simulation_id, simulation_requirement, **kwargs):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement

        def generate_report(self, progress_callback=None, report_id=None):
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                outline=None,
                markdown_content="# Legacy report\n",
                created_at="2026-03-10T13:10:00",
                completed_at="2026-03-10T13:11:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_report_get_keeps_legacy_reports_without_probabilistic_scope(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    class _FakeReportAgent:
        def __init__(self, graph_id, simulation_id, simulation_requirement, **kwargs):
            self.graph_id = graph_id
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement

        def generate_report(self, progress_callback=None, report_id=None):
            return report_agent_module.Report(
                report_id=report_id,
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                outline=None,
                markdown_content="# Legacy report\n",
                created_at="2026-03-09T10:30:00",
                completed_at="2026-03-09T10:31:00",
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "force_regenerate": True,
        },
    )

    assert response.status_code == 200
    report_id = response.get_json()["data"]["report_id"]

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200
    report_payload = report_response.get_json()["data"]
    assert report_payload["simulation_id"] == state.simulation_id
    assert report_payload.get("ensemble_id") in (None, "")
    assert report_payload.get("run_id") in (None, "")
    assert report_payload.get("probabilistic_context") is None


def test_report_agent_chat_prefers_explicit_report_id_and_saved_probabilistic_context(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    legacy_report = report_agent_module.Report(
        report_id="report-legacy",
        simulation_id="sim-chat",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Legacy report body\n\nLegacy-only summary.\n",
        created_at="2026-03-09T10:00:00",
        completed_at="2026-03-09T10:01:00",
    )
    probabilistic_report = report_agent_module.Report(
        report_id="report-probabilistic",
        simulation_id="sim-chat",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        run_id="0002",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "run_id": "0002",
            "probability_semantics": {
                "summary": "empirical",
                "sensitivity": "observational",
            },
        },
    )
    report_agent_module.ReportManager.save_report(legacy_report)
    report_agent_module.ReportManager.save_report(probabilistic_report)

    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "get_report_by_simulation",
        lambda _simulation_id: legacy_report,
    )

    class _FakeLLM:
        def __init__(self):
            self.messages = None

        def chat(self, messages, temperature=0.5):
            self.messages = messages
            return "Scoped answer"

    fake_llm = _FakeLLM()
    agent = report_agent_module.ReportAgent(
        graph_id="graph-1",
        simulation_id="sim-chat",
        simulation_requirement="Forecast discussion spread",
        llm_client=fake_llm,
        graph_tools=object(),
        report_id="report-probabilistic",
        probabilistic_context=probabilistic_report.probabilistic_context,
    )

    response = agent.chat("What does the ensemble show?")

    assert response["response"] == "Scoped answer"
    system_prompt = fake_llm.messages[0]["content"]
    assert "Probabilistic report body" in system_prompt
    assert "Legacy report body" not in system_prompt
    assert '"ensemble_id": "0001"' in system_prompt
    assert '"summary": "empirical"' in system_prompt


def test_report_agent_chat_includes_confidence_status_in_prompt_safe_context(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    probabilistic_report = report_agent_module.Report(
        report_id="report-probabilistic-confidence",
        simulation_id="sim-chat",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "confidence_status": {
                "status": "not_ready",
                "supported_metric_ids": [],
                "ready_metric_ids": [],
                "not_ready_metric_ids": [],
                "gating_reasons": ["no_supported_binary_metrics"],
                "warnings": ["unsupported_confidence_contract"],
                "boundary_note": "Ensemble calibration artifacts apply only to named simulation metrics with validated backtest artifacts. Forecast-workspace categorical and numeric calibration, when present, is a separate answer-bound lane.",
            },
            "forecast_workspace": {
                "forecast_question": {
                    "question_text": "Will the hybrid system surface honest summaries?",
                    "supported_question_templates": [
                        {
                            "template_id": "binary-resolution",
                            "label": "Binary resolution",
                            "question_type": "binary",
                            "prompt_template": "Will {subject} happen by {horizon}?",
                            "required_fields": ["question_text", "horizon"],
                            "abstain_guidance": "Abstain if evidence remains sparse.",
                            "notes": ["Supported as an explicit bounded question."],
                        }
                    ],
                },
                "evidence_bundle": {
                    "status": "ready",
                    "source_entries": [
                        {
                            "source_id": "source-1",
                            "title": "memo.md",
                            "provenance": "uploaded_local_artifact",
                        }
                    ],
                },
                "prediction_ledger": {
                    "entries": [{"entry_id": "entry-1"}],
                    "worker_outputs": [{"worker_output_id": "worker-output-1"}],
                    "final_resolution_state": "pending",
                },
                "evaluation_results": {
                    "status": "available",
                    "case_count": 1,
                    "resolved_case_count": 1,
                    "pending_case_count": 0,
                },
                "forecast_answer": {
                    "answer_type": "hybrid_forecast",
                    "answer_payload": {
                        "abstain": False,
                        "best_estimate": {"value": 0.61, "semantics": "forecast_probability"},
                        "worker_contribution_trace": [
                            {"summary": "Simulation remains supporting scenario analysis."}
                        ],
                    },
                },
                "worker_comparison": {
                    "worker_count": 2,
                    "worker_kinds": ["simulation", "base_rate"],
                    "worker_contribution_trace": [
                        {"summary": "Simulation remains supporting scenario analysis."}
                    ],
                    "abstain": False,
                    "best_estimate": {"value": 0.61},
                },
                "truthfulness_surface": {
                    "evidence_available": True,
                    "evaluation_available": True,
                    "calibrated_confidence_earned": False,
                    "simulation_only_scenario_exploration": False,
                },
                "abstain_state": {
                    "abstain": False,
                    "abstain_reason": "",
                    "summary": "Hybrid answer available",
                },
                "resolution_record": {
                    "forecast_id": "forecast-chat",
                    "status": "resolved_true",
                    "resolved_at": "2026-07-01T10:00:00",
                    "resolution_note": "Observed yes.",
                },
                "scoring_events": [
                    {
                        "scoring_event_id": "score-1",
                        "forecast_id": "forecast-chat",
                        "status": "scored",
                        "scoring_method": "brier_score",
                        "score_value": 0.1521,
                        "recorded_at": "2026-07-01T10:05:00",
                    }
                ],
            },
            "forecast_object": {
                "forecast_id": "forecast-chat",
                "status": "available",
                "resolution": {
                    "status": "resolved_true",
                },
                "scoring": {
                    "event_count": 1,
                    "latest_method": "brier_score",
                },
            },
            "selected_run": {
                "run_id": "0001",
                "simulation_market": {
                    "summary": {
                        "artifact_type": "simulation_market_summary",
                        "synthetic_consensus_probability": 0.61,
                        "disagreement_index": 0.18,
                    },
                    "provenance_validation": {
                        "status": "partial",
                        "weight_multiplier": 0.65,
                    },
                },
            },
        },
    )
    report_agent_module.ReportManager.save_report(probabilistic_report)

    class _FakeLLM:
        def __init__(self):
            self.messages = None

        def chat(self, messages, temperature=0.5):
            self.messages = messages
            return "Scoped answer"

    fake_llm = _FakeLLM()
    agent = report_agent_module.ReportAgent(
        graph_id="graph-1",
        simulation_id="sim-chat",
        simulation_requirement="Forecast discussion spread",
        llm_client=fake_llm,
        graph_tools=object(),
        report_id="report-probabilistic-confidence",
        probabilistic_context=probabilistic_report.probabilistic_context,
    )

    response = agent.chat("Can I call this calibrated?")

    assert response["response"] == "Scoped answer"
    system_prompt = fake_llm.messages[0]["content"]
    assert '"confidence_status"' in system_prompt
    assert '"status": "not_ready"' in system_prompt
    assert '"no_supported_binary_metrics"' in system_prompt
    assert '"forecast_workspace"' in system_prompt
    assert '"forecast_object"' in system_prompt
    assert '"resolution"' in system_prompt
    assert '"scoring"' in system_prompt
    assert '"forecast_workspace_status"' in system_prompt
    assert '"abstain_state"' in system_prompt
    assert '"simulation_market_summary"' in system_prompt
    assert '"signal_provenance_summary"' in system_prompt


def test_report_agent_chat_includes_answer_confidence_status_and_ensemble_policy(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    probabilistic_report = report_agent_module.Report(
        report_id="report-probabilistic-answer-confidence",
        simulation_id="sim-chat",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "answer_confidence_status": {
                "status": "ready",
                "confidence_semantics": "calibrated",
                "question_type": "binary",
                "calibration_kind": "binary_reliability",
                "policy_name": "empirically_tuned_worker_ensemble",
                "evidence_regime": "corroborated_local_evidence",
            },
            "forecast_workspace": {
                "forecast_question": {
                    "forecast_id": "forecast-1",
                    "question_text": "Will the upgraded forecast lane remain truthful?",
                    "question_type": "binary",
                },
                "forecast_answer": {
                    "answer_id": "answer-1",
                    "answer_type": "hybrid_forecast",
                    "summary": "Bounded hybrid forecast answer.",
                    "confidence_semantics": "calibrated",
                    "answer_payload": {
                        "best_estimate": {"value": 0.62, "value_type": "probability"},
                        "ensemble_policy": {
                            "policy_name": "empirically_tuned_worker_ensemble",
                            "evidence_regime": {"label": "corroborated_local_evidence"},
                        },
                    },
                },
                "truthfulness_surface": {
                    "calibrated_confidence_earned": True,
                },
            },
        },
    )
    report_agent_module.ReportManager.save_report(probabilistic_report)

    class _FakeLLM:
        def __init__(self):
            self.messages = None

        def chat(self, messages, temperature=0.5):
            self.messages = messages
            return "Scoped answer"

    fake_llm = _FakeLLM()
    agent = report_agent_module.ReportAgent(
        graph_id="graph-1",
        simulation_id="sim-chat",
        simulation_requirement="Forecast discussion spread",
        llm_client=fake_llm,
        graph_tools=object(),
        report_id="report-probabilistic-answer-confidence",
        probabilistic_context=probabilistic_report.probabilistic_context,
    )

    response = agent.chat("What supports confidence in the answer?")

    assert response["response"] == "Scoped answer"
    system_prompt = fake_llm.messages[0]["content"]
    assert '"answer_confidence_status"' in system_prompt
    assert '"policy_name": "empirically_tuned_worker_ensemble"' in system_prompt
    assert '"evidence_regime": "corroborated_local_evidence"' in system_prompt


def test_report_agent_chat_includes_authoritative_scoped_answer_brief(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    probabilistic_report = report_agent_module.Report(
        report_id="report-probabilistic-authoritative-answer-brief",
        simulation_id="sim-chat",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-31T19:16:00",
        completed_at="2026-03-31T19:17:00",
        ensemble_id="0001",
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "run_id": "0001",
            "answer_confidence_status": {
                "status": "not_ready",
                "confidence_semantics": "uncalibrated",
                "question_type": "binary",
                "backtest_status": "not_run",
                "calibration_status": "not_applicable",
                "policy_name": "empirically_tuned_worker_ensemble",
                "evidence_regime": "corroborated_local_evidence",
            },
            "forecast_workspace": {
                "forecast_question": {
                    "forecast_id": "forecast-1",
                    "question_text": "Will the upgraded forecast lane remain truthful?",
                    "question_type": "binary",
                },
                "forecast_answer": {
                    "answer_id": "answer-1",
                    "answer_type": "hybrid_forecast",
                    "summary": "Bounded hybrid forecast answer.",
                    "confidence_semantics": "uncalibrated",
                    "backtest_summary": {"status": "not_run"},
                    "calibration_summary": {"status": "not_applicable"},
                    "answer_payload": {
                        "best_estimate": {
                            "value": 0.666926,
                            "value_type": "probability",
                            "semantics": "forecast_probability",
                        },
                        "ensemble_policy": {
                            "policy_name": "empirically_tuned_worker_ensemble",
                            "evidence_regime": {"label": "corroborated_local_evidence"},
                        },
                    },
                },
                "truthfulness_surface": {
                    "calibrated_confidence_earned": False,
                },
            },
        },
    )
    report_agent_module.ReportManager.save_report(probabilistic_report)

    class _FakeLLM:
        def __init__(self):
            self.messages = None

        def chat(self, messages, temperature=0.5):
            self.messages = messages
            return "Scoped answer"

    fake_llm = _FakeLLM()
    agent = report_agent_module.ReportAgent(
        graph_id="graph-1",
        simulation_id="sim-chat",
        simulation_requirement="Forecast discussion spread",
        llm_client=fake_llm,
        graph_tools=object(),
        report_id="report-probabilistic-authoritative-answer-brief",
        probabilistic_context=probabilistic_report.probabilistic_context,
    )

    response = agent.chat("What is the actual saved probability and confidence status?")

    assert response["response"] == "Scoped answer"
    system_prompt = fake_llm.messages[0]["content"]
    assert "Authoritative scoped forecast answer facts" in system_prompt
    assert '"best_estimate_probability": 0.666926' in system_prompt
    assert '"answer_confidence_status": "not_ready"' in system_prompt
    assert '"confidence_semantics": "uncalibrated"' in system_prompt
    assert '"backtest_status": "not_run"' in system_prompt
    assert '"calibration_status": "not_applicable"' in system_prompt
    assert '"ensemble_policy_name": "empirically_tuned_worker_ensemble"' in system_prompt
    assert '"evidence_regime": "corroborated_local_evidence"' in system_prompt


def test_report_agent_generate_report_persists_report_phase_timings(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    outline = report_agent_module.ReportOutline(
        title="Forecast Report",
        summary="Observed outcomes across the ensemble.",
        sections=[
            report_agent_module.ReportSection(title="Executive Summary"),
            report_agent_module.ReportSection(title="Signals"),
        ],
    )

    monkeypatch.setattr(
        report_agent_module.ReportAgent,
        "plan_outline",
        lambda self, progress_callback=None: outline,
    )
    monkeypatch.setattr(
        report_agent_module.ReportAgent,
        "_generate_section_react",
        lambda self, section, outline, previous_sections, progress_callback, section_index: (
            f"Section {section_index} content."
        ),
    )

    agent = report_agent_module.ReportAgent(
        graph_id="graph-1",
        simulation_id="sim-report",
        simulation_requirement="Forecast discussion spread",
        llm_client=object(),
        graph_tools=object(),
    )

    report = agent.generate_report(report_id="report-phase-timing")

    assert report.status == report_agent_module.ReportStatus.COMPLETED
    timing_payload = json.loads(
        (
            reports_dir / "report-phase-timing" / "report_phase_timings.json"
        ).read_text(encoding="utf-8")
    )
    assert timing_payload["scope_kind"] == "report"
    assert timing_payload["scope_id"] == "report-phase-timing"
    assert "report_synthesis" in timing_payload["phases"]


def test_report_chat_endpoint_passes_explicit_report_scope_to_agent(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    scoped_report = report_agent_module.Report(
        report_id="report-chat-scope",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        base_graph_id="graph-1",
        runtime_graph_id="runtime-graph-1",
        graph_ids=["graph-1", "runtime-graph-1"],
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-09T10:10:00",
        completed_at="2026-03-09T10:11:00",
        ensemble_id=created["ensemble_id"],
        cluster_id="cluster_0001",
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": created["ensemble_id"],
            "cluster_id": "cluster_0001",
            "run_id": "0001",
        },
    )
    report_agent_module.ReportManager.save_report(scoped_report)

    captures = {}

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            report_id,
            probabilistic_context,
            **kwargs,
        ):
            captures["graph_id"] = graph_id
            captures["simulation_id"] = simulation_id
            captures["simulation_requirement"] = simulation_requirement
            captures["report_id"] = report_id
            captures["probabilistic_context"] = probabilistic_context
            captures["base_graph_id"] = kwargs.get("base_graph_id")
            captures["runtime_graph_id"] = kwargs.get("runtime_graph_id")
            captures["graph_ids"] = kwargs.get("graph_ids")

        def chat(self, message, chat_history=None):
            captures["message"] = message
            captures["chat_history"] = chat_history
            return {
                "response": "Scoped reply",
                "tool_calls": [],
                "sources": [],
            }

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "report_id": scoped_report.report_id,
            "message": "What does the ensemble show?",
            "chat_history": [
                {"role": "user", "content": "Earlier question"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["response"] == "Scoped reply"
    assert captures["report_id"] == scoped_report.report_id
    assert captures["probabilistic_context"]["ensemble_id"] == created["ensemble_id"]
    assert captures["probabilistic_context"]["cluster_id"] == "cluster_0001"
    assert captures["base_graph_id"] == "graph-1"
    assert captures["runtime_graph_id"] == "runtime-graph-1"
    assert captures["graph_ids"] == ["graph-1", "runtime-graph-1"]
    assert captures["message"] == "What does the ensemble show?"
    assert captures["chat_history"] == [{"role": "user", "content": "Earlier question"}]


def test_report_chat_endpoint_can_override_saved_run_scope_and_apply_compare_selection(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    scoped_report = report_agent_module.Report(
        report_id="report-chat-scope-override",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        base_graph_id="graph-1",
        runtime_graph_id="runtime-graph-1",
        graph_ids=["graph-1", "runtime-graph-1"],
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-09T10:10:00",
        completed_at="2026-03-09T10:11:00",
        ensemble_id=created["ensemble_id"],
        cluster_id="cluster_0001",
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": created["ensemble_id"],
            "cluster_id": "cluster_0001",
            "run_id": "0001",
            "scope": {
                "level": "run",
                "ensemble_id": created["ensemble_id"],
                "cluster_id": "cluster_0001",
                "run_id": "0001",
            },
        },
    )
    report_agent_module.ReportManager.save_report(scoped_report)

    captures = {}

    class _FakeContextBuilder:
        def build_context(self, simulation_id, ensemble_id, cluster_id=None, run_id=None):
            captures["rebuilt_scope"] = (
                simulation_id,
                ensemble_id,
                cluster_id,
                run_id,
            )
            return {
                "artifact_type": "probabilistic_report_context",
                "ensemble_id": ensemble_id,
                "cluster_id": cluster_id,
                "run_id": run_id,
                "scope": {
                    "level": "ensemble",
                    "ensemble_id": ensemble_id,
                    "cluster_id": None,
                    "run_id": None,
                },
                "compare_catalog": {
                    "boundary_note": "Compare only scopes inside one saved report context and one ensemble.",
                    "options": [
                        {
                            "compare_id": f"run-0001__ensemble-{ensemble_id}",
                            "label": "Run 0001 vs ensemble",
                            "left_scope": {
                                "level": "run",
                                "ensemble_id": ensemble_id,
                                "cluster_id": "cluster_0001",
                                "run_id": "0001",
                            },
                            "right_scope": {
                                "level": "ensemble",
                                "ensemble_id": ensemble_id,
                                "cluster_id": None,
                                "run_id": None,
                            },
                            "left_snapshot": {
                                "scope": {
                                    "level": "run",
                                    "ensemble_id": ensemble_id,
                                    "cluster_id": "cluster_0001",
                                    "run_id": "0001",
                                },
                                "headline": "Run 0001",
                            },
                            "right_snapshot": {
                                "scope": {
                                    "level": "ensemble",
                                    "ensemble_id": ensemble_id,
                                    "cluster_id": None,
                                    "run_id": None,
                                },
                                "headline": f"Ensemble {ensemble_id}",
                            },
                            "comparison_summary": {
                                "what_differs": ["Observed run versus empirical ensemble"],
                                "weak_support": [],
                                "boundary_note": "Do not treat this comparison as causal.",
                            },
                            "warnings": [],
                            "prompt": "Explain how run 0001 differs from the ensemble.",
                        }
                    ],
                },
            }

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            report_id,
            probabilistic_context,
            **kwargs,
        ):
            captures["probabilistic_context"] = probabilistic_context
            captures["report_id"] = report_id

        def chat(self, message, chat_history=None):
            captures["message"] = message
            return {
                "response": "Scoped override reply",
                "tool_calls": [],
                "sources": [],
            }

    monkeypatch.setattr(
        report_module,
        "ProbabilisticReportContextBuilder",
        _FakeContextBuilder,
    )
    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "report_id": scoped_report.report_id,
            "ensemble_id": created["ensemble_id"],
            "scope_level": "ensemble",
            "compare_id": f"run-0001__ensemble-{created['ensemble_id']}",
            "message": "Compare the saved run against the ensemble.",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    assert captures["rebuilt_scope"] == (
        state.simulation_id,
        created["ensemble_id"],
        None,
        None,
    )
    assert captures["probabilistic_context"]["scope"]["level"] == "ensemble"
    assert captures["probabilistic_context"]["run_id"] is None
    assert (
        captures["probabilistic_context"]["selected_compare"]["compare_id"]
        == f"run-0001__ensemble-{created['ensemble_id']}"
    )
    assert captures["message"] == "Compare the saved run against the ensemble."


def test_probabilistic_report_chat_requires_interaction_flag(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.SimulationManager,
        "get_simulation",
        lambda _self, _simulation_id: type(
            "State",
            (),
            {
                "simulation_id": state.simulation_id,
                "project_id": "proj-1",
                "graph_id": "graph-1",
            },
        )(),
        raising=False,
    )

    scoped_report = report_agent_module.Report(
        report_id="report-chat-flagged-off",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n\nObserved ensemble summary.\n",
        created_at="2026-03-10T13:10:00",
        completed_at="2026-03-10T13:11:00",
        ensemble_id=created["ensemble_id"],
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
        },
    )
    report_agent_module.ReportManager.save_report(scoped_report)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "report_id": scoped_report.report_id,
            "message": "What does the saved report show?",
        },
    )

    assert response.status_code == 409
    assert "Probabilistic report interaction is disabled" in response.get_json()["error"]


def test_probabilistic_report_chat_builds_scoped_context_without_saved_report(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    report_module = _load_report_api_module()

    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.SimulationManager,
        "get_simulation",
        lambda _self, _simulation_id: type(
            "State",
            (),
            {
                "simulation_id": state.simulation_id,
                "project_id": "proj-1",
                "graph_id": "graph-1",
            },
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    expected_context = {
        "artifact_type": "probabilistic_report_context",
        "ensemble_id": created["ensemble_id"],
        "run_id": "0001",
        "scope": {"level": "run"},
    }
    captures = {}

    class _FakeContextBuilder:
        def build_context(self, simulation_id, ensemble_id, run_id=None):
            captures["context_scope"] = (simulation_id, ensemble_id, run_id)
            return expected_context

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            report_id,
            probabilistic_context,
            **kwargs,
        ):
            captures["probabilistic_context"] = probabilistic_context

        def chat(self, message, chat_history=None):
            return {
                "response": "Scoped probabilistic chat reply",
                "tool_calls": [],
                "sources": [],
            }

    monkeypatch.setattr(
        report_module,
        "ProbabilisticReportContextBuilder",
        _FakeContextBuilder,
    )
    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": created["ensemble_id"],
            "run_id": "0001",
            "message": "Compare the selected run to the representative runs.",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    assert captures["context_scope"] == (state.simulation_id, created["ensemble_id"], "0001")
    assert captures["probabilistic_context"] == expected_context


def test_probabilistic_report_generation_reuses_existing_exact_scope_not_latest_report(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(report_module.ReportManager, "REPORTS_DIR", str(reports_dir))
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.SimulationManager,
        "get_simulation",
        lambda _self, _simulation_id: type(
            "State",
            (),
            {
                "simulation_id": state.simulation_id,
                "project_id": "proj-1",
                "graph_id": "graph-1",
            },
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    scoped_report = report_agent_module.Report(
        report_id="report-existing-scope",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Scoped report body\n",
        created_at="2026-03-10T13:01:00",
        completed_at="2026-03-10T13:02:00",
        ensemble_id="0004",
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0004",
            "run_id": "0001",
        },
    )
    newer_unscoped_report = report_agent_module.Report(
        report_id="report-newer-legacy",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Newer legacy report body\n",
        created_at="2026-03-10T13:05:00",
        completed_at="2026-03-10T13:06:00",
    )
    report_agent_module.ReportManager.save_report(scoped_report)
    report_agent_module.ReportManager.save_report(newer_unscoped_report)

    class _UnexpectedReportAgent:
        def __init__(self, *args, **kwargs):
            raise AssertionError("generate_report should reuse the existing exact-scope report")

    monkeypatch.setattr(report_module, "ReportAgent", _UnexpectedReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": "0004",
            "run_id": "0001",
            "force_regenerate": False,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_generated"] is True
    assert payload["report_id"] == scoped_report.report_id


def test_report_lookup_and_endpoints_prefer_latest_report_when_directory_order_is_shuffled(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    legacy_report = report_agent_module.Report(
        report_id="report-selection-legacy",
        simulation_id="sim-selection",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Legacy report body\n",
        created_at="2026-03-09T10:00:00",
        completed_at="2026-03-09T10:01:00",
    )
    probabilistic_report = report_agent_module.Report(
        report_id="report-selection-probabilistic",
        simulation_id="sim-selection",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        run_id="0002",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "run_id": "0002",
        },
    )
    report_agent_module.ReportManager.save_report(legacy_report)
    report_agent_module.ReportManager.save_report(probabilistic_report)

    def _shuffled_listdir(_path):
        return [
            legacy_report.report_id,
            probabilistic_report.report_id,
        ]

    monkeypatch.setattr(report_agent_module.os, "listdir", _shuffled_listdir)

    direct_lookup = report_agent_module.ReportManager.get_report_by_simulation(
        "sim-selection"
    )
    assert direct_lookup is not None
    assert direct_lookup.report_id == probabilistic_report.report_id

    client = _build_test_client(report_module)

    by_simulation_response = client.get("/api/report/by-simulation/sim-selection")
    assert by_simulation_response.status_code == 200
    assert (
        by_simulation_response.get_json()["data"]["report_id"]
        == probabilistic_report.report_id
    )

    status_response = client.post(
        "/api/report/generate/status",
        json={"simulation_id": "sim-selection"},
    )
    assert status_response.status_code == 200
    assert (
        status_response.get_json()["data"]["report_id"]
        == probabilistic_report.report_id
    )

    check_response = client.get("/api/report/check/sim-selection")
    assert check_response.status_code == 200
    assert check_response.get_json()["data"]["report_id"] == probabilistic_report.report_id


def test_generate_status_uses_exact_probabilistic_scope_instead_of_latest_report(
    tmp_path, monkeypatch
):
    report_agent_module = _load_report_agent_module()
    report_module = _load_report_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    exact_scope_report = report_agent_module.Report(
        report_id="report-status-exact-scope",
        simulation_id="sim-status-scope",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Exact-scope report body\n",
        created_at="2026-03-09T10:01:00",
        completed_at="2026-03-09T10:02:00",
        ensemble_id="0004",
        run_id="0001",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0004",
            "run_id": "0001",
        },
    )
    newer_latest_report = report_agent_module.Report(
        report_id="report-status-latest",
        simulation_id="sim-status-scope",
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Later report body\n",
        created_at="2026-03-09T10:05:00",
        completed_at="2026-03-09T10:06:00",
        ensemble_id="0009",
        run_id="0007",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0009",
            "run_id": "0007",
        },
    )
    report_agent_module.ReportManager.save_report(exact_scope_report)
    report_agent_module.ReportManager.save_report(newer_latest_report)

    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/generate/status",
        json={
            "simulation_id": "sim-status-scope",
            "ensemble_id": "0004",
            "run_id": "0001",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["already_completed"] is True
    assert payload["report_id"] == exact_scope_report.report_id


def test_legacy_report_chat_stays_available_when_interaction_flag_is_off(
    simulation_data_dir, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    report_module = _load_report_api_module()

    monkeypatch.setattr(
        report_module.Config,
        "PROBABILISTIC_INTERACTION_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        report_module.SimulationManager,
        "get_simulation",
        lambda _self, _simulation_id: type(
            "State",
            (),
            {
                "simulation_id": state.simulation_id,
                "project_id": "proj-1",
                "graph_id": "graph-1",
            },
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    captures = {}

    class _FakeReportAgent:
        def __init__(
            self,
            graph_id,
            simulation_id,
            simulation_requirement,
            report_id,
            probabilistic_context,
            **kwargs,
        ):
            captures["graph_id"] = graph_id
            captures["simulation_id"] = simulation_id
            captures["simulation_requirement"] = simulation_requirement
            captures["report_id"] = report_id
            captures["probabilistic_context"] = probabilistic_context

        def chat(self, message, chat_history=None):
            captures["message"] = message
            captures["chat_history"] = chat_history
            return {
                "response": "Legacy reply",
                "tool_calls": [],
                "sources": [],
            }

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)
    client = _build_test_client(report_module)

    response = client.post(
        "/api/report/chat",
        json={
            "simulation_id": state.simulation_id,
            "message": "What does the single run show?",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["response"] == "Legacy reply"
    assert captures["report_id"] is None
    assert captures["probabilistic_context"] is None


def test_simulation_history_returns_latest_report_replay_metadata(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    simulation_module = _load_simulation_api_module()
    report_agent_module = _load_report_agent_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    legacy_report = report_agent_module.Report(
        report_id="report-history-legacy",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Legacy report body\n",
        created_at="2026-03-09T10:00:00",
        completed_at="2026-03-09T10:01:00",
    )
    probabilistic_report = report_agent_module.Report(
        report_id="report-history-probabilistic",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        run_id="0002",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "run_id": "0002",
        },
    )
    report_agent_module.ReportManager.save_report(legacy_report)
    report_agent_module.ReportManager.save_report(probabilistic_report)

    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        lambda _project_id: type("Project", (), {"files": []})(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.os.path,
        "dirname",
        lambda _path: str(tmp_path / "backend" / "app" / "api"),
    )

    client = _build_simulation_test_client(simulation_module)
    response = client.get("/api/simulation/history?limit=1")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert len(payload) == 1
    assert payload[0]["report_id"] == "report-history-probabilistic"
    assert payload[0]["latest_report"] == {
        "report_id": "report-history-probabilistic",
        "created_at": "2026-03-09T10:02:00",
        "ensemble_id": "0001",
        "run_id": "0002",
        "has_probabilistic_context": True,
    }
    assert payload[0]["latest_probabilistic_runtime"] == {
        "source": "report",
        "report_id": "report-history-probabilistic",
        "ensemble_id": "0001",
        "run_id": "0002",
        "has_probabilistic_context": True,
        "run_status": "completed",
        "run_updated_at": None,
    }


def test_simulation_history_preserves_probabilistic_step3_reentry_when_latest_report_is_legacy(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    simulation_module = _load_simulation_api_module()
    report_agent_module = _load_report_agent_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )

    probabilistic_report = report_agent_module.Report(
        report_id="report-history-probabilistic",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Probabilistic report body\n",
        created_at="2026-03-09T10:02:00",
        completed_at="2026-03-09T10:03:00",
        ensemble_id="0001",
        run_id="0002",
        probabilistic_context={
            "artifact_type": "probabilistic_report_context",
            "ensemble_id": "0001",
            "run_id": "0002",
        },
    )
    legacy_report = report_agent_module.Report(
        report_id="report-history-legacy-newest",
        simulation_id=state.simulation_id,
        graph_id="graph-1",
        simulation_requirement="Forecast discussion spread",
        status=report_agent_module.ReportStatus.COMPLETED,
        markdown_content="# Legacy report body\n",
        created_at="2026-03-09T10:05:00",
        completed_at="2026-03-09T10:06:00",
    )
    report_agent_module.ReportManager.save_report(probabilistic_report)
    report_agent_module.ReportManager.save_report(legacy_report)

    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        lambda _project_id: type("Project", (), {"files": []})(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.os.path,
        "dirname",
        lambda _path: str(tmp_path / "backend" / "app" / "api"),
    )

    client = _build_simulation_test_client(simulation_module)
    response = client.get("/api/simulation/history?limit=1")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert len(payload) == 1
    assert payload[0]["report_id"] == "report-history-legacy-newest"
    assert payload[0]["latest_report"] == {
        "report_id": "report-history-legacy-newest",
        "created_at": "2026-03-09T10:05:00",
        "ensemble_id": None,
        "run_id": None,
        "has_probabilistic_context": False,
    }
    assert payload[0]["latest_probabilistic_runtime"] == {
        "source": "report",
        "report_id": "report-history-probabilistic",
        "ensemble_id": "0001",
        "run_id": "0002",
        "has_probabilistic_context": True,
        "run_status": "completed",
        "run_updated_at": None,
    }


def test_simulation_history_falls_back_to_latest_probabilistic_storage_reentry_without_reports(
    simulation_data_dir, tmp_path, monkeypatch
):
    state = _prepare_probabilistic_simulation(simulation_data_dir, monkeypatch)
    created = _create_probabilistic_ensemble(
        simulation_data_dir,
        monkeypatch,
        state.simulation_id,
    )
    simulation_module = _load_simulation_api_module()

    run_dir = (
        Path(simulation_data_dir)
        / state.simulation_id
        / "ensemble"
        / f"ensemble_{created['ensemble_id']}"
        / "runs"
    )
    run_one_manifest_path = run_dir / "run_0001" / "run_manifest.json"
    run_two_manifest_path = run_dir / "run_0002" / "run_manifest.json"
    run_one_manifest = json.loads(run_one_manifest_path.read_text(encoding="utf-8"))
    run_two_manifest = json.loads(run_two_manifest_path.read_text(encoding="utf-8"))
    run_one_manifest["updated_at"] = "2026-03-09T10:03:00"
    run_two_manifest["updated_at"] = "2026-03-09T10:04:00"
    _write_json(run_one_manifest_path, run_one_manifest)
    _write_json(run_two_manifest_path, run_two_manifest)

    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        lambda _project_id: type("Project", (), {"files": []})(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.os.path,
        "dirname",
        lambda _path: str(tmp_path / "backend" / "app" / "api"),
    )

    client = _build_simulation_test_client(simulation_module)
    response = client.get("/api/simulation/history?limit=1")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert len(payload) == 1
    assert payload[0]["report_id"] is None
    assert payload[0]["latest_report"] is None
    assert payload[0]["latest_probabilistic_runtime"] == {
        "source": "storage",
        "report_id": None,
        "ensemble_id": "0001",
        "run_id": "0002",
        "has_probabilistic_context": False,
        "run_status": "completed",
        "run_updated_at": "2026-03-09T10:04:00",
    }


def test_simulation_history_sorts_newest_records_first(monkeypatch):
    manager_module = _load_manager_module()
    simulation_module = _load_simulation_api_module()

    older = manager_module.SimulationState(
        simulation_id="sim-older",
        project_id="proj-1",
        graph_id="graph-1",
        created_at="2026-03-09T10:00:00",
        updated_at="2026-03-09T10:00:00",
    )
    newer = manager_module.SimulationState(
        simulation_id="sim-newer",
        project_id="proj-2",
        graph_id="graph-2",
        created_at="2026-03-09T10:05:00",
        updated_at="2026-03-09T10:05:00",
    )

    monkeypatch.setattr(
        simulation_module.SimulationManager,
        "list_simulations",
        lambda self, project_id=None, include_archived=False: [older, newer],
    )
    monkeypatch.setattr(
        simulation_module.SimulationManager,
        "get_simulation_config",
        lambda self, simulation_id: {
            "simulation_requirement": f"Requirement for {simulation_id}",
            "time_config": {
                "total_simulation_hours": 24,
                "minutes_per_round": 60,
            },
        },
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda _simulation_id: None,
    )
    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        lambda _project_id: type("Project", (), {"files": []})(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module,
        "_get_latest_report_summary_for_simulation",
        lambda simulation_id: {
            "report_id": f"report-for-{simulation_id}",
            "created_at": "2026-03-09T10:06:00",
            "ensemble_id": None,
            "run_id": None,
            "has_probabilistic_context": False,
        },
    )

    client = _build_simulation_test_client(simulation_module)
    response = client.get("/api/simulation/history?limit=2")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert [item["simulation_id"] for item in payload] == [
        newer.simulation_id,
        older.simulation_id,
    ]


def test_simulation_history_excludes_archived_simulations_by_default(
    simulation_data_dir, monkeypatch
):
    manager_module = _load_manager_module()
    simulation_module = _load_simulation_api_module()
    _configure_simulation_data_dir(monkeypatch, simulation_data_dir, manager_module)

    manager = manager_module.SimulationManager()

    active = manager_module.SimulationState(
        simulation_id="sim-active",
        project_id="proj-active",
        graph_id="graph-active",
        created_at="2026-03-29T10:05:00",
        updated_at="2026-03-29T10:05:00",
    )
    archived = manager_module.SimulationState(
        simulation_id="sim-archived",
        project_id="proj-archived",
        graph_id="graph-archived",
        created_at="2026-03-29T10:06:00",
        updated_at="2026-03-29T10:06:00",
    )
    manager._save_simulation_state(active)
    manager._save_simulation_state(archived)
    _write_forecast_archive(
        Path(simulation_data_dir) / archived.simulation_id,
        reason="Nonconforming pre-contract probabilistic artifacts.",
    )

    monkeypatch.setattr(
        simulation_module.ProjectManager,
        "get_project",
        lambda _project_id: type("Project", (), {"files": []})(),
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda _simulation_id: None,
    )
    monkeypatch.setattr(
        simulation_module,
        "_get_latest_report_summary_for_simulation",
        lambda simulation_id: None,
    )
    monkeypatch.setattr(
        simulation_module,
        "_get_latest_probabilistic_runtime_summary_for_simulation",
        lambda simulation_id: None,
    )

    client = _build_simulation_test_client(simulation_module)

    response = client.get("/api/simulation/history?limit=5")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert [item["simulation_id"] for item in payload] == ["sim-active"]

    archived_response = client.get("/api/simulation/history?limit=5&include_archived=true")

    assert archived_response.status_code == 200
    archived_payload = archived_response.get_json()["data"]
    assert [item["simulation_id"] for item in archived_payload] == [
        "sim-archived",
        "sim-active",
    ]
    assert archived_payload[0]["forecast_archive"] == {
        "artifact_type": "forecast_archive",
        "schema_version": "forecast.archive.v1",
        "archived_at": "2026-03-29T12:00:00",
        "archive_scope": "historical_read_only",
        "reason": "Nonconforming pre-contract probabilistic artifacts.",
    }
