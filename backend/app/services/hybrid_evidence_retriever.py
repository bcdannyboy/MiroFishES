"""Hybrid retrieval over source-unit embeddings plus graph-aware local artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from ..models.project import ProjectManager
from ..utils.embedding_client import LocalEmbeddingClient
from .local_evidence_index import EvidenceIndexRecord, LocalEvidenceIndex
from .forecast_hint_service import ForecastHintService


def _namespace(project_id: str, suffix: str) -> str:
    return f"project:{project_id}:{suffix}"


def build_retrieval_contract(
    *,
    project_id: str,
    graph_id: Optional[str] = None,
    source_units_payload: Optional[Dict[str, Any]] = None,
    graph_index_payload: Optional[Dict[str, Any]] = None,
    graph_summary_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source_unit_count = int((source_units_payload or {}).get("unit_count") or 0)
    actor_count = len((graph_index_payload or {}).get("entities") or [])
    analytical_object_count = int(
        (graph_index_payload or {}).get("analytical_object_count")
        or len((graph_index_payload or {}).get("analytical_objects") or [])
    )
    resolved_graph_id = (
        graph_id
        or (graph_index_payload or {}).get("graph_id")
        or (graph_summary_payload or {}).get("graph_id")
    )
    if source_unit_count and analytical_object_count:
        status = "ready"
    elif source_unit_count or analytical_object_count or actor_count:
        status = "partial"
    else:
        status = "unavailable"
    return {
        "status": status,
        "source_unit_count": source_unit_count,
        "actor_count": actor_count,
        "analytical_object_count": analytical_object_count,
        "graph_id": resolved_graph_id,
        "index_namespaces": {
            "source_units": _namespace(project_id, "source_units"),
            "graph_objects": _namespace(project_id, "graph_objects"),
        },
        "citation_coverage": dict(
            (graph_index_payload or {}).get("citation_coverage")
            or (graph_summary_payload or {}).get("citation_coverage")
            or {}
        ),
    }


@dataclass
class HybridRetrievalResult:
    project_id: str
    query: str
    hits: List[Dict[str, Any]]
    missing_evidence_markers: List[Dict[str, Any]]
    index_stats: Dict[str, Any]

    @property
    def total_count(self) -> int:
        return len(self.hits)


class HybridEvidenceRetriever:
    """Search persisted source units and graph objects with hybrid local ranking."""

    def __init__(
        self,
        *,
        embedding_client: Optional[LocalEmbeddingClient] = None,
        evidence_index: Optional[LocalEvidenceIndex] = None,
        hint_service: Optional[ForecastHintService] = None,
    ) -> None:
        self.embedding_client = embedding_client or LocalEmbeddingClient()
        self.evidence_index = evidence_index or LocalEvidenceIndex()
        self.hint_service = hint_service or ForecastHintService()

    def retrieve(
        self,
        *,
        project_id: str,
        query: str,
        question_type: str = "binary",
        issue_timestamp: Optional[str] = None,
        limit: int = 6,
    ) -> HybridRetrievalResult:
        source_units_payload = ProjectManager.get_source_units(project_id) or {}
        graph_index_payload = ProjectManager.get_graph_entity_index(project_id) or {}
        graph_summary_payload = ProjectManager.get_graph_build_summary(project_id) or {}
        contract = build_retrieval_contract(
            project_id=project_id,
            source_units_payload=source_units_payload,
            graph_index_payload=graph_index_payload,
            graph_summary_payload=graph_summary_payload,
        )

        missing_markers: List[Dict[str, Any]] = []
        source_units = list(source_units_payload.get("units") or [])
        graph_objects = list(graph_index_payload.get("analytical_objects") or [])
        if not source_units:
            missing_markers.append(
                {
                    "code": "missing_source_units",
                    "kind": "missing_source_units",
                    "reason": "No source_units.json artifact is available for hybrid retrieval.",
                }
            )
        if not graph_objects:
            missing_markers.append(
                {
                    "code": "missing_graph_entity_index",
                    "kind": "missing_graph_entity_index",
                    "reason": "No graph_entity_index.json artifact is available for hybrid retrieval.",
                }
            )

        source_records = self._build_source_unit_records(project_id, source_units)
        graph_records = self._build_graph_object_records(project_id, graph_objects)
        self.evidence_index.upsert_many([*source_records, *graph_records])
        if not source_records and not graph_records:
            missing_markers.append(
                {
                    "code": "no_ranked_local_evidence",
                    "kind": "no_ranked_local_evidence",
                    "reason": "Hybrid retrieval could not find indexed source units or graph objects.",
                }
            )
            return HybridRetrievalResult(
                project_id=project_id,
                query=query,
                hits=[],
                missing_evidence_markers=missing_markers,
                index_stats=self.evidence_index.stats(),
            )

        query_vector = self.embedding_client.embed_text(query)
        source_hits = self.evidence_index.search(
            namespace=contract["index_namespaces"]["source_units"],
            query_vector=query_vector,
            limit=max(limit * 2, 4),
        )
        graph_hits = self.evidence_index.search(
            namespace=contract["index_namespaces"]["graph_objects"],
            query_vector=query_vector,
            limit=max(limit * 2, 4),
        )

        source_unit_to_graph = self._source_unit_to_graph_objects(graph_objects)
        candidates: List[Dict[str, Any]] = []
        candidates.extend(
            self._materialize_source_hit(
                hit=hit,
                query=query,
                question_type=question_type,
                issue_timestamp=issue_timestamp,
                linked_graph_objects=source_unit_to_graph.get(
                    str((hit.metadata or {}).get("unit_id") or ""),
                    [],
                ),
            )
            for hit in source_hits
        )
        candidates.extend(
            self._materialize_graph_hit(
                hit=hit,
                query=query,
                question_type=question_type,
                issue_timestamp=issue_timestamp,
            )
            for hit in graph_hits
        )
        candidates = [candidate for candidate in candidates if candidate]
        candidates.sort(
            key=lambda item: (
                -float(item.get("score", 0.0)),
                0 if item.get("record_type") == "graph_object" else 1,
                str(item.get("record_id") or ""),
            )
        )
        return HybridRetrievalResult(
            project_id=project_id,
            query=query,
            hits=candidates[:limit],
            missing_evidence_markers=missing_markers,
            index_stats=self.evidence_index.stats(),
        )

    def _build_source_unit_records(
        self,
        project_id: str,
        source_units: List[Dict[str, Any]],
    ) -> List[EvidenceIndexRecord]:
        records: List[EvidenceIndexRecord] = []
        if not source_units:
            return records
        vectors = self.embedding_client.embed_texts(
            [str(unit.get("text") or "") for unit in source_units]
        )
        for unit, vector in zip(source_units, vectors):
            unit_id = str(unit.get("unit_id") or "").strip()
            if not unit_id:
                continue
            records.append(
                EvidenceIndexRecord(
                    record_id=unit_id,
                    namespace=_namespace(project_id, "source_units"),
                    content=str(unit.get("text") or ""),
                    vector=vector,
                    metadata={
                        "record_type": "source_unit",
                        "unit_id": unit_id,
                        "source_id": unit.get("source_id"),
                        "stable_source_id": unit.get("stable_source_id"),
                        "original_filename": unit.get("original_filename"),
                        "relative_path": unit.get("relative_path"),
                        "source_order": unit.get("source_order"),
                        "unit_order": unit.get("unit_order"),
                        "unit_type": unit.get("unit_type"),
                        "char_start": unit.get("char_start"),
                        "char_end": unit.get("char_end"),
                        "combined_text_start": unit.get("combined_text_start"),
                        "combined_text_end": unit.get("combined_text_end"),
                    },
                )
            )
        return records

    def _build_graph_object_records(
        self,
        project_id: str,
        graph_objects: List[Dict[str, Any]],
    ) -> List[EvidenceIndexRecord]:
        records: List[EvidenceIndexRecord] = []
        if not graph_objects:
            return records
        texts = [self._graph_object_content(item) for item in graph_objects]
        vectors = self.embedding_client.embed_texts(texts)
        for graph_object, vector, content in zip(graph_objects, vectors, texts):
            record_id = str(graph_object.get("uuid") or "").strip()
            if not record_id:
                continue
            provenance = dict(graph_object.get("provenance") or {})
            records.append(
                EvidenceIndexRecord(
                    record_id=record_id,
                    namespace=_namespace(project_id, "graph_objects"),
                    content=content,
                    vector=vector,
                    metadata={
                        "record_type": "graph_object",
                        "uuid": record_id,
                        "name": graph_object.get("name"),
                        "labels": list(graph_object.get("labels") or []),
                        "summary": graph_object.get("summary"),
                        "object_type": graph_object.get("object_type")
                        or next(iter(graph_object.get("labels") or []), None),
                        "layer": graph_object.get("layer"),
                        "related_edges": list(graph_object.get("related_edges") or []),
                        "related_nodes": list(graph_object.get("related_nodes") or []),
                        "related_edge_count": len(graph_object.get("related_edges") or []),
                        "related_node_count": len(graph_object.get("related_nodes") or []),
                        "provenance": provenance,
                        "citations": list(provenance.get("citations") or []),
                    },
                )
            )
        return records

    def _materialize_source_hit(
        self,
        *,
        hit: Any,
        query: str,
        question_type: str,
        issue_timestamp: Optional[str],
        linked_graph_objects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = dict(hit.metadata or {})
        title = f"{metadata.get('original_filename') or 'Source unit'}"
        summary = str(hit.content or "")[:280]
        lexical_score = self._lexical_score(query, [hit.content, title, summary])
        graph_score = min(1.0, 0.1 * len(linked_graph_objects))
        total_score = self._blend_scores(hit.score, lexical_score, graph_score)
        citation = self._build_source_unit_citation(metadata)
        provenance = {
            "source_unit_ids": [metadata.get("unit_id")] if metadata.get("unit_id") else [],
            "source_ids": [metadata.get("source_id")] if metadata.get("source_id") else [],
            "stable_source_ids": [metadata.get("stable_source_id")] if metadata.get("stable_source_id") else [],
            "linked_graph_records": [
                {
                    "record_id": item.get("uuid"),
                    "title": item.get("name"),
                    "object_type": item.get("object_type"),
                }
                for item in linked_graph_objects[:4]
            ],
        }
        annotation = self.hint_service.annotate_hit(
            query=query,
            question_type=question_type,
            title=title,
            summary=summary,
            content=str(hit.content or ""),
            object_type=metadata.get("unit_type"),
            related_edge_names=[],
            citations=[citation],
            provenance=provenance,
            score=total_score,
        )
        return {
            "record_id": hit.record_id,
            "record_type": "source_unit",
            "title": title,
            "summary": summary,
            "content": str(hit.content or ""),
            "object_type": metadata.get("unit_type"),
            "citation_id": citation["citation_id"],
            "locator": citation["locator"],
            "citations": [citation],
            "provenance": provenance,
            "freshness": {
                "status": "unknown",
                "score": 0.45,
                "reason": "Source units preserve local provenance but not live-world recency.",
            },
            "relevance": {
                "status": self._score_status(total_score),
                "score": round(total_score, 4),
                "reason": "Hybrid ranking combines semantic match, lexical overlap, and graph linkage.",
            },
            "quality": {
                "status": "usable",
                "score": round(min(0.95, 0.35 + (0.4 * hit.score) + (0.25 * graph_score)), 4),
                "reason": "Direct source-unit evidence with preserved file and span provenance.",
            },
            "score": round(total_score, 6),
            "score_components": {
                "semantic": round(float(hit.score), 6),
                "lexical": round(lexical_score, 6),
                "graph": round(graph_score, 6),
            },
            **annotation,
        }

    def _materialize_graph_hit(
        self,
        *,
        hit: Any,
        query: str,
        question_type: str,
        issue_timestamp: Optional[str],
    ) -> Dict[str, Any]:
        metadata = dict(hit.metadata or {})
        provenance = dict(metadata.get("provenance") or {})
        citations = [
            self._build_graph_citation(dict(item))
            for item in metadata.get("citations") or provenance.get("citations") or []
        ]
        title = str(metadata.get("name") or "Graph object")
        summary = str(metadata.get("summary") or hit.content or "")[:280]
        related_edge_names = [
            str((edge or {}).get("edge_name") or "")
            for edge in metadata.get("related_edges") or []
        ]
        lexical_score = self._lexical_score(query, [hit.content, title, summary])
        graph_score = min(
            1.0,
            0.2
            + (0.1 * len(citations))
            + (0.05 * int(metadata.get("related_edge_count") or 0)),
        )
        total_score = self._blend_scores(hit.score, lexical_score, graph_score)
        annotation = self.hint_service.annotate_hit(
            query=query,
            question_type=question_type,
            title=title,
            summary=summary,
            content=str(hit.content or ""),
            object_type=metadata.get("object_type"),
            related_edge_names=related_edge_names,
            citations=citations,
            provenance=provenance,
            score=total_score,
        )
        return {
            "record_id": hit.record_id,
            "record_type": "graph_object",
            "title": title,
            "summary": summary,
            "content": str(hit.content or ""),
            "object_type": metadata.get("object_type"),
            "citation_id": self._stable_citation_id("GO", hit.record_id),
            "locator": citations[0]["locator"] if citations else f"graph:{metadata.get('uuid') or hit.record_id}",
            "citations": citations,
            "provenance": provenance,
            "freshness": {
                "status": "unknown",
                "score": 0.45,
                "reason": "Graph-derived analytical objects keep citation lineage but not live-world timestamps.",
            },
            "relevance": {
                "status": self._score_status(total_score),
                "score": round(total_score, 4),
                "reason": "Hybrid ranking combines semantic match, lexical overlap, and graph neighborhood strength.",
            },
            "quality": {
                "status": "strong" if total_score >= 0.75 else "usable",
                "score": round(min(0.97, 0.4 + (0.35 * hit.score) + (0.25 * graph_score)), 4),
                "reason": "Graph object retrieval preserved connected citations and neighborhood context.",
            },
            "score": round(total_score, 6),
            "score_components": {
                "semantic": round(float(hit.score), 6),
                "lexical": round(lexical_score, 6),
                "graph": round(graph_score, 6),
            },
            **annotation,
        }

    def _source_unit_to_graph_objects(
        self,
        graph_objects: Iterable[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        mapping: Dict[str, List[Dict[str, Any]]] = {}
        for graph_object in graph_objects:
            provenance = dict(graph_object.get("provenance") or {})
            for unit_id in provenance.get("source_unit_ids") or []:
                if not unit_id:
                    continue
                mapping.setdefault(str(unit_id), []).append(graph_object)
        return mapping

    @staticmethod
    def _graph_object_content(graph_object: Dict[str, Any]) -> str:
        related_facts = [
            str((edge or {}).get("fact") or "")
            for edge in graph_object.get("related_edges") or []
            if str((edge or {}).get("fact") or "").strip()
        ]
        related_nodes = [
            str((node or {}).get("name") or "")
            for node in graph_object.get("related_nodes") or []
            if str((node or {}).get("name") or "").strip()
        ]
        return " ".join(
            part
            for part in [
                str(graph_object.get("name") or ""),
                str(graph_object.get("summary") or ""),
                " ".join(related_facts),
                " ".join(related_nodes),
            ]
            if part
        ).strip()

    @staticmethod
    def _score_status(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.5:
            return "medium"
        return "low"

    @staticmethod
    def _blend_scores(semantic_score: float, lexical_score: float, graph_score: float) -> float:
        return max(
            0.0,
            min(
                1.0,
                (0.6 * float(semantic_score))
                + (0.25 * lexical_score)
                + (0.15 * graph_score),
            ),
        )

    @staticmethod
    def _lexical_score(query: str, texts: Iterable[str]) -> float:
        query_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", query.lower())
            if len(token) > 2
        }
        if not query_tokens:
            return 0.0
        combined = " ".join(str(text or "") for text in texts).lower()
        overlap = sum(1 for token in query_tokens if token in combined)
        exact_bonus = 1 if query.lower().strip() and query.lower().strip() in combined else 0
        return min(1.0, (overlap / max(len(query_tokens), 1)) + (0.2 * exact_bonus))

    def _build_source_unit_citation(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        locator = self._locator_from_path_and_chars(
            metadata.get("relative_path"),
            metadata.get("char_start"),
            metadata.get("char_end"),
        )
        return {
            "citation_id": self._stable_citation_id("SU", metadata.get("unit_id")),
            "unit_id": metadata.get("unit_id"),
            "source_id": metadata.get("source_id"),
            "stable_source_id": metadata.get("stable_source_id"),
            "original_filename": metadata.get("original_filename"),
            "relative_path": metadata.get("relative_path"),
            "unit_type": metadata.get("unit_type"),
            "source_order": metadata.get("source_order"),
            "unit_order": metadata.get("unit_order"),
            "char_start": metadata.get("char_start"),
            "char_end": metadata.get("char_end"),
            "combined_text_start": metadata.get("combined_text_start"),
            "combined_text_end": metadata.get("combined_text_end"),
            "locator": locator,
        }

    def _build_graph_citation(self, citation: Dict[str, Any]) -> Dict[str, Any]:
        citation.setdefault("citation_id", self._stable_citation_id("SU", citation.get("unit_id")))
        citation["locator"] = self._locator_from_path_and_chars(
            citation.get("relative_path"),
            citation.get("char_start"),
            citation.get("char_end"),
        )
        return citation

    @staticmethod
    def _locator_from_path_and_chars(
        relative_path: Any,
        char_start: Any,
        char_end: Any,
    ) -> Optional[str]:
        if not relative_path:
            return None
        if isinstance(char_start, int) and isinstance(char_end, int):
            return f"{relative_path}#chars={char_start}-{char_end}"
        return str(relative_path)

    @staticmethod
    def _stable_citation_id(prefix: str, identifier: Any) -> str:
        token = re.sub(r"[^A-Za-z0-9]+", "", str(identifier or ""))[-8:] or "1"
        return f"[{prefix}{token}]"
