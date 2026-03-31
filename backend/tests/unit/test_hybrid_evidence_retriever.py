from __future__ import annotations

import importlib
import json
from pathlib import Path


QUESTION_ISSUED_AT = "2026-03-30T09:00:00"


class _FakeEmbeddingClient:
    def embed_text(self, text: str, *, normalize: bool = True) -> list[float]:
        return self.embed_texts([text], normalize=normalize)[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        normalize: bool = True,
    ) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if any(token in lowered for token in ("june", "cut", "rate")) else 0.0,
                    1.0 if any(token in lowered for token in ("payroll", "hiring", "support", "likely")) else 0.0,
                    1.0 if any(token in lowered for token in ("inflation", "delay", "sticky", "contradict")) else 0.0,
                ]
            )
        return vectors


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _configure_projects_dir(monkeypatch, tmp_path: Path):
    project_module = importlib.import_module("app.models.project")
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(projects_dir),
        raising=False,
    )
    return projects_dir


def _seed_project_artifacts(projects_dir: Path, *, project_id: str) -> str:
    project_dir = projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    unit_support_id = "su-test-0001"
    unit_contra_id = "su-test-0002"
    _write_json(
        project_dir / "source_units.json",
        {
            "artifact_type": "source_units",
            "project_id": project_id,
            "source_count": 1,
            "unit_count": 2,
            "units": [
                {
                    "unit_id": unit_support_id,
                    "source_id": "src-1",
                    "stable_source_id": "src-alpha",
                    "source_sha256": "sha-support",
                    "original_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "source_order": 1,
                    "unit_order": 1,
                    "unit_type": "paragraph",
                    "char_start": 0,
                    "char_end": 86,
                    "combined_text_start": 0,
                    "combined_text_end": 86,
                    "text": "Payroll preview showed weaker hiring, supporting a June rate cut.",
                    "metadata": {},
                    "extraction_warnings": [],
                },
                {
                    "unit_id": unit_contra_id,
                    "source_id": "src-1",
                    "stable_source_id": "src-alpha",
                    "source_sha256": "sha-support",
                    "original_filename": "memo.md",
                    "relative_path": "files/memo.md",
                    "source_order": 1,
                    "unit_order": 2,
                    "unit_type": "paragraph",
                    "char_start": 88,
                    "char_end": 176,
                    "combined_text_start": 88,
                    "combined_text_end": 176,
                    "text": "Sticky inflation could delay cuts and contradict the stronger easing case.",
                    "metadata": {},
                    "extraction_warnings": [],
                },
            ],
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "project_id": project_id,
            "graph_id": "graph-test",
            "total_count": 0,
            "filtered_count": 0,
            "entity_types": [],
            "entities": [],
            "analytical_object_count": 2,
            "analytical_types": ["Claim", "UncertaintyFactor"],
            "analytical_objects": [
                {
                    "uuid": "claim-1",
                    "name": "June cut likely",
                    "labels": ["Claim"],
                    "summary": "A June rate cut is increasingly likely after the weaker payroll preview.",
                    "attributes": {"claim_text": "June rate cut likely"},
                    "related_edges": [
                        {
                            "direction": "outgoing",
                            "edge_name": "SUPPORTED_BY",
                            "fact": "A June rate cut is supported by the payroll preview.",
                            "target_node_uuid": "evidence-1",
                            "provenance": {
                                "episode_ids": ["ep-1"],
                                "chunk_ids": ["chunk-0001"],
                                "source_unit_ids": [unit_support_id],
                                "source_ids": ["src-1"],
                                "stable_source_ids": ["src-alpha"],
                                "citation_count": 1,
                                "citations": [
                                    {
                                        "unit_id": unit_support_id,
                                        "source_id": "src-1",
                                        "stable_source_id": "src-alpha",
                                        "original_filename": "memo.md",
                                        "relative_path": "files/memo.md",
                                        "unit_type": "paragraph",
                                        "source_order": 1,
                                        "unit_order": 1,
                                        "char_start": 0,
                                        "char_end": 86,
                                        "combined_text_start": 0,
                                        "combined_text_end": 86,
                                        "text_excerpt": "Payroll preview showed weaker hiring, supporting a June rate cut.",
                                        "reason": "episode_linked",
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [],
                    "object_type": "Claim",
                    "layer": "analytical",
                    "provenance": {
                        "match_reason": "edge_episode",
                        "episode_ids": ["ep-1"],
                        "chunk_ids": ["chunk-0001"],
                        "source_unit_ids": [unit_support_id],
                        "source_ids": ["src-1"],
                        "stable_source_ids": ["src-alpha"],
                        "citation_count": 1,
                        "citations": [
                            {
                                "unit_id": unit_support_id,
                                "source_id": "src-1",
                                "stable_source_id": "src-alpha",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "source_order": 1,
                                "unit_order": 1,
                                "char_start": 0,
                                "char_end": 86,
                                "combined_text_start": 0,
                                "combined_text_end": 86,
                                "text_excerpt": "Payroll preview showed weaker hiring, supporting a June rate cut.",
                                "reason": "edge_episode",
                            }
                        ],
                    },
                },
                {
                    "uuid": "risk-1",
                    "name": "Sticky inflation risk",
                    "labels": ["UncertaintyFactor"],
                    "summary": "Sticky inflation could delay cuts and contradict the easing case.",
                    "attributes": {"factor_name": "Sticky inflation risk"},
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "CONTRADICTS",
                            "fact": "Sticky inflation contradicts a near-term June rate cut.",
                            "source_node_uuid": "risk-1",
                            "provenance": {
                                "episode_ids": ["ep-2"],
                                "chunk_ids": ["chunk-0002"],
                                "source_unit_ids": [unit_contra_id],
                                "source_ids": ["src-1"],
                                "stable_source_ids": ["src-alpha"],
                                "citation_count": 1,
                                "citations": [
                                    {
                                        "unit_id": unit_contra_id,
                                        "source_id": "src-1",
                                        "stable_source_id": "src-alpha",
                                        "original_filename": "memo.md",
                                        "relative_path": "files/memo.md",
                                        "unit_type": "paragraph",
                                        "source_order": 1,
                                        "unit_order": 2,
                                        "char_start": 88,
                                        "char_end": 176,
                                        "combined_text_start": 88,
                                        "combined_text_end": 176,
                                        "text_excerpt": "Sticky inflation could delay cuts and contradict the stronger easing case.",
                                        "reason": "episode_linked",
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [],
                    "object_type": "UncertaintyFactor",
                    "layer": "analytical",
                    "provenance": {
                        "match_reason": "edge_episode",
                        "episode_ids": ["ep-2"],
                        "chunk_ids": ["chunk-0002"],
                        "source_unit_ids": [unit_contra_id],
                        "source_ids": ["src-1"],
                        "stable_source_ids": ["src-alpha"],
                        "citation_count": 1,
                        "citations": [
                            {
                                "unit_id": unit_contra_id,
                                "source_id": "src-1",
                                "stable_source_id": "src-alpha",
                                "original_filename": "memo.md",
                                "relative_path": "files/memo.md",
                                "unit_type": "paragraph",
                                "source_order": 1,
                                "unit_order": 2,
                                "char_start": 88,
                                "char_end": 176,
                                "combined_text_start": 88,
                                "combined_text_end": 176,
                                "text_excerpt": "Sticky inflation could delay cuts and contradict the stronger easing case.",
                                "reason": "edge_episode",
                            }
                        ],
                    },
                },
            ],
            "graph_node_count": 2,
            "graph_edge_count": 2,
            "object_count": 2,
            "citation_coverage": {
                "source_unit_backed_node_count": 2,
                "source_unit_backed_edge_count": 2,
                "edge_episode_link_count": 2,
            },
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "project_id": project_id,
            "graph_id": "graph-test",
            "chunk_count": 2,
            "chunking_strategy": "semantic_source_units",
            "graph_counts": {
                "node_count": 2,
                "edge_count": 2,
                "actor_count": 0,
                "analytical_object_count": 2,
                "entity_types": ["Claim", "UncertaintyFactor"],
                "analytical_types": ["Claim", "UncertaintyFactor"],
            },
            "citation_coverage": {
                "source_unit_backed_node_count": 2,
                "source_unit_backed_edge_count": 2,
                "edge_episode_link_count": 2,
            },
        },
    )
    return unit_support_id


def test_hybrid_evidence_retriever_ranks_graph_backed_support_and_generates_forecast_hints(
    monkeypatch,
    tmp_path,
):
    projects_dir = _configure_projects_dir(monkeypatch, tmp_path)
    support_unit_id = _seed_project_artifacts(projects_dir, project_id="proj-hybrid")

    module = importlib.import_module("app.services.hybrid_evidence_retriever")
    index_module = importlib.import_module("app.services.local_evidence_index")

    retriever = module.HybridEvidenceRetriever(
        embedding_client=_FakeEmbeddingClient(),
        evidence_index=index_module.LocalEvidenceIndex(
            index_path=str(tmp_path / "local_evidence.sqlite3")
        ),
    )

    result = retriever.retrieve(
        project_id="proj-hybrid",
        query="Will weaker payroll data make a June rate cut more likely?",
        question_type="binary",
        issue_timestamp=QUESTION_ISSUED_AT,
        limit=4,
    )

    assert result.total_count == 4
    assert result.hits[0]["record_id"] == "claim-1"
    assert result.hits[0]["conflict_status"] == "supports"
    assert result.hits[0]["forecast_hints"][0]["estimate"] > 0.5
    assert result.hits[0]["provenance"]["source_unit_ids"] == [support_unit_id]
    assert result.hits[0]["citations"][0]["unit_id"] == support_unit_id
    assert result.hits[0]["score_components"]["graph"] > 0.0
    assert result.index_stats["record_count"] >= 4


def test_hybrid_evidence_retriever_propagates_explicit_contradictions_and_citations(
    monkeypatch,
    tmp_path,
):
    projects_dir = _configure_projects_dir(monkeypatch, tmp_path)
    _seed_project_artifacts(projects_dir, project_id="proj-hybrid")

    module = importlib.import_module("app.services.hybrid_evidence_retriever")
    index_module = importlib.import_module("app.services.local_evidence_index")

    retriever = module.HybridEvidenceRetriever(
        embedding_client=_FakeEmbeddingClient(),
        evidence_index=index_module.LocalEvidenceIndex(
            index_path=str(tmp_path / "local_evidence.sqlite3")
        ),
    )

    result = retriever.retrieve(
        project_id="proj-hybrid",
        query="Could sticky inflation delay a June rate cut?",
        question_type="binary",
        issue_timestamp=QUESTION_ISSUED_AT,
        limit=3,
    )

    contradictory = next(hit for hit in result.hits if hit["record_id"] == "risk-1")
    assert contradictory["conflict_status"] == "contradicts"
    assert contradictory["conflict_markers"][0]["code"] == "contradicts"
    assert contradictory["forecast_hints"][0]["estimate"] < 0.5
    assert contradictory["citations"][0]["locator"].endswith("#chars=88-176")
