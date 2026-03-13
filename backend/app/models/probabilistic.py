"""
Minimal probabilistic artifact models for the preparation foundation slice.

This module intentionally focuses on validation and serialization contracts.
Sampling and runtime resolution land in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PROBABILISTIC_SCHEMA_VERSION = "probabilistic.prepare.v1"
PROBABILISTIC_GENERATOR_VERSION = "probabilistic.prepare.generator.v1"
SUPPORTED_DISTRIBUTIONS = {"fixed", "categorical", "uniform", "normal"}
SUPPORTED_UNCERTAINTY_PROFILES = {
    "deterministic-baseline",
    "balanced",
    "stress-test",
}
DEFAULT_UNCERTAINTY_PROFILE = "deterministic-baseline"
DEFAULT_OUTCOME_METRICS = ("simulation.total_actions",)
SUPPORTED_OUTCOME_METRIC_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "simulation.total_actions": {
        "label": "Simulation Total Actions",
        "description": "Count all actions across every enabled platform.",
    },
    "platform.twitter.total_actions": {
        "label": "Twitter Total Actions",
        "description": "Count all Twitter-side actions.",
    },
    "platform.reddit.total_actions": {
        "label": "Reddit Total Actions",
        "description": "Count all Reddit-side actions.",
    },
}
SUPPORTED_OUTCOME_METRICS = frozenset(SUPPORTED_OUTCOME_METRIC_DEFINITIONS)
SUPPORTED_SEED_STRATEGIES = {"deterministic-root"}


def _coerce_non_negative_int(value: Any, default: int = 0) -> int:
    """Normalize persisted counters without letting malformed values go negative."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(normalized, 0)


def build_default_run_lifecycle(
    lifecycle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the persisted lifecycle contract for one stored run manifest."""
    lifecycle = dict(lifecycle or {})
    return {
        "start_count": _coerce_non_negative_int(lifecycle.get("start_count")),
        "retry_count": _coerce_non_negative_int(lifecycle.get("retry_count")),
        "cleanup_count": _coerce_non_negative_int(lifecycle.get("cleanup_count")),
        "last_launch_reason": lifecycle.get("last_launch_reason"),
    }


def build_default_run_lineage(
    ensemble_id: Optional[str],
    lineage: Optional[Dict[str, Any]] = None,
    *,
    default_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Return one stable lineage payload for seeded members and reruns alike."""
    lineage = dict(lineage or {})
    kind = lineage.get("kind")
    if not kind:
        kind = default_kind or ("seeded_member" if ensemble_id else "legacy_single_run")
    return {
        "kind": kind,
        "source_run_id": lineage.get("source_run_id"),
        "parent_run_id": lineage.get("parent_run_id"),
    }


def normalize_uncertainty_profile(profile: Optional[str]) -> str:
    """Return a supported uncertainty profile or raise a clear error."""
    normalized = profile or DEFAULT_UNCERTAINTY_PROFILE
    if normalized not in SUPPORTED_UNCERTAINTY_PROFILES:
        raise ValueError(
            f"Unsupported uncertainty profile: {normalized}. "
            f"Supported: {sorted(SUPPORTED_UNCERTAINTY_PROFILES)}"
        )
    return normalized


def validate_outcome_metric_id(metric_id: str) -> str:
    """Ensure the requested outcome metric is in the explicit allowlist."""
    if metric_id not in SUPPORTED_OUTCOME_METRICS:
        raise ValueError(
            f"Unsupported outcome metric: {metric_id}. "
            f"Supported: {sorted(SUPPORTED_OUTCOME_METRICS)}"
        )
    return metric_id


def build_supported_outcome_metric(metric_id: str) -> "OutcomeMetricDefinition":
    """Create a metric definition from the explicit registry."""
    validate_outcome_metric_id(metric_id)
    definition = SUPPORTED_OUTCOME_METRIC_DEFINITIONS[metric_id]
    return OutcomeMetricDefinition(
        metric_id=metric_id,
        label=definition["label"],
        description=definition["description"],
    )


def get_prepare_capabilities_domain() -> Dict[str, Any]:
    """Return the read-only probabilistic prepare capability domain."""
    return {
        "supported_uncertainty_profiles": sorted(SUPPORTED_UNCERTAINTY_PROFILES),
        "default_uncertainty_profile": DEFAULT_UNCERTAINTY_PROFILE,
        "supported_outcome_metrics": SUPPORTED_OUTCOME_METRIC_DEFINITIONS,
        "default_outcome_metrics": list(DEFAULT_OUTCOME_METRICS),
        "schema_version": PROBABILISTIC_SCHEMA_VERSION,
        "generator_version": PROBABILISTIC_GENERATOR_VERSION,
    }


@dataclass(eq=True)
class RandomVariableSpec:
    """One unresolved field that may vary across future ensemble runs."""

    field_path: str
    distribution: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.field_path:
            raise ValueError("field_path is required")
        if self.distribution not in SUPPORTED_DISTRIBUTIONS:
            raise ValueError(
                f"Unsupported distribution: {self.distribution}. "
                f"Supported: {sorted(SUPPORTED_DISTRIBUTIONS)}"
            )
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")

        if self.distribution == "categorical":
            choices = self.parameters.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("categorical distributions require a non-empty choices list")
            weights = self.parameters.get("weights")
            if weights is not None and len(weights) != len(choices):
                raise ValueError("categorical weights must match choices length")

        if self.distribution == "uniform":
            low = self.parameters.get("low")
            high = self.parameters.get("high")
            if low is None or high is None or low > high:
                raise ValueError("uniform distributions require low <= high")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "distribution": self.distribution,
            "parameters": self.parameters,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RandomVariableSpec":
        return cls(
            field_path=data["field_path"],
            distribution=data["distribution"],
            parameters=data.get("parameters", {}),
            description=data.get("description"),
        )


@dataclass(eq=True)
class OutcomeMetricDefinition:
    """One metric the future aggregation/reporting stack should compute."""

    metric_id: str
    label: str
    description: str
    aggregation: str = "count"
    unit: str = "count"
    probability_mode: str = "empirical"
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ValueError("metric_id is required")
        if not self.label:
            raise ValueError("label is required")
        if not self.description:
            raise ValueError("description is required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "label": self.label,
            "description": self.description,
            "aggregation": self.aggregation,
            "unit": self.unit,
            "probability_mode": self.probability_mode,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutcomeMetricDefinition":
        return cls(
            metric_id=data["metric_id"],
            label=data["label"],
            description=data["description"],
            aggregation=data.get("aggregation", "count"),
            unit=data.get("unit", "count"),
            probability_mode=data.get("probability_mode", "empirical"),
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
        )


@dataclass(eq=True)
class SeedPolicy:
    """Seed derivation contract for future ensemble execution."""

    strategy: str = "deterministic-root"
    root_seed: int = 0
    derive_run_seeds: bool = True
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if self.strategy not in SUPPORTED_SEED_STRATEGIES:
            raise ValueError(
                f"Unsupported seed strategy: {self.strategy}. "
                f"Supported: {sorted(SUPPORTED_SEED_STRATEGIES)}"
            )
        if self.root_seed < 0:
            raise ValueError("root_seed must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "strategy": self.strategy,
            "root_seed": self.root_seed,
            "derive_run_seeds": self.derive_run_seeds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeedPolicy":
        return cls(
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
            strategy=data.get("strategy", "deterministic-root"),
            root_seed=data.get("root_seed", 0),
            derive_run_seeds=data.get("derive_run_seeds", True),
        )


@dataclass(eq=True)
class UncertaintySpec:
    """Preparation-time uncertainty contract for later runtime resolution."""

    profile: str
    random_variables: List[RandomVariableSpec] = field(default_factory=list)
    artifact_type: str = "uncertainty_spec"
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION
    root_seed: Optional[int] = None
    seed_policy: SeedPolicy = field(default_factory=SeedPolicy)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.profile:
            raise ValueError("profile is required")
        self.profile = normalize_uncertainty_profile(self.profile)
        if self.root_seed is None:
            self.root_seed = self.seed_policy.root_seed
        elif self.seed_policy.root_seed != self.root_seed:
            self.seed_policy.root_seed = self.root_seed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "profile": self.profile,
            "root_seed": self.root_seed,
            "seed_policy": self.seed_policy.to_dict(),
            "notes": self.notes,
            "random_variables": [item.to_dict() for item in self.random_variables],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UncertaintySpec":
        return cls(
            artifact_type=data.get("artifact_type", "uncertainty_spec"),
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
            profile=data["profile"],
            root_seed=data.get("root_seed"),
            seed_policy=SeedPolicy.from_dict(
                data.get("seed_policy", {"root_seed": data.get("root_seed", 0)})
            ),
            notes=data.get("notes", []),
            random_variables=[
                RandomVariableSpec.from_dict(item)
                for item in data.get("random_variables", [])
            ],
        )


@dataclass(eq=True)
class EnsembleSpec:
    """Execution policy for a family of stochastic runs."""

    run_count: int
    max_concurrency: int = 1
    root_seed: Optional[int] = None
    sampling_mode: str = "seeded"
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if self.run_count <= 0:
            raise ValueError("run_count must be positive")
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        if self.max_concurrency > self.run_count:
            raise ValueError("max_concurrency cannot exceed run_count")
        if self.root_seed is not None and self.root_seed < 0:
            raise ValueError("root_seed must be non-negative")
        if self.sampling_mode not in {"seeded", "unseeded"}:
            raise ValueError("sampling_mode must be 'seeded' or 'unseeded'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "run_count": self.run_count,
            "max_concurrency": self.max_concurrency,
            "root_seed": self.root_seed,
            "sampling_mode": self.sampling_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnsembleSpec":
        return cls(
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
            run_count=data["run_count"],
            max_concurrency=data.get("max_concurrency", 1),
            root_seed=data.get("root_seed"),
            sampling_mode=data.get("sampling_mode", "seeded"),
        )


@dataclass(eq=True)
class RunManifest:
    """Recorded inputs and resolved values for one future concrete run."""

    simulation_id: str
    run_id: str
    ensemble_id: Optional[str] = None
    base_graph_id: Optional[str] = None
    runtime_graph_id: Optional[str] = None
    root_seed: Optional[int] = None
    seed_metadata: Dict[str, Any] = field(default_factory=dict)
    resolved_values: Dict[str, Any] = field(default_factory=dict)
    config_artifact: str = "resolved_config.json"
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    generated_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: str = "prepared"
    lifecycle: Dict[str, Any] = field(default_factory=build_default_run_lifecycle)
    lineage: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not self.run_id:
            raise ValueError("run_id is required")
        if not isinstance(self.seed_metadata, dict):
            raise ValueError("seed_metadata must be a dictionary")
        if not isinstance(self.resolved_values, dict):
            raise ValueError("resolved_values must be a dictionary")
        if not isinstance(self.artifact_paths, dict):
            raise ValueError("artifact_paths must be a dictionary")
        self.lifecycle = build_default_run_lifecycle(self.lifecycle)
        self.lineage = build_default_run_lineage(
            self.ensemble_id,
            self.lineage,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "simulation_id": self.simulation_id,
            "run_id": self.run_id,
            "ensemble_id": self.ensemble_id,
            "base_graph_id": self.base_graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "root_seed": self.root_seed,
            "seed_metadata": self.seed_metadata,
            "resolved_values": self.resolved_values,
            "config_artifact": self.config_artifact,
            "artifact_paths": self.artifact_paths,
            "generated_at": self.generated_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "lifecycle": self.lifecycle,
            "lineage": self.lineage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunManifest":
        return cls(
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
            simulation_id=data["simulation_id"],
            run_id=data["run_id"],
            ensemble_id=data.get("ensemble_id"),
            base_graph_id=data.get("base_graph_id"),
            runtime_graph_id=data.get("runtime_graph_id"),
            root_seed=data.get("root_seed"),
            seed_metadata=data.get("seed_metadata", {}),
            resolved_values=data.get("resolved_values", {}),
            config_artifact=data.get("config_artifact", "resolved_config.json"),
            artifact_paths=data.get("artifact_paths", {}),
            generated_at=data.get("generated_at"),
            updated_at=data.get("updated_at"),
            status=data.get("status", "prepared"),
            lifecycle=data.get("lifecycle", {}),
            lineage=data.get("lineage", {}),
        )
