#!/usr/bin/env python3
"""Live runtime graph validation using the real repo .env/defaults."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (BACKEND_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


from app.config import project_root_env  # noqa: E402
from app.services.graph_backend import (  # noqa: E402
    GraphBackendSettings,
    build_graph_backend_service,
)
from app.services.graph_backend.neo4j_factory import probe_neo4j_endpoint  # noqa: E402
from app.services.runtime_graph_updater import RuntimeGraphActivity  # noqa: E402


def main() -> int:
    settings = GraphBackendSettings.from_env()
    backend = build_graph_backend_service(settings)
    descriptor = backend.create_runtime_graph(
        simulation_id="live-probe",
        ensemble_id="0000",
        run_id="0000",
        project_id="live-probe",
        project_name="Live Probe",
    )
    sample_event = RuntimeGraphActivity(
        base_graph_id="mirofish-base-live-probe",
        runtime_graph_id=descriptor.namespace_id,
        run_key="live-probe::0000::0000",
        platform="twitter",
        agent_id=1,
        agent_name="Live Probe",
        action_type="CREATE_POST",
        action_args={"content": "Runtime live probe", "topic": "Live Probe"},
        round_num=1,
        timestamp="2026-03-31T12:00:00",
    ).to_event_payload()

    env_path = Path(project_root_env).resolve()
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    graph_backend_keys_present = [
        key
        for key in (
            "GRAPH_BACKEND",
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "GRAPHITI_EXTRACTION_MODEL",
            "GRAPHITI_EMBEDDING_MODEL",
        )
        if f"{key}=" in env_text
    ]
    neo4j_probe = probe_neo4j_endpoint(settings, timeout_seconds=1.0)
    passed = bool(env_path.exists() and neo4j_probe.get("reachable"))

    payload = {
        "status": "passed" if passed else "failed",
        "env_file_present": env_path.exists(),
        "graph_backend_keys_present": graph_backend_keys_present,
        "resolved_backend": settings.backend,
        "resolved_runtime_batch_size": settings.runtime_batch_size,
        "resolved_runtime_namespace": descriptor.to_dict(),
        "sample_runtime_event": {
            "artifact_type": sample_event["artifact_type"],
            "runtime_graph_id": sample_event["runtime_graph_id"],
            "transition_type": sample_event["transition_type"],
            "source_artifact": sample_event["source_artifact"],
        },
        "configuration_gaps": settings.validate(),
        "neo4j_probe": neo4j_probe,
        "notes": [
            "This live probe validates real .env/default resolution, runtime namespace construction, runtime event serialization, and local Neo4j reachability.",
            "It does not claim live Graphiti ingestion succeeded when graphiti-core or Neo4j auth is not available in the local environment.",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
