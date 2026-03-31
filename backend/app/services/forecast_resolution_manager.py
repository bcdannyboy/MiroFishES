"""
Resolution and scoring helpers for forecast workspaces.

This layer scores the latest forecast answer as a first-class forecast object
without widening the epistemic scope of the underlying simulation artifacts.
"""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Iterable, Optional

from ..models.forecasting import ForecastScoringEvent, ForecastWorkspaceRecord
from .forecast_manager import ForecastManager


def _compact_timestamp(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def _clip_probability(value: float, lower: float = 1e-12, upper: float = 1.0 - 1e-12) -> float:
    return max(lower, min(upper, float(value)))


def _normalize_distribution(values: dict[str, Any]) -> dict[str, float]:
    usable: dict[str, float] = {}
    for label, raw_value in (values or {}).items():
        normalized_label = str(label or "").strip()
        if not normalized_label:
            continue
        try:
            score = float(raw_value)
        except (TypeError, ValueError):
            continue
        if score < 0:
            continue
        usable[normalized_label] = usable.get(normalized_label, 0.0) + score
    total = sum(usable.values())
    if total <= 0:
        return {}
    return {
        label: round(score / total, 12)
        for label, score in sorted(usable.items(), key=lambda item: (-item[1], item[0]))
    }


def _top_distribution_label(distribution: dict[str, float]) -> Optional[str]:
    if not distribution:
        return None
    return max(distribution.items(), key=lambda item: (float(item[1]), item[0]))[0]


def _categorical_log_loss(distribution: dict[str, float], observed_label: str) -> Optional[float]:
    probability = distribution.get(observed_label)
    if probability is None:
        return None
    return -math.log(_clip_probability(float(probability)))


def _categorical_brier_score(distribution: dict[str, float], observed_label: str) -> Optional[float]:
    if not distribution:
        return None
    labels = list(distribution.keys())
    if observed_label not in labels:
        labels.append(observed_label)
    return sum(
        (float(distribution.get(label, 0.0)) - (1.0 if label == observed_label else 0.0)) ** 2
        for label in labels
    )


class ForecastResolutionManager:
    """Append scoring events for the latest forecast answer in one workspace."""

    def __init__(
        self,
        *,
        forecast_data_dir: Optional[str] = None,
        forecast_manager: Optional[ForecastManager] = None,
    ) -> None:
        self.forecast_manager = forecast_manager or ForecastManager(
            forecast_data_dir=forecast_data_dir
        )

    def score_forecast(
        self,
        forecast_id: str,
        *,
        observed_outcome: Any,
        scoring_methods: Optional[list[str]] = None,
        recorded_at: Optional[str] = None,
        notes: Optional[Iterable[str]] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self.forecast_manager.get_workspace(forecast_id)
        if workspace is None:
            raise ValueError(f"Unknown forecast question: {forecast_id}")
        if not workspace.forecast_answers:
            raise ValueError("forecast workspace does not have a forecast answer to score")

        latest_answer = workspace.forecast_answers[-1]
        answer_payload = dict(latest_answer.answer_payload or {})
        best_estimate = answer_payload.get("best_estimate")
        if not isinstance(best_estimate, dict):
            raise ValueError("latest forecast answer does not expose a scoreable best_estimate")

        question_type = str(workspace.forecast_question.question_type or "").strip().lower()
        scoring_recorded_at = (
            datetime.now().isoformat()
            if recorded_at is None
            else datetime.fromisoformat(str(recorded_at)).isoformat()
        )
        event_notes = [str(item).strip() for item in (notes or []) if str(item).strip()]

        if question_type == "binary":
            events = self._score_binary(
                workspace=workspace,
                best_estimate=best_estimate,
                observed_outcome=observed_outcome,
                scoring_methods=scoring_methods or ["brier_score", "log_score"],
                recorded_at=scoring_recorded_at,
                notes=event_notes,
            )
        elif question_type == "categorical":
            events = self._score_categorical(
                workspace=workspace,
                best_estimate=best_estimate,
                observed_outcome=observed_outcome,
                scoring_methods=scoring_methods
                or ["multiclass_log_loss", "multiclass_brier_score", "top1_accuracy"],
                recorded_at=scoring_recorded_at,
                notes=event_notes,
            )
        elif question_type == "numeric":
            events = self._score_numeric(
                workspace=workspace,
                best_estimate=best_estimate,
                observed_outcome=observed_outcome,
                scoring_methods=scoring_methods or ["absolute_error", "squared_error"],
                recorded_at=scoring_recorded_at,
                notes=event_notes,
            )
        else:
            raise ValueError(f"unsupported question type for scoring: {question_type}")

        workspace.scoring_events.extend(events)
        return self.forecast_manager.save_workspace(workspace)

    def _score_binary(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        best_estimate: dict[str, Any],
        observed_outcome: Any,
        scoring_methods: list[str],
        recorded_at: str,
        notes: list[str],
    ) -> list[ForecastScoringEvent]:
        probability = self._extract_binary_probability(best_estimate)
        if probability is None:
            raise ValueError("latest forecast answer does not expose a binary probability")
        observed_value = self._extract_binary_outcome(observed_outcome)

        score_lookup = {
            "brier_score": (probability - observed_value) ** 2,
            "log_score": -(
                observed_value * math.log(_clip_probability(probability))
                + (1.0 - observed_value) * math.log(_clip_probability(1.0 - probability))
            ),
        }
        return self._build_events(
            workspace=workspace,
            scoring_methods=scoring_methods,
            score_lookup=score_lookup,
            recorded_at=recorded_at,
            notes=notes,
        )

    def _score_categorical(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        best_estimate: dict[str, Any],
        observed_outcome: Any,
        scoring_methods: list[str],
        recorded_at: str,
        notes: list[str],
    ) -> list[ForecastScoringEvent]:
        distribution = _normalize_distribution(
            best_estimate.get("distribution")
            or best_estimate.get("value")
            or {}
        )
        if not distribution:
            raise ValueError("latest forecast answer does not expose a categorical distribution")
        observed_label = str(observed_outcome or "").strip()
        if not observed_label:
            raise ValueError("categorical scoring requires a non-empty observed_outcome label")
        top_label = _top_distribution_label(distribution)
        score_lookup = {
            "multiclass_log_loss": _categorical_log_loss(distribution, observed_label),
            "multiclass_brier_score": _categorical_brier_score(distribution, observed_label),
            "top1_accuracy": 1.0 if top_label == observed_label else 0.0,
        }
        return self._build_events(
            workspace=workspace,
            scoring_methods=scoring_methods,
            score_lookup=score_lookup,
            recorded_at=recorded_at,
            notes=notes,
        )

    def _score_numeric(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        best_estimate: dict[str, Any],
        observed_outcome: Any,
        scoring_methods: list[str],
        recorded_at: str,
        notes: list[str],
    ) -> list[ForecastScoringEvent]:
        point_estimate = best_estimate.get("value")
        if point_estimate is None:
            point_estimate = best_estimate.get("point_estimate")
        try:
            predicted_value = float(point_estimate)
            observed_value = float(observed_outcome)
        except (TypeError, ValueError):
            raise ValueError("numeric scoring requires numeric predicted and observed values")

        absolute_error = abs(predicted_value - observed_value)
        score_lookup = {
            "absolute_error": absolute_error,
            "squared_error": absolute_error ** 2,
        }
        return self._build_events(
            workspace=workspace,
            scoring_methods=scoring_methods,
            score_lookup=score_lookup,
            recorded_at=recorded_at,
            notes=notes,
        )

    def _build_events(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        scoring_methods: list[str],
        score_lookup: dict[str, Any],
        recorded_at: str,
        notes: list[str],
    ) -> list[ForecastScoringEvent]:
        events: list[ForecastScoringEvent] = []
        timestamp_suffix = _compact_timestamp(recorded_at)
        base_count = len(workspace.scoring_events)
        for index, method in enumerate(scoring_methods, start=1):
            if method not in score_lookup:
                raise ValueError(f"unsupported scoring method: {method}")
            raw_score = score_lookup[method]
            if raw_score is None:
                raise ValueError(f"scoring method is unavailable for the current answer: {method}")
            score_value = round(float(raw_score), 12)
            events.append(
                ForecastScoringEvent(
                    scoring_event_id=(
                        f"score_{workspace.forecast_question.forecast_id}_{timestamp_suffix}_{base_count + index:02d}"
                    ),
                    forecast_id=workspace.forecast_question.forecast_id,
                    status="scored",
                    scoring_method=method,
                    score_value=score_value,
                    recorded_at=recorded_at,
                    notes=list(notes),
                )
            )
        return events

    @staticmethod
    def _extract_binary_probability(best_estimate: dict[str, Any]) -> Optional[float]:
        try:
            value = best_estimate.get("value")
            if value is None:
                value = best_estimate.get("probability")
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_binary_outcome(observed_outcome: Any) -> float:
        if isinstance(observed_outcome, bool):
            return 1.0 if observed_outcome else 0.0
        if isinstance(observed_outcome, (int, float)) and observed_outcome in {0, 1}:
            return float(observed_outcome)
        if isinstance(observed_outcome, dict):
            for key in ("value", "observed_value", "outcome", "result"):
                value = observed_outcome.get(key)
                if isinstance(value, bool):
                    return 1.0 if value else 0.0
                if isinstance(value, (int, float)) and value in {0, 1}:
                    return float(value)
        normalized = str(observed_outcome or "").strip().lower()
        if normalized in {"true", "yes", "resolved_true", "1"}:
            return 1.0
        if normalized in {"false", "no", "resolved_false", "0"}:
            return 0.0
        raise ValueError("binary scoring requires a boolean observed_outcome")
