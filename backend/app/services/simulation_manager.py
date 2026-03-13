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
    DEFAULT_OUTCOME_METRICS,
    OutcomeMetricDefinition,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    RandomVariableSpec,
    SeedPolicy,
    UncertaintySpec,
    build_supported_outcome_metric,
    normalize_uncertainty_profile,
    validate_outcome_metric_id,
)
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters

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
        "uncertainty_spec": "uncertainty_spec.json",
        "outcome_spec": "outcome_spec.json",
        "prepared_snapshot": "prepared_snapshot.json",
    }
    REQUIRED_PROBABILISTIC_ARTIFACT_KEYS = (
        "base_config",
        "uncertainty_spec",
        "outcome_spec",
        "prepared_snapshot",
    )
    PREPARE_SCHEMA_VERSION = PROBABILISTIC_SCHEMA_VERSION
    PREPARE_GENERATOR_VERSION = PROBABILISTIC_GENERATOR_VERSION
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
            "uncertainty_spec",
            "outcome_spec",
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
        return UncertaintySpec(
            profile=normalized_profile,
            random_variables=random_variables,
            seed_policy=SeedPolicy(),
            notes=[
                "Preparation persists one explicit catalog of run-varying config fields.",
                "Persona text, graph-derived identity, and scheduled events remain fixed in this slice.",
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
        return {
            "uncertainty_profile": uncertainty_spec.profile,
            "seed_policy": uncertainty_spec.seed_policy.to_dict(),
            "random_variable_count": len(variable_paths),
            "non_fixed_random_variable_count": non_fixed_count,
            "random_variable_preview": variable_paths[:5],
            "sampling_enabled": non_fixed_count > 0,
        }

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

    def _build_prepared_snapshot(
        self,
        state: SimulationState,
        config_payload: Dict[str, Any],
        uncertainty_spec: UncertaintySpec,
        outcome_spec: Dict[str, Any],
        sim_dir: str,
    ) -> Dict[str, Any]:
        """Build a deterministic summary of the prepared probabilistic artifact layer."""
        artifacts = {
            "legacy_config": self._describe_artifact(sim_dir, "legacy_config"),
            "base_config": self._describe_artifact(sim_dir, "base_config"),
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
            "feature_metadata": {
                "probabilistic_mode": True,
                "legacy_config_compatible": True,
                "outcome_metrics": [
                    metric["metric_id"] for metric in outcome_spec.get("metrics", [])
                ],
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
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        normalized_outcome_metrics: List[OutcomeMetricDefinition] = []
        normalized_uncertainty_profile: Optional[str] = None
        if probabilistic_mode:
            normalized_outcome_metrics = self._normalize_outcome_metrics(outcome_metrics)
            normalized_uncertainty_profile = normalize_uncertainty_profile(
                uncertainty_profile
            )
        elif uncertainty_profile is not None or outcome_metrics:
            raise ValueError(
                "uncertainty_profile and outcome_metrics require probabilistic_mode=True"
            )
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            
            # ========== Stage 1: read and filter entities ==========
            if progress_callback:
                progress_callback("reading", 0, "Connecting to the Zep graph...")
            
            reader = ZepEntityReader()
            
            if progress_callback:
                progress_callback("reading", 30, "Reading node data...")
            
            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
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
            
            config_payload = sim_params.to_dict()

            # Save the legacy-compatible configuration file used by the current runtime.
            config_path = os.path.join(
                sim_dir, self.PREPARE_ARTIFACT_FILENAMES["legacy_config"]
            )
            self._write_json(config_path, config_payload)

            # Clear stale sidecars if the simulation is being prepared in legacy mode.
            self._clear_probabilistic_artifacts(sim_dir)

            if probabilistic_mode:
                uncertainty_spec = self._build_uncertainty_spec(
                    normalized_uncertainty_profile,
                    config_payload,
                )
                base_config_path = os.path.join(
                    sim_dir, self.PREPARE_ARTIFACT_FILENAMES["base_config"]
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
                self._write_json(uncertainty_path, uncertainty_spec.to_dict())
                self._write_json(outcome_path, outcome_spec)
                self._write_json(
                    prepared_snapshot_path,
                    self._build_prepared_snapshot(
                        state=state,
                        config_payload=config_payload,
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
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """List all simulations."""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # Skip hidden files such as .DS_Store and any non-directory entries
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
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
        if not os.path.exists(sim_dir):
            return {
                "schema_version": self.PREPARE_SCHEMA_VERSION,
                "generator_version": self.PREPARE_GENERATOR_VERSION,
                "simulation_id": simulation_id,
                "mode": "legacy",
                "probabilistic_mode": False,
                "uncertainty_profile": None,
                "outcome_metrics": [],
                "lineage": {},
                "feature_metadata": {
                    "probabilistic_mode": False,
                    "legacy_config_compatible": False,
                    "sampling_enabled": False,
                },
                "artifacts": {
                    name: self._describe_artifact(sim_dir, name)
                    for name in self.PREPARE_ARTIFACT_FILENAMES
                },
            }

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
        feature_metadata = {
            "probabilistic_mode": probabilistic_mode,
            "probabilistic_artifacts_complete": probabilistic_mode,
            "partial_probabilistic_artifacts": partial_probabilistic_artifacts,
            "missing_probabilistic_artifacts": missing_probabilistic_artifacts,
            "legacy_config_compatible": artifacts["legacy_config"]["exists"],
            "sampling_enabled": False,
        }
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

        return {
            "schema_version": self.PREPARE_SCHEMA_VERSION,
            "generator_version": self.PREPARE_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "mode": "probabilistic" if probabilistic_mode else "legacy",
            "probabilistic_mode": probabilistic_mode,
            "uncertainty_profile": uncertainty_profile,
            "outcome_metrics": outcome_metric_ids,
            "lineage": lineage,
            "feature_metadata": feature_metadata,
            "missing_probabilistic_artifacts": missing_probabilistic_artifacts,
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
