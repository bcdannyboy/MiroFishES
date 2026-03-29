"""
Deterministic experiment-design planning for probabilistic ensembles.

This layer builds explicit, inspectable design rows ahead of run resolution so
ensemble artifacts can show how coverage was constructed.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from ..models.probabilistic import (
    ExperimentDesignSpec,
    PROBABILISTIC_GENERATOR_VERSION,
    PROBABILISTIC_SCHEMA_VERSION,
    UncertaintySpec,
)


class ExperimentDesignService:
    """Generate deterministic structured ensemble plans."""

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

        scenario_template_ids = list(design_spec.scenario_template_ids)
        if scenario_template_ids and design_spec.scenario_assignment == "cyclic":
            for row_index, row in enumerate(rows):
                row["scenario_template_ids"] = [
                    scenario_template_ids[row_index % len(scenario_template_ids)]
                ]

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
            "scenario_template_ids": scenario_template_ids,
            "scenario_assignment": design_spec.scenario_assignment,
            "rows": rows,
        }

    def _map_field_groups(self, uncertainty_spec: UncertaintySpec) -> Dict[str, str]:
        field_groups: Dict[str, str] = {}
        for group in uncertainty_spec.variable_groups:
            for field_path in group.field_paths:
                field_groups[field_path] = group.group_id
        return field_groups
