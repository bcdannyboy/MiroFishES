"""
Forecasting foundation service interfaces.

These contracts keep the architecture explicit before additional workers or
execution engines are layered in.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from ..models.forecasting import (
    EvidenceBundle,
    EvaluationCase,
    ForecastAnswer,
    ForecastQuestion,
    ForecastWorker,
    ForecastWorkspaceRecord,
    PredictionLedger,
    PredictionLedgerEntry,
    SimulationWorkerContract,
)


@runtime_checkable
class ForecastWorkspaceStore(Protocol):
    """Persistence contract for one forecast workspace."""

    def create_workspace(self, workspace: ForecastWorkspaceRecord) -> ForecastWorkspaceRecord:
        ...

    def save_workspace(self, workspace: ForecastWorkspaceRecord) -> ForecastWorkspaceRecord:
        ...

    def get_workspace(self, forecast_id: str) -> Optional[ForecastWorkspaceRecord]:
        ...

    def list_workspaces(self) -> list[ForecastWorkspaceRecord]:
        ...


@runtime_checkable
class ForecastQuestionService(Protocol):
    """Question-centric service contract for the primary forecast object."""

    def create_question(self, question: ForecastQuestion) -> ForecastWorkspaceRecord:
        ...

    def get_question(self, forecast_id: str) -> Optional[ForecastQuestion]:
        ...

    def list_questions(self) -> list[ForecastQuestion]:
        ...

    def update_question(
        self,
        forecast_id: str,
        question: ForecastQuestion | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...

    def resolve_forecast(
        self,
        forecast_id: str,
        resolution_state: Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...

    def resolve_question(
        self,
        forecast_id: str,
        resolution_state: Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...


@runtime_checkable
class PredictionLedgerService(Protocol):
    """Append-only ledger contract for issued predictions and revisions."""

    def get_prediction_ledger(self, forecast_id: str) -> PredictionLedger:
        ...

    def issue_prediction(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        ...

    def revise_prediction(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        ...

    def record_worker_output(
        self,
        forecast_id: str,
        worker_output: Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...

    def get_prediction_history(
        self,
        forecast_id: str,
        prediction_id: str,
    ) -> list[PredictionLedgerEntry]:
        ...


@runtime_checkable
class EvidenceProvider(Protocol):
    """Provider contract for bounded evidence acquisition."""

    provider_id: str
    provider_kind: str
    label: str
    is_live: bool

    def collect(
        self,
        *,
        question: ForecastQuestion,
        existing_bundle: Optional[EvidenceBundle] = None,
    ) -> Dict[str, Any]:
        ...


@runtime_checkable
class EvidenceBundleService(Protocol):
    """Bundle lifecycle contract for forecast evidence state."""

    def get_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: Optional[str] = None,
    ) -> Optional[EvidenceBundle]:
        ...

    def list_evidence_bundles(self, forecast_id: str) -> list[EvidenceBundle]:
        ...

    def create_evidence_bundle(
        self,
        forecast_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...

    def update_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        ...

    def acquire_evidence_bundle(
        self,
        forecast_id: str,
        *,
        bundle_id: Optional[str] = None,
        provider_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        ...

    def list_evidence_providers(self) -> list[Dict[str, Any]]:
        ...


@runtime_checkable
class ForecastPhaseService(
    ForecastQuestionService,
    PredictionLedgerService,
    EvidenceBundleService,
    Protocol,
):
    """Service contract for additive forecasting work inside one workspace."""

    def register_worker(
        self,
        forecast_id: str,
        worker: ForecastWorker,
        simulation_worker_contract: Optional[SimulationWorkerContract] = None,
    ) -> ForecastWorkspaceRecord:
        ...

    def append_prediction_entry(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        ...

    def append_evaluation_case(
        self,
        forecast_id: str,
        case: EvaluationCase,
    ) -> ForecastWorkspaceRecord:
        ...

    def append_forecast_answer(
        self,
        forecast_id: str,
        answer: ForecastAnswer,
    ) -> ForecastWorkspaceRecord:
        ...

    def generate_hybrid_forecast_answer(
        self,
        forecast_id: str,
        *,
        requested_at: Optional[str] = None,
    ) -> ForecastWorkspaceRecord:
        ...

    def generate_hybrid_forecast_answer(
        self,
        forecast_id: str,
        *,
        requested_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        ...
