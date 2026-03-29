"""
Shared analytics semantics for probabilistic ensemble analysis.

This layer keeps support and eligibility rules explicit and reusable across:
- aggregate summaries
- scenario clustering
- sensitivity analysis
- report-context packaging
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


class AnalyticsPolicy:
    """Centralize run eligibility and support metadata for analytics artifacts."""

    THIN_SAMPLE_WARNING_THRESHOLD = 5
    MINIMUM_SUPPORT_COUNT = 2
    DEFAULT_CLUSTER_RADIUS = 1.25
    MAX_NUMERIC_DRIVER_GROUPS = 3

    def assess_run(
        self,
        *,
        mode: str,
        run_payload: Dict[str, Any],
        required_metric_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        run_id = str(run_payload.get("run_id", "")).strip()
        metrics_payload = run_payload.get("metrics_payload") or run_payload.get("metrics")
        required_metric_ids = list(required_metric_ids or [])
        reasons: List[str] = []
        warning_hints: List[str] = []

        if not isinstance(metrics_payload, dict):
            reasons.append("missing_run_metrics")
            return {
                "run_id": run_id,
                "eligible": False,
                "reasons": reasons,
                "warning_hints": warning_hints,
            }

        quality_checks = metrics_payload.get("quality_checks", {})
        metrics_complete = (
            quality_checks.get("status") == "complete"
            and quality_checks.get("run_status") == "completed"
        )
        if not metrics_complete:
            if mode == "aggregate":
                warning_hints.append("degraded_run_metrics")
            else:
                reasons.append("degraded_run_metrics")

        if mode == "sensitivity" and not run_payload.get("manifest_valid", True):
            reasons.append("invalid_run_manifest")

        if mode == "sensitivity":
            resolved_values = run_payload.get("resolved_values")
            if not isinstance(resolved_values, dict) or not resolved_values:
                reasons.append("missing_resolved_values")

        if required_metric_ids:
            available_metric_ids = set(run_payload.get("available_numeric_metric_ids", []))
            if not available_metric_ids:
                available_metric_ids = set(
                    self.extract_available_numeric_metric_ids(metrics_payload)
                )
            if any(metric_id not in available_metric_ids for metric_id in required_metric_ids):
                reasons.append("missing_required_metrics")

        return {
            "run_id": run_id,
            "eligible": not reasons,
            "reasons": reasons,
            "warning_hints": warning_hints,
        }

    def build_support_metadata(
        self,
        *,
        support_count: int,
        total_count: int,
        include_thin_sample: bool = True,
    ) -> Dict[str, Any]:
        support_count = int(support_count)
        total_count = int(total_count)
        warnings: List[str] = []
        if support_count < self.MINIMUM_SUPPORT_COUNT:
            warnings.append("minimum_support_not_met")
        if include_thin_sample and support_count < self.THIN_SAMPLE_WARNING_THRESHOLD:
            warnings.append("thin_sample")
        return {
            "support_count": support_count,
            "support_fraction": (
                support_count / total_count if total_count > 0 else 0.0
            ),
            "minimum_support_count": self.MINIMUM_SUPPORT_COUNT,
            "minimum_support_met": support_count >= self.MINIMUM_SUPPORT_COUNT,
            "warnings": warnings,
        }

    def build_sample_policy(
        self,
        *,
        mode: str,
        total_runs: int,
        eligible_run_ids: List[str],
        excluded_runs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "analysis_mode": mode,
            "total_runs": total_runs,
            "eligible_run_count": len(eligible_run_ids),
            "eligible_run_ids": list(eligible_run_ids),
            "excluded_run_count": len(excluded_runs),
            "excluded_runs": list(excluded_runs),
            "thin_sample_threshold": self.THIN_SAMPLE_WARNING_THRESHOLD,
            "minimum_support_count": self.MINIMUM_SUPPORT_COUNT,
        }

    def extract_available_numeric_metric_ids(
        self,
        metrics_payload: Dict[str, Any],
    ) -> List[str]:
        metric_values = metrics_payload.get("metric_values", {})
        available = [
            metric_id
            for metric_id, raw_entry in metric_values.items()
            if self.coerce_numeric_value(raw_entry) is not None
        ]
        return sorted(available)

    def coerce_numeric_value(self, raw_entry: Any) -> Optional[float]:
        if isinstance(raw_entry, dict):
            value = raw_entry.get("value")
        else:
            value = raw_entry

        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def build_numeric_driver_groups(
        self,
        values_by_run: List[tuple[Dict[str, Any], float]],
    ) -> List[Dict[str, Any]]:
        ordered = sorted(
            values_by_run,
            key=lambda item: (float(item[1]), item[0].get("run_id", "")),
        )
        max_group_count = min(
            self.MAX_NUMERIC_DRIVER_GROUPS,
            len(ordered) // self.MINIMUM_SUPPORT_COUNT,
        )
        if max_group_count < 2:
            return []

        base_size = len(ordered) // max_group_count
        remainder = len(ordered) % max_group_count
        sizes = [
            base_size + (1 if index < remainder else 0)
            for index in range(max_group_count)
        ]

        groups: List[Dict[str, Any]] = []
        cursor = 0
        for group_index, size in enumerate(sizes):
            members = ordered[cursor : cursor + size]
            cursor += size
            values = [float(value) for _, value in members]
            support = self.build_support_metadata(
                support_count=len(members),
                total_count=len(ordered),
                include_thin_sample=False,
            )
            minimum = min(values)
            maximum = max(values)
            label = (
                format(minimum, "g")
                if minimum == maximum
                else f"{format(minimum, 'g')}..{format(maximum, 'g')}"
            )
            groups.append(
                {
                    "group_kind": "numeric_band",
                    "group_index": group_index,
                    "value_label": label,
                    "members": [payload for payload, _ in members],
                    "support_count": support["support_count"],
                    "support_fraction": support["support_fraction"],
                    "minimum_support_count": support["minimum_support_count"],
                    "minimum_support_met": support["minimum_support_met"],
                    "warnings": support["warnings"],
                    "range_min": minimum,
                    "range_max": maximum,
                }
            )
        return groups

    def build_identity_groups(
        self,
        values_by_run: List[tuple[Dict[str, Any], Any]],
        *,
        format_value,
        stable_key,
        sort_value,
    ) -> List[Dict[str, Any]]:
        group_map: Dict[str, Dict[str, Any]] = {}
        for payload, raw_value in values_by_run:
            key = stable_key(raw_value)
            group = group_map.setdefault(
                key,
                {
                    "value": raw_value,
                    "value_label": format_value(raw_value),
                    "members": [],
                },
            )
            group["members"].append(payload)

        ordered_groups = sorted(
            group_map.values(),
            key=lambda item: (sort_value(item["value"]), item["value_label"]),
        )
        total_count = len(values_by_run)
        for group in ordered_groups:
            support = self.build_support_metadata(
                support_count=len(group["members"]),
                total_count=total_count,
                include_thin_sample=False,
            )
            group.update(support)
            group["group_kind"] = "identity"
            group["warnings"] = support["warnings"]
        return ordered_groups

    def build_report_analytics_semantics(
        self,
        *,
        aggregate_summary: Dict[str, Any],
        scenario_clusters: Dict[str, Any],
        sensitivity: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "aggregate": aggregate_summary.get("sample_policy", {"analysis_mode": "aggregate"}),
            "scenario": scenario_clusters.get("sample_policy", {"analysis_mode": "scenario"}),
            "sensitivity": sensitivity.get("sample_policy", {"analysis_mode": "sensitivity"}),
        }
