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
from app.services.graph_backend import GraphBackendSettings  # noqa: E402
from app.services.graph_backend.live_probe import (  # noqa: E402
    apply_managed_local_graph_defaults,
    run_live_graphiti_probe,
)


def main() -> int:
    managed_local_defaults = apply_managed_local_graph_defaults()
    settings = GraphBackendSettings.from_env()
    live_probe = run_live_graphiti_probe(settings)

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
    passed = live_probe.get("status") == "passed"

    payload = {
        "status": "passed" if passed else "failed",
        "env_file_present": env_path.exists(),
        "graph_backend_keys_present": graph_backend_keys_present,
        "resolved_backend": settings.backend,
        "resolved_runtime_batch_size": settings.runtime_batch_size,
        "managed_local_defaults": managed_local_defaults,
        "live_probe": live_probe,
        "configuration_gaps": settings.validate(),
        "notes": [
            "This live probe validates repo .env plus managed-local defaults, local Neo4j startup, graph export, merged search, and runtime-history reads.",
            "The verification wrapper is green only when the graph-native probe passes end to end.",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
