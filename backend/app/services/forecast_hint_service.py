"""Build structured forecast hints and conflict annotations from retrieved evidence."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_SUPPORT_TERMS = {
    "support",
    "supports",
    "supported",
    "likely",
    "indicates",
    "suggests",
    "reinforces",
    "confirms",
}
_CONTRADICTION_TERMS = {
    "contradict",
    "contradicts",
    "contradiction",
    "dispute",
    "disputes",
    "refute",
    "refutes",
    "delay",
    "delays",
}
_UNCERTAINTY_TERMS = {
    "uncertain",
    "uncertainty",
    "risk",
    "volatile",
    "volatility",
    "revision",
    "mixed",
}


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _sanitize_counterparty_text(title: str, summary: str) -> str:
    combined = " ".join(part.strip() for part in [summary, title] if str(part).strip())
    return re.sub(r"\s+", " ", combined).strip()


class ForecastHintService:
    """Derive additive forecast hints without changing downstream worker contracts."""

    def annotate_hit(
        self,
        *,
        query: str,
        question_type: str,
        title: str,
        summary: str,
        content: str,
        object_type: str | None,
        related_edge_names: List[str],
        citations: List[Dict[str, Any]],
        provenance: Dict[str, Any],
        score: float,
    ) -> Dict[str, Any]:
        text = " ".join(part for part in [title, summary, content, query] if part).lower()
        edge_text = " ".join(name.lower() for name in related_edge_names if name)
        conflict_status = self._derive_conflict_status(
            text=text,
            edge_text=edge_text,
            object_type=object_type,
        )

        conflict_markers: List[Dict[str, Any]] = []
        if conflict_status == "contradicts":
            conflict_markers.append(
                {
                    "code": "contradicts",
                    "summary": _sanitize_counterparty_text(title, summary),
                }
            )
        elif conflict_status == "mixed":
            conflict_markers.append(
                {
                    "code": "mixed",
                    "summary": _sanitize_counterparty_text(title, summary),
                }
            )

        forecast_hints = self._build_forecast_hints(
            question_type=question_type,
            conflict_status=conflict_status,
            title=title,
            summary=summary,
            citations=citations,
            provenance=provenance,
            score=score,
            object_type=object_type,
        )
        return {
            "conflict_status": conflict_status,
            "conflict_markers": conflict_markers,
            "forecast_hints": forecast_hints,
        }

    def _derive_conflict_status(
        self,
        *,
        text: str,
        edge_text: str,
        object_type: str | None,
    ) -> str:
        if "contradict" in edge_text or "refute" in edge_text or _contains_any(text, _CONTRADICTION_TERMS):
            return "contradicts"
        if object_type == "UncertaintyFactor" or _contains_any(text, _UNCERTAINTY_TERMS):
            return "mixed"
        if object_type in {"Claim", "Evidence", "Metric", "Event", "Scenario", "Topic"}:
            return "supports"
        if _contains_any(text, _SUPPORT_TERMS):
            return "supports"
        return "none"

    def _build_forecast_hints(
        self,
        *,
        question_type: str,
        conflict_status: str,
        title: str,
        summary: str,
        citations: List[Dict[str, Any]],
        provenance: Dict[str, Any],
        score: float,
        object_type: str | None,
    ) -> List[Dict[str, Any]]:
        if conflict_status == "none":
            return []

        hint: Dict[str, Any] = {
            "signal": conflict_status,
            "confidence_weight": round(max(0.05, min(score, 1.0)), 4),
            "citation_ids": [item.get("citation_id") for item in citations if item.get("citation_id")],
            "source_unit_ids": list(provenance.get("source_unit_ids") or []),
            "object_type": object_type,
        }
        descriptive_text = _sanitize_counterparty_text(title, summary)
        if descriptive_text:
            if conflict_status == "supports":
                hint["assumption"] = descriptive_text
            else:
                hint["counterevidence"] = descriptive_text

        if question_type == "binary":
            if conflict_status == "supports":
                hint["estimate"] = round(min(0.9, 0.55 + (0.25 * score)), 4)
            elif conflict_status == "contradicts":
                hint["estimate"] = round(max(0.1, 0.45 - (0.25 * score)), 4)
            else:
                hint["estimate"] = 0.5
        return [hint]
