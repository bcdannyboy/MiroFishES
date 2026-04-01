"""
Minimal probabilistic artifact models for the preparation foundation slice.

This module intentionally focuses on validation and serialization contracts.
Sampling and runtime resolution land in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


PROBABILISTIC_SCHEMA_VERSION = "probabilistic.prepare.v1"
PROBABILISTIC_GENERATOR_VERSION = "probabilistic.prepare.generator.v1"
OBSERVED_TRUTH_SCHEMA_VERSION = "probabilistic.observed_truth.v2"
OBSERVED_TRUTH_GENERATOR_VERSION = "probabilistic.observed_truth.generator.v2"
BACKTEST_SCHEMA_VERSION = "probabilistic.backtest.v2"
BACKTEST_GENERATOR_VERSION = "probabilistic.backtest.generator.v2"
CALIBRATION_SCHEMA_VERSION = "probabilistic.calibration.v2"
CALIBRATION_GENERATOR_VERSION = "probabilistic.calibration.generator.v2"
SUPPORTED_DISTRIBUTIONS = {"fixed", "categorical", "uniform", "normal"}
SUPPORTED_UNCERTAINTY_PROFILES = {
    "deterministic-baseline",
    "balanced",
    "stress-test",
}
DEFAULT_UNCERTAINTY_PROFILE = "deterministic-baseline"
DEFAULT_OUTCOME_METRICS = ("simulation.total_actions",)
SUPPORTED_SCORING_RULES = {"brier_score", "log_score"}
SUPPORTED_SUMMARY_SCORE_KEYS = {"brier_score", "log_score", "brier_skill_score"}
SUPPORTED_OUTCOME_METRIC_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "simulation.total_actions": {
        "label": "Simulation Total Actions",
        "description": "Count all actions across every enabled platform.",
        "aggregation": "count",
        "unit": "count",
        "value_kind": "numeric",
    },
    "simulation.any_actions": {
        "label": "Simulation Any Actions",
        "description": "Flag whether the run produced any observed action logs.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "simulation.completed": {
        "label": "Simulation Completed",
        "description": "Flag whether every expected platform emitted an explicit simulation_end marker.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "simulation.unique_active_agents": {
        "label": "Simulation Unique Active Agents",
        "description": "Count the distinct agents that produced at least one observed action.",
        "aggregation": "count",
        "unit": "agents",
        "value_kind": "numeric",
    },
    "simulation.rounds_with_actions": {
        "label": "Simulation Rounds With Actions",
        "description": "Count the observed rounds that contained at least one action entry.",
        "aggregation": "count",
        "unit": "rounds",
        "value_kind": "numeric",
    },
    "simulation.observed_action_window_seconds": {
        "label": "Simulation Observed Action Window",
        "description": (
            "Measure the observed span in seconds between the first and last action log entries."
        ),
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "simulation.observed_completion_window_seconds": {
        "label": "Simulation Observed Completion Window",
        "description": (
            "Measure elapsed seconds from the first observed action to the recorded run completion time when both timestamps are explicit."
        ),
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "simulation.time_to_first_action_seconds": {
        "label": "Simulation Time To First Action",
        "description": "Measure elapsed seconds from the recorded run start until the first observed action when both timestamps are explicit.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "simulation.active_round_share": {
        "label": "Simulation Active Round Share",
        "description": "Measure the share of configured simulation rounds that produced at least one observed action.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "simulation.actions_per_active_round_cv": {
        "label": "Simulation Actions Per Active Round CV",
        "description": "Summarize the volatility of action counts across active rounds using the coefficient of variation.",
        "aggregation": "dispersion",
        "unit": "cv",
        "value_kind": "numeric",
    },
    "simulation.agent_action_concentration_hhi": {
        "label": "Agent Action Concentration",
        "description": "Summarize how concentrated activity was across active agents using a Herfindahl-Hirschman style index.",
        "aggregation": "concentration",
        "unit": "hhi",
        "value_kind": "numeric",
    },
    "simulation.top_agent_action_share": {
        "label": "Top Agent Action Share",
        "description": "Measure the share of observed actions contributed by the most active agent.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "simulation.top_2_agent_action_share": {
        "label": "Top 2 Agent Action Share",
        "description": "Measure the share of observed actions contributed by the two most active agents combined.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "simulation.max_round_action_share": {
        "label": "Maximum Round Action Share",
        "description": "Measure the share of observed actions concentrated in the single busiest round.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "simulation.top_agent_action_share_ge_0_5": {
        "label": "Top Agent Action Share At Least 0.5",
        "description": "Flag whether the most active agent contributed at least half of all observed actions.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "platform.twitter.total_actions": {
        "label": "Twitter Total Actions",
        "description": "Count all Twitter-side actions.",
        "aggregation": "count",
        "unit": "count",
        "value_kind": "numeric",
    },
    "platform.reddit.total_actions": {
        "label": "Reddit Total Actions",
        "description": "Count all Reddit-side actions.",
        "aggregation": "count",
        "unit": "count",
        "value_kind": "numeric",
    },
    "platform.twitter.any_actions": {
        "label": "Twitter Any Actions",
        "description": "Flag whether Twitter emitted any observed actions in the run.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "platform.reddit.any_actions": {
        "label": "Reddit Any Actions",
        "description": "Flag whether Reddit emitted any observed actions in the run.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "platform.twitter.action_share": {
        "label": "Twitter Action Share",
        "description": "Measure Twitter's share of all observed actions in the run.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "platform.reddit.action_share": {
        "label": "Reddit Action Share",
        "description": "Measure Reddit's share of all observed actions in the run.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "platform.twitter.observed_action_window_seconds": {
        "label": "Twitter Observed Action Window",
        "description": (
            "Measure the observed span in seconds between Twitter's first and last action log entries."
        ),
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "platform.reddit.observed_action_window_seconds": {
        "label": "Reddit Observed Action Window",
        "description": (
            "Measure the observed span in seconds between Reddit's first and last action log entries."
        ),
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "platform.twitter.time_to_first_action_seconds": {
        "label": "Twitter Time To First Action",
        "description": "Measure elapsed seconds from the recorded run start until Twitter emitted its first observed action.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "platform.reddit.time_to_first_action_seconds": {
        "label": "Reddit Time To First Action",
        "description": "Measure elapsed seconds from the recorded run start until Reddit emitted its first observed action.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "platform.leading_platform": {
        "label": "Leading Platform",
        "description": "Identify which platform contributed the larger share of observed actions, or whether activity was tied.",
        "aggregation": "category",
        "unit": "category",
        "value_kind": "categorical",
    },
    "platform.action_balance_gap": {
        "label": "Platform Action Balance Gap",
        "description": "Measure the absolute difference between Twitter and Reddit action share.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "platform.action_balance_gap_ge_0_5": {
        "label": "Platform Action Balance Gap At Least 0.5",
        "description": "Flag whether one platform exceeded the other by at least half of total observed action share.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "platform.action_balance_band": {
        "label": "Platform Action Balance Band",
        "description": "Bucket the observed platform action-share gap into balanced, tilted, or dominated regimes.",
        "aggregation": "category",
        "unit": "category",
        "value_kind": "categorical",
    },
    "cross_platform.first_action_lag_seconds": {
        "label": "Cross-Platform First Action Lag",
        "description": "Measure the observed lag in seconds between Twitter's first action and Reddit's first action.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "cross_platform.completion_lag_seconds": {
        "label": "Cross-Platform Completion Lag",
        "description": "Measure the observed lag in seconds between Twitter's completion marker and Reddit's completion marker.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "cross_platform.topic_transfer_observed": {
        "label": "Cross-Platform Topic Transfer Observed",
        "description": "Flag whether at least one normalized topic was observed on both supported platforms during the run.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "cross_platform.topic_transfer_lag_seconds": {
        "label": "Cross-Platform Topic Transfer Lag",
        "description": "Measure the shortest observed lag in seconds between the first cross-platform sightings of a shared normalized topic.",
        "aggregation": "duration",
        "unit": "seconds",
        "value_kind": "numeric",
    },
    "content.unique_topics_mentioned": {
        "label": "Unique Topics Mentioned",
        "description": "Count the distinct topic labels or configured hot topics that appeared in observed actions.",
        "aggregation": "count",
        "unit": "topics",
        "value_kind": "numeric",
    },
    "content.top_topic_share": {
        "label": "Top Topic Share",
        "description": "Measure the share of all observed topic mentions captured by the most-mentioned topic.",
        "aggregation": "ratio",
        "unit": "share",
        "value_kind": "numeric",
    },
    "content.top_topic_share_ge_0_5": {
        "label": "Top Topic Share At Least 0.5",
        "description": "Flag whether the most-mentioned topic captured at least half of all observed topic mentions.",
        "aggregation": "flag",
        "unit": "boolean",
        "value_kind": "binary",
    },
    "content.dominant_topic": {
        "label": "Dominant Topic",
        "description": "Identify the most-mentioned observed topic when at least one topic mention exists.",
        "aggregation": "category",
        "unit": "category",
        "value_kind": "categorical",
    },
    "content.dominant_topic_agent_reach": {
        "label": "Dominant Topic Agent Reach",
        "description": "Count the distinct agents that mentioned the observed dominant topic at least once.",
        "aggregation": "count",
        "unit": "agents",
        "value_kind": "numeric",
    },
    "content.dominant_topic_platform_reach": {
        "label": "Dominant Topic Platform Reach",
        "description": "Count the distinct supported platforms where the observed dominant topic appeared at least once.",
        "aggregation": "count",
        "unit": "platforms",
        "value_kind": "numeric",
    },
    "content.dominant_topic_round_reach": {
        "label": "Dominant Topic Round Reach",
        "description": "Count the distinct rounds where the observed dominant topic appeared at least once.",
        "aggregation": "count",
        "unit": "rounds",
        "value_kind": "numeric",
    },
    "content.topic_concentration_hhi": {
        "label": "Topic Concentration",
        "description": "Summarize how concentrated observed topic mentions were using a Herfindahl-Hirschman style index.",
        "aggregation": "concentration",
        "unit": "hhi",
        "value_kind": "numeric",
    },
    "content.topic_concentration_band": {
        "label": "Topic Concentration Band",
        "description": "Bucket observed topic concentration into diffuse, mixed, or focused regimes.",
        "aggregation": "category",
        "unit": "category",
        "value_kind": "categorical",
    },
}
SUPPORTED_OUTCOME_METRICS = frozenset(SUPPORTED_OUTCOME_METRIC_DEFINITIONS)
SUPPORTED_SEED_STRATEGIES = {"deterministic-root"}
SUPPORTED_GROUP_CORRELATION_MODES = {"shared_rank"}
SUPPORTED_CONDITIONAL_OPERATORS = {"eq", "in", "gte", "lte"}
SUPPORTED_EXPERIMENT_DESIGN_METHODS = {"latin-hypercube"}
SUPPORTED_SCENARIO_ASSIGNMENTS = {"cyclic", "weighted_cycle", "none"}
SUPPORTED_STRUCTURAL_UNCERTAINTY_KINDS = {
    "event_arrival_process",
    "exposure_path_variation",
    "influencer_activation",
    "credibility_shock",
    "moderation_policy_change",
    "graph_rewiring",
}
SUPPORTED_TEMPLATE_COMBINATION_POLICIES = {"single_template", "pairwise"}
CALIBRATION_BOUNDARY_NOTE = (
    "Ensemble calibration artifacts apply only to named simulation metrics with "
    "validated backtest artifacts. Forecast-workspace categorical and numeric "
    "calibration, when present, is a separate answer-bound lane."
)


def _coerce_non_negative_int(value: Any, default: int = 0) -> int:
    """Normalize persisted counters without letting malformed values go negative."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(normalized, 0)


def _normalize_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_string_list(
    values: Any,
    *,
    field_name: str,
    allow_empty: bool = True,
) -> List[str]:
    """Normalize one list of user-provided strings without silently dropping bad entries."""
    if values is None:
        if allow_empty:
            return []
        raise ValueError(f"{field_name} is required")
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: List[str] = []
    seen = set()
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} entries must be strings")
        text = item.strip()
        if not text:
            raise ValueError(f"{field_name} entries must be non-empty strings")
        if text not in seen:
            normalized.append(text)
            seen.add(text)

    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return normalized


def _normalize_iso_resolution_date(value: Any) -> str:
    """Validate one forecast resolution date without changing the caller's chosen precision."""
    if value is None:
        raise ValueError("resolution_date is required")

    normalized = str(value).strip()
    if not normalized:
        raise ValueError("resolution_date is required")

    parse_candidate = normalized.replace("Z", "+00:00") if normalized.endswith("Z") else normalized
    try:
        if "T" in parse_candidate or " " in parse_candidate:
            datetime.fromisoformat(parse_candidate)
        else:
            date.fromisoformat(parse_candidate)
    except ValueError as exc:
        raise ValueError(
            "resolution_date must be an ISO 8601 date or datetime string"
        ) from exc

    return normalized


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
        aggregation=definition.get("aggregation", "count"),
        unit=definition.get("unit", "count"),
        probability_mode=definition.get("probability_mode", "empirical"),
        value_kind=definition.get("value_kind", "numeric"),
        confidence_support=_build_confidence_support(
            metric_id=metric_id,
            definition=definition,
        ),
    )


def get_prepare_capabilities_domain() -> Dict[str, Any]:
    """Return the read-only probabilistic prepare capability domain."""
    return {
        "supported_uncertainty_profiles": sorted(SUPPORTED_UNCERTAINTY_PROFILES),
        "default_uncertainty_profile": DEFAULT_UNCERTAINTY_PROFILE,
        "supported_scoring_rules": sorted(SUPPORTED_SCORING_RULES),
        "supported_outcome_metrics": {
            metric_id: {
                **definition,
                "confidence_support": _build_confidence_support(
                    metric_id=metric_id,
                    definition=definition,
                ),
            }
            for metric_id, definition in SUPPORTED_OUTCOME_METRIC_DEFINITIONS.items()
        },
        "default_outcome_metrics": list(DEFAULT_OUTCOME_METRICS),
        "schema_version": PROBABILISTIC_SCHEMA_VERSION,
        "generator_version": PROBABILISTIC_GENERATOR_VERSION,
    }


def _build_confidence_support(
    *,
    metric_id: str,
    definition: Dict[str, Any],
) -> Dict[str, Any]:
    if isinstance(definition.get("confidence_support"), dict):
        return dict(definition["confidence_support"])

    if definition.get("value_kind") == "binary":
        return {
            "backtesting_supported": True,
            "calibration_supported": True,
            "support_tier": "binary-ready",
            "boundary_note": (
                "Binary backtesting and calibration are supported only when "
                "explicit observed-truth artifacts exist."
            ),
        }

    return {
        "backtesting_supported": False,
        "calibration_supported": False,
        "support_tier": "unsupported",
        "boundary_note": (
            "This metric remains empirical or observed only; calibrated language "
            "is not supported in-repo."
        ),
    }


def _normalize_scoring_rules(
    scoring_rules: List[str],
    *,
    field_name: str,
    allow_empty: bool = True,
) -> List[str]:
    normalized = _normalize_string_list(
        scoring_rules,
        field_name=field_name,
        allow_empty=allow_empty,
    )
    for scoring_rule in normalized:
        if scoring_rule not in SUPPORTED_SCORING_RULES:
            raise ValueError(
                f"Unsupported scoring rule for {field_name}: {scoring_rule}. "
                f"Supported: {sorted(SUPPORTED_SCORING_RULES)}"
            )
    return normalized


def _normalize_iso_datetime(
    value: Optional[str],
    *,
    field_name: str,
    allow_empty: bool = True,
) -> Optional[str]:
    if value in (None, ""):
        if allow_empty:
            return None
        raise ValueError(f"{field_name} is required")

    normalized = str(value).strip()
    if not normalized:
        if allow_empty:
            return None
        raise ValueError(f"{field_name} is required")

    parse_value = normalized.replace("Z", "+00:00") if normalized.endswith("Z") else normalized
    try:
        datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime string") from exc
    return normalized


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
    value_kind: str = "numeric"
    confidence_support: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ValueError("metric_id is required")
        if not self.label:
            raise ValueError("label is required")
        if not self.description:
            raise ValueError("description is required")
        if self.value_kind not in {"numeric", "binary", "categorical"}:
            raise ValueError("value_kind must be numeric, binary, or categorical")
        if not isinstance(self.confidence_support, dict):
            raise ValueError("confidence_support must be a dictionary")
        if not self.confidence_support:
            self.confidence_support = _build_confidence_support(
                metric_id=self.metric_id,
                definition={"value_kind": self.value_kind},
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "label": self.label,
            "description": self.description,
            "aggregation": self.aggregation,
            "unit": self.unit,
            "probability_mode": self.probability_mode,
            "value_kind": self.value_kind,
            "confidence_support": dict(self.confidence_support),
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
            value_kind=data.get("value_kind", "numeric"),
            confidence_support=data.get("confidence_support", {}),
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
class VariableGroupSpec:
    """Coarsely couple related variables inside one structured design group."""

    group_id: str
    field_paths: List[str]
    correlation_mode: str = "shared_rank"
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.group_id = str(self.group_id or "").strip()
        if not self.group_id:
            raise ValueError("group_id is required")
        self.field_paths = _normalize_string_list(
            self.field_paths,
            field_name="field_paths",
            allow_empty=False,
        )
        if len(self.field_paths) < 2:
            raise ValueError("field_paths must contain at least two entries")
        if self.correlation_mode not in SUPPORTED_GROUP_CORRELATION_MODES:
            raise ValueError(
                f"Unsupported correlation mode: {self.correlation_mode}. "
                f"Supported: {sorted(SUPPORTED_GROUP_CORRELATION_MODES)}"
            )
        self.notes = _normalize_string_list(
            self.notes,
            field_name="variable_group.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "field_paths": list(self.field_paths),
            "correlation_mode": self.correlation_mode,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VariableGroupSpec":
        return cls(
            group_id=data["group_id"],
            field_paths=data["field_paths"],
            correlation_mode=data.get("correlation_mode", "shared_rank"),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class ConditionalVariableSpec:
    """Apply one variable only when an explicit resolved condition is met."""

    variable: RandomVariableSpec
    condition_field_path: str
    operator: str
    condition_value: Any
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.variable, dict):
            self.variable = RandomVariableSpec.from_dict(self.variable)
        elif not isinstance(self.variable, RandomVariableSpec):
            raise ValueError("variable must be a RandomVariableSpec or dictionary")
        self.condition_field_path = str(self.condition_field_path or "").strip()
        if not self.condition_field_path:
            raise ValueError("condition_field_path is required")
        if self.operator not in SUPPORTED_CONDITIONAL_OPERATORS:
            raise ValueError(
                f"Unsupported conditional operator: {self.operator}. "
                f"Supported: {sorted(SUPPORTED_CONDITIONAL_OPERATORS)}"
            )
        if self.operator == "in" and not isinstance(self.condition_value, list):
            raise ValueError("condition_value must be a list when operator='in'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable.to_dict(),
            "condition_field_path": self.condition_field_path,
            "operator": self.operator,
            "condition_value": self.condition_value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConditionalVariableSpec":
        return cls(
            variable=RandomVariableSpec.from_dict(data["variable"]),
            condition_field_path=data["condition_field_path"],
            operator=data.get("operator", "eq"),
            condition_value=data.get("condition_value"),
            description=data.get("description"),
        )


@dataclass(eq=True)
class ScenarioTemplateSpec:
    """Name one inspectable assumption bundle that can be assigned to runs."""

    template_id: str
    label: str
    field_overrides: Dict[str, Any] = field(default_factory=dict)
    coverage_tags: List[str] = field(default_factory=list)
    exogenous_events: List[Dict[str, Any]] = field(default_factory=list)
    conditional_overrides: List[ConditionalVariableSpec] = field(default_factory=list)
    correlated_field_paths: List[str] = field(default_factory=list)
    weight: float = 1.0
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.template_id = str(self.template_id or "").strip()
        self.label = str(self.label or "").strip()
        if not self.template_id:
            raise ValueError("template_id is required")
        if not self.label:
            raise ValueError("label is required")
        if not isinstance(self.field_overrides, dict):
            raise ValueError("field_overrides must be a dictionary")
        self.coverage_tags = _normalize_string_list(
            self.coverage_tags,
            field_name="scenario_template.coverage_tags",
            allow_empty=True,
        )
        if not isinstance(self.exogenous_events, list):
            raise ValueError("exogenous_events must be a list")
        normalized_events: List[Dict[str, Any]] = []
        seen_event_ids = set()
        for index, item in enumerate(self.exogenous_events):
            if not isinstance(item, dict):
                raise ValueError("exogenous_events entries must be dictionaries")
            normalized_item = dict(item)
            event_id = str(
                normalized_item.get("event_id")
                or normalized_item.get("label")
                or f"{self.template_id}-event-{index + 1}"
            ).strip()
            if not event_id:
                raise ValueError("exogenous_events entries must include event_id or label")
            normalized_item["event_id"] = event_id
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            normalized_events.append(normalized_item)
        self.exogenous_events = normalized_events
        if not isinstance(self.conditional_overrides, list):
            raise ValueError("conditional_overrides must be a list")
        self.conditional_overrides = [
            item
            if isinstance(item, ConditionalVariableSpec)
            else ConditionalVariableSpec.from_dict(item)
            for item in self.conditional_overrides
        ]
        self.correlated_field_paths = _normalize_string_list(
            self.correlated_field_paths,
            field_name="scenario_template.correlated_field_paths",
            allow_empty=True,
        )
        self.weight = float(self.weight)
        if self.weight <= 0:
            raise ValueError("weight must be positive")
        self.notes = _normalize_string_list(
            self.notes,
            field_name="scenario_template.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "label": self.label,
            "field_overrides": dict(self.field_overrides),
            "coverage_tags": list(self.coverage_tags),
            "exogenous_events": [dict(item) for item in self.exogenous_events],
            "conditional_overrides": [
                item.to_dict() for item in self.conditional_overrides
            ],
            "correlated_field_paths": list(self.correlated_field_paths),
            "weight": self.weight,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioTemplateSpec":
        return cls(
            template_id=data["template_id"],
            label=data.get("label", data["template_id"]),
            field_overrides=data.get("field_overrides", {}),
            coverage_tags=data.get("coverage_tags", []),
            exogenous_events=data.get("exogenous_events", []),
            conditional_overrides=data.get("conditional_overrides", []),
            correlated_field_paths=data.get("correlated_field_paths", []),
            weight=data.get("weight", 1.0),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class StructuralUncertaintyOption:
    """One discrete structural regime that can be assigned to a run."""

    option_id: str
    label: str
    weight: float = 1.0
    config_overrides: Dict[str, Any] = field(default_factory=dict)
    coverage_tags: List[str] = field(default_factory=list)
    runtime_transition_hints: List[Dict[str, Any]] = field(default_factory=list)
    assumption_text: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.option_id = str(self.option_id or "").strip()
        self.label = str(self.label or "").strip()
        if not self.option_id:
            raise ValueError("option_id is required")
        if not self.label:
            raise ValueError("label is required")
        self.weight = float(self.weight)
        if self.weight <= 0:
            raise ValueError("weight must be positive")
        if not isinstance(self.config_overrides, dict):
            raise ValueError("config_overrides must be a dictionary")
        self.coverage_tags = _normalize_string_list(
            self.coverage_tags,
            field_name="structural_uncertainty_option.coverage_tags",
            allow_empty=True,
        )
        if not isinstance(self.runtime_transition_hints, list):
            raise ValueError("runtime_transition_hints must be a list")
        normalized_hints: List[Dict[str, Any]] = []
        for item in self.runtime_transition_hints:
            if not isinstance(item, dict):
                raise ValueError("runtime_transition_hints entries must be dictionaries")
            normalized_hints.append(dict(item))
        self.runtime_transition_hints = normalized_hints
        if self.assumption_text is not None:
            normalized_assumption_text = str(self.assumption_text).strip()
            self.assumption_text = normalized_assumption_text or None
        self.notes = _normalize_string_list(
            self.notes,
            field_name="structural_uncertainty_option.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "weight": self.weight,
            "config_overrides": dict(self.config_overrides),
            "coverage_tags": list(self.coverage_tags),
            "runtime_transition_hints": [
                dict(item) for item in self.runtime_transition_hints
            ],
            "assumption_text": self.assumption_text,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuralUncertaintyOption":
        return cls(
            option_id=data["option_id"],
            label=data.get("label", data["option_id"]),
            weight=data.get("weight", 1.0),
            config_overrides=data.get("config_overrides", {}),
            coverage_tags=data.get("coverage_tags", []),
            runtime_transition_hints=data.get("runtime_transition_hints", []),
            assumption_text=data.get("assumption_text"),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class StructuralUncertaintySpec:
    """Declare one structural uncertainty axis with explicit run-level options."""

    uncertainty_id: str
    kind: str
    label: str
    options: List[StructuralUncertaintyOption] = field(default_factory=list)
    coverage_tags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.uncertainty_id = str(self.uncertainty_id or "").strip()
        self.kind = str(self.kind or "").strip()
        self.label = str(self.label or "").strip()
        if not self.uncertainty_id:
            raise ValueError("uncertainty_id is required")
        if self.kind not in SUPPORTED_STRUCTURAL_UNCERTAINTY_KINDS:
            raise ValueError(
                f"Unsupported structural uncertainty kind: {self.kind}. "
                f"Supported: {sorted(SUPPORTED_STRUCTURAL_UNCERTAINTY_KINDS)}"
            )
        if not self.label:
            raise ValueError("label is required")
        if not isinstance(self.options, list) or not self.options:
            raise ValueError("options must be a non-empty list")
        normalized_options: List[StructuralUncertaintyOption] = []
        seen_option_ids = set()
        for item in self.options:
            option = (
                item
                if isinstance(item, StructuralUncertaintyOption)
                else StructuralUncertaintyOption.from_dict(item)
            )
            if option.option_id in seen_option_ids:
                raise ValueError("options must use unique option_id values")
            normalized_options.append(option)
            seen_option_ids.add(option.option_id)
        self.options = normalized_options
        self.coverage_tags = _normalize_string_list(
            self.coverage_tags,
            field_name="structural_uncertainty.coverage_tags",
            allow_empty=True,
        )
        self.notes = _normalize_string_list(
            self.notes,
            field_name="structural_uncertainty.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uncertainty_id": self.uncertainty_id,
            "kind": self.kind,
            "label": self.label,
            "options": [item.to_dict() for item in self.options],
            "coverage_tags": list(self.coverage_tags),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuralUncertaintySpec":
        return cls(
            uncertainty_id=data["uncertainty_id"],
            kind=data["kind"],
            label=data.get("label", data["uncertainty_id"]),
            options=data.get("options", []),
            coverage_tags=data.get("coverage_tags", []),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class ExperimentDesignSpec:
    """Declare which structured design family should drive ensemble coverage."""

    method: str = "latin-hypercube"
    numeric_dimensions: List[str] = field(default_factory=list)
    scenario_template_ids: List[str] = field(default_factory=list)
    structural_uncertainty_ids: List[str] = field(default_factory=list)
    scenario_assignment: str = "cyclic"
    diversity_axes: List[str] = field(default_factory=list)
    scenario_coverage_axes: List[str] = field(default_factory=list)
    max_templates_per_run: int = 1
    template_combination_policy: str = ""
    max_template_reuse_streak: int = 1
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.method not in SUPPORTED_EXPERIMENT_DESIGN_METHODS:
            raise ValueError(
                f"Unsupported experiment design method: {self.method}. "
                f"Supported: {sorted(SUPPORTED_EXPERIMENT_DESIGN_METHODS)}"
            )
        self.numeric_dimensions = _normalize_string_list(
            self.numeric_dimensions,
            field_name="numeric_dimensions",
            allow_empty=True,
        )
        self.scenario_template_ids = _normalize_string_list(
            self.scenario_template_ids,
            field_name="scenario_template_ids",
            allow_empty=True,
        )
        self.structural_uncertainty_ids = _normalize_string_list(
            self.structural_uncertainty_ids,
            field_name="structural_uncertainty_ids",
            allow_empty=True,
        )
        if self.scenario_assignment not in SUPPORTED_SCENARIO_ASSIGNMENTS:
            raise ValueError(
                f"Unsupported scenario assignment: {self.scenario_assignment}. "
                f"Supported: {sorted(SUPPORTED_SCENARIO_ASSIGNMENTS)}"
            )
        self.diversity_axes = _normalize_string_list(
            self.diversity_axes,
            field_name="diversity_axes",
            allow_empty=True,
        )
        self.scenario_coverage_axes = _normalize_string_list(
            self.scenario_coverage_axes,
            field_name="scenario_coverage_axes",
            allow_empty=True,
        )
        if self.diversity_axes and not self.scenario_coverage_axes:
            self.scenario_coverage_axes = list(self.diversity_axes)
        elif self.scenario_coverage_axes and not self.diversity_axes:
            self.diversity_axes = list(self.scenario_coverage_axes)
        self.max_templates_per_run = int(self.max_templates_per_run)
        if self.max_templates_per_run <= 0:
            raise ValueError("max_templates_per_run must be positive")
        if not self.template_combination_policy:
            self.template_combination_policy = (
                "pairwise" if self.max_templates_per_run > 1 else "single_template"
            )
        if self.template_combination_policy not in SUPPORTED_TEMPLATE_COMBINATION_POLICIES:
            raise ValueError(
                f"Unsupported template_combination_policy: {self.template_combination_policy}. "
                f"Supported: {sorted(SUPPORTED_TEMPLATE_COMBINATION_POLICIES)}"
            )
        self.max_template_reuse_streak = int(self.max_template_reuse_streak)
        if self.max_template_reuse_streak <= 0:
            raise ValueError("max_template_reuse_streak must be positive")
        self.notes = _normalize_string_list(
            self.notes,
            field_name="experiment_design.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "numeric_dimensions": list(self.numeric_dimensions),
            "scenario_template_ids": list(self.scenario_template_ids),
            "structural_uncertainty_ids": list(self.structural_uncertainty_ids),
            "scenario_assignment": self.scenario_assignment,
            "diversity_axes": list(self.diversity_axes),
            "scenario_coverage_axes": list(self.scenario_coverage_axes),
            "max_templates_per_run": self.max_templates_per_run,
            "template_combination_policy": self.template_combination_policy,
            "max_template_reuse_streak": self.max_template_reuse_streak,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentDesignSpec":
        return cls(
            method=data.get("method", "latin-hypercube"),
            numeric_dimensions=data.get("numeric_dimensions", []),
            scenario_template_ids=data.get("scenario_template_ids", []),
            structural_uncertainty_ids=data.get("structural_uncertainty_ids", []),
            scenario_assignment=data.get("scenario_assignment", "cyclic"),
            diversity_axes=data.get(
                "diversity_axes", data.get("scenario_coverage_axes", [])
            ),
            scenario_coverage_axes=data.get("scenario_coverage_axes", []),
            max_templates_per_run=data.get("max_templates_per_run", 1),
            template_combination_policy=data.get(
                "template_combination_policy",
                "pairwise" if data.get("max_templates_per_run", 1) > 1 else "single_template",
            ),
            max_template_reuse_streak=data.get("max_template_reuse_streak", 1),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class UncertaintySpec:
    """Preparation-time uncertainty contract for later runtime resolution."""

    profile: str
    random_variables: List[RandomVariableSpec] = field(default_factory=list)
    variable_groups: List[VariableGroupSpec] = field(default_factory=list)
    conditional_variables: List[ConditionalVariableSpec] = field(default_factory=list)
    scenario_templates: List[ScenarioTemplateSpec] = field(default_factory=list)
    structural_uncertainties: List[StructuralUncertaintySpec] = field(default_factory=list)
    experiment_design: Optional[ExperimentDesignSpec] = None
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
        self.random_variables = [
            item
            if isinstance(item, RandomVariableSpec)
            else RandomVariableSpec.from_dict(item)
            for item in self.random_variables
        ]
        self.variable_groups = [
            item
            if isinstance(item, VariableGroupSpec)
            else VariableGroupSpec.from_dict(item)
            for item in self.variable_groups
        ]
        self.conditional_variables = [
            item
            if isinstance(item, ConditionalVariableSpec)
            else ConditionalVariableSpec.from_dict(item)
            for item in self.conditional_variables
        ]
        self.scenario_templates = [
            item
            if isinstance(item, ScenarioTemplateSpec)
            else ScenarioTemplateSpec.from_dict(item)
            for item in self.scenario_templates
        ]
        self.structural_uncertainties = [
            item
            if isinstance(item, StructuralUncertaintySpec)
            else StructuralUncertaintySpec.from_dict(item)
            for item in self.structural_uncertainties
        ]
        if isinstance(self.experiment_design, dict):
            self.experiment_design = ExperimentDesignSpec.from_dict(
                self.experiment_design
            )
        elif self.experiment_design is not None and not isinstance(
            self.experiment_design, ExperimentDesignSpec
        ):
            raise ValueError(
                "experiment_design must be an ExperimentDesignSpec or dictionary"
            )
        self.notes = _normalize_string_list(
            self.notes,
            field_name="uncertainty_spec.notes",
            allow_empty=True,
        )
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
            "variable_groups": [item.to_dict() for item in self.variable_groups],
            "conditional_variables": [
                item.to_dict() for item in self.conditional_variables
            ],
            "scenario_templates": [
                item.to_dict() for item in self.scenario_templates
            ],
            "structural_uncertainties": [
                item.to_dict() for item in self.structural_uncertainties
            ],
            "experiment_design": (
                self.experiment_design.to_dict()
                if self.experiment_design is not None
                else None
            ),
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
            variable_groups=[
                VariableGroupSpec.from_dict(item)
                for item in data.get("variable_groups", [])
            ],
            conditional_variables=[
                ConditionalVariableSpec.from_dict(item)
                for item in data.get("conditional_variables", [])
            ],
            scenario_templates=[
                ScenarioTemplateSpec.from_dict(item)
                for item in data.get("scenario_templates", [])
            ],
            structural_uncertainties=[
                StructuralUncertaintySpec.from_dict(item)
                for item in data.get("structural_uncertainties", [])
            ],
            experiment_design=(
                ExperimentDesignSpec.from_dict(data["experiment_design"])
                if data.get("experiment_design") is not None
                else None
            ),
        )


@dataclass(eq=True)
class ForecastRunBudget:
    """Budget the control plane intends to spend on one forecast question."""

    ensemble_size: int
    max_concurrency: Optional[int] = None

    def __post_init__(self) -> None:
        self.ensemble_size = int(self.ensemble_size)
        if self.ensemble_size <= 0:
            raise ValueError("run_budget.ensemble_size must be positive")

        if self.max_concurrency is not None:
            self.max_concurrency = int(self.max_concurrency)
            if self.max_concurrency <= 0:
                raise ValueError("run_budget.max_concurrency must be positive")
            if self.max_concurrency > self.ensemble_size:
                raise ValueError(
                    "run_budget.max_concurrency cannot exceed run_budget.ensemble_size"
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ensemble_size": self.ensemble_size,
            "max_concurrency": self.max_concurrency,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastRunBudget":
        if "ensemble_size" not in data:
            raise ValueError("run_budget.ensemble_size is required")
        return cls(
            ensemble_size=data["ensemble_size"],
            max_concurrency=data.get("max_concurrency"),
        )


@dataclass(eq=True)
class ForecastUncertaintyPlan:
    """Persist the selected uncertainty stance for one forecast brief."""

    profile: str
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.profile = normalize_uncertainty_profile(self.profile)
        self.notes = _normalize_string_list(
            self.notes,
            field_name="uncertainty_plan.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastUncertaintyPlan":
        if "profile" not in data:
            raise ValueError("uncertainty_plan.profile is required")
        return cls(
            profile=data["profile"],
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class ForecastBrief:
    """One durable, forecast-centric control-plane artifact prepared ahead of runtime."""

    forecast_question: str
    resolution_criteria: List[str]
    resolution_date: str
    selected_outcome_metrics: List[str]
    run_budget: ForecastRunBudget
    uncertainty_plan: ForecastUncertaintyPlan
    scoring_rule_preferences: List[str] = field(default_factory=list)
    compare_candidates: List[str] = field(default_factory=list)
    scenario_templates: List[str] = field(default_factory=list)
    scenario_template_specs: List[ScenarioTemplateSpec] = field(default_factory=list)
    grounding_summary: Optional[Dict[str, Any]] = None
    artifact_type: str = "forecast_brief"
    schema_version: str = PROBABILISTIC_SCHEMA_VERSION
    generator_version: str = PROBABILISTIC_GENERATOR_VERSION
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.forecast_question = str(self.forecast_question or "").strip()
        if not self.forecast_question:
            raise ValueError("forecast_question is required")

        self.resolution_criteria = _normalize_string_list(
            self.resolution_criteria,
            field_name="resolution_criteria",
            allow_empty=False,
        )
        self.resolution_date = _normalize_iso_resolution_date(self.resolution_date)

        metric_ids = _normalize_string_list(
            self.selected_outcome_metrics,
            field_name="selected_outcome_metrics",
            allow_empty=False,
        )
        self.selected_outcome_metrics = [
            validate_outcome_metric_id(metric_id)
            for metric_id in metric_ids
        ]

        if isinstance(self.run_budget, dict):
            self.run_budget = ForecastRunBudget.from_dict(self.run_budget)
        elif not isinstance(self.run_budget, ForecastRunBudget):
            raise ValueError("run_budget must be a ForecastRunBudget or dictionary")

        if isinstance(self.uncertainty_plan, dict):
            self.uncertainty_plan = ForecastUncertaintyPlan.from_dict(
                self.uncertainty_plan
            )
        elif not isinstance(self.uncertainty_plan, ForecastUncertaintyPlan):
            raise ValueError(
                "uncertainty_plan must be a ForecastUncertaintyPlan or dictionary"
            )

        self.scoring_rule_preferences = _normalize_string_list(
            self.scoring_rule_preferences,
            field_name="scoring_rule_preferences",
            allow_empty=True,
        )
        self.compare_candidates = _normalize_string_list(
            self.compare_candidates,
            field_name="compare_candidates",
            allow_empty=True,
        )
        raw_scenario_templates = self.scenario_templates
        normalized_template_ids: List[str] = []
        normalized_template_specs: List[ScenarioTemplateSpec] = []
        if raw_scenario_templates is None:
            raw_scenario_templates = []
        if not isinstance(raw_scenario_templates, list):
            raise ValueError("scenario_templates must be a list")
        for item in raw_scenario_templates:
            if isinstance(item, str):
                normalized_template_ids.extend(
                    _normalize_string_list(
                        [item],
                        field_name="scenario_templates",
                        allow_empty=True,
                    )
                )
                continue
            if not isinstance(item, dict):
                raise ValueError("scenario_templates entries must be strings or objects")
            normalized_spec = ScenarioTemplateSpec.from_dict(item)
            normalized_template_specs.append(normalized_spec)
            normalized_template_ids.append(normalized_spec.template_id)
        if isinstance(self.scenario_template_specs, list):
            for item in self.scenario_template_specs:
                if isinstance(item, ScenarioTemplateSpec):
                    normalized_template_specs.append(item)
                elif isinstance(item, dict):
                    normalized_template_specs.append(ScenarioTemplateSpec.from_dict(item))
                else:
                    raise ValueError(
                        "scenario_template_specs entries must be ScenarioTemplateSpec or objects"
                    )
        else:
            raise ValueError("scenario_template_specs must be a list")
        deduped_template_ids: List[str] = []
        seen_template_ids = set()
        for template_id in normalized_template_ids:
            if template_id not in seen_template_ids:
                deduped_template_ids.append(template_id)
                seen_template_ids.add(template_id)
        deduped_template_specs: List[ScenarioTemplateSpec] = []
        seen_spec_ids = set()
        for spec in normalized_template_specs:
            if spec.template_id not in seen_spec_ids:
                deduped_template_specs.append(spec)
                seen_spec_ids.add(spec.template_id)
        self.scenario_templates = deduped_template_ids
        self.scenario_template_specs = deduped_template_specs
        self.notes = _normalize_string_list(
            self.notes,
            field_name="forecast_brief.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "forecast_question": self.forecast_question,
            "resolution_criteria": list(self.resolution_criteria),
            "resolution_date": self.resolution_date,
            "selected_outcome_metrics": list(self.selected_outcome_metrics),
            "run_budget": self.run_budget.to_dict(),
            "uncertainty_plan": self.uncertainty_plan.to_dict(),
            "scoring_rule_preferences": list(self.scoring_rule_preferences),
            "compare_candidates": list(self.compare_candidates),
            "scenario_templates": list(self.scenario_templates),
            **(
                {
                    "scenario_template_specs": [
                        item.to_dict() for item in self.scenario_template_specs
                    ]
                }
                if self.scenario_template_specs
                else {}
            ),
            **(
                {"grounding_summary": dict(self.grounding_summary)}
                if isinstance(self.grounding_summary, dict)
                else {}
            ),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastBrief":
        required_fields = (
            "forecast_question",
            "resolution_criteria",
            "resolution_date",
            "selected_outcome_metrics",
            "run_budget",
            "uncertainty_plan",
        )
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"forecast_brief.{field_name} is required")
        return cls(
            artifact_type=data.get("artifact_type", "forecast_brief"),
            schema_version=data.get("schema_version", PROBABILISTIC_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", PROBABILISTIC_GENERATOR_VERSION
            ),
            forecast_question=data["forecast_question"],
            resolution_criteria=data["resolution_criteria"],
            resolution_date=data["resolution_date"],
            selected_outcome_metrics=data["selected_outcome_metrics"],
            run_budget=ForecastRunBudget.from_dict(data["run_budget"]),
            uncertainty_plan=ForecastUncertaintyPlan.from_dict(
                data["uncertainty_plan"]
            ),
            scoring_rule_preferences=data.get("scoring_rule_preferences", []),
            compare_candidates=data.get("compare_candidates", []),
            scenario_templates=data.get("scenario_templates", []),
            scenario_template_specs=data.get("scenario_template_specs", []),
            grounding_summary=data.get("grounding_summary"),
            notes=data.get("notes", []),
        )


def normalize_forecast_brief(
    forecast_brief: Optional[Any],
    *,
    uncertainty_profile: Optional[str],
    outcome_metric_ids: Optional[List[str]],
) -> Optional[ForecastBrief]:
    """Normalize one optional forecast brief against the selected prepare contract."""
    if forecast_brief is None:
        return None

    selected_metric_ids = [
        validate_outcome_metric_id(metric_id)
        for metric_id in (outcome_metric_ids or list(DEFAULT_OUTCOME_METRICS))
    ]
    selected_profile = normalize_uncertainty_profile(uncertainty_profile)

    if isinstance(forecast_brief, ForecastBrief):
        brief = forecast_brief
    else:
        if not isinstance(forecast_brief, dict):
            raise ValueError(
                "forecast_brief must be an object when probabilistic_mode=true"
            )

        payload = dict(forecast_brief)
        brief_metric_ids = payload.get("selected_outcome_metrics")
        if brief_metric_ids in (None, [], ()):
            payload["selected_outcome_metrics"] = list(selected_metric_ids)
        else:
            normalized_brief_metric_ids = [
                validate_outcome_metric_id(metric_id)
                for metric_id in _normalize_string_list(
                    brief_metric_ids,
                    field_name="forecast_brief.selected_outcome_metrics",
                    allow_empty=False,
                )
            ]
            if normalized_brief_metric_ids != selected_metric_ids:
                raise ValueError(
                    "forecast_brief.selected_outcome_metrics must match outcome_metrics when both are provided"
                )
            payload["selected_outcome_metrics"] = normalized_brief_metric_ids

        uncertainty_plan = dict(payload.get("uncertainty_plan") or {})
        brief_profile = uncertainty_plan.get("profile")
        if brief_profile is not None and brief_profile != selected_profile:
            raise ValueError(
                "forecast_brief.uncertainty_plan.profile must match uncertainty_profile when both are provided"
            )
        uncertainty_plan["profile"] = selected_profile
        payload["uncertainty_plan"] = uncertainty_plan

        brief = ForecastBrief.from_dict(payload)

    if brief.selected_outcome_metrics != selected_metric_ids:
        raise ValueError(
            "forecast_brief.selected_outcome_metrics must match outcome_metrics when both are provided"
        )
    if brief.uncertainty_plan.profile != selected_profile:
        raise ValueError(
            "forecast_brief.uncertainty_plan.profile must match uncertainty_profile when both are provided"
        )

    return brief


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
    assumption_ledger: Dict[str, Any] = field(default_factory=dict)
    experiment_design_row: Dict[str, Any] = field(default_factory=dict)
    structural_resolutions: List[Dict[str, Any]] = field(default_factory=list)
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
        if not isinstance(self.assumption_ledger, dict):
            raise ValueError("assumption_ledger must be a dictionary")
        if not isinstance(self.experiment_design_row, dict):
            raise ValueError("experiment_design_row must be a dictionary")
        if not isinstance(self.structural_resolutions, list):
            raise ValueError("structural_resolutions must be a list")
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
            "assumption_ledger": self.assumption_ledger,
            "experiment_design_row": self.experiment_design_row,
            "structural_resolutions": self.structural_resolutions,
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
            assumption_ledger=data.get("assumption_ledger", {}),
            experiment_design_row=data.get("experiment_design_row", {}),
            structural_resolutions=data.get("structural_resolutions", []),
            config_artifact=data.get("config_artifact", "resolved_config.json"),
            artifact_paths=data.get("artifact_paths", {}),
            generated_at=data.get("generated_at"),
            updated_at=data.get("updated_at"),
            status=data.get("status", "prepared"),
            lifecycle=data.get("lifecycle", {}),
            lineage=data.get("lineage", {}),
        )


@dataclass(eq=True)
class ObservedTruthCase:
    """One resolved historical case linking a forecast probability to observed truth."""

    case_id: str
    metric_id: str
    observed_value: Any
    issued_at: Optional[str] = None
    resolved_at: Optional[str] = None
    question_class: Optional[str] = None
    comparable_question_class: Optional[str] = None
    evaluation_split: Optional[str] = None
    evaluation_window_id: Optional[str] = None
    window_id: Optional[str] = None
    evaluation_lane: Optional[str] = None
    benchmark_id: Optional[str] = None
    benchmark_probabilities: Dict[str, Any] = field(default_factory=dict)
    value_kind: Optional[str] = None
    forecast_probability: Optional[float] = None
    forecast_source: Optional[str] = None
    forecast_issued_at: Optional[str] = None
    forecast_scope: Dict[str, Any] = field(default_factory=dict)
    observed_source: Optional[str] = None
    observed_at: Optional[str] = None
    resolution_note: Optional[str] = None
    source_run_id: Optional[str] = None
    source_artifact: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.case_id = str(self.case_id or "").strip()
        if not self.case_id:
            raise ValueError("case_id is required")
        self.metric_id = validate_outcome_metric_id(str(self.metric_id or "").strip())
        if self.forecast_probability is not None:
            self.forecast_probability = float(self.forecast_probability)
            if not 0.0 <= self.forecast_probability <= 1.0:
                raise ValueError("forecast_probability must be between 0.0 and 1.0")
        metric = build_supported_outcome_metric(self.metric_id)
        self.value_kind = str(self.value_kind or metric.value_kind).strip()
        if self.value_kind != metric.value_kind:
            raise ValueError("value_kind must match the registered outcome metric")
        if metric.value_kind == "binary" and not isinstance(self.observed_value, bool):
            raise ValueError(
                "observed_value must be a boolean for binary calibration cases"
            )
        if not isinstance(self.forecast_scope, dict):
            raise ValueError("forecast_scope must be a dictionary")
        self.issued_at = _normalize_iso_datetime(
            self.issued_at if self.issued_at is not None else self.forecast_issued_at,
            field_name="issued_at",
            allow_empty=True,
        )
        if self.forecast_source is not None:
            self.forecast_source = str(self.forecast_source).strip() or None
        self.forecast_issued_at = _normalize_iso_datetime(
            self.forecast_issued_at if self.forecast_issued_at is not None else self.issued_at,
            field_name="forecast_issued_at",
            allow_empty=True,
        )
        self.resolved_at = _normalize_iso_datetime(
            self.resolved_at if self.resolved_at is not None else self.observed_at,
            field_name="resolved_at",
            allow_empty=True,
        )
        self.question_class = _normalize_optional_string(self.question_class)
        self.comparable_question_class = _normalize_optional_string(
            self.comparable_question_class or self.question_class
        )
        self.evaluation_split = _normalize_optional_string(self.evaluation_split)
        self.evaluation_window_id = _normalize_optional_string(
            self.evaluation_window_id
        )
        self.window_id = _normalize_optional_string(self.window_id)
        if self.evaluation_window_id is None:
            self.evaluation_window_id = self.window_id
        if self.window_id is None:
            self.window_id = self.evaluation_window_id
        self.evaluation_lane = _normalize_optional_string(self.evaluation_lane)
        self.benchmark_id = _normalize_optional_string(self.benchmark_id)
        if not isinstance(self.benchmark_probabilities, dict):
            raise ValueError("benchmark_probabilities must be a dictionary")
        if self.observed_source is not None:
            self.observed_source = str(self.observed_source).strip() or None
        self.observed_at = _normalize_iso_datetime(
            self.observed_at if self.observed_at is not None else self.resolved_at,
            field_name="observed_at",
            allow_empty=True,
        )
        if self.resolution_note is not None:
            self.resolution_note = str(self.resolution_note).strip() or None
        if self.source_run_id is not None:
            self.source_run_id = str(self.source_run_id).strip() or None
        if self.source_artifact is not None:
            self.source_artifact = str(self.source_artifact).strip() or None
        self.notes = _normalize_string_list(
            self.notes,
            field_name="observed_truth_case.notes",
            allow_empty=True,
        )
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="observed_truth_case.warnings",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "metric_id": self.metric_id,
            "issued_at": self.issued_at,
            "resolved_at": self.resolved_at,
            "question_class": self.question_class,
            "comparable_question_class": self.comparable_question_class,
            "evaluation_split": self.evaluation_split,
            "evaluation_window_id": self.evaluation_window_id,
            "window_id": self.window_id,
            "evaluation_lane": self.evaluation_lane,
            "benchmark_id": self.benchmark_id,
            "benchmark_probabilities": dict(self.benchmark_probabilities),
            "value_kind": self.value_kind,
            "forecast_probability": self.forecast_probability,
            "observed_value": self.observed_value,
            "forecast_source": self.forecast_source,
            "forecast_issued_at": self.forecast_issued_at,
            "forecast_scope": dict(self.forecast_scope),
            "observed_source": self.observed_source,
            "observed_at": self.observed_at,
            "resolution_note": self.resolution_note,
            "source_run_id": self.source_run_id,
            "source_artifact": self.source_artifact,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservedTruthCase":
        return cls(
            case_id=data["case_id"],
            metric_id=data["metric_id"],
            value_kind=data.get("value_kind"),
            forecast_probability=data.get("forecast_probability"),
            observed_value=data.get("observed_value"),
            issued_at=data.get("issued_at"),
            resolved_at=data.get("resolved_at"),
            question_class=data.get("question_class"),
            comparable_question_class=data.get("comparable_question_class"),
            evaluation_split=data.get("evaluation_split"),
            evaluation_window_id=data.get("evaluation_window_id"),
            window_id=data.get("window_id"),
            evaluation_lane=data.get("evaluation_lane"),
            benchmark_id=data.get("benchmark_id"),
            benchmark_probabilities=data.get("benchmark_probabilities", {}),
            forecast_source=data.get("forecast_source"),
            forecast_issued_at=data.get("forecast_issued_at"),
            forecast_scope=data.get("forecast_scope", {}),
            observed_source=data.get("observed_source"),
            observed_at=data.get("observed_at"),
            resolution_note=data.get("resolution_note"),
            source_run_id=data.get("source_run_id"),
            source_artifact=data.get("source_artifact"),
            notes=data.get("notes", []),
            warnings=data.get("warnings", []),
        )


@dataclass(eq=True)
class ObservedTruthRegistry:
    """One persisted registry of historical cases for one ensemble."""

    simulation_id: str
    ensemble_id: str
    cases: List[ObservedTruthCase] = field(default_factory=list)
    registry_scope: Dict[str, Any] = field(default_factory=dict)
    evaluation_scope: Dict[str, Any] = field(default_factory=dict)
    benchmark_scope: Dict[str, Any] = field(default_factory=dict)
    quality_summary: Dict[str, Any] = field(default_factory=dict)
    artifact_type: str = "observed_truth_registry"
    schema_version: str = OBSERVED_TRUTH_SCHEMA_VERSION
    generator_version: str = OBSERVED_TRUTH_GENERATOR_VERSION
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not self.ensemble_id:
            raise ValueError("ensemble_id is required")
        if not isinstance(self.registry_scope, dict):
            raise ValueError("registry_scope must be a dictionary")
        self.cases = [
            item if isinstance(item, ObservedTruthCase) else ObservedTruthCase.from_dict(item)
            for item in self.cases
        ]
        if not isinstance(self.quality_summary, dict):
            raise ValueError("quality_summary must be a dictionary")
        if not isinstance(self.evaluation_scope, dict):
            raise ValueError("evaluation_scope must be a dictionary")
        if not isinstance(self.benchmark_scope, dict):
            raise ValueError("benchmark_scope must be a dictionary")
        if not self.registry_scope:
            self.registry_scope = {
                "level": "ensemble",
                "simulation_id": self.simulation_id,
                "ensemble_id": self.ensemble_id,
            }
        if not self.quality_summary:
            self.quality_summary = {
                "status": "complete",
                "total_case_count": len(self.cases),
                "metric_ids": sorted({item.metric_id for item in self.cases}),
                "warnings": [],
            }
        self.notes = _normalize_string_list(
            self.notes,
            field_name="observed_truth_registry.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "registry_scope": dict(self.registry_scope),
            "evaluation_scope": dict(self.evaluation_scope),
            "benchmark_scope": dict(self.benchmark_scope),
            "cases": [item.to_dict() for item in self.cases],
            "quality_summary": dict(self.quality_summary),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservedTruthRegistry":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data["ensemble_id"],
            cases=[ObservedTruthCase.from_dict(item) for item in data.get("cases", [])],
            registry_scope=data.get("registry_scope", {}),
            evaluation_scope=data.get("evaluation_scope", {}),
            benchmark_scope=data.get("benchmark_scope", {}),
            quality_summary=data.get("quality_summary", {}),
            artifact_type=data.get("artifact_type", "observed_truth_registry"),
            schema_version=data.get("schema_version", OBSERVED_TRUTH_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", OBSERVED_TRUTH_GENERATOR_VERSION
            ),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class BenchmarkComparisonSummary:
    """One explicit comparison between scored system cases and a simple baseline."""

    benchmark_id: str
    metric_id: str
    case_count: int
    system_scores: Dict[str, float] = field(default_factory=dict)
    baseline_scores: Dict[str, float] = field(default_factory=dict)
    score_deltas: Dict[str, float] = field(default_factory=dict)
    skill_scores: Dict[str, float] = field(default_factory=dict)
    baseline_probability: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.benchmark_id = _normalize_optional_string(self.benchmark_id) or ""
        if not self.benchmark_id:
            raise ValueError("benchmark_id is required")
        self.metric_id = validate_outcome_metric_id(str(self.metric_id or "").strip())
        self.case_count = int(self.case_count)
        if self.case_count < 0:
            raise ValueError("case_count must be non-negative")
        if not isinstance(self.system_scores, dict):
            raise ValueError("system_scores must be a dictionary")
        if not isinstance(self.baseline_scores, dict):
            raise ValueError("baseline_scores must be a dictionary")
        if not isinstance(self.score_deltas, dict):
            raise ValueError("score_deltas must be a dictionary")
        if not isinstance(self.skill_scores, dict):
            raise ValueError("skill_scores must be a dictionary")
        for payload in (
            self.system_scores,
            self.baseline_scores,
            self.score_deltas,
            self.skill_scores,
        ):
            for key, value in list(payload.items()):
                payload[key] = float(value)
        if self.baseline_probability is not None:
            self.baseline_probability = float(self.baseline_probability)
        self.notes = _normalize_string_list(
            self.notes,
            field_name="benchmark_comparison.notes",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "metric_id": self.metric_id,
            "case_count": self.case_count,
            "system_scores": dict(self.system_scores),
            "baseline_scores": dict(self.baseline_scores),
            "score_deltas": dict(self.score_deltas),
            "skill_scores": dict(self.skill_scores),
            "baseline_probability": self.baseline_probability,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkComparisonSummary":
        return cls(
            benchmark_id=data["benchmark_id"],
            metric_id=data["metric_id"],
            case_count=data.get("case_count", 0),
            system_scores=data.get("system_scores", {}),
            baseline_scores=data.get("baseline_scores", {}),
            score_deltas=data.get("score_deltas", {}),
            skill_scores=data.get("skill_scores", {}),
            baseline_probability=data.get("baseline_probability"),
            notes=data.get("notes", []),
        )


@dataclass(eq=True)
class EvaluationWindowSummary:
    """One cohort summary for an explicit split/window of historical cases."""

    window_id: str
    case_count: int
    scored_case_count: int = 0
    evaluation_split: Optional[str] = None
    question_class: Optional[str] = None
    comparable_question_class: Optional[str] = None
    metric_ids: List[str] = field(default_factory=list)
    question_classes: List[str] = field(default_factory=list)
    comparable_question_classes: List[str] = field(default_factory=list)
    split_counts: Dict[str, int] = field(default_factory=dict)
    issue_window: Dict[str, Optional[str]] = field(default_factory=dict)
    resolution_window: Dict[str, Optional[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.window_id = _normalize_optional_string(self.window_id) or ""
        if not self.window_id:
            raise ValueError("window_id is required")
        self.case_count = int(self.case_count)
        self.scored_case_count = int(self.scored_case_count)
        if self.case_count < 0 or self.scored_case_count < 0:
            raise ValueError("window counts must be non-negative")
        self.evaluation_split = _normalize_optional_string(self.evaluation_split)
        self.question_class = _normalize_optional_string(self.question_class)
        self.comparable_question_class = _normalize_optional_string(
            self.comparable_question_class or self.question_class
        )
        self.metric_ids = _normalize_string_list(
            self.metric_ids,
            field_name="evaluation_window.metric_ids",
            allow_empty=True,
        )
        self.question_classes = _normalize_string_list(
            self.question_classes,
            field_name="evaluation_window.question_classes",
            allow_empty=True,
        )
        self.comparable_question_classes = _normalize_string_list(
            self.comparable_question_classes,
            field_name="evaluation_window.comparable_question_classes",
            allow_empty=True,
        )
        if not isinstance(self.split_counts, dict):
            raise ValueError("split_counts must be a dictionary")
        self.split_counts = {
            str(key): _coerce_non_negative_int(value)
            for key, value in self.split_counts.items()
        }
        if not isinstance(self.issue_window, dict):
            raise ValueError("issue_window must be a dictionary")
        if not isinstance(self.resolution_window, dict):
            raise ValueError("resolution_window must be a dictionary")
        self.issue_window = {
            "start": _normalize_optional_string(self.issue_window.get("start")),
            "end": _normalize_optional_string(self.issue_window.get("end")),
        }
        self.resolution_window = {
            "start": _normalize_optional_string(self.resolution_window.get("start")),
            "end": _normalize_optional_string(self.resolution_window.get("end")),
        }
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="evaluation_window.warnings",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "case_count": self.case_count,
            "scored_case_count": self.scored_case_count,
            "evaluation_split": self.evaluation_split,
            "question_class": self.question_class,
            "comparable_question_class": self.comparable_question_class,
            "metric_ids": list(self.metric_ids),
            "question_classes": list(self.question_classes),
            "comparable_question_classes": list(self.comparable_question_classes),
            "split_counts": dict(self.split_counts),
            "issue_window": dict(self.issue_window),
            "resolution_window": dict(self.resolution_window),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationWindowSummary":
        return cls(
            window_id=data["window_id"],
            case_count=data.get("case_count", 0),
            scored_case_count=data.get("scored_case_count", 0),
            evaluation_split=data.get("evaluation_split"),
            question_class=data.get("question_class"),
            comparable_question_class=data.get("comparable_question_class"),
            metric_ids=data.get("metric_ids", []),
            question_classes=data.get("question_classes", []),
            comparable_question_classes=data.get("comparable_question_classes", []),
            split_counts=data.get("split_counts", {}),
            issue_window=data.get("issue_window", {}),
            resolution_window=data.get("resolution_window", {}),
            warnings=data.get("warnings", []),
        )


@dataclass(eq=True)
class BacktestCaseResult:
    """One case-level proper-scoring result."""

    case_id: str
    metric_id: str
    forecast_probability: float
    observed_value: bool
    scores: Dict[str, float] = field(default_factory=dict)
    score_inputs: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.case_id = str(self.case_id or "").strip()
        if not self.case_id:
            raise ValueError("case_id is required")
        self.metric_id = validate_outcome_metric_id(str(self.metric_id or "").strip())
        self.forecast_probability = float(self.forecast_probability)
        if not 0.0 <= self.forecast_probability <= 1.0:
            raise ValueError("forecast_probability must be between 0.0 and 1.0")
        if not isinstance(self.observed_value, bool):
            raise ValueError("observed_value must be a boolean")
        if not isinstance(self.scores, dict):
            raise ValueError("scores must be a dictionary")
        if not isinstance(self.score_inputs, dict):
            raise ValueError("score_inputs must be a dictionary")
        for key, value in self.scores.items():
            if key not in SUPPORTED_SCORING_RULES:
                raise ValueError(
                    f"Unsupported scoring rule for backtest case: {key}. "
                    f"Supported: {sorted(SUPPORTED_SCORING_RULES)}"
                )
            self.scores[key] = float(value)
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="backtest_case_result.warnings",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "metric_id": self.metric_id,
            "forecast_probability": self.forecast_probability,
            "observed_value": self.observed_value,
            "scores": dict(self.scores),
            "score_inputs": dict(self.score_inputs),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestCaseResult":
        return cls(
            case_id=data["case_id"],
            metric_id=data["metric_id"],
            forecast_probability=data["forecast_probability"],
            observed_value=data["observed_value"],
            scores=data.get("scores", {}),
            score_inputs=data.get("score_inputs", {}),
            warnings=data.get("warnings", []),
        )


@dataclass(eq=True)
class MetricBacktestSummary:
    """One metric-level backtest summary."""

    metric_id: str
    value_kind: str
    case_count: int
    positive_case_count: int = 0
    negative_case_count: int = 0
    observed_event_rate: Optional[float] = None
    mean_forecast_probability: Optional[float] = None
    scoring_rules: List[str] = field(default_factory=list)
    case_results: List[BacktestCaseResult] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    mean_scores: Dict[str, float] = field(default_factory=dict)
    question_classes: List[str] = field(default_factory=list)
    comparable_question_classes: List[str] = field(default_factory=list)
    evaluation_splits: List[str] = field(default_factory=list)
    evaluation_window_ids: List[str] = field(default_factory=list)
    benchmark_summaries: Dict[str, Any] = field(default_factory=dict)
    evaluation_slices: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.metric_id = validate_outcome_metric_id(str(self.metric_id or "").strip())
        self.value_kind = str(self.value_kind or "").strip()
        if not self.value_kind:
            raise ValueError("value_kind is required")
        self.case_count = int(self.case_count)
        self.positive_case_count = int(self.positive_case_count)
        self.negative_case_count = int(self.negative_case_count)
        if self.case_count < 0:
            raise ValueError("case_count must be non-negative")
        if self.positive_case_count < 0 or self.negative_case_count < 0:
            raise ValueError("class counts must be non-negative")
        self.scoring_rules = _normalize_scoring_rules(
            self.scoring_rules,
            field_name="metric_backtest_summary.scoring_rules",
            allow_empty=True,
        )
        self.case_results = [
            item if isinstance(item, BacktestCaseResult) else BacktestCaseResult.from_dict(item)
            for item in self.case_results
        ]
        if not isinstance(self.scores, dict):
            raise ValueError("scores must be a dictionary")
        if not isinstance(self.mean_scores, dict):
            raise ValueError("mean_scores must be a dictionary")
        if self.scores and self.mean_scores and self.scores != self.mean_scores:
            merged_scores = dict(self.mean_scores)
            merged_scores.update(self.scores)
            self.scores = merged_scores
        elif self.scores and not self.mean_scores:
            self.mean_scores = dict(self.scores)
        elif self.mean_scores and not self.scores:
            self.scores = dict(self.mean_scores)
        for key, value in self.scores.items():
            if key not in SUPPORTED_SUMMARY_SCORE_KEYS:
                raise ValueError(
                    f"Unsupported score for metric_backtest_summary.scores: {key}. "
                    f"Supported: {sorted(SUPPORTED_SUMMARY_SCORE_KEYS)}"
                )
            self.scores[key] = float(value)
        self.mean_scores = dict(self.scores)
        if self.observed_event_rate is not None:
            self.observed_event_rate = float(self.observed_event_rate)
        if self.mean_forecast_probability is not None:
            self.mean_forecast_probability = float(self.mean_forecast_probability)
        self.question_classes = _normalize_string_list(
            self.question_classes,
            field_name="metric_backtest_summary.question_classes",
            allow_empty=True,
        )
        self.comparable_question_classes = _normalize_string_list(
            self.comparable_question_classes,
            field_name="metric_backtest_summary.comparable_question_classes",
            allow_empty=True,
        )
        self.evaluation_splits = _normalize_string_list(
            self.evaluation_splits,
            field_name="metric_backtest_summary.evaluation_splits",
            allow_empty=True,
        )
        self.evaluation_window_ids = _normalize_string_list(
            self.evaluation_window_ids,
            field_name="metric_backtest_summary.evaluation_window_ids",
            allow_empty=True,
        )
        if not isinstance(self.benchmark_summaries, dict):
            raise ValueError("benchmark_summaries must be a dictionary")
        if not isinstance(self.evaluation_slices, list):
            raise ValueError("evaluation_slices must be a list")
        self.benchmark_summaries = {
            str(key): (dict(value) if isinstance(value, dict) else value)
            for key, value in self.benchmark_summaries.items()
        }
        normalized_slices: List[Dict[str, Any]] = []
        for item in self.evaluation_slices:
            if not isinstance(item, dict):
                raise ValueError("evaluation_slices entries must be dictionaries")
            normalized_slices.append(dict(item))
        self.evaluation_slices = normalized_slices
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="metric_backtest_summary.warnings",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "value_kind": self.value_kind,
            "case_count": self.case_count,
            "positive_case_count": self.positive_case_count,
            "negative_case_count": self.negative_case_count,
            "observed_event_rate": self.observed_event_rate,
            "mean_forecast_probability": self.mean_forecast_probability,
            "scoring_rules": list(self.scoring_rules),
            "case_results": [item.to_dict() for item in self.case_results],
            "scores": dict(self.scores),
            "mean_scores": dict(self.mean_scores),
            "question_classes": list(self.question_classes),
            "comparable_question_classes": list(self.comparable_question_classes),
            "evaluation_splits": list(self.evaluation_splits),
            "evaluation_window_ids": list(self.evaluation_window_ids),
            "benchmark_summaries": {
                benchmark_id: dict(summary)
                if isinstance(summary, dict)
                else summary
                for benchmark_id, summary in self.benchmark_summaries.items()
            },
            "evaluation_slices": [dict(item) for item in self.evaluation_slices],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricBacktestSummary":
        return cls(
            metric_id=data["metric_id"],
            value_kind=data["value_kind"],
            case_count=data.get("case_count", 0),
            positive_case_count=data.get("positive_case_count", 0),
            negative_case_count=data.get("negative_case_count", 0),
            observed_event_rate=data.get("observed_event_rate"),
            mean_forecast_probability=data.get("mean_forecast_probability"),
            scoring_rules=data.get("scoring_rules", []),
            case_results=[
                BacktestCaseResult.from_dict(item)
                for item in data.get("case_results", [])
            ],
            scores=data.get("scores", data.get("mean_scores", {})),
            mean_scores=data.get("mean_scores", data.get("scores", {})),
            question_classes=data.get("question_classes", []),
            comparable_question_classes=data.get(
                "comparable_question_classes", []
            ),
            evaluation_splits=data.get("evaluation_splits", []),
            evaluation_window_ids=data.get("evaluation_window_ids", []),
            benchmark_summaries=data.get("benchmark_summaries", {}),
            evaluation_slices=data.get("evaluation_slices", []),
            warnings=data.get("warnings", []),
        )


@dataclass(eq=True)
class BacktestSummary:
    """One persisted backtest summary artifact."""

    simulation_id: str
    ensemble_id: str
    metric_backtests: Dict[str, MetricBacktestSummary] = field(default_factory=dict)
    evaluation_windows: Dict[str, EvaluationWindowSummary] = field(default_factory=dict)
    benchmark_comparisons: Dict[str, BenchmarkComparisonSummary] = field(default_factory=dict)
    evaluation_summary: Dict[str, Any] = field(default_factory=dict)
    quality_summary: Dict[str, Any] = field(default_factory=dict)
    artifact_type: str = "backtest_summary"
    schema_version: str = BACKTEST_SCHEMA_VERSION
    generator_version: str = BACKTEST_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not self.ensemble_id:
            raise ValueError("ensemble_id is required")
        if not isinstance(self.metric_backtests, dict):
            raise ValueError("metric_backtests must be a dictionary")
        self.metric_backtests = {
            metric_id: (
                summary
                if isinstance(summary, MetricBacktestSummary)
                else MetricBacktestSummary.from_dict(summary)
            )
            for metric_id, summary in self.metric_backtests.items()
        }
        self.evaluation_windows = {
            window_id: (
                summary
                if isinstance(summary, EvaluationWindowSummary)
                else EvaluationWindowSummary.from_dict(summary)
            )
            for window_id, summary in self.evaluation_windows.items()
        }
        self.benchmark_comparisons = {
            comparison_id: (
                summary
                if isinstance(summary, BenchmarkComparisonSummary)
                else BenchmarkComparisonSummary.from_dict(summary)
            )
            for comparison_id, summary in self.benchmark_comparisons.items()
        }
        if not isinstance(self.evaluation_summary, dict):
            raise ValueError("evaluation_summary must be a dictionary")
        if not isinstance(self.quality_summary, dict):
            raise ValueError("quality_summary must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "metric_backtests": {
                metric_id: summary.to_dict()
                for metric_id, summary in self.metric_backtests.items()
            },
            "evaluation_windows": {
                window_id: summary.to_dict()
                for window_id, summary in self.evaluation_windows.items()
            },
            "benchmark_comparisons": {
                comparison_id: summary.to_dict()
                for comparison_id, summary in self.benchmark_comparisons.items()
            },
            "evaluation_summary": dict(self.evaluation_summary),
            "quality_summary": dict(self.quality_summary),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestSummary":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data["ensemble_id"],
            metric_backtests={
                metric_id: MetricBacktestSummary.from_dict(summary)
                for metric_id, summary in data.get("metric_backtests", {}).items()
            },
            evaluation_windows={
                window_id: EvaluationWindowSummary.from_dict(summary)
                for window_id, summary in data.get("evaluation_windows", {}).items()
            },
            benchmark_comparisons={
                comparison_id: BenchmarkComparisonSummary.from_dict(summary)
                for comparison_id, summary in data.get("benchmark_comparisons", {}).items()
            },
            evaluation_summary=data.get("evaluation_summary", {}),
            quality_summary=data.get("quality_summary", {}),
            artifact_type=data.get("artifact_type", "backtest_summary"),
            schema_version=data.get("schema_version", BACKTEST_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", BACKTEST_GENERATOR_VERSION
            ),
        )


@dataclass(eq=True)
class ReliabilityBin:
    """One fixed-width reliability bucket for binary forecasts."""

    bin_index: int
    lower_bound: float
    upper_bound: float
    case_count: int
    mean_forecast_probability: Optional[float] = None
    observed_frequency: Optional[float] = None
    observed_minus_forecast: Optional[float] = None

    def __post_init__(self) -> None:
        self.bin_index = int(self.bin_index)
        self.lower_bound = float(self.lower_bound)
        self.upper_bound = float(self.upper_bound)
        self.case_count = int(self.case_count)
        if self.case_count < 0:
            raise ValueError("case_count must be non-negative")
        if not 0.0 <= self.lower_bound <= 1.0:
            raise ValueError("lower_bound must be between 0.0 and 1.0")
        if not 0.0 <= self.upper_bound <= 1.0:
            raise ValueError("upper_bound must be between 0.0 and 1.0")
        if self.upper_bound <= self.lower_bound:
            raise ValueError("upper_bound must be greater than lower_bound")
        for field_name in (
            "mean_forecast_probability",
            "observed_frequency",
            "observed_minus_forecast",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, float(value))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bin_index": self.bin_index,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "case_count": self.case_count,
            "mean_forecast_probability": self.mean_forecast_probability,
            "observed_frequency": self.observed_frequency,
            "observed_minus_forecast": self.observed_minus_forecast,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReliabilityBin":
        return cls(
            bin_index=data["bin_index"],
            lower_bound=data["lower_bound"],
            upper_bound=data["upper_bound"],
            case_count=data.get("case_count", 0),
            mean_forecast_probability=data.get("mean_forecast_probability"),
            observed_frequency=data.get("observed_frequency"),
            observed_minus_forecast=data.get("observed_minus_forecast"),
        )


@dataclass(eq=True)
class CalibrationReadiness:
    """Conservative readiness metadata for surfacing calibrated summaries."""

    ready: bool
    minimum_case_count: int
    actual_case_count: int
    minimum_positive_case_count: int = 0
    actual_positive_case_count: int = 0
    minimum_negative_case_count: int = 0
    actual_negative_case_count: int = 0
    non_empty_bin_count: int = 0
    supported_bin_count: int = 0
    minimum_supported_bin_count: int = 0
    gating_reasons: List[str] = field(default_factory=list)
    confidence_label: str = "insufficient"

    def __post_init__(self) -> None:
        self.ready = bool(self.ready)
        self.minimum_case_count = int(self.minimum_case_count)
        self.actual_case_count = int(self.actual_case_count)
        self.minimum_positive_case_count = int(self.minimum_positive_case_count)
        self.actual_positive_case_count = int(self.actual_positive_case_count)
        self.minimum_negative_case_count = int(self.minimum_negative_case_count)
        self.actual_negative_case_count = int(self.actual_negative_case_count)
        self.non_empty_bin_count = int(self.non_empty_bin_count)
        self.supported_bin_count = int(self.supported_bin_count)
        self.minimum_supported_bin_count = int(self.minimum_supported_bin_count)
        if self.minimum_case_count < 0 or self.actual_case_count < 0:
            raise ValueError("case counts must be non-negative")
        if (
            self.minimum_positive_case_count < 0
            or self.actual_positive_case_count < 0
            or self.minimum_negative_case_count < 0
            or self.actual_negative_case_count < 0
        ):
            raise ValueError("class-count readiness fields must be non-negative")
        if self.non_empty_bin_count < 0:
            raise ValueError("non_empty_bin_count must be non-negative")
        if self.supported_bin_count < 0 or self.minimum_supported_bin_count < 0:
            raise ValueError("supported-bin readiness fields must be non-negative")
        self.gating_reasons = _normalize_string_list(
            self.gating_reasons,
            field_name="calibration_readiness.gating_reasons",
            allow_empty=True,
        )
        self.confidence_label = str(self.confidence_label or "").strip() or "insufficient"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "minimum_case_count": self.minimum_case_count,
            "actual_case_count": self.actual_case_count,
            "minimum_positive_case_count": self.minimum_positive_case_count,
            "actual_positive_case_count": self.actual_positive_case_count,
            "minimum_negative_case_count": self.minimum_negative_case_count,
            "actual_negative_case_count": self.actual_negative_case_count,
            "non_empty_bin_count": self.non_empty_bin_count,
            "supported_bin_count": self.supported_bin_count,
            "minimum_supported_bin_count": self.minimum_supported_bin_count,
            "gating_reasons": list(self.gating_reasons),
            "confidence_label": self.confidence_label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationReadiness":
        return cls(
            ready=data.get("ready", False),
            minimum_case_count=data.get("minimum_case_count", 0),
            actual_case_count=data.get("actual_case_count", 0),
            minimum_positive_case_count=data.get("minimum_positive_case_count", 0),
            actual_positive_case_count=data.get("actual_positive_case_count", 0),
            minimum_negative_case_count=data.get("minimum_negative_case_count", 0),
            actual_negative_case_count=data.get("actual_negative_case_count", 0),
            non_empty_bin_count=data.get("non_empty_bin_count", 0),
            supported_bin_count=data.get("supported_bin_count", 0),
            minimum_supported_bin_count=data.get("minimum_supported_bin_count", 0),
            gating_reasons=data.get("gating_reasons", []),
            confidence_label=data.get("confidence_label", "insufficient"),
        )


@dataclass(eq=True)
class MetricCalibrationSummary:
    """One metric-level calibration artifact for supported binary outcomes."""

    metric_id: str
    value_kind: str
    case_count: int
    supported_scoring_rules: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    reliability_bins: List[ReliabilityBin] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    readiness: CalibrationReadiness = field(default_factory=lambda: CalibrationReadiness(
        ready=False,
        minimum_case_count=0,
        actual_case_count=0,
        minimum_positive_case_count=0,
        actual_positive_case_count=0,
        minimum_negative_case_count=0,
        actual_negative_case_count=0,
        non_empty_bin_count=0,
        supported_bin_count=0,
        minimum_supported_bin_count=0,
    ))
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.metric_id = validate_outcome_metric_id(str(self.metric_id or "").strip())
        self.value_kind = str(self.value_kind or "").strip()
        if not self.value_kind:
            raise ValueError("value_kind is required")
        self.case_count = int(self.case_count)
        if self.case_count < 0:
            raise ValueError("case_count must be non-negative")
        self.supported_scoring_rules = _normalize_scoring_rules(
            self.supported_scoring_rules,
            field_name="metric_calibration_summary.supported_scoring_rules",
            allow_empty=True,
        )
        if not isinstance(self.scores, dict):
            raise ValueError("scores must be a dictionary")
        for key, value in self.scores.items():
            if key not in SUPPORTED_SUMMARY_SCORE_KEYS:
                raise ValueError(
                    f"Unsupported scoring rule for metric_calibration_summary.scores: {key}. "
                    f"Supported: {sorted(SUPPORTED_SUMMARY_SCORE_KEYS)}"
                )
            self.scores[key] = float(value)
        self.reliability_bins = [
            item if isinstance(item, ReliabilityBin) else ReliabilityBin.from_dict(item)
            for item in self.reliability_bins
        ]
        if not isinstance(self.diagnostics, dict):
            raise ValueError("diagnostics must be a dictionary")
        for key, value in list(self.diagnostics.items()):
            if value is not None:
                self.diagnostics[key] = float(value)
        if isinstance(self.readiness, dict):
            self.readiness = CalibrationReadiness.from_dict(self.readiness)
        elif not isinstance(self.readiness, CalibrationReadiness):
            raise ValueError("readiness must be a CalibrationReadiness or dictionary")
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="metric_calibration_summary.warnings",
            allow_empty=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "value_kind": self.value_kind,
            "case_count": self.case_count,
            "supported_scoring_rules": list(self.supported_scoring_rules),
            "scores": dict(self.scores),
            "reliability_bins": [item.to_dict() for item in self.reliability_bins],
            "diagnostics": dict(self.diagnostics),
            "readiness": self.readiness.to_dict(),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricCalibrationSummary":
        return cls(
            metric_id=data["metric_id"],
            value_kind=data["value_kind"],
            case_count=data.get("case_count", 0),
            supported_scoring_rules=data.get("supported_scoring_rules", []),
            scores=data.get("scores", {}),
            reliability_bins=[
                ReliabilityBin.from_dict(item)
                for item in data.get("reliability_bins", [])
            ],
            diagnostics=data.get("diagnostics", {}),
            readiness=CalibrationReadiness.from_dict(data.get("readiness", {})),
            warnings=data.get("warnings", []),
        )


@dataclass(eq=True)
class CalibrationSummary:
    """One persisted calibration summary artifact."""

    simulation_id: str
    ensemble_id: str
    metric_calibrations: Dict[str, MetricCalibrationSummary] = field(default_factory=dict)
    evaluation_provenance: Dict[str, Any] = field(default_factory=dict)
    quality_summary: Dict[str, Any] = field(default_factory=dict)
    artifact_type: str = "calibration_summary"
    schema_version: str = CALIBRATION_SCHEMA_VERSION
    generator_version: str = CALIBRATION_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not self.ensemble_id:
            raise ValueError("ensemble_id is required")
        if not isinstance(self.metric_calibrations, dict):
            raise ValueError("metric_calibrations must be a dictionary")
        self.metric_calibrations = {
            metric_id: (
                summary
                if isinstance(summary, MetricCalibrationSummary)
                else MetricCalibrationSummary.from_dict(summary)
            )
            for metric_id, summary in self.metric_calibrations.items()
        }
        if not isinstance(self.evaluation_provenance, dict):
            raise ValueError("evaluation_provenance must be a dictionary")
        if not isinstance(self.quality_summary, dict):
            raise ValueError("quality_summary must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "metric_calibrations": {
                metric_id: summary.to_dict()
                for metric_id, summary in self.metric_calibrations.items()
            },
            "evaluation_provenance": dict(self.evaluation_provenance),
            "quality_summary": dict(self.quality_summary),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationSummary":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data["ensemble_id"],
            metric_calibrations={
                metric_id: MetricCalibrationSummary.from_dict(summary)
                for metric_id, summary in data.get("metric_calibrations", {}).items()
            },
            evaluation_provenance=data.get("evaluation_provenance", {}),
            quality_summary=data.get("quality_summary", {}),
            artifact_type=data.get("artifact_type", "calibration_summary"),
            schema_version=data.get("schema_version", CALIBRATION_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", CALIBRATION_GENERATOR_VERSION
            ),
        )
