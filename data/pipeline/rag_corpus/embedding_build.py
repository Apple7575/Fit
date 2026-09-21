"""Persist only missing or changed evidence embeddings, committing one batch at a time."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np



class Encoder(Protocol):
    def embed_passages(self, texts: list[str]) -> np.ndarray: ...


# 저장 정밀도. 벡터는 코퍼스 용량의 대부분을 차지하므로 절반으로 줄일 수 있으면 크다.
# 정규화된 값이라 범위가 좁아(-0.2~0.2) float16 으로도 검색 결과가 바뀌지 않는다 —
# 실측에서 코사인 유사도 오차 최대 8.8e-05, 상위 8건 일치율 100%.
DTYPES = {"float32": "<f4", "float16": "<f2"}
DEFAULT_DTYPE = "float32"


def encode_vector(vector: np.ndarray, dtype: str = DEFAULT_DTYPE) -> bytes:
    values = np.asarray(vector, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("embedding vector must be a finite, nonempty vector")
    scale = np.max(np.abs(values))
    if scale == 0:
        raise ValueError("embedding vector must not be zero")
    normalized = (values / scale) / np.sqrt(np.dot(values / scale, values / scale))
    try:
        code = DTYPES[dtype]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 벡터 정밀도입니다: {dtype}") from error
    return normalized.astype(code).tobytes()


def document_embedding_text(row: Mapping[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    fields = (
        ("기업", row.get("company_name")),
        ("자료 유형", row.get("source_type")),
        ("제목", row.get("title")),
        ("문서 구간", metadata.get("section_title")),
        ("지표", metadata.get("metric_name")),
        ("기준 기간", row.get("reference_period")),
        ("발행일", row["published_at"].isoformat()),
    )
    lines = [f"{label}: {value}" for label, value in fields if value]
    lines.append(f"본문: {row['content']}")
    return "\n".join(lines)


DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_VERSION = "document-v1"
KNOWN_DIMENSIONS = {
    DEFAULT_MODEL: 1024,
    "intfloat/multilingual-e5-large": 1024,
}
ALLOWED_SOURCE_TYPES = frozenset({
    "COMPANY_PROFILE", "COMPANY_METRIC", "COMPANY_TEXT", "SEGMENT_METRIC",
    "COMPANY_ACTIVITY", "DART_BUSINESS_REPORT", "NEWS",
})

_COLUMNS = (
    "evidence_id", "company_name", "corp_code", "source_type", "title",
    "published_at", "content", "source_url", "reference_period", "quality",
    "metadata", "content_hash",
)
_JOIN = """
FROM rag_evidence e
JOIN company c ON c.corp_code = e.corp_code
LEFT JOIN rag_evidence_embedding re
  ON re.evidence_id = e.evidence_id
 AND re.embedding_model = %s AND re.embedding_version = %s
"""
_PENDING = "(re.evidence_id IS NULL OR re.content_hash <> e.content_hash)"
_UPSERT = """INSERT INTO rag_evidence_embedding (
    evidence_id, embedding_model, embedding_version, content_hash, dimension, vector_bytes
) VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (evidence_id, embedding_model, embedding_version)
DO UPDATE SET content_hash = EXCLUDED.content_hash,
              dimension = EXCLUDED.dimension,
              vector_bytes = EXCLUDED.vector_bytes,
              embedded_at = now()
"""


@dataclass
class EmbeddingBuildSummary:
    selected: int = 0
    embedded: int = 0
    unchanged: int = 0
    failed: int = 0
    dimension: int | None = None


class EmbeddingBuildError(RuntimeError):
    def __init__(self, summary: EmbeddingBuildSummary):
        super().__init__("Embedding batch failed; completed batches remain committed")
        self.summary = summary


class EmbeddingBuildRepository:
    def __init__(self, connection: Any):
        self.connection = connection

    def counts(
        self, model: str, version: str, corp_codes: list[str] | None,
        source_types: list[str] | None = None,
    ) -> tuple[int, int]:
        params: list[object] = [model, version]
        sql = f"SELECT COUNT(*) FILTER (WHERE {_PENDING}), COUNT(*) FILTER (WHERE NOT {_PENDING}) {_JOIN}"
        if corp_codes is not None:
            sql += " WHERE e.corp_code = ANY(%s)"
            params.append(corp_codes)
        if source_types is not None:
            sql += " AND" if corp_codes is not None else " WHERE"
            sql += " e.source_type = ANY(%s)"
            params.append(source_types)
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            selected, unchanged = cur.fetchone()
        return int(selected), int(unchanged)

    def pending(
        self, model: str, version: str, corp_codes: list[str] | None,
        source_types: list[str] | None = None,
        *, batch_size: int = 64, after: str | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        columns = ", ".join("c.corp_name AS company_name" if name == "company_name" else f"e.{name}" for name in _COLUMNS)
        sql = f"SELECT {columns} {_JOIN} WHERE {_PENDING}"
        params: list[object] = [model, version]
        if corp_codes is not None:
            sql += " AND e.corp_code = ANY(%s)"
            params.append(corp_codes)
        if source_types is not None:
            sql += " AND e.source_type = ANY(%s)"
            params.append(source_types)
        if after is not None:
            sql += " AND e.evidence_id > %s"
            params.append(after)
        sql += " ORDER BY e.evidence_id LIMIT %s"
        params.append(batch_size)
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) if isinstance(row, Mapping) else dict(zip(_COLUMNS, row, strict=True)) for row in cur.fetchall()]

    def upsert(self, rows: list[tuple[object, ...]]) -> None:
        with self.connection.cursor() as cur:
            for row in rows:
                cur.execute(_UPSERT, row)


def build_embeddings(
    conn_factory: Callable[[], Any], encoder: Encoder | None,
    model: str, version: str, corp_codes: list[str] | None,
    source_types: list[str] | None = None,
    batch_size: int = 64, dry_run: bool = False,
    dtype: str = DEFAULT_DTYPE,
) -> EmbeddingBuildSummary:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if not model.strip() or len(model) > 200 or not version.strip() or len(version) > 40:
        raise ValueError("model and version must be nonempty and fit the storage schema")
    if dtype not in DTYPES:
        raise ValueError(f"지원하지 않는 벡터 정밀도입니다: {dtype}")
    if source_types is not None and any(
        source_type not in ALLOWED_SOURCE_TYPES for source_type in source_types
    ):
        raise ValueError("source_types contains an unsupported value")
    with conn_factory() as conn:
        selected, unchanged = EmbeddingBuildRepository(conn).counts(
            model, version, corp_codes, source_types,
        )
    summary = EmbeddingBuildSummary(selected=selected, unchanged=unchanged,
                                    dimension=KNOWN_DIMENSIONS.get(model))
    if dry_run or selected == 0:
        return summary
    if encoder is None:
        raise ValueError("encoder is required for pending embeddings")

    after = None
    batch: list[dict[str, Any]] = []
    try:
        while True:
            batch = []
            with conn_factory() as conn:
                batch = EmbeddingBuildRepository(conn).pending(
                    model, version, corp_codes, source_types,
                    batch_size=batch_size, after=after,
                )
            if not batch:
                break
            # Model inference runs after the read transaction has closed.
            texts = [document_embedding_text(row) for row in batch]
            vectors = np.asarray(encoder.embed_passages(texts))
            if vectors.ndim != 2 or vectors.shape[0] != len(batch) or vectors.shape[1] == 0:
                raise ValueError("embedding shape does not match the batch")
            dimension = int(vectors.shape[1])
            if summary.dimension is not None and dimension != summary.dimension:
                raise ValueError("embedding dimension changed")
            summary.dimension = dimension
            stored = [(row["evidence_id"], model, version, row["content_hash"],
                       dimension, encode_vector(vector, dtype))
                      for row, vector in zip(batch, vectors, strict=True)]
            with conn_factory() as conn:
                EmbeddingBuildRepository(conn).upsert(stored)
            summary.embedded += len(batch)
            after = batch[-1]["evidence_id"]
    except Exception as error:
        summary.failed = len(batch)
        raise EmbeddingBuildError(summary) from error
    return summary
