"""
Compatibility service layer around the hybrid forecast engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import Config
from ..models.forecasting import ForecastWorker, ForecastWorkspaceRecord
from .forecast_engine import HybridForecastEngine, HybridForecastExecutionResult


@dataclass
class HybridForecastServiceExecution(HybridForecastExecutionResult):
    registered_workers: list[ForecastWorker]


class HybridForecastService:
    def __init__(self, *, simulation_data_dir: Optional[str] = None):
        self.engine = HybridForecastEngine(
            simulation_data_dir=simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR
        )

    @staticmethod
    def _worker_family(worker: ForecastWorker) -> str:
        family = str(worker.metadata.get("worker_family") or "").strip()
        if family in {"base_rate", "reference_class", "retrieval_synthesis", "simulation"}:
            return family
        if worker.kind in {"base_rate", "reference_class", "retrieval_synthesis", "simulation"}:
            return worker.kind
        if worker.kind == "retrieval":
            return "retrieval_synthesis"
        if worker.kind == "analytical":
            return "reference_class" if "reference" in worker.label.lower() else "base_rate"
        return worker.kind

    def _ensure_registered_workers(
        self,
        workspace: ForecastWorkspaceRecord,
    ) -> list[ForecastWorker]:
        worker_map = {worker.worker_id: worker for worker in workspace.forecast_workers}
        family_map = {self._worker_family(worker): worker for worker in workspace.forecast_workers}
        forecast_id = workspace.forecast_question.forecast_id
        question_type = str(workspace.forecast_question.question_type or "binary").strip() or "binary"

        analytical_output_semantics = (
            "forecast_distribution"
            if question_type == "categorical"
            else "numeric_interval_estimate"
            if question_type == "numeric"
            else "forecast_probability"
        )

        if "base_rate" not in family_map:
            worker_map["worker-base-rate"] = ForecastWorker(
                worker_id="worker-base-rate",
                forecast_id=forecast_id,
                kind="base_rate",
                label="Base-rate benchmark worker",
                status="ready",
                capabilities=["benchmark_lookup", "historical_baseline"],
                primary_output_semantics=analytical_output_semantics,
                metadata={"worker_family": "base_rate"},
            )
        if "reference_class" not in family_map:
            worker_map["worker-reference-class"] = ForecastWorker(
                worker_id="worker-reference-class",
                forecast_id=forecast_id,
                kind="reference_class",
                label="Reference-class worker",
                status="ready",
                capabilities=["case_based_reasoning", "reference_class_lookup"],
                primary_output_semantics=analytical_output_semantics,
                metadata={"worker_family": "reference_class"},
            )
        if "retrieval_synthesis" not in family_map:
            worker_map["worker-retrieval-synthesis"] = ForecastWorker(
                worker_id="worker-retrieval-synthesis",
                forecast_id=forecast_id,
                kind="retrieval_synthesis",
                label="Retrieval synthesis worker",
                status="ready",
                capabilities=["bounded_local_retrieval", "evidence_synthesis"],
                primary_output_semantics=analytical_output_semantics,
                metadata={"worker_family": "retrieval_synthesis"},
            )
        if "simulation" not in family_map and workspace.simulation_worker_contract is not None:
            worker_map[workspace.simulation_worker_contract.worker_id] = ForecastWorker(
                worker_id=workspace.simulation_worker_contract.worker_id,
                forecast_id=forecast_id,
                kind="simulation",
                label="Scenario simulation worker",
                status="ready",
                capabilities=["scenario_generation", "scenario_analysis"],
                primary_output_semantics="scenario_evidence",
                metadata={"worker_family": "simulation_adapter"},
            )
        return list(worker_map.values())

    def execute(
        self,
        workspace: ForecastWorkspaceRecord,
        *,
        requested_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
        comparable_workspaces: Optional[list[ForecastWorkspaceRecord]] = None,
    ) -> HybridForecastServiceExecution:
        registered_workers = self._ensure_registered_workers(workspace)
        selected_worker_ids = {str(item).strip() for item in worker_ids or [] if str(item).strip()}
        prepared_workers = (
            [worker for worker in registered_workers if worker.worker_id in selected_worker_ids]
            if selected_worker_ids
            else registered_workers
        )
        prepared_workspace = ForecastWorkspaceRecord.from_dict(
            {
                **workspace.to_dict(),
                "forecast_workers": [worker.to_dict() for worker in prepared_workers],
            }
        )
        execution = self.engine.execute(
            prepared_workspace,
            recorded_at=requested_at,
            comparable_workspaces=comparable_workspaces or [],
        )
        return HybridForecastServiceExecution(
            forecast_answer=execution.forecast_answer,
            prediction_entries=execution.prediction_entries,
            worker_results=execution.worker_results,
            registered_workers=prepared_workers,
        )

    def run(
        self,
        *,
        workspace: ForecastWorkspaceRecord,
        comparable_workspaces: Optional[list[ForecastWorkspaceRecord]] = None,
        issued_at: Optional[str] = None,
    ) -> HybridForecastExecutionResult:
        return self.execute(
            workspace,
            requested_at=issued_at,
            comparable_workspaces=comparable_workspaces or [],
        )
