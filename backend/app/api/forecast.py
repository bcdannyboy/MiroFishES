"""
API scaffolding for the canonical forecasting foundation.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from flask import jsonify, request

from . import forecast_bp
from ..models.forecasting import (
    EvaluationCase,
    ForecastAnswer,
    ForecastQuestion,
    ForecastWorker,
    ForecastWorkspaceRecord,
    PredictionLedgerEntry,
    ResolutionCriteria,
    SimulationWorkerContract,
    get_forecast_capabilities_domain,
)
from ..services.forecast_manager import ForecastManager
from ..services.forecast_resolution_manager import ForecastResolutionManager


def _json_error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _autofill_workspace_payload(data: dict) -> dict:
    forecast_question = dict(data.get("forecast_question") or {})
    forecast_id = str(forecast_question.get("forecast_id") or _new_id("forecast")).strip()
    now = datetime.now().isoformat()

    forecast_question.setdefault("forecast_id", forecast_id)
    forecast_question.setdefault("created_at", now)
    forecast_question.setdefault("updated_at", now)

    resolution_criteria = []
    resolution_criteria_ids = []
    for index, item in enumerate(data.get("resolution_criteria") or []):
        criteria = dict(item or {})
        criteria.setdefault("criteria_id", _new_id(f"criteria{index + 1}"))
        criteria.setdefault("forecast_id", forecast_id)
        resolution_criteria.append(criteria)
        resolution_criteria_ids.append(criteria["criteria_id"])
    forecast_question.setdefault("resolution_criteria_ids", resolution_criteria_ids)

    evidence_bundle = dict(data.get("evidence_bundle") or {})
    evidence_bundle.setdefault("bundle_id", _new_id("bundle"))
    evidence_bundle.setdefault("forecast_id", forecast_id)
    evidence_bundle.setdefault("created_at", now)

    forecast_workers = []
    for index, item in enumerate(data.get("forecast_workers") or []):
        worker = dict(item or {})
        worker.setdefault("worker_id", _new_id(f"worker{index + 1}"))
        worker.setdefault("forecast_id", forecast_id)
        forecast_workers.append(worker)

    simulation_worker_contract = data.get("simulation_worker_contract")
    if simulation_worker_contract is not None:
        simulation_worker_contract = dict(simulation_worker_contract)
        simulation_worker_contract.setdefault("forecast_id", forecast_id)
        if not simulation_worker_contract.get("worker_id"):
            simulation_worker_contract["worker_id"] = _new_id("simulation_worker")

    prediction_ledger = dict(data.get("prediction_ledger") or {})
    prediction_ledger.setdefault("forecast_id", forecast_id)
    prediction_ledger.setdefault("entries", [])
    prediction_ledger.setdefault("worker_outputs", [])
    prediction_ledger.setdefault("resolution_history", [])
    prediction_ledger.setdefault("final_resolution_state", "pending")
    prediction_ledger.setdefault("resolved_at", None)
    prediction_ledger.setdefault("resolution_note", "")

    evaluation_cases = []
    for index, item in enumerate(data.get("evaluation_cases") or []):
        case = dict(item or {})
        case.setdefault("case_id", _new_id(f"case{index + 1}"))
        case.setdefault("forecast_id", forecast_id)
        evaluation_cases.append(case)

    forecast_answers = []
    for index, item in enumerate(data.get("forecast_answers") or []):
        answer = dict(item or {})
        answer.setdefault("answer_id", _new_id(f"answer{index + 1}"))
        answer.setdefault("forecast_id", forecast_id)
        answer.setdefault("created_at", now)
        forecast_answers.append(answer)

    return {
        "forecast_question": forecast_question,
        "resolution_criteria": resolution_criteria,
        "evidence_bundle": evidence_bundle,
        "forecast_workers": forecast_workers,
        "prediction_ledger": prediction_ledger,
        "evaluation_cases": evaluation_cases,
        "forecast_answers": forecast_answers,
        "simulation_worker_contract": simulation_worker_contract,
    }


def _workspace_from_request(data: dict) -> ForecastWorkspaceRecord:
    normalized = _autofill_workspace_payload(data)
    return ForecastWorkspaceRecord(
        forecast_question=ForecastQuestion.from_dict(normalized["forecast_question"]),
        resolution_criteria=[
            ResolutionCriteria.from_dict(item)
            for item in normalized["resolution_criteria"]
        ],
        evidence_bundle=normalized["evidence_bundle"],
        forecast_workers=[
            ForecastWorker.from_dict(item)
            for item in normalized["forecast_workers"]
        ],
        prediction_ledger=normalized["prediction_ledger"],
        evaluation_cases=[
            EvaluationCase.from_dict(item) for item in normalized["evaluation_cases"]
        ],
        forecast_answers=[
            ForecastAnswer.from_dict(item) for item in normalized["forecast_answers"]
        ],
        simulation_worker_contract=normalized["simulation_worker_contract"],
    )


def _question_request_payload(data: dict) -> dict:
    question_value = data.get("question")
    forecast_question_value = data.get("forecast_question")

    if isinstance(question_value, dict):
        payload = dict(question_value)
    elif isinstance(forecast_question_value, dict):
        payload = dict(forecast_question_value)
    else:
        payload = dict(data)
    if not payload:
        payload = dict(data)
    if isinstance(question_value, str):
        normalized_question = question_value.strip()
        if normalized_question:
            payload.setdefault("question", normalized_question)
            payload.setdefault("question_text", normalized_question)
    payload.setdefault("question", payload.get("question_text", payload.get("title", "")))
    payload.setdefault("question_text", payload.get("question", payload.get("title", "")))
    payload.setdefault("title", payload.get("title", payload.get("question", "")))
    payload.setdefault("project_id", payload.get("project_id") or payload.get("owner") or _new_id("project"))
    payload.setdefault("forecast_id", payload.get("forecast_id") or _new_id("forecast"))
    payload.setdefault("created_at", datetime.now().isoformat())
    payload.setdefault("updated_at", payload["created_at"])
    payload.setdefault(
        "issue_timestamp",
        payload.get("issue_timestamp", payload.get("issued_at", payload["created_at"])),
    )
    payload.setdefault("status", payload.get("status", "draft"))
    payload.setdefault("resolution_criteria_ids", payload.get("resolution_criteria_ids", []))
    payload.setdefault("decomposition_support", payload.get("decomposition_support", []))
    payload.setdefault("abstention_conditions", payload.get("abstention_conditions", []))
    payload.setdefault("tags", payload.get("tags", []))
    return payload


def _question_workspace_from_request(data: dict) -> ForecastWorkspaceRecord:
    question_payload = _question_request_payload(data)
    forecast_id = question_payload["forecast_id"]
    now = question_payload["created_at"]

    resolution_criteria_payloads = []
    resolution_criteria_ids = []
    for index, item in enumerate(data.get("resolution_criteria") or []):
        criteria = dict(item or {})
        criteria.setdefault("criteria_id", _new_id(f"criteria{index + 1}"))
        criteria.setdefault("forecast_id", forecast_id)
        resolution_criteria_payloads.append(criteria)
        resolution_criteria_ids.append(criteria["criteria_id"])
    if resolution_criteria_ids and not question_payload.get("resolution_criteria_ids"):
        question_payload["resolution_criteria_ids"] = resolution_criteria_ids
    if question_payload.get("resolution_criteria_ids") and not resolution_criteria_payloads:
        raise ValueError(
            "resolution_criteria entries are required when resolution_criteria_ids are supplied"
        )

    evidence_bundle = dict(data.get("evidence_bundle") or {})
    evidence_bundle.setdefault("bundle_id", _new_id("bundle"))
    evidence_bundle.setdefault("forecast_id", forecast_id)
    evidence_bundle.setdefault("title", question_payload["title"] or "Question evidence scaffold")
    evidence_bundle.setdefault(
        "summary",
        "Placeholder evidence bundle created alongside a question-first forecast workspace.",
    )
    evidence_bundle.setdefault(
        "boundary_note",
        "This bundle marks the question as created before supporting evidence is attached.",
    )
    evidence_bundle.setdefault("created_at", now)

    forecast_workers = []
    for index, item in enumerate(data.get("forecast_workers") or []):
        worker = dict(item or {})
        worker.setdefault("worker_id", _new_id(f"worker{index + 1}"))
        worker.setdefault("forecast_id", forecast_id)
        forecast_workers.append(worker)

    simulation_worker_contract = data.get("simulation_worker_contract")
    if simulation_worker_contract is not None:
        simulation_worker_contract = dict(simulation_worker_contract)
        simulation_worker_contract.setdefault("forecast_id", forecast_id)
        if not simulation_worker_contract.get("worker_id"):
            simulation_worker_contract["worker_id"] = _new_id("simulation_worker")

    prediction_ledger = dict(data.get("prediction_ledger") or {})
    prediction_ledger["forecast_id"] = forecast_id
    prediction_ledger["entries"] = []
    prediction_ledger["worker_outputs"] = []
    prediction_ledger["resolution_history"] = []
    prediction_ledger["final_resolution_state"] = "pending"
    prediction_ledger["resolved_at"] = None
    prediction_ledger["resolution_note"] = ""

    evaluation_cases = []
    forecast_answers = []

    return ForecastWorkspaceRecord(
        forecast_question=ForecastQuestion.from_dict(question_payload),
        resolution_criteria=[ResolutionCriteria.from_dict(item) for item in resolution_criteria_payloads],
        evidence_bundle=evidence_bundle,
        forecast_workers=[ForecastWorker.from_dict(item) for item in forecast_workers],
        prediction_ledger=prediction_ledger,
        evaluation_cases=[EvaluationCase.from_dict(item) for item in evaluation_cases],
        forecast_answers=[ForecastAnswer.from_dict(item) for item in forecast_answers],
        simulation_worker_contract=simulation_worker_contract,
    )


def _prediction_entry_payload(data: dict, forecast_id: str, *, revision_of: str | None = None) -> dict:
    entry_payload = dict(data.get("prediction_entry") or data.get("prediction") or data.get("entry") or {})
    entry_payload.setdefault("entry_id", _new_id("entry"))
    entry_payload.setdefault("prediction_id", entry_payload["entry_id"])
    entry_payload.setdefault("forecast_id", forecast_id)
    entry_payload.setdefault("recorded_at", datetime.now().isoformat())
    entry_payload.setdefault("entry_kind", "revision" if revision_of else "issue")
    if revision_of is not None:
        entry_payload.setdefault("revises_prediction_id", revision_of)
        entry_payload.setdefault("revises_entry_id", revision_of)
    return entry_payload


def _evidence_bundle_payload(
    data: dict,
    forecast_id: str,
    *,
    bundle_id: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    payload = dict(data.get("evidence_bundle") or data.get("bundle") or data)
    payload.setdefault("bundle_id", bundle_id or payload.get("bundle_id") or _new_id("bundle"))
    payload["bundle_id"] = bundle_id or payload["bundle_id"]
    payload.setdefault("forecast_id", forecast_id)
    payload.setdefault("title", payload.get("title") or "Forecast evidence bundle")
    payload.setdefault(
        "summary",
        payload.get("summary")
        or "Bounded forecast evidence assembled from configured providers.",
    )
    payload.setdefault(
        "boundary_note",
        payload.get("boundary_note")
        or "Evidence remains bounded to the providers listed in this bundle.",
    )
    payload.setdefault("created_at", now)
    payload.setdefault("source_entries", payload.get("source_entries", payload.get("entries", [])))
    payload.setdefault("provider_snapshots", payload.get("providers", []))
    payload.setdefault("missing_evidence_markers", [])
    payload.setdefault("question_ids", payload.get("question_links", [forecast_id]))
    payload.setdefault("prediction_entry_ids", payload.get("prediction_links", []))
    payload.setdefault("status", payload.get("status", "draft"))
    payload["source_entries"] = _normalize_internal_evidence_items(
        payload.get("source_entries", [])
    )
    payload["provider_snapshots"] = _normalize_internal_evidence_items(
        payload.get("provider_snapshots", [])
    )
    payload["missing_evidence_markers"] = _normalize_internal_evidence_items(
        payload.get("missing_evidence_markers", [])
    )
    return payload


def _question_response(workspace: ForecastWorkspaceRecord) -> dict:
    ledger_payload = _ledger_response(workspace)
    return {
        "question": workspace.forecast_question.to_dict(),
        "evidence_bundle": _normalize_evidence_bundle_response(
            workspace.evidence_bundle.to_dict()
        ),
        "ledger": ledger_payload,
        "prediction_ledger": ledger_payload,
        "resolution_criteria": [item.to_dict() for item in workspace.resolution_criteria],
        "resolution_record": workspace.resolution_record.to_dict(),
        "scoring_events": [item.to_dict() for item in workspace.scoring_events],
        "forecast_object": _forecast_object_response(workspace),
        "workspace": _workspace_response(workspace),
    }


def _ledger_response(workspace: ForecastWorkspaceRecord) -> dict:
    ledger_payload = workspace.prediction_ledger.to_dict()
    resolution_status = workspace.prediction_ledger.resolution_status
    if isinstance(resolution_status, dict):
        resolution_status = resolution_status.get("status", resolution_status)
    ledger_payload["final_resolution_state"] = resolution_status
    ledger_payload["resolved_at"] = workspace.prediction_ledger.resolved_at
    ledger_payload["resolution_note"] = workspace.prediction_ledger.resolution_note
    return ledger_payload


def _workspace_response(workspace: ForecastWorkspaceRecord) -> dict:
    workspace_payload = workspace.to_dict()
    workspace_payload["prediction_ledger"] = _ledger_response(workspace)
    evidence_bundle = workspace_payload.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        workspace_payload["evidence_bundle"] = _normalize_evidence_bundle_response(
            evidence_bundle
        )
    return workspace_payload


def _forecast_object_response(workspace: ForecastWorkspaceRecord) -> dict:
    latest_answer = workspace.forecast_answers[-1] if workspace.forecast_answers else None
    latest_scoring = workspace.scoring_events[-1] if workspace.scoring_events else None
    return {
        "forecast_id": workspace.forecast_question.forecast_id,
        "status": "available",
        "question_text": workspace.forecast_question.question_text,
        "question_type": workspace.forecast_question.question_type,
        "latest_answer_id": latest_answer.answer_id if latest_answer is not None else None,
        "latest_answer_type": latest_answer.answer_type if latest_answer is not None else None,
        "resolution": workspace.resolution_record.to_dict(),
        "scoring": {
            "event_count": len(workspace.scoring_events),
            "latest_method": latest_scoring.scoring_method if latest_scoring is not None else None,
            "latest_score_value": latest_scoring.score_value if latest_scoring is not None else None,
        },
    }


def _normalize_public_evidence_provider_id(provider_id: str | None) -> str | None:
    provider_aliases = {
        "uploaded_local": "uploaded_local_artifacts",
        "uploaded_local_artifact": "uploaded_local_artifacts",
        "external_live": "external_live_unconfigured",
        "live_external": "external_live_unconfigured",
    }
    return provider_aliases.get(provider_id, provider_id)


def _normalize_internal_evidence_provider_id(provider_id: str | None) -> str | None:
    provider_aliases = {
        "uploaded_local": "uploaded_local_artifact",
        "uploaded_local_artifact": "uploaded_local_artifact",
        "uploaded_local_artifacts": "uploaded_local_artifact",
        "external_live": "live_external",
        "external_live_unconfigured": "live_external",
        "live_external": "live_external",
    }
    return provider_aliases.get(provider_id, provider_id)


def _normalize_evidence_provider_catalog(providers: list[dict] | None) -> list[dict]:
    normalized_providers = []
    for provider in providers or []:
        if not isinstance(provider, dict):
            continue
        normalized = dict(provider)
        normalized["provider_id"] = _normalize_public_evidence_provider_id(
            normalized.get("provider_id")
        )
        normalized_providers.append(normalized)
    return normalized_providers


def _normalize_internal_evidence_items(items: list[dict] | None) -> list[dict]:
    normalized_items = []
    for item in items or []:
        if not isinstance(item, dict):
            normalized_items.append(item)
            continue
        normalized = dict(item)
        normalized["provider_id"] = _normalize_internal_evidence_provider_id(
            normalized.get("provider_id")
        )
        provenance = normalized.get("provenance")
        if isinstance(provenance, dict):
            normalized_provenance = dict(provenance)
            normalized_provenance["provider"] = _normalize_internal_evidence_provider_id(
                normalized_provenance.get("provider")
            )
            normalized["provenance"] = normalized_provenance
        normalized_items.append(normalized)
    return normalized_items


def _normalize_evidence_bundle_response(bundle_payload: dict) -> dict:
    normalized_bundle = dict(bundle_payload)
    provider_snapshots = []
    for provider in normalized_bundle.get("provider_snapshots") or []:
        if not isinstance(provider, dict):
            continue
        normalized_provider = dict(provider)
        normalized_provider["provider_id"] = _normalize_public_evidence_provider_id(
            normalized_provider.get("provider_id")
        )
        provider_snapshots.append(normalized_provider)
    if provider_snapshots:
        normalized_bundle["provider_snapshots"] = provider_snapshots
        normalized_bundle["providers"] = [dict(item) for item in provider_snapshots]
    source_entries = []
    for entry in normalized_bundle.get("source_entries") or []:
        if not isinstance(entry, dict):
            continue
        normalized_entry = dict(entry)
        normalized_entry["provider_id"] = _normalize_public_evidence_provider_id(
            normalized_entry.get("provider_id")
        )
        source_entries.append(normalized_entry)
    if source_entries:
        normalized_bundle["source_entries"] = source_entries
        normalized_bundle["entries"] = [dict(item) for item in source_entries]
    missing_markers = []
    for marker in normalized_bundle.get("missing_evidence_markers") or []:
        if not isinstance(marker, dict):
            missing_markers.append(marker)
            continue
        normalized_marker = dict(marker)
        normalized_marker["provider_id"] = _normalize_public_evidence_provider_id(
            normalized_marker.get("provider_id")
        )
        missing_markers.append(normalized_marker)
    if missing_markers:
        normalized_bundle["missing_evidence_markers"] = missing_markers
    if (
        normalized_bundle.get("status") == "degraded"
        and any(
            isinstance(provider, dict) and provider.get("status") == "unavailable"
            for provider in provider_snapshots
        )
    ):
        normalized_bundle["status"] = "partial"
    return normalized_bundle


def _evidence_bundle_request_payload(
    data: dict,
    *,
    forecast_id: str,
    existing_bundle: dict | None = None,
) -> dict:
    payload = dict(existing_bundle or {})
    patch_payload = dict(data.get("evidence_bundle") or data.get("bundle") or data)
    payload.update(patch_payload)
    payload.setdefault("bundle_id", (existing_bundle or {}).get("bundle_id") or _new_id("bundle"))
    payload["forecast_id"] = forecast_id
    payload.setdefault("title", (existing_bundle or {}).get("title") or "Forecast evidence bundle")
    payload.setdefault(
        "summary",
        (existing_bundle or {}).get("summary")
        or "Bounded forecast evidence assembled from configured providers.",
    )
    payload.setdefault(
        "boundary_note",
        (existing_bundle or {}).get("boundary_note")
        or "Evidence remains bounded to the providers attached to this bundle.",
    )
    payload.setdefault(
        "created_at",
        (existing_bundle or {}).get("created_at") or datetime.now().isoformat(),
    )
    if "source_entries" in patch_payload or "entries" in patch_payload:
        payload["source_entries"] = patch_payload.get(
            "source_entries",
            patch_payload.get("entries", []),
        )
    else:
        payload.setdefault(
            "source_entries",
            payload.get("source_entries", payload.get("entries", [])),
        )
    if "provider_snapshots" in patch_payload or "providers" in patch_payload:
        payload["provider_snapshots"] = patch_payload.get(
            "provider_snapshots",
            patch_payload.get("providers", []),
        )
    else:
        payload.setdefault(
            "provider_snapshots",
            payload.get("provider_snapshots", payload.get("providers", [])),
        )
    if "question_ids" in patch_payload or "question_links" in patch_payload:
        payload["question_ids"] = patch_payload.get(
            "question_ids",
            patch_payload.get("question_links", [forecast_id]),
        )
    else:
        payload.setdefault(
            "question_ids",
            payload.get("question_ids", payload.get("question_links", [forecast_id])),
        )
    if "prediction_entry_ids" in patch_payload or "prediction_links" in patch_payload:
        payload["prediction_entry_ids"] = patch_payload.get(
            "prediction_entry_ids",
            patch_payload.get("prediction_links", []),
        )
    else:
        payload.setdefault(
            "prediction_entry_ids",
            payload.get(
                "prediction_entry_ids",
                payload.get("prediction_links", (existing_bundle or {}).get("prediction_links", [])),
            ),
        )
    payload["source_entries"] = _normalize_internal_evidence_items(
        payload.get("source_entries", [])
    )
    payload["provider_snapshots"] = _normalize_internal_evidence_items(
        payload.get("provider_snapshots", [])
    )
    payload["missing_evidence_markers"] = _normalize_internal_evidence_items(
        payload.get("missing_evidence_markers", [])
    )
    return payload


@forecast_bp.route("/capabilities", methods=["GET"])
def get_capabilities():
    return jsonify({"success": True, "capabilities": get_forecast_capabilities_domain()})


@forecast_bp.route("/evidence-providers", methods=["GET"])
def list_global_evidence_providers():
    try:
        providers = _normalize_evidence_provider_catalog(
            ForecastManager().list_evidence_providers()
        )
        return jsonify(
            {
                "success": True,
                "providers": providers,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions", methods=["POST"])
def create_question():
    try:
        data = request.get_json(force=True) or {}
        workspace = _question_workspace_from_request(data)
        created = ForecastManager().create_workspace(workspace)
        return jsonify({"success": True, **_question_response(created)}), 201
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions", methods=["GET"])
def list_questions():
    try:
        manager = ForecastManager()
        questions = manager.list_questions()
        return jsonify(
            {
                "success": True,
                "questions": [question.to_dict() for question in questions],
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>", methods=["GET"])
def get_question(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify({"success": True, **_question_response(workspace)})
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>", methods=["PATCH"])
def update_question(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        merged_question = workspace.forecast_question.to_dict()
        patch_payload = data.get("question") or data.get("forecast_question") or data
        merged_question.update(patch_payload)
        merged_question["forecast_id"] = forecast_id
        merged_question.setdefault("project_id", workspace.forecast_question.project_id)
        merged_question.setdefault("title", workspace.forecast_question.title)
        if "question_text" in patch_payload and "question" not in patch_payload:
            merged_question["question"] = patch_payload["question_text"]
        else:
            merged_question["question"] = merged_question.get(
                "question_text",
                merged_question.get("question", workspace.forecast_question.question),
            )
        merged_question.setdefault("created_at", workspace.forecast_question.created_at)
        merged_question.setdefault("issue_timestamp", workspace.forecast_question.issue_timestamp)
        merged_question["updated_at"] = datetime.now().isoformat()
        updated_question = ForecastQuestion.from_dict(merged_question)
        updated_workspace = manager.update_question(forecast_id, updated_question)
        return jsonify({"success": True, **_question_response(updated_workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/resolve", methods=["POST"])
def resolve_question(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        resolution_state = dict(data.get("resolution_state") or data.get("resolution") or data)
        if not resolution_state:
            resolution_state = {"status": "resolved", "resolved_at": datetime.now().isoformat()}
        workspace = ForecastManager().resolve_forecast(forecast_id, resolution_state)
        return jsonify({"success": True, **_question_response(workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/score", methods=["POST"])
def score_question(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        if "observed_outcome" not in data:
            return _json_error("observed_outcome is required to score a forecast answer", 400)
        workspace = ForecastResolutionManager().score_forecast(
            forecast_id,
            observed_outcome=data.get("observed_outcome"),
            scoring_methods=data.get("scoring_methods"),
            recorded_at=data.get("recorded_at"),
            notes=data.get("notes"),
        )
        return jsonify({"success": True, **_question_response(workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/scoring-events", methods=["GET"])
def get_question_scoring_events(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "resolution_record": workspace.resolution_record.to_dict(),
                "scoring_events": [item.to_dict() for item in workspace.scoring_events],
                "forecast_object": _forecast_object_response(workspace),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/ledger", methods=["GET"])
def get_question_ledger(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "ledger": _ledger_response(workspace),
                "prediction_ledger": _ledger_response(workspace),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/evidence/providers", methods=["GET"])
def list_evidence_providers_alias():
    try:
        providers = _normalize_evidence_provider_catalog(
            ForecastManager().list_evidence_providers()
        )
        return jsonify(
            {
                "success": True,
                "providers": providers,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence", methods=["GET"])
def get_question_evidence_bundle(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "evidence_bundle": _normalize_evidence_bundle_response(
                    workspace.evidence_bundle.to_dict()
                ),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence", methods=["PUT", "PATCH"])
def update_question_evidence_bundle(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        payload = _evidence_bundle_request_payload(
            data,
            forecast_id=forecast_id,
            existing_bundle=workspace.evidence_bundle.to_dict(),
        )
        updated = manager.update_evidence_bundle(
            forecast_id,
            workspace.evidence_bundle.bundle_id,
            payload,
        )
        return jsonify(
            {
                "success": True,
                "question": updated.forecast_question.to_dict(),
                "evidence_bundle": _normalize_evidence_bundle_response(
                    updated.evidence_bundle.to_dict()
                ),
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence/providers", methods=["GET"])
def list_question_evidence_providers(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "providers": _normalize_evidence_provider_catalog(
                    ForecastManager().list_evidence_providers()
                ),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence/acquire", methods=["POST"])
@forecast_bp.route("/questions/<forecast_id>/evidence/refresh", methods=["POST"])
def acquire_question_evidence_bundle(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        if "provider_ids" in data:
            provider_ids = data.get("provider_ids")
            if provider_ids is not None and not isinstance(provider_ids, list):
                return _json_error("provider_ids must be a list", 400)
            updated = manager.acquire_evidence_bundle(
                forecast_id,
                bundle_id=workspace.evidence_bundle.bundle_id,
                provider_ids=provider_ids,
            )
        else:
            updated = manager.refresh_evidence_bundle(
                forecast_id,
                include_live_external=bool(data.get("include_live_external", False)),
                live_provider_request=data.get("live_provider_request"),
            )
        return jsonify(
            {
                "success": True,
                "question": updated.forecast_question.to_dict(),
                "evidence_bundle": _normalize_evidence_bundle_response(
                    updated.evidence_bundle.to_dict()
                ),
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence-bundles", methods=["GET"])
def list_evidence_bundles(forecast_id: str):
    try:
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        bundles = manager.list_evidence_bundles(forecast_id)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "active_bundle_id": workspace.evidence_bundle.bundle_id,
                "evidence_bundles": [
                    _normalize_evidence_bundle_response(bundle.to_dict())
                    for bundle in bundles
                ],
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence-bundles", methods=["POST"])
def create_evidence_bundle(forecast_id: str):
    try:
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        bundle = _evidence_bundle_payload(request.get_json(force=True) or {}, forecast_id)
        updated = manager.create_evidence_bundle(forecast_id, bundle)
        return jsonify({"success": True, **_question_response(updated)}), 201
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence-bundles/<bundle_id>", methods=["GET"])
def get_evidence_bundle(forecast_id: str, bundle_id: str):
    try:
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        bundle = manager.get_evidence_bundle(forecast_id, bundle_id)
        if bundle is None:
            return _json_error(
                f"Unknown evidence bundle for forecast question: {forecast_id}/{bundle_id}",
                404,
            )
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "evidence_bundle": _normalize_evidence_bundle_response(
                    bundle.to_dict()
                ),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence-bundles/<bundle_id>", methods=["PATCH"])
def update_evidence_bundle(forecast_id: str, bundle_id: str):
    try:
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        bundle_patch = _evidence_bundle_payload(
            request.get_json(force=True) or {},
            forecast_id,
            bundle_id=bundle_id,
        )
        updated = manager.update_evidence_bundle(forecast_id, bundle_id, bundle_patch)
        return jsonify({"success": True, **_question_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/evidence-bundles/acquire", methods=["POST"])
@forecast_bp.route("/questions/<forecast_id>/evidence-bundles/<bundle_id>/acquire", methods=["POST"])
def acquire_evidence_bundle(forecast_id: str, bundle_id: str | None = None):
    try:
        manager = ForecastManager()
        workspace = manager.get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        data = request.get_json(force=True) or {}
        provider_ids = data.get("provider_ids")
        if provider_ids is not None and not isinstance(provider_ids, list):
            return _json_error("provider_ids must be a list", 400)
        updated = manager.acquire_evidence_bundle(
            forecast_id,
            bundle_id=bundle_id,
            provider_ids=provider_ids,
        )
        return jsonify({"success": True, **_question_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/predictions", methods=["GET"])
@forecast_bp.route("/questions/<forecast_id>/ledger/predictions", methods=["GET"])
def list_predictions(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "question": workspace.forecast_question.to_dict(),
                "predictions": [entry.to_dict() for entry in workspace.prediction_ledger.entries],
                "prediction_ledger": _ledger_response(workspace),
                "ledger": _ledger_response(workspace),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/predictions", methods=["POST"])
@forecast_bp.route("/questions/<forecast_id>/ledger/predictions", methods=["POST"])
def issue_prediction(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        entry = PredictionLedgerEntry.from_dict(_prediction_entry_payload(data, forecast_id))
        updated = ForecastManager().issue_prediction(forecast_id, entry)
        return jsonify({"success": True, **_question_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/predictions/<prediction_id>", methods=["GET"])
@forecast_bp.route("/questions/<forecast_id>/ledger/predictions/<prediction_id>", methods=["GET"])
def get_prediction_history(forecast_id: str, prediction_id: str):
    try:
        history = ForecastManager().get_prediction_history(forecast_id, prediction_id)
        if not history:
            return _json_error(
                f"Unknown prediction for forecast question: {forecast_id}/{prediction_id}",
                404,
            )
        return jsonify(
            {
                "success": True,
                "forecast_id": forecast_id,
                "prediction_id": prediction_id,
                "history": [entry.to_dict() for entry in history],
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/predictions/<prediction_id>/revisions", methods=["POST"])
@forecast_bp.route("/questions/<forecast_id>/ledger/predictions/<prediction_id>/revisions", methods=["POST"])
def revise_prediction(forecast_id: str, prediction_id: str):
    try:
        data = request.get_json(force=True) or {}
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        entry = PredictionLedgerEntry.from_dict(
            _prediction_entry_payload(data, forecast_id, revision_of=prediction_id)
        )
        entry.revises_prediction_id = prediction_id
        entry.revises_entry_id = prediction_id
        updated = ForecastManager().revise_prediction(forecast_id, entry)
        return jsonify({"success": True, **_question_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast question" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/forecast-answers/generate", methods=["POST"])
def generate_hybrid_forecast_answer(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        worker_ids = data.get("worker_ids")
        if worker_ids is not None and not isinstance(worker_ids, list):
            return _json_error("worker_ids must be a list when provided", 400)
        requested_at = data.get("requested_at")
        updated = ForecastManager().generate_hybrid_forecast_answer(
            forecast_id,
            requested_at=requested_at,
            worker_ids=worker_ids,
        )
        generated_answer = updated.forecast_answers[-1] if updated.forecast_answers else None
        return jsonify(
            {
                "success": True,
                **_question_response(updated),
                "forecast_answer": (
                    generated_answer.to_dict() if generated_answer is not None else None
                ),
                "generated_answer": (
                    generated_answer.to_dict() if generated_answer is not None else None
                ),
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/forecast-answers/compose", methods=["POST"])
def compose_hybrid_forecast_answer(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        worker_ids = data.get("worker_ids")
        if worker_ids is not None and not isinstance(worker_ids, list):
            return _json_error("worker_ids must be a list when provided", 400)
        recorded_at = data.get("recorded_at")
        updated = ForecastManager().compose_hybrid_forecast_answer(
            forecast_id,
            recorded_at=recorded_at,
            worker_ids=worker_ids,
        )
        generated_answer = updated.forecast_answers[-1] if updated.forecast_answers else None
        return jsonify(
            {
                "success": True,
                **_question_response(updated),
                "forecast_answer": (
                    generated_answer.to_dict() if generated_answer is not None else None
                ),
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/questions/<forecast_id>/forecast-answers", methods=["GET"])
def list_forecast_answers(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast question: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "forecast_answers": [item.to_dict() for item in workspace.forecast_answers],
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces", methods=["POST"])
def create_workspace():
    try:
        data = request.get_json(force=True) or {}
        workspace = _workspace_from_request(data)
        created = ForecastManager().create_workspace(workspace)
        return jsonify({"success": True, "workspace": _workspace_response(created)}), 201
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces", methods=["GET"])
def list_workspaces():
    try:
        workspaces = ForecastManager().list_workspaces()
        return jsonify(
            {
                "success": True,
                "workspaces": [workspace.to_summary_dict() for workspace in workspaces],
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>", methods=["GET"])
def get_workspace(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast workspace: {forecast_id}", 404)
        return jsonify({"success": True, "workspace": _workspace_response(workspace)})
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/workers", methods=["POST"])
def register_worker(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        worker = ForecastWorker.from_dict(
            {
                **data.get("forecast_worker", {}),
                "forecast_id": data.get("forecast_worker", {}).get("forecast_id", forecast_id),
            }
        )
        simulation_worker_contract = data.get("simulation_worker_contract")
        if simulation_worker_contract is not None:
            simulation_worker_contract = SimulationWorkerContract.from_dict(
                {
                    **simulation_worker_contract,
                    "forecast_id": simulation_worker_contract.get("forecast_id", forecast_id),
                }
            )
        workspace = ForecastManager().register_worker(
            forecast_id,
            worker,
            simulation_worker_contract=simulation_worker_contract,
        )
        return jsonify({"success": True, "workspace": _workspace_response(workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/prediction-ledger/entries", methods=["POST"])
def append_prediction_entry(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast workspace: {forecast_id}", 404)
        entry = PredictionLedgerEntry.from_dict(_prediction_entry_payload(data, forecast_id))
        updated = ForecastManager().append_prediction_entry(forecast_id, entry)
        return jsonify({"success": True, "workspace": _workspace_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/evaluation-cases", methods=["POST"])
def append_evaluation_case(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        case_payload = dict(data.get("evaluation_case") or {})
        case_payload.setdefault("case_id", _new_id("case"))
        case_payload.setdefault("forecast_id", forecast_id)
        case = EvaluationCase.from_dict(case_payload)
        workspace = ForecastManager().append_evaluation_case(forecast_id, case)
        return jsonify({"success": True, "workspace": _workspace_response(workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/evaluation-cases", methods=["GET"])
def list_evaluation_cases(forecast_id: str):
    try:
        workspace = ForecastManager().get_workspace(forecast_id)
        if workspace is None:
            return _json_error(f"Unknown forecast workspace: {forecast_id}", 404)
        return jsonify(
            {
                "success": True,
                "evaluation_cases": [item.to_dict() for item in workspace.evaluation_cases],
                "workspace": _workspace_response(workspace),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/evaluation-cases/<case_id>", methods=["GET"])
def get_evaluation_case(forecast_id: str, case_id: str):
    try:
        case = ForecastManager().get_evaluation_case(forecast_id, case_id)
        if case is None:
            return _json_error(f"Unknown evaluation case: {forecast_id}/{case_id}", 404)
        return jsonify({"success": True, "evaluation_case": case.to_dict()})
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/evaluation-cases/<case_id>", methods=["PATCH"])
def update_evaluation_case(forecast_id: str, case_id: str):
    try:
        data = request.get_json(force=True) or {}
        case_payload = dict(data.get("evaluation_case") or {})
        case_payload.setdefault("case_id", case_id)
        case_payload.setdefault("forecast_id", forecast_id)
        updated = ForecastManager().update_evaluation_case(
            forecast_id,
            case_id,
            EvaluationCase.from_dict(case_payload),
        )
        return jsonify({"success": True, "workspace": _workspace_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/evaluation-cases/<case_id>/resolve", methods=["POST"])
def resolve_evaluation_case(forecast_id: str, case_id: str):
    try:
        data = request.get_json(force=True) or {}
        updated = ForecastManager().resolve_evaluation_case(
            forecast_id,
            case_id,
            observed_outcome=data.get("observed_outcome"),
            resolved_at=data.get("resolved_at"),
            resolution_note=data.get("resolution_note"),
            answer_id=data.get("answer_id"),
        )
        return jsonify({"success": True, "workspace": _workspace_response(updated)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/forecast-answers", methods=["POST"])
def append_forecast_answer(forecast_id: str):
    try:
        data = request.get_json(force=True) or {}
        answer_payload = dict(data.get("forecast_answer") or {})
        answer_payload.setdefault("answer_id", _new_id("answer"))
        answer_payload.setdefault("forecast_id", forecast_id)
        answer_payload.setdefault("created_at", datetime.now().isoformat())
        answer = ForecastAnswer.from_dict(answer_payload)
        workspace = ForecastManager().append_forecast_answer(forecast_id, answer)
        return jsonify({"success": True, "workspace": _workspace_response(workspace)})
    except ValueError as exc:
        return _json_error(str(exc), 400 if "Unknown forecast workspace" not in str(exc) else 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(str(exc), 500)


@forecast_bp.route("/workspaces/<forecast_id>/forecast-answers/generate", methods=["POST"])
def generate_hybrid_forecast_answer_workspace(forecast_id: str):
    return generate_hybrid_forecast_answer(forecast_id)


@forecast_bp.route("/workspaces/<forecast_id>/hybrid-answer", methods=["POST"])
def generate_hybrid_forecast_answer_workspace_alias(forecast_id: str):
    return generate_hybrid_forecast_answer(forecast_id)
