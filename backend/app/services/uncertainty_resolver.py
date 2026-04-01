"""
Deterministically resolve prepare-time uncertainty specs into one concrete run.

This service is intentionally narrow: it transforms an in-memory base config into
one resolved config plus a run manifest. Runtime execution and persistence land
in later phases.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.probabilistic import (
    RandomVariableSpec,
    RunManifest,
    StructuralUncertaintyOption,
    StructuralUncertaintySpec,
    UncertaintySpec,
)


_PATH_TOKEN_RE = re.compile(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?")


class UncertaintyResolver:
    """Resolve one concrete config deterministically for a future run."""

    def resolve_run_config(
        self,
        simulation_id: str,
        run_id: str,
        base_config: dict,
        uncertainty_spec: UncertaintySpec,
        resolution_seed: int | None = None,
        ensemble_id: str | None = None,
        fallback_to_root_seed: bool = True,
        experiment_design_row: Optional[Dict[str, Any]] = None,
    ) -> dict:
        if not isinstance(base_config, dict):
            raise ValueError("base_config must be a dictionary")

        if resolution_seed is not None:
            effective_seed = resolution_seed
        elif fallback_to_root_seed:
            effective_seed = (
                uncertainty_spec.root_seed
                if uncertainty_spec.root_seed is not None
                else 0
            )
        else:
            effective_seed = None

        rng = random.Random(effective_seed)
        resolved_config = copy.deepcopy(base_config)
        resolved_values = {}
        design_row_coverage = copy.deepcopy(
            (experiment_design_row or {}).get("scenario_coverage")
            or {
                "coverage_tags": list(
                    (experiment_design_row or {}).get("scenario_coverage_tags", [])
                ),
                "exogenous_event_ids": list(
                    (experiment_design_row or {}).get("scenario_event_ids", [])
                ),
            }
        )
        assumption_ledger = {
            "design_method": (
                uncertainty_spec.experiment_design.method
                if uncertainty_spec.experiment_design is not None
                else "legacy-random"
            ),
            "scenario_template_ids": list(
                (experiment_design_row or {}).get("scenario_template_ids", [])
            ),
            "applied_templates": [],
            "scenario_override_fields": [],
            "scenario_coverage_tags": [],
            "applied_exogenous_event_ids": [],
            "activated_template_conditions": [],
            "activated_conditions": [],
            "scenario_template_labels": [],
            "scenario_signature": {
                "template_count": len(
                    list((experiment_design_row or {}).get("scenario_template_ids", []))
                ),
            },
            "scenario_coverage": design_row_coverage,
            "design_row": copy.deepcopy(experiment_design_row) if experiment_design_row else None,
            "structural_uncertainties": [],
            "structural_coverage_tags": [],
            "structural_runtime_transition_types": [],
            "assumption_statements": [],
        }

        for variable in uncertainty_spec.random_variables:
            sampled_value = self._sample_value(
                variable,
                rng,
                normalized_coordinate=self._get_design_coordinate(
                    experiment_design_row,
                    variable.field_path,
                ),
            )
            self._set_path_value(resolved_config, variable.field_path, sampled_value)
            resolved_values[variable.field_path] = sampled_value

        (
            applied_templates,
            scenario_override_fields,
            scenario_coverage_tags,
            applied_exogenous_event_ids,
            activated_template_conditions,
            scenario_template_labels,
        ) = self._apply_scenario_templates(
            resolved_config,
            uncertainty_spec,
            assumption_ledger["scenario_template_ids"],
            rng=rng,
            experiment_design_row=experiment_design_row,
        )
        assumption_ledger["applied_templates"] = applied_templates
        assumption_ledger["scenario_override_fields"] = scenario_override_fields
        assumption_ledger["scenario_coverage_tags"] = scenario_coverage_tags
        assumption_ledger["applied_exogenous_event_ids"] = applied_exogenous_event_ids
        assumption_ledger["activated_template_conditions"] = activated_template_conditions
        assumption_ledger["scenario_template_labels"] = scenario_template_labels
        if not assumption_ledger["scenario_coverage"].get("coverage_tags"):
            assumption_ledger["scenario_coverage"]["coverage_tags"] = list(
                scenario_coverage_tags
            )
        if not assumption_ledger["scenario_coverage"].get("exogenous_event_ids"):
            assumption_ledger["scenario_coverage"]["exogenous_event_ids"] = list(
                applied_exogenous_event_ids
            )
        (
            structural_resolutions,
            structural_coverage_tags,
            structural_runtime_transition_types,
            assumption_statements,
        ) = self._apply_structural_uncertainties(
            resolved_config,
            uncertainty_spec,
            rng=rng,
            experiment_design_row=experiment_design_row,
        )
        assumption_ledger["structural_uncertainties"] = structural_resolutions
        assumption_ledger["structural_coverage_tags"] = structural_coverage_tags
        assumption_ledger["structural_runtime_transition_types"] = (
            structural_runtime_transition_types
        )
        assumption_ledger["assumption_statements"] = assumption_statements
        for conditional in uncertainty_spec.conditional_variables:
            if not self._condition_matches(
                resolved_config,
                condition_field_path=conditional.condition_field_path,
                operator=conditional.operator,
                condition_value=conditional.condition_value,
            ):
                continue
            sampled_value = self._sample_value(
                conditional.variable,
                rng,
                normalized_coordinate=self._get_design_coordinate(
                    experiment_design_row,
                    conditional.variable.field_path,
                ),
            )
            self._set_path_value(
                resolved_config,
                conditional.variable.field_path,
                sampled_value,
            )
            resolved_values[conditional.variable.field_path] = sampled_value
            assumption_ledger["activated_conditions"].append(
                conditional.variable.field_path
            )

        return {
            "resolved_config": resolved_config,
            "run_manifest": RunManifest(
                simulation_id=simulation_id,
                run_id=run_id,
                ensemble_id=ensemble_id,
                root_seed=uncertainty_spec.root_seed,
                seed_metadata={
                    "root_seed": uncertainty_spec.root_seed,
                    "resolution_seed": effective_seed,
                },
                resolved_values=resolved_values,
                assumption_ledger=assumption_ledger,
                experiment_design_row=copy.deepcopy(experiment_design_row)
                if experiment_design_row
                else {},
                structural_resolutions=structural_resolutions,
                artifact_paths={
                    "resolved_config": "resolved_config.json",
                },
            ),
        }

    def _sample_value(
        self,
        variable: RandomVariableSpec,
        rng: random.Random,
        *,
        normalized_coordinate: Optional[float] = None,
    ) -> Any:
        parameters = variable.parameters

        if variable.distribution == "fixed":
            if "value" not in parameters:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "fixed distributions require value"
                )
            return parameters["value"]

        if variable.distribution == "categorical":
            choices = parameters.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "categorical distributions require choices"
                )
            weights = parameters.get("weights")
            if weights is not None and len(weights) != len(choices):
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "weights must match choices length"
                )
            if normalized_coordinate is not None:
                return self._sample_categorical_from_coordinate(
                    choices,
                    weights=weights,
                    normalized_coordinate=normalized_coordinate,
                )
            return rng.choices(choices, weights=weights, k=1)[0]

        if variable.distribution == "uniform":
            low = parameters.get("low")
            high = parameters.get("high")
            if low is None or high is None:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "uniform distributions require low and high"
                )
            if low > high:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "uniform low cannot exceed high"
                )
            if normalized_coordinate is not None:
                coordinate = min(max(float(normalized_coordinate), 0.0), 1.0)
                return low + ((high - low) * coordinate)
            return rng.uniform(low, high)

        if variable.distribution == "normal":
            mean = parameters.get("mean")
            stddev = parameters.get("stddev")
            if mean is None or stddev is None:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "normal distributions require mean and stddev"
                )
            if stddev < 0:
                raise ValueError(
                    f"Malformed distribution parameters for {variable.field_path}: "
                    "normal stddev must be non-negative"
                )
            return rng.gauss(mean, stddev)

        raise ValueError(f"Unsupported distribution: {variable.distribution}")

    def _sample_categorical_from_coordinate(
        self,
        choices: List[Any],
        *,
        weights: Optional[List[float]],
        normalized_coordinate: float,
    ) -> Any:
        if not choices:
            raise ValueError("categorical choices are required")
        coordinate = min(max(float(normalized_coordinate), 0.0), 0.999999999)
        if not weights:
            weights = [1.0] * len(choices)
        total = float(sum(weights))
        threshold = coordinate * total
        running = 0.0
        for choice, weight in zip(choices, weights):
            running += float(weight)
            if threshold < running:
                return choice
        return choices[-1]

    def _get_design_coordinate(
        self,
        experiment_design_row: Optional[Dict[str, Any]],
        field_path: str,
    ) -> Optional[float]:
        if not experiment_design_row:
            return None
        normalized_coordinates = experiment_design_row.get("normalized_coordinates", {})
        value = normalized_coordinates.get(field_path)
        return float(value) if isinstance(value, (int, float)) else None

    def _apply_structural_uncertainties(
        self,
        resolved_config: Dict[str, Any],
        uncertainty_spec: UncertaintySpec,
        *,
        rng: random.Random,
        experiment_design_row: Optional[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str], List[str], List[str]]:
        if not uncertainty_spec.structural_uncertainties:
            return [], [], [], []

        selected_by_id = {}
        for item in (experiment_design_row or {}).get("structural_assignments", []):
            if not isinstance(item, dict):
                continue
            uncertainty_id = str(item.get("uncertainty_id") or "").strip()
            option_id = str(item.get("option_id") or "").strip()
            if uncertainty_id and option_id:
                selected_by_id[uncertainty_id] = option_id

        structural_resolutions: List[Dict[str, Any]] = []
        structural_coverage_tags: List[str] = []
        structural_runtime_transition_types: List[str] = []
        assumption_statements: List[str] = []

        for structural_spec in uncertainty_spec.structural_uncertainties:
            option = self._resolve_structural_option(
                structural_spec,
                selected_option_id=selected_by_id.get(structural_spec.uncertainty_id),
                rng=rng,
            )
            for field_path, value in option.config_overrides.items():
                self._set_path_value(resolved_config, field_path, value)
            runtime_transition_types = []
            for hint in option.runtime_transition_hints:
                transition_type = str(hint.get("transition_type") or "").strip()
                if (
                    transition_type
                    and transition_type not in runtime_transition_types
                ):
                    runtime_transition_types.append(transition_type)
            resolution = {
                "uncertainty_id": structural_spec.uncertainty_id,
                "kind": structural_spec.kind,
                "label": structural_spec.label,
                "option_id": option.option_id,
                "option_label": option.label,
                "coverage_tags": list(option.coverage_tags),
                "runtime_transition_hints": [
                    dict(item) for item in option.runtime_transition_hints
                ],
                "runtime_transition_types": runtime_transition_types,
                "override_fields": sorted(option.config_overrides.keys()),
                "assumption_text": option.assumption_text,
            }
            structural_resolutions.append(resolution)
            for coverage_tag in option.coverage_tags:
                if coverage_tag not in structural_coverage_tags:
                    structural_coverage_tags.append(coverage_tag)
            for transition_type in runtime_transition_types:
                if transition_type not in structural_runtime_transition_types:
                    structural_runtime_transition_types.append(transition_type)
            if option.assumption_text and option.assumption_text not in assumption_statements:
                assumption_statements.append(option.assumption_text)

        return (
            structural_resolutions,
            sorted(structural_coverage_tags),
            sorted(structural_runtime_transition_types),
            assumption_statements,
        )

    def _resolve_structural_option(
        self,
        structural_spec: StructuralUncertaintySpec,
        *,
        selected_option_id: Optional[str],
        rng: random.Random,
    ) -> StructuralUncertaintyOption:
        options_by_id = {
            option.option_id: option for option in structural_spec.options
        }
        if selected_option_id:
            option = options_by_id.get(selected_option_id)
            if option is None:
                raise ValueError(
                    f"Unknown structural option for {structural_spec.uncertainty_id}: {selected_option_id}"
                )
            return option
        weights = [option.weight for option in structural_spec.options]
        return rng.choices(structural_spec.options, weights=weights, k=1)[0]

    def _apply_scenario_templates(
        self,
        resolved_config: Dict[str, Any],
        uncertainty_spec: UncertaintySpec,
        scenario_template_ids: List[str],
        *,
        rng: random.Random,
        experiment_design_row: Optional[Dict[str, Any]],
    ) -> Tuple[List[str], List[str], List[str], List[str], List[str], List[str]]:
        if not scenario_template_ids:
            return [], [], [], [], [], []
        templates_by_id = {
            template.template_id: template
            for template in uncertainty_spec.scenario_templates
        }
        applied_templates: List[str] = []
        scenario_override_fields: List[str] = []
        scenario_coverage_tags: List[str] = []
        applied_exogenous_event_ids: List[str] = []
        activated_template_conditions: List[str] = []
        scenario_template_labels: List[str] = []
        for template_id in scenario_template_ids:
            template = templates_by_id.get(template_id)
            if template is None:
                continue
            applied_templates.append(template_id)
            if template.label not in scenario_template_labels:
                scenario_template_labels.append(template.label)
            for field_path, value in template.field_overrides.items():
                self._set_path_value(resolved_config, field_path, value)
                if field_path not in scenario_override_fields:
                    scenario_override_fields.append(field_path)
            for coverage_tag in getattr(template, "coverage_tags", []):
                normalized_tag = str(coverage_tag or "").strip()
                if normalized_tag and normalized_tag not in scenario_coverage_tags:
                    scenario_coverage_tags.append(normalized_tag)
            for event_id in self._merge_exogenous_events(
                resolved_config,
                getattr(template, "exogenous_events", []),
            ):
                if event_id not in applied_exogenous_event_ids:
                    applied_exogenous_event_ids.append(event_id)
            for conditional in getattr(template, "conditional_overrides", []):
                if not self._condition_matches(
                    resolved_config,
                    condition_field_path=conditional.condition_field_path,
                    operator=conditional.operator,
                    condition_value=conditional.condition_value,
                ):
                    continue
                sampled_value = self._sample_value(
                    conditional.variable,
                    rng,
                    normalized_coordinate=self._get_design_coordinate(
                        experiment_design_row,
                        conditional.variable.field_path,
                    ),
                )
                self._set_path_value(
                    resolved_config,
                    conditional.variable.field_path,
                    sampled_value,
                )
                if conditional.variable.field_path not in activated_template_conditions:
                    activated_template_conditions.append(conditional.variable.field_path)
        return (
            applied_templates,
            sorted(scenario_override_fields),
            sorted(scenario_coverage_tags),
            applied_exogenous_event_ids,
            sorted(activated_template_conditions),
            sorted(scenario_template_labels),
        )

    def _merge_exogenous_events(
        self,
        resolved_config: Dict[str, Any],
        exogenous_events: List[Dict[str, Any]],
    ) -> List[str]:
        event_config = resolved_config.get("event_config")
        if not isinstance(event_config, dict):
            return []
        scheduled_events = event_config.get("scheduled_events")
        if not isinstance(scheduled_events, list):
            scheduled_events = []
        event_ids: List[str] = []
        existing_event_ids = {
            str(item.get("event_id") or "").strip()
            for item in scheduled_events
            if isinstance(item, dict)
        }
        for item in exogenous_events:
            if not isinstance(item, dict):
                continue
            normalized_item = dict(item)
            event_id = str(normalized_item.get("event_id") or "").strip()
            if not event_id:
                continue
            if event_id not in existing_event_ids:
                scheduled_events.append(normalized_item)
                existing_event_ids.add(event_id)
            if event_id not in event_ids:
                event_ids.append(event_id)
        event_config["scheduled_events"] = scheduled_events
        return event_ids

    def _condition_matches(
        self,
        resolved_config: Dict[str, Any],
        *,
        condition_field_path: str,
        operator: str,
        condition_value: Any,
    ) -> bool:
        observed_value = self._get_path_value(resolved_config, condition_field_path)
        if operator == "eq":
            return observed_value == condition_value
        if operator == "in":
            return observed_value in condition_value
        if operator == "gte":
            return observed_value >= condition_value
        if operator == "lte":
            return observed_value <= condition_value
        raise ValueError(f"Unsupported conditional operator: {operator}")

    def _set_path_value(self, target: dict, field_path: str, value: Any) -> None:
        path_tokens = self._parse_path(field_path)
        current: Any = target

        for key, index in path_tokens[:-1]:
            current = self._descend(current, field_path, key, index)

        last_key, last_index = path_tokens[-1]
        if last_index is None:
            if not isinstance(current, dict) or last_key not in current:
                raise ValueError(f"Invalid config path: {field_path}")
            current[last_key] = value
            return

        if not isinstance(current, dict) or last_key not in current:
            raise ValueError(f"Invalid config path: {field_path}")
        container = current[last_key]
        if not isinstance(container, list) or last_index >= len(container):
            raise ValueError(f"Invalid config path: {field_path}")
        container[last_index] = value

    def _get_path_value(self, target: dict, field_path: str) -> Any:
        path_tokens = self._parse_path(field_path)
        current: Any = target
        for key, index in path_tokens:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Invalid config path: {field_path}")
            current = current[key]
            if index is not None:
                if not isinstance(current, list) or index >= len(current):
                    raise ValueError(f"Invalid config path: {field_path}")
                current = current[index]
        return current

    def _descend(
        self,
        current: Any,
        field_path: str,
        key: str,
        index: int | None,
    ) -> Any:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"Invalid config path: {field_path}")

        next_value = current[key]
        if index is None:
            return next_value

        if not isinstance(next_value, list) or index >= len(next_value):
            raise ValueError(f"Invalid config path: {field_path}")

        return next_value[index]

    def _parse_path(self, field_path: str) -> List[Tuple[str, int | None]]:
        tokens: List[Tuple[str, int | None]] = []
        for raw_token in field_path.split("."):
            match = _PATH_TOKEN_RE.fullmatch(raw_token)
            if not match:
                raise ValueError(f"Invalid config path: {field_path}")
            key, index = match.groups()
            tokens.append((key, int(index) if index is not None else None))

        if not tokens:
            raise ValueError(f"Invalid config path: {field_path}")

        return tokens
