"""
Versioned simulation-market artifacts for run-scoped inference extraction.

These artifacts are explicitly bounded:
- they summarize synthetic discourse from one simulation-backed run,
- they remain heuristic and observational,
- they do not claim calibration or causal semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


SIMULATION_MARKET_SCHEMA_VERSION = "forecast.simulation_market.v1"
SIMULATION_MARKET_GENERATOR_VERSION = "forecast.simulation_market.generator.v1"

SUPPORTED_SIMULATION_MARKET_QUESTION_TYPES = {
    "binary",
    "categorical",
}
SUPPORTED_SIMULATION_MARKET_EXTRACTION_STATUSES = {
    "ready",
    "partial",
    "no_signals",
    "missing_action_logs",
    "unlinked_forecast_workspace",
    "unsupported_question_type",
}
SUPPORTED_SIMULATION_MARKET_PROVENANCE_STATUSES = {
    "ready",
    "partial",
    "invalid",
}

SIMULATION_MARKET_ARTIFACT_FILENAMES = {
    "simulation_market_manifest": "simulation_market_manifest.json",
    "agent_belief_book": "agent_belief_book.json",
    "belief_update_trace": "belief_update_trace.json",
    "disagreement_summary": "disagreement_summary.json",
    "market_snapshot": "market_snapshot.json",
    "argument_map": "argument_map.json",
    "missing_information_signals": "missing_information_signals.json",
}

SIMULATION_MARKET_SUMMARY_ARTIFACT_TYPE = "simulation_market_summary"


def _require_non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _normalize_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def _normalize_optional_score(name: str, value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if score < 0 or score > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return round(score, 4)


def _normalize_string_list(name: str, values: Any) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")
    normalized: List[str] = []
    for item in values:
        text = _normalize_optional_string(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_dict(name: str, value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a dictionary")
    return dict(value)


def _require_iso_datetime(name: str, value: Any) -> str:
    text = _require_non_empty_string(name, value)
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime") from exc
    return text


def _validate_supported_value(name: str, value: str, supported_values: set[str]) -> str:
    if value not in supported_values:
        raise ValueError(
            f"Unsupported {name}: {value}. Expected one of: {', '.join(sorted(supported_values))}"
        )
    return value


@dataclass
class SimulationMarketReference:
    simulation_id: str
    ensemble_id: Optional[str]
    run_id: Optional[str]
    platform: str
    round_num: int
    line_number: int
    agent_id: int
    agent_name: str
    timestamp: str
    action_type: str
    source_artifact: str

    def __post_init__(self) -> None:
        self.simulation_id = _require_non_empty_string("simulation_id", self.simulation_id)
        self.ensemble_id = _normalize_optional_string(self.ensemble_id)
        self.run_id = _normalize_optional_string(self.run_id)
        self.platform = _require_non_empty_string("platform", self.platform)
        self.round_num = int(self.round_num or 0)
        self.line_number = int(self.line_number or 0)
        self.agent_id = int(self.agent_id or 0)
        self.agent_name = _require_non_empty_string("agent_name", self.agent_name)
        self.timestamp = _require_iso_datetime("timestamp", self.timestamp)
        self.action_type = _require_non_empty_string("action_type", self.action_type)
        self.source_artifact = _require_non_empty_string("source_artifact", self.source_artifact)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "platform": self.platform,
            "round_num": self.round_num,
            "line_number": self.line_number,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "source_artifact": self.source_artifact,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketReference":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data.get("ensemble_id"),
            run_id=data.get("run_id"),
            platform=data["platform"],
            round_num=data.get("round_num", 0),
            line_number=data.get("line_number", 0),
            agent_id=data.get("agent_id", 0),
            agent_name=data["agent_name"],
            timestamp=data["timestamp"],
            action_type=data["action_type"],
            source_artifact=data["source_artifact"],
        )


@dataclass
class SimulationMarketAgentBelief:
    forecast_id: Optional[str]
    question_type: str
    agent_id: int
    agent_name: str
    judgment_type: str
    probability: Optional[float] = None
    confidence: Optional[float] = None
    uncertainty_expression: Optional[str] = None
    dominant_outcome: Optional[str] = None
    outcome_distribution: Dict[str, float] = field(default_factory=dict)
    rationale_tags: List[str] = field(default_factory=list)
    missing_information_requests: List[str] = field(default_factory=list)
    reference: Optional[SimulationMarketReference] = None
    parse_mode: str = "heuristic"
    source_excerpt: Optional[str] = None

    def __post_init__(self) -> None:
        self.forecast_id = _normalize_optional_string(self.forecast_id)
        self.question_type = _require_non_empty_string("question_type", self.question_type)
        self.agent_id = int(self.agent_id or 0)
        self.agent_name = _require_non_empty_string("agent_name", self.agent_name)
        self.judgment_type = _require_non_empty_string("judgment_type", self.judgment_type)
        self.probability = _normalize_optional_score("probability", self.probability)
        self.confidence = _normalize_optional_score("confidence", self.confidence)
        self.uncertainty_expression = _normalize_optional_string(self.uncertainty_expression)
        self.dominant_outcome = _normalize_optional_string(self.dominant_outcome)
        normalized_distribution: Dict[str, float] = {}
        for key, value in _normalize_dict("outcome_distribution", self.outcome_distribution).items():
            label = _require_non_empty_string("outcome_distribution label", key)
            score = _normalize_optional_score(
                f"outcome_distribution.{label}",
                value,
            )
            if score is not None:
                normalized_distribution[label] = score
        self.outcome_distribution = normalized_distribution
        self.rationale_tags = _normalize_string_list("rationale_tags", self.rationale_tags)
        self.missing_information_requests = _normalize_string_list(
            "missing_information_requests",
            self.missing_information_requests,
        )
        if self.reference is not None and isinstance(self.reference, dict):
            self.reference = SimulationMarketReference.from_dict(self.reference)
        self.parse_mode = _require_non_empty_string("parse_mode", self.parse_mode)
        self.source_excerpt = _normalize_optional_string(self.source_excerpt)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "question_type": self.question_type,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "judgment_type": self.judgment_type,
            "probability": self.probability,
            "confidence": self.confidence,
            "uncertainty_expression": self.uncertainty_expression,
            "dominant_outcome": self.dominant_outcome,
            "outcome_distribution": dict(self.outcome_distribution),
            "rationale_tags": list(self.rationale_tags),
            "missing_information_requests": list(self.missing_information_requests),
            "reference": self.reference.to_dict() if self.reference else None,
            "parse_mode": self.parse_mode,
            "source_excerpt": self.source_excerpt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketAgentBelief":
        return cls(
            forecast_id=data.get("forecast_id"),
            question_type=data["question_type"],
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            judgment_type=data["judgment_type"],
            probability=data.get("probability"),
            confidence=data.get("confidence"),
            uncertainty_expression=data.get("uncertainty_expression"),
            dominant_outcome=data.get("dominant_outcome"),
            outcome_distribution=data.get("outcome_distribution", {}),
            rationale_tags=data.get("rationale_tags", []),
            missing_information_requests=data.get("missing_information_requests", []),
            reference=data.get("reference"),
            parse_mode=data.get("parse_mode", "heuristic"),
            source_excerpt=data.get("source_excerpt"),
        )


@dataclass
class SimulationMarketSnapshot:
    simulation_id: str
    ensemble_id: Optional[str]
    run_id: Optional[str]
    forecast_id: Optional[str]
    question_type: Optional[str]
    extraction_status: str
    participating_agent_count: int
    extracted_signal_count: int
    disagreement_index: Optional[float] = None
    synthetic_consensus_probability: Optional[float] = None
    dominant_outcome: Optional[str] = None
    categorical_distribution: Dict[str, float] = field(default_factory=dict)
    missing_information_request_count: int = 0
    support_status: Optional[str] = None
    boundary_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.simulation_id = _require_non_empty_string("simulation_id", self.simulation_id)
        self.ensemble_id = _normalize_optional_string(self.ensemble_id)
        self.run_id = _normalize_optional_string(self.run_id)
        self.forecast_id = _normalize_optional_string(self.forecast_id)
        self.question_type = _normalize_optional_string(self.question_type)
        self.extraction_status = _validate_supported_value(
            "extraction_status",
            _require_non_empty_string("extraction_status", self.extraction_status),
            SUPPORTED_SIMULATION_MARKET_EXTRACTION_STATUSES,
        )
        self.participating_agent_count = int(self.participating_agent_count or 0)
        self.extracted_signal_count = int(self.extracted_signal_count or 0)
        self.disagreement_index = _normalize_optional_score(
            "disagreement_index",
            self.disagreement_index,
        )
        self.synthetic_consensus_probability = _normalize_optional_score(
            "synthetic_consensus_probability",
            self.synthetic_consensus_probability,
        )
        self.dominant_outcome = _normalize_optional_string(self.dominant_outcome)
        normalized_distribution: Dict[str, float] = {}
        for key, value in _normalize_dict("categorical_distribution", self.categorical_distribution).items():
            label = _require_non_empty_string("categorical_distribution label", key)
            score = _normalize_optional_score(
                f"categorical_distribution.{label}",
                value,
            )
            if score is not None:
                normalized_distribution[label] = score
        self.categorical_distribution = normalized_distribution
        self.missing_information_request_count = int(
            self.missing_information_request_count or 0
        )
        self.support_status = _normalize_optional_string(self.support_status) or self.extraction_status
        self.boundary_notes = _normalize_string_list("boundary_notes", self.boundary_notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": "simulation_market_snapshot",
            "schema_version": SIMULATION_MARKET_SCHEMA_VERSION,
            "generator_version": SIMULATION_MARKET_GENERATOR_VERSION,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "forecast_id": self.forecast_id,
            "question_type": self.question_type,
            "extraction_status": self.extraction_status,
            "support_status": self.support_status,
            "participating_agent_count": self.participating_agent_count,
            "extracted_signal_count": self.extracted_signal_count,
            "disagreement_index": self.disagreement_index,
            "synthetic_consensus_probability": self.synthetic_consensus_probability,
            "dominant_outcome": self.dominant_outcome,
            "categorical_distribution": dict(self.categorical_distribution),
            "missing_information_request_count": self.missing_information_request_count,
            "boundary_notes": list(self.boundary_notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketSnapshot":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data.get("ensemble_id"),
            run_id=data.get("run_id"),
            forecast_id=data.get("forecast_id"),
            question_type=data.get("question_type"),
            extraction_status=data.get("extraction_status", "partial"),
            participating_agent_count=data.get("participating_agent_count", 0),
            extracted_signal_count=data.get("extracted_signal_count", 0),
            disagreement_index=data.get("disagreement_index"),
            synthetic_consensus_probability=data.get("synthetic_consensus_probability"),
            dominant_outcome=data.get("dominant_outcome"),
            categorical_distribution=data.get("categorical_distribution", {}),
            missing_information_request_count=data.get(
                "missing_information_request_count",
                0,
            ),
            support_status=data.get("support_status"),
            boundary_notes=data.get("boundary_notes", []),
        )


@dataclass
class SimulationMarketDisagreementSummary:
    simulation_id: str
    ensemble_id: Optional[str]
    run_id: Optional[str]
    forecast_id: Optional[str]
    question_type: Optional[str]
    support_status: str
    participant_count: int
    judgment_count: int
    disagreement_index: Optional[float] = None
    consensus_probability: Optional[float] = None
    consensus_outcome: Optional[str] = None
    distribution: Dict[str, float] = field(default_factory=dict)
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    boundary_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.simulation_id = _require_non_empty_string("simulation_id", self.simulation_id)
        self.ensemble_id = _normalize_optional_string(self.ensemble_id)
        self.run_id = _normalize_optional_string(self.run_id)
        self.forecast_id = _normalize_optional_string(self.forecast_id)
        self.question_type = _normalize_optional_string(self.question_type)
        self.support_status = _validate_supported_value(
            "support_status",
            _require_non_empty_string("support_status", self.support_status),
            SUPPORTED_SIMULATION_MARKET_EXTRACTION_STATUSES,
        )
        self.participant_count = int(self.participant_count or 0)
        self.judgment_count = int(self.judgment_count or 0)
        self.disagreement_index = _normalize_optional_score(
            "disagreement_index",
            self.disagreement_index,
        )
        self.consensus_probability = _normalize_optional_score(
            "consensus_probability",
            self.consensus_probability,
        )
        self.consensus_outcome = _normalize_optional_string(self.consensus_outcome)
        normalized_distribution: Dict[str, float] = {}
        for key, value in _normalize_dict("distribution", self.distribution).items():
            label = _require_non_empty_string("distribution label", key)
            score = _normalize_optional_score(f"distribution.{label}", value)
            if score is not None:
                normalized_distribution[label] = score
        self.distribution = normalized_distribution
        self.range_low = _normalize_optional_score("range_low", self.range_low)
        self.range_high = _normalize_optional_score("range_high", self.range_high)
        self.warnings = _normalize_string_list("warnings", self.warnings)
        self.boundary_notes = _normalize_string_list("boundary_notes", self.boundary_notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": "simulation_market_disagreement_summary",
            "schema_version": SIMULATION_MARKET_SCHEMA_VERSION,
            "generator_version": SIMULATION_MARKET_GENERATOR_VERSION,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "forecast_id": self.forecast_id,
            "question_type": self.question_type,
            "support_status": self.support_status,
            "participant_count": self.participant_count,
            "judgment_count": self.judgment_count,
            "disagreement_index": self.disagreement_index,
            "consensus_probability": self.consensus_probability,
            "consensus_outcome": self.consensus_outcome,
            "distribution": dict(self.distribution),
            "range_low": self.range_low,
            "range_high": self.range_high,
            "warnings": list(self.warnings),
            "boundary_notes": list(self.boundary_notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketDisagreementSummary":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data.get("ensemble_id"),
            run_id=data.get("run_id"),
            forecast_id=data.get("forecast_id"),
            question_type=data.get("question_type"),
            support_status=data.get("support_status", "partial"),
            participant_count=data.get("participant_count", 0),
            judgment_count=data.get("judgment_count", 0),
            disagreement_index=data.get("disagreement_index"),
            consensus_probability=data.get("consensus_probability"),
            consensus_outcome=data.get("consensus_outcome"),
            distribution=data.get("distribution", {}),
            range_low=data.get("range_low"),
            range_high=data.get("range_high"),
            warnings=data.get("warnings", []),
            boundary_notes=data.get("boundary_notes", []),
        )


@dataclass
class SimulationMarketManifest:
    simulation_id: str
    ensemble_id: Optional[str]
    run_id: Optional[str]
    forecast_id: Optional[str]
    question_type: Optional[str]
    extraction_status: str
    supported_question_type: bool
    forecast_workspace_linked: bool
    scope_linked_to_run: bool
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    signal_counts: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    source_artifacts: Dict[str, Any] = field(default_factory=dict)
    boundary_notes: List[str] = field(default_factory=list)
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self) -> None:
        self.simulation_id = _require_non_empty_string("simulation_id", self.simulation_id)
        self.ensemble_id = _normalize_optional_string(self.ensemble_id)
        self.run_id = _normalize_optional_string(self.run_id)
        self.forecast_id = _normalize_optional_string(self.forecast_id)
        self.question_type = _normalize_optional_string(self.question_type)
        self.extraction_status = _validate_supported_value(
            "extraction_status",
            _require_non_empty_string("extraction_status", self.extraction_status),
            SUPPORTED_SIMULATION_MARKET_EXTRACTION_STATUSES,
        )
        self.supported_question_type = bool(self.supported_question_type)
        self.forecast_workspace_linked = bool(self.forecast_workspace_linked)
        self.scope_linked_to_run = bool(self.scope_linked_to_run)
        self.artifact_paths = {
            _require_non_empty_string("artifact_paths key", key): _require_non_empty_string(
                f"artifact_paths.{key}",
                value,
            )
            for key, value in _normalize_dict("artifact_paths", self.artifact_paths).items()
        }
        self.signal_counts = {
            _require_non_empty_string("signal_counts key", key): int(value or 0)
            for key, value in _normalize_dict("signal_counts", self.signal_counts).items()
        }
        self.warnings = _normalize_string_list("warnings", self.warnings)
        self.source_artifacts = _normalize_dict("source_artifacts", self.source_artifacts)
        self.boundary_notes = _normalize_string_list("boundary_notes", self.boundary_notes)
        self.extracted_at = _require_iso_datetime("extracted_at", self.extracted_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": "simulation_market_manifest",
            "schema_version": SIMULATION_MARKET_SCHEMA_VERSION,
            "generator_version": SIMULATION_MARKET_GENERATOR_VERSION,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "forecast_id": self.forecast_id,
            "question_type": self.question_type,
            "extraction_status": self.extraction_status,
            "supported_question_type": self.supported_question_type,
            "forecast_workspace_linked": self.forecast_workspace_linked,
            "scope_linked_to_run": self.scope_linked_to_run,
            "artifact_paths": dict(self.artifact_paths),
            "signal_counts": dict(self.signal_counts),
            "warnings": list(self.warnings),
            "source_artifacts": dict(self.source_artifacts),
            "boundary_notes": list(self.boundary_notes),
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketManifest":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data.get("ensemble_id"),
            run_id=data.get("run_id"),
            forecast_id=data.get("forecast_id"),
            question_type=data.get("question_type"),
            extraction_status=data.get("extraction_status", "partial"),
            supported_question_type=data.get("supported_question_type", False),
            forecast_workspace_linked=data.get("forecast_workspace_linked", False),
            scope_linked_to_run=data.get("scope_linked_to_run", False),
            artifact_paths=data.get("artifact_paths", {}),
            signal_counts=data.get("signal_counts", {}),
            warnings=data.get("warnings", []),
            source_artifacts=data.get("source_artifacts", {}),
            boundary_notes=data.get("boundary_notes", []),
            extracted_at=data.get("extracted_at", datetime.now().isoformat()),
        )


@dataclass
class SimulationMarketSummary:
    simulation_id: str
    ensemble_id: Optional[str]
    run_id: Optional[str]
    forecast_id: Optional[str]
    question_type: Optional[str]
    support_status: str
    provenance_status: str = "partial"
    participant_count: int = 0
    judgment_count: int = 0
    evidence_bundle_ids: List[str] = field(default_factory=list)
    synthetic_consensus_probability: Optional[float] = None
    disagreement_index: Optional[float] = None
    argument_cluster_distribution: Dict[str, float] = field(default_factory=dict)
    belief_momentum: Dict[str, Any] = field(default_factory=dict)
    minority_warning_signal: Dict[str, Any] = field(default_factory=dict)
    missing_information_signal: Dict[str, Any] = field(default_factory=dict)
    scenario_split_distribution: Dict[str, float] = field(default_factory=dict)
    signals: Dict[str, Any] = field(default_factory=dict)
    signal_provenance: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    downgrade_reasons: List[str] = field(default_factory=list)
    boundary_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.simulation_id = _require_non_empty_string("simulation_id", self.simulation_id)
        self.ensemble_id = _normalize_optional_string(self.ensemble_id)
        self.run_id = _normalize_optional_string(self.run_id)
        self.forecast_id = _normalize_optional_string(self.forecast_id)
        self.question_type = _normalize_optional_string(self.question_type)
        self.support_status = _validate_supported_value(
            "support_status",
            _require_non_empty_string("support_status", self.support_status),
            SUPPORTED_SIMULATION_MARKET_EXTRACTION_STATUSES,
        )
        self.provenance_status = _validate_supported_value(
            "provenance_status",
            _require_non_empty_string("provenance_status", self.provenance_status),
            SUPPORTED_SIMULATION_MARKET_PROVENANCE_STATUSES,
        )
        self.participant_count = int(self.participant_count or 0)
        self.judgment_count = int(self.judgment_count or 0)
        self.evidence_bundle_ids = _normalize_string_list(
            "evidence_bundle_ids",
            self.evidence_bundle_ids,
        )
        self.synthetic_consensus_probability = _normalize_optional_score(
            "synthetic_consensus_probability",
            self.synthetic_consensus_probability,
        )
        self.disagreement_index = _normalize_optional_score(
            "disagreement_index",
            self.disagreement_index,
        )
        self.argument_cluster_distribution = {
            _require_non_empty_string("argument_cluster_distribution key", key): score
            for key, score in (
                (
                    key,
                    _normalize_optional_score(
                        f"argument_cluster_distribution.{key}",
                        value,
                    ),
                )
                for key, value in _normalize_dict(
                    "argument_cluster_distribution",
                    self.argument_cluster_distribution,
                ).items()
            )
            if score is not None
        }
        self.belief_momentum = _normalize_dict("belief_momentum", self.belief_momentum)
        self.minority_warning_signal = _normalize_dict(
            "minority_warning_signal",
            self.minority_warning_signal,
        )
        self.missing_information_signal = _normalize_dict(
            "missing_information_signal",
            self.missing_information_signal,
        )
        self.scenario_split_distribution = {
            _require_non_empty_string("scenario_split_distribution key", key): score
            for key, score in (
                (
                    key,
                    _normalize_optional_score(
                        f"scenario_split_distribution.{key}",
                        value,
                    ),
                )
                for key, value in _normalize_dict(
                    "scenario_split_distribution",
                    self.scenario_split_distribution,
                ).items()
            )
            if score is not None
        }
        self.signals = _normalize_dict("signals", self.signals)
        provenance_map = _normalize_dict("signal_provenance", self.signal_provenance)
        normalized_provenance: Dict[str, List[Dict[str, Any]]] = {}
        for signal_name, references in provenance_map.items():
            normalized_signal_name = _require_non_empty_string(
                "signal_provenance key",
                signal_name,
            )
            if references is None:
                normalized_provenance[normalized_signal_name] = []
                continue
            if not isinstance(references, list):
                raise ValueError("signal_provenance values must be lists")
            normalized_references: List[Dict[str, Any]] = []
            for item in references:
                if isinstance(item, SimulationMarketReference):
                    normalized_references.append(item.to_dict())
                elif isinstance(item, dict):
                    normalized_references.append(SimulationMarketReference.from_dict(item).to_dict())
                else:
                    raise ValueError("signal_provenance references must be dictionaries")
            normalized_provenance[normalized_signal_name] = normalized_references
        self.signal_provenance = normalized_provenance
        self.warnings = _normalize_string_list("warnings", self.warnings)
        self.downgrade_reasons = _normalize_string_list(
            "downgrade_reasons",
            self.downgrade_reasons,
        )
        self.boundary_notes = _normalize_string_list("boundary_notes", self.boundary_notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": SIMULATION_MARKET_SUMMARY_ARTIFACT_TYPE,
            "schema_version": SIMULATION_MARKET_SCHEMA_VERSION,
            "generator_version": SIMULATION_MARKET_GENERATOR_VERSION,
            "simulation_id": self.simulation_id,
            "ensemble_id": self.ensemble_id,
            "run_id": self.run_id,
            "forecast_id": self.forecast_id,
            "question_type": self.question_type,
            "support_status": self.support_status,
            "provenance_status": self.provenance_status,
            "participant_count": self.participant_count,
            "judgment_count": self.judgment_count,
            "evidence_bundle_ids": list(self.evidence_bundle_ids),
            "synthetic_consensus_probability": self.synthetic_consensus_probability,
            "disagreement_index": self.disagreement_index,
            "argument_cluster_distribution": dict(self.argument_cluster_distribution),
            "belief_momentum": dict(self.belief_momentum),
            "minority_warning_signal": dict(self.minority_warning_signal),
            "missing_information_signal": dict(self.missing_information_signal),
            "scenario_split_distribution": dict(self.scenario_split_distribution),
            "signals": dict(self.signals),
            "signal_provenance": {
                key: [dict(item) for item in value]
                for key, value in self.signal_provenance.items()
            },
            "warnings": list(self.warnings),
            "downgrade_reasons": list(self.downgrade_reasons),
            "boundary_notes": list(self.boundary_notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationMarketSummary":
        return cls(
            simulation_id=data["simulation_id"],
            ensemble_id=data.get("ensemble_id"),
            run_id=data.get("run_id"),
            forecast_id=data.get("forecast_id"),
            question_type=data.get("question_type"),
            support_status=data.get("support_status", "partial"),
            provenance_status=data.get("provenance_status", "partial"),
            participant_count=data.get("participant_count", 0),
            judgment_count=data.get("judgment_count", 0),
            evidence_bundle_ids=data.get("evidence_bundle_ids", []),
            synthetic_consensus_probability=data.get("synthetic_consensus_probability"),
            disagreement_index=data.get("disagreement_index"),
            argument_cluster_distribution=data.get("argument_cluster_distribution", {}),
            belief_momentum=data.get("belief_momentum", {}),
            minority_warning_signal=data.get("minority_warning_signal", {}),
            missing_information_signal=data.get("missing_information_signal", {}),
            scenario_split_distribution=data.get("scenario_split_distribution", {}),
            signals=data.get("signals", {}),
            signal_provenance=data.get("signal_provenance", {}),
            warnings=data.get("warnings", []),
            downgrade_reasons=data.get("downgrade_reasons", []),
            boundary_notes=data.get("boundary_notes", []),
        )
