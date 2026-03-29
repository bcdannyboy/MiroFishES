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

from ..models.probabilistic import RandomVariableSpec, RunManifest, UncertaintySpec


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
        assumption_ledger = {
            "design_method": (
                uncertainty_spec.experiment_design.method
                if uncertainty_spec.experiment_design is not None
                else "legacy-random"
            ),
            "scenario_template_ids": list(
                (experiment_design_row or {}).get("scenario_template_ids", [])
            ),
            "activated_conditions": [],
            "design_row": copy.deepcopy(experiment_design_row) if experiment_design_row else None,
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

        self._apply_scenario_templates(
            resolved_config,
            uncertainty_spec,
            assumption_ledger["scenario_template_ids"],
        )
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

    def _apply_scenario_templates(
        self,
        resolved_config: Dict[str, Any],
        uncertainty_spec: UncertaintySpec,
        scenario_template_ids: List[str],
    ) -> None:
        if not scenario_template_ids:
            return
        templates_by_id = {
            template.template_id: template
            for template in uncertainty_spec.scenario_templates
        }
        for template_id in scenario_template_ids:
            template = templates_by_id.get(template_id)
            if template is None:
                continue
            for field_path, value in template.field_overrides.items():
                self._set_path_value(resolved_config, field_path, value)

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
