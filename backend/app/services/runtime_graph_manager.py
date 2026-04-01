"""Per-run runtime graph provisioning for probabilistic stored runs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger
from .ensemble_manager import EnsembleManager
from .graph_builder import GraphBuilderService
from .runtime_graph_state_store import RuntimeGraphStateStore

logger = get_logger('mirofish.runtime_graph')


class RuntimeGraphManager:
    """Provision and reset runtime-only graphs for stored probabilistic runs."""

    def __init__(
        self,
        *,
        graph_builder: Optional[GraphBuilderService] = None,
        ensemble_manager: Optional[EnsembleManager] = None,
    ) -> None:
        self.graph_builder = graph_builder or GraphBuilderService()
        self.ensemble_manager = ensemble_manager or EnsembleManager()

    def provision_runtime_graph(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
        state: Any,
        force_reset: bool = False,
    ) -> dict[str, Optional[str]]:
        """Create one fresh runtime graph for a stored run and persist its IDs."""
        base_graph_id, project = self._resolve_base_graph_context(state)
        existing = self.ensemble_manager.load_run(simulation_id, ensemble_id, run_id)
        existing_runtime_graph_id = (
            existing.get("run_manifest", {}).get("runtime_graph_id")
        )
        if existing_runtime_graph_id:
            self._delete_graph_safe(existing_runtime_graph_id)

        graph_name = self._build_runtime_graph_name(
            project_name=(project.name if project else None),
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )
        runtime_graph_id = self.graph_builder.create_graph(graph_name)
        ontology = project.ontology if project else None
        if ontology:
            self.graph_builder.set_ontology(runtime_graph_id, ontology)
        runtime_artifacts = self._initialize_runtime_state(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            project_id=getattr(project, "project_id", None) or getattr(state, "project_id", None),
            base_graph_id=base_graph_id,
            runtime_graph_id=runtime_graph_id,
        )

        self._persist_run_graph_ids(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            base_graph_id=base_graph_id,
            runtime_graph_id=runtime_graph_id,
            runtime_artifacts=runtime_artifacts,
        )
        logger.info(
            "Provisioned runtime graph: simulation_id=%s ensemble_id=%s run_id=%s "
            "base_graph_id=%s runtime_graph_id=%s force_reset=%s",
            simulation_id,
            ensemble_id,
            run_id,
            base_graph_id,
            runtime_graph_id,
            force_reset,
        )
        return {
            "base_graph_id": base_graph_id,
            "runtime_graph_id": runtime_graph_id,
            "graph_id": base_graph_id,
        }

    def cleanup_runtime_graph(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
    ) -> dict[str, Optional[str]]:
        """Delete any runtime graph linked to one stored run and clear the manifest."""
        run_payload = self.ensemble_manager.load_run(simulation_id, ensemble_id, run_id)
        run_manifest = run_payload.get("run_manifest", {})
        base_graph_id = (
            run_manifest.get("base_graph_id")
            or run_manifest.get("graph_id")
            or run_payload.get("resolved_config", {}).get("base_graph_id")
            or run_payload.get("resolved_config", {}).get("graph_id")
        )
        runtime_graph_id = run_manifest.get("runtime_graph_id")
        if runtime_graph_id:
            self._delete_graph_safe(runtime_graph_id)
        self._delete_runtime_artifacts(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
        )

        self._persist_run_graph_ids(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            base_graph_id=base_graph_id,
            runtime_graph_id=None,
            runtime_artifacts={},
        )
        logger.info(
            "Cleared runtime graph: simulation_id=%s ensemble_id=%s run_id=%s "
            "base_graph_id=%s deleted_runtime_graph_id=%s",
            simulation_id,
            ensemble_id,
            run_id,
            base_graph_id,
            runtime_graph_id,
        )
        return {
            "base_graph_id": base_graph_id,
            "runtime_graph_id": None,
            "deleted_runtime_graph_id": runtime_graph_id,
            "graph_id": base_graph_id,
        }

    def _resolve_base_graph_context(self, state: Any) -> tuple[str, Any]:
        """Resolve the immutable project graph and project metadata."""
        project = None
        project_id = getattr(state, "project_id", None)
        if project_id:
            project = ProjectManager.get_project(project_id)

        base_graph_id = (
            getattr(state, "base_graph_id", None)
            or getattr(state, "graph_id", None)
            or (project.graph_id if project else None)
        )
        if not base_graph_id:
            raise ValueError(
                "A valid base graph_id is required to enable graph memory updates. "
                "Please make sure the project graph has been built."
            )
        return str(base_graph_id), project

    def _persist_run_graph_ids(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
        base_graph_id: Optional[str],
        runtime_graph_id: Optional[str],
        runtime_artifacts: Optional[dict[str, str]] = None,
    ) -> None:
        """Keep stored run artifacts aligned with runtime graph ownership."""
        run_dir = self.ensemble_manager._get_run_dir(simulation_id, ensemble_id, run_id)
        manifest_path = os.path.join(run_dir, EnsembleManager.RUN_MANIFEST_FILENAME)
        resolved_config_path = os.path.join(run_dir, EnsembleManager.RESOLVED_CONFIG_FILENAME)

        if os.path.exists(manifest_path):
            manifest = self._read_json(manifest_path)
            manifest["base_graph_id"] = base_graph_id
            manifest["runtime_graph_id"] = runtime_graph_id
            manifest["graph_id"] = base_graph_id
            artifact_paths = manifest.setdefault("artifact_paths", {})
            for key in (
                "runtime_graph_base_snapshot",
                "runtime_graph_state",
                "runtime_graph_updates",
            ):
                artifact_paths.pop(key, None)
            if runtime_artifacts:
                artifact_paths.update(runtime_artifacts)
            manifest["updated_at"] = datetime.now().isoformat()
            self._write_json(manifest_path, manifest)

        if os.path.exists(resolved_config_path):
            resolved_config = self._read_json(resolved_config_path)
            resolved_config["base_graph_id"] = base_graph_id
            resolved_config["runtime_graph_id"] = runtime_graph_id
            resolved_config["graph_id"] = base_graph_id
            for field in (
                "runtime_graph_base_snapshot_artifact",
                "runtime_graph_state_artifact",
                "runtime_graph_updates_artifact",
            ):
                resolved_config.pop(field, None)
            if runtime_artifacts:
                resolved_config["runtime_graph_base_snapshot_artifact"] = runtime_artifacts.get(
                    "runtime_graph_base_snapshot"
                )
                resolved_config["runtime_graph_state_artifact"] = runtime_artifacts.get(
                    "runtime_graph_state"
                )
                resolved_config["runtime_graph_updates_artifact"] = runtime_artifacts.get(
                    "runtime_graph_updates"
                )
            resolved_config["updated_at"] = datetime.now().isoformat()
            self._write_json(resolved_config_path, resolved_config)

    def _initialize_runtime_state(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
        project_id: Optional[str],
        base_graph_id: str,
        runtime_graph_id: str,
    ) -> dict[str, str]:
        sim_dir = self.ensemble_manager._get_simulation_dir(simulation_id)
        run_dir = self.ensemble_manager._get_run_dir(simulation_id, ensemble_id, run_id)
        store = RuntimeGraphStateStore(run_dir)
        store.initialize(
            simulation_id=simulation_id,
            ensemble_id=ensemble_id,
            run_id=run_id,
            project_id=project_id,
            base_graph_id=base_graph_id,
            runtime_graph_id=runtime_graph_id,
            prepared_world_state=self._read_json_if_exists(
                os.path.join(sim_dir, "prepared_world_state.json")
            ),
            prepared_agent_states=self._read_json_if_exists(
                os.path.join(sim_dir, "prepared_agent_states.json")
            ),
            graph_index_payload=ProjectManager.get_graph_entity_index(project_id)
            if project_id
            else None,
        )
        return store.artifact_paths()

    def _delete_runtime_artifacts(
        self,
        *,
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
    ) -> None:
        run_dir = self.ensemble_manager._get_run_dir(simulation_id, ensemble_id, run_id)
        RuntimeGraphStateStore(run_dir).delete_artifacts()

    def _read_json_if_exists(self, file_path: str) -> Optional[dict[str, Any]]:
        if not os.path.exists(file_path):
            return None
        return self._read_json(file_path)

    def _delete_graph_safe(self, graph_id: str) -> None:
        """Delete a graph best-effort so cleanup does not wedge on stale IDs."""
        try:
            self.graph_builder.delete_graph(graph_id)
        except Exception as exc:
            logger.warning("Failed to delete runtime graph %s: %s", graph_id, exc)

    def _build_runtime_graph_name(
        self,
        *,
        project_name: Optional[str],
        simulation_id: str,
        ensemble_id: str,
        run_id: str,
    ) -> str:
        """Produce one stable human-readable runtime graph name."""
        name_root = (project_name or "MiroFish Runtime").strip()
        return (
            f"{name_root} Runtime {simulation_id[-6:]} "
            f"E{ensemble_id} R{run_id}"
        )

    def _read_json(self, file_path: str) -> dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, file_path: str, payload: dict[str, Any]) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
