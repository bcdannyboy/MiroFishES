"""
Filesystem-backed persistence for the canonical forecasting foundation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..config import Config
from ..models.forecasting import (
    EvidenceBundle,
    EvaluationCase,
    ForecastAnswer,
    ForecastLifecycleMetadata,
    ForecastQuestion,
    ForecastResolutionRecord,
    ForecastScoringEvent,
    ForecastSimulationScope,
    ForecastWorker,
    ForecastWorkspaceRecord,
    PredictionLedger,
    PredictionLedgerEntry,
    ResolutionCriteria,
    SimulationWorkerContract,
    _parse_iso_temporal,
)
from ..utils.logger import get_logger
from .forecast_interfaces import ForecastPhaseService, ForecastWorkspaceStore
from .evidence_bundle_service import EvidenceBundleService
from .hybrid_forecast_service import HybridForecastService


logger = get_logger("mirofish.forecast")
DEFAULT_FORECAST_DATA_DIR = Config.FORECAST_DATA_DIR


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

QUESTION_TYPE_PREDICTION_VALUE_TYPES = {
    "binary": {"probability", "scenario_observed_share", "qualitative"},
    "categorical": {"distribution", "categorical_distribution", "scenario_observed_share", "qualitative"},
    "numeric": {"numeric_estimate", "numeric_interval", "scenario_observed_share", "qualitative"},
    "scenario": {
        "distribution",
        "categorical_distribution",
        "numeric_estimate",
        "numeric_interval",
        "scenario_observed_share",
        "qualitative",
        "probability",
    },
}
QUESTION_TYPE_PREDICTION_VALUE_SEMANTICS = {
    "binary": {"forecast_probability", "observed_run_share", "qualitative_judgment"},
    "categorical": {"forecast_distribution", "observed_run_share", "qualitative_judgment"},
    "numeric": {"numeric_estimate", "numeric_interval_estimate", "observed_run_share", "qualitative_judgment"},
    "scenario": {
        "forecast_probability",
        "forecast_distribution",
        "numeric_estimate",
        "numeric_interval_estimate",
        "observed_run_share",
        "qualitative_judgment",
    },
}


class ForecastManager(ForecastWorkspaceStore, ForecastPhaseService):
    """Persist additive forecast workspaces as explicit JSON artifacts."""

    FORECAST_DATA_DIR = Config.FORECAST_DATA_DIR
    ARTIFACT_FILENAMES = {
        "workspace_manifest": "workspace_manifest.json",
        "forecast_question": "forecast_question.json",
        "resolution_criteria": "resolution_criteria.json",
        "evidence_bundle": "evidence_bundle.json",
        "evidence_bundles": "evidence_bundles.json",
        "forecast_workers": "forecast_workers.json",
        "simulation_worker_contract": "simulation_worker_contract.json",
        "simulation_scope": "simulation_scope.json",
        "lifecycle_metadata": "lifecycle_metadata.json",
        "resolution_record": "resolution_record.json",
        "scoring_events": "scoring_events.json",
        "prediction_ledger": "prediction_ledger.json",
        "evaluation_cases": "evaluation_cases.json",
        "forecast_answers": "forecast_answers.json",
    }
    EVIDENCE_PROVIDERS = (
        {
            "provider_id": "uploaded_local_artifact",
            "provider_kind": "uploaded_local_artifact",
            "label": "Uploaded/local artifact provider",
            "is_live": False,
            "retrieval_quality": "bounded_local_artifacts",
            "boundary_note": (
                "Uses persisted uploaded sources, stored graph provenance, and saved simulation artifacts only."
            ),
        },
        {
            "provider_id": "live_external",
            "provider_kind": "live_external",
            "label": "Live external evidence provider",
            "is_live": True,
            "retrieval_quality": "not_configured",
            "boundary_note": (
                "Pluggable interface only; this environment does not imply live external retrieval coverage."
            ),
        },
    )

    def __init__(
        self,
        forecast_data_dir: Optional[str] = None,
        evidence_bundle_service: Optional[EvidenceBundleService] = None,
        hybrid_forecast_service: Optional[HybridForecastService] = None,
    ):
        class_dir = getattr(type(self), "FORECAST_DATA_DIR", None)
        configured_dir = getattr(Config, "FORECAST_DATA_DIR", None)
        if forecast_data_dir is not None:
            self.forecast_data_dir = forecast_data_dir
        elif class_dir and class_dir != DEFAULT_FORECAST_DATA_DIR:
            self.forecast_data_dir = class_dir
        else:
            self.forecast_data_dir = configured_dir or class_dir or DEFAULT_FORECAST_DATA_DIR
        self.evidence_bundle_service = evidence_bundle_service or EvidenceBundleService()
        self.hybrid_forecast_service = hybrid_forecast_service or HybridForecastService(
            simulation_data_dir=self._infer_simulation_data_dir(
                self.evidence_bundle_service
            )
        )
        os.makedirs(self.forecast_data_dir, exist_ok=True)

    @staticmethod
    def _infer_simulation_data_dir(
        evidence_bundle_service: EvidenceBundleService,
    ) -> Optional[str]:
        providers = getattr(evidence_bundle_service, "providers", {})
        for provider in getattr(providers, "values", lambda: [])():
            simulation_data_dir = getattr(provider, "simulation_data_dir", None)
            if simulation_data_dir:
                return simulation_data_dir
        return None

    def _get_workspace_dir(self, forecast_id: str) -> str:
        workspace_dir = os.path.join(self.forecast_data_dir, forecast_id)
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir

    def _candidate_forecast_dirs(self) -> list[str]:
        candidates = [
            self.forecast_data_dir,
            getattr(type(self), "FORECAST_DATA_DIR", None),
            getattr(Config, "FORECAST_DATA_DIR", None),
            DEFAULT_FORECAST_DATA_DIR,
        ]
        normalized: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            path = os.path.abspath(str(candidate))
            if path not in normalized:
                normalized.append(path)
        return normalized

    def _resolve_workspace_root(self, forecast_id: str) -> Optional[str]:
        artifact_name = self.ARTIFACT_FILENAMES["forecast_question"]
        for candidate_dir in self._candidate_forecast_dirs():
            candidate_path = os.path.join(candidate_dir, forecast_id, artifact_name)
            if os.path.exists(candidate_path):
                if candidate_dir != self.forecast_data_dir:
                    self.forecast_data_dir = candidate_dir
                return candidate_dir
        return None

    def _get_artifact_path(self, forecast_id: str, artifact_name: str) -> str:
        return os.path.join(
            self._get_workspace_dir(forecast_id),
            self.ARTIFACT_FILENAMES[artifact_name],
        )

    def _write_json(self, path: str, payload: Dict[str, Any] | list[Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _read_json_if_exists(self, path: str) -> Optional[Any]:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _normalize_evidence_bundle(
        self,
        bundle: EvidenceBundle | Dict[str, Any],
        *,
        forecast_id: str,
    ) -> EvidenceBundle:
        normalized_bundle = (
            bundle
            if isinstance(bundle, EvidenceBundle)
            else EvidenceBundle.from_dict(
                {
                    **bundle,
                    "source_entries": (
                        bundle.get("source_entries", bundle.get("entries", []))
                        if isinstance(bundle, dict)
                        else []
                    ),
                    "provider_snapshots": (
                        bundle.get("provider_snapshots", bundle.get("providers", []))
                        if isinstance(bundle, dict)
                        else []
                    ),
                }
            )
        )
        if normalized_bundle.forecast_id != forecast_id:
            raise ValueError("evidence bundle forecast_id must match the workspace forecast_id")
        return normalized_bundle

    def _load_evidence_bundle_collection(self, forecast_id: str) -> list[EvidenceBundle]:
        collection_payload = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "evidence_bundles")
        )
        if isinstance(collection_payload, list):
            return [
                item if isinstance(item, EvidenceBundle) else EvidenceBundle.from_dict(item)
                for item in collection_payload
            ]
        primary_payload = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "evidence_bundle")
        )
        if primary_payload is None:
            return []
        return [EvidenceBundle.from_dict(primary_payload)]

    def _write_evidence_bundle_collection(
        self,
        forecast_id: str,
        bundles: list[EvidenceBundle],
        *,
        active_bundle_id: Optional[str] = None,
    ) -> EvidenceBundle:
        if not bundles:
            raise ValueError("At least one evidence bundle is required")
        bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
        active_bundle = (
            bundle_map.get(active_bundle_id)
            if active_bundle_id is not None
            else bundles[-1]
        )
        if active_bundle is None:
            raise ValueError(f"Unknown active evidence bundle: {active_bundle_id}")
        self._write_json(
            self._get_artifact_path(forecast_id, "evidence_bundles"),
            [bundle.to_dict() for bundle in bundle_map.values()],
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "evidence_bundle"),
            active_bundle.to_dict(),
        )
        return active_bundle

    def _ensure_evidence_bundle_ids_exist(
        self,
        forecast_id: str,
        bundle_ids: list[str],
    ) -> None:
        if not bundle_ids:
            return
        existing_ids = {
            bundle.bundle_id for bundle in self._load_evidence_bundle_collection(forecast_id)
        }
        missing_ids = [bundle_id for bundle_id in bundle_ids if bundle_id not in existing_ids]
        if missing_ids:
            raise ValueError(
                "prediction entry references unknown evidence_bundle_ids: "
                + ", ".join(missing_ids)
            )

    def _ensure_not_before_question_issue(
        self,
        workspace: ForecastWorkspaceRecord,
        timestamp: str,
        context: str,
    ) -> None:
        timestamp_value = _parse_iso_temporal(timestamp)
        issue_value = _parse_iso_temporal(workspace.forecast_question.issue_timestamp)
        if timestamp_value < issue_value:
            raise ValueError(
                f"{context} timestamp cannot precede forecast question issue_timestamp"
            )

    def _workspace_exists(self, forecast_id: str) -> bool:
        return self._resolve_workspace_root(forecast_id) is not None

    def _build_manifest(self, workspace: ForecastWorkspaceRecord) -> Dict[str, Any]:
        summary = workspace.to_summary_dict()
        summary.update(
            {
                "artifact_type": "forecast_workspace_manifest",
                "generated_at": datetime.now().isoformat(),
                "artifacts": {
                    artifact_name: filename
                    for artifact_name, filename in self.ARTIFACT_FILENAMES.items()
                    if artifact_name != "simulation_worker_contract"
                    or workspace.simulation_worker_contract is not None
                },
            }
        )
        return summary

    def create_workspace(self, workspace: ForecastWorkspaceRecord) -> ForecastWorkspaceRecord:
        forecast_id = workspace.forecast_question.forecast_id
        if self._workspace_exists(forecast_id):
            raise ValueError(f"Forecast workspace already exists: {forecast_id}")
        return self.save_workspace(workspace)

    def save_workspace(self, workspace: ForecastWorkspaceRecord) -> ForecastWorkspaceRecord:
        forecast_id = workspace.forecast_question.forecast_id
        workspace.forecast_question.updated_at = _utcnow_iso()
        if workspace.simulation_worker_contract is not None and not workspace.forecast_question.primary_simulation_id:
            workspace.forecast_question.primary_simulation_id = (
                workspace.simulation_worker_contract.simulation_id
                or workspace.simulation_worker_contract.worker_id
            )
        workspace = ForecastWorkspaceRecord.from_dict(workspace.to_dict())
        self._sync_evaluation_context(workspace)

        self._write_json(
            self._get_artifact_path(forecast_id, "workspace_manifest"),
            self._build_manifest(workspace),
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "forecast_question"),
            workspace.forecast_question.to_dict(),
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "resolution_criteria"),
            [item.to_dict() for item in workspace.resolution_criteria],
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "evidence_bundle"),
            workspace.evidence_bundle.to_dict(),
        )
        existing_bundles = self._load_evidence_bundle_collection(forecast_id)
        bundle_map = {bundle.bundle_id: bundle for bundle in existing_bundles}
        bundle_map[workspace.evidence_bundle.bundle_id] = workspace.evidence_bundle
        self._write_json(
            self._get_artifact_path(forecast_id, "evidence_bundles"),
            [bundle.to_dict() for bundle in bundle_map.values()],
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "forecast_workers"),
            [item.to_dict() for item in workspace.forecast_workers],
        )
        prediction_ledger_path = self._get_artifact_path(forecast_id, "prediction_ledger")
        self._write_json(prediction_ledger_path, workspace.prediction_ledger.to_dict())
        self._write_json(
            self._get_artifact_path(forecast_id, "evaluation_cases"),
            [item.to_dict() for item in workspace.evaluation_cases],
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "forecast_answers"),
            [item.to_dict() for item in workspace.forecast_answers],
        )

        simulation_contract_path = self._get_artifact_path(
            forecast_id, "simulation_worker_contract"
        )
        if workspace.simulation_worker_contract is not None:
            self._write_json(
                simulation_contract_path, workspace.simulation_worker_contract.to_dict()
            )
        elif os.path.exists(simulation_contract_path):
            os.remove(simulation_contract_path)

        self._write_json(
            self._get_artifact_path(forecast_id, "simulation_scope"),
            workspace.simulation_scope.to_dict(),
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "lifecycle_metadata"),
            workspace.lifecycle_metadata.to_dict(),
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "resolution_record"),
            workspace.resolution_record.to_dict(),
        )
        self._write_json(
            self._get_artifact_path(forecast_id, "scoring_events"),
            [item.to_dict() for item in workspace.scoring_events],
        )

        logger.info("Saved forecast workspace %s", forecast_id)
        loaded = self.get_workspace(forecast_id)
        if loaded is None:
            raise ValueError(f"Failed to reload forecast workspace: {forecast_id}")
        return loaded

    def get_question(self, forecast_id: str) -> Optional[ForecastQuestion]:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            return None
        return workspace.forecast_question

    def create_question(self, question: ForecastQuestion) -> ForecastWorkspaceRecord:
        resolution_date = question.horizon.get("value") if isinstance(question.horizon, dict) else None
        try:
            if not isinstance(resolution_date, str) or not resolution_date:
                raise ValueError
            datetime.fromisoformat(resolution_date)
        except Exception:
            resolution_date = question.issue_timestamp.split("T", 1)[0]
        placeholder_criteria = [
            ResolutionCriteria(
                criteria_id=criteria_id,
                forecast_id=question.forecast_id,
                label=f"Resolution criteria for {question.question_text}",
                description="Placeholder resolution criteria created from the question-first flow.",
                resolution_date=resolution_date,
                criteria_type="manual",
                thresholds={},
            )
            for criteria_id in question.resolution_criteria_ids
        ]
        workspace = ForecastWorkspaceRecord(
            forecast_question=question,
            resolution_criteria=placeholder_criteria,
            evidence_bundle=EvidenceBundle(
                bundle_id=f"{question.forecast_id}-bundle",
                forecast_id=question.forecast_id,
                title="Question workspace evidence",
                summary=question.question_text,
                artifacts=[],
                question_ids=[question.forecast_id],
                prediction_entry_ids=[],
                status="draft",
                boundary_note="Placeholder evidence bundle for the question-first flow.",
                created_at=question.issue_timestamp,
            ),
            forecast_workers=[],
            prediction_ledger=PredictionLedger(forecast_id=question.forecast_id),
            evaluation_cases=[],
            forecast_answers=[],
            simulation_worker_contract=None,
        )
        if question.primary_simulation_id:
            workspace.evidence_bundle = self.evidence_bundle_service.build_bundle(
                question=question,
                existing_bundle=workspace.evidence_bundle,
                provider_ids=["uploaded_local_artifact"],
            )
        return self.create_workspace(workspace)

    def list_questions(self) -> list[ForecastQuestion]:
        return [workspace.forecast_question for workspace in self.list_workspaces()]

    def _prediction_links_for_workspace(
        self,
        workspace: ForecastWorkspaceRecord,
    ) -> list[str]:
        links: list[str] = []
        for entry in workspace.prediction_ledger.entries:
            prediction_id = entry.prediction_id or entry.entry_id
            if prediction_id and prediction_id not in links:
                links.append(prediction_id)
        return links

    def _evidence_bundle_payload(
        self,
        workspace: ForecastWorkspaceRecord,
        bundle: EvidenceBundle | Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload = workspace.evidence_bundle.to_dict()
        if isinstance(bundle, EvidenceBundle):
            payload = bundle.to_dict()
        elif isinstance(bundle, dict):
            payload.update(bundle)
        payload.setdefault("bundle_id", workspace.evidence_bundle.bundle_id)
        payload["forecast_id"] = workspace.forecast_question.forecast_id
        payload.setdefault("title", workspace.evidence_bundle.title)
        payload.setdefault(
            "summary",
            workspace.evidence_bundle.summary or workspace.forecast_question.question_text,
        )
        payload.setdefault("boundary_note", workspace.evidence_bundle.boundary_note)
        payload.setdefault("created_at", workspace.evidence_bundle.created_at)
        payload.setdefault("question_links", [workspace.forecast_question.forecast_id])
        payload.setdefault(
            "prediction_links",
            self._prediction_links_for_workspace(workspace),
        )
        if "providers" in payload and "provider_snapshots" not in payload:
            payload["provider_snapshots"] = payload["providers"]
        if "entries" in payload and "source_entries" not in payload:
            payload["source_entries"] = payload["entries"]
        return payload

    def get_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: Optional[str] = None,
    ) -> Optional[EvidenceBundle]:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            return None
        if bundle_id is not None and workspace.evidence_bundle.bundle_id != bundle_id:
            return None
        return workspace.evidence_bundle

    def list_evidence_bundles(self, forecast_id: str) -> list[EvidenceBundle]:
        bundle = self.get_evidence_bundle(forecast_id)
        return [bundle] if bundle is not None else []

    def create_evidence_bundle(
        self,
        forecast_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        workspace.evidence_bundle = EvidenceBundle.from_dict(
            self._evidence_bundle_payload(workspace, bundle)
        )
        return self.save_workspace(workspace)

    def update_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if workspace.evidence_bundle.bundle_id != bundle_id:
            raise ValueError(
                f"Unknown evidence bundle for forecast workspace: {forecast_id}/{bundle_id}"
            )
        payload = self._evidence_bundle_payload(workspace, bundle)
        payload["bundle_id"] = bundle_id
        workspace.evidence_bundle = EvidenceBundle.from_dict(payload)
        return self.save_workspace(workspace)

    def list_evidence_providers(self) -> list[Dict[str, Any]]:
        return [dict(item) for item in self.EVIDENCE_PROVIDERS]

    def _build_local_evidence_entries(
        self,
        workspace: ForecastWorkspaceRecord,
    ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        from .grounding_bundle_builder import GroundingBundleBuilder
        from .simulation_manager import SimulationManager

        simulation_id = (
            workspace.forecast_question.primary_simulation_id
            or (
                workspace.simulation_worker_contract.simulation_id
                if workspace.simulation_worker_contract is not None
                else None
            )
        )
        boundary_note = (
            "Uploaded/local artifact provider uses persisted uploads, stored graph provenance, "
            "and saved simulation artifacts only. It does not imply live external retrieval."
        )
        if not simulation_id:
            return (
                [
                    {
                        "entry_id": (
                            f"{workspace.forecast_question.forecast_id}-local-missing"
                        ),
                        "source_type": "missing_evidence",
                        "provider_id": "uploaded_local_artifact",
                        "provider_kind": "uploaded_local_artifact",
                        "title": "Local evidence scope is not linked to a simulation yet",
                        "summary": "No primary simulation is linked, so uploaded/local artifact acquisition cannot resolve scope.",
                        "captured_at": workspace.forecast_question.issue_timestamp,
                        "freshness": {"status": "unknown"},
                        "relevance": {"score": 0.2},
                        "quality_score": 0.0,
                        "conflict_status": "missing",
                        "missing_evidence_markers": ["simulation_scope_unlinked"],
                        "provenance": {"provider": "uploaded_local_artifact"},
                    }
                ],
                {
                    "provider_id": "uploaded_local_artifact",
                    "provider_kind": "uploaded_local_artifact",
                    "status": "unavailable",
                    "retrieval_quality": "bounded_local_artifacts",
                    "boundary_note": boundary_note,
                },
            )

        grounding_bundle = GroundingBundleBuilder(
            simulation_data_dir=Config.OASIS_SIMULATION_DATA_DIR
        ).load_bundle(simulation_id)
        prepare_summary = SimulationManager().get_prepare_artifact_summary(simulation_id)
        entries: list[Dict[str, Any]] = []

        generated_at = (
            grounding_bundle.get("generated_at")
            if isinstance(grounding_bundle, dict)
            else workspace.forecast_question.issue_timestamp
        )
        for item in (grounding_bundle or {}).get("evidence_items", []):
            kind = str(item.get("kind") or "").strip().lower()
            source_type = (
                "uploaded_source"
                if kind == "source"
                else "graph_provenance"
                if kind == "graph"
                else "uploaded_local_artifact"
            )
            entries.append(
                {
                    "entry_id": item.get("citation_id") or item.get("title") or source_type,
                    "source_type": source_type,
                    "provider_id": "uploaded_local_artifact",
                    "provider_kind": "uploaded_local_artifact",
                    "title": item.get("title") or source_type.replace("_", " "),
                    "summary": item.get("summary") or item.get("support_label") or "",
                    "locator": item.get("locator"),
                    "citation_id": item.get("citation_id"),
                    "captured_at": generated_at,
                    "freshness": {"status": "fresh"},
                    "relevance": {
                        "score": 0.9 if source_type == "uploaded_source" else 0.75
                    },
                    "quality_score": 0.78 if source_type == "uploaded_source" else 0.72,
                    "conflict_status": "supports",
                    "missing_evidence_markers": [],
                    "provenance": {
                        "provider": "uploaded_local_artifact",
                        "artifact_type": "grounding_bundle",
                        "simulation_id": simulation_id,
                    },
                }
            )

        prepared_snapshot = (
            (prepare_summary or {}).get("prepared_artifacts", {}) or {}
        ).get("prepared_snapshot")
        if isinstance(prepared_snapshot, dict) and prepared_snapshot.get("exists"):
            entries.append(
                {
                    "entry_id": f"{simulation_id}-prepared-snapshot",
                    "source_type": "prepared_snapshot",
                    "provider_id": "uploaded_local_artifact",
                    "provider_kind": "uploaded_local_artifact",
                    "title": "Prepared simulation snapshot",
                    "summary": "Stored simulation prepare artifact linked to the forecast question scope.",
                    "locator": prepared_snapshot.get("relative_path")
                    or prepared_snapshot.get("filename"),
                    "captured_at": workspace.forecast_question.issue_timestamp,
                    "freshness": {"status": "fresh"},
                    "relevance": {"score": 0.65},
                    "quality_score": 0.6,
                    "conflict_status": "supports",
                    "missing_evidence_markers": [],
                    "provenance": {
                        "provider": "uploaded_local_artifact",
                        "artifact_type": "prepared_snapshot",
                        "simulation_id": simulation_id,
                    },
                }
            )

        provider_status = {
            "provider_id": "uploaded_local_artifact",
            "provider_kind": "uploaded_local_artifact",
            "status": "ready" if entries else "unavailable",
            "retrieval_quality": "bounded_local_artifacts",
            "boundary_note": (
                (grounding_bundle or {}).get("boundary_note") if isinstance(grounding_bundle, dict) else None
            )
            or boundary_note,
        }
        return entries, provider_status

    def _build_live_external_placeholder(
        self,
        workspace: ForecastWorkspaceRecord,
        live_provider_request: Optional[Dict[str, Any]] = None,
    ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        return (
            [
                {
                    "entry_id": f"{workspace.forecast_question.forecast_id}-live-external-gap",
                    "source_type": "missing_evidence",
                    "provider_id": "live_external",
                    "provider_kind": "live_external",
                    "title": "Live external evidence unavailable",
                    "summary": "No live external retrieval adapter is configured in this environment.",
                    "captured_at": workspace.forecast_question.issue_timestamp,
                    "freshness": {"status": "unknown"},
                    "relevance": {"score": 0.4},
                    "quality_score": 0.0,
                    "conflict_status": "missing",
                    "missing_evidence_markers": ["live_external_provider_unconfigured"],
                    "provenance": {
                        "provider": "live_external",
                        "adapter_status": "unconfigured",
                        "request": live_provider_request or {},
                    },
                }
            ],
            {
                "provider_id": "live_external",
                "provider_kind": "live_external",
                "status": "unavailable",
                "retrieval_quality": "not_configured",
                "boundary_note": (
                    "Live external evidence is pluggable, but no provider is configured in this environment."
                ),
            },
        )

    def acquire_evidence_bundle(
        self,
        forecast_id: str,
        *,
        bundle_id: Optional[str] = None,
        provider_ids: Optional[list[str]] = None,
        include_live_external: bool = False,
        live_provider_request: Optional[Dict[str, Any]] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        requested_provider_ids = list(provider_ids or ["uploaded_local_artifact"])
        if include_live_external and "live_external" not in requested_provider_ids:
            requested_provider_ids.append("live_external")

        preserved_entries = [
            entry.to_dict()
            for entry in workspace.evidence_bundle.source_entries
            if entry.provider_id not in requested_provider_ids
        ]
        preserved_providers = [
            dict(item)
            for item in workspace.evidence_bundle.provider_snapshots
            if item.get("provider_id") not in requested_provider_ids
        ]

        refreshed_entries = list(preserved_entries)
        refreshed_providers = list(preserved_providers)
        if "uploaded_local_artifact" in requested_provider_ids:
            entries, provider = self._build_local_evidence_entries(workspace)
            refreshed_entries.extend(entries)
            refreshed_providers.append(provider)
        if "live_external" in requested_provider_ids:
            entries, provider = self._build_live_external_placeholder(
                workspace,
                live_provider_request=live_provider_request,
            )
            refreshed_entries.extend(entries)
            refreshed_providers.append(provider)

        payload = self._evidence_bundle_payload(
            workspace,
            {
                "bundle_id": bundle_id or workspace.evidence_bundle.bundle_id,
                "source_entries": refreshed_entries,
                "provider_snapshots": refreshed_providers,
                "status": "draft",
            },
        )
        workspace.evidence_bundle = EvidenceBundle.from_dict(payload)
        return self.save_workspace(workspace)

    def refresh_evidence_bundle(
        self,
        forecast_id: str,
        *,
        include_live_external: bool = False,
        live_provider_request: Optional[Dict[str, Any]] = None,
    ) -> ForecastWorkspaceRecord:
        return self.acquire_evidence_bundle(
            forecast_id,
            include_live_external=include_live_external,
            live_provider_request=live_provider_request,
        )

    def get_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: Optional[str] = None,
    ) -> Optional[EvidenceBundle]:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            return None
        if bundle_id is not None and workspace.evidence_bundle.bundle_id != bundle_id:
            return None
        return workspace.evidence_bundle

    def list_evidence_bundles(self, forecast_id: str) -> list[EvidenceBundle]:
        bundle = self.get_evidence_bundle(forecast_id)
        return [bundle] if bundle is not None else []

    def create_evidence_bundle(
        self,
        forecast_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if workspace.evidence_bundle.source_entries:
            raise ValueError(f"Evidence bundle already exists for forecast workspace: {forecast_id}")
        return self.update_evidence_bundle(
            forecast_id,
            workspace.evidence_bundle.bundle_id,
            bundle,
        )

    def update_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if workspace.evidence_bundle.bundle_id != bundle_id:
            raise ValueError(f"Unknown evidence bundle for forecast workspace: {forecast_id}/{bundle_id}")
        if not isinstance(bundle, EvidenceBundle):
            payload = dict(workspace.evidence_bundle.to_dict())
            payload.update(dict(bundle))
            payload["bundle_id"] = bundle_id
            payload["forecast_id"] = forecast_id
            payload.setdefault("created_at", workspace.evidence_bundle.created_at)
            bundle = EvidenceBundle.from_dict(payload)
        if bundle.forecast_id != forecast_id:
            raise ValueError("evidence bundle forecast_id must match the workspace forecast_id")
        bundle.question_ids = sorted(set(bundle.question_ids + [forecast_id]))
        workspace.evidence_bundle = bundle
        return self.save_workspace(workspace)

    def acquire_evidence_bundle(
        self,
        forecast_id: str,
        *,
        bundle_id: Optional[str] = None,
        provider_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        active_bundle_id = bundle_id or workspace.evidence_bundle.bundle_id
        if workspace.evidence_bundle.bundle_id != active_bundle_id:
            raise ValueError(f"Unknown evidence bundle for forecast workspace: {forecast_id}/{active_bundle_id}")
        service = EvidenceBundleOrchestrator()
        workspace.evidence_bundle = service.build_bundle(
            question=workspace.forecast_question,
            existing_bundle=workspace.evidence_bundle,
            bundle_id=active_bundle_id,
            provider_ids=provider_ids,
        )
        linked_prediction_entry_ids = {
            entry.entry_id
            for entry in workspace.prediction_ledger.entries
            if active_bundle_id in entry.evidence_bundle_ids
        }
        linked_prediction_entry_ids.update(workspace.evidence_bundle.prediction_entry_ids)
        workspace.evidence_bundle.question_ids = [workspace.forecast_question.forecast_id]
        workspace.evidence_bundle.prediction_entry_ids = sorted(linked_prediction_entry_ids)
        return self.save_workspace(workspace)

    def refresh_evidence_bundle(
        self,
        forecast_id: str,
        *,
        bundle_id: Optional[str] = None,
        include_live_external: bool = False,
        live_provider_request: Optional[Dict[str, Any]] = None,
        provider_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        selected_provider_ids = list(provider_ids or ["uploaded_local_artifact"])
        if include_live_external and "live_external" not in selected_provider_ids:
            selected_provider_ids.append("live_external")
        return self.acquire_evidence_bundle(
            forecast_id,
            bundle_id=bundle_id,
            provider_ids=selected_provider_ids,
        )

    def list_evidence_providers(self) -> list[Dict[str, Any]]:
        return EvidenceBundleOrchestrator().list_provider_capabilities()

    def list_question_summaries_for_simulation(
        self,
        simulation_id: str,
    ) -> list[Dict[str, Any]]:
        normalized_simulation_id = str(simulation_id or "").strip()
        if not normalized_simulation_id:
            return []

        summaries: list[Dict[str, Any]] = []
        for workspace in self.list_workspaces():
            if workspace.forecast_question.primary_simulation_id != normalized_simulation_id:
                continue
            summaries.append(
                {
                    "forecast_id": workspace.forecast_question.forecast_id,
                    "title": workspace.forecast_question.title,
                    "question_text": workspace.forecast_question.question_text,
                    "question_status": workspace.forecast_question.status,
                    "issue_timestamp": workspace.forecast_question.issue_timestamp,
                    "resolution_status": workspace.prediction_ledger.resolution_status,
                    "prediction_entry_count": len(workspace.prediction_ledger.entries),
                    "worker_kinds": [worker.kind for worker in workspace.forecast_workers],
                }
            )
        return summaries

    def update_question(
        self,
        forecast_id: str,
        question: ForecastQuestion | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if isinstance(question, dict):
            question_payload = {**workspace.forecast_question.to_dict(), **question}
            if "question_text" in question and "question" not in question:
                question_payload["question"] = question["question_text"]
            question_payload["forecast_id"] = forecast_id
            question_payload["project_id"] = workspace.forecast_question.project_id
            question_payload["created_at"] = workspace.forecast_question.created_at
            question_payload["issue_timestamp"] = workspace.forecast_question.issue_timestamp
            question = ForecastQuestion.from_dict(question_payload)
        if question.forecast_id != forecast_id:
            raise ValueError("question forecast_id must match the workspace forecast_id")
        question.updated_at = datetime.now().isoformat()
        updated_workspace = ForecastWorkspaceRecord(
            forecast_question=question,
            resolution_criteria=workspace.resolution_criteria,
            evidence_bundle=workspace.evidence_bundle,
            forecast_workers=workspace.forecast_workers,
            prediction_ledger=workspace.prediction_ledger,
            evaluation_cases=workspace.evaluation_cases,
            forecast_answers=workspace.forecast_answers,
            simulation_worker_contract=workspace.simulation_worker_contract,
            schema_version=workspace.schema_version,
            generator_version=workspace.generator_version,
        )
        return self.save_workspace(updated_workspace)

    def resolve_forecast(
        self,
        forecast_id: str,
        resolution_state: Dict[str, Any] | str,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if (
            workspace.forecast_question.status == "resolved"
            or workspace.prediction_ledger.final_resolution_state not in {"pending", "open"}
        ):
            raise ValueError("forecast question is already resolved")
        normalized_resolution_state = dict(resolution_state or {}) if isinstance(resolution_state, dict) else {
            "final_resolution_state": resolution_state,
        }
        requested_status = normalized_resolution_state.get("final_resolution_state")
        if isinstance(requested_status, dict):
            requested_status = requested_status.get("status")
        if requested_status is None:
            requested_status = normalized_resolution_state.get("status", "resolved")
        normalized_resolution_state["final_resolution_state"] = requested_status
        normalized_resolution_state.setdefault("status", requested_status)
        normalized_resolution_state.setdefault("resolved_at", datetime.now().isoformat())
        if normalized_resolution_state.get("resolved_at") is not None:
            self._ensure_not_before_question_issue(
                workspace,
                str(normalized_resolution_state["resolved_at"]),
                "resolution",
            )
            resolved_value = _parse_iso_temporal(str(normalized_resolution_state["resolved_at"]))
            for entry in workspace.prediction_ledger.entries:
                if _parse_iso_temporal(entry.recorded_at) > resolved_value:
                    raise ValueError("resolution timestamp cannot precede existing prediction history")
        workspace.prediction_ledger.record_resolution_state(normalized_resolution_state)
        normalized_status = str(workspace.prediction_ledger.final_resolution_state or requested_status)
        if normalized_status in {"resolved", "resolved_true", "resolved_false"}:
            workspace.forecast_question.status = "resolved"
        elif normalized_status in {"pending", "open"}:
            workspace.forecast_question.status = "active"
        else:
            workspace.forecast_question.status = "archived"
        workspace.forecast_question.updated_at = datetime.now().isoformat()
        return self.save_workspace(workspace)

    def resolve_question(
        self,
        forecast_id: str,
        resolution_state: Dict[str, Any] | str,
    ) -> ForecastWorkspaceRecord:
        return self.resolve_forecast(forecast_id, resolution_state)

    def get_prediction_ledger(self, forecast_id: str) -> PredictionLedger:
        workspace = self._require_workspace(forecast_id)
        return workspace.prediction_ledger

    def get_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: Optional[str] = None,
    ) -> Optional[EvidenceBundle]:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            return None
        if bundle_id is None:
            return workspace.evidence_bundle
        for bundle in self._load_evidence_bundle_collection(forecast_id):
            if bundle.bundle_id == bundle_id:
                return bundle
        return None

    def list_evidence_bundles(self, forecast_id: str) -> list[EvidenceBundle]:
        self._require_workspace(forecast_id)
        return self._load_evidence_bundle_collection(forecast_id)

    def create_evidence_bundle(
        self,
        forecast_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        normalized_bundle = self._normalize_evidence_bundle(bundle, forecast_id=forecast_id)
        existing_bundles = self._load_evidence_bundle_collection(forecast_id)
        if any(existing.bundle_id == normalized_bundle.bundle_id for existing in existing_bundles):
            raise ValueError(f"Evidence bundle already exists: {normalized_bundle.bundle_id}")
        existing_bundles.append(normalized_bundle)
        workspace.evidence_bundle = self._write_evidence_bundle_collection(
            forecast_id,
            existing_bundles,
            active_bundle_id=normalized_bundle.bundle_id,
        )
        return self.save_workspace(workspace)

    def update_evidence_bundle(
        self,
        forecast_id: str,
        bundle_id: str,
        bundle: EvidenceBundle | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        existing_bundles = self._load_evidence_bundle_collection(forecast_id)
        existing_bundle = next(
            (item for item in existing_bundles if item.bundle_id == bundle_id),
            None,
        )
        if existing_bundle is None:
            raise ValueError(f"Unknown evidence bundle: {bundle_id}")
        if isinstance(bundle, dict):
            merged_payload = existing_bundle.to_dict()
            merged_payload.update(bundle)
            if "entries" in bundle and "source_entries" not in bundle:
                merged_payload["source_entries"] = bundle.get("entries", [])
            if "providers" in bundle and "provider_snapshots" not in bundle:
                merged_payload["provider_snapshots"] = bundle.get("providers", [])
            merged_payload["bundle_id"] = bundle_id
            merged_payload["forecast_id"] = forecast_id
            normalized_bundle = EvidenceBundle.from_dict(merged_payload)
        else:
            normalized_bundle = bundle
        normalized_bundle = self._normalize_evidence_bundle(
            normalized_bundle, forecast_id=forecast_id
        )
        bundle_map = {item.bundle_id: item for item in existing_bundles}
        bundle_map[bundle_id] = normalized_bundle
        workspace.evidence_bundle = self._write_evidence_bundle_collection(
            forecast_id,
            list(bundle_map.values()),
            active_bundle_id=bundle_id,
        )
        return self.save_workspace(workspace)

    def acquire_evidence_bundle(
        self,
        forecast_id: str,
        *,
        bundle_id: Optional[str] = None,
        provider_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        selected_provider_ids = provider_ids or ["uploaded_local_artifacts"]
        existing_bundle = self.get_evidence_bundle(
            forecast_id,
            bundle_id=bundle_id or workspace.evidence_bundle.bundle_id,
        )
        refreshed_bundle = self.evidence_bundle_service.build_bundle(
            question=workspace.forecast_question,
            existing_bundle=existing_bundle,
            bundle_id=bundle_id or workspace.evidence_bundle.bundle_id,
            provider_ids=selected_provider_ids,
        )
        refreshed_bundle.question_ids = [workspace.forecast_question.forecast_id]
        linked_prediction_entry_ids = {
            entry.entry_id
            for entry in workspace.prediction_ledger.entries
            if refreshed_bundle.bundle_id in entry.evidence_bundle_ids
        }
        if existing_bundle is not None:
            linked_prediction_entry_ids.update(existing_bundle.prediction_entry_ids)
        refreshed_bundle.prediction_entry_ids = sorted(linked_prediction_entry_ids)
        refreshed_bundle._finalize_derived_fields()
        return self.update_evidence_bundle(
            forecast_id,
            refreshed_bundle.bundle_id,
            refreshed_bundle,
        )

    def refresh_evidence_bundle(
        self,
        forecast_id: str,
        *,
        include_live_external: bool = False,
        live_provider_request: Optional[Dict[str, Any]] = None,
    ) -> ForecastWorkspaceRecord:
        provider_ids = ["uploaded_local_artifacts"]
        if include_live_external:
            provider_ids.append("external_live_unconfigured")
        # live_provider_request is accepted for forward compatibility; the
        # default provider keeps graceful unavailability explicit in this environment.
        _ = live_provider_request
        return self.acquire_evidence_bundle(
            forecast_id,
            provider_ids=provider_ids,
        )

    def list_evidence_providers(self) -> list[Dict[str, Any]]:
        return self.evidence_bundle_service.list_provider_capabilities()

    def get_workspace(self, forecast_id: str) -> Optional[ForecastWorkspaceRecord]:
        if self._resolve_workspace_root(forecast_id) is None:
            return None
        forecast_question_payload = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "forecast_question")
        )
        if forecast_question_payload is None:
            return None

        resolution_criteria = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "resolution_criteria")
        ) or []
        evidence_bundle = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "evidence_bundle")
        )
        if evidence_bundle is None:
            bundle_collection = self._load_evidence_bundle_collection(forecast_id)
            if bundle_collection:
                evidence_bundle = bundle_collection[-1].to_dict()
        if evidence_bundle is None:
            raise ValueError(f"Missing evidence_bundle.json for forecast workspace {forecast_id}")

        forecast_workers = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "forecast_workers")
        ) or []
        prediction_ledger = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "prediction_ledger")
        ) or {
            "forecast_id": forecast_id,
            "entries": [],
            "worker_outputs": [],
            "resolution_history": [],
            "final_resolution_state": "pending",
        }
        evaluation_cases = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "evaluation_cases")
        ) or []
        forecast_answers = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "forecast_answers")
        ) or []
        simulation_worker_contract = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "simulation_worker_contract")
        )
        simulation_scope = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "simulation_scope")
        )
        lifecycle_metadata = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "lifecycle_metadata")
        )
        resolution_record = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "resolution_record")
        )
        scoring_events = self._read_json_if_exists(
            self._get_artifact_path(forecast_id, "scoring_events")
        ) or []

        return ForecastWorkspaceRecord(
            forecast_question=forecast_question_payload,
            resolution_criteria=resolution_criteria,
            evidence_bundle=evidence_bundle,
            forecast_workers=forecast_workers,
            prediction_ledger=prediction_ledger,
            evaluation_cases=evaluation_cases,
            forecast_answers=forecast_answers,
            simulation_worker_contract=simulation_worker_contract,
            simulation_scope=simulation_scope,
            lifecycle_metadata=lifecycle_metadata,
            resolution_record=resolution_record,
            scoring_events=scoring_events,
        )

    @staticmethod
    def _merge_string_lists(existing: list[str], additions: list[str]) -> list[str]:
        merged: list[str] = []
        for item in list(existing) + list(additions):
            normalized = str(item or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        return merged

    def attach_simulation_scope(
        self,
        forecast_id: str,
        *,
        simulation_id: Optional[str] = None,
        prepare_artifact_paths: Optional[list[str]] = None,
        ensemble_ids: Optional[list[str]] = None,
        run_ids: Optional[list[str]] = None,
        latest_ensemble_id: Optional[str] = None,
        latest_run_id: Optional[str] = None,
        prepare_status: Optional[str] = None,
        prepare_task_id: Optional[str] = None,
        source_stage: Optional[str] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            raise ValueError(f"Forecast workspace does not exist: {forecast_id}")

        scope = workspace.simulation_scope or ForecastSimulationScope(forecast_id=forecast_id)
        if simulation_id is not None:
            scope.simulation_id = str(simulation_id).strip() or None
        if prepare_artifact_paths:
            scope.prepare_artifact_paths = self._merge_string_lists(
                scope.prepare_artifact_paths,
                prepare_artifact_paths,
            )
        if ensemble_ids:
            scope.ensemble_ids = self._merge_string_lists(scope.ensemble_ids, ensemble_ids)
        if run_ids:
            scope.run_ids = self._merge_string_lists(scope.run_ids, run_ids)
        if latest_ensemble_id is not None:
            scope.latest_ensemble_id = str(latest_ensemble_id).strip() or None
        elif ensemble_ids:
            scope.latest_ensemble_id = self._merge_string_lists([], ensemble_ids)[-1]
        if latest_run_id is not None:
            scope.latest_run_id = str(latest_run_id).strip() or None
        elif run_ids:
            scope.latest_run_id = self._merge_string_lists([], run_ids)[-1]
        if prepare_status is not None:
            scope.prepare_status = str(prepare_status).strip()
        if prepare_task_id is not None:
            scope.prepare_task_id = str(prepare_task_id).strip() or None
        if source_stage is not None:
            scope.last_attached_stage = str(source_stage).strip() or None
        scope.updated_at = datetime.now().isoformat()

        workspace.simulation_scope = scope
        if scope.simulation_id:
            workspace.forecast_question.primary_simulation_id = scope.simulation_id
            if workspace.simulation_worker_contract is not None:
                workspace.simulation_worker_contract.simulation_id = scope.simulation_id
                workspace.simulation_worker_contract.prepare_artifact_paths = list(
                    scope.prepare_artifact_paths
                )
                workspace.simulation_worker_contract.ensemble_ids = list(scope.ensemble_ids)
        return self.save_workspace(workspace)

    def list_workspaces(self) -> list[ForecastWorkspaceRecord]:
        workspaces: list[ForecastWorkspaceRecord] = []
        for entry in sorted(os.listdir(self.forecast_data_dir)):
            workspace_dir = os.path.join(self.forecast_data_dir, entry)
            if not os.path.isdir(workspace_dir):
                continue
            workspace = self.get_workspace(entry)
            if workspace is not None:
                workspaces.append(workspace)
        return workspaces

    def list_question_summaries_for_simulation(self, simulation_id: str) -> list[Dict[str, Any]]:
        return [
            workspace.to_summary_dict()
            for workspace in self.list_workspaces()
            if workspace.forecast_question.primary_simulation_id == simulation_id
        ]

    def register_worker(
        self,
        forecast_id: str,
        worker: ForecastWorker,
        simulation_worker_contract: Optional[SimulationWorkerContract] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if worker.forecast_id != forecast_id:
            raise ValueError("worker forecast_id must match the workspace forecast_id")

        worker_map = {item.worker_id: item for item in workspace.forecast_workers}
        worker_map[worker.worker_id] = worker
        workspace.forecast_workers = list(worker_map.values())

        if simulation_worker_contract is not None:
            if worker.kind != "simulation":
                raise ValueError("simulation_worker_contract requires a simulation worker")
            if simulation_worker_contract.forecast_id != forecast_id:
                raise ValueError(
                    "simulation_worker_contract forecast_id must match the workspace forecast_id"
                )
            workspace.simulation_worker_contract = simulation_worker_contract
            if simulation_worker_contract.simulation_id is not None:
                workspace.forecast_question.primary_simulation_id = (
                    simulation_worker_contract.simulation_id
                )
        elif worker.kind == "simulation" and not workspace.forecast_question.primary_simulation_id:
            workspace.forecast_question.primary_simulation_id = worker.worker_id

        return self.save_workspace(workspace)

    def append_prediction_entry(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        if entry.entry_kind == "revision" or entry.revises_entry_id or entry.revises_prediction_id:
            return self.revise_prediction(forecast_id, entry)
        return self.issue_prediction(forecast_id, entry)

    def issue_prediction(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if entry.forecast_id != forecast_id:
            raise ValueError("prediction entry forecast_id must match the workspace forecast_id")
        if workspace.forecast_question.status == "resolved":
            raise ValueError("resolved forecast questions cannot accept new predictions")
        if not entry.evidence_bundle_ids and workspace.evidence_bundle.bundle_id:
            entry.evidence_bundle_ids = [workspace.evidence_bundle.bundle_id]
        self._ensure_evidence_bundle_ids_exist(forecast_id, entry.evidence_bundle_ids)
        self._ensure_not_before_question_issue(
            workspace,
            entry.recorded_at,
            "prediction",
        )
        self._validate_prediction_entry_for_workspace(workspace, entry)
        entry.entry_kind = "issue"
        entry.revision_number = max(entry.revision_number, 1)
        entry.revises_prediction_id = None
        entry.revises_entry_id = None
        entry.prediction_id = entry.prediction_id or entry.entry_id
        workspace.prediction_ledger.record_issued_prediction(entry)
        self._link_evidence_bundle_prediction_entry(workspace, entry)
        return self.save_workspace(workspace)

    def revise_prediction(
        self,
        forecast_id: str,
        entry: PredictionLedgerEntry,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if entry.forecast_id != forecast_id:
            raise ValueError("prediction entry forecast_id must match the workspace forecast_id")
        if workspace.forecast_question.status == "resolved":
            raise ValueError("resolved forecast questions cannot accept new prediction revisions")
        revision_target = entry.revises_entry_id or entry.revises_prediction_id
        if revision_target is None:
            raise ValueError("revision entries must declare revises_prediction_id")
        if not entry.evidence_bundle_ids and workspace.evidence_bundle.bundle_id:
            entry.evidence_bundle_ids = [workspace.evidence_bundle.bundle_id]
        self._ensure_evidence_bundle_ids_exist(forecast_id, entry.evidence_bundle_ids)
        self._ensure_not_before_question_issue(
            workspace,
            entry.recorded_at,
            "prediction revision",
        )
        self._validate_prediction_entry_for_workspace(workspace, entry)
        entry.entry_kind = "revision"
        base_entry = workspace.prediction_ledger.find_entry(revision_target)
        if base_entry is None:
            raise ValueError(f"Unknown prediction entry for revision: {revision_target}")
        entry.revision_number = max(entry.revision_number, base_entry.revision_number + 1)
        entry.revises_entry_id = base_entry.entry_id
        entry.revises_prediction_id = base_entry.prediction_id
        entry.prediction_id = entry.prediction_id or entry.entry_id
        workspace.prediction_ledger.record_prediction_revision(entry)
        self._link_evidence_bundle_prediction_entry(workspace, entry)
        return self.save_workspace(workspace)

    def record_worker_output(
        self,
        forecast_id: str,
        worker_output: Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if not isinstance(worker_output, dict):
            raise ValueError("worker_output must be a dictionary")
        if worker_output.get("forecast_id") not in (None, forecast_id):
            raise ValueError("worker_output forecast_id must match the workspace forecast_id")
        normalized_output = dict(worker_output)
        normalized_output.setdefault("forecast_id", forecast_id)
        normalized_output.setdefault("recorded_at", datetime.now().isoformat())
        self._ensure_not_before_question_issue(
            workspace,
            normalized_output["recorded_at"],
            "worker output",
        )
        workspace.prediction_ledger.record_worker_output(normalized_output)
        return self.save_workspace(workspace)

    def get_prediction_history(
        self,
        forecast_id: str,
        prediction_id: str,
    ) -> list[PredictionLedgerEntry]:
        workspace = self._require_workspace(forecast_id)
        return workspace.prediction_ledger.history_for_prediction(prediction_id)

    def append_evaluation_case(
        self,
        forecast_id: str,
        case: EvaluationCase,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if case.forecast_id != forecast_id:
            raise ValueError("evaluation case forecast_id must match the workspace forecast_id")
        if case.issued_at is not None:
            self._ensure_not_before_question_issue(workspace, case.issued_at, "evaluation case")
        self._validate_evaluation_case_for_workspace(workspace, case)
        workspace.evaluation_cases.append(case)
        self._sync_evaluation_context(workspace)
        return self.save_workspace(workspace)

    def list_evaluation_cases(self, forecast_id: str) -> list[EvaluationCase]:
        workspace = self._require_workspace(forecast_id)
        return list(workspace.evaluation_cases)

    def get_evaluation_case(
        self,
        forecast_id: str,
        case_id: str,
    ) -> Optional[EvaluationCase]:
        workspace = self._require_workspace(forecast_id)
        normalized_case_id = str(case_id).strip()
        for case in workspace.evaluation_cases:
            if case.case_id == normalized_case_id:
                return case
        return None

    def update_evaluation_case(
        self,
        forecast_id: str,
        case_id: str,
        case: EvaluationCase | Dict[str, Any],
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        normalized_case_id = str(case_id).strip()
        replacement = case if isinstance(case, EvaluationCase) else EvaluationCase.from_dict(case)
        if replacement.forecast_id != forecast_id:
            raise ValueError("evaluation case forecast_id must match the workspace forecast_id")
        if replacement.case_id != normalized_case_id:
            raise ValueError("evaluation case case_id must match the requested case_id")
        if replacement.issued_at is not None:
            self._ensure_not_before_question_issue(workspace, replacement.issued_at, "evaluation case")
        if replacement.status == "resolved" and replacement.resolved_at is not None:
            self._ensure_not_before_question_issue(workspace, replacement.resolved_at, "evaluation case")
        self._validate_evaluation_case_for_workspace(workspace, replacement)
        updated_cases: list[EvaluationCase] = []
        replaced = False
        for existing in workspace.evaluation_cases:
            if existing.case_id == normalized_case_id:
                updated_cases.append(replacement)
                replaced = True
            else:
                updated_cases.append(existing)
        if not replaced:
            raise ValueError(f"Unknown evaluation case for forecast workspace: {forecast_id}/{case_id}")
        workspace.evaluation_cases = updated_cases
        self._sync_evaluation_context(workspace)
        return self.save_workspace(workspace)

    def resolve_evaluation_case(
        self,
        forecast_id: str,
        case_id: str,
        *,
        observed_outcome: Any = None,
        resolved_at: Optional[str] = None,
        resolution_note: Optional[str] = None,
        answer_id: Optional[str] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        current = self.get_evaluation_case(forecast_id, case_id)
        if current is None:
            raise ValueError(f"Unknown evaluation case for forecast workspace: {forecast_id}/{case_id}")
        payload = current.to_dict()
        payload.update(
            {
                "status": "resolved",
                "observed_outcome": observed_outcome if observed_outcome is not None else current.observed_outcome,
                "resolved_at": resolved_at or datetime.now().isoformat(),
                "resolution_note": resolution_note if resolution_note is not None else current.resolution_note,
                "answer_id": answer_id if answer_id is not None else current.answer_id,
                "confidence_basis": {
                    **dict(current.confidence_basis),
                    "status": "resolved",
                    "workspace_forecast_id": forecast_id,
                    "resolved_at": resolved_at or datetime.now().isoformat(),
                },
            }
        )
        if "observed_value" not in payload or payload.get("observed_value") is None:
            payload["observed_value"] = payload.get("observed_outcome")
        replacement = EvaluationCase.from_dict(payload)
        return self.update_evaluation_case(forecast_id, case_id, replacement)

    def append_forecast_answer(
        self,
        forecast_id: str,
        answer: ForecastAnswer,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if answer.forecast_id != forecast_id:
            raise ValueError("forecast answer forecast_id must match the workspace forecast_id")
        workspace.forecast_answers.append(answer)
        self._sync_forecast_answer_context(workspace, answer)
        return self.save_workspace(workspace)

    def generate_hybrid_forecast_answer(
        self,
        forecast_id: str,
        *,
        requested_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        workspace = self._require_workspace(forecast_id)
        if workspace.prediction_ledger.resolution_status not in {"pending", "open"}:
            raise ValueError("resolved forecast questions cannot accept new hybrid forecast answers")

        execution = self.hybrid_forecast_service.execute(
            workspace,
            requested_at=requested_at,
            worker_ids=worker_ids,
            comparable_workspaces=[
                item
                for item in self.list_workspaces()
                if item.forecast_question.forecast_id != forecast_id
                and item.prediction_ledger.resolution_status not in {"pending", "open"}
            ],
        )

        worker_map = {item.worker_id: item for item in workspace.forecast_workers}
        for worker in execution.registered_workers:
            worker_map[worker.worker_id] = worker
        workspace.forecast_workers = list(worker_map.values())

        for worker_output in execution.worker_outputs:
            self._ensure_not_before_question_issue(
                workspace,
                worker_output["recorded_at"],
                "worker output",
            )
            workspace.prediction_ledger.record_worker_output(worker_output)

        for entry in execution.prediction_entries:
            self._ensure_evidence_bundle_ids_exist(forecast_id, entry.evidence_bundle_ids)
            self._ensure_not_before_question_issue(
                workspace,
                entry.recorded_at,
                "hybrid forecast entry",
            )
            if entry.entry_kind == "revision":
                workspace.prediction_ledger.record_prediction_revision(entry)
            else:
                workspace.prediction_ledger.record_issued_prediction(entry)
            self._link_evidence_bundle_prediction_entry(workspace, entry)
            self._sync_prediction_ledger_entry_context(workspace, entry)

        if execution.forecast_answer.forecast_id != forecast_id:
            raise ValueError("generated forecast answer forecast_id must match the workspace forecast_id")
        workspace.forecast_answers.append(execution.forecast_answer)
        self._sync_forecast_answer_context(workspace, execution.forecast_answer)
        workspace.forecast_question.updated_at = datetime.now().isoformat()
        return self.save_workspace(workspace)

    def generate_hybrid_answer(
        self,
        forecast_id: str,
        *,
        issued_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        return self.generate_hybrid_forecast_answer(
            forecast_id,
            requested_at=issued_at,
            worker_ids=worker_ids,
        )

    def compose_hybrid_forecast_answer(
        self,
        forecast_id: str,
        *,
        recorded_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        return self.generate_hybrid_forecast_answer(
            forecast_id,
            requested_at=recorded_at,
            worker_ids=worker_ids,
        )

    def list_forecast_answers(self, forecast_id: str) -> list[ForecastAnswer]:
        workspace = self._require_workspace(forecast_id)
        return list(workspace.forecast_answers)

    def generate_hybrid_answer(
        self,
        forecast_id: str,
        *,
        issued_at: Optional[str] = None,
        worker_ids: Optional[list[str]] = None,
    ) -> ForecastWorkspaceRecord:
        return self.generate_hybrid_forecast_answer(
            forecast_id,
            requested_at=issued_at,
            worker_ids=worker_ids,
        )

    def _require_workspace(self, forecast_id: str) -> ForecastWorkspaceRecord:
        workspace = self.get_workspace(forecast_id)
        if workspace is None:
            raise ValueError(f"Unknown forecast workspace: {forecast_id}")
        return workspace

    @staticmethod
    def _link_evidence_bundle_prediction_entry(
        workspace: ForecastWorkspaceRecord,
        entry: PredictionLedgerEntry,
    ) -> None:
        if workspace.evidence_bundle.bundle_id not in entry.evidence_bundle_ids:
            return
        linked_question_ids = set(workspace.evidence_bundle.question_ids)
        linked_question_ids.add(workspace.forecast_question.forecast_id)
        workspace.evidence_bundle.question_ids = sorted(linked_question_ids)

        linked_prediction_entry_ids = set(workspace.evidence_bundle.prediction_entry_ids)
        linked_prediction_entry_ids.add(entry.entry_id)
        workspace.evidence_bundle.prediction_entry_ids = sorted(linked_prediction_entry_ids)

    @staticmethod
    def _sync_evaluation_context(workspace: ForecastWorkspaceRecord) -> None:
        for entry in workspace.prediction_ledger.entries:
            ForecastManager._sync_prediction_ledger_entry_context(workspace, entry)

    @staticmethod
    def _sync_prediction_ledger_entry_context(
        workspace: ForecastWorkspaceRecord,
        entry: PredictionLedgerEntry,
    ) -> None:
        linked_case_ids = [
            case.case_id
            for case in workspace.evaluation_cases
            if case.prediction_entry_id in {entry.entry_id, entry.prediction_id}
        ]
        if linked_case_ids:
            entry.evaluation_case_ids = sorted(set(entry.evaluation_case_ids + linked_case_ids))
            entry.metadata["evaluation_case_ids"] = list(entry.evaluation_case_ids)
        entry.evaluation_summary.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )
        entry.evaluation_summary["evaluation_case_count"] = len(workspace.evaluation_cases)
        entry.benchmark_summary.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )
        entry.confidence_basis.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )
        entry.confidence_basis.setdefault(
            "status",
            "available" if entry.evaluation_case_ids else "unavailable",
        )
        entry.confidence_basis["evaluation_case_count"] = len(workspace.evaluation_cases)
        entry.metadata.setdefault("confidence_basis", dict(entry.confidence_basis))
        entry.metadata.setdefault("evaluation_summary", dict(entry.evaluation_summary))
        entry.metadata.setdefault("benchmark_summary", dict(entry.benchmark_summary))

    @staticmethod
    def _sync_forecast_answer_context(
        workspace: ForecastWorkspaceRecord,
        answer: ForecastAnswer,
    ) -> None:
        answer.confidence_basis.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )
        answer.evaluation_summary.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )
        answer.benchmark_summary.setdefault(
            "workspace_forecast_id", workspace.forecast_question.forecast_id
        )

    @staticmethod
    def _question_prediction_contract(
        question_type: str,
    ) -> tuple[set[str], set[str]]:
        return (
            set(QUESTION_TYPE_PREDICTION_VALUE_TYPES.get(question_type, set())),
            set(QUESTION_TYPE_PREDICTION_VALUE_SEMANTICS.get(question_type, set())),
        )

    @staticmethod
    def _validate_prediction_entry_for_workspace(
        workspace: ForecastWorkspaceRecord,
        entry: PredictionLedgerEntry,
    ) -> None:
        question_type = workspace.forecast_question.question_type
        allowed_value_types, allowed_value_semantics = ForecastManager._question_prediction_contract(
            question_type
        )
        if entry.value_type not in allowed_value_types:
            raise ValueError(
                f"{question_type} forecast questions do not accept prediction value_type "
                f"{entry.value_type!r}"
            )
        if entry.value_semantics not in allowed_value_semantics:
            raise ValueError(
                f"{question_type} forecast questions do not accept prediction value_semantics "
                f"{entry.value_semantics!r}"
            )

        value = entry.value if entry.value is not None else entry.prediction
        if entry.value_semantics == "observed_run_share":
            if entry.value_type != "scenario_observed_share":
                raise ValueError(
                    "observed_run_share predictions must use value_type 'scenario_observed_share'"
                )
            return

        if question_type == "categorical":
            if not isinstance(value, dict):
                raise ValueError(
                    "categorical prediction entries must store a distribution object"
                )
            outcome_labels = set(
                workspace.forecast_question.question_spec.get("outcome_labels") or []
            )
            if outcome_labels:
                unknown_labels = sorted(
                    label for label in value.keys() if str(label) not in outcome_labels
                )
                if unknown_labels:
                    raise ValueError(
                        "categorical prediction entries reference unknown outcome labels: "
                        + ", ".join(unknown_labels)
                    )
            return

        if question_type == "numeric":
            if entry.value_semantics == "numeric_estimate":
                numeric_value = value
                if isinstance(value, dict):
                    numeric_value = value.get("point_estimate", value.get("value"))
                try:
                    float(numeric_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "numeric_estimate prediction entries must carry a numeric point estimate"
                    ) from exc
                return

            if not isinstance(value, dict):
                raise ValueError(
                    "numeric_interval_estimate prediction entries must store an interval payload"
                )
            point_estimate = value.get("point_estimate", value.get("value"))
            try:
                float(point_estimate)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "numeric_interval_estimate prediction entries must include a numeric point_estimate"
                ) from exc
            intervals = value.get("intervals")
            if not isinstance(intervals, list) or not intervals:
                raise ValueError(
                    "numeric_interval_estimate prediction entries must include interval bounds"
                )

    @staticmethod
    def _validate_evaluation_case_for_workspace(
        workspace: ForecastWorkspaceRecord,
        case: EvaluationCase,
    ) -> None:
        question_type = workspace.forecast_question.question_type
        if case.prediction_value_type is not None or case.prediction_value_semantics is not None:
            allowed_value_types, allowed_value_semantics = ForecastManager._question_prediction_contract(
                question_type
            )
            if case.prediction_value_type is not None and case.prediction_value_type not in allowed_value_types:
                raise ValueError(
                    f"{question_type} forecast questions do not accept evaluation prediction_value_type "
                    f"{case.prediction_value_type!r}"
                )
            if (
                case.prediction_value_semantics is not None
                and case.prediction_value_semantics not in allowed_value_semantics
            ):
                raise ValueError(
                    f"{question_type} forecast questions do not accept evaluation prediction_value_semantics "
                    f"{case.prediction_value_semantics!r}"
                )

        if question_type == "categorical":
            prediction_distribution = case.prediction_payload.get("distribution")
            outcome_labels = set(
                workspace.forecast_question.question_spec.get("outcome_labels") or []
            )
            if prediction_distribution is not None and not isinstance(
                prediction_distribution, dict
            ):
                raise ValueError(
                    "categorical evaluation cases must store prediction_payload.distribution as a dictionary"
                )
            if isinstance(prediction_distribution, dict) and outcome_labels:
                unknown_labels = sorted(
                    label
                    for label in prediction_distribution.keys()
                    if str(label) not in outcome_labels
                )
                if unknown_labels:
                    raise ValueError(
                        "categorical evaluation cases reference unknown outcome labels: "
                        + ", ".join(unknown_labels)
                    )
            if case.status == "resolved":
                observed = (
                    case.observed_outcome
                    if case.observed_outcome is not None
                    else case.observed_value
                )
                observed_label = observed.get("label") if isinstance(observed, dict) else observed
                observed_label = str(observed_label).strip() if observed_label is not None else ""
                if not observed_label:
                    raise ValueError(
                        "resolved categorical evaluation cases must include an observed outcome label"
                    )
                if outcome_labels and observed_label not in outcome_labels:
                    raise ValueError(
                        f"resolved categorical outcome {observed_label!r} is not in question_spec.outcome_labels"
                    )
            return

        if question_type == "numeric" and case.status == "resolved":
            observed = (
                case.observed_outcome if case.observed_outcome is not None else case.observed_value
            )
            observed_value = observed.get("value") if isinstance(observed, dict) else observed
            try:
                float(observed_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "resolved numeric evaluation cases must include a numeric observed outcome"
                ) from exc

    @classmethod
    def build_workspace(
        cls,
        question: ForecastQuestion,
        resolution_criteria: list[ResolutionCriteria],
        evidence_bundle,
        forecast_workers: list[ForecastWorker],
        simulation_worker_contract: Optional[SimulationWorkerContract] = None,
    ) -> ForecastWorkspaceRecord:
        if simulation_worker_contract is not None and not question.primary_simulation_id:
            question.primary_simulation_id = (
                simulation_worker_contract.simulation_id
                or simulation_worker_contract.worker_id
            )
        return ForecastWorkspaceRecord(
            forecast_question=question,
            resolution_criteria=resolution_criteria,
            evidence_bundle=evidence_bundle,
            forecast_workers=forecast_workers,
            prediction_ledger=PredictionLedger(forecast_id=question.forecast_id),
            evaluation_cases=[],
            forecast_answers=[],
            simulation_worker_contract=simulation_worker_contract,
        )
