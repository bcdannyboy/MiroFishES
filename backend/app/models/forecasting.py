"""
Canonical hybrid forecasting foundation artifacts.

This module defines the additive forecasting workspace contract used by the
hybrid architecture reset. Simulation remains a worker inside this workspace;
it is no longer the only engine implied by the domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


FORECAST_SCHEMA_VERSION = "forecast.foundation.v1"
FORECAST_GENERATOR_VERSION = "forecast.foundation.generator.v1"
SIMULATION_WORKER_CONTRACT_VERSION = "forecast.simulation_worker_contract.v1"
FORECAST_LIFECYCLE_METADATA_VERSION = "forecast.lifecycle_metadata.v1"
FORECAST_SIMULATION_SCOPE_VERSION = "forecast.simulation_scope.v1"
FORECAST_RESOLUTION_RECORD_VERSION = "forecast.resolution_record.v1"
FORECAST_SCORING_EVENT_VERSION = "forecast.scoring_event.v1"

CANONICAL_FORECAST_STAGE_SEQUENCE = (
    "forecast_question",
    "forecast_workspace",
    "forecast_answer",
    "resolution_record",
    "scoring_event",
)

REQUIRED_FORECAST_PRIMITIVES = (
    "forecast_question",
    "resolution_criteria",
    "evidence_bundle",
    "forecast_worker",
    "prediction_ledger",
    "evaluation_case",
    "forecast_answer",
    "simulation_worker_contract",
)

SUPPORTED_FORECAST_QUESTION_TYPES = {
    "binary",
    "categorical",
    "numeric",
    "scenario",
}
SUPPORTED_FORECAST_QUESTION_TEMPLATES = (
    {
        "template_id": "binary_event_by_horizon",
        "label": "Binary event by horizon",
        "question_type": "binary",
        "prompt_template": "Will <named event> happen by <date>?",
        "required_fields": [
            "question_text",
            "horizon",
            "resolution_criteria",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Abstain when the event boundary, horizon, or named resolution source is missing."
        ),
        "notes": [
            "Best for yes-or-no questions with explicit timing and resolution rules.",
        ],
    },
    {
        "template_id": "numeric_threshold_by_horizon",
        "label": "Binary threshold event by horizon",
        "question_type": "binary",
        "prompt_template": "Will <metric> be <operator> <threshold> by <date>?",
        "required_fields": [
            "question_text",
            "horizon",
            "resolution_criteria",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Abstain when the metric, threshold operator, or resolution source is underspecified."
        ),
        "notes": [
            "Threshold questions resolve yes-or-no and remain part of the binary lane.",
        ],
    },
    {
        "template_id": "numeric_value_by_horizon",
        "label": "Numeric value by horizon",
        "question_type": "numeric",
        "prompt_template": "What value will <metric> have by <date>?",
        "required_fields": [
            "question_text",
            "horizon",
            "resolution_criteria",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Abstain when the metric definition, unit, or resolution source is underspecified."
        ),
        "notes": [
            "Use for scalar numeric forecasts that should resolve to one observed value with units.",
        ],
    },
    {
        "template_id": "numeric_range_by_horizon",
        "label": "Numeric range by horizon",
        "question_type": "numeric",
        "prompt_template": "What bounded range will <metric> fall within by <date>?",
        "required_fields": [
            "question_text",
            "horizon",
            "resolution_criteria",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Abstain when the metric definition, units, or admissible value bounds are underspecified."
        ),
        "notes": [
            "Use when the answer should be a numeric estimate with explicit interval bounds rather than a binary threshold.",
        ],
    },
    {
        "template_id": "categorical_outcome_by_horizon",
        "label": "Categorical outcome by horizon",
        "question_type": "categorical",
        "prompt_template": "Which named outcome will be observed by <date>?",
        "required_fields": [
            "question_text",
            "horizon",
            "resolution_criteria",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Abstain when the candidate outcomes are not mutually exclusive or cannot be resolved from one source."
        ),
        "notes": [
            "Use only when the outcome labels are explicitly named and resolution is externally checkable.",
        ],
    },
    {
        "template_id": "scenario_exploration_prompt",
        "label": "Scenario exploration prompt",
        "question_type": "scenario",
        "prompt_template": "What scenario families dominate under <bounded assumptions>?",
        "required_fields": [
            "question_text",
            "issue_timestamp",
            "source",
        ],
        "abstain_guidance": (
            "Treat this as scenario exploration only unless non-simulation evidence supports a defended forecast estimate."
        ),
        "notes": [
            "This template preserves simulation-led scenario analysis without claiming forecast probability by default.",
        ],
    },
)
SUPPORTED_FORECAST_STATUSES = {
    "draft",
    "active",
    "resolved",
    "archived",
}
SUPPORTED_RESOLUTION_CRITERIA_TYPES = {
    "manual",
    "metric_threshold",
    "event_resolution",
}
SUPPORTED_EVIDENCE_BUNDLE_AVAILABILITY_STATUSES = {
    "available",
    "partial",
    "unavailable",
}
SUPPORTED_EVIDENCE_PROVIDER_KINDS = {
    "uploaded_local_artifact",
    "live_external",
    "manual",
}
SUPPORTED_EVIDENCE_PROVIDER_STATUSES = {
    "available",
    "partial",
    "unavailable",
}
SUPPORTED_EVIDENCE_ENTRY_KINDS = {
    "uploaded_source",
    "graph_provenance",
    "local_artifact",
    "prepared_artifact",
    "report_artifact",
    "external_document",
    "external_availability",
    "manual_note",
    "missing_evidence",
}
SUPPORTED_EVIDENCE_DESCRIPTOR_STATUSES = {
    "fresh",
    "stale",
    "unknown",
    "high",
    "medium",
    "low",
    "strong",
    "usable",
    "weak",
}
SUPPORTED_EVIDENCE_UNCERTAINTY_CODES = {
    "stale",
    "sparse",
    "conflicting",
    "missing",
}
SUPPORTED_FORECAST_WORKER_KINDS = {
    "simulation",
    "simulation_market",
    "base_rate",
    "reference_class",
    "retrieval_synthesis",
    "analytical",
    "retrieval",
    "human",
}
SUPPORTED_FORECAST_WORKER_STATUSES = {
    "registered",
    "ready",
    "running",
    "completed",
    "failed",
}
SUPPORTED_PREDICTION_LEDGER_ENTRY_KINDS = {
    "issue",
    "revision",
}
SUPPORTED_WORKER_OUTPUT_SEMANTICS = {
    "scenario_evidence",
    "forecast_probability",
    "forecast_distribution",
    "retrieval_evidence",
    "qualitative_judgment",
    "numeric_estimate",
    "numeric_interval_estimate",
    "evaluation_outcome",
}
SUPPORTED_PREDICTION_VALUE_TYPES = {
    "probability",
    "distribution",
    "categorical_distribution",
    "numeric_estimate",
    "numeric_interval",
    "scenario_observed_share",
    "qualitative",
}
SUPPORTED_PREDICTION_VALUE_SEMANTICS = {
    "forecast_probability",
    "forecast_distribution",
    "observed_run_share",
    "qualitative_judgment",
    "numeric_estimate",
    "numeric_interval_estimate",
}
SUPPORTED_CALIBRATION_STATES = {
    "uncalibrated",
    "calibrated",
    "not_applicable",
}
SUPPORTED_PREDICTION_RESOLUTION_STATES = {
    "pending",
    "open",
    "resolved",
    "resolved_true",
    "resolved_false",
    "abstained",
    "voided",
    "superseded",
}
SUPPORTED_EVALUATION_CASE_STATUSES = {
    "pending",
    "resolved",
    "superseded",
}
SUPPORTED_FORECAST_ANSWER_TYPES = {
    "hybrid_forecast",
    "simulation_scenario_summary",
    "evaluation_snapshot",
    "working_note",
}
SUPPORTED_EVIDENCE_BUNDLE_STATUSES = {
    "unavailable",
    "partial",
    "ready",
}
SUPPORTED_CONFIDENCE_SEMANTICS = {
    "uncalibrated",
    "calibrated",
    "not_applicable",
}
SUPPORTED_FORECAST_CALIBRATION_KINDS = {
    "binary_reliability",
    "categorical_distribution",
    "numeric_interval",
}
SUPPORTED_SIMULATION_PROBABILITY_INTERPRETATIONS = {
    "do_not_treat_as_real_world_probability",
    "evaluation_required_for_probability_claims",
}
SUPPORTED_WORKSPACE_LIFECYCLE_STAGES = set(CANONICAL_FORECAST_STAGE_SEQUENCE)
SUPPORTED_SIMULATION_SCOPE_PREPARE_STATUSES = {
    "unprepared",
    "requested",
    "ready",
}
SUPPORTED_SIMULATION_SCOPE_STATUSES = {
    "linked",
    "unlinked",
}
SUPPORTED_SCORING_EVENT_STATUSES = {
    "pending",
    "scored",
    "not_applicable",
}
SUPPORTED_EVIDENCE_PROVIDER_KINDS = {
    "uploaded_local_artifact",
    "live_external",
    "manual",
    "derived",
}
SUPPORTED_EVIDENCE_PROVIDER_STATUSES = {
    "ready",
    "partial",
    "unavailable",
    "not_configured",
    "error",
}
SUPPORTED_EVIDENCE_FRESHNESS_STATES = {
    "fresh",
    "aging",
    "stale",
    "unknown",
}
SUPPORTED_EVIDENCE_RELEVANCE_STATES = {
    "high",
    "medium",
    "low",
    "unknown",
}
SUPPORTED_EVIDENCE_UNCERTAINTY_LABELS = {
    "stale_evidence",
    "sparse_evidence",
    "conflicting_evidence",
    "missing_evidence",
}
SUPPORTED_EVIDENCE_PROVIDER_KINDS = {
    "uploaded_local",
    "uploaded_local_artifact",
    "external_live",
    "live_external",
    "manual",
    "derived",
}
SUPPORTED_EVIDENCE_ENTRY_KINDS = {
    "uploaded_source",
    "uploaded_local_artifact",
    "graph_provenance",
    "graph_summary",
    "grounding_bundle",
    "prepared_snapshot",
    "report_context",
    "local_artifact",
    "prepared_artifact",
    "report_artifact",
    "external_document",
    "manual_note",
    "missing_evidence",
}
SUPPORTED_EVIDENCE_FRESHNESS_STATUSES = {
    "fresh",
    "aging",
    "stale",
    "timeless",
    "unknown",
}
SUPPORTED_EVIDENCE_CONFLICT_STATUSES = {
    "none",
    "supports",
    "contradicts",
    "mixed",
    "missing",
    "unknown",
}
SUPPORTED_EVIDENCE_BUNDLE_STATUSES = {
    "draft",
    "ready",
    "degraded",
    "partial",
    "unavailable",
}
SUPPORTED_EVIDENCE_UNCERTAINTY_CAUSES = {
    "stale",
    "sparse",
    "conflicting",
    "missing",
    "stale_evidence",
    "sparse_evidence",
    "conflicting_evidence",
    "missing_evidence",
    "provider_unavailable",
    "relevance_uncertain",
}


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


def _normalize_score(
    name: str,
    value: Any,
    *,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if normalized < minimum or normalized > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return normalized


def _clamp_score(value: Any, *, default: float = 0.5) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = float(default)
    return max(0.0, min(1.0, normalized))


class ResolutionStateRecord(dict):
    """Dict-like resolution state that also compares cleanly to a status string."""

    def __init__(
        self,
        status: str = "pending",
        *,
        resolved_at: Optional[str] = None,
        resolution_note: str = "",
        **extra: Any,
    ) -> None:
        payload: Dict[str, Any] = {
            "status": status,
            "resolved_at": resolved_at,
            "resolution_note": resolution_note,
        }
        payload.update(extra)
        super().__init__(payload)

    def __eq__(self, other: Any) -> bool:  # pragma: no cover - exercised via tests
        if isinstance(other, str):
            return self.get("status") == other
        return dict.__eq__(self, other)


def _require_iso_datetime(name: str, value: Any) -> str:
    text = _require_non_empty_string(name, value)
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime") from exc
    return text


def _require_iso_date(name: str, value: Any) -> str:
    text = _require_non_empty_string(name, value)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 date") from exc
    return text


def _normalize_string_list(name: str, values: Any) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")

    normalized: List[str] = []
    seen = set()
    for item in values:
        text = _require_non_empty_string(name, item)
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def _normalize_dict(name: str, value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a dictionary")
    return dict(value)


def _normalize_optional_datetime(name: str, value: Any) -> Optional[str]:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    return _require_iso_datetime(name, normalized)


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


def _normalize_label_list(
    name: str,
    values: Any,
    supported_values: Optional[set[str]] = None,
) -> List[str]:
    labels = _normalize_string_list(name, values)
    if supported_values is None:
        return labels
    for label in labels:
        _validate_supported_value(name, label, supported_values)
    return labels


def _dedupe_marker_dicts(markers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for marker in markers:
        normalized_marker = {key: value for key, value in marker.items() if value is not None}
        marker_key = jsonish_dumps(normalized_marker)
        if marker_key in seen:
            continue
        seen.add(marker_key)
        deduped.append(normalized_marker)
    return deduped


def _normalize_marker_list(name: str, values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")

    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            payload = {key: value for key, value in item.items() if value is not None}
            text = (
                _normalize_optional_string(item.get("code"))
                or _normalize_optional_string(item.get("kind"))
                or _normalize_optional_string(item.get("label"))
                or _normalize_optional_string(item.get("summary"))
                or _normalize_optional_string(item.get("reason"))
            )
        else:
            text = _normalize_optional_string(item)
            payload = {"code": text} if text is not None else {}
        if text and text not in seen:
            payload.setdefault("code", text)
            normalized.append(payload)
            seen.add(text)
    return normalized


def _normalize_provider_kind_alias(value: Any) -> str:
    normalized = _require_non_empty_string("provider_kind", value)
    aliases = {
        "uploaded_local_artifact": "uploaded_local",
        "uploaded_local_artifacts": "uploaded_local",
        "live_external": "external_live",
    }
    return aliases.get(normalized, normalized)


def _freshness_from_timestamps(*timestamps: Optional[str], reference_time: Optional[str] = None) -> str:
    normalized_reference = _normalize_optional_string(reference_time)
    reference_value = (
        datetime.fromisoformat(normalized_reference)
        if normalized_reference
        else datetime.now()
    )
    evidence_times = [
        datetime.fromisoformat(timestamp)
        for timestamp in timestamps
        if _normalize_optional_string(timestamp) is not None
    ]
    if not evidence_times:
        return "unknown"
    age_days = (reference_value - max(evidence_times)).total_seconds() / 86400
    if age_days <= 7:
        return "fresh"
    if age_days <= 30:
        return "aging"
    return "stale"


def _score_from_label(label: str, mapping: Dict[str, float], *, fallback: float = 0.5) -> float:
    return mapping.get(label, fallback)


def _normalize_quality_scores(
    quality_scores: Any,
    *,
    entry_scores: List[float],
    freshness_states: List[str],
    relevance_states: List[str],
    contradiction_markers: List[Dict[str, Any]],
    missing_markers: List[Dict[str, Any]],
) -> Dict[str, float]:
    if quality_scores is None:
        quality_scores = {}
    if not isinstance(quality_scores, dict):
        raise ValueError("quality_scores must be a dictionary")

    normalized: Dict[str, float] = {}
    for key, value in quality_scores.items():
        score = _normalize_optional_score(f"quality_scores.{key}", value)
        if score is not None:
            normalized[key] = score

    if entry_scores:
        normalized.setdefault("entry_average", round(sum(entry_scores) / len(entry_scores), 4))
    else:
        normalized.setdefault("entry_average", 0.0)

    freshness_score = (
        sum(
            _score_from_label(
                state,
                {"fresh": 0.9, "aging": 0.7, "stale": 0.35, "unknown": 0.5},
            )
            for state in freshness_states
        )
        / len(freshness_states)
        if freshness_states
        else 0.0
    )
    relevance_score = (
        sum(
            _score_from_label(
                state,
                {"high": 0.9, "medium": 0.7, "low": 0.4, "unknown": 0.5},
            )
            for state in relevance_states
        )
        / len(relevance_states)
        if relevance_states
        else 0.0
    )
    normalized.setdefault("freshness", round(freshness_score, 4))
    normalized.setdefault("relevance", round(relevance_score, 4))
    normalized.setdefault("coverage", round(min(len(entry_scores) / 3, 1.0), 4))
    conflict_penalty = 0.12 if contradiction_markers else 0.0
    missing_penalty = 0.08 if missing_markers else 0.0
    sparse_penalty = 0.05 if len(entry_scores) < 2 else 0.0
    derived_overall = max(
        0.0,
        min(
            (
                normalized["entry_average"]
                + normalized["freshness"]
                + normalized["relevance"]
                + normalized["coverage"]
            )
            / 4
            - conflict_penalty
            - missing_penalty
            - sparse_penalty,
            1.0,
        ),
    )
    normalized.setdefault("overall", round(derived_overall, 4))
    return normalized


def _build_state_summary(states: List[str], *, unknown_label: str) -> Dict[str, Any]:
    counts = {state: states.count(state) for state in sorted(set(states))}
    if states:
        dominant_state = max(counts, key=counts.get)
    else:
        dominant_state = unknown_label
    return {
        "status": dominant_state,
        "counts": counts,
        "count": len(states),
    }


def _derive_uncertainty(
    *,
    source_entries: List["EvidenceSourceEntry"],
    contradiction_markers: List[Dict[str, Any]],
    missing_markers: List[Dict[str, Any]],
) -> tuple[List[str], List[str]]:
    labels: List[str] = []
    reasons: List[str] = []
    freshness_states = [entry.freshness for entry in source_entries]
    if any(state == "stale" for state in freshness_states):
        labels.append("stale_evidence")
        reasons.append("At least one evidence source is stale relative to the bundle reference time.")
    if len(source_entries) < 2:
        labels.append("sparse_evidence")
        reasons.append("Evidence coverage is sparse; fewer than two normalized evidence entries are attached.")
    if contradiction_markers:
        labels.append("conflicting_evidence")
        reasons.append("Evidence contains explicit contradiction or conflict markers that require analyst review.")
    if missing_markers or not source_entries:
        labels.append("missing_evidence")
        reasons.append("Evidence coverage has explicit missing markers or no normalized evidence entries.")
    return labels, reasons


def jsonish_dumps(value: Any) -> str:
    """Return a stable string key for de-duplication without importing json here."""
    return repr(value)


def _normalize_optional_iso_temporal(name: str, value: Any) -> Optional[str]:
    text = _normalize_optional_string(value)
    if text is None:
        return None
    try:
        if "T" in text:
            datetime.fromisoformat(text)
        else:
            date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime or date") from exc
    return text


def _parse_iso_temporal(value: str) -> datetime:
    if "T" in value:
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime.combine(date.fromisoformat(value), datetime.min.time())
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _sorted_iso_temporals(values: List[Any]) -> List[str]:
    normalized: List[tuple[datetime, str]] = []
    for value in values:
        text = _normalize_optional_string(value)
        if text is None:
            continue
        normalized.append((_parse_iso_temporal(text), text))
    normalized.sort(key=lambda item: item[0])
    return [text for _, text in normalized]


def _normalize_optional_score(name: str, value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric between 0 and 1") from exc
    if score < 0 or score > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return score


def _infer_descriptor_status(
    score: Optional[float],
    *,
    high_threshold: float,
    medium_threshold: float,
    high_label: str,
    medium_label: str,
    low_label: str,
) -> str:
    if score is None:
        return "unknown"
    if score >= high_threshold:
        return high_label
    if score >= medium_threshold:
        return medium_label
    return low_label


def _normalize_evidence_descriptor(
    name: str,
    value: Any,
    *,
    default_status: str,
    inferred_high_label: str,
    inferred_medium_label: str,
    inferred_low_label: str,
    default_reason: str,
) -> Dict[str, Any]:
    if value is None:
        return {
            "status": default_status,
            "score": None,
            "reason": default_reason,
        }
    if isinstance(value, (int, float)):
        score = _normalize_optional_score(name, value)
        return {
            "status": _infer_descriptor_status(
                score,
                high_threshold=0.8,
                medium_threshold=0.5,
                high_label=inferred_high_label,
                medium_label=inferred_medium_label,
                low_label=inferred_low_label,
            ),
            "score": score,
            "reason": default_reason,
        }
    payload = _normalize_dict(name, value)
    score = _normalize_optional_score(f"{name}.score", payload.get("score"))
    status = _normalize_optional_string(payload.get("status"))
    if status is None:
        status = _infer_descriptor_status(
            score,
            high_threshold=0.8,
            medium_threshold=0.5,
            high_label=inferred_high_label,
            medium_label=inferred_medium_label,
            low_label=inferred_low_label,
        )
    status = _validate_supported_value(
        f"{name} status",
        status,
        SUPPORTED_EVIDENCE_DESCRIPTOR_STATUSES,
    )
    return {
        "status": status,
        "score": score,
        "reason": _normalize_optional_string(payload.get("reason")) or default_reason,
    }


def _normalize_marker_list(name: str, values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")
    normalized: List[Dict[str, Any]] = []
    for item in values:
        if isinstance(item, str):
            item = {
                "code": item,
                "summary": item.replace("_", " "),
            }
        elif not isinstance(item, dict):
            raise ValueError(f"{name} entries must be dictionaries or strings")
        normalized.append(
            {
                "code": (
                    _normalize_optional_string(item.get("code"))
                    or _normalize_optional_string(item.get("kind"))
                    or "unspecified"
                ),
                "summary": _normalize_optional_string(item.get("summary")) or "",
                "severity": _normalize_optional_string(item.get("severity")) or "note",
                "status": _normalize_optional_string(item.get("status")) or "present",
                "entry_id": _normalize_optional_string(item.get("entry_id")),
                "provider_id": _normalize_optional_string(item.get("provider_id")),
            }
        )
    return normalized


def _normalize_provider_status_list(values: Any) -> List[Dict[str, Any]]:
    raw_items = _normalize_list_of_dicts("provider_statuses", values)
    normalized: List[Dict[str, Any]] = []
    for item in raw_items:
        provider_id = _require_non_empty_string(
            "provider_statuses.provider_id",
            item.get("provider_id"),
        )
        provider_kind = _validate_supported_value(
            "provider_statuses.provider_kind",
            _normalize_provider_kind_alias(item.get("provider_kind")),
            SUPPORTED_EVIDENCE_PROVIDER_KINDS,
        )
        status = _validate_supported_value(
            "provider_statuses.status",
            _require_non_empty_string(
                "provider_statuses.status",
                item.get("status", "unavailable"),
            ),
            SUPPORTED_EVIDENCE_PROVIDER_STATUSES,
        )
        normalized.append(
            {
                "provider_id": provider_id,
                "provider_kind": provider_kind,
                "label": _normalize_optional_string(item.get("label")) or provider_id,
                "status": status,
                "boundary_note": _normalize_optional_string(item.get("boundary_note")) or "",
                "collected_at": _normalize_optional_iso_temporal(
                    "provider_statuses.collected_at", item.get("collected_at")
                ),
                "entry_count": int(item.get("entry_count", 0) or 0),
                "warnings": _normalize_string_list(
                    "provider_statuses.warnings", item.get("warnings", [])
                ),
                "metadata": _normalize_dict(
                    "provider_statuses.metadata", item.get("metadata")
                ),
            }
        )
    return normalized


def _normalize_question_horizon(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        text = value.strip()
        return {"label": text} if text else {}
    if not isinstance(value, dict):
        raise ValueError("horizon must be a dictionary or string")
    normalized = dict(value)
    label = _normalize_optional_string(normalized.get("label"))
    if label is not None:
        normalized["label"] = label
    return normalized


def _normalize_numeric_interval_levels(
    name: str,
    values: Any,
    *,
    default: Optional[list[int]] = None,
) -> List[int]:
    if values is None:
        values = default or []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")
    normalized: List[int] = []
    seen: set[int] = set()
    for item in values:
        try:
            level = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} entries must be integer percentages") from exc
        if level <= 0 or level >= 100:
            raise ValueError(f"{name} entries must be between 1 and 99")
        if level in seen:
            continue
        normalized.append(level)
        seen.add(level)
    normalized.sort()
    return normalized


def _normalize_question_spec(
    question_type: str,
    value: Any,
) -> Dict[str, Any]:
    spec = _normalize_dict("question_spec", value)
    if question_type == "categorical":
        outcome_labels = _normalize_string_list(
            "question_spec.outcome_labels",
            spec.get("outcome_labels", spec.get("categories", [])),
        )
        if not outcome_labels:
            raise ValueError(
                "categorical forecast questions require question_spec.outcome_labels"
            )
        spec["outcome_labels"] = outcome_labels
        spec.setdefault("exclusive", True)
    elif question_type == "numeric":
        unit = _normalize_optional_string(spec.get("unit"))
        if unit is not None:
            spec["unit"] = unit
        lower_bound = spec.get("lower_bound")
        upper_bound = spec.get("upper_bound")
        if lower_bound is not None:
            try:
                spec["lower_bound"] = float(lower_bound)
            except (TypeError, ValueError) as exc:
                raise ValueError("question_spec.lower_bound must be numeric") from exc
        if upper_bound is not None:
            try:
                spec["upper_bound"] = float(upper_bound)
            except (TypeError, ValueError) as exc:
                raise ValueError("question_spec.upper_bound must be numeric") from exc
        if (
            spec.get("lower_bound") is not None
            and spec.get("upper_bound") is not None
            and spec["lower_bound"] > spec["upper_bound"]
        ):
            raise ValueError(
                "question_spec.lower_bound cannot exceed question_spec.upper_bound"
            )
        spec["interval_levels"] = _normalize_numeric_interval_levels(
            "question_spec.interval_levels",
            spec.get("interval_levels"),
            default=[50, 80, 90],
        )
    return spec


def _normalize_list_of_dicts(name: str, values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list")

    normalized: List[Dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError(f"{name} entries must be dictionaries")
        normalized.append(dict(item))
    return normalized


def _normalize_evidence_markers(name: str, values: Any) -> List[Dict[str, Any]]:
    markers = _normalize_list_of_dicts(name, values)
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for marker in markers:
        marker_id = (
            _normalize_optional_string(marker.get("marker_id"))
            or _normalize_optional_string(marker.get("marker"))
            or _normalize_optional_string(marker.get("code"))
            or _normalize_optional_string(marker.get("label"))
        )
        if marker_id is None or marker_id in seen:
            continue
        normalized.append(
            {
                "marker_id": marker_id,
                "label": _normalize_optional_string(marker.get("label")) or marker_id,
                "reason": _normalize_optional_string(marker.get("reason")) or "",
                "severity": _normalize_optional_string(marker.get("severity")) or "info",
                **{
                    key: value
                    for key, value in marker.items()
                    if key not in {"marker", "code", "marker_id", "label", "reason", "severity"}
                },
            }
        )
        seen.add(marker_id)
    return normalized


def _normalize_resolution_state(value: Any) -> ResolutionStateRecord:
    if value is None:
        return ResolutionStateRecord("pending")
    if isinstance(value, dict):
        candidate_value = (
            value.get("final_resolution_state")
            or value.get("status")
            or value.get("resolution_state")
            or "pending"
        )
        if isinstance(candidate_value, dict):
            candidate_value = (
                candidate_value.get("status")
                or candidate_value.get("final_resolution_state")
                or candidate_value.get("resolution_state")
                or "pending"
            )
        candidate = _normalize_optional_string(candidate_value) or "pending"
        resolved_at = value.get("resolved_at")
        resolution_note = value.get("resolution_note", "")
        if resolved_at is not None:
            resolved_at = _require_iso_datetime("resolved_at", resolved_at)
        extra = {
            key: val
            for key, val in value.items()
            if key not in {"final_resolution_state", "status", "resolution_state", "resolved_at", "resolution_note"}
        }
        return ResolutionStateRecord(
            candidate,
            resolved_at=resolved_at,
            resolution_note=resolution_note,
            **extra,
        )
    else:
        candidate = value
    if not isinstance(candidate, str):
        candidate = str(candidate)
    candidate = candidate.strip()
    return ResolutionStateRecord(candidate or "pending")


def _validate_supported_value(name: str, value: str, supported_values: set[str]) -> str:
    if value not in supported_values:
        raise ValueError(
            f"Unsupported {name}: {value}. Expected one of: {', '.join(sorted(supported_values))}"
        )
    return value


@dataclass
class ForecastQuestion:
    forecast_id: str
    project_id: str
    title: str
    question: str
    question_text: Optional[str] = None
    question_type: str = "binary"
    question_spec: Dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    horizon: Dict[str, Any] = field(default_factory=dict)
    decomposition: Dict[str, Any] = field(default_factory=dict)
    issue_timestamp: Optional[str] = None
    owner: Optional[str] = None
    source: Optional[str] = None
    decomposition_support: List[Dict[str, Any]] = field(default_factory=list)
    abstention_conditions: List[str] = field(default_factory=list)
    resolution_criteria_ids: List[str] = field(default_factory=list)
    primary_simulation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self) -> None:
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.project_id = _require_non_empty_string("project_id", self.project_id)
        self.title = _require_non_empty_string("title", self.title)
        normalized_question = _normalize_optional_string(self.question) or _normalize_optional_string(
            self.question_text
        )
        self.question = _require_non_empty_string("question", normalized_question)
        self.question_text = self.question
        self.question_type = _validate_supported_value(
            "question_type",
            _require_non_empty_string("question_type", self.question_type),
            SUPPORTED_FORECAST_QUESTION_TYPES,
        )
        self.question_spec = _normalize_question_spec(self.question_type, self.question_spec)
        self.status = _validate_supported_value(
            "status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_FORECAST_STATUSES,
        )
        self.horizon = _normalize_question_horizon(self.horizon)
        self.decomposition = _normalize_dict("decomposition", self.decomposition)
        self.created_at = _require_iso_datetime("created_at", self.created_at)
        self.updated_at = _require_iso_datetime("updated_at", self.updated_at)
        self.issue_timestamp = _require_iso_datetime(
            "issue_timestamp",
            _normalize_optional_string(self.issue_timestamp) or self.created_at,
        )
        if self.horizon.get("type") == "date" and self.horizon.get("value") is not None:
            self.horizon["value"] = _require_iso_date("horizon.value", self.horizon["value"])
        if self.horizon.get("close_at") is not None:
            self.horizon["close_at"] = _require_iso_datetime(
                "horizon.close_at",
                self.horizon["close_at"],
            )
            if _parse_iso_temporal(self.horizon["close_at"]) < _parse_iso_temporal(
                self.issue_timestamp
            ):
                raise ValueError("horizon.close_at must be on or after issue_timestamp")
        if self.horizon.get("resolve_by") is not None:
            resolve_by = _normalize_optional_string(self.horizon.get("resolve_by"))
            if resolve_by is not None:
                if "T" in resolve_by:
                    self.horizon["resolve_by"] = _require_iso_datetime("horizon.resolve_by", resolve_by)
                else:
                    self.horizon["resolve_by"] = _require_iso_date("horizon.resolve_by", resolve_by)
        self.owner = _normalize_optional_string(self.owner)
        self.source = _normalize_optional_string(self.source)
        self.decomposition_support = _normalize_list_of_dicts(
            "decomposition_support", self.decomposition_support
        )
        self.abstention_conditions = _normalize_string_list(
            "abstention_conditions", self.abstention_conditions
        )
        self.resolution_criteria_ids = _normalize_string_list(
            "resolution_criteria_ids", self.resolution_criteria_ids
        )
        self.primary_simulation_id = _normalize_optional_string(self.primary_simulation_id)
        self.tags = _normalize_string_list("tags", self.tags)
        if _parse_iso_temporal(self.issue_timestamp) > _parse_iso_temporal(self.updated_at):
            raise ValueError("issue_timestamp cannot be after updated_at")
        if _parse_iso_temporal(self.created_at) > _parse_iso_temporal(self.updated_at):
            raise ValueError("created_at cannot be after updated_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "project_id": self.project_id,
            "title": self.title,
            "question": self.question,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "question_spec": dict(self.question_spec),
            "status": self.status,
            "horizon": dict(self.horizon),
            "decomposition": dict(self.decomposition),
            "issue_timestamp": self.issue_timestamp,
            "issued_at": self.issue_timestamp,
            "owner": self.owner,
            "source": self.source,
            "decomposition_support": [dict(item) for item in self.decomposition_support],
            "abstention_conditions": list(self.abstention_conditions),
            "resolution_criteria_ids": list(self.resolution_criteria_ids),
            "primary_simulation_id": self.primary_simulation_id,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastQuestion":
        question_text = data.get("question", data.get("question_text", data.get("title")))
        return cls(
            forecast_id=data["forecast_id"],
            project_id=data["project_id"],
            title=data.get("title", question_text),
            question=question_text,
            question_text=data.get("question_text", question_text),
            question_type=data.get("question_type", "binary"),
            question_spec=data.get("question_spec", {}),
            status=data.get("status", "draft"),
            horizon=data.get("horizon", {}),
            decomposition=data.get("decomposition", {}),
            issue_timestamp=data.get("issue_timestamp", data.get("issued_at", data.get("created_at"))),
            owner=data.get("owner"),
            source=data.get("source"),
            decomposition_support=data.get("decomposition_support", []),
            abstention_conditions=data.get("abstention_conditions", []),
            resolution_criteria_ids=data.get("resolution_criteria_ids", []),
            primary_simulation_id=data.get("primary_simulation_id"),
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class ResolutionCriteria:
    criteria_id: str
    forecast_id: str
    label: str
    description: str
    resolution_date: str
    criteria_type: str = "manual"
    thresholds: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.criteria_id = _require_non_empty_string("criteria_id", self.criteria_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.label = _require_non_empty_string("label", self.label)
        self.description = _require_non_empty_string("description", self.description)
        self.resolution_date = _require_iso_date("resolution_date", self.resolution_date)
        self.criteria_type = _validate_supported_value(
            "criteria_type",
            _require_non_empty_string("criteria_type", self.criteria_type),
            SUPPORTED_RESOLUTION_CRITERIA_TYPES,
        )
        self.thresholds = _normalize_dict("thresholds", self.thresholds)
        self.notes = _normalize_string_list("notes", self.notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria_id": self.criteria_id,
            "forecast_id": self.forecast_id,
            "label": self.label,
            "description": self.description,
            "resolution_date": self.resolution_date,
            "criteria_type": self.criteria_type,
            "thresholds": dict(self.thresholds),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResolutionCriteria":
        return cls(
            criteria_id=data["criteria_id"],
            forecast_id=data["forecast_id"],
            label=data["label"],
            description=data["description"],
            resolution_date=data["resolution_date"],
            criteria_type=data.get("criteria_type", "manual"),
            thresholds=data.get("thresholds", {}),
            notes=data.get("notes", []),
        )


@dataclass
class EvidenceSourceEntry:
    source_id: str
    provider_id: str
    provider_kind: str
    kind: str
    title: str
    summary: str = ""
    citation_id: Optional[str] = None
    locator: Optional[str] = None
    timestamps: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    freshness: Dict[str, Any] = field(default_factory=dict)
    relevance: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)
    conflict_status: str = "none"
    conflict_markers: List[Dict[str, Any]] = field(default_factory=list)
    missing_evidence_markers: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source_id = _require_non_empty_string("source_id", self.source_id)
        self.provider_id = _require_non_empty_string("provider_id", self.provider_id)
        self.provider_kind = _validate_supported_value(
            "provider_kind",
            _normalize_provider_kind_alias(self.provider_kind),
            SUPPORTED_EVIDENCE_PROVIDER_KINDS,
        )
        self.kind = _validate_supported_value(
            "evidence entry kind",
            _require_non_empty_string("kind", self.kind),
            SUPPORTED_EVIDENCE_ENTRY_KINDS,
        )
        self.title = _require_non_empty_string("title", self.title)
        self.summary = _normalize_optional_string(self.summary) or ""
        self.citation_id = _normalize_optional_string(self.citation_id)
        self.locator = _normalize_optional_string(self.locator)
        self.timestamps = _normalize_dict("timestamps", self.timestamps)
        for key, value in list(self.timestamps.items()):
            if value is None:
                continue
            self.timestamps[key] = _require_iso_datetime(f"timestamps.{key}", value)
        self.provenance = _normalize_dict("provenance", self.provenance)
        self.freshness = self._normalize_measurement(
            "freshness",
            self.freshness,
            allowed_statuses=SUPPORTED_EVIDENCE_FRESHNESS_STATUSES,
            default_status="unknown",
        )
        self.relevance = self._normalize_measurement("relevance", self.relevance)
        self.quality = self._normalize_measurement("quality", self.quality)
        self.conflict_status = _validate_supported_value(
            "conflict_status",
            _require_non_empty_string("conflict_status", self.conflict_status),
            SUPPORTED_EVIDENCE_CONFLICT_STATUSES,
        )
        self.conflict_markers = _normalize_marker_list(
            "conflict_markers", self.conflict_markers
        )
        self.missing_evidence_markers = _normalize_marker_list(
            "missing_evidence_markers",
            self.missing_evidence_markers,
        )
        self.notes = _normalize_string_list("notes", self.notes)
        self.metadata = _normalize_dict("metadata", self.metadata)

    @staticmethod
    def _normalize_measurement(
        name: str,
        measurement: Any,
        *,
        allowed_statuses: Optional[set[str]] = None,
        default_status: str = "unknown",
    ) -> Dict[str, Any]:
        normalized = _normalize_dict(name, measurement)
        if allowed_statuses is not None:
            normalized["status"] = _validate_supported_value(
                f"{name}.status",
                _normalize_optional_string(normalized.get("status")) or default_status,
                allowed_statuses,
            )
        elif "status" in normalized and normalized["status"] is not None:
            normalized["status"] = _normalize_optional_string(normalized["status"])
        if "score" in normalized:
            normalized["score"] = _normalize_score(f"{name}.score", normalized["score"])
        return normalized

    @property
    def freshness_score(self) -> Optional[float]:
        return _normalize_score("freshness.score", self.freshness.get("score"))

    @property
    def relevance_score(self) -> Optional[float]:
        return _normalize_score("relevance.score", self.relevance.get("score"))

    @property
    def quality_score(self) -> Optional[float]:
        return _normalize_score("quality.score", self.quality.get("score"))

    @property
    def is_missing(self) -> bool:
        return bool(self.missing_evidence_markers) or self.kind == "missing_evidence"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "entry_id": self.source_id,
            "source_type": self.kind,
            "provider_id": self.provider_id,
            "provider_kind": self.provider_kind,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "citation_id": self.citation_id,
            "locator": self.locator,
            "timestamps": dict(self.timestamps),
            "captured_at": self.timestamps.get("captured_at"),
            "observed_at": self.timestamps.get("observed_at"),
            "published_at": self.timestamps.get("published_at"),
            "provenance": dict(self.provenance),
            "freshness": dict(self.freshness),
            "relevance": dict(self.relevance),
            "quality": dict(self.quality),
            "quality_score": self.quality.get("score"),
            "conflict_status": self.conflict_status,
            "conflict_markers": [dict(item) for item in self.conflict_markers],
            "missing_evidence_markers": [dict(item) for item in self.missing_evidence_markers],
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceSourceEntry":
        path = _normalize_optional_string(data.get("path"))
        locator = _normalize_optional_string(data.get("locator")) or path
        source_type = _normalize_optional_string(data.get("source_type"))
        title = (
            data.get("title")
            or data.get("label")
            or data.get("artifact_id")
            or locator
            or data.get("kind")
            or source_type
            or "Evidence source"
        )
        source_id = (
            data.get("source_id")
            or data.get("entry_id")
            or data.get("artifact_id")
            or data.get("citation_id")
            or (
                "source-"
                + "-".join(
                    (
                        _normalize_optional_string(title) or "entry",
                        _normalize_optional_string(locator) or "locator",
                        _normalize_optional_string(data.get("kind")) or "kind",
                    )
                ).lower().replace(" ", "-").replace("/", "-").replace("#", "-")
            )
        )
        provider_kind = data.get("provider_kind")
        if provider_kind is not None:
            provider_kind = _normalize_provider_kind_alias(provider_kind)
        if provider_kind is None and source_type in {"live_external", "external_live"}:
            provider_kind = "external_live"
        elif provider_kind is None and data.get("kind") in {
            "external_document",
        }:
            provider_kind = "external_live"
        elif provider_kind is None and data.get("kind") == "manual_note":
            provider_kind = "manual"
        elif provider_kind is None:
            provider_kind = "uploaded_local_artifact"
        provider_id = data.get("provider_id") or (
            "legacy_artifact_list" if data.get("artifact_id") else provider_kind
        )
        timestamps = data.get("timestamps")
        if not isinstance(timestamps, dict):
            timestamps = {}
        if data.get("created_at") and "captured_at" not in timestamps:
            timestamps["captured_at"] = data["created_at"]
        if data.get("captured_at") and "captured_at" not in timestamps:
            timestamps["captured_at"] = data["captured_at"]
        if data.get("observed_at") and "observed_at" not in timestamps:
            timestamps["observed_at"] = data["observed_at"]
        if data.get("published_at") and "published_at" not in timestamps:
            timestamps["published_at"] = data["published_at"]
        freshness = data.get("freshness") or {}
        if not freshness and data.get("freshness_score") is not None:
            freshness = {"score": data.get("freshness_score")}
        relevance = data.get("relevance") or {}
        if not relevance and data.get("relevance_score") is not None:
            relevance = {"score": data.get("relevance_score")}
        quality = data.get("quality") or {}
        if not quality and data.get("quality_score") is not None:
            quality = {"score": data.get("quality_score")}
        kind = data.get("kind") or source_type or "uploaded_source"
        return cls(
            source_id=source_id,
            provider_id=provider_id,
            provider_kind=provider_kind,
            kind=kind,
            title=title,
            summary=data.get("summary", ""),
            citation_id=data.get("citation_id"),
            locator=locator,
            timestamps=timestamps,
            provenance=data.get("provenance", {}),
            freshness=freshness,
            relevance=relevance,
            quality=quality,
            conflict_status=data.get("conflict_status", "none"),
            conflict_markers=data.get("conflict_markers", []),
            missing_evidence_markers=data.get("missing_evidence_markers", []),
            notes=data.get("notes", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EvidenceBundle:
    bundle_id: str
    forecast_id: str
    title: str
    summary: str
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    source_entries: List[EvidenceSourceEntry] = field(default_factory=list)
    provider_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    timestamps: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    citation_index: Dict[str, Any] = field(default_factory=dict)
    freshness_summary: Dict[str, Any] = field(default_factory=dict)
    relevance_summary: Dict[str, Any] = field(default_factory=dict)
    quality_summary: Dict[str, Any] = field(default_factory=dict)
    conflict_summary: Dict[str, Any] = field(default_factory=dict)
    conflict_markers: List[Dict[str, Any]] = field(default_factory=list)
    missing_evidence_markers: List[Dict[str, Any]] = field(default_factory=list)
    uncertainty_summary: Dict[str, Any] = field(default_factory=dict)
    uncertainty_labels: List[str] = field(default_factory=list)
    retrieval_quality: Dict[str, Any] = field(default_factory=dict)
    question_ids: List[str] = field(default_factory=list)
    prediction_entry_ids: List[str] = field(default_factory=list)
    status: str = "draft"
    boundary_note: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self) -> None:
        self.bundle_id = _require_non_empty_string("bundle_id", self.bundle_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.title = _require_non_empty_string("title", self.title)
        self.summary = _require_non_empty_string("summary", self.summary)
        self.artifacts = _normalize_list_of_dicts("artifacts", self.artifacts)
        self.source_entries = [
            item
            if isinstance(item, EvidenceSourceEntry)
            else EvidenceSourceEntry.from_dict(item)
            for item in self.source_entries
        ]
        if not self.source_entries and self.artifacts:
            self.source_entries = [
                EvidenceSourceEntry.from_dict(item) for item in self.artifacts
            ]
        self.provider_snapshots = _normalize_provider_status_list(
            self.provider_snapshots
        )
        self.timestamps = _normalize_dict("timestamps", self.timestamps)
        for key, value in list(self.timestamps.items()):
            if value is None:
                self.timestamps.pop(key, None)
                continue
            self.timestamps[key] = _normalize_optional_iso_temporal(
                f"timestamps.{key}",
                value,
            )
        self.provenance = _normalize_dict("provenance", self.provenance)
        self.citation_index = _normalize_dict("citation_index", self.citation_index)
        self.freshness_summary = _normalize_dict("freshness_summary", self.freshness_summary)
        self.relevance_summary = _normalize_dict("relevance_summary", self.relevance_summary)
        self.quality_summary = _normalize_dict("quality_summary", self.quality_summary)
        self.conflict_summary = _normalize_dict("conflict_summary", self.conflict_summary)
        self.conflict_markers = _normalize_marker_list(
            "conflict_markers",
            self.conflict_markers,
        )
        self.missing_evidence_markers = _normalize_marker_list(
            "missing_evidence_markers",
            self.missing_evidence_markers,
        )
        self.uncertainty_summary = _normalize_dict(
            "uncertainty_summary", self.uncertainty_summary
        )
        self.uncertainty_labels = _normalize_label_list(
            "uncertainty_labels",
            self.uncertainty_labels,
            SUPPORTED_EVIDENCE_UNCERTAINTY_LABELS,
        )
        self.retrieval_quality = _normalize_dict("retrieval_quality", self.retrieval_quality)
        self.question_ids = _normalize_string_list("question_ids", self.question_ids)
        self.prediction_entry_ids = _normalize_string_list(
            "prediction_entry_ids",
            self.prediction_entry_ids,
        )
        if not self.question_ids:
            self.question_ids = [self.forecast_id]
        self.status = _validate_supported_value(
            "evidence bundle status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_EVIDENCE_BUNDLE_STATUSES,
        )
        self.boundary_note = _require_non_empty_string("boundary_note", self.boundary_note)
        self.created_at = _require_iso_datetime("created_at", self.created_at)
        self._finalize_derived_fields()

    @property
    def entries(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.source_entries]

    @property
    def providers(self) -> List[Dict[str, Any]]:
        return [dict(item) for item in self.provider_snapshots]

    @property
    def question_links(self) -> List[str]:
        return list(self.question_ids)

    @property
    def prediction_links(self) -> List[str]:
        return list(self.prediction_entry_ids)

    def _finalize_derived_fields(self) -> None:
        if not self.artifacts:
            self.artifacts = self._derive_artifacts()
        self.timestamps = self._derive_bundle_timestamps()
        self.provenance = self._derive_bundle_provenance()
        self.citation_index = self._derive_citation_index()
        self.freshness_summary = self._derive_score_summary(
            self.freshness_summary,
            attribute_name="freshness_score",
            status_key="freshness",
            stale_status="stale",
        )
        self.relevance_summary = self._derive_score_summary(
            self.relevance_summary,
            attribute_name="relevance_score",
            status_key="relevance",
        )
        self.quality_summary = self._derive_score_summary(
            self.quality_summary,
            attribute_name="quality_score",
            status_key="quality",
        )
        self.quality_summary.setdefault(
            "conflicting_entry_count",
            len(
                [
                    entry
                    for entry in self.source_entries
                    if entry.conflict_status in {"contradicts", "mixed"}
                    or entry.conflict_markers
                ]
            ),
        )
        self.quality_summary.setdefault(
            "missing_evidence_count",
            len(
                [
                    entry
                    for entry in self.source_entries
                    if entry.is_missing
                    or entry.conflict_status == "missing"
                ]
            ),
        )
        self.quality_summary.setdefault(
            "stale_entry_count",
            self.freshness_summary.get("stale_entry_count", 0),
        )
        self.conflict_markers = self._derive_conflict_markers()
        self.conflict_summary = self._derive_conflict_summary()
        self.uncertainty_summary = self._derive_uncertainty_summary()
        self.uncertainty_labels = self._derive_uncertainty_labels()
        self.retrieval_quality = self._derive_retrieval_quality()
        if self.status == "draft":
            if self.uncertainty_summary.get("status") == "degraded":
                self.status = "degraded"
            elif self.source_entries:
                self.status = "ready"
            else:
                self.status = "unavailable"

    def _derive_artifacts(self) -> List[Dict[str, Any]]:
        derived_artifacts: List[Dict[str, Any]] = []
        for entry in self.source_entries:
            derived_artifacts.append(
                {
                    "artifact_id": entry.source_id,
                    "kind": entry.kind,
                    "title": entry.title,
                    "path": entry.locator,
                    "provider_id": entry.provider_id,
                    "provider_kind": entry.provider_kind,
                    "citation_id": entry.citation_id,
                }
            )
        return derived_artifacts

    def _derive_bundle_timestamps(self) -> Dict[str, Any]:
        timestamps = dict(self.timestamps)
        captured = [
            entry.timestamps.get("captured_at")
            for entry in self.source_entries
            if _normalize_optional_string(entry.timestamps.get("captured_at"))
        ]
        observed = [
            entry.timestamps.get("observed_at")
            for entry in self.source_entries
            if _normalize_optional_string(entry.timestamps.get("observed_at"))
        ]
        published = [
            entry.timestamps.get("published_at")
            for entry in self.source_entries
            if _normalize_optional_string(entry.timestamps.get("published_at"))
        ]
        provider_collected = [
            provider.get("collected_at")
            for provider in self.provider_snapshots
            if _normalize_optional_string(provider.get("collected_at"))
        ]
        captured = _sorted_iso_temporals(captured)
        observed = _sorted_iso_temporals(observed)
        published = _sorted_iso_temporals(published)
        provider_collected = _sorted_iso_temporals(provider_collected)
        timestamps.setdefault("created_at", self.created_at)
        if provider_collected:
            timestamps.setdefault("collected_at", max(provider_collected))
        if captured:
            timestamps.setdefault("latest_captured_at", max(captured))
            timestamps.setdefault("earliest_captured_at", min(captured))
            timestamps.setdefault("reference_time", max(captured))
        if observed:
            timestamps.setdefault("latest_observed_at", max(observed))
            timestamps.setdefault("earliest_observed_at", min(observed))
        if published:
            timestamps.setdefault("latest_published_at", max(published))
            timestamps.setdefault("earliest_published_at", min(published))
        return timestamps

    def _derive_bundle_provenance(self) -> Dict[str, Any]:
        provenance = dict(self.provenance)
        provider_ids = sorted(
            {
                provider.get("provider_id")
                for provider in self.provider_snapshots
                if _normalize_optional_string(provider.get("provider_id"))
            }
            | {entry.provider_id for entry in self.source_entries}
        )
        provider_kinds = sorted(
            {
                provider.get("provider_kind")
                for provider in self.provider_snapshots
                if _normalize_optional_string(provider.get("provider_kind"))
            }
            | {entry.provider_kind for entry in self.source_entries}
        )
        artifact_ids = [
            item.get("artifact_id")
            for item in self.artifacts
            if _normalize_optional_string(item.get("artifact_id"))
        ]
        source_entry_ids = [entry.source_id for entry in self.source_entries]
        citation_ids = [
            entry.citation_id
            for entry in self.source_entries
            if _normalize_optional_string(entry.citation_id)
        ]
        provenance.setdefault("forecast_id", self.forecast_id)
        provenance.setdefault("bundle_id", self.bundle_id)
        provenance.setdefault("provider_ids", provider_ids)
        provenance.setdefault("provider_kinds", provider_kinds)
        provenance.setdefault("artifact_ids", artifact_ids)
        provenance.setdefault("source_entry_ids", source_entry_ids)
        provenance.setdefault("citation_ids", citation_ids)
        provenance.setdefault("entry_count", len(self.source_entries))
        provenance.setdefault(
            "boundary_note",
            self.boundary_note,
        )
        provenance.setdefault(
            "has_live_external_provider",
            any(kind in {"live_external", "external_live"} for kind in provider_kinds),
        )
        return provenance

    def _derive_citation_index(self) -> Dict[str, Any]:
        all_citations: List[Dict[str, Any]] = []
        by_group: Dict[str, List[Dict[str, Any]]] = {}
        provider_group_aliases = {
            "uploaded_local": "uploaded_local_artifact",
            "external_live": "live_external",
        }
        for entry in self.source_entries:
            if not entry.citation_id:
                continue
            if entry.kind in {"uploaded_source", "uploaded_local_artifact"}:
                group = "source"
            elif entry.kind in {"graph_provenance", "graph_summary"}:
                group = "graph"
            elif entry.kind == "external_document":
                group = "external"
            elif entry.kind == "manual_note":
                group = "manual"
            elif entry.kind == "missing_evidence":
                group = "missing"
            else:
                group = "artifact"
            citation_payload = {
                "citation_id": entry.citation_id,
                "source_id": entry.source_id,
                "kind": entry.kind,
                "provider_id": entry.provider_id,
                "provider_kind": entry.provider_kind,
                "title": entry.title,
                "locator": entry.locator,
            }
            all_citations.append(citation_payload)
            by_group.setdefault(group, []).append(citation_payload)
            by_group.setdefault(entry.provider_kind, []).append(citation_payload)
            alias_group = provider_group_aliases.get(entry.provider_kind)
            if alias_group is not None:
                by_group.setdefault(alias_group, []).append(citation_payload)
        if self.citation_index:
            normalized_index = dict(self.citation_index)
            normalized_index.setdefault("all", all_citations)
            for key, value in by_group.items():
                normalized_index.setdefault(key, value)
            return normalized_index
        return {
            "all": all_citations,
            **by_group,
        }

    def _derive_score_summary(
        self,
        current_summary: Dict[str, Any],
        *,
        attribute_name: str,
        status_key: str,
        stale_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        scores = [
            getattr(entry, attribute_name)
            for entry in self.source_entries
            if getattr(entry, attribute_name) is not None
        ]
        statuses = [
            _normalize_optional_string(getattr(entry, status_key).get("status"))
            for entry in self.source_entries
            if isinstance(getattr(entry, status_key), dict)
        ]
        summary = dict(current_summary)
        summary.setdefault("entry_count", len(self.source_entries))
        summary.setdefault(
            "average_score",
            round(sum(scores) / len(scores), 4) if scores else None,
        )
        if stale_status is not None:
            summary.setdefault(
                "stale_entry_count",
                len([status for status in statuses if status == stale_status]),
            )
            summary.setdefault("stale_entry_count", summary.get("stale_entry_count", 0))
        return summary

    def _derive_conflict_summary(self) -> Dict[str, Any]:
        summary = dict(self.conflict_summary)
        conflict_entries = [
            entry
            for entry in self.source_entries
            if entry.conflict_status in {"contradicts", "mixed"}
            or entry.conflict_markers
        ]
        summary.setdefault(
            "status",
            "conflicting" if conflict_entries else "clear",
        )
        summary.setdefault("conflict_entry_count", len(conflict_entries))
        summary.setdefault(
            "conflict_marker_count",
            len(self.conflict_markers),
        )
        return summary

    def _derive_conflict_markers(self) -> List[Dict[str, Any]]:
        markers = list(self.conflict_markers)
        for entry in self.source_entries:
            markers.extend(entry.conflict_markers)
            if entry.conflict_status in {"contradicts", "mixed"} and not entry.conflict_markers:
                markers.append(
                    {
                        "code": entry.conflict_status,
                        "summary": entry.summary or entry.title,
                        "entry_id": entry.source_id,
                        "provider_id": entry.provider_id,
                    }
                )
        return _dedupe_marker_dicts(_normalize_marker_list("conflict_markers", markers))

    def _derive_uncertainty_summary(self) -> Dict[str, Any]:
        summary = dict(self.uncertainty_summary)
        causes = list(summary.get("causes") or [])
        if self.freshness_summary.get("stale_entry_count", 0) > 0:
            causes.append("stale_evidence")
        evidence_count_for_density = len(self.artifacts) or len(self.source_entries)
        if evidence_count_for_density < 2:
            causes.append("sparse_evidence")
        if self.conflict_summary.get("conflict_entry_count", 0) > 0:
            causes.append("conflicting_evidence")
        if self.missing_evidence_markers or any(entry.is_missing for entry in self.source_entries):
            causes.append("missing_evidence")
        if any(
            (_normalize_optional_string(provider.get("status")) or "") == "unavailable"
            for provider in self.provider_snapshots
        ):
            causes.append("provider_unavailable")
        average_relevance = self.relevance_summary.get("average_score")
        if average_relevance is None or average_relevance < 0.5:
            causes.append("relevance_uncertain")
        deduped_causes: List[str] = []
        for cause in causes:
            normalized = _normalize_optional_string(cause)
            if normalized and normalized in SUPPORTED_EVIDENCE_UNCERTAINTY_CAUSES and normalized not in deduped_causes:
                deduped_causes.append(normalized)
        summary["causes"] = deduped_causes
        drivers = []
        for cause in deduped_causes:
            if cause.endswith("_evidence"):
                drivers.append(cause.replace("_evidence", ""))
            elif cause == "provider_unavailable":
                drivers.append("missing")
            elif cause == "relevance_uncertain":
                drivers.append("low_relevance")
            else:
                drivers.append(cause)
        deduped_drivers: List[str] = []
        for driver in drivers:
            if driver not in deduped_drivers:
                deduped_drivers.append(driver)
        summary["drivers"] = deduped_drivers
        labels = []
        for cause in deduped_causes:
            if cause in SUPPORTED_EVIDENCE_UNCERTAINTY_LABELS:
                labels.append(cause)
        summary["labels"] = labels
        summary.setdefault(
            "status",
            "degraded" if deduped_drivers else "bounded",
        )
        return summary

    def _derive_uncertainty_labels(self) -> List[str]:
        labels = list(self.uncertainty_labels)
        for label in self.uncertainty_summary.get("labels", []):
            normalized = _normalize_optional_string(label)
            if (
                normalized
                and normalized in SUPPORTED_EVIDENCE_UNCERTAINTY_LABELS
                and normalized not in labels
            ):
                labels.append(normalized)
        return labels

    def _derive_retrieval_quality(self) -> Dict[str, Any]:
        summary = dict(self.retrieval_quality)
        provider_kinds = sorted(
            {
                provider.get("provider_kind")
                for provider in self.provider_snapshots
                if _normalize_optional_string(provider.get("provider_kind"))
            }
            | {entry.provider_kind for entry in self.source_entries}
        )
        has_uploaded_local = any(
            kind in {"uploaded_local", "uploaded_local_artifact"}
            for kind in provider_kinds
        )
        has_live_external = "live_external" in provider_kinds or "external_live" in provider_kinds
        any_ready_external = any(
            provider.get("provider_kind") in {"live_external", "external_live"}
            and provider.get("status") in {"ready", "partial"}
            for provider in self.provider_snapshots
        )
        if not self.source_entries:
            status = "unavailable"
        elif has_live_external and any_ready_external and has_uploaded_local:
            status = "mixed_provider_unverified"
        elif has_live_external and any_ready_external:
            status = "external_live_unverified"
        elif has_live_external:
            status = "local_only_external_unavailable"
        else:
            status = "bounded_local_only"
        summary.setdefault("status", status)
        summary.setdefault("provider_kinds", provider_kinds)
        summary.setdefault("entry_count", len(self.source_entries))
        summary.setdefault(
            "notes",
            [
                "Evidence quality scores are heuristic bundle diagnostics, not truth guarantees.",
                "Uploaded/local evidence remains bounded to persisted project and simulation artifacts unless a live external provider actually returns entries.",
            ],
        )
        return summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "forecast_id": self.forecast_id,
            "title": self.title,
            "summary": self.summary,
            "artifacts": [dict(item) for item in self.artifacts],
            "source_entries": [item.to_dict() for item in self.source_entries],
            "entries": [item.to_dict() for item in self.source_entries],
            "provider_snapshots": [dict(item) for item in self.provider_snapshots],
            "providers": [dict(item) for item in self.provider_snapshots],
            "timestamps": dict(self.timestamps),
            "provenance": dict(self.provenance),
            "citation_index": dict(self.citation_index),
            "freshness_summary": dict(self.freshness_summary),
            "relevance_summary": dict(self.relevance_summary),
            "quality_summary": dict(self.quality_summary),
            "conflict_summary": dict(self.conflict_summary),
            "conflict_markers": [dict(item) for item in self.conflict_markers],
            "missing_evidence_markers": [dict(item) for item in self.missing_evidence_markers],
            "uncertainty_summary": dict(self.uncertainty_summary),
            "uncertainty_labels": list(self.uncertainty_labels),
            "retrieval_quality": dict(self.retrieval_quality),
            "question_ids": list(self.question_ids),
            "question_links": list(self.question_ids),
            "prediction_entry_ids": list(self.prediction_entry_ids),
            "prediction_links": list(self.prediction_entry_ids),
            "references": {
                "forecast_id": self.forecast_id,
                "question_ids": list(self.question_ids),
                "prediction_entry_ids": list(self.prediction_entry_ids),
            },
            "status": self.status,
            "boundary_note": self.boundary_note,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceBundle":
        return cls(
            bundle_id=data["bundle_id"],
            forecast_id=data["forecast_id"],
            title=data["title"],
            summary=data["summary"],
            artifacts=data.get("artifacts", []),
            source_entries=data.get("source_entries", data.get("entries", [])),
            provider_snapshots=data.get("provider_snapshots", data.get("providers", [])),
            timestamps=data.get("timestamps", {}),
            provenance=data.get("provenance", {}),
            citation_index=data.get("citation_index", {}),
            freshness_summary=data.get("freshness_summary", {}),
            relevance_summary=data.get("relevance_summary", {}),
            quality_summary=data.get("quality_summary", {}),
            conflict_summary=data.get("conflict_summary", {}),
            conflict_markers=data.get("conflict_markers", []),
            missing_evidence_markers=data.get("missing_evidence_markers", []),
            uncertainty_summary=data.get("uncertainty_summary", {}),
            uncertainty_labels=data.get("uncertainty_labels", []),
            retrieval_quality=data.get("retrieval_quality", {}),
            question_ids=data.get("question_ids", data.get("question_links", [])),
            prediction_entry_ids=data.get(
                "prediction_entry_ids",
                data.get("prediction_links", []),
            ),
            status=data.get("status", "draft"),
            boundary_note=(
                data.get("boundary_note")
                or "Evidence remains bounded to the providers listed in this bundle."
            ),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class ForecastWorker:
    worker_id: str
    forecast_id: str
    kind: str
    label: str
    status: str = "registered"
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    primary_output_semantics: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.worker_id = _require_non_empty_string("worker_id", self.worker_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.kind = _validate_supported_value(
            "worker kind",
            _require_non_empty_string("kind", self.kind),
            SUPPORTED_FORECAST_WORKER_KINDS,
        )
        self.label = _require_non_empty_string("label", self.label)
        self.status = _validate_supported_value(
            "worker status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_FORECAST_WORKER_STATUSES,
        )
        self.description = _normalize_optional_string(self.description) or ""
        self.capabilities = _normalize_string_list("capabilities", self.capabilities)
        if self.kind == "simulation":
            default_semantics = "scenario_evidence"
        elif self.kind in {"retrieval", "retrieval_synthesis"}:
            default_semantics = "retrieval_evidence"
        elif self.kind in {"base_rate", "reference_class"}:
            default_semantics = "forecast_probability"
        else:
            default_semantics = "qualitative_judgment"
        self.primary_output_semantics = _validate_supported_value(
            "worker output semantics",
            _normalize_optional_string(self.primary_output_semantics) or default_semantics,
            SUPPORTED_WORKER_OUTPUT_SEMANTICS,
        )
        if self.kind == "simulation" and self.primary_output_semantics == "forecast_probability":
            raise ValueError(
                "Simulation workers cannot declare forecast_probability semantics"
            )
        self.metadata = _normalize_dict("metadata", self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "forecast_id": self.forecast_id,
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "primary_output_semantics": self.primary_output_semantics,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastWorker":
        return cls(
            worker_id=data["worker_id"],
            forecast_id=data["forecast_id"],
            kind=data["kind"],
            label=data["label"],
            status=data.get("status", "registered"),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            primary_output_semantics=data.get("primary_output_semantics", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SimulationWorkerContract:
    worker_id: str
    forecast_id: str
    simulation_id: Optional[str] = None
    prepare_artifact_paths: List[str] = field(default_factory=list)
    ensemble_ids: List[str] = field(default_factory=list)
    scenario_diversity_strategy: str = "weighted_cycle"
    probability_interpretation: str = "do_not_treat_as_real_world_probability"
    notes: List[str] = field(default_factory=list)
    schema_version: str = SIMULATION_WORKER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        self.worker_id = _require_non_empty_string("worker_id", self.worker_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.simulation_id = _normalize_optional_string(self.simulation_id)
        self.prepare_artifact_paths = _normalize_string_list(
            "prepare_artifact_paths", self.prepare_artifact_paths
        )
        self.ensemble_ids = _normalize_string_list("ensemble_ids", self.ensemble_ids)
        self.scenario_diversity_strategy = _require_non_empty_string(
            "scenario_diversity_strategy", self.scenario_diversity_strategy
        )
        self.probability_interpretation = _validate_supported_value(
            "probability interpretation",
            _require_non_empty_string(
                "probability_interpretation", self.probability_interpretation
            ),
            SUPPORTED_SIMULATION_PROBABILITY_INTERPRETATIONS,
        )
        self.notes = _normalize_string_list("notes", self.notes)
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "forecast_id": self.forecast_id,
            "simulation_id": self.simulation_id,
            "prepare_artifact_paths": list(self.prepare_artifact_paths),
            "ensemble_ids": list(self.ensemble_ids),
            "scenario_diversity_strategy": self.scenario_diversity_strategy,
            "probability_interpretation": self.probability_interpretation,
            "notes": list(self.notes),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationWorkerContract":
        return cls(
            worker_id=data["worker_id"],
            forecast_id=data["forecast_id"],
            simulation_id=data.get("simulation_id"),
            prepare_artifact_paths=data.get("prepare_artifact_paths", []),
            ensemble_ids=data.get("ensemble_ids", []),
            scenario_diversity_strategy=data.get(
                "scenario_diversity_strategy", "weighted_cycle"
            ),
            probability_interpretation=data.get(
                "probability_interpretation",
                "do_not_treat_as_real_world_probability",
            ),
            notes=data.get("notes", []),
            schema_version=data.get(
                "schema_version", SIMULATION_WORKER_CONTRACT_VERSION
            ),
        )


@dataclass
class ForecastSimulationScope:
    forecast_id: str
    simulation_id: Optional[str] = None
    prepare_artifact_paths: List[str] = field(default_factory=list)
    ensemble_ids: List[str] = field(default_factory=list)
    run_ids: List[str] = field(default_factory=list)
    latest_ensemble_id: Optional[str] = None
    latest_run_id: Optional[str] = None
    prepare_status: str = "unprepared"
    prepare_task_id: Optional[str] = None
    last_attached_stage: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: str = FORECAST_SIMULATION_SCOPE_VERSION

    def __post_init__(self) -> None:
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.simulation_id = _normalize_optional_string(self.simulation_id)
        self.prepare_artifact_paths = _normalize_string_list(
            "prepare_artifact_paths", self.prepare_artifact_paths
        )
        self.ensemble_ids = _normalize_string_list("ensemble_ids", self.ensemble_ids)
        self.run_ids = _normalize_string_list("run_ids", self.run_ids)
        self.latest_ensemble_id = _normalize_optional_string(self.latest_ensemble_id)
        self.latest_run_id = _normalize_optional_string(self.latest_run_id)
        self.prepare_status = _validate_supported_value(
            "prepare_status",
            _require_non_empty_string("prepare_status", self.prepare_status),
            SUPPORTED_SIMULATION_SCOPE_PREPARE_STATUSES,
        )
        self.prepare_task_id = _normalize_optional_string(self.prepare_task_id)
        self.last_attached_stage = _normalize_optional_string(self.last_attached_stage)
        self.updated_at = _require_iso_datetime("updated_at", self.updated_at)
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)
        if self.latest_ensemble_id and self.latest_ensemble_id not in self.ensemble_ids:
            self.ensemble_ids.append(self.latest_ensemble_id)
        if self.latest_run_id and self.latest_run_id not in self.run_ids:
            self.run_ids.append(self.latest_run_id)
        if self.prepare_artifact_paths and self.prepare_status == "unprepared":
            self.prepare_status = "ready"

    @property
    def status(self) -> str:
        return "linked" if self.simulation_id else "unlinked"

    @property
    def scope_level(self) -> str:
        if self.latest_run_id or self.run_ids:
            return "run"
        if self.latest_ensemble_id or self.ensemble_ids:
            return "ensemble"
        if self.simulation_id:
            return "simulation"
        return "unlinked"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "simulation_id": self.simulation_id,
            "prepare_artifact_paths": list(self.prepare_artifact_paths),
            "ensemble_ids": list(self.ensemble_ids),
            "run_ids": list(self.run_ids),
            "latest_ensemble_id": self.latest_ensemble_id,
            "latest_run_id": self.latest_run_id,
            "prepare_status": self.prepare_status,
            "prepare_task_id": self.prepare_task_id,
            "last_attached_stage": self.last_attached_stage,
            "updated_at": self.updated_at,
            "status": self.status,
            "scope_level": self.scope_level,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastSimulationScope":
        return cls(
            forecast_id=data["forecast_id"],
            simulation_id=data.get("simulation_id"),
            prepare_artifact_paths=data.get("prepare_artifact_paths", []),
            ensemble_ids=data.get("ensemble_ids", []),
            run_ids=data.get("run_ids", []),
            latest_ensemble_id=data.get("latest_ensemble_id"),
            latest_run_id=data.get("latest_run_id"),
            prepare_status=data.get("prepare_status", "unprepared"),
            prepare_task_id=data.get("prepare_task_id"),
            last_attached_stage=data.get("last_attached_stage"),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            schema_version=data.get(
                "schema_version", FORECAST_SIMULATION_SCOPE_VERSION
            ),
        )


@dataclass
class ForecastResolutionRecord:
    forecast_id: str
    status: str = "pending"
    resolved_at: Optional[str] = None
    resolution_note: str = ""
    evidence_bundle_ids: List[str] = field(default_factory=list)
    prediction_entry_ids: List[str] = field(default_factory=list)
    revision_entry_ids: List[str] = field(default_factory=list)
    worker_output_ids: List[str] = field(default_factory=list)
    schema_version: str = FORECAST_RESOLUTION_RECORD_VERSION

    def __post_init__(self) -> None:
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.status = _validate_supported_value(
            "resolution status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_PREDICTION_RESOLUTION_STATES,
        )
        self.resolved_at = (
            _require_iso_datetime("resolved_at", self.resolved_at)
            if self.resolved_at is not None
            else None
        )
        self.resolution_note = str(self.resolution_note or "").strip()
        self.evidence_bundle_ids = _normalize_string_list(
            "evidence_bundle_ids", self.evidence_bundle_ids
        )
        self.prediction_entry_ids = _normalize_string_list(
            "prediction_entry_ids", self.prediction_entry_ids
        )
        self.revision_entry_ids = _normalize_string_list(
            "revision_entry_ids", self.revision_entry_ids
        )
        self.worker_output_ids = _normalize_string_list(
            "worker_output_ids", self.worker_output_ids
        )
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "status": self.status,
            "resolved_at": self.resolved_at,
            "resolution_note": self.resolution_note,
            "evidence_bundle_ids": list(self.evidence_bundle_ids),
            "prediction_entry_ids": list(self.prediction_entry_ids),
            "revision_entry_ids": list(self.revision_entry_ids),
            "worker_output_ids": list(self.worker_output_ids),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastResolutionRecord":
        return cls(
            forecast_id=data["forecast_id"],
            status=data.get("status", "pending"),
            resolved_at=data.get("resolved_at"),
            resolution_note=data.get("resolution_note", ""),
            evidence_bundle_ids=data.get("evidence_bundle_ids", []),
            prediction_entry_ids=data.get("prediction_entry_ids", []),
            revision_entry_ids=data.get("revision_entry_ids", []),
            worker_output_ids=data.get("worker_output_ids", []),
            schema_version=data.get(
                "schema_version", FORECAST_RESOLUTION_RECORD_VERSION
            ),
        )


@dataclass
class ForecastScoringEvent:
    scoring_event_id: str
    forecast_id: str
    status: str = "pending"
    scoring_method: Optional[str] = None
    score_value: Optional[float] = None
    recorded_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: List[str] = field(default_factory=list)
    schema_version: str = FORECAST_SCORING_EVENT_VERSION

    def __post_init__(self) -> None:
        self.scoring_event_id = _require_non_empty_string(
            "scoring_event_id", self.scoring_event_id
        )
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.status = _validate_supported_value(
            "scoring status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_SCORING_EVENT_STATUSES,
        )
        self.scoring_method = _normalize_optional_string(self.scoring_method)
        if self.score_value is not None:
            self.score_value = float(self.score_value)
        self.recorded_at = _require_iso_datetime("recorded_at", self.recorded_at)
        self.notes = _normalize_string_list("notes", self.notes)
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scoring_event_id": self.scoring_event_id,
            "forecast_id": self.forecast_id,
            "status": self.status,
            "scoring_method": self.scoring_method,
            "score_value": self.score_value,
            "recorded_at": self.recorded_at,
            "notes": list(self.notes),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastScoringEvent":
        return cls(
            scoring_event_id=data["scoring_event_id"],
            forecast_id=data["forecast_id"],
            status=data.get("status", "pending"),
            scoring_method=data.get("scoring_method"),
            score_value=data.get("score_value"),
            recorded_at=data.get("recorded_at", datetime.now().isoformat()),
            notes=data.get("notes", []),
            schema_version=data.get(
                "schema_version", FORECAST_SCORING_EVENT_VERSION
            ),
        )


@dataclass
class ForecastLifecycleMetadata:
    forecast_id: str
    current_stage: str = "forecast_workspace"
    stage_sequence: List[str] = field(
        default_factory=lambda: list(CANONICAL_FORECAST_STAGE_SEQUENCE)
    )
    latest_answer_id: Optional[str] = None
    resolution_record_status: str = "pending"
    scoring_event_count: int = 0
    simulation_scope_status: str = "unlinked"
    last_simulation_id: Optional[str] = None
    last_ensemble_id: Optional[str] = None
    last_run_id: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: str = FORECAST_LIFECYCLE_METADATA_VERSION

    def __post_init__(self) -> None:
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.current_stage = _validate_supported_value(
            "current_stage",
            _require_non_empty_string("current_stage", self.current_stage),
            SUPPORTED_WORKSPACE_LIFECYCLE_STAGES,
        )
        self.stage_sequence = _normalize_string_list(
            "stage_sequence", self.stage_sequence
        ) or list(CANONICAL_FORECAST_STAGE_SEQUENCE)
        self.latest_answer_id = _normalize_optional_string(self.latest_answer_id)
        self.resolution_record_status = _validate_supported_value(
            "resolution_record_status",
            _require_non_empty_string(
                "resolution_record_status", self.resolution_record_status
            ),
            SUPPORTED_PREDICTION_RESOLUTION_STATES,
        )
        self.scoring_event_count = max(int(self.scoring_event_count or 0), 0)
        self.simulation_scope_status = _validate_supported_value(
            "simulation_scope_status",
            _require_non_empty_string(
                "simulation_scope_status", self.simulation_scope_status
            ),
            SUPPORTED_SIMULATION_SCOPE_STATUSES,
        )
        self.last_simulation_id = _normalize_optional_string(self.last_simulation_id)
        self.last_ensemble_id = _normalize_optional_string(self.last_ensemble_id)
        self.last_run_id = _normalize_optional_string(self.last_run_id)
        self.updated_at = _require_iso_datetime("updated_at", self.updated_at)
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "current_stage": self.current_stage,
            "stage_sequence": list(self.stage_sequence),
            "latest_answer_id": self.latest_answer_id,
            "resolution_record_status": self.resolution_record_status,
            "scoring_event_count": self.scoring_event_count,
            "simulation_scope_status": self.simulation_scope_status,
            "last_simulation_id": self.last_simulation_id,
            "last_ensemble_id": self.last_ensemble_id,
            "last_run_id": self.last_run_id,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastLifecycleMetadata":
        return cls(
            forecast_id=data["forecast_id"],
            current_stage=data.get("current_stage", "forecast_workspace"),
            stage_sequence=data.get("stage_sequence", list(CANONICAL_FORECAST_STAGE_SEQUENCE)),
            latest_answer_id=data.get("latest_answer_id"),
            resolution_record_status=data.get("resolution_record_status", "pending"),
            scoring_event_count=data.get("scoring_event_count", 0),
            simulation_scope_status=data.get("simulation_scope_status", "unlinked"),
            last_simulation_id=data.get("last_simulation_id"),
            last_ensemble_id=data.get("last_ensemble_id"),
            last_run_id=data.get("last_run_id"),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            schema_version=data.get(
                "schema_version", FORECAST_LIFECYCLE_METADATA_VERSION
            ),
        )


@dataclass
class PredictionLedgerEntry:
    entry_id: str
    forecast_id: str
    worker_id: str
    recorded_at: str
    value_type: str
    value: Any
    value_semantics: str
    prediction: Any = None
    prediction_id: Optional[str] = None
    revision_number: int = 1
    entry_kind: str = "issue"
    revises_prediction_id: Optional[str] = None
    revises_entry_id: Optional[str] = None
    worker_output_ids: List[str] = field(default_factory=list)
    calibration_state: str = "uncalibrated"
    evaluation_case_ids: List[str] = field(default_factory=list)
    evaluation_summary: Dict[str, Any] = field(default_factory=dict)
    benchmark_summary: Dict[str, Any] = field(default_factory=dict)
    backtest_summary_ref: Optional[str] = None
    calibration_summary_ref: Optional[str] = None
    confidence_basis: Dict[str, Any] = field(default_factory=dict)
    evidence_bundle_ids: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    final_resolution_state: str = "pending"

    def __post_init__(self) -> None:
        self.entry_id = _require_non_empty_string("entry_id", self.entry_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.worker_id = _require_non_empty_string("worker_id", self.worker_id)
        self.recorded_at = _require_iso_datetime("recorded_at", self.recorded_at)
        self.value_type = _validate_supported_value(
            "prediction value type",
            _require_non_empty_string("value_type", self.value_type),
            SUPPORTED_PREDICTION_VALUE_TYPES,
        )
        self.value_semantics = _validate_supported_value(
            "prediction value semantics",
            _require_non_empty_string("value_semantics", self.value_semantics),
            SUPPORTED_PREDICTION_VALUE_SEMANTICS,
        )
        if self.prediction is None:
            self.prediction = self.value
        elif self.value is None:
            self.value = self.prediction
        self.prediction_id = _normalize_optional_string(self.prediction_id) or self.entry_id
        self.revision_number = int(self.revision_number)
        if self.revision_number < 1:
            raise ValueError("revision_number must be greater than or equal to 1")
        self.entry_kind = _validate_supported_value(
            "prediction ledger entry kind",
            _require_non_empty_string(
                "entry_kind",
                "revision" if (self.revises_prediction_id or self.revises_entry_id) else self.entry_kind,
            ),
            SUPPORTED_PREDICTION_LEDGER_ENTRY_KINDS,
        )
        normalized_revision_target = (
            _normalize_optional_string(self.revises_prediction_id)
            or _normalize_optional_string(self.revises_entry_id)
        )
        self.revises_prediction_id = normalized_revision_target
        self.revises_entry_id = normalized_revision_target
        if self.entry_kind == "issue" and self.revises_entry_id is not None:
            raise ValueError("issue entries cannot declare revises_entry_id")
        if self.entry_kind == "revision" and self.revises_entry_id is None:
            raise ValueError("revision entries must declare revises_entry_id")
        self.worker_output_ids = _normalize_string_list("worker_output_ids", self.worker_output_ids)
        self.calibration_state = _validate_supported_value(
            "calibration state",
            _require_non_empty_string("calibration_state", self.calibration_state),
            SUPPORTED_CALIBRATION_STATES,
        )
        self.evaluation_case_ids = _normalize_string_list(
            "evaluation_case_ids", self.evaluation_case_ids
        )
        self.evaluation_summary = _normalize_dict(
            "evaluation_summary", self.evaluation_summary
        )
        self.benchmark_summary = _normalize_dict(
            "benchmark_summary", self.benchmark_summary
        )
        self.backtest_summary_ref = _normalize_optional_string(self.backtest_summary_ref)
        self.calibration_summary_ref = _normalize_optional_string(
            self.calibration_summary_ref
        )
        self.confidence_basis = _normalize_dict("confidence_basis", self.confidence_basis)
        self.evidence_bundle_ids = _normalize_string_list(
            "evidence_bundle_ids", self.evidence_bundle_ids
        )
        self.notes = _normalize_string_list("notes", self.notes)
        self.metadata = _normalize_dict("metadata", self.metadata)
        self.final_resolution_state = _normalize_resolution_state(self.final_resolution_state)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "forecast_id": self.forecast_id,
            "worker_id": self.worker_id,
            "recorded_at": self.recorded_at,
            "issued_at": self.recorded_at,
            "value_type": self.value_type,
            "value": self.value,
            "prediction": self.prediction,
            "value_semantics": self.value_semantics,
            "prediction_id": self.prediction_id,
            "revision_number": self.revision_number,
            "entry_kind": self.entry_kind,
            "revises_prediction_id": self.revises_prediction_id,
            "revises_entry_id": self.revises_entry_id,
            "worker_output_ids": list(self.worker_output_ids),
            "calibration_state": self.calibration_state,
            "evaluation_case_ids": list(self.evaluation_case_ids),
            "evaluation_summary": dict(self.evaluation_summary),
            "benchmark_summary": dict(self.benchmark_summary),
            "backtest_summary_ref": self.backtest_summary_ref,
            "calibration_summary_ref": self.calibration_summary_ref,
            "confidence_basis": dict(self.confidence_basis),
            "evidence_bundle_ids": list(self.evidence_bundle_ids),
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
            "final_resolution_state": self.final_resolution_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionLedgerEntry":
        revises_prediction_id = data.get("revises_prediction_id", data.get("revises_entry_id"))
        return cls(
            entry_id=data["entry_id"],
            forecast_id=data["forecast_id"],
            worker_id=data["worker_id"],
            recorded_at=data.get("recorded_at", data.get("issued_at", datetime.now().isoformat())),
            value_type=data["value_type"],
            value=data.get("value"),
            value_semantics=data["value_semantics"],
            prediction=data.get("prediction", data.get("value")),
            prediction_id=data.get("prediction_id"),
            revision_number=data.get("revision_number", 1),
            entry_kind=data.get("entry_kind", "revision" if revises_prediction_id else "issue"),
            revises_prediction_id=revises_prediction_id,
            revises_entry_id=revises_prediction_id,
            worker_output_ids=data.get("worker_output_ids", []),
            calibration_state=data.get("calibration_state", "uncalibrated"),
            evaluation_case_ids=data.get("evaluation_case_ids", []),
            evaluation_summary=data.get("evaluation_summary", {}),
            benchmark_summary=data.get("benchmark_summary", {}),
            backtest_summary_ref=data.get("backtest_summary_ref"),
            calibration_summary_ref=data.get("calibration_summary_ref"),
            confidence_basis=data.get("confidence_basis", {}),
            evidence_bundle_ids=data.get("evidence_bundle_ids", []),
            notes=data.get("notes", []),
            metadata=data.get("metadata", {}),
            final_resolution_state=data.get("final_resolution_state", "pending"),
        )


@dataclass
class PredictionLedger:
    forecast_id: str
    entries: List[PredictionLedgerEntry] = field(default_factory=list)
    worker_outputs: List[Dict[str, Any]] = field(default_factory=list)
    resolution_history: List[Dict[str, Any]] = field(default_factory=list)
    final_resolution_state: str = "pending"
    resolved_at: Optional[str] = None
    resolution_note: str = ""

    def __post_init__(self) -> None:
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        normalized_entries: List[PredictionLedgerEntry] = []
        for item in self.entries:
            normalized_entries.append(
                item if isinstance(item, PredictionLedgerEntry) else PredictionLedgerEntry.from_dict(item)
            )
        self.entries = normalized_entries
        self.worker_outputs = _normalize_list_of_dicts("worker_outputs", self.worker_outputs)
        self.resolution_history = _normalize_list_of_dicts(
            "resolution_history", self.resolution_history
        )
        normalized_final_state = _normalize_resolution_state(self.final_resolution_state)
        self.final_resolution_state = normalized_final_state.get("status", "pending")
        self.resolved_at = _normalize_optional_string(self.resolved_at)
        if self.final_resolution_state not in {"pending", "open"}:
            self.resolved_at = _require_iso_datetime("resolved_at", self.resolved_at)
        elif self.resolved_at is not None:
            self.resolved_at = _require_iso_datetime("resolved_at", self.resolved_at)
        self.resolution_note = _normalize_optional_string(self.resolution_note) or ""
        for entry in self.entries:
            if entry.forecast_id != self.forecast_id:
                raise ValueError("prediction ledger entry forecast_id must match the ledger forecast_id")

    def to_dict(self) -> Dict[str, Any]:
        resolution_state = {
            "status": self.final_resolution_state,
            "resolved_at": self.resolved_at,
            "resolution_note": self.resolution_note,
        }
        return {
            "forecast_id": self.forecast_id,
            "entries": [entry.to_dict() for entry in self.entries],
            "issued_predictions": [entry.to_dict() for entry in self.issued_predictions],
            "prediction_revisions": [entry.to_dict() for entry in self.prediction_revisions],
            "worker_outputs": [dict(item) for item in self.worker_outputs],
            "resolution_history": [dict(item) for item in self.resolution_history],
            "final_resolution_state": resolution_state,
            "resolution_status": self.resolution_status,
            "resolution_state": dict(resolution_state),
            "resolved_at": self.resolved_at,
            "resolution_note": self.resolution_note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionLedger":
        entries = data.get("entries")
        if entries is None:
            entries = list(data.get("issued_predictions", [])) + list(
                data.get("prediction_revisions", [])
            )
        raw_final_state = data.get("final_resolution_state", data.get("resolution_state", "pending"))
        resolved_at = data.get("resolved_at")
        resolution_note = data.get("resolution_note", "")
        if isinstance(raw_final_state, dict):
            resolved_at = raw_final_state.get("resolved_at", resolved_at)
            resolution_note = raw_final_state.get("resolution_note", resolution_note)
            raw_final_state = (
                raw_final_state.get("status")
                or raw_final_state.get("final_resolution_state")
                or raw_final_state.get("resolution_state")
                or "pending"
            )
        return cls(
            forecast_id=data["forecast_id"],
            entries=entries,
            worker_outputs=data.get("worker_outputs", []),
            resolution_history=data.get("resolution_history", []),
            final_resolution_state=raw_final_state,
            resolved_at=resolved_at,
            resolution_note=resolution_note,
        )

    @property
    def issued_predictions(self) -> List[PredictionLedgerEntry]:
        return [entry for entry in self.entries if entry.entry_kind == "issue"]

    @property
    def prediction_revisions(self) -> List[PredictionLedgerEntry]:
        return [entry for entry in self.entries if entry.entry_kind == "revision"]

    @property
    def resolution_status(self) -> str:
        return self.final_resolution_state

    def find_entry(self, entry_id: str) -> Optional[PredictionLedgerEntry]:
        normalized_entry_id = _require_non_empty_string("entry_id", entry_id)
        for entry in self.entries:
            if entry.entry_id == normalized_entry_id or entry.prediction_id == normalized_entry_id:
                return entry
        return None

    def history_for_prediction(self, prediction_id: str) -> List[PredictionLedgerEntry]:
        normalized_prediction_id = _require_non_empty_string("prediction_id", prediction_id)
        history: List[PredictionLedgerEntry] = []
        pending_ids = [normalized_prediction_id]
        seen_ids = {normalized_prediction_id}
        while pending_ids:
            current_id = pending_ids.pop(0)
            for entry in self.entries:
                if entry in history:
                    continue
                if (
                    entry.prediction_id == current_id
                    or entry.entry_id == current_id
                    or entry.revises_entry_id == current_id
                    or entry.revises_prediction_id == current_id
                ):
                    history.append(entry)
                    if entry.prediction_id not in seen_ids:
                        seen_ids.add(entry.prediction_id)
                        pending_ids.append(entry.prediction_id)
        return sorted(
            history,
            key=lambda item: (item.recorded_at, item.revision_number, item.entry_id),
        )

    def record_issued_prediction(self, entry: PredictionLedgerEntry) -> None:
        if self.resolution_status not in {"pending", "open"}:
            raise ValueError("resolved forecast questions cannot accept new issued predictions")
        if entry.entry_kind != "issue":
            raise ValueError("record_issued_prediction requires an issue entry")
        for existing in self.entries:
            if existing.entry_id == entry.entry_id:
                return
        if any(existing.prediction_id == entry.prediction_id and existing.entry_kind == "issue" for existing in self.entries):
            raise ValueError(f"prediction ledger already contains prediction_id: {entry.prediction_id}")
        self.entries.append(entry)

    def record_prediction_revision(self, entry: PredictionLedgerEntry) -> None:
        if self.resolution_status not in {"pending", "open"}:
            raise ValueError("resolved forecast questions cannot accept new prediction revisions")
        if entry.entry_kind != "revision":
            raise ValueError("record_prediction_revision requires a revision entry")
        for existing in self.entries:
            if existing.entry_id == entry.entry_id:
                return
        base_entry = self.find_entry(entry.revises_entry_id or entry.revises_prediction_id or "")
        if base_entry is None:
            raise ValueError(
                f"revision entry references unknown entry_id: {entry.revises_entry_id or entry.revises_prediction_id}"
            )
        if _parse_iso_temporal(entry.recorded_at) < _parse_iso_temporal(base_entry.recorded_at):
            raise ValueError("prediction revision timestamp cannot precede the prediction it revises")
        if entry.revision_number <= base_entry.revision_number:
            raise ValueError("prediction revision_number must increase monotonically")
        entry.revises_prediction_id = base_entry.prediction_id
        entry.revises_entry_id = base_entry.entry_id
        self.entries.append(entry)

    def record_worker_output(self, output: Dict[str, Any]) -> None:
        if not isinstance(output, dict):
            raise ValueError("worker output must be a dictionary")
        self.worker_outputs.append(dict(output))

    def record_resolution_state(self, state: Any) -> None:
        normalized_state = _normalize_resolution_state(state)
        final_state_status = normalized_state.get("status", "pending")
        resolved_at = normalized_state.get("resolved_at", self.resolved_at)
        resolution_note = normalized_state.get("resolution_note", self.resolution_note)
        if final_state_status not in {"pending", "open"}:
            resolved_at = _require_iso_datetime("resolved_at", resolved_at)
        elif resolved_at is not None:
            resolved_at = _require_iso_datetime("resolved_at", resolved_at)
        self.resolution_history.append(
            {
                "status": final_state_status,
                "final_resolution_state": final_state_status,
                "resolved_at": resolved_at,
                "resolution_note": _normalize_optional_string(resolution_note) or "",
            }
        )
        self.final_resolution_state = final_state_status
        self.resolved_at = resolved_at
        self.resolution_note = _normalize_optional_string(resolution_note) or ""


@dataclass
class EvaluationCase:
    case_id: str
    forecast_id: str
    criteria_id: str
    status: str = "pending"
    issued_at: Optional[str] = None
    question_class: Optional[str] = None
    comparable_question_class: Optional[str] = None
    source: Optional[str] = None
    prediction_entry_id: Optional[str] = None
    prediction_value_type: Optional[str] = None
    prediction_value_semantics: Optional[str] = None
    prediction_payload: Dict[str, Any] = field(default_factory=dict)
    observed_unit: Optional[str] = None
    forecast_probability: Optional[float] = None
    observed_value: Any = None
    evaluation_split: Optional[str] = None
    window_id: Optional[str] = None
    benchmark_id: Optional[str] = None
    observed_outcome: Any = None
    resolved_at: Optional[str] = None
    answer_id: Optional[str] = None
    evidence_bundle_id: Optional[str] = None
    resolution_note: str = ""
    confidence_basis: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.case_id = _require_non_empty_string("case_id", self.case_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.criteria_id = _require_non_empty_string("criteria_id", self.criteria_id)
        self.status = _validate_supported_value(
            "evaluation case status",
            _require_non_empty_string("status", self.status),
            SUPPORTED_EVALUATION_CASE_STATUSES,
        )
        self.issued_at = _normalize_optional_string(self.issued_at)
        if self.issued_at is not None:
            self.issued_at = _require_iso_datetime("issued_at", self.issued_at)
        self.question_class = _normalize_optional_string(self.question_class)
        self.comparable_question_class = _normalize_optional_string(
            self.comparable_question_class
        )
        self.source = _normalize_optional_string(self.source)
        self.prediction_entry_id = _normalize_optional_string(self.prediction_entry_id)
        self.prediction_value_type = _normalize_optional_string(self.prediction_value_type)
        if self.prediction_value_type is not None:
            self.prediction_value_type = _validate_supported_value(
                "prediction_value_type",
                self.prediction_value_type,
                SUPPORTED_PREDICTION_VALUE_TYPES,
            )
        self.prediction_value_semantics = _normalize_optional_string(
            self.prediction_value_semantics
        )
        if self.prediction_value_semantics is not None:
            self.prediction_value_semantics = _validate_supported_value(
                "prediction_value_semantics",
                self.prediction_value_semantics,
                SUPPORTED_PREDICTION_VALUE_SEMANTICS,
            )
        self.prediction_payload = _normalize_dict(
            "prediction_payload", self.prediction_payload
        )
        self.observed_unit = _normalize_optional_string(self.observed_unit)
        if self.forecast_probability is not None:
            self.forecast_probability = float(self.forecast_probability)
            if not 0.0 <= self.forecast_probability <= 1.0:
                raise ValueError("forecast_probability must be between 0.0 and 1.0")
        if self.evaluation_split is not None:
            self.evaluation_split = _normalize_optional_string(self.evaluation_split)
        self.window_id = _normalize_optional_string(self.window_id)
        self.benchmark_id = _normalize_optional_string(self.benchmark_id)
        self.resolved_at = _normalize_optional_string(self.resolved_at)
        if self.status == "resolved":
            self.resolved_at = _require_iso_datetime("resolved_at", self.resolved_at)
        self.answer_id = _normalize_optional_string(self.answer_id)
        self.evidence_bundle_id = _normalize_optional_string(self.evidence_bundle_id)
        self.resolution_note = _normalize_optional_string(self.resolution_note) or ""
        self.confidence_basis = _normalize_dict("confidence_basis", self.confidence_basis)
        if self.status == "resolved":
            self.confidence_basis["status"] = "resolved"
        else:
            self.confidence_basis.setdefault("status", self.status)
        self.notes = _normalize_string_list("evaluation_case.notes", self.notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "forecast_id": self.forecast_id,
            "criteria_id": self.criteria_id,
            "status": self.status,
            "issued_at": self.issued_at,
            "question_class": self.question_class,
            "comparable_question_class": self.comparable_question_class,
            "source": self.source,
            "prediction_entry_id": self.prediction_entry_id,
            "prediction_value_type": self.prediction_value_type,
            "prediction_value_semantics": self.prediction_value_semantics,
            "prediction_payload": dict(self.prediction_payload),
            "observed_unit": self.observed_unit,
            "forecast_probability": self.forecast_probability,
            "observed_value": self.observed_value,
            "evaluation_split": self.evaluation_split,
            "window_id": self.window_id,
            "benchmark_id": self.benchmark_id,
            "observed_outcome": self.observed_outcome,
            "resolved_at": self.resolved_at,
            "answer_id": self.answer_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "resolution_note": self.resolution_note,
            "confidence_basis": dict(self.confidence_basis),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=data["case_id"],
            forecast_id=data["forecast_id"],
            criteria_id=data["criteria_id"],
            status=data.get("status", "pending"),
            issued_at=data.get("issued_at"),
            question_class=data.get("question_class"),
            comparable_question_class=data.get("comparable_question_class"),
            source=data.get("source"),
            prediction_entry_id=data.get("prediction_entry_id"),
            prediction_value_type=data.get("prediction_value_type"),
            prediction_value_semantics=data.get("prediction_value_semantics"),
            prediction_payload=data.get("prediction_payload", {}),
            observed_unit=data.get("observed_unit"),
            forecast_probability=data.get("forecast_probability"),
            observed_value=data.get("observed_value", data.get("observed_outcome")),
            evaluation_split=data.get("evaluation_split"),
            window_id=data.get("window_id"),
            benchmark_id=data.get("benchmark_id"),
            observed_outcome=data.get("observed_outcome"),
            resolved_at=data.get("resolved_at"),
            answer_id=data.get("answer_id"),
            evidence_bundle_id=data.get("evidence_bundle_id"),
            resolution_note=data.get("resolution_note", ""),
            confidence_basis=data.get("confidence_basis", {}),
            notes=data.get("notes", []),
        )


@dataclass
class ForecastAnswer:
    answer_id: str
    forecast_id: str
    answer_type: str
    summary: str
    worker_ids: List[str] = field(default_factory=list)
    prediction_entry_ids: List[str] = field(default_factory=list)
    confidence_semantics: str = "uncalibrated"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    answer_payload: Dict[str, Any] = field(default_factory=dict)
    evaluation_summary: Dict[str, Any] = field(default_factory=dict)
    benchmark_summary: Dict[str, Any] = field(default_factory=dict)
    backtest_summary: Dict[str, Any] = field(default_factory=dict)
    calibration_summary: Dict[str, Any] = field(default_factory=dict)
    confidence_basis: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.answer_id = _require_non_empty_string("answer_id", self.answer_id)
        self.forecast_id = _require_non_empty_string("forecast_id", self.forecast_id)
        self.answer_type = _validate_supported_value(
            "answer type",
            _require_non_empty_string("answer_type", self.answer_type),
            SUPPORTED_FORECAST_ANSWER_TYPES,
        )
        self.summary = _require_non_empty_string("summary", self.summary)
        self.worker_ids = _normalize_string_list("worker_ids", self.worker_ids)
        self.prediction_entry_ids = _normalize_string_list(
            "prediction_entry_ids", self.prediction_entry_ids
        )
        self.confidence_semantics = _validate_supported_value(
            "confidence semantics",
            _require_non_empty_string("confidence_semantics", self.confidence_semantics),
            SUPPORTED_CONFIDENCE_SEMANTICS,
        )
        self.created_at = _require_iso_datetime("created_at", self.created_at)
        self.answer_payload = _normalize_dict("answer_payload", self.answer_payload)
        self.evaluation_summary = _normalize_dict(
            "evaluation_summary", self.evaluation_summary
        )
        self.benchmark_summary = _normalize_dict(
            "benchmark_summary", self.benchmark_summary
        )
        self.backtest_summary = _normalize_dict("backtest_summary", self.backtest_summary)
        self.calibration_summary = _normalize_dict(
            "calibration_summary", self.calibration_summary
        )
        self.confidence_basis = _normalize_dict("confidence_basis", self.confidence_basis)
        self.notes = _normalize_string_list("notes", self.notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "forecast_id": self.forecast_id,
            "answer_type": self.answer_type,
            "summary": self.summary,
            "worker_ids": list(self.worker_ids),
            "prediction_entry_ids": list(self.prediction_entry_ids),
            "confidence_semantics": self.confidence_semantics,
            "created_at": self.created_at,
            "answer_payload": dict(self.answer_payload),
            "evaluation_summary": dict(self.evaluation_summary),
            "benchmark_summary": dict(self.benchmark_summary),
            "backtest_summary": dict(self.backtest_summary),
            "calibration_summary": dict(self.calibration_summary),
            "confidence_basis": dict(self.confidence_basis),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastAnswer":
        return cls(
            answer_id=data["answer_id"],
            forecast_id=data["forecast_id"],
            answer_type=data["answer_type"],
            summary=data["summary"],
            worker_ids=data.get("worker_ids", []),
            prediction_entry_ids=data.get("prediction_entry_ids", []),
            confidence_semantics=data.get("confidence_semantics", "uncalibrated"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            answer_payload=data.get("answer_payload", {}),
            evaluation_summary=data.get("evaluation_summary", {}),
            benchmark_summary=data.get("benchmark_summary", {}),
            backtest_summary=data.get("backtest_summary", {}),
            calibration_summary=data.get("calibration_summary", {}),
            confidence_basis=data.get("confidence_basis", {}),
            notes=data.get("notes", []),
        )


@dataclass
class ForecastWorkspaceRecord:
    forecast_question: ForecastQuestion
    resolution_criteria: List[ResolutionCriteria]
    evidence_bundle: EvidenceBundle
    forecast_workers: List[ForecastWorker]
    prediction_ledger: PredictionLedger
    evaluation_cases: List[EvaluationCase] = field(default_factory=list)
    forecast_answers: List[ForecastAnswer] = field(default_factory=list)
    simulation_worker_contract: Optional[SimulationWorkerContract] = None
    simulation_scope: Optional[ForecastSimulationScope] = None
    lifecycle_metadata: Optional[ForecastLifecycleMetadata] = None
    resolution_record: Optional[ForecastResolutionRecord] = None
    scoring_events: List[ForecastScoringEvent] = field(default_factory=list)
    schema_version: str = FORECAST_SCHEMA_VERSION
    generator_version: str = FORECAST_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.forecast_question, ForecastQuestion):
            self.forecast_question = ForecastQuestion.from_dict(self.forecast_question)
        if not isinstance(self.evidence_bundle, EvidenceBundle):
            self.evidence_bundle = EvidenceBundle.from_dict(self.evidence_bundle)
        if not isinstance(self.prediction_ledger, PredictionLedger):
            self.prediction_ledger = PredictionLedger.from_dict(self.prediction_ledger)
        if self.simulation_worker_contract is not None and not isinstance(
            self.simulation_worker_contract, SimulationWorkerContract
        ):
            self.simulation_worker_contract = SimulationWorkerContract.from_dict(
                self.simulation_worker_contract
            )
        if self.simulation_scope is not None and not isinstance(
            self.simulation_scope, ForecastSimulationScope
        ):
            self.simulation_scope = ForecastSimulationScope.from_dict(
                self.simulation_scope
            )
        if self.lifecycle_metadata is not None and not isinstance(
            self.lifecycle_metadata, ForecastLifecycleMetadata
        ):
            self.lifecycle_metadata = ForecastLifecycleMetadata.from_dict(
                self.lifecycle_metadata
            )
        if self.resolution_record is not None and not isinstance(
            self.resolution_record, ForecastResolutionRecord
        ):
            self.resolution_record = ForecastResolutionRecord.from_dict(
                self.resolution_record
            )

        forecast_id = self.forecast_question.forecast_id
        self.resolution_criteria = [
            item if isinstance(item, ResolutionCriteria) else ResolutionCriteria.from_dict(item)
            for item in self.resolution_criteria
        ]
        self.forecast_workers = [
            item if isinstance(item, ForecastWorker) else ForecastWorker.from_dict(item)
            for item in self.forecast_workers
        ]
        self.evaluation_cases = [
            item if isinstance(item, EvaluationCase) else EvaluationCase.from_dict(item)
            for item in self.evaluation_cases
        ]
        self.forecast_answers = [
            item if isinstance(item, ForecastAnswer) else ForecastAnswer.from_dict(item)
            for item in self.forecast_answers
        ]
        self.scoring_events = [
            item if isinstance(item, ForecastScoringEvent) else ForecastScoringEvent.from_dict(item)
            for item in self.scoring_events
        ]

        if self.evidence_bundle.forecast_id != forecast_id:
            raise ValueError("evidence_bundle forecast_id must match forecast_question.forecast_id")
        if self.prediction_ledger.forecast_id != forecast_id:
            raise ValueError("prediction_ledger forecast_id must match forecast_question.forecast_id")
        for criteria in self.resolution_criteria:
            if criteria.forecast_id != forecast_id:
                raise ValueError("resolution_criteria forecast_id must match forecast_question.forecast_id")
        for worker in self.forecast_workers:
            if worker.forecast_id != forecast_id:
                raise ValueError("forecast_workers forecast_id must match forecast_question.forecast_id")
        for case in self.evaluation_cases:
            if case.forecast_id != forecast_id:
                raise ValueError("evaluation_cases forecast_id must match forecast_question.forecast_id")
        for answer in self.forecast_answers:
            if answer.forecast_id != forecast_id:
                raise ValueError("forecast_answers forecast_id must match forecast_question.forecast_id")

        worker_ids = {worker.worker_id: worker for worker in self.forecast_workers}
        missing_criteria_ids = [
            criteria_id
            for criteria_id in self.forecast_question.resolution_criteria_ids
            if not any(criteria.criteria_id == criteria_id for criteria in self.resolution_criteria)
        ]
        if missing_criteria_ids:
            raise ValueError(
                "forecast_question references unknown resolution_criteria_ids: "
                + ", ".join(missing_criteria_ids)
            )
        if self.simulation_worker_contract is not None:
            if self.simulation_worker_contract.forecast_id != forecast_id:
                raise ValueError(
                    "simulation_worker_contract forecast_id must match forecast_question.forecast_id"
                )
            contract_worker = worker_ids.get(self.simulation_worker_contract.worker_id)
            if contract_worker is None:
                raise ValueError(
                    "simulation_worker_contract worker_id must reference an existing forecast worker"
                )
            if contract_worker.kind != "simulation":
                raise ValueError(
                    "simulation_worker_contract worker_id must reference a simulation worker"
                )
        if self.simulation_scope is not None and self.simulation_scope.forecast_id != forecast_id:
            raise ValueError(
                "simulation_scope forecast_id must match forecast_question.forecast_id"
            )
        if self.resolution_record is not None and self.resolution_record.forecast_id != forecast_id:
            raise ValueError(
                "resolution_record forecast_id must match forecast_question.forecast_id"
            )
        for scoring_event in self.scoring_events:
            if scoring_event.forecast_id != forecast_id:
                raise ValueError(
                    "scoring_events forecast_id must match forecast_question.forecast_id"
                )

        self.simulation_scope = self._derive_simulation_scope()
        self._synchronize_simulation_contract()
        self.resolution_record = self._derive_resolution_record()
        self.lifecycle_metadata = self._derive_lifecycle_metadata()
        self.schema_version = _require_non_empty_string("schema_version", self.schema_version)
        self.generator_version = _require_non_empty_string(
            "generator_version", self.generator_version
        )

    def _derive_simulation_scope(self) -> ForecastSimulationScope:
        forecast_id = self.forecast_question.forecast_id
        contract = self.simulation_worker_contract
        if self.simulation_scope is not None:
            scope = self.simulation_scope
        else:
            scope = ForecastSimulationScope(
                forecast_id=forecast_id,
                simulation_id=(
                    self.forecast_question.primary_simulation_id
                    or (contract.simulation_id if contract is not None else None)
                ),
                prepare_artifact_paths=(
                    list(contract.prepare_artifact_paths) if contract is not None else []
                ),
                ensemble_ids=(
                    list(contract.ensemble_ids) if contract is not None else []
                ),
                latest_ensemble_id=(
                    contract.ensemble_ids[-1]
                    if contract is not None and contract.ensemble_ids
                    else None
                ),
                prepare_status=(
                    "ready"
                    if contract is not None and contract.prepare_artifact_paths
                    else "unprepared"
                ),
                updated_at=self.forecast_question.updated_at,
            )

        if (
            scope.simulation_id is None
            and self.forecast_question.primary_simulation_id is not None
        ):
            scope.simulation_id = self.forecast_question.primary_simulation_id
        if (
            scope.simulation_id is not None
            and not self.forecast_question.primary_simulation_id
        ):
            self.forecast_question.primary_simulation_id = scope.simulation_id
        if contract is not None and contract.ensemble_ids and not scope.ensemble_ids:
            scope.ensemble_ids = list(contract.ensemble_ids)
        if scope.latest_ensemble_id is None and scope.ensemble_ids:
            scope.latest_ensemble_id = scope.ensemble_ids[-1]
        if scope.latest_run_id is None and scope.run_ids:
            scope.latest_run_id = scope.run_ids[-1]
        if scope.updated_at != self.forecast_question.updated_at:
            scope.updated_at = self.forecast_question.updated_at
        return scope

    def _synchronize_simulation_contract(self) -> None:
        if self.simulation_scope is None:
            return
        if self.simulation_worker_contract is None:
            return
        if (
            self.simulation_scope.simulation_id
            and not self.simulation_worker_contract.simulation_id
        ):
            self.simulation_worker_contract.simulation_id = self.simulation_scope.simulation_id
        if self.simulation_scope.prepare_artifact_paths:
            self.simulation_worker_contract.prepare_artifact_paths = list(
                self.simulation_scope.prepare_artifact_paths
            )
        if self.simulation_scope.ensemble_ids:
            self.simulation_worker_contract.ensemble_ids = list(
                self.simulation_scope.ensemble_ids
            )

    def _derive_resolution_record(self) -> ForecastResolutionRecord:
        forecast_id = self.forecast_question.forecast_id
        issue_ids = [
            entry.prediction_id or entry.entry_id
            for entry in self.prediction_ledger.issued_predictions
        ]
        revision_ids = [
            entry.entry_id for entry in self.prediction_ledger.prediction_revisions
        ]
        worker_output_ids = [
            str(item.get("output_id"))
            for item in self.prediction_ledger.worker_outputs
            if item.get("output_id")
        ]
        evidence_bundle_ids = [self.evidence_bundle.bundle_id]
        if self.resolution_record is not None:
            record = self.resolution_record
            record.status = self.prediction_ledger.resolution_status
            record.resolved_at = self.prediction_ledger.resolved_at
            record.resolution_note = self.prediction_ledger.resolution_note
            record.evidence_bundle_ids = list(evidence_bundle_ids)
            record.prediction_entry_ids = list(issue_ids)
            record.revision_entry_ids = list(revision_ids)
            record.worker_output_ids = list(worker_output_ids)
        else:
            record = ForecastResolutionRecord(
                forecast_id=forecast_id,
                status=self.prediction_ledger.resolution_status,
                resolved_at=self.prediction_ledger.resolved_at,
                resolution_note=self.prediction_ledger.resolution_note,
                evidence_bundle_ids=evidence_bundle_ids,
                prediction_entry_ids=issue_ids,
                revision_entry_ids=revision_ids,
                worker_output_ids=worker_output_ids,
            )

        if not record.evidence_bundle_ids:
            record.evidence_bundle_ids = [self.evidence_bundle.bundle_id]
        return record

    def _derive_lifecycle_metadata(self) -> ForecastLifecycleMetadata:
        forecast_id = self.forecast_question.forecast_id
        latest_answer_id = (
            self.forecast_answers[-1].answer_id if self.forecast_answers else None
        )
        resolution_status = self.resolution_record.status
        scoring_event_count = len(self.scoring_events)

        if scoring_event_count > 0:
            current_stage = "scoring_event"
        elif resolution_status not in {"pending", "open"}:
            current_stage = "resolution_record"
        elif latest_answer_id is not None:
            current_stage = "forecast_answer"
        else:
            current_stage = "forecast_workspace"

        if self.lifecycle_metadata is not None:
            metadata = self.lifecycle_metadata
            metadata.current_stage = current_stage
            metadata.stage_sequence = list(CANONICAL_FORECAST_STAGE_SEQUENCE)
            metadata.latest_answer_id = latest_answer_id
            metadata.resolution_record_status = resolution_status
            metadata.scoring_event_count = scoring_event_count
            metadata.simulation_scope_status = self.simulation_scope.status
            metadata.last_simulation_id = self.simulation_scope.simulation_id
            metadata.last_ensemble_id = self.simulation_scope.latest_ensemble_id
            metadata.last_run_id = self.simulation_scope.latest_run_id
            metadata.updated_at = self.forecast_question.updated_at
            return metadata

        return ForecastLifecycleMetadata(
            forecast_id=forecast_id,
            current_stage=current_stage,
            stage_sequence=list(CANONICAL_FORECAST_STAGE_SEQUENCE),
            latest_answer_id=latest_answer_id,
            resolution_record_status=resolution_status,
            scoring_event_count=scoring_event_count,
            simulation_scope_status=self.simulation_scope.status,
            last_simulation_id=self.simulation_scope.simulation_id,
            last_ensemble_id=self.simulation_scope.latest_ensemble_id,
            last_run_id=self.simulation_scope.latest_run_id,
            updated_at=self.forecast_question.updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "forecast_question": self.forecast_question.to_dict(),
            "resolution_criteria": [item.to_dict() for item in self.resolution_criteria],
            "evidence_bundle": self.evidence_bundle.to_dict(),
            "forecast_workers": [item.to_dict() for item in self.forecast_workers],
            "prediction_ledger": self.prediction_ledger.to_dict(),
            "evaluation_cases": [item.to_dict() for item in self.evaluation_cases],
            "forecast_answers": [item.to_dict() for item in self.forecast_answers],
            "simulation_worker_contract": (
                self.simulation_worker_contract.to_dict()
                if self.simulation_worker_contract is not None
                else None
            ),
            "simulation_scope": self.simulation_scope.to_dict(),
            "lifecycle_metadata": self.lifecycle_metadata.to_dict(),
            "resolution_record": self.resolution_record.to_dict(),
            "scoring_events": [item.to_dict() for item in self.scoring_events],
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        worker_kinds = [worker.kind for worker in self.forecast_workers]
        return {
            "forecast_id": self.forecast_question.forecast_id,
            "project_id": self.forecast_question.project_id,
            "title": self.forecast_question.title,
            "question_text": self.forecast_question.question_text,
            "question": self.forecast_question.question_text,
            "question_type": self.forecast_question.question_type,
            "question_spec": dict(self.forecast_question.question_spec),
            "status": self.forecast_question.status,
            "question_status": self.forecast_question.status,
            "horizon": dict(self.forecast_question.horizon),
            "issue_timestamp": self.forecast_question.issue_timestamp,
            "issued_at": self.forecast_question.issue_timestamp,
            "owner": self.forecast_question.owner,
            "source": self.forecast_question.source,
            "decomposition_support_count": len(self.forecast_question.decomposition_support)
            or len(self.forecast_question.decomposition.get("subquestion_ids", [])),
            "abstention_condition_count": len(self.forecast_question.abstention_conditions),
            "worker_count": len(self.forecast_workers),
            "worker_kinds": worker_kinds,
            "evidence_bundle_id": self.evidence_bundle.bundle_id,
            "evidence_entry_count": len(self.evidence_bundle.artifacts)
            or len(self.evidence_bundle.source_entries),
            "evidence_bundle_status": self.evidence_bundle.status,
            "evidence_uncertainty_causes": list(
                self.evidence_bundle.uncertainty_summary.get("causes", [])
            ),
            "evidence_uncertainty_drivers": list(
                self.evidence_bundle.uncertainty_summary.get("drivers", [])
            ),
            "retrieval_quality_status": self.evidence_bundle.retrieval_quality.get(
                "status"
            ),
            "prediction_entry_count": len(self.prediction_ledger.entries),
            "prediction_issue_count": len(self.prediction_ledger.issued_predictions),
            "prediction_revision_count": len(self.prediction_ledger.prediction_revisions),
            "worker_output_count": len(self.prediction_ledger.worker_outputs),
            "evaluation_case_count": len(self.evaluation_cases),
            "evaluation_resolved_case_count": len(
                [case for case in self.evaluation_cases if case.status == "resolved"]
            ),
            "evaluation_pending_case_count": len(
                [case for case in self.evaluation_cases if case.status != "resolved"]
            ),
            "evaluation_case_status": (
                "available"
                if any(case.status == "resolved" for case in self.evaluation_cases)
                else "partial"
                if self.evaluation_cases
                else "unavailable"
            ),
            "forecast_answer_count": len(self.forecast_answers),
            "resolution_status": self.prediction_ledger.resolution_status,
            "final_resolution_state": self.prediction_ledger.resolution_status,
            "resolved_at": self.prediction_ledger.resolved_at,
            "resolution_history_count": len(self.prediction_ledger.resolution_history),
            "has_simulation_worker_contract": self.simulation_worker_contract is not None,
            "primary_simulation_id": self.forecast_question.primary_simulation_id,
            "lifecycle_stage": self.lifecycle_metadata.current_stage,
            "simulation_scope_status": self.simulation_scope.status,
            "latest_ensemble_id": self.simulation_scope.latest_ensemble_id,
            "latest_run_id": self.simulation_scope.latest_run_id,
            "created_at": self.forecast_question.created_at,
            "updated_at": self.forecast_question.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastWorkspaceRecord":
        return cls(
            schema_version=data.get("schema_version", FORECAST_SCHEMA_VERSION),
            generator_version=data.get(
                "generator_version", FORECAST_GENERATOR_VERSION
            ),
            forecast_question=data["forecast_question"],
            resolution_criteria=data.get("resolution_criteria", []),
            evidence_bundle=data["evidence_bundle"],
            forecast_workers=data.get("forecast_workers", []),
            prediction_ledger=data.get(
                "prediction_ledger",
                {
                    "forecast_id": data["forecast_question"]["forecast_id"],
                    "entries": [],
                },
            ),
            evaluation_cases=data.get("evaluation_cases", []),
            forecast_answers=data.get("forecast_answers", []),
            simulation_worker_contract=data.get("simulation_worker_contract"),
            simulation_scope=data.get("simulation_scope"),
            lifecycle_metadata=data.get("lifecycle_metadata"),
            resolution_record=data.get("resolution_record"),
            scoring_events=data.get("scoring_events", []),
        )


def get_forecast_capabilities_domain() -> Dict[str, Any]:
    """Return the canonical additive forecasting capability contract."""
    return {
        "schema_version": FORECAST_SCHEMA_VERSION,
        "generator_version": FORECAST_GENERATOR_VERSION,
        "required_primitives": list(REQUIRED_FORECAST_PRIMITIVES),
        "primary_object": "forecast_question",
        "question_contract": {
            "fields": [
                "question",
                "question_type",
                "horizon",
                "issue_timestamp",
                "owner",
                "source",
                "decomposition_support",
                "abstention_conditions",
                "resolution_criteria_ids",
            ],
            "notes": [
                "The question object is the primary unit of forecast work.",
                "Question artifacts remain compatible with workspace aggregation.",
            ],
        },
        "prediction_ledger_contract": {
            "append_only": True,
            "supports_immutable_issues": True,
            "supports_revisions": True,
            "supports_final_resolution_state": True,
            "worker_outputs_are_preserved": True,
        },
        "hybrid_worker_contract": {
            "supports_inputs": True,
            "supports_outputs": True,
            "supports_assumptions": True,
            "supports_confidence_inputs": True,
            "supports_failure_modes": True,
            "default_workers": [
                "base_rate",
                "reference_class",
                "retrieval_synthesis",
                "simulation",
            ],
            "notes": [
                "Only non-simulation forecast-probability workers can drive the hybrid best estimate by default.",
                "Simulation remains preserved and visible as supporting scenario evidence.",
            ],
        },
        "evidence_bundle_contract": {
            "supports_provider_snapshots": True,
            "supports_citation_indexing": True,
            "supports_freshness_relevance_quality_summaries": True,
            "supports_conflict_and_missing_markers": True,
            "notes": [
                "Evidence bundles describe bounded retrieval and provenance quality for forecast work.",
                "Bundle quality scores are heuristic diagnostics, not proof that evidence is complete or true.",
                "Live external provider support is pluggable and remains unavailable unless a provider actually returns evidence.",
            ],
        },
        "evidence_bundle": {
            "primary_semantics": "retrieval_quality_bounded",
            "availability_statuses": sorted(SUPPORTED_EVIDENCE_BUNDLE_STATUSES),
            "provider_kinds": sorted(SUPPORTED_EVIDENCE_PROVIDER_KINDS),
            "uncertainty_causes": sorted(SUPPORTED_EVIDENCE_UNCERTAINTY_CAUSES),
        },
        "supported_question_types": sorted(SUPPORTED_FORECAST_QUESTION_TYPES),
        "supported_question_templates": [
            {
                "template_id": template["template_id"],
                "label": template["label"],
                "question_type": template["question_type"],
                "prompt_template": template["prompt_template"],
                "required_fields": list(template["required_fields"]),
                "abstain_guidance": template["abstain_guidance"],
                "notes": list(template["notes"]),
            }
            for template in SUPPORTED_FORECAST_QUESTION_TEMPLATES
        ],
        "supported_worker_kinds": sorted(SUPPORTED_FORECAST_WORKER_KINDS),
        "supported_prediction_value_types": sorted(SUPPORTED_PREDICTION_VALUE_TYPES),
        "supported_prediction_value_semantics": sorted(
            SUPPORTED_PREDICTION_VALUE_SEMANTICS
        ),
        "supported_evidence_provider_kinds": sorted(SUPPORTED_EVIDENCE_PROVIDER_KINDS),
        "supported_confidence_semantics": sorted(SUPPORTED_CONFIDENCE_SEMANTICS),
        "supported_calibration_kinds": sorted(SUPPORTED_FORECAST_CALIBRATION_KINDS),
        "answer_payload_shapes": {
            "binary": {
                "best_estimate": "probability",
                "uncertainty": "binary_probability",
                "calibration_kind": "binary_reliability",
            },
            "categorical": {
                "best_estimate": "categorical_distribution",
                "uncertainty": "distribution_disagreement",
                "calibration_kind": "categorical_distribution",
            },
            "numeric": {
                "best_estimate": "numeric_point_and_intervals",
                "uncertainty": "interval_width_and_worker_spread",
                "calibration_kind": "numeric_interval",
            },
            "scenario": {
                "best_estimate": "scenario_summary_only",
                "uncertainty": "scenario_diversity_and_support",
                "calibration_kind": "not_applicable",
            },
        },
        "simulation": {
            "role": "scenario_worker",
            "contract_schema_version": SIMULATION_WORKER_CONTRACT_VERSION,
            "probability_interpretation": "do_not_treat_as_real_world_probability",
            "notes": [
                "Simulation is preserved as a first-class worker in the hybrid architecture.",
                "Simulation run shares are descriptive scenario evidence, not real-world probabilities by default.",
                "Probability claims require evaluation or calibration evidence outside the simulation worker contract.",
            ],
        },
    }
