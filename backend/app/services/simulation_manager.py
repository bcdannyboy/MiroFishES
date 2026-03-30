"""
OASIS simulation manager.
Manages parallel simulation runs across Twitter and Reddit.
Uses preset scripts plus LLM-generated configuration parameters.
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..models.probabilistic import (
    ConditionalVariableSpec,
    DEFAULT_OUTCOME_METRICS,
    ExperimentDesignSpec,
    ForecastBrief,
    OutcomeMetricDefinition,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    RandomVariableSpec,
    ScenarioTemplateSpec,
    SeedPolicy,
    UncertaintySpec,
    VariableGroupSpec,
    build_supported_outcome_metric,
    normalize_uncertainty_profile,
    normalize_forecast_brief,
    validate_outcome_metric_id,
)
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters
from .grounding_bundle_builder import GroundingBundleBuilder
from .phase_timing import PhaseTimingRecorder
from forecast_archive import (
    FORECAST_ARCHIVE_FILENAME,
    is_forecast_archived,
    load_forecast_archive_metadata,
)

logger = get_logger('mirofish.simulation')


class SimulationStatus(str, Enum):
    """Simulation status."""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # Simulation stopped manually
    COMPLETED = "completed"  # Simulation completed naturally
    FAILED = "failed"


class PlatformType(str, Enum):
    """Platform type."""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """Simulation state."""
    simulation_id: str
    project_id: str
    graph_id: str
    base_graph_id: str = ""
    runtime_graph_id: Optional[str] = None
    
    # Platform enablement flags
    enable_twitter: bool = True
    enable_reddit: bool = True
    
    # Status
    status: SimulationStatus = SimulationStatus.CREATED
    
    # Preparation-stage data
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    
    # Configuration generation data
    config_generated: bool = False
    config_reasoning: str = ""
    
    # Runtime data
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Error details
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.base_graph_id and self.graph_id:
            self.base_graph_id = self.graph_id
        if not self.graph_id and self.base_graph_id:
            self.graph_id = self.base_graph_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Full state dictionary used internally."""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "base_graph_id": self.base_graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """Simplified state dictionary used for API responses."""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "base_graph_id": self.base_graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    Simulation manager.
    
    Core responsibilities:
    1. Read and filter entities from a Zep graph
    2. Generate OASIS agent profiles
    3. Use an LLM to generate simulation configuration parameters
    4. Prepare all files required by the preset scripts
    """
    
    # Simulation data storage directory
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )

    PREPARE_ARTIFACT_FILENAMES = {
        "legacy_config": "simulation_config.json",
        "base_config": "simulation_config.base.json",
        "forecast_brief": "forecast_brief.json",
        "grounding_bundle": "grounding_bundle.json",
        "uncertainty_spec": "uncertainty_spec.json",
        "outcome_spec": "outcome_spec.json",
        "prepare_phase_timings": "prepare_phase_timings.json",
        "prepared_snapshot": "prepared_snapshot.json",
    }
    REQUIRED_PROBABILISTIC_ARTIFACT_KEYS = (
        "base_config",
        "grounding_bundle",
        "uncertainty_spec",
        "outcome_spec",
        "prepared_snapshot",
    )
    PREPARE_SCHEMA_VERSION = PROBABILISTIC_SCHEMA_VERSION
    PREPARE_GENERATOR_VERSION = PROBABILISTIC_GENERATOR_VERSION
    FORECAST_ARCHIVE_FILENAME = FORECAST_ARCHIVE_FILENAME
    UNCERTAINTY_PROFILE_RULES = {
        "deterministic-baseline": {
            "bounded_delta": 0.0,
            "rate_relative_delta": 0.0,
            "rate_minimum_delta": 0.0,
            "bias_delta": 0.0,
            "weight_relative_delta": 0.0,
            "weight_minimum_delta": 0.0,
        },
        "balanced": {
            "bounded_delta": 0.15,
            "rate_relative_delta": 0.35,
            "rate_minimum_delta": 0.2,
            "bias_delta": 0.2,
            "weight_relative_delta": 0.25,
            "weight_minimum_delta": 0.2,
        },
        "stress-test": {
            "bounded_delta": 0.30,
            "rate_relative_delta": 0.60,
            "rate_minimum_delta": 0.4,
            "bias_delta": 0.4,
            "weight_relative_delta": 0.45,
            "weight_minimum_delta": 0.35,
        },
    }
    
    def __init__(self):
        # Ensure the directory exists
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        
        # In-memory simulation state cache
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """Get the simulation data directory."""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir

    def _write_json(self, file_path: str, payload: Dict[str, Any]) -> None:
        """Write a JSON artifact with stable UTF-8 formatting."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _read_json_if_exists(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Read a JSON artifact when present."""
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _clear_probabilistic_artifacts(self, sim_dir: str) -> None:
        """Remove sidecar artifacts when preparing a legacy-only snapshot."""
        for artifact_name in (
            "base_config",
            "forecast_brief",
            "grounding_bundle",
            "uncertainty_spec",
            "outcome_spec",
            "prepare_phase_timings",
            "prepared_snapshot",
        ):
            artifact_path = os.path.join(
                sim_dir, self.PREPARE_ARTIFACT_FILENAMES[artifact_name]
            )
            if os.path.exists(artifact_path):
                os.remove(artifact_path)

    def _describe_artifact(self, sim_dir: str, artifact_name: str) -> Dict[str, Any]:
        """Describe one preparation artifact, including version and path metadata."""
        filename = self.PREPARE_ARTIFACT_FILENAMES[artifact_name]
        artifact_path = os.path.join(sim_dir, filename)
        exists = os.path.exists(artifact_path)

        description = {
            "artifact_type": artifact_name,
            "filename": filename,
            "path": artifact_path,
            "relative_path": os.path.relpath(artifact_path, sim_dir),
            "exists": exists,
        }
        if not exists:
            return description

        description["size_bytes"] = os.path.getsize(artifact_path)
        artifact_payload = self._read_json_if_exists(artifact_path)
        if artifact_payload:
            for field_name in (
                "schema_version",
                "generator_version",
                "artifact_type",
                "prepared_at",
                "generated_at",
            ):
                if field_name in artifact_payload:
                    description[field_name] = artifact_payload[field_name]

        return description

    @classmethod
    def derive_prepare_readiness(
        cls,
        *,
        artifacts: Dict[str, Any],
        grounding_summary: Optional[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Derive explicit readiness signals for artifact completeness and forecast handoff."""
        missing_probabilistic_artifacts = [
            cls.PREPARE_ARTIFACT_FILENAMES[name]
            for name in cls.REQUIRED_PROBABILISTIC_ARTIFACT_KEYS
            if not (artifacts.get(name, {}) or {}).get("exists")
        ]

        if not missing_probabilistic_artifacts:
            artifact_completeness = {
                "ready": True,
                "status": "ready",
                "reason": "",
                "missing_artifacts": [],
            }
        else:
            artifact_completeness = {
                "ready": False,
                "status": (
                    "missing"
                    if len(missing_probabilistic_artifacts)
                    == len(cls.REQUIRED_PROBABILISTIC_ARTIFACT_KEYS)
                    else "partial"
                ),
                "reason": (
                    "Forecast artifacts are incomplete. Missing files: "
                    + ", ".join(missing_probabilistic_artifacts)
                    + "."
                ),
                "missing_artifacts": missing_probabilistic_artifacts,
            }

        grounding_artifact = (artifacts.get("grounding_bundle", {}) or {})
        grounding_status = str(
            (grounding_summary or {}).get("status") or "unavailable"
        ).strip() or "unavailable"

        if not grounding_artifact.get("exists"):
            missing_artifact_count = len(artifact_completeness["missing_artifacts"])
            grounding_readiness = {
                "ready": False,
                "status": "missing",
                "reason": (
                    artifact_completeness["reason"]
                    if missing_artifact_count > 1
                    else "Stored-run shell handoff is blocked because grounding_bundle.json is missing."
                ),
            }
        elif grounding_status == "ready":
            grounding_readiness = {
                "ready": True,
                "status": "ready",
                "reason": "",
            }
        elif grounding_status == "partial":
            grounding_readiness = {
                "ready": False,
                "status": "partial",
                "reason": (
                    "Stored-run shell handoff is blocked because grounding evidence is partial in grounding_bundle.json."
                ),
            }
        elif grounding_status == "unavailable":
            grounding_readiness = {
                "ready": False,
                "status": "unavailable",
                "reason": (
                    "Stored-run shell handoff is blocked because grounding evidence is unavailable in grounding_bundle.json."
                ),
            }
        else:
            grounding_readiness = {
                "ready": False,
                "status": grounding_status,
                "reason": (
                    "Stored-run shell handoff is blocked because grounding_bundle.json has "
                    f"status {grounding_status}. Workflow handoff requires status ready."
                ),
            }

        if (
            not grounding_readiness["ready"]
            and not artifact_completeness["ready"]
            and len(artifact_completeness["missing_artifacts"]) > 1
        ):
            forecast_readiness = {
                "ready": False,
                "status": "blocked",
                "reason": artifact_completeness["reason"],
                "blocking_stage": "artifacts",
            }
        elif not grounding_readiness["ready"]:
            forecast_readiness = {
                "ready": False,
                "status": "blocked",
                "reason": grounding_readiness["reason"],
                "blocking_stage": "grounding",
            }
        elif not artifact_completeness["ready"]:
            forecast_readiness = {
                "ready": False,
                "status": "blocked",
                "reason": artifact_completeness["reason"],
                "blocking_stage": "artifacts",
            }
        else:
            forecast_readiness = {
                "ready": True,
                "status": "ready",
                "reason": "",
                "blocking_stage": None,
            }

        workflow_handoff_status = {
            **forecast_readiness,
            "semantics": "workflow_handoff_status",
        }

        return {
            "artifact_completeness": artifact_completeness,
            "grounding_readiness": grounding_readiness,
            "forecast_readiness": forecast_readiness,
            "workflow_handoff_status": workflow_handoff_status,
        }

    def _normalize_outcome_metrics(
        self, outcome_metrics: Optional[List[Any]]
    ) -> List[OutcomeMetricDefinition]:
        """Normalize requested outcome metrics into validated definitions."""
        if not outcome_metrics:
            return [
                build_supported_outcome_metric(metric_id)
                for metric_id in DEFAULT_OUTCOME_METRICS
            ]

        normalized: List[OutcomeMetricDefinition] = []
        seen_metric_ids = set()

        for item in outcome_metrics:
            if isinstance(item, str):
                metric = build_supported_outcome_metric(validate_outcome_metric_id(item))
            elif isinstance(item, dict):
                metric_id = item.get("metric_id")
                if not metric_id:
                    raise ValueError("Outcome metric dictionaries require metric_id")
                validate_outcome_metric_id(metric_id)

                metric = OutcomeMetricDefinition(
                    metric_id=metric_id,
                    label=(
                        item.get("label")
                        or build_supported_outcome_metric(metric_id).label
                    ),
                    description=(
                        item.get("description")
                        or build_supported_outcome_metric(metric_id).description
                    ),
                    aggregation=item.get("aggregation", "count"),
                    unit=item.get("unit", "count"),
                    probability_mode=item.get("probability_mode", "empirical"),
                )
            else:
                raise ValueError("outcome_metrics entries must be strings or dictionaries")

            if metric.metric_id not in seen_metric_ids:
                normalized.append(metric)
                seen_metric_ids.add(metric.metric_id)

        return normalized

    def _build_uncertainty_spec(
        self,
        uncertainty_profile: Optional[str],
        config_payload: Dict[str, Any],
        forecast_brief: Optional[ForecastBrief] = None,
    ) -> UncertaintySpec:
        """
        Build the initial uncertainty contract from the generated config payload.

        The first-pass catalog stays intentionally narrow:
        selected numeric behavior and platform fields become explicit prepare-time
        uncertainty objects, while persona text, graph identity, events, and
        richer narrative fields remain fixed until later phases.
        """
        normalized_profile = normalize_uncertainty_profile(uncertainty_profile)
        random_variables = self._build_random_variables_for_profile(
            config_payload,
            normalized_profile,
        )
        variable_groups = self._build_variable_groups(random_variables)
        scenario_templates = self._build_scenario_templates(
            forecast_brief,
            config_payload=config_payload,
        )
        conditional_variables = self._build_conditional_variables(
            config_payload=config_payload,
            scenario_templates=scenario_templates,
        )
        experiment_design = self._build_experiment_design_spec(
            random_variables=random_variables,
            variable_groups=variable_groups,
            conditional_variables=conditional_variables,
            scenario_templates=scenario_templates,
        )
        return UncertaintySpec(
            profile=normalized_profile,
            random_variables=random_variables,
            variable_groups=variable_groups,
            conditional_variables=conditional_variables,
            scenario_templates=scenario_templates,
            experiment_design=experiment_design,
            seed_policy=SeedPolicy(),
            notes=[
                "Preparation persists one explicit catalog of run-varying config fields.",
                "Persona text, graph-derived identity, and scheduled events remain fixed in this slice.",
                "Structured experiment design metadata is explicit so ensemble coverage can be inspected later.",
                (
                    "The deterministic-baseline profile keeps those fields fixed so seeded resolution remains explicit without adding extra config variance."
                    if normalized_profile == "deterministic-baseline"
                    else "Initial variability is limited to selected numeric behavior and platform scalars; runtime sampling and calibration remain separate concerns."
                ),
            ],
        )

    def _build_random_variables_for_profile(
        self,
        config_payload: Dict[str, Any],
        profile: str,
    ) -> List[RandomVariableSpec]:
        """Materialize the first prepare-time uncertainty catalog from one base config."""
        profile_rules = self.UNCERTAINTY_PROFILE_RULES[profile]
        random_variables: List[RandomVariableSpec] = []

        for index, agent_config in enumerate(config_payload.get("agent_configs", [])):
            random_variables.extend(
                item
                for item in (
                    self._build_bounded_scalar_variable(
                        field_path=f"agent_configs[{index}].activity_level",
                        baseline_value=agent_config.get("activity_level"),
                        description=f"Agent {index} activity level",
                        lower_bound=0.0,
                        upper_bound=1.0,
                        absolute_delta=profile_rules["bounded_delta"],
                        profile=profile,
                    ),
                    self._build_positive_scalar_variable(
                        field_path=f"agent_configs[{index}].posts_per_hour",
                        baseline_value=agent_config.get("posts_per_hour"),
                        description=f"Agent {index} posts per hour",
                        relative_delta=profile_rules["rate_relative_delta"],
                        minimum_delta=profile_rules["rate_minimum_delta"],
                        profile=profile,
                    ),
                    self._build_positive_scalar_variable(
                        field_path=f"agent_configs[{index}].comments_per_hour",
                        baseline_value=agent_config.get("comments_per_hour"),
                        description=f"Agent {index} comments per hour",
                        relative_delta=profile_rules["rate_relative_delta"],
                        minimum_delta=profile_rules["rate_minimum_delta"],
                        profile=profile,
                    ),
                    self._build_bounded_scalar_variable(
                        field_path=f"agent_configs[{index}].sentiment_bias",
                        baseline_value=agent_config.get("sentiment_bias"),
                        description=f"Agent {index} sentiment bias",
                        lower_bound=-1.0,
                        upper_bound=1.0,
                        absolute_delta=profile_rules["bias_delta"],
                        profile=profile,
                    ),
                    self._build_positive_scalar_variable(
                        field_path=f"agent_configs[{index}].influence_weight",
                        baseline_value=agent_config.get("influence_weight"),
                        description=f"Agent {index} influence weight",
                        relative_delta=profile_rules["weight_relative_delta"],
                        minimum_delta=profile_rules["weight_minimum_delta"],
                        profile=profile,
                    ),
                )
                if item is not None
            )

        for platform_key, platform_label in (
            ("twitter_config", "Twitter"),
            ("reddit_config", "Reddit"),
        ):
            platform_config = config_payload.get(platform_key) or {}
            variable = self._build_bounded_scalar_variable(
                field_path=f"{platform_key}.echo_chamber_strength",
                baseline_value=platform_config.get("echo_chamber_strength"),
                description=f"{platform_label} echo chamber strength",
                lower_bound=0.0,
                upper_bound=1.0,
                absolute_delta=profile_rules["bounded_delta"],
                profile=profile,
            )
            if variable is not None:
                random_variables.append(variable)

        time_config = config_payload.get("time_config") or {}
        random_variables.extend(
            item
            for item in (
                self._build_positive_scalar_variable(
                    field_path="time_config.peak_activity_multiplier",
                    baseline_value=time_config.get("peak_activity_multiplier"),
                    description="Peak activity multiplier",
                    relative_delta=profile_rules["rate_relative_delta"],
                    minimum_delta=0.15,
                    profile=profile,
                ),
                self._build_bounded_scalar_variable(
                    field_path="time_config.off_peak_activity_multiplier",
                    baseline_value=time_config.get("off_peak_activity_multiplier"),
                    description="Off-peak activity multiplier",
                    lower_bound=0.0,
                    upper_bound=1.0,
                    absolute_delta=max(profile_rules["bounded_delta"], 0.05),
                    profile=profile,
                ),
                self._build_bounded_scalar_variable(
                    field_path="time_config.work_activity_multiplier",
                    baseline_value=time_config.get("work_activity_multiplier"),
                    description="Work-hours activity multiplier",
                    lower_bound=0.0,
                    upper_bound=2.0,
                    absolute_delta=max(profile_rules["bounded_delta"], 0.05),
                    profile=profile,
                ),
            )
            if item is not None
        )

        return random_variables

    def _build_positive_scalar_variable(
        self,
        *,
        field_path: str,
        baseline_value: Any,
        description: str,
        relative_delta: float,
        minimum_delta: float,
        profile: str,
    ) -> Optional[RandomVariableSpec]:
        """Create one fixed or uniformly bounded positive scalar variable."""
        return self._build_numeric_random_variable(
            field_path=field_path,
            baseline_value=baseline_value,
            description=description,
            lower_bound=0.0,
            upper_bound=None,
            absolute_delta=max(abs(float(baseline_value or 0.0)) * relative_delta, minimum_delta),
            profile=profile,
        )

    def _build_bounded_scalar_variable(
        self,
        *,
        field_path: str,
        baseline_value: Any,
        description: str,
        lower_bound: float,
        upper_bound: float,
        absolute_delta: float,
        profile: str,
    ) -> Optional[RandomVariableSpec]:
        """Create one fixed or uniformly bounded scalar variable."""
        return self._build_numeric_random_variable(
            field_path=field_path,
            baseline_value=baseline_value,
            description=description,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            absolute_delta=absolute_delta,
            profile=profile,
        )

    def _build_numeric_random_variable(
        self,
        *,
        field_path: str,
        baseline_value: Any,
        description: str,
        lower_bound: Optional[float],
        upper_bound: Optional[float],
        absolute_delta: float,
        profile: str,
    ) -> Optional[RandomVariableSpec]:
        """Create one numeric variable while preserving deterministic-baseline semantics."""
        if baseline_value is None:
            return None

        baseline_numeric = float(baseline_value)
        if profile == "deterministic-baseline" or absolute_delta <= 0:
            return RandomVariableSpec(
                field_path=field_path,
                distribution="fixed",
                parameters={"value": baseline_value},
                description=description,
            )

        low = baseline_numeric - absolute_delta
        high = baseline_numeric + absolute_delta
        if lower_bound is not None:
            low = max(lower_bound, low)
        if upper_bound is not None:
            high = min(upper_bound, high)
        if high < low:
            low = high = baseline_numeric
        if low == high:
            return RandomVariableSpec(
                field_path=field_path,
                distribution="fixed",
                parameters={"value": baseline_value},
                description=description,
            )

        return RandomVariableSpec(
            field_path=field_path,
            distribution="uniform",
            parameters={"low": low, "high": high},
            description=description,
        )

    def _build_variable_groups(
        self,
        random_variables: List[RandomVariableSpec],
    ) -> List[VariableGroupSpec]:
        """Create conservative shared-rank groups for related numeric fields."""
        grouped_field_paths: Dict[str, List[str]] = {}

        for variable in random_variables:
            if variable.distribution == "fixed":
                continue
            field_path = variable.field_path
            if field_path.startswith("agent_configs[") and "." in field_path:
                prefix, suffix = field_path.split("].", 1)
                if suffix in {
                    "activity_level",
                    "posts_per_hour",
                    "comments_per_hour",
                    "sentiment_bias",
                    "influence_weight",
                }:
                    grouped_field_paths.setdefault(
                        f"{prefix.removeprefix('agent_configs[')}-engagement",
                        [],
                    ).append(field_path)
                    continue
            if field_path in {
                "twitter_config.echo_chamber_strength",
                "reddit_config.echo_chamber_strength",
            }:
                grouped_field_paths.setdefault("cross-platform-echo-chamber", []).append(
                    field_path
                )
                continue
            if field_path in {
                "time_config.peak_activity_multiplier",
                "time_config.off_peak_activity_multiplier",
                "time_config.work_activity_multiplier",
            }:
                grouped_field_paths.setdefault("time-profile", []).append(field_path)

        variable_groups: List[VariableGroupSpec] = []
        for group_key, field_paths in sorted(grouped_field_paths.items()):
            unique_field_paths = sorted(dict.fromkeys(field_paths))
            if len(unique_field_paths) < 2:
                continue
            variable_groups.append(
                VariableGroupSpec(
                    group_id=group_key,
                    field_paths=unique_field_paths,
                    notes=[
                        "Grouped variables share one structured design rank in this preparation slice."
                    ],
                )
            )
        return variable_groups

    def _build_conditional_variables(
        self,
        *,
        config_payload: Dict[str, Any],
        scenario_templates: List[ScenarioTemplateSpec],
    ) -> List[ConditionalVariableSpec]:
        template_ids = {
            str(template.template_id or "").strip()
            for template in scenario_templates
            if str(template.template_id or "").strip()
        }
        conditional_variables: List[ConditionalVariableSpec] = []

        def add_directional_condition(
            *,
            field_path: str,
            value: Any,
            narrative_direction: str,
            description: str,
        ) -> None:
            if not self._config_path_exists(config_payload, field_path):
                return
            conditional_variables.append(
                ConditionalVariableSpec(
                    variable=RandomVariableSpec(
                        field_path=field_path,
                        distribution="fixed",
                        parameters={"value": value},
                        description=description,
                    ),
                    condition_field_path="event_config.narrative_direction",
                    operator="eq",
                    condition_value=narrative_direction,
                    description=description,
                )
            )

        if "viral_spike" in template_ids:
            add_directional_condition(
                field_path="twitter_config.recency_weight",
                value=0.55,
                narrative_direction="viral_spike",
                description="Raise Twitter recency weighting during viral-spike scenarios.",
            )
            add_directional_condition(
                field_path="twitter_config.viral_threshold",
                value=6,
                narrative_direction="viral_spike",
                description="Lower the Twitter viral threshold during viral-spike scenarios.",
            )
        if "cooldown_recovery" in template_ids:
            add_directional_condition(
                field_path="reddit_config.relevance_weight",
                value=0.45,
                narrative_direction="cooldown",
                description="Shift Reddit relevance weighting during cooldown scenarios.",
            )
            add_directional_condition(
                field_path="reddit_config.viral_threshold",
                value=12,
                narrative_direction="cooldown",
                description="Raise the Reddit viral threshold during cooldown scenarios.",
            )
        if "crisis_case" in template_ids or "crisis_spike" in template_ids:
            add_directional_condition(
                field_path="twitter_config.viral_threshold",
                value=6,
                narrative_direction="crisis",
                description="Lower the Twitter viral threshold during crisis scenarios.",
            )

        return conditional_variables

    def _build_scenario_templates(
        self,
        forecast_brief: Optional[ForecastBrief],
        *,
        config_payload: Optional[Dict[str, Any]] = None,
    ) -> List[ScenarioTemplateSpec]:
        """Materialize inspectable scenario templates into concrete config overrides."""
        if forecast_brief is None:
            return []

        scenario_templates: List[ScenarioTemplateSpec] = []
        expand_auto_template_substance = self._should_expand_auto_template_substance(
            forecast_brief
        )
        explicit_specs = {
            template.template_id: template
            for template in forecast_brief.scenario_template_specs
        }
        for template_id in forecast_brief.scenario_templates:
            explicit_template = explicit_specs.get(template_id)
            if explicit_template is not None:
                scenario_templates.append(explicit_template)
                continue
            template_payload = self._build_scenario_template_payload(
                template_id=template_id,
                config_payload=config_payload or {},
                expand_substance=expand_auto_template_substance,
            )
            scenario_templates.append(
                self._instantiate_scenario_template_spec(
                    template_id=template_id,
                    template_payload=template_payload,
                )
            )
        return scenario_templates

    def _should_expand_auto_template_substance(
        self,
        forecast_brief: ForecastBrief,
    ) -> bool:
        return len(forecast_brief.scenario_templates) >= 3

    def _instantiate_scenario_template_spec(
        self,
        *,
        template_id: str,
        template_payload: Dict[str, Any],
    ) -> ScenarioTemplateSpec:
        template_kwargs = {
            "template_id": template_id,
            "label": template_payload["label"],
            "field_overrides": template_payload["field_overrides"],
            "weight": template_payload.get("weight", 1.0),
            "notes": template_payload["notes"],
        }
        supported_fields = getattr(ScenarioTemplateSpec, "__dataclass_fields__", {})
        for optional_field in (
            "coverage_tags",
            "exogenous_events",
            "conditional_overrides",
            "correlated_field_paths",
        ):
            if optional_field in supported_fields and optional_field in template_payload:
                template_kwargs[optional_field] = template_payload[optional_field]
        return ScenarioTemplateSpec(**template_kwargs)

    def _build_scenario_template_payload(
        self,
        *,
        template_id: str,
        config_payload: Dict[str, Any],
        expand_substance: bool,
    ) -> Dict[str, Any]:
        normalized_template_id = str(template_id or "").strip()
        template_slug = normalized_template_id.lower().replace("-", "_").replace(" ", "_")
        template_kind = self._classify_scenario_template_kind(template_slug)
        field_overrides: Dict[str, Any] = {}
        coverage_tags: List[str] = []
        exogenous_events: List[Dict[str, Any]] = []
        conditional_overrides: List[Dict[str, Any]] = []
        correlated_field_paths: List[str] = []
        notes = [
            "Scenario template overrides create concrete simulation worlds ahead of runtime.",
            "Template assignments widen scenario coverage for the stored simulation ensemble; they do not create real-world probability claims.",
        ]

        if self._config_has_event_narrative_direction(config_payload):
            field_overrides["event_config.narrative_direction"] = (
                self._get_template_narrative_direction(
                    template_kind=template_kind,
                    template_slug=template_slug,
                )
            )

        if template_kind == "viral_spike":
            coverage_tags = [
                "amplification",
                "trajectory:shock",
                "attention:surge",
                "platform:cross",
            ]
            if expand_substance:
                self._add_event_override(
                    field_overrides,
                    config_payload=config_payload,
                    field_name="hot_topics",
                    value=["seed", "viral_spike", "attention_surge"],
                )
                self._add_event_override(
                    field_overrides,
                    config_payload=config_payload,
                    field_name="scheduled_events",
                    value=[
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
                )
                self._add_time_override(
                    field_overrides,
                    config_payload=config_payload,
                    field_name="peak_activity_multiplier",
                    value=1.9,
                )
                self._add_time_override(
                    field_overrides,
                    config_payload=config_payload,
                    field_name="off_peak_activity_multiplier",
                    value=0.15,
                )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="twitter_config",
                field_name="echo_chamber_strength",
                value=0.8,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="reddit_config",
                field_name="echo_chamber_strength",
                value=0.75,
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="activity_level",
                transform=lambda value: min(1.0, value + 0.3),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="posts_per_hour",
                transform=lambda value: round(max(0.1, value * 1.5), 4),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="comments_per_hour",
                transform=lambda value: round(max(0.1, value * 1.5), 4),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="influence_weight",
                transform=lambda value: round(max(0.1, value * 1.35), 4),
            )
            exogenous_events = [
                {
                    "event_id": "viral_spike_alert",
                    "kind": "attention_surge",
                    "timing_window": "early",
                }
            ]
            conditional_overrides = self._build_template_conditional_overrides(
                {
                    "twitter_config.viral_threshold": 6,
                },
                condition_value="viral_spike",
            )
            correlated_field_paths = [
                "agent_configs[0].activity_level",
                "agent_configs[0].posts_per_hour",
                "agent_configs[0].comments_per_hour",
                "agent_configs[0].influence_weight",
            ]
            notes.append(
                "This template raises engagement and echo-chamber pressure to probe higher-spread simulation paths."
            )
        elif template_kind == "crisis":
            coverage_tags = [
                "trajectory:crisis",
                "attention:elevated",
                "platform:polarized",
            ]
            self._add_event_override(
                field_overrides,
                config_payload=config_payload,
                field_name="hot_topics",
                value=["seed", "crisis", "breaking_update"],
            )
            self._add_event_override(
                field_overrides,
                config_payload=config_payload,
                field_name="scheduled_events",
                value=[
                    {
                        "offset_hours": 2,
                        "event_type": "breaking_update",
                        "topic": "crisis",
                        "intensity": "high",
                    }
                ],
            )
            self._add_time_override(
                field_overrides,
                config_payload=config_payload,
                field_name="peak_activity_multiplier",
                value=2.0,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="twitter_config",
                field_name="echo_chamber_strength",
                value=0.85,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="reddit_config",
                field_name="echo_chamber_strength",
                value=0.8,
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="activity_level",
                transform=lambda value: min(1.0, value + 0.2),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="comments_per_hour",
                transform=lambda value: round(max(0.1, value * 1.6), 4),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="sentiment_bias",
                transform=lambda value: max(-1.0, value - 0.35),
            )
            exogenous_events = [
                {
                    "event_id": "crisis_case_briefing",
                    "kind": "breaking_update",
                    "timing_window": "early",
                }
            ]
            conditional_overrides = self._build_template_conditional_overrides(
                {
                    "twitter_config.viral_threshold": 6,
                },
                condition_value="crisis",
            )
            correlated_field_paths = [
                "agent_configs[0].activity_level",
                "twitter_config.echo_chamber_strength",
            ]
            notes.append(
                "This template shifts narrative and engagement toward crisis-style simulation stress."
            )
        elif template_kind == "high_echo":
            coverage_tags = [
                "trajectory:polarized",
                "attention:volatile",
                "platform:echo",
            ]
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="twitter_config",
                field_name="echo_chamber_strength",
                value=0.9,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="reddit_config",
                field_name="echo_chamber_strength",
                value=0.85,
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="comments_per_hour",
                transform=lambda value: round(max(0.1, value * 1.25), 4),
            )
            notes.append(
                "This template emphasizes fragmentation and echo-chamber concentration inside the simulation."
            )
        elif template_kind == "cooldown":
            coverage_tags = [
                "trajectory:recovery",
                "attention:cooling",
                "platform:stabilized",
            ]
            self._add_event_override(
                field_overrides,
                config_payload=config_payload,
                field_name="hot_topics",
                value=["seed", "stabilization", "clarification"],
            )
            self._add_event_override(
                field_overrides,
                config_payload=config_payload,
                field_name="scheduled_events",
                value=[
                    {
                        "offset_hours": 6,
                        "event_type": "clarification",
                        "topic": "stabilization",
                        "intensity": "medium",
                    }
                ],
            )
            self._add_time_override(
                field_overrides,
                config_payload=config_payload,
                field_name="peak_activity_multiplier",
                value=1.1,
            )
            self._add_time_override(
                field_overrides,
                config_payload=config_payload,
                field_name="work_activity_multiplier",
                value=0.75,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="twitter_config",
                field_name="echo_chamber_strength",
                value=0.25,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="reddit_config",
                field_name="echo_chamber_strength",
                value=0.2,
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="activity_level",
                transform=lambda value: max(0.0, value - 0.2),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="posts_per_hour",
                transform=lambda value: round(max(0.1, value * 0.6), 4),
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="comments_per_hour",
                transform=lambda value: round(max(0.1, value * 0.6), 4),
            )
            exogenous_events = [
                {
                    "event_id": "cooldown_recovery_guidance",
                    "kind": "clarification",
                    "timing_window": "mid",
                }
            ]
            conditional_overrides = self._build_template_conditional_overrides(
                {
                    "reddit_config.viral_threshold": 12,
                },
                condition_value="cooldown",
            )
            correlated_field_paths = [
                "agent_configs[0].activity_level",
                "time_config.work_activity_multiplier",
            ]
            notes.append(
                "This template cools narrative pressure so the simulation can probe stabilization paths."
            )
        elif template_kind == "consensus":
            coverage_tags = [
                "trajectory:bridge",
                "attention:coordinated",
                "platform:bridge",
            ]
            self._add_event_override(
                field_overrides,
                config_payload=config_payload,
                field_name="scheduled_events",
                value=[
                    {
                        "offset_hours": 5,
                        "event_type": "community_response",
                        "topic": "coordination",
                        "intensity": "medium",
                    }
                ],
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="twitter_config",
                field_name="echo_chamber_strength",
                value=0.2,
            )
            self._add_platform_override(
                field_overrides,
                config_payload=config_payload,
                platform_key="reddit_config",
                field_name="echo_chamber_strength",
                value=0.2,
            )
            self._add_agent_scalar_override(
                field_overrides,
                config_payload=config_payload,
                field_name="sentiment_bias",
                transform=lambda value: min(1.0, value + 0.2),
            )
            exogenous_events = [
                {
                    "event_id": "consensus_bridge_briefing",
                    "kind": "community_response",
                    "timing_window": "mid",
                }
            ]
            conditional_overrides = self._build_template_conditional_overrides(
                {
                    "time_config.work_activity_multiplier": 0.95,
                },
                condition_value="consensus",
            )
            correlated_field_paths = [
                "agent_configs[0].activity_level",
            ]
            notes.append(
                "This template dampens echo-chamber effects to probe coordination-heavy simulation paths."
            )
        elif template_kind == "baseline":
            coverage_tags = [
                "trajectory:baseline",
                "attention:steady",
                "platform:reference",
            ]
            notes.append(
                "This template keeps the scenario near the reference shell while still marking the baseline narrative path explicitly."
            )
        else:
            coverage_tags = ["trajectory:custom"]
            notes.append(
                "No recognized numeric pattern was found for this template id, so only a narrative-direction override is applied."
            )

        return {
            "label": normalized_template_id.replace("_", " ").replace("-", " ").title(),
            "field_overrides": field_overrides,
            "coverage_tags": coverage_tags,
            "exogenous_events": exogenous_events,
            "conditional_overrides": conditional_overrides,
            "correlated_field_paths": correlated_field_paths,
            "notes": notes,
        }

    def _classify_scenario_template_kind(self, template_slug: str) -> str:
        if any(token in template_slug for token in ("base", "baseline", "reference", "control", "watch")):
            return "baseline"
        if any(token in template_slug for token in ("viral", "spike", "surge", "amplif", "breakout")):
            return "viral_spike"
        if any(token in template_slug for token in ("crisis", "panic", "shock", "stress", "backlash")):
            return "crisis"
        if any(token in template_slug for token in ("high_echo", "echo", "polar", "fragment")):
            return "high_echo"
        if any(token in template_slug for token in ("cool", "contain", "recover", "stabil", "moder")):
            return "cooldown"
        if any(token in template_slug for token in ("consensus", "bridge", "coord", "cooper")):
            return "consensus"
        return "custom"

    def _get_template_narrative_direction(
        self,
        *,
        template_kind: str,
        template_slug: str,
    ) -> str:
        mapping = {
            "baseline": "baseline",
            "viral_spike": "viral_spike",
            "crisis": "crisis",
            "high_echo": "high_echo",
            "cooldown": "cooldown",
            "consensus": "consensus",
        }
        return mapping.get(template_kind, template_slug or "scenario_template")

    def _config_has_event_narrative_direction(
        self,
        config_payload: Dict[str, Any],
    ) -> bool:
        return isinstance(config_payload.get("event_config"), dict) and (
            "narrative_direction" in config_payload["event_config"]
        )

    def _config_path_exists(
        self,
        config_payload: Dict[str, Any],
        field_path: str,
    ) -> bool:
        current: Any = config_payload
        for raw_token in field_path.split("."):
            if "[" in raw_token and raw_token.endswith("]"):
                key, raw_index = raw_token[:-1].split("[", 1)
                if not isinstance(current, dict) or key not in current:
                    return False
                current = current[key]
                try:
                    index = int(raw_index)
                except ValueError:
                    return False
                if not isinstance(current, list) or index >= len(current):
                    return False
                current = current[index]
                continue
            if not isinstance(current, dict) or raw_token not in current:
                return False
            current = current[raw_token]
        return True

    def _add_event_override(
        self,
        field_overrides: Dict[str, Any],
        *,
        config_payload: Dict[str, Any],
        field_name: str,
        value: Any,
    ) -> None:
        event_payload = config_payload.get("event_config")
        if not isinstance(event_payload, dict) or field_name not in event_payload:
            return
        field_overrides[f"event_config.{field_name}"] = value

    def _add_time_override(
        self,
        field_overrides: Dict[str, Any],
        *,
        config_payload: Dict[str, Any],
        field_name: str,
        value: Any,
    ) -> None:
        time_payload = config_payload.get("time_config")
        if not isinstance(time_payload, dict) or field_name not in time_payload:
            return
        field_overrides[f"time_config.{field_name}"] = value

    def _build_template_conditional_overrides(
        self,
        field_values: Dict[str, Any],
        *,
        condition_value: str,
    ) -> List[Dict[str, Any]]:
        overrides: List[Dict[str, Any]] = []
        for field_path, value in field_values.items():
            overrides.append(
                {
                    "variable": {
                        "field_path": field_path,
                        "distribution": "fixed",
                        "parameters": {"value": value},
                    },
                    "condition_field_path": "event_config.narrative_direction",
                    "operator": "eq",
                    "condition_value": condition_value,
                }
            )
        return overrides

    def _add_platform_override(
        self,
        field_overrides: Dict[str, Any],
        *,
        config_payload: Dict[str, Any],
        platform_key: str,
        field_name: str,
        value: Any,
    ) -> None:
        platform_payload = config_payload.get(platform_key)
        if not isinstance(platform_payload, dict) or field_name not in platform_payload:
            return
        field_overrides[f"{platform_key}.{field_name}"] = value

    def _add_agent_scalar_override(
        self,
        field_overrides: Dict[str, Any],
        *,
        config_payload: Dict[str, Any],
        field_name: str,
        transform,
    ) -> None:
        for index, agent_payload in enumerate(config_payload.get("agent_configs", [])):
            if not isinstance(agent_payload, dict) or field_name not in agent_payload:
                continue
            try:
                baseline_value = float(agent_payload[field_name])
            except (TypeError, ValueError):
                continue
            field_overrides[f"agent_configs[{index}].{field_name}"] = transform(
                baseline_value
            )

    def _build_experiment_design_spec(
        self,
        *,
        random_variables: List[RandomVariableSpec],
        variable_groups: List[VariableGroupSpec],
        conditional_variables: List[ConditionalVariableSpec],
        scenario_templates: List[ScenarioTemplateSpec],
    ) -> ExperimentDesignSpec:
        """Build the explicit structured design contract used by ensemble planning."""
        scenario_assignment = (
            "weighted_cycle"
            if any(template.weight != 1.0 for template in scenario_templates)
            else "cyclic"
        )
        max_templates_per_run = 2 if len(scenario_templates) >= 3 else 1
        diversity_axes = self._derive_scenario_diversity_axes(scenario_templates)
        scenario_coverage_axes = self._derive_scenario_coverage_axes(scenario_templates)
        return ExperimentDesignSpec(
            method="latin-hypercube",
            numeric_dimensions=[
                variable.field_path
                for variable in random_variables
                if variable.distribution == "uniform"
            ],
            scenario_template_ids=[
                template.template_id for template in scenario_templates
            ],
            scenario_assignment=scenario_assignment,
            diversity_axes=diversity_axes,
            scenario_coverage_axes=scenario_coverage_axes,
            max_templates_per_run=max_templates_per_run,
            template_combination_policy=(
                "pairwise" if max_templates_per_run > 1 else "single_template"
            ),
            max_template_reuse_streak=1 if max_templates_per_run > 1 else 2,
            notes=[
                "Numeric uniform variables use deterministic Latin-hypercube coverage.",
                (
                    "Scenario templates are assigned with deterministic weighted coverage when template weights differ."
                    if scenario_assignment == "weighted_cycle"
                    else "Scenario templates are assigned cyclically when declared."
                ),
                (
                    "Pairwise template combinations are allowed so richer scenario packs cover more event-space combinations per run."
                    if max_templates_per_run > 1
                    else "Each run receives at most one scenario template in the lean prepare path."
                ),
                (
                    "Conditional template variables are tracked separately so scenario expansion does not hide assumption triggers."
                    if conditional_variables
                    else "No conditional template variables were emitted for this prepare-time slice."
                ),
                (
                    "Variable groups preserve shared-rank structure for related fields across the scenario design."
                    if variable_groups
                    else "No non-fixed shared-rank variable groups were required in this prepare-time slice."
                ),
            ],
        )

    def _build_uncertainty_feature_metadata(
        self,
        uncertainty_spec: UncertaintySpec,
    ) -> Dict[str, Any]:
        """Summarize the uncertainty catalog for API and UI responses."""
        variable_paths = [
            variable.field_path for variable in uncertainty_spec.random_variables
        ]
        non_fixed_count = sum(
            1
            for variable in uncertainty_spec.random_variables
            if variable.distribution != "fixed"
        )
        rich_preview_enabled = self._should_include_rich_template_preview(
            uncertainty_spec.scenario_templates
        )
        scenario_template_preview = self._build_scenario_template_preview(
            uncertainty_spec.scenario_templates,
            include_rich_fields=rich_preview_enabled,
        )
        scenario_template_override_total = sum(
            len(template.field_overrides)
            for template in uncertainty_spec.scenario_templates
        )
        return {
            "uncertainty_profile": uncertainty_spec.profile,
            "seed_policy": uncertainty_spec.seed_policy.to_dict(),
            "random_variable_count": len(variable_paths),
            "non_fixed_random_variable_count": non_fixed_count,
            "random_variable_preview": variable_paths[:5],
            "sampling_enabled": non_fixed_count > 0,
            "structured_design_enabled": uncertainty_spec.experiment_design is not None,
            "experiment_design_method": (
                uncertainty_spec.experiment_design.method
                if uncertainty_spec.experiment_design is not None
                else None
            ),
            "variable_group_count": len(uncertainty_spec.variable_groups),
            "conditional_variable_count": len(uncertainty_spec.conditional_variables),
            "scenario_template_count": len(uncertainty_spec.scenario_templates),
            "scenario_diversity_enabled": any(
                bool(template.field_overrides)
                for template in uncertainty_spec.scenario_templates
            ),
            "scenario_diversity_axes": self._derive_scenario_diversity_axes(
                uncertainty_spec.scenario_templates
            ),
            "scenario_coverage_axes": (
                uncertainty_spec.experiment_design.scenario_coverage_axes
                if uncertainty_spec.experiment_design is not None
                else []
            ),
            "scenario_diversity_strategy": (
                uncertainty_spec.experiment_design.scenario_assignment
                if uncertainty_spec.experiment_design is not None
                else None
            ),
            "scenario_template_override_total": scenario_template_override_total,
            "scenario_template_substantive_count": len(
                uncertainty_spec.scenario_templates
            ),
            "scenario_template_preview": scenario_template_preview,
            "scenario_worker": "simulation",
        }

    def _build_scenario_template_preview(
        self,
        scenario_templates: List[ScenarioTemplateSpec],
        *,
        include_rich_fields: bool,
    ) -> List[Dict[str, Any]]:
        preview: List[Dict[str, Any]] = []
        for template in scenario_templates:
            item = {
                "template_id": template.template_id,
                "label": template.label,
                "override_field_count": len(template.field_overrides),
                "override_fields": sorted(template.field_overrides.keys()),
            }
            if include_rich_fields:
                item.update(
                    {
                        "coverage_tags": sorted(template.coverage_tags),
                        "exogenous_event_count": len(template.exogenous_events),
                        "conditional_override_count": len(
                            template.conditional_overrides
                        ),
                        "correlated_field_count": len(
                            template.correlated_field_paths
                        ),
                        "substantive_override_count": (
                            len(template.field_overrides)
                            + len(template.exogenous_events)
                            + len(template.conditional_overrides)
                            + len(template.correlated_field_paths)
                        ),
                    }
                )
            preview.append(item)
        return preview

    def _should_include_rich_template_preview(
        self,
        scenario_templates: List[ScenarioTemplateSpec],
    ) -> bool:
        if any(
            template.exogenous_events
            or template.conditional_overrides
            or template.correlated_field_paths
            for template in scenario_templates
            if self._classify_scenario_template_kind(
                str(template.template_id or "")
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )
            in {"consensus", "crisis"}
        ):
            return True
        return any(
            template.weight != 1.0
            for template in scenario_templates
        )

    def _derive_scenario_diversity_axes(
        self,
        scenario_templates: List[ScenarioTemplateSpec],
    ) -> List[str]:
        axis_order = [
            ("agent_configs[", "agent_behavior"),
            ("event_config.", "event_process"),
            ("twitter_config.", "platform_dynamics"),
            ("reddit_config.", "platform_dynamics"),
            ("time_config.", "time_profile"),
        ]
        axes: List[str] = []
        for prefix, axis in axis_order:
            if any(
                field_path.startswith(prefix)
                for template in scenario_templates
                for field_path in template.field_overrides
            ) and axis not in axes:
                axes.append(axis)
        return axes

    def _derive_scenario_coverage_axes(
        self,
        scenario_templates: List[ScenarioTemplateSpec],
    ) -> List[str]:
        axes = set()
        for template in scenario_templates:
            for tag in template.coverage_tags:
                if ":" not in tag:
                    continue
                axis, _ = tag.split(":", 1)
                normalized_axis = str(axis or "").strip()
                if normalized_axis:
                    axes.add(normalized_axis)
        return sorted(axes)

    def _ensure_diversity_ready_config_payload(
        self,
        config_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        time_config = config_payload.setdefault("time_config", {})
        if isinstance(time_config, dict):
            time_config.setdefault("peak_activity_multiplier", 1.0)
            time_config.setdefault("off_peak_activity_multiplier", 0.35)
            time_config.setdefault("work_activity_multiplier", 1.0)

        event_config = config_payload.setdefault("event_config", {})
        if isinstance(event_config, dict):
            event_config.setdefault("scheduled_events", [])
            event_config.setdefault("hot_topics", ["seed"])
            event_config.setdefault("narrative_direction", "neutral")

        for platform_key in ("twitter_config", "reddit_config"):
            platform_config = config_payload.setdefault(platform_key, {})
            if not isinstance(platform_config, dict):
                continue
            platform_config.setdefault("echo_chamber_strength", 0.5)
            platform_config.setdefault("viral_threshold", 10)
        twitter_config = config_payload.get("twitter_config")
        if isinstance(twitter_config, dict):
            twitter_config.setdefault("recency_weight", 0.4)
        reddit_config = config_payload.get("reddit_config")
        if isinstance(reddit_config, dict):
            reddit_config.setdefault("relevance_weight", 0.4)

        for agent_payload in config_payload.get("agent_configs", []):
            if not isinstance(agent_payload, dict):
                continue
            agent_payload.setdefault("activity_level", 0.5)
            agent_payload.setdefault("posts_per_hour", 1.0)
            agent_payload.setdefault("comments_per_hour", 1.0)
            agent_payload.setdefault("influence_weight", 1.0)
            agent_payload.setdefault("sentiment_bias", 0.0)

        return config_payload

    def _build_lineage_context(
        self,
        state: SimulationState,
        config_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Capture deterministic lineage between project, graph, and prepared artifacts."""
        return {
            "simulation_id": state.simulation_id,
            "project_id": state.project_id,
            "graph_id": state.graph_id,
            "base_graph_id": state.base_graph_id,
            "runtime_graph_id": state.runtime_graph_id,
            "config": {
                "legacy_config": self.PREPARE_ARTIFACT_FILENAMES["legacy_config"],
                "base_config": self.PREPARE_ARTIFACT_FILENAMES["base_config"],
                "source_generated_at": config_payload.get("generated_at"),
            },
        }

    def _build_base_config_artifact(
        self,
        state: SimulationState,
        config_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the probabilistic base-config sidecar without changing legacy runtime input."""
        base_config = dict(config_payload)
        base_config.update({
            "artifact_type": "base_config",
            "schema_version": self.PREPARE_SCHEMA_VERSION,
            "generator_version": self.PREPARE_GENERATOR_VERSION,
            "lineage": self._build_lineage_context(state, config_payload),
        })
        return base_config

    def _build_outcome_spec(
        self, outcome_metrics: List[OutcomeMetricDefinition]
    ) -> Dict[str, Any]:
        """Build the initial outcome artifact for probabilistic preparation."""
        return {
            "artifact_type": "outcome_spec",
            "schema_version": self.PREPARE_SCHEMA_VERSION,
            "generator_version": self.PREPARE_GENERATOR_VERSION,
            "metrics": [metric.to_dict() for metric in outcome_metrics],
            "notes": [
                "Metrics are declared during prepare so later runtime/report stages can resolve them consistently.",
                "Probability claims are not generated by this artifact layer.",
            ],
        }

    def _build_forecast_brief_feature_metadata(
        self,
        forecast_brief: Optional[ForecastBrief],
    ) -> Dict[str, Any]:
        """Expose whether one explicit forecast brief is attached to the prepared scope."""
        return {
            "forecast_brief_attached": forecast_brief is not None,
        }

    def _build_prepared_snapshot(
        self,
        state: SimulationState,
        config_payload: Dict[str, Any],
        forecast_brief: Optional[ForecastBrief],
        grounding_summary: Dict[str, Any],
        uncertainty_spec: UncertaintySpec,
        outcome_spec: Dict[str, Any],
        sim_dir: str,
    ) -> Dict[str, Any]:
        """Build a deterministic summary of the prepared probabilistic artifact layer."""
        artifacts = {
            "legacy_config": self._describe_artifact(sim_dir, "legacy_config"),
            "base_config": self._describe_artifact(sim_dir, "base_config"),
            "forecast_brief": self._describe_artifact(sim_dir, "forecast_brief"),
            "grounding_bundle": self._describe_artifact(sim_dir, "grounding_bundle"),
            "uncertainty_spec": self._describe_artifact(sim_dir, "uncertainty_spec"),
            "outcome_spec": self._describe_artifact(sim_dir, "outcome_spec"),
            "prepared_snapshot": {
                "filename": self.PREPARE_ARTIFACT_FILENAMES["prepared_snapshot"],
                "exists": True,
            },
        }

        return {
            "artifact_type": "prepared_snapshot",
            "schema_version": self.PREPARE_SCHEMA_VERSION,
            "generator_version": self.PREPARE_GENERATOR_VERSION,
            "simulation_id": state.simulation_id,
            "prepared_at": datetime.now().isoformat(),
            "mode": "probabilistic",
            "lineage": self._build_lineage_context(state, config_payload),
            "forecast_brief": (
                forecast_brief.to_dict() if forecast_brief is not None else None
            ),
            "grounding_summary": grounding_summary,
            "feature_metadata": {
                "probabilistic_mode": True,
                "legacy_config_compatible": True,
                "outcome_metrics": [
                    metric["metric_id"] for metric in outcome_spec.get("metrics", [])
                ],
                **self._build_forecast_brief_feature_metadata(forecast_brief),
                **self._build_uncertainty_feature_metadata(uncertainty_spec),
            },
            "artifacts": artifacts,
        }
    
    def _save_simulation_state(self, state: SimulationState):
        """Save simulation state to disk."""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """Load simulation state from disk."""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            base_graph_id=data.get("base_graph_id", data.get("graph_id", "")),
            runtime_graph_id=data.get("runtime_graph_id"),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        )
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        """
        Create a new simulation.
        
        Args:
            project_id: Project ID
            graph_id: Zep graph ID
            enable_twitter: Whether to enable the Twitter simulation
            enable_reddit: Whether to enable the Reddit simulation
            
        Returns:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            base_graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            status=SimulationStatus.CREATED,
        )
        
        self._save_simulation_state(state)
        logger.info(f"Created simulation: {simulation_id}, project={project_id}, graph={graph_id}")
        
        return state
    
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3,
        probabilistic_mode: bool = False,
        uncertainty_profile: Optional[str] = None,
        outcome_metrics: Optional[List[Any]] = None,
        forecast_brief: Optional[Any] = None,
    ) -> SimulationState:
        """
        Prepare the simulation environment end to end.
        
        Steps:
        1. Read and filter entities from the Zep graph
        2. Generate an OASIS agent profile for each entity, optionally with LLM enhancement and parallelism
        3. Use the LLM to generate simulation configuration parameters such as time, activity, and posting frequency
        4. Save configuration and profile files
        5. Prepare the preset scripts required by the simulation
        
        Args:
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description used for LLM configuration generation
            document_text: Original document content used to give the LLM background context
            defined_entity_types: Predefined entity types, if any
            use_llm_for_profiles: Whether to use the LLM to generate detailed personas
            progress_callback: Progress callback `(stage, progress, message)`
            parallel_profile_count: Number of profiles to generate in parallel, default 3
            probabilistic_mode: Whether to persist probabilistic sidecar artifacts
            uncertainty_profile: Minimal uncertainty contract identifier for the sidecar
            outcome_metrics: Minimal prepared outcome metrics for the sidecar
            forecast_brief: Optional forecast-centric control-plane artifact payload
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        normalized_outcome_metrics: List[OutcomeMetricDefinition] = []
        normalized_uncertainty_profile: Optional[str] = None
        normalized_forecast_brief: Optional[ForecastBrief] = None
        if probabilistic_mode:
            normalized_outcome_metrics = self._normalize_outcome_metrics(outcome_metrics)
            normalized_uncertainty_profile = normalize_uncertainty_profile(
                uncertainty_profile
            )
            normalized_forecast_brief = normalize_forecast_brief(
                forecast_brief,
                uncertainty_profile=normalized_uncertainty_profile,
                outcome_metric_ids=[
                    metric.metric_id for metric in normalized_outcome_metrics
                ],
            )
        elif uncertainty_profile is not None or outcome_metrics or forecast_brief is not None:
            raise ValueError(
                "uncertainty_profile, outcome_metrics, and forecast_brief require probabilistic_mode=True"
            )
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            phase_timing = (
                PhaseTimingRecorder(
                    artifact_path=os.path.join(
                        sim_dir,
                        self.PREPARE_ARTIFACT_FILENAMES["prepare_phase_timings"],
                    ),
                    scope_kind="prepare",
                    scope_id=simulation_id,
                )
                if probabilistic_mode
                else None
            )
            
            # ========== Stage 1: read and filter entities ==========
            if progress_callback:
                progress_callback("reading", 0, "Connecting to the Zep graph...")
            
            reader = ZepEntityReader()
            
            if progress_callback:
                progress_callback("reading", 30, "Reading node data...")

            if phase_timing is not None:
                with phase_timing.measure_phase(
                    "entity_read",
                    metadata={"graph_id": state.graph_id, "project_id": state.project_id},
                ) as entity_read_metadata:
                    filtered = reader.filter_defined_entities(
                        graph_id=state.graph_id,
                        defined_entity_types=defined_entity_types,
                        enrich_with_edges=True,
                        project_id=state.project_id,
                    )
                    entity_read_metadata["entity_count"] = filtered.filtered_count
                    entity_read_metadata["entity_types"] = sorted(filtered.entity_types)
            else:
                filtered = reader.filter_defined_entities(
                    graph_id=state.graph_id,
                    defined_entity_types=defined_entity_types,
                    enrich_with_edges=True,
                    project_id=state.project_id,
                )
            
            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)
            
            if progress_callback:
                progress_callback(
                    "reading", 100, 
                    f"Completed, found {filtered.filtered_count} entities",
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )
            
            if filtered.filtered_count == 0:
                state.status = SimulationStatus.FAILED
                state.error = "No matching entities were found. Please verify that the graph was built correctly."
                self._save_simulation_state(state)
                return state
            
            # ========== Stage 2: generate agent profiles ==========
            total_entities = len(filtered.entities)
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 0, 
                    "Starting generation...",
                    current=0,
                    total=total_entities
                )
            
            # Pass graph_id to enable Zep retrieval for richer context
            generator = OasisProfileGenerator(graph_id=state.graph_id)
            
            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles", 
                        int(current / total * 100), 
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )
            
            # Configure the realtime output path, preferring Reddit JSON format
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"
            
            if phase_timing is not None:
                with phase_timing.measure_phase(
                    "profile_generation",
                    metadata={"entity_count": total_entities},
                ) as profile_metadata:
                    profiles = generator.generate_profiles_from_entities(
                        entities=filtered.entities,
                        use_llm=use_llm_for_profiles,
                        progress_callback=profile_progress,
                        graph_id=state.graph_id,  # Pass graph_id for Zep retrieval
                        parallel_count=parallel_profile_count,  # Parallel generation count
                        realtime_output_path=realtime_output_path,  # Realtime output path
                        output_platform=realtime_platform  # Output format
                    )
                    profile_metadata["profile_count"] = len(profiles)
            else:
                profiles = generator.generate_profiles_from_entities(
                    entities=filtered.entities,
                    use_llm=use_llm_for_profiles,
                    progress_callback=profile_progress,
                    graph_id=state.graph_id,  # Pass graph_id for Zep retrieval
                    parallel_count=parallel_profile_count,  # Parallel generation count
                    realtime_output_path=realtime_output_path,  # Realtime output path
                    output_platform=realtime_platform  # Output format
                )
            
            state.profiles_count = len(profiles)
            
            # Save profile files. Twitter uses CSV; Reddit uses JSON.
            # Reddit profiles were already saved during generation; save again to ensure completeness.
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95, 
                    "Saving profile files...",
                    current=total_entities,
                    total=total_entities
                )
            
            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )
            
            if state.enable_twitter:
                # Twitter must use CSV format because OASIS requires it
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 100, 
                    f"Completed, generated {len(profiles)} profiles",
                    current=len(profiles),
                    total=len(profiles)
                )
            
            # ========== Stage 3: generate simulation configuration with the LLM ==========
            if progress_callback:
                progress_callback(
                    "generating_config", 0, 
                    "Analyzing simulation requirements...",
                    current=0,
                    total=3
                )
            
            config_generator = SimulationConfigGenerator()
            
            if progress_callback:
                progress_callback(
                    "generating_config", 30, 
                    "Calling the LLM to generate configuration...",
                    current=1,
                    total=3
                )
            
            if phase_timing is not None:
                with phase_timing.measure_phase(
                    "config_generation",
                    metadata={"entity_count": filtered.filtered_count},
                ) as config_metadata:
                    sim_params = config_generator.generate_config(
                        simulation_id=simulation_id,
                        project_id=state.project_id,
                        graph_id=state.graph_id,
                        simulation_requirement=simulation_requirement,
                        document_text=document_text,
                        entities=filtered.entities,
                        enable_twitter=state.enable_twitter,
                        enable_reddit=state.enable_reddit
                    )
                    config_metadata["agent_config_count"] = len(
                        (sim_params.to_dict() or {}).get("agent_configs", [])
                    )
            else:
                sim_params = config_generator.generate_config(
                    simulation_id=simulation_id,
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    entities=filtered.entities,
                    enable_twitter=state.enable_twitter,
                    enable_reddit=state.enable_reddit
                )
            
            if progress_callback:
                progress_callback(
                    "generating_config", 70, 
                    "Saving configuration file...",
                    current=2,
                    total=3
                )
            
            config_payload = self._ensure_diversity_ready_config_payload(
                sim_params.to_dict()
            )

            # Save the legacy-compatible configuration file used by the current runtime.
            config_path = os.path.join(
                sim_dir, self.PREPARE_ARTIFACT_FILENAMES["legacy_config"]
            )
            self._write_json(config_path, config_payload)

            # Clear stale sidecars if the simulation is being prepared in legacy mode.
            if not probabilistic_mode:
                self._clear_probabilistic_artifacts(sim_dir)

            if probabilistic_mode:
                grounding_builder = GroundingBundleBuilder(
                    simulation_data_dir=self.SIMULATION_DATA_DIR
                )
                grounding_bundle = grounding_builder.build_bundle(
                    simulation_id=simulation_id,
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                )
                grounding_summary = grounding_builder.build_summary(grounding_bundle)
                uncertainty_spec = self._build_uncertainty_spec(
                    normalized_uncertainty_profile,
                    config_payload,
                    normalized_forecast_brief,
                )
                base_config_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["base_config"]
                )
                forecast_brief_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["forecast_brief"]
                )
                grounding_bundle_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["grounding_bundle"]
                )
                uncertainty_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["uncertainty_spec"]
                )
                outcome_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["outcome_spec"]
                )
                prepared_snapshot_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["prepared_snapshot"]
                )

                outcome_spec = self._build_outcome_spec(normalized_outcome_metrics)

                self._write_json(
                    base_config_path,
                    self._build_base_config_artifact(state, config_payload),
                )
                self._write_json(grounding_bundle_path, grounding_bundle)
                if normalized_forecast_brief is not None:
                    normalized_forecast_brief.grounding_summary = grounding_summary
                    self._write_json(
                        forecast_brief_path,
                        normalized_forecast_brief.to_dict(),
                    )
                self._write_json(uncertainty_path, uncertainty_spec.to_dict())
                self._write_json(outcome_path, outcome_spec)
                self._write_json(
                    prepared_snapshot_path,
                    self._build_prepared_snapshot(
                        state=state,
                        config_payload=config_payload,
                        forecast_brief=normalized_forecast_brief,
                        grounding_summary=grounding_summary,
                        uncertainty_spec=uncertainty_spec,
                        outcome_spec=outcome_spec,
                        sim_dir=sim_dir,
                    ),
                )
            
            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning
            
            if progress_callback:
                progress_callback(
                    "generating_config", 100, 
                    "Configuration generation complete",
                    current=3,
                    total=3
                )
            
            # Runtime scripts remain in `backend/scripts/` and are no longer copied into the simulation directory
            # When the simulation starts, simulation_runner executes the scripts from `scripts/`
            
            # Update the state
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"Simulation preparation completed: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"Simulation preparation failed: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """Get simulation state."""
        return self._load_simulation_state(simulation_id)
    
    def get_forecast_archive_metadata(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Return read-only archive metadata when this simulation is historical-only."""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        return load_forecast_archive_metadata(sim_dir)

    def list_simulations(
        self,
        project_id: Optional[str] = None,
        *,
        include_archived: bool = False,
    ) -> List[SimulationState]:
        """List all simulations."""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # Skip hidden files such as .DS_Store and any non-directory entries
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                if not include_archived and is_forecast_archived(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """Get agent profiles for a simulation."""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation configuration."""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_prepare_artifact_summary(self, simulation_id: str) -> Dict[str, Any]:
        """Summarize preparation artifacts for API responses and verification."""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        artifacts = {
            name: self._describe_artifact(sim_dir, name)
            for name in self.PREPARE_ARTIFACT_FILENAMES
        }
        missing_probabilistic_artifacts = [
            self.PREPARE_ARTIFACT_FILENAMES[name]
            for name in self.REQUIRED_PROBABILISTIC_ARTIFACT_KEYS
            if not artifacts[name]["exists"]
        ]
        probabilistic_mode = len(missing_probabilistic_artifacts) == 0
        partial_probabilistic_artifacts = len(missing_probabilistic_artifacts) < len(
            self.REQUIRED_PROBABILISTIC_ARTIFACT_KEYS
        ) and not probabilistic_mode

        uncertainty_profile = None
        uncertainty_spec = self._read_json_if_exists(
            os.path.join(sim_dir, self.PREPARE_ARTIFACT_FILENAMES["uncertainty_spec"])
        )
        if uncertainty_spec:
            uncertainty_profile = uncertainty_spec.get("profile")

        outcome_metric_ids: List[str] = []
        outcome_spec = self._read_json_if_exists(
            os.path.join(sim_dir, self.PREPARE_ARTIFACT_FILENAMES["outcome_spec"])
        )
        if outcome_spec:
            outcome_metric_ids = [
                metric.get("metric_id")
                for metric in outcome_spec.get("metrics", [])
                if metric.get("metric_id")
            ]

        prepared_snapshot = self._read_json_if_exists(
            os.path.join(sim_dir, self.PREPARE_ARTIFACT_FILENAMES["prepared_snapshot"])
        )
        grounding_bundle = self._read_json_if_exists(
            os.path.join(sim_dir, self.PREPARE_ARTIFACT_FILENAMES["grounding_bundle"])
        )
        grounding_summary = GroundingBundleBuilder(
            simulation_data_dir=self.SIMULATION_DATA_DIR
        ).build_summary(grounding_bundle)
        readiness = self.derive_prepare_readiness(
            artifacts=artifacts,
            grounding_summary=grounding_summary,
        )
        feature_metadata = {
            "probabilistic_mode": probabilistic_mode,
            "probabilistic_artifacts_complete": probabilistic_mode,
            "partial_probabilistic_artifacts": partial_probabilistic_artifacts,
            "missing_probabilistic_artifacts": missing_probabilistic_artifacts,
            "legacy_config_compatible": artifacts["legacy_config"]["exists"],
            "sampling_enabled": False,
            "forecast_brief_attached": False,
            "grounding_ready": readiness["grounding_readiness"]["ready"],
            "workflow_handoff_ready": readiness["workflow_handoff_status"]["ready"],
            "scenario_analysis_ready": readiness["forecast_readiness"]["ready"],
        }
        forecast_brief_payload = self._read_json_if_exists(
            os.path.join(sim_dir, self.PREPARE_ARTIFACT_FILENAMES["forecast_brief"])
        )
        if forecast_brief_payload:
            feature_metadata.update(
                self._build_forecast_brief_feature_metadata(
                    ForecastBrief.from_dict(forecast_brief_payload)
                )
            )
        if uncertainty_spec:
            feature_metadata.update(
                self._build_uncertainty_feature_metadata(
                    UncertaintySpec.from_dict(uncertainty_spec)
                )
            )
        lineage = {}
        if prepared_snapshot:
            feature_metadata.update(prepared_snapshot.get("feature_metadata", {}))
            lineage = prepared_snapshot.get("lineage", {})

        linked_forecast_questions = []
        try:
            from .forecast_manager import ForecastManager

            linked_forecast_questions = ForecastManager().list_question_summaries_for_simulation(
                simulation_id
            )
        except Exception:
            linked_forecast_questions = []
        feature_metadata["linked_forecast_question_count"] = len(linked_forecast_questions)

        return {
            "schema_version": self.PREPARE_SCHEMA_VERSION,
            "generator_version": self.PREPARE_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "mode": (
                "probabilistic"
                if probabilistic_mode or partial_probabilistic_artifacts
                else "legacy"
            ),
            "probabilistic_mode": probabilistic_mode,
            "uncertainty_profile": uncertainty_profile,
            "outcome_metrics": outcome_metric_ids,
            "forecast_brief": forecast_brief_payload,
            "grounding_summary": grounding_summary,
            "lineage": lineage,
            "feature_metadata": feature_metadata,
            "missing_probabilistic_artifacts": missing_probabilistic_artifacts,
            "artifact_completeness": readiness["artifact_completeness"],
            "grounding_readiness": readiness["grounding_readiness"],
            "forecast_readiness": readiness["forecast_readiness"],
            "workflow_handoff_status": readiness["workflow_handoff_status"],
            "linked_forecast_questions": linked_forecast_questions,
            "artifacts": artifacts,
        }
    
    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """Get run instructions."""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. Activate the conda environment: conda activate MiroFishES\n"
                f"2. Run the simulation (scripts are located in {scripts_dir}):\n"
                f"   - Run Twitter only: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - Run Reddit only: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - Run both platforms in parallel: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }
