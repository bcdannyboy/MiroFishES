"""
Signal-level provenance validation for simulation-derived forecast inputs.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ..config import Config
from ..models.simulation_market import (
    SUPPORTED_SIMULATION_MARKET_PROVENANCE_STATUSES,
    SimulationMarketManifest,
    SimulationMarketReference,
    SimulationMarketSummary,
)


def _line_count(path: str) -> int:
    with open(path, "r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


class ForecastSignalProvenanceValidator:
    """Validate that simulation-market signals remain traceable to run-scoped artifacts."""

    CRITICAL_SIGNALS = {
        "synthetic_consensus_probability",
        "disagreement_index",
        "scenario_split_distribution",
    }

    def __init__(self, *, simulation_data_dir: Optional[str] = None) -> None:
        self.simulation_data_dir = simulation_data_dir or Config.OASIS_SIMULATION_DATA_DIR

    def validate_simulation_market_summary(
        self,
        summary_payload: Dict[str, Any] | SimulationMarketSummary,
        *,
        available_evidence_bundle_ids: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        summary = (
            summary_payload
            if isinstance(summary_payload, SimulationMarketSummary)
            else SimulationMarketSummary.from_dict(summary_payload)
        )
        run_dir = os.path.join(
            self.simulation_data_dir,
            summary.simulation_id,
            "ensemble",
            f"ensemble_{summary.ensemble_id}",
            "runs",
            f"run_{summary.run_id}",
        )
        manifest = self._load_manifest(run_dir)
        listed_action_logs = set(manifest.source_artifacts.get("action_logs") or [])
        available_bundle_ids = set(available_evidence_bundle_ids or [])
        issues: list[str] = []
        downgrade_reasons: list[str] = []
        per_signal: Dict[str, Dict[str, Any]] = {}
        critical_failure = False

        if available_bundle_ids:
            missing_bundle_ids = [
                bundle_id
                for bundle_id in summary.evidence_bundle_ids
                if bundle_id not in available_bundle_ids
            ]
            if missing_bundle_ids:
                issues.append(
                    "unknown_evidence_bundle_ids:" + ",".join(sorted(missing_bundle_ids))
                )
                critical_failure = True

        for signal_name, references in summary.signal_provenance.items():
            valid_reference_count = 0
            invalid_reference_count = 0
            signal_issues: list[str] = []
            for reference_payload in references:
                try:
                    reference = (
                        reference_payload
                        if isinstance(reference_payload, SimulationMarketReference)
                        else SimulationMarketReference.from_dict(reference_payload)
                    )
                except Exception:
                    invalid_reference_count += 1
                    signal_issues.append("malformed_reference")
                    continue
                if reference.simulation_id != summary.simulation_id:
                    invalid_reference_count += 1
                    signal_issues.append("simulation_id_mismatch")
                    continue
                if summary.ensemble_id and reference.ensemble_id not in {None, summary.ensemble_id}:
                    invalid_reference_count += 1
                    signal_issues.append("ensemble_id_mismatch")
                    continue
                if summary.run_id and reference.run_id not in {None, summary.run_id}:
                    invalid_reference_count += 1
                    signal_issues.append("run_id_mismatch")
                    continue
                if reference.source_artifact not in listed_action_logs:
                    invalid_reference_count += 1
                    signal_issues.append("source_artifact_unlisted")
                    continue
                artifact_path = os.path.join(run_dir, reference.source_artifact)
                if not os.path.exists(artifact_path):
                    invalid_reference_count += 1
                    signal_issues.append("source_artifact_missing")
                    continue
                if reference.line_number <= 0 or reference.line_number > _line_count(artifact_path):
                    invalid_reference_count += 1
                    signal_issues.append("line_number_out_of_range")
                    continue
                valid_reference_count += 1

            if valid_reference_count > 0 and invalid_reference_count == 0:
                signal_status = "ready"
            elif signal_name in self.CRITICAL_SIGNALS and invalid_reference_count > 0:
                signal_status = "invalid"
                issues.append(f"invalid_signal_provenance:{signal_name}")
                critical_failure = True
            elif valid_reference_count > 0:
                signal_status = "partial"
                downgrade_reasons.append(f"partial_provenance:{signal_name}")
            else:
                signal_status = "invalid"
                if signal_name in self.CRITICAL_SIGNALS:
                    if references:
                        issues.append(f"invalid_signal_provenance:{signal_name}")
                    else:
                        issues.append(f"missing_signal_provenance:{signal_name}")
                    critical_failure = True
                else:
                    downgrade_reasons.append(f"missing_signal_provenance:{signal_name}")

            per_signal[signal_name] = {
                "status": signal_status,
                "valid_reference_count": valid_reference_count,
                "invalid_reference_count": invalid_reference_count,
                "issues": signal_issues,
            }

        critical_statuses = {
            signal_name: per_signal.get(signal_name, {}).get("status", "invalid")
            for signal_name in self.CRITICAL_SIGNALS
        }
        if critical_failure or any(status == "invalid" for status in critical_statuses.values()):
            status = "invalid"
            weight_multiplier = 0.0
            allow_best_estimate = False
        elif any(status == "partial" for status in critical_statuses.values()) or downgrade_reasons:
            status = "partial"
            weight_multiplier = 0.65
            allow_best_estimate = True
        else:
            status = "ready"
            weight_multiplier = 1.0
            allow_best_estimate = True

        if status not in SUPPORTED_SIMULATION_MARKET_PROVENANCE_STATUSES:
            status = "invalid"
            weight_multiplier = 0.0
            allow_best_estimate = False

        return {
            "status": status,
            "allow_best_estimate": allow_best_estimate,
            "weight_multiplier": weight_multiplier,
            "issues": issues,
            "downgrade_reasons": downgrade_reasons,
            "per_signal": per_signal,
        }

    def _load_manifest(self, run_dir: str) -> SimulationMarketManifest:
        manifest_path = os.path.join(run_dir, "simulation_market_manifest.json")
        if not os.path.exists(manifest_path):
            return SimulationMarketManifest(
                simulation_id="missing",
                ensemble_id=None,
                run_id=None,
                forecast_id=None,
                question_type=None,
                extraction_status="missing_action_logs",
                supported_question_type=False,
                forecast_workspace_linked=False,
                scope_linked_to_run=False,
                artifact_paths={},
                signal_counts={},
                warnings=["missing_manifest"],
                source_artifacts={},
                boundary_notes=[],
                extracted_at="2026-03-30T00:00:00",
            )
        with open(manifest_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return SimulationMarketManifest.from_dict(payload)
