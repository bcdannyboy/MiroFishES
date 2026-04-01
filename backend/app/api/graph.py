"""
Graph-related API routes.
Uses a project context mechanism with server-persisted state.
"""

import os
import hashlib
import traceback
import threading
from flask import request, jsonify, current_app
from werkzeug.exceptions import RequestEntityTooLarge

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.phase_timing import PhaseTimingRecorder
from ..services.text_processor import TextProcessor
from ..services.forecast_graph import (
    build_chunk_records,
    build_episode_chunk_map,
    build_layered_graph_index,
    summarize_graph_snapshot,
)
from ..services.graph_backend import describe_graph_backend_readiness
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus
from ..models.grounding import (
    GROUNDING_GENERATOR_VERSION,
    GROUNDING_SCHEMA_VERSION,
    SOURCE_BOUNDARY_NOTE,
)
from ..models.source_units import (
    build_source_units_artifact,
    build_stable_source_id,
)

# Get logger
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """Check whether the file extension is allowed."""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


def _classify_content_kind(filename: str) -> str:
    """Classify one uploaded file coarsely for provenance reporting."""
    extension = os.path.splitext(filename or "")[1].lower()
    if extension in {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml"}:
        return "code"
    if extension in {".md", ".txt", ".pdf", ".docx", ".csv"}:
        return "document"
    return "unknown"


def _sha256_file(path: str) -> str:
    """Hash one stored file for durable source identity."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _project_payload(project):
    """Serialize one project plus compact grounding artifact summaries."""
    return {
        **project.to_dict(),
        "grounding_artifacts": ProjectManager.describe_grounding_artifacts(
            project.project_id
        ),
    }


def _upload_too_large_response():
    """Build a consistent 413 response for multipart uploads that exceed the limit."""
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", Config.MAX_CONTENT_LENGTH)
    if not max_bytes:
        limit_label = "configured size limit"
    elif max_bytes >= 1024 * 1024:
        max_megabytes = max_bytes / (1024 * 1024)
        if float(max_megabytes).is_integer():
            limit_label = f"{int(max_megabytes)} MB"
        else:
            limit_label = f"{max_megabytes:.1f} MB"
    elif max_bytes >= 1024:
        max_kilobytes = max_bytes / 1024
        if float(max_kilobytes).is_integer():
            limit_label = f"{int(max_kilobytes)} KB"
        else:
            limit_label = f"{max_kilobytes:.1f} KB"
    else:
        limit_label = f"{max_bytes} bytes"
    return jsonify({
        "success": False,
        "error": (
            f"Upload exceeds the {limit_label} limit. "
            "Remove some files or split the upload into smaller batches."
        ),
        "max_upload_bytes": max_bytes,
    }), 413


@graph_bp.route('/backend/readiness', methods=['GET'])
def get_graph_backend_readiness():
    """Expose Prompt 1 Graphiti + Neo4j readiness without mutating graph state."""
    return jsonify({
        "success": True,
        "data": describe_graph_backend_readiness(),
    })


# ============== Project management endpoints ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    Get project details.
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": _project_payload(project)
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    List all projects.
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [_project_payload(p) for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    Delete a project.
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"Project not found or failed to delete: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "message": f"Project deleted: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    Reset project state for rebuilding the graph.
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404
    
    # Reset to the ontology-generated state
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.delete_graph_build_summary(project_id)
    ProjectManager.delete_graph_entity_index(project_id)
    ProjectManager.delete_graph_phase_timings(project_id)
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": f"Project reset: {project_id}",
        "data": _project_payload(project)
    })


# ============== Interface 1: upload files and generate ontology ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    Interface 1: upload files and analyze them to generate an ontology definition.

    Request type: multipart/form-data

    Parameters:
        files: Uploaded files (PDF/MD/TXT), multiple allowed
        simulation_requirement: Simulation requirement description (required)
        project_name: Project name (optional)
        additional_context: Additional notes (optional)

    Returns:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== Starting ontology generation ===")
        
        # Get parameters
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        
        logger.debug(f"Project name: {project_name}")
        logger.debug(f"Simulation requirement: {simulation_requirement[:100]}...")
        
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_requirement"
            }), 400
        
        # Get uploaded files
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "Please upload at least one document file"
            }), 400
        
        # Create project
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"Created project: {project.project_id}")
        phase_timing = PhaseTimingRecorder(
            artifact_path=ProjectManager._get_graph_phase_timings_path(project.project_id),
            scope_kind="project",
            scope_id=project.project_id,
        )

        # Save files and extract text
        document_texts = []
        all_text = ""
        source_records = []
        source_units = []

        with phase_timing.measure_phase(
            "upload_parse",
            metadata={
                "uploaded_file_count": len(uploaded_files),
                "parsed_file_count": 0,
                "failed_file_count": 0,
                "total_text_length": 0,
                "source_unit_count": 0,
            },
        ) as upload_metadata:
            for source_index, file in enumerate(uploaded_files, start=1):
                if file and file.filename and allowed_file(file.filename):
                    # Save file to the project directory
                    file_info = ProjectManager.save_file_to_project(
                        project.project_id, 
                        file, 
                        file.filename
                    )
                    project.files.append({
                        "filename": file_info["original_filename"],
                        "size": file_info["size"]
                    })

                    extracted_text = ""
                    extraction_status = "succeeded"
                    parser_warnings = []
                    parsed_document = None
                    try:
                        parsed_document = FileParser.extract_document(file_info["path"])
                        extracted_text = parsed_document["text"]
                        parser_warnings.extend(parsed_document.get("extraction_warnings", []))
                        extracted_text = TextProcessor.preprocess_text(extracted_text)
                    except Exception as exc:
                        extraction_status = "failed"
                        parser_warnings.append(str(exc))
                        logger.warning(
                            "File extraction failed for %s: %s",
                            file_info["original_filename"],
                            exc,
                        )

                    combined_text_start = None
                    combined_text_end = None
                    combined_source_text_start = None
                    if extracted_text:
                        prefix = f"\n\n=== {file_info['original_filename']} ===\n"
                        combined_text_start = len(all_text)
                        combined_source_text_start = combined_text_start + len(prefix)
                        all_text += prefix + extracted_text
                        combined_text_end = len(all_text)
                        document_texts.append(extracted_text)

                    source_sha256 = (
                        parsed_document.get("sha256")
                        if isinstance(parsed_document, dict)
                        else _sha256_file(file_info["path"])
                    )
                    stable_source_id = build_stable_source_id(source_sha256)
                    source_record = {
                        "source_id": f"src-{source_index}",
                        "stable_source_id": stable_source_id,
                        "original_filename": file_info["original_filename"],
                        "saved_filename": file_info["saved_filename"],
                        "relative_path": os.path.relpath(
                            file_info["path"],
                            ProjectManager._get_project_dir(project.project_id),
                        ),
                        "size_bytes": file_info["size"],
                        "sha256": source_sha256,
                        "content_kind": _classify_content_kind(
                            file_info["original_filename"]
                        ),
                        "extraction_status": extraction_status,
                        "extracted_text_length": len(extracted_text),
                        "combined_text_start": combined_source_text_start,
                        "combined_text_end": combined_text_end,
                        "parser_warnings": parser_warnings,
                        "excerpt": extracted_text[:280],
                        "source_order": source_index,
                    }
                    source_records.append(source_record)

                    if extracted_text:
                        source_units.extend(
                            TextProcessor.build_source_units(
                                text=extracted_text,
                                source_record=source_record,
                                combined_text_start=combined_source_text_start,
                            )
                        )

            upload_metadata["parsed_file_count"] = len(
                [item for item in source_records if item["extraction_status"] == "succeeded"]
            )
            upload_metadata["failed_file_count"] = len(source_records) - upload_metadata["parsed_file_count"]
            upload_metadata["total_text_length"] = len(all_text)
            upload_metadata["source_unit_count"] = len(source_units)
        
        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "No documents were processed successfully. Please check the file format."
            }), 400
        
        # Save extracted text
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"Text extraction completed, {len(all_text)} characters total")
        
        # Generate ontology
        logger.info("Calling LLM to generate ontology definition...")
        generator = OntologyGenerator()
        with phase_timing.measure_phase(
            "ontology_generation",
            metadata={"entity_type_count": 0, "edge_type_count": 0},
        ) as ontology_metadata:
            ontology = generator.generate(
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
                additional_context=additional_context if additional_context else None
            )
            ontology_metadata["entity_type_count"] = len(ontology.get("entity_types", []))
            ontology_metadata["edge_type_count"] = len(ontology.get("edge_types", []))
        
        # Save ontology to the project
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"Ontology generation completed: {entity_count} entity types, {edge_count} edge types")
        
        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", []),
            "schema_mode": ontology.get("schema_mode"),
            "actor_types": ontology.get("actor_types", []),
            "analytical_types": ontology.get("analytical_types", []),
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        ProjectManager.save_source_manifest(
            project.project_id,
            {
                "artifact_type": "source_manifest",
                "schema_version": GROUNDING_SCHEMA_VERSION,
                "generator_version": GROUNDING_GENERATOR_VERSION,
                "project_id": project.project_id,
                "created_at": project.updated_at,
                "simulation_requirement": simulation_requirement,
                "boundary_note": SOURCE_BOUNDARY_NOTE,
                "source_artifacts": {"source_units": "source_units.json"},
                "source_count": len(source_records),
                "sources": source_records,
            },
        )
        ProjectManager.save_source_units(
            project.project_id,
            build_source_units_artifact(
                project_id=project.project_id,
                created_at=project.updated_at,
                simulation_requirement=simulation_requirement,
                source_records=source_records,
                units=source_units,
            ),
        )
        logger.info(f"=== Ontology generation completed === project_id: {project.project_id}")
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length,
                "grounding_artifacts": ProjectManager.describe_grounding_artifacts(
                    project.project_id
                ),
            }
        })
        
    except RequestEntityTooLarge:
        max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", Config.MAX_CONTENT_LENGTH)
        logger.warning(
            "Ontology generation upload rejected because the multipart payload exceeds %s bytes",
            max_bytes,
        )
        return _upload_too_large_response()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interface 2: build graph ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    Interface 2: build a graph from project_id.

    Request (JSON):
        {
            "project_id": "proj_xxxx",  // required, from Interface 1
            "graph_name": "Graph name", // optional
            "chunk_size": 500,          // optional, default 500
            "chunk_overlap": 50         // optional, default 50
        }
        
    Returns:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "Graph build task started"
            }
        }
    """
    try:
        logger.info("=== Starting graph build ===")
        
        # Check configuration
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        if errors:
            logger.error(f"Configuration error: {errors}")
            return jsonify({
                "success": False,
                "error": "Configuration error: " + "; ".join(errors)
            }), 500
        
        # Parse request
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"Request params: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400
        
        # Get project
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project not found: {project_id}"
            }), 404
        
        # Check project status
        force = data.get('force', False)  # Force rebuild
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": "The project has not generated an ontology yet. Please call /ontology/generate first."
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "The graph is already building. Do not submit again. To force a rebuild, set force: true.",
                "task_id": project.graph_build_task_id
            }), 400
        
        # Reset state if forcing a rebuild
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
            ProjectManager.delete_graph_build_summary(project_id)
            ProjectManager.delete_graph_entity_index(project_id)
            ProjectManager.delete_graph_phase_timings(project_id)
        
        # Get configuration
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # Update project configuration
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # Get extracted text
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "Extracted text content not found"
            }), 400
        
        # Get ontology
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "Ontology definition not found"
            }), 400
        
        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"Building graph: {graph_name}")
        logger.info(f"Created graph build task: task_id={task_id}, project_id={project_id}")
        
        # Update project status
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # Start background task
        def build_task():
            build_logger = get_logger('mirofish.build')
            try:
                build_logger.info(f"[{task_id}] Starting graph build...")
                phase_timing = PhaseTimingRecorder(
                    artifact_path=ProjectManager._get_graph_phase_timings_path(project_id),
                    scope_kind="project",
                    scope_id=project_id,
                )
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message="Initializing graph builder service..."
                )
                
                # Create graph builder service
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # Split text
                task_manager.update_task(
                    task_id,
                    message="Splitting text...",
                    progress=5
                )
                source_units_artifact = ProjectManager.get_source_units(project_id)
                source_units_payload = (
                    source_units_artifact.get("units")
                    if isinstance(source_units_artifact, dict)
                    else None
                )
                if source_units_payload:
                    chunk_records = build_chunk_records(
                        text,
                        chunk_size=chunk_size,
                        overlap=chunk_overlap,
                        source_units=source_units_payload,
                    )
                else:
                    plain_chunks = TextProcessor.split_text(
                        text,
                        chunk_size=chunk_size,
                        overlap=chunk_overlap,
                    )
                    chunk_records = [
                        {
                            "chunk_id": f"chunk-{index:04d}",
                            "text": chunk,
                            "char_start": None,
                            "char_end": None,
                            "source_unit_ids": [],
                            "source_ids": [],
                            "stable_source_ids": [],
                            "unit_types": [],
                        }
                        for index, chunk in enumerate(plain_chunks, start=1)
                    ]
                chunks = [record["text"] for record in chunk_records]
                total_chunks = len(chunks)
                
                # Create graph
                task_manager.update_task(
                    task_id,
                    message="Creating Zep graph...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # Update the project's graph_id
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # Set ontology
                task_manager.update_task(
                    task_id,
                    message="Setting ontology definition...",
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)
                
                # Add text (progress_callback signature is (msg, progress_ratio))
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=f"Starting to add {total_chunks} text chunks...",
                    progress=15
                )

                with phase_timing.measure_phase(
                    "graph_batch_send",
                    metadata={"chunk_count": total_chunks},
                ) as batch_metadata:
                    episode_uuids = builder.add_text_batches(
                        graph_id,
                        chunks,
                        progress_callback=add_progress_callback,
                    )
                    batch_metadata["episode_count"] = len(episode_uuids)
                episode_chunk_map = build_episode_chunk_map(episode_uuids, chunk_records)
                
                # Wait for Zep processing to finish (check each episode's processed status)
                task_manager.update_task(
                    task_id,
                    message="Waiting for Zep to process data...",
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                with phase_timing.measure_phase(
                    "graph_wait",
                    metadata={"episode_count": len(episode_uuids)},
                ):
                    builder._wait_for_episodes(
                        graph_id,
                        episode_uuids,
                        wait_progress_callback,
                    )

                # Fetch graph snapshot
                task_manager.update_task(
                    task_id,
                    message="Fetching graph snapshot...",
                    progress=95
                )
                graph_snapshot = builder.get_graph_snapshot(graph_id)
                graph_counts = (
                    graph_snapshot.get("graph_counts")
                    if isinstance(graph_snapshot, dict)
                    else None
                ) or summarize_graph_snapshot(graph_snapshot)
                layered_index = build_layered_graph_index(
                    snapshot=graph_snapshot,
                    source_units=source_units_payload,
                    episode_chunk_map=episode_chunk_map,
                )
                
                # Update project status
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                graph_summary_warnings = []
                if not ProjectManager.get_source_manifest(project_id):
                    graph_summary_warnings.append("missing_source_manifest")
                source_units_summary = ProjectManager.get_source_units(project_id)
                ProjectManager.save_graph_build_summary(
                    project_id,
                    {
                        "artifact_type": "graph_build_summary",
                        "schema_version": GROUNDING_SCHEMA_VERSION,
                        "generator_version": GROUNDING_GENERATOR_VERSION,
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "generated_at": project.updated_at,
                        "source_artifacts": (
                            {
                                **(
                                    {"source_manifest": "source_manifest.json"}
                                    if ProjectManager.get_source_manifest(project_id)
                                    else {}
                                ),
                                **(
                                    {"source_units": "source_units.json"}
                                    if source_units_summary
                                    else {}
                                ),
                            }
                        ),
                        "ontology_summary": {
                            "analysis_summary": project.analysis_summary,
                            "entity_type_count": len(
                                (ontology or {}).get("entity_types", [])
                            ),
                            "edge_type_count": len(
                                (ontology or {}).get("edge_types", [])
                            ),
                            "entity_types": [
                                item.get("name", "")
                                for item in (ontology or {}).get("entity_types", [])
                                if isinstance(item, dict)
                            ],
                            "edge_types": [
                                item.get("name", "")
                                for item in (ontology or {}).get("edge_types", [])
                                if isinstance(item, dict)
                            ],
                        },
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "chunk_count": total_chunks,
                        "chunking_strategy": (
                            "semantic_source_units"
                            if source_units_summary
                            else "fixed_char_fallback"
                        ),
                        "source_unit_count": (
                            len((source_units_summary or {}).get("units", []))
                            if source_units_summary
                            else 0
                        ),
                        "graph_counts": {
                            **graph_counts,
                        },
                        "citation_coverage": layered_index.get(
                            "citation_coverage", {}
                        ),
                        "warnings": graph_summary_warnings,
                    },
                )
                ProjectManager.save_graph_entity_index(
                    project_id,
                    {
                        "artifact_type": "graph_entity_index",
                        "schema_version": GROUNDING_SCHEMA_VERSION,
                        "generator_version": GROUNDING_GENERATOR_VERSION,
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "generated_at": project.updated_at,
                        **layered_index,
                    },
                )
                
                node_count = graph_snapshot.get("node_count", 0)
                edge_count = graph_snapshot.get("edge_count", 0)
                build_logger.info(f"[{task_id}] Graph build completed: graph_id={graph_id}, nodes={node_count}, edges={edge_count}")
                
                # Complete
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="Graph build completed",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # Mark project as failed
                build_logger.error(f"[{task_id}] Graph build failed: {str(e)}")
                build_logger.debug(traceback.format_exc())
                
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"Build failed: {str(e)}",
                    error=traceback.format_exc()
                )
        
        # Start background thread
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "Graph build task started. Check progress via /task/{task_id}"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Task query endpoints ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    Query task status.
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": f"Task not found: {task_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    List all tasks.
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== Graph data endpoints ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    Get graph data (nodes and edges).
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY is not configured"
            }), 500
        
        mode = request.args.get('mode', 'full')
        max_nodes = request.args.get('max_nodes', type=int)
        max_edges = request.args.get('max_edges', type=int)

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(
            graph_id,
            mode=mode,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    Delete a Zep graph.
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY is not configured"
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": f"Graph deleted: {graph_id}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
