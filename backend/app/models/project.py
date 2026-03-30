"""
Project context management.
Persists project state on the server so the frontend does not need to pass
large payloads between endpoints.
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config
from .grounding import (
    GROUNDING_GENERATOR_VERSION,
    GROUNDING_SCHEMA_VERSION,
)


class ProjectStatus(str, Enum):
    """Project status."""
    CREATED = "created"              # Newly created, files uploaded
    ONTOLOGY_GENERATED = "ontology_generated"  # Ontology generated
    GRAPH_BUILDING = "graph_building"    # Graph build in progress
    GRAPH_COMPLETED = "graph_completed"  # Graph build completed
    FAILED = "failed"                # Failed


@dataclass
class Project:
    """Project data model."""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # File information.
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # Ontology information, filled after API step 1.
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # Graph information, filled after API step 2.
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # Configuration.
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Error details.
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Build an instance from a dictionary."""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """Project manager responsible for persistence and retrieval."""
    
    # Root directory for persisted projects.
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """Ensure the project directory exists."""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """Return the project directory path."""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """Return the project metadata file path."""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """Return the project file storage directory."""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """Return the extracted text storage path for the project."""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')

    @classmethod
    def _get_source_manifest_path(cls, project_id: str) -> str:
        """Return the source-manifest artifact path for the project."""
        return os.path.join(cls._get_project_dir(project_id), 'source_manifest.json')

    @classmethod
    def _get_graph_build_summary_path(cls, project_id: str) -> str:
        """Return the graph-build summary artifact path for the project."""
        return os.path.join(
            cls._get_project_dir(project_id), 'graph_build_summary.json'
        )

    @classmethod
    def _get_graph_phase_timings_path(cls, project_id: str) -> str:
        """Return the graph phase-timing artifact path for the project."""
        return os.path.join(
            cls._get_project_dir(project_id), 'graph_phase_timings.json'
        )

    @classmethod
    def _get_graph_entity_index_path(cls, project_id: str) -> str:
        """Return the graph entity-index artifact path for the project."""
        return os.path.join(
            cls._get_project_dir(project_id), 'graph_entity_index.json'
        )
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        Create a new project.
        
        Args:
            name: Project name
            
        Returns:
            Newly created Project object
        """
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        
        # Create the project directory structure.
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # Persist project metadata.
        cls.save_project(project)
        
        return project
    
    @classmethod
    def save_project(cls, project: Project) -> None:
        """Save project metadata."""
        project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)
        cls._write_json(meta_path, project.to_dict())
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        Get a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project object, or `None` if it does not exist
        """
        meta_path = cls._get_project_meta_path(project_id)
        
        if not os.path.exists(meta_path):
            return None
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Project.from_dict(data)
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        List all projects.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            Project list in reverse chronological order
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # Sort by creation time in descending order.
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        Delete a project and all of its files.
        
        Args:
            project_id: Project ID
            
        Returns:
            Whether the deletion succeeded
        """
        project_dir = cls._get_project_dir(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        shutil.rmtree(project_dir)
        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        Save an uploaded file into the project directory.
        
        Args:
            project_id: Project ID
            file_storage: Flask FileStorage object
            original_filename: Original filename
            
        Returns:
            File information dictionary with filename, path, and size
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # Generate a safe filename.
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # Save the file.
        file_storage.save(file_path)
        
        # Get file size.
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }

    @classmethod
    def _write_json(cls, path: str, payload: Dict[str, Any]) -> None:
        """Persist a JSON artifact with stable formatting."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @classmethod
    def _read_json_if_exists(cls, path: str) -> Optional[Dict[str, Any]]:
        """Read one JSON artifact if it exists."""
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def save_source_manifest(cls, project_id: str, payload: Dict[str, Any]) -> None:
        """Persist the uploaded-source provenance artifact."""
        cls._write_json(cls._get_source_manifest_path(project_id), payload)

    @classmethod
    def get_source_manifest(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """Load the uploaded-source provenance artifact when present."""
        return cls._read_json_if_exists(cls._get_source_manifest_path(project_id))

    @classmethod
    def save_graph_build_summary(
        cls, project_id: str, payload: Dict[str, Any]
    ) -> None:
        """Persist the graph-build provenance artifact."""
        cls._write_json(cls._get_graph_build_summary_path(project_id), payload)

    @classmethod
    def get_graph_build_summary(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """Load the graph-build provenance artifact when present."""
        return cls._read_json_if_exists(cls._get_graph_build_summary_path(project_id))

    @classmethod
    def delete_graph_build_summary(cls, project_id: str) -> None:
        """Remove a stale graph-build summary artifact when the graph scope resets."""
        path = cls._get_graph_build_summary_path(project_id)
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def save_graph_phase_timings(cls, project_id: str, payload: Dict[str, Any]) -> None:
        """Persist the graph phase timing artifact."""
        cls._write_json(cls._get_graph_phase_timings_path(project_id), payload)

    @classmethod
    def get_graph_phase_timings(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """Load the graph phase timing artifact when present."""
        return cls._read_json_if_exists(cls._get_graph_phase_timings_path(project_id))

    @classmethod
    def delete_graph_phase_timings(cls, project_id: str) -> None:
        """Remove a stale graph timing artifact when the graph scope resets."""
        path = cls._get_graph_phase_timings_path(project_id)
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def save_graph_entity_index(cls, project_id: str, payload: Dict[str, Any]) -> None:
        """Persist the graph entity index artifact."""
        cls._write_json(cls._get_graph_entity_index_path(project_id), payload)

    @classmethod
    def get_graph_entity_index(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """Load the graph entity index artifact when present."""
        return cls._read_json_if_exists(cls._get_graph_entity_index_path(project_id))

    @classmethod
    def delete_graph_entity_index(cls, project_id: str) -> None:
        """Remove a stale graph entity index artifact when the graph scope resets."""
        path = cls._get_graph_entity_index_path(project_id)
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def describe_grounding_artifacts(cls, project_id: str) -> Dict[str, Dict[str, Any]]:
        """Return compact artifact metadata without inlining full grounding payloads."""
        project_dir = cls._get_project_dir(project_id)
        return {
            "source_manifest": cls._describe_json_artifact(
                cls._get_source_manifest_path(project_id),
                project_dir=project_dir,
                artifact_name="source_manifest",
            ),
            "graph_build_summary": cls._describe_json_artifact(
                cls._get_graph_build_summary_path(project_id),
                project_dir=project_dir,
                artifact_name="graph_build_summary",
            ),
            "graph_phase_timings": cls._describe_json_artifact(
                cls._get_graph_phase_timings_path(project_id),
                project_dir=project_dir,
                artifact_name="graph_phase_timings",
            ),
            "graph_entity_index": cls._describe_json_artifact(
                cls._get_graph_entity_index_path(project_id),
                project_dir=project_dir,
                artifact_name="graph_entity_index",
            ),
        }

    @classmethod
    def _describe_json_artifact(
        cls,
        path: str,
        *,
        project_dir: str,
        artifact_name: str,
    ) -> Dict[str, Any]:
        """Describe one project artifact with stable filename and version metadata."""
        exists = os.path.exists(path)
        description = {
            "artifact_type": artifact_name,
            "filename": os.path.basename(path),
            "path": path,
            "relative_path": os.path.relpath(path, project_dir),
            "exists": exists,
        }
        if not exists:
            description["schema_version"] = GROUNDING_SCHEMA_VERSION
            description["generator_version"] = GROUNDING_GENERATOR_VERSION
            return description

        description["size_bytes"] = os.path.getsize(path)
        payload = cls._read_json_if_exists(path)
        if payload:
            for field_name in (
                "artifact_type",
                "schema_version",
                "generator_version",
                "created_at",
                "generated_at",
                "status",
                "project_id",
                "graph_id",
                "source_count",
                "chunk_count",
            ):
                if field_name in payload:
                    description[field_name] = payload[field_name]
        return description
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """Save extracted text."""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """Get extracted text."""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """Get all file paths for a project."""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
