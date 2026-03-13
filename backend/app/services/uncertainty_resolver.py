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
from typing import Any, List, Tuple

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

        for variable in uncertainty_spec.random_variables:
            sampled_value = self._sample_value(variable, rng)
            self._set_path_value(resolved_config, variable.field_path, sampled_value)
            resolved_values[variable.field_path] = sampled_value

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
                artifact_paths={
                    "resolved_config": "resolved_config.json",
                },
            ),
        }

    def _sample_value(self, variable: RandomVariableSpec, rng: random.Random) -> Any:
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
