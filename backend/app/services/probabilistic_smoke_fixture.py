"""
Developer-only probabilistic smoke-fixture seeding.

This module creates a prepared probabilistic simulation without relying on the
live Zep graph or LLM-backed configuration/profile generators. It exists to
support deterministic local QA and browser smoke evidence for the Step 2 ->
Step 3 probabilistic handoff.
"""

from __future__ import annotations

import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..config import Config
from ..models.probabilistic import EnsembleSpec
from ..models.project import ProjectManager, ProjectStatus
from .oasis_profile_generator import OasisAgentProfile, OasisProfileGenerator
from . import simulation_manager as simulation_manager_module
from .ensemble_manager import EnsembleManager
from .simulation_manager import SimulationManager
from .zep_entity_reader import EntityNode, FilteredEntities


DEFAULT_PROJECT_NAME = "Probabilistic Smoke Fixture"
DEFAULT_GRAPH_ID = ""
DEFAULT_SIMULATION_REQUIREMENT = (
    "Smoke-test the probabilistic Step 2 to Step 3 handoff with one prepared "
    "simulation and deterministic seeded ensemble setup."
)
DEFAULT_DOCUMENT_TEXT = (
    "This is a synthetic probabilistic smoke fixture used for local browser "
    "verification. It is empirical-only and does not imply calibrated results."
)
DEFAULT_OUTCOME_METRICS = [
    "simulation.total_actions",
    "platform.twitter.total_actions",
]
FIXTURE_REPORT_CREATED_AT = "2026-03-09T12:30:00"
FIXTURE_REPORT_COMPLETED_AT = "2026-03-09T12:31:00"


class _FixtureProfileGenerator:
    """Profile generator stub that avoids external calls during smoke seeding."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def generate_profiles_from_entities(self, *args, **kwargs) -> list[OasisAgentProfile]:
        return [
            OasisAgentProfile(
                user_id=0,
                user_name="agent_one",
                name="Agent One",
                bio="Synthetic smoke-fixture participant",
                persona=(
                    "Agent One is a deterministic analyst persona used for local "
                    "probabilistic runtime verification."
                ),
                friend_count=120,
                follower_count=180,
                statuses_count=360,
                profession="Analyst",
                interested_topics=["Forecasting", "Simulation"],
                source_entity_uuid="entity-1",
                source_entity_type="Person",
            ),
            OasisAgentProfile(
                user_id=1,
                user_name="agent_two",
                name="Agent Two",
                bio="Synthetic smoke-fixture participant",
                persona=(
                    "Agent Two is a deterministic analyst persona used for local "
                    "probabilistic runtime verification."
                ),
                friend_count=90,
                follower_count=140,
                statuses_count=280,
                profession="Analyst",
                interested_topics=["Forecasting", "Simulation"],
                source_entity_uuid="entity-2",
                source_entity_type="Person",
            ),
        ]

    def save_profiles(self, profiles, file_path: str, platform: str) -> None:
        serializer = OasisProfileGenerator.__new__(OasisProfileGenerator)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if platform == "twitter":
            serializer._save_twitter_csv(profiles, file_path)
            return
        serializer._save_reddit_json(profiles, file_path)


class _FixtureSimulationParameters:
    """Minimal deterministic config payload that satisfies prepare contracts."""

    def __init__(
        self,
        *,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
    ) -> None:
        self.generation_reasoning = (
            "Synthetic smoke-fixture configuration. This payload is developer-only "
            "and exists to support deterministic browser verification."
        )
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
                    "entity_name": "Analyst One",
                    "entity_type": "Person",
                    "activity_level": 0.45,
                    "posts_per_hour": 1.0,
                    "comments_per_hour": 1.0,
                    "active_hours": [8, 9, 10],
                    "response_delay_min": 5,
                    "response_delay_max": 15,
                    "sentiment_bias": 0.0,
                    "stance": "neutral",
                    "influence_weight": 1.0,
                },
                {
                    "agent_id": 1,
                    "entity_uuid": "entity-2",
                    "entity_name": "Analyst Two",
                    "entity_type": "Person",
                    "activity_level": 0.55,
                    "posts_per_hour": 1.2,
                    "comments_per_hour": 0.8,
                    "active_hours": [9, 10, 11],
                    "response_delay_min": 4,
                    "response_delay_max": 12,
                    "sentiment_bias": 0.1,
                    "stance": "supportive",
                    "influence_weight": 1.2,
                },
            ],
            "event_config": {
                "initial_posts": [],
                "scheduled_events": [],
                "hot_topics": ["seeded-smoke"],
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
            "generated_at": "2026-03-09T12:00:00",
            "generation_reasoning": self.generation_reasoning,
        }

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self.payload))


class _FixtureSimulationConfigGenerator:
    """Config-generator stub that returns one deterministic config payload."""

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def generate_config(self, **kwargs) -> _FixtureSimulationParameters:
        return _FixtureSimulationParameters(
            simulation_id=kwargs["simulation_id"],
            project_id=kwargs["project_id"],
            graph_id=kwargs["graph_id"],
            simulation_requirement=kwargs["simulation_requirement"],
        )


class _FixtureReader:
    """Zep-reader stub that returns a small deterministic entity set."""

    def filter_defined_entities(self, *args, **kwargs) -> FilteredEntities:
        return FilteredEntities(
            entities=[
                EntityNode(
                    uuid="entity-1",
                    name="Analyst One",
                    labels=["Entity", "Person"],
                    summary="Synthetic smoke-fixture analyst",
                    attributes={"role": "analyst"},
                ),
                EntityNode(
                    uuid="entity-2",
                    name="Analyst Two",
                    labels=["Entity", "Person"],
                    summary="Synthetic smoke-fixture analyst",
                    attributes={"role": "analyst"},
                ),
            ],
            entity_types={"Person"},
            total_count=2,
            filtered_count=2,
        )


def _normalize_metrics(outcome_metrics: Optional[Iterable[str]]) -> list[str]:
    metrics = [metric for metric in (outcome_metrics or DEFAULT_OUTCOME_METRICS) if metric]
    if not metrics:
        raise ValueError("outcome_metrics must contain at least one metric")
    return metrics


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _seed_completed_run_artifacts(
    *,
    simulation_data_dir: str,
    simulation_id: str,
    ensemble_id: str,
    run_ids: list[str],
) -> None:
    """Seed deterministic completed-run metrics so report-context artifacts are meaningful."""
    base_actions = 4
    for offset, run_id in enumerate(run_ids, start=1):
        run_dir = (
            Path(simulation_data_dir)
            / simulation_id
            / "ensemble"
            / f"ensemble_{ensemble_id}"
            / "runs"
            / f"run_{run_id}"
        )
        manifest_path = run_dir / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        total_actions = base_actions + (offset - 1) * 3
        twitter_actions = max(1, total_actions - 2)

        manifest["status"] = "completed"
        manifest["generated_at"] = f"2026-03-09T12:00:{offset:02d}"
        manifest["updated_at"] = manifest["generated_at"]
        _write_json(manifest_path, manifest)
        _write_json(
            run_dir / "metrics.json",
            {
                "artifact_type": "run_metrics",
                "schema_version": "probabilistic.metrics.v1",
                "generator_version": "probabilistic.metrics.generator.v1",
                "quality_checks": {
                    "status": "complete",
                    "run_status": "completed",
                    "warnings": [],
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
                "top_topics": [{"topic": "seeded-smoke", "count": total_actions}],
                "extracted_at": f"2026-03-09T12:10:{offset:02d}",
            },
        )


def _seed_completed_probabilistic_report(
    *,
    simulation_id: str,
    graph_id: str,
    simulation_requirement: str,
    ensemble_id: str,
    run_id: str,
) -> Dict[str, Any]:
    """Persist one synthetic completed report with embedded probabilistic context."""
    from .probabilistic_report_context import ProbabilisticReportContextBuilder
    from .report_agent import (
        Report,
        ReportManager,
        ReportOutline,
        ReportSection,
        ReportStatus,
    )

    ReportManager.REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, "reports")
    probabilistic_context = ProbabilisticReportContextBuilder().build_context(
        simulation_id=simulation_id,
        ensemble_id=ensemble_id,
        run_id=run_id,
    )
    report_id = f"smoke-{simulation_id}-{ensemble_id}-{run_id}"
    report = Report(
        report_id=report_id,
        simulation_id=simulation_id,
        graph_id=graph_id,
        simulation_requirement=simulation_requirement,
        status=ReportStatus.COMPLETED,
        outline=ReportOutline(
            title="Probabilistic Smoke Report",
            summary=(
                "Developer-only report body with observed empirical ensemble context. "
                "This fixture does not imply calibrated probabilities."
            ),
            sections=[
                ReportSection(
                    title="Summary",
                    content=(
                        "This synthetic report preserves the legacy body and attaches "
                        "observed empirical ensemble context for smoke testing."
                    ),
                )
            ],
        ),
        markdown_content=(
            "# Probabilistic Smoke Report\n\n"
            "This developer-only fixture keeps the legacy report body and adds "
            "observed empirical ensemble context.\n"
        ),
        created_at=FIXTURE_REPORT_CREATED_AT,
        completed_at=FIXTURE_REPORT_COMPLETED_AT,
        ensemble_id=ensemble_id,
        run_id=run_id,
        probabilistic_context=probabilistic_context,
    )
    ReportManager.save_report(report)
    return {
        "report_id": report_id,
        "report_dir": ReportManager._get_report_folder(report_id),
        "report_route": (
            f"/report/{report_id}"
            f"?mode=probabilistic&ensembleId={ensemble_id}&runId={run_id}"
        ),
        "interaction_route": (
            f"/interaction/{report_id}"
            f"?mode=probabilistic&ensembleId={ensemble_id}&runId={run_id}"
        ),
        "ensemble_id": ensemble_id,
        "run_id": run_id,
    }


def seed_probabilistic_smoke_fixture(
    *,
    project_name: str = DEFAULT_PROJECT_NAME,
    graph_id: str = DEFAULT_GRAPH_ID,
    simulation_requirement: str = DEFAULT_SIMULATION_REQUIREMENT,
    document_text: str = DEFAULT_DOCUMENT_TEXT,
    uncertainty_profile: str = "balanced",
    outcome_metrics: Optional[Iterable[str]] = None,
    create_ensemble_run_count: int = 0,
    ensemble_root_seed: int = 101,
    seed_completed_report: bool = False,
    report_run_id: Optional[str] = None,
    projects_dir: Optional[str] = None,
    simulation_data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Seed one deterministic probabilistic simulation for local smoke testing.

    When `create_ensemble_run_count` is greater than zero, the helper also
    materializes a stored ensemble under the prepared simulation so Step 3, Step
    4, or report flows can be exercised without running the live prepare path.
    Leave `graph_id` empty to avoid unrelated graph-panel fetch failures during
    the developer-only Step 2 -> Step 3 browser smoke.
    """

    if create_ensemble_run_count < 0:
        raise ValueError("create_ensemble_run_count must be >= 0")
    if seed_completed_report and create_ensemble_run_count <= 0:
        raise ValueError(
            "seed_completed_report requires create_ensemble_run_count > 0"
        )

    normalized_metrics = _normalize_metrics(outcome_metrics)

    with ExitStack() as stack:
        if projects_dir is not None:
            stack.callback(setattr, ProjectManager, "PROJECTS_DIR", ProjectManager.PROJECTS_DIR)
            ProjectManager.PROJECTS_DIR = projects_dir

        if simulation_data_dir is not None:
            stack.callback(setattr, Config, "OASIS_SIMULATION_DATA_DIR", Config.OASIS_SIMULATION_DATA_DIR)
            Config.OASIS_SIMULATION_DATA_DIR = simulation_data_dir
            stack.callback(
                setattr,
                SimulationManager,
                "SIMULATION_DATA_DIR",
                SimulationManager.SIMULATION_DATA_DIR,
            )
            SimulationManager.SIMULATION_DATA_DIR = simulation_data_dir

        stack.callback(
            setattr,
            simulation_manager_module,
            "ZepEntityReader",
            simulation_manager_module.ZepEntityReader,
        )
        simulation_manager_module.ZepEntityReader = _FixtureReader
        stack.callback(
            setattr,
            simulation_manager_module,
            "OasisProfileGenerator",
            simulation_manager_module.OasisProfileGenerator,
        )
        simulation_manager_module.OasisProfileGenerator = _FixtureProfileGenerator
        stack.callback(
            setattr,
            simulation_manager_module,
            "SimulationConfigGenerator",
            simulation_manager_module.SimulationConfigGenerator,
        )
        simulation_manager_module.SimulationConfigGenerator = _FixtureSimulationConfigGenerator

        project = ProjectManager.create_project(name=project_name)
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.graph_id = graph_id
        project.simulation_requirement = simulation_requirement
        ProjectManager.save_project(project)
        ProjectManager.save_extracted_text(project.project_id, document_text)

        manager = SimulationManager()
        state = manager.create_simulation(project.project_id, graph_id)
        manager.prepare_simulation(
            simulation_id=state.simulation_id,
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            use_llm_for_profiles=False,
            parallel_profile_count=1,
            probabilistic_mode=True,
            uncertainty_profile=uncertainty_profile,
            outcome_metrics=normalized_metrics,
        )

        prepared_summary = manager.get_prepare_artifact_summary(state.simulation_id)
        result = {
            "fixture_type": "probabilistic_step2_step3_smoke",
            "project_id": project.project_id,
            "simulation_id": state.simulation_id,
            "graph_id": graph_id,
            "project_dir": ProjectManager._get_project_dir(project.project_id),
            "simulation_dir": manager._get_simulation_dir(state.simulation_id),
            "simulation_route": f"/simulation/{state.simulation_id}",
            "prepared_artifact_summary": prepared_summary,
            "ensemble": None,
            "report": None,
        }

        if create_ensemble_run_count > 0:
            effective_simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
            ensemble_manager = EnsembleManager(simulation_data_dir=effective_simulation_data_dir)
            created = ensemble_manager.create_ensemble(
                simulation_id=state.simulation_id,
                ensemble_spec=EnsembleSpec(
                    run_count=create_ensemble_run_count,
                    max_concurrency=1,
                    root_seed=ensemble_root_seed,
                ),
            )
            result["ensemble"] = {
                "ensemble_id": created["ensemble_id"],
                "run_ids": [run["run_id"] for run in created["runs"]],
                "ensemble_dir": created["ensemble_dir"],
            }
            if seed_completed_report:
                selected_report_run_id = report_run_id or result["ensemble"]["run_ids"][0]
                if selected_report_run_id not in result["ensemble"]["run_ids"]:
                    raise ValueError(
                        "report_run_id must reference one of the seeded ensemble run_ids"
                    )
                _seed_completed_run_artifacts(
                    simulation_data_dir=effective_simulation_data_dir,
                    simulation_id=state.simulation_id,
                    ensemble_id=created["ensemble_id"],
                    run_ids=result["ensemble"]["run_ids"],
                )
                result["report"] = _seed_completed_probabilistic_report(
                    simulation_id=state.simulation_id,
                    graph_id=graph_id,
                    simulation_requirement=simulation_requirement,
                    ensemble_id=created["ensemble_id"],
                    run_id=selected_report_run_id,
                )

        return result
