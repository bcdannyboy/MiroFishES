"""
Deterministic experiment-design planning for probabilistic ensembles.

This layer builds explicit, inspectable design rows ahead of run resolution so
ensemble artifacts can show how coverage was constructed.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from ..models.probabilistic import (
    ExperimentDesignSpec,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    ScenarioTemplateSpec,
    UncertaintySpec,
)


class ExperimentDesignService:
    """Generate deterministic structured ensemble plans."""

    def _effective_max_templates_per_run(
        self,
        design_spec: ExperimentDesignSpec,
    ) -> int:
        return max(1, int(design_spec.max_templates_per_run or 1))

    def _effective_template_combination_policy(
        self,
        design_spec: ExperimentDesignSpec,
    ) -> str:
        policy = str(design_spec.template_combination_policy or "").strip()
        if policy:
            return policy
        return (
            "pairwise"
            if self._effective_max_templates_per_run(design_spec) > 1
            else "single_template"
        )

    def build_plan(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_count: int,
        root_seed: int,
        uncertainty_spec: UncertaintySpec,
    ) -> Dict[str, Any]:
        if run_count <= 0:
            raise ValueError("run_count must be positive")

        design_spec = uncertainty_spec.experiment_design or ExperimentDesignSpec()
        rows = [
            {
                "run_id": f"{row_index + 1:04d}",
                "row_index": row_index,
                "normalized_coordinates": {},
                "stratum_indices": {},
                "scenario_template_ids": [],
            }
            for row_index in range(run_count)
        ]

        rng = random.Random(root_seed)
        group_by_field = self._map_field_groups(uncertainty_spec)
        cached_group_permutations: Dict[str, List[int]] = {}

        for dimension in design_spec.numeric_dimensions:
            group_id = group_by_field.get(dimension)
            if group_id and group_id in cached_group_permutations:
                permutation = cached_group_permutations[group_id]
            else:
                permutation = list(range(run_count))
                rng.shuffle(permutation)
                if group_id:
                    cached_group_permutations[group_id] = permutation

            for row_index, row in enumerate(rows):
                stratum_index = permutation[row_index]
                coordinate = (stratum_index + 0.5) / run_count
                row["stratum_indices"][dimension] = stratum_index
                row["normalized_coordinates"][dimension] = coordinate

        templates_by_id = {
            template.template_id: template
            for template in uncertainty_spec.scenario_templates
            if template.template_id in design_spec.scenario_template_ids
        }
        target_counts = self._build_target_counts(
            run_count=run_count,
            design_spec=design_spec,
            templates_by_id=templates_by_id,
        )
        scenario_assignments = self._build_scenario_assignments(
            run_count=run_count,
            design_spec=design_spec,
            templates_by_id=templates_by_id,
            target_counts=target_counts,
        )

        previous_row: Optional[Dict[str, Any]] = None
        for row, assignment in zip(rows, scenario_assignments):
            row.update(assignment)
            row["scenario_distance_from_previous"] = (
                round(
                    self._row_distance(
                        row,
                        previous_row,
                        design_spec.numeric_dimensions,
                        templates_by_id,
                    ),
                    4,
                )
                if previous_row is not None
                else None
            )
            previous_row = row

        diversity_plan = self._build_diversity_plan(
            design_spec=design_spec,
            target_counts=target_counts,
            rows=rows,
            templates_by_id=templates_by_id,
            uncertainty_spec=uncertainty_spec,
        )
        coverage_metrics = self._build_coverage_metrics(
            run_count=run_count,
            design_spec=design_spec,
            rows=rows,
            templates_by_id=templates_by_id,
        )
        support_metrics = self._build_support_metrics(rows)
        scenario_distance_metrics = self._build_scenario_distance_metrics(
            rows=rows,
            numeric_dimensions=design_spec.numeric_dimensions,
            templates_by_id=templates_by_id,
        )
        diversity_warnings = self._build_diversity_warnings(
            design_spec=design_spec,
            coverage_metrics=coverage_metrics,
            support_metrics=support_metrics,
        )

        return {
            "artifact_type": "experiment_design",
            "schema_version": PROBABILISTIC_SCHEMA_VERSION,
            "generator_version": PROBABILISTIC_GENERATOR_VERSION,
            "simulation_id": simulation_id,
            "ensemble_id": ensemble_id,
            "method": design_spec.method,
            "root_seed": root_seed,
            "run_count": run_count,
            "dimensions": [
                {
                    "field_path": dimension,
                    "group_id": group_by_field.get(dimension),
                }
                for dimension in design_spec.numeric_dimensions
            ],
            "scenario_template_ids": list(design_spec.scenario_template_ids),
            "scenario_assignment": design_spec.scenario_assignment,
            "max_templates_per_run": self._effective_max_templates_per_run(design_spec),
            "template_combination_policy": self._effective_template_combination_policy(
                design_spec
            ),
            "diversity_axes": list(design_spec.diversity_axes),
            "coverage_metrics": coverage_metrics,
            "support_metrics": support_metrics,
            "scenario_distance_metrics": scenario_distance_metrics,
            "diversity_warnings": diversity_warnings,
            "diversity_plan": diversity_plan,
            "scenario_diversity_plan": diversity_plan,
            "rows": rows,
        }

    def _map_field_groups(self, uncertainty_spec: UncertaintySpec) -> Dict[str, str]:
        field_groups: Dict[str, str] = {}
        for group in uncertainty_spec.variable_groups:
            for field_path in group.field_paths:
                field_groups[field_path] = group.group_id
        return field_groups

    def _build_target_counts(
        self,
        *,
        run_count: int,
        design_spec: ExperimentDesignSpec,
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> Dict[str, int]:
        scenario_template_ids = list(design_spec.scenario_template_ids)
        if design_spec.scenario_assignment == "weighted_cycle":
            weights_by_id = {
                template_id: float(templates_by_id[template_id].weight)
                for template_id in scenario_template_ids
                if template_id in templates_by_id
            }
            return self._build_weighted_target_counts(
                run_count=run_count,
                scenario_template_ids=scenario_template_ids,
                weights_by_id=weights_by_id,
            )

        target_counts = {template_id: 0 for template_id in scenario_template_ids}
        if not scenario_template_ids:
            return target_counts
        for row_index in range(run_count):
            template_id = scenario_template_ids[row_index % len(scenario_template_ids)]
            target_counts[template_id] += 1
        return target_counts

    def _build_scenario_assignments(
        self,
        *,
        run_count: int,
        design_spec: ExperimentDesignSpec,
        templates_by_id: Dict[str, ScenarioTemplateSpec],
        target_counts: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        scenario_template_ids = list(design_spec.scenario_template_ids)
        if not scenario_template_ids or design_spec.scenario_assignment == "none":
            return [self._build_assignment_payload([], templates_by_id) for _ in range(run_count)]

        primary_sequence = self._build_primary_sequence(
            run_count=run_count,
            design_spec=design_spec,
            templates_by_id=templates_by_id,
            target_counts=target_counts,
        )
        pair_counts: Dict[tuple[str, str], int] = {}
        seen_coverage_tags: set[str] = set()
        seen_event_ids: set[str] = set()
        assignments: List[Dict[str, Any]] = []

        max_templates_per_run = min(
            self._effective_max_templates_per_run(design_spec),
            max(len(scenario_template_ids), 1),
        )
        template_combination_policy = self._effective_template_combination_policy(
            design_spec
        )
        for row_index, primary_template_id in enumerate(primary_sequence):
            row_template_ids = [primary_template_id]
            if (
                template_combination_policy == "pairwise"
                and max_templates_per_run > 1
                and len(scenario_template_ids) > 1
            ):
                while len(row_template_ids) < max_templates_per_run:
                    secondary_template_id = self._select_secondary_template_id(
                        row_index=row_index,
                        primary_template_id=primary_template_id,
                        current_template_ids=row_template_ids,
                        scenario_template_ids=scenario_template_ids,
                        templates_by_id=templates_by_id,
                        pair_counts=pair_counts,
                        seen_coverage_tags=seen_coverage_tags,
                        seen_event_ids=seen_event_ids,
                    )
                    if secondary_template_id is None:
                        break
                    row_template_ids.append(secondary_template_id)
                    pair_key = tuple(sorted((primary_template_id, secondary_template_id)))
                    pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

            assignment = self._build_assignment_payload(row_template_ids, templates_by_id)
            assignments.append(assignment)
            seen_coverage_tags.update(assignment["scenario_coverage_tags"])
            seen_event_ids.update(assignment["scenario_event_ids"])
        return assignments

    def _build_primary_sequence(
        self,
        *,
        run_count: int,
        design_spec: ExperimentDesignSpec,
        templates_by_id: Dict[str, ScenarioTemplateSpec],
        target_counts: Dict[str, int],
    ) -> List[str]:
        scenario_template_ids = list(design_spec.scenario_template_ids)
        if design_spec.scenario_assignment == "cyclic":
            return [
                scenario_template_ids[row_index % len(scenario_template_ids)]
                for row_index in range(run_count)
            ]

        delivered_counts = {template_id: 0 for template_id in scenario_template_ids}
        seen_coverage_tags: set[str] = set()
        seen_event_ids: set[str] = set()
        previous_template_id: Optional[str] = None
        previous_reuse_streak = 0
        sequence: List[str] = []

        for _ in range(run_count):
            active_template_ids = [
                template_id
                for template_id in scenario_template_ids
                if delivered_counts[template_id] < target_counts.get(template_id, 0)
            ]
            if not active_template_ids:
                active_template_ids = list(scenario_template_ids)
            if (
                previous_template_id is not None
                and previous_reuse_streak >= design_spec.max_template_reuse_streak
                and len(active_template_ids) > 1
            ):
                without_previous = [
                    template_id
                    for template_id in active_template_ids
                    if template_id != previous_template_id
                ]
                if without_previous:
                    active_template_ids = without_previous

            next_template_id = min(
                active_template_ids,
                key=lambda template_id: (
                    delivered_counts[template_id] / max(target_counts.get(template_id, 1), 1),
                    -len(
                        set(self._template_coverage_tags(templates_by_id.get(template_id)))
                        - seen_coverage_tags
                    ),
                    -len(
                        set(self._template_event_ids(templates_by_id.get(template_id)))
                        - seen_event_ids
                    ),
                    -self._template_distance(
                        templates_by_id.get(template_id),
                        templates_by_id.get(previous_template_id),
                    ),
                    scenario_template_ids.index(template_id),
                ),
            )
            delivered_counts[next_template_id] += 1
            sequence.append(next_template_id)
            seen_coverage_tags.update(
                self._template_coverage_tags(templates_by_id.get(next_template_id))
            )
            seen_event_ids.update(
                self._template_event_ids(templates_by_id.get(next_template_id))
            )
            if next_template_id == previous_template_id:
                previous_reuse_streak += 1
            else:
                previous_reuse_streak = 1
            previous_template_id = next_template_id
        return sequence

    def _select_secondary_template_id(
        self,
        *,
        row_index: int,
        primary_template_id: str,
        current_template_ids: List[str],
        scenario_template_ids: List[str],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
        pair_counts: Dict[tuple[str, str], int],
        seen_coverage_tags: set[str],
        seen_event_ids: set[str],
    ) -> Optional[str]:
        candidate_template_ids = [
            template_id
            for template_id in scenario_template_ids
            if template_id not in current_template_ids
        ]
        if not candidate_template_ids:
            return None

        return min(
            candidate_template_ids,
            key=lambda template_id: (
                pair_counts.get(tuple(sorted((primary_template_id, template_id))), 0),
                -len(
                    set(self._template_coverage_tags(templates_by_id.get(template_id)))
                    - seen_coverage_tags
                ),
                -len(
                    set(self._template_event_ids(templates_by_id.get(template_id)))
                    - seen_event_ids
                ),
                -self._template_distance(
                    templates_by_id.get(primary_template_id),
                    templates_by_id.get(template_id),
                ),
                (row_index + scenario_template_ids.index(template_id))
                % max(len(candidate_template_ids), 1),
                scenario_template_ids.index(template_id),
            ),
        )

    def _build_assignment_payload(
        self,
        template_ids: List[str],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> Dict[str, Any]:
        coverage_tags = self._dedupe_strings(
            tag
            for template_id in template_ids
            for tag in self._template_coverage_tags(templates_by_id.get(template_id))
        )
        event_ids = self._dedupe_strings(
            event_id
            for template_id in template_ids
            for event_id in self._template_event_ids(templates_by_id.get(template_id))
        )
        override_fields = self._dedupe_strings(
            field_path
            for template_id in template_ids
            for field_path in sorted(
                getattr(templates_by_id.get(template_id), "field_overrides", {}).keys()
            )
        )
        correlated_field_paths = self._dedupe_strings(
            field_path
            for template_id in template_ids
            for field_path in getattr(
                templates_by_id.get(template_id), "correlated_field_paths", []
            )
        )
        conditional_override_count = sum(
            len(getattr(templates_by_id.get(template_id), "conditional_overrides", []))
            for template_id in template_ids
        )
        scenario_coverage = {
            "template_count": len(template_ids),
            "coverage_tags": coverage_tags,
            "exogenous_event_ids": event_ids,
            "correlated_field_paths": correlated_field_paths,
            "override_field_count": len(override_fields),
            "conditional_override_count": conditional_override_count,
        }
        return {
            "scenario_template_ids": list(template_ids),
            "scenario_template_labels": self._dedupe_strings(
                getattr(templates_by_id.get(template_id), "label", "")
                for template_id in template_ids
            ),
            "scenario_coverage_tags": coverage_tags,
            "scenario_event_ids": event_ids,
            "scenario_override_fields": override_fields,
            "scenario_coverage": scenario_coverage,
            "coverage_signature": {
                "template_count": len(template_ids),
                "override_field_count": len(override_fields),
            },
        }

    def _build_diversity_plan(
        self,
        *,
        design_spec: ExperimentDesignSpec,
        target_counts: Dict[str, int],
        rows: List[Dict[str, Any]],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
        uncertainty_spec: UncertaintySpec,
    ) -> Dict[str, Any]:
        coverage_axes = list(design_spec.scenario_coverage_axes or design_spec.diversity_axes)
        if not coverage_axes:
            coverage_axes = sorted(
                {
                    tag.split(":", 1)[0]
                    for template in templates_by_id.values()
                    for tag in self._template_coverage_tags(template)
                    if ":" in tag
                }
            )

        coverage_tag_counts: Dict[str, int] = {}
        for template in templates_by_id.values():
            for tag in self._template_coverage_tags(template):
                coverage_tag_counts[tag] = coverage_tag_counts.get(tag, 0) + 1

        observed_assignment_counts: Dict[str, int] = {}
        for row in rows:
            for template_id in row.get("scenario_template_ids", []):
                observed_assignment_counts[template_id] = (
                    observed_assignment_counts.get(template_id, 0) + 1
                )

        return {
            "strategy": design_spec.scenario_assignment,
            "coverage_axes": coverage_axes,
            "max_templates_per_run": self._effective_max_templates_per_run(design_spec),
            "template_combination_policy": self._effective_template_combination_policy(
                design_spec
            ),
            "max_template_reuse_streak": design_spec.max_template_reuse_streak,
            "template_target_counts": dict(target_counts),
            "observed_assignment_counts": observed_assignment_counts,
            "coverage_tag_counts": coverage_tag_counts,
            "exogenous_event_count": len(
                {
                    event_id
                    for template in templates_by_id.values()
                    for event_id in self._template_event_ids(template)
                }
            ),
            "conditional_override_count": sum(
                len(template.conditional_overrides) for template in templates_by_id.values()
            ),
            "correlated_group_count": len(uncertainty_spec.variable_groups),
        }

    def _build_coverage_metrics(
        self,
        *,
        run_count: int,
        design_spec: ExperimentDesignSpec,
        rows: List[Dict[str, Any]],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> Dict[str, Any]:
        numeric_dimension_coverage_ratios = {
            dimension: (
                len({row["stratum_indices"].get(dimension) for row in rows}) / run_count
                if run_count
                else 0.0
            )
            for dimension in design_spec.numeric_dimensions
        }
        numeric_dimension_coverage_ratio = (
            round(
                sum(numeric_dimension_coverage_ratios.values())
                / len(numeric_dimension_coverage_ratios),
                4,
            )
            if numeric_dimension_coverage_ratios
            else 0.0
        )
        template_support_counts: Dict[str, int] = {}
        for row in rows:
            for template_id in row.get("scenario_template_ids", []):
                template_support_counts[template_id] = (
                    template_support_counts.get(template_id, 0) + 1
                )
        declared_template_count = len(design_spec.scenario_template_ids)
        declared_coverage_tags = {
            tag
            for template in templates_by_id.values()
            for tag in self._template_coverage_tags(template)
        }
        observed_coverage_tags = {
            tag
            for row in rows
            for tag in row.get("scenario_coverage_tags", [])
        }
        observed_template_pairs = {
            tuple(sorted(row.get("scenario_template_ids", [])))
            for row in rows
            if len(row.get("scenario_template_ids", [])) > 1
        }
        include_extended_metrics = bool(
            declared_coverage_tags
            or observed_template_pairs
            or self._effective_max_templates_per_run(design_spec) > 1
            or design_spec.diversity_axes
            or design_spec.scenario_coverage_axes
        )
        substantive_template_count = sum(
            1
            for template in templates_by_id.values()
            if template.field_overrides
            or template.exogenous_events
            or template.conditional_overrides
        )
        template_coverage_fraction = (
            len(template_support_counts) / declared_template_count
            if declared_template_count
            else 0.0
        )
        coverage_tag_fraction = (
            len(observed_coverage_tags) / len(declared_coverage_tags)
            if declared_coverage_tags
            else 0.0
        )
        multi_template_row_fraction = (
            sum(1 for row in rows if len(row.get("scenario_template_ids", [])) > 1)
            / run_count
            if run_count
            else 0.0
        )

        metrics = {
            "numeric_dimension_coverage_ratio": round(numeric_dimension_coverage_ratio, 4),
            "numeric_dimension_coverage_ratios": {
                key: round(value, 4)
                for key, value in numeric_dimension_coverage_ratios.items()
            },
            "scenario_template_count": declared_template_count,
            "substantive_template_count": substantive_template_count,
            "substantive_template_ratio": round(
                substantive_template_count / declared_template_count,
                4,
            )
            if declared_template_count
            else 0.0,
            "template_support_counts": template_support_counts,
            "template_coverage_ratio": round(template_coverage_fraction, 4),
        }
        if include_extended_metrics:
            metrics.update(
                {
                    "template_coverage_fraction": round(template_coverage_fraction, 4),
                    "coverage_tag_ratio": round(coverage_tag_fraction, 4),
                    "coverage_tag_fraction": round(coverage_tag_fraction, 4),
                    "multi_template_row_fraction": round(multi_template_row_fraction, 4),
                    "observed_template_pair_count": len(observed_template_pairs),
                }
            )
        return metrics

    def _build_support_metrics(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        template_support_counts: Dict[str, int] = {}
        for row in rows:
            for template_id in row.get("scenario_template_ids", []):
                template_support_counts[template_id] = (
                    template_support_counts.get(template_id, 0) + 1
                )
        if not template_support_counts:
            return {
                "maximum_template_support_count": 0,
                "minimum_template_support_count": 0,
                "singleton_template_count": 0,
                "template_support_counts": {},
            }

        counts = list(template_support_counts.values())
        return {
            "maximum_template_support_count": max(counts),
            "minimum_template_support_count": min(counts),
            "singleton_template_count": sum(1 for count in counts if count == 1),
            "template_support_counts": template_support_counts,
        }

    def _build_scenario_distance_metrics(
        self,
        *,
        rows: List[Dict[str, Any]],
        numeric_dimensions: List[str],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> Dict[str, Any]:
        distances: List[float] = []
        for left_index, left_row in enumerate(rows):
            for right_row in rows[left_index + 1 :]:
                distances.append(
                    self._row_distance(
                        left_row,
                        right_row,
                        numeric_dimensions,
                        templates_by_id,
                    )
                )
        if not distances:
            return {
                "distance_metric": "hybrid_template_numeric",
                "pair_count": 0,
                "min_pairwise_distance": 0.0,
                "mean_pairwise_distance": 0.0,
                "max_pairwise_distance": 0.0,
            }
        return {
            "distance_metric": "hybrid_template_numeric",
            "pair_count": len(distances),
            "min_pairwise_distance": round(min(distances), 4),
            "mean_pairwise_distance": round(sum(distances) / len(distances), 4),
            "max_pairwise_distance": round(max(distances), 4),
        }

    def _build_diversity_warnings(
        self,
        *,
        design_spec: ExperimentDesignSpec,
        coverage_metrics: Dict[str, Any],
        support_metrics: Dict[str, Any],
    ) -> List[str]:
        warnings: List[str] = []
        if (
            design_spec.scenario_template_ids
            and coverage_metrics.get(
                "template_coverage_fraction",
                coverage_metrics.get("template_coverage_ratio", 0.0),
            )
            < 1.0
        ):
            warnings.append("limited_template_coverage")
        if (
            (design_spec.scenario_coverage_axes or design_spec.diversity_axes)
            and coverage_metrics.get(
                "coverage_tag_fraction",
                coverage_metrics.get("coverage_tag_ratio", 0.0),
            )
            < 1.0
        ):
            warnings.append("limited_coverage_tag_span")
        if (
            self._effective_max_templates_per_run(design_spec) > 1
            and coverage_metrics.get("multi_template_row_fraction", 0.0) < 1.0
        ):
            warnings.append("partial_multi_template_assignment")
        if support_metrics.get("singleton_template_count", 0) > 0:
            warnings.append("singleton_template_support")
        return warnings

    def _row_distance(
        self,
        left_row: Optional[Dict[str, Any]],
        right_row: Optional[Dict[str, Any]],
        numeric_dimensions: List[str],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> float:
        if left_row is None or right_row is None:
            return 0.0
        left_features = self._row_feature_set(left_row, templates_by_id)
        right_features = self._row_feature_set(right_row, templates_by_id)
        feature_union = left_features | right_features
        feature_distance = 0.0
        if feature_union:
            feature_distance = 1.0 - (len(left_features & right_features) / len(feature_union))
        numeric_distance = 0.0
        if numeric_dimensions:
            numeric_distance = math.sqrt(
                sum(
                    (
                        float(left_row.get("normalized_coordinates", {}).get(dimension, 0.0))
                        - float(right_row.get("normalized_coordinates", {}).get(dimension, 0.0))
                    )
                    ** 2
                    for dimension in numeric_dimensions
                )
            )
        return feature_distance + numeric_distance

    def _row_feature_set(
        self,
        row: Dict[str, Any],
        templates_by_id: Dict[str, ScenarioTemplateSpec],
    ) -> set[str]:
        feature_set: set[str] = set()
        for template_id in row.get("scenario_template_ids", []):
            template = templates_by_id.get(template_id)
            feature_set.add(f"template:{template_id}")
            feature_set.update(
                f"tag:{tag}" for tag in self._template_coverage_tags(template)
            )
            feature_set.update(
                f"event:{event_id}" for event_id in self._template_event_ids(template)
            )
            feature_set.update(
                f"field:{field_path}"
                for field_path in getattr(template, "field_overrides", {}).keys()
            )
        return feature_set

    def _template_coverage_tags(
        self,
        template: Optional[ScenarioTemplateSpec],
    ) -> List[str]:
        if template is None:
            return []
        return sorted(
            {
                str(tag).strip()
                for tag in template.coverage_tags
                if str(tag).strip()
            }
        )

    def _template_event_ids(
        self,
        template: Optional[ScenarioTemplateSpec],
    ) -> List[str]:
        if template is None:
            return []
        event_ids: List[str] = []
        for event in template.exogenous_events:
            event_id = str((event or {}).get("event_id") or "").strip()
            if event_id and event_id not in event_ids:
                event_ids.append(event_id)
        return event_ids

    def _template_distance(
        self,
        left: Optional[ScenarioTemplateSpec],
        right: Optional[ScenarioTemplateSpec],
    ) -> float:
        if left is None or right is None:
            return 1.0 if left is not None or right is not None else 0.0
        left_features = (
            set(self._template_coverage_tags(left))
            | {f"event:{event_id}" for event_id in self._template_event_ids(left)}
            | {f"field:{field_path}" for field_path in left.field_overrides.keys()}
        )
        right_features = (
            set(self._template_coverage_tags(right))
            | {f"event:{event_id}" for event_id in self._template_event_ids(right)}
            | {f"field:{field_path}" for field_path in right.field_overrides.keys()}
        )
        feature_union = left_features | right_features
        if not feature_union:
            return 0.0
        return 1.0 - (len(left_features & right_features) / len(feature_union))

    def _dedupe_strings(self, values) -> List[str]:
        deduped: List[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped

    def _build_weighted_target_counts(
        self,
        *,
        run_count: int,
        scenario_template_ids: List[str],
        weights_by_id: Dict[str, float],
    ) -> Dict[str, int]:
        if run_count <= 0:
            return {template_id: 0 for template_id in scenario_template_ids}
        positive_template_ids = [
            template_id
            for template_id in scenario_template_ids
            if weights_by_id.get(template_id, 1.0) > 0
        ]
        if not positive_template_ids:
            return {template_id: 0 for template_id in scenario_template_ids}
        total_weight = sum(
            weights_by_id.get(template_id, 1.0) for template_id in positive_template_ids
        )
        if total_weight <= 0:
            return {template_id: 0 for template_id in scenario_template_ids}

        target_counts = {template_id: 0 for template_id in scenario_template_ids}
        remainders: List[tuple[float, str]] = []
        assigned = 0
        for template_id in positive_template_ids:
            exact_count = run_count * weights_by_id.get(template_id, 1.0) / total_weight
            count = int(exact_count)
            target_counts[template_id] = count
            assigned += count
            remainders.append((exact_count - count, template_id))

        if run_count >= len(positive_template_ids):
            for template_id in positive_template_ids:
                if target_counts[template_id] == 0:
                    target_counts[template_id] = 1
                    assigned += 1

        while assigned > run_count:
            removable_template_id = max(
                (
                    template_id
                    for template_id in positive_template_ids
                    if target_counts[template_id] > 1
                    or run_count < len(positive_template_ids)
                ),
                key=lambda template_id: (
                    target_counts[template_id],
                    -weights_by_id.get(template_id, 1.0),
                ),
            )
            target_counts[removable_template_id] -= 1
            assigned -= 1

        remainders.sort(
            key=lambda item: (-item[0], scenario_template_ids.index(item[1]))
        )
        remainder_index = 0
        while assigned < run_count and remainders:
            _, template_id = remainders[remainder_index % len(remainders)]
            target_counts[template_id] += 1
            assigned += 1
            remainder_index += 1
        return target_counts
