"""Local vector-backed evidence index foundation for later forecasting phases."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence

from ..config import Config


@dataclass(frozen=True)
class EvidenceIndexRecord:
    """One persisted evidence vector record."""

    record_id: str
    namespace: str
    content: str
    vector: Sequence[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceSearchHit:
    """One similarity-ranked evidence result."""

    record_id: str
    namespace: str
    content: str
    metadata: dict[str, Any]
    vector: list[float]
    score: float


class LocalEvidenceIndex:
    """Persist and search evidence vectors in a local SQLite index."""

    SCHEMA_VERSION = "mirofish.local_evidence_index.v1"

    def __init__(self, *, index_path: str | None = None):
        self.index_path = index_path or Config.get_local_evidence_index_path()
        self._ensure_parent_dir()
        self._initialize()

    def upsert(self, record: EvidenceIndexRecord) -> None:
        """Upsert a single record."""
        self.upsert_many([record])

    def upsert_many(self, records: Sequence[EvidenceIndexRecord]) -> None:
        """Upsert a batch of vector records."""
        if not records:
            return

        timestamp = datetime.now().isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO evidence_records (
                    namespace,
                    record_id,
                    content,
                    vector_json,
                    metadata_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, record_id) DO UPDATE SET
                    content = excluded.content,
                    vector_json = excluded.vector_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        record.namespace,
                        record.record_id,
                        record.content,
                        json.dumps([float(value) for value in record.vector]),
                        json.dumps(record.metadata or {}, sort_keys=True),
                        timestamp,
                    )
                    for record in records
                ],
            )

    def search(
        self,
        *,
        namespace: str,
        query_vector: Sequence[float],
        limit: int = 5,
    ) -> list[EvidenceSearchHit]:
        """Search one namespace with cosine similarity over persisted vectors."""
        query = [float(value) for value in query_vector]
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT namespace, record_id, content, vector_json, metadata_json
                FROM evidence_records
                WHERE namespace = ?
                """,
                (namespace,),
            ).fetchall()

        hits: list[EvidenceSearchHit] = []
        for row in rows:
            vector = json.loads(row["vector_json"])
            score = self._cosine_similarity(query, vector)
            hits.append(
                EvidenceSearchHit(
                    record_id=row["record_id"],
                    namespace=row["namespace"],
                    content=row["content"],
                    metadata=json.loads(row["metadata_json"]),
                    vector=vector,
                    score=score,
                )
            )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def stats(self) -> dict[str, Any]:
        """Return lightweight index statistics for verification and handoff."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS record_count,
                    COUNT(DISTINCT namespace) AS namespace_count
                FROM evidence_records
                """
            ).fetchone()
        return {
            "schema_version": self.SCHEMA_VERSION,
            "index_path": self.index_path,
            "record_count": int(row["record_count"]),
            "namespace_count": int(row["namespace_count"]),
        }

    def _ensure_parent_dir(self) -> None:
        directory = os.path.dirname(self.index_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_records (
                    namespace TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, record_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.index_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
        left_vector = [float(value) for value in left]
        right_vector = [float(value) for value in right]
        if len(left_vector) != len(right_vector) or not left_vector:
            return 0.0

        left_norm = math.sqrt(sum(value * value for value in left_vector))
        right_norm = math.sqrt(sum(value * value for value in right_vector))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0

        dot = sum(left_value * right_value for left_value, right_value in zip(left_vector, right_vector))
        return dot / (left_norm * right_norm)
