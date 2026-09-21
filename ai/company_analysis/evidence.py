"""사업보고서 원문 청크(rag_evidence, DART_BUSINESS_REPORT) 읽기.

리포트 서술은 벡터 검색 없이 **절 제목으로 고른다**. 사업보고서 한 편에서 서술 텍스트는
60여 개뿐이고 사업 관련 서술은 "II. 사업의 내용" 7개 절과 MD&A 에 몰려 있어, 섹션마다
정해진 절을 순서대로 넣는 것이 검색보다 정확하고 재현 가능하다. 벡터 검색은 대화 단계용이다.

기준일 이전 최신 사업보고서(rcept_no 최대) 한 편만 쓴다. 이전 보고서를 섞으면 연도가 다른
숫자가 한 문장에 들어간다(기존 실험 로그 우리금융지주 v2).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .contracts import Citation

SOURCE_TYPE = "DART_BUSINESS_REPORT"
DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


@dataclass(frozen=True)
class EvidenceChunk:
    evidence_id: str
    corp_code: str
    rcept_no: str
    report_name: str
    published_at: datetime
    section_index: int
    section_title: str
    content_type: str  # TEXT | TABLE
    order: int  # 절 안 순서(chunk_index 또는 table_index)
    content: str
    unit: str | None = None
    # 표 위 【 법인명 】 제목에서 뽑은 소속 법인(rag_evidence_entity_scope). 자회사 표를 본사 실적으로 읽지 않게 한다.
    entity_scope: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def is_table(self) -> bool:
        return self.content_type == "TABLE"

    def citation(self, excerpt: str | None = None) -> Citation:
        return Citation(
            source_type=SOURCE_TYPE,
            source_id=self.evidence_id,
            rcept_no=self.rcept_no,
            excerpt=(excerpt or self.content)[:1_000],
        )


@dataclass(frozen=True)
class BusinessReport:
    corp_code: str
    rcept_no: str
    report_name: str
    published_at: datetime
    chunks: tuple[EvidenceChunk, ...]

    def by_id(self) -> dict[str, EvidenceChunk]:
        return {chunk.evidence_id: chunk for chunk in self.chunks}

    def select(
        self,
        title_patterns: Iterable[str],
        *,
        content_types: tuple[str, ...] = ("TEXT", "TABLE"),
        max_chars: int,
    ) -> tuple[EvidenceChunk, ...]:
        """절 제목이 패턴에 맞는 청크를 문서 순서대로, 글자 예산 안에서 고른다.

        패턴 목록 순서가 우선순위다 — 앞 패턴의 절을 먼저 채우고 남은 예산으로 뒤 절을 넣는다.
        같은 절 안에서는 TEXT 를 표보다 먼저 넣는다. 서술이 핵심이고 표는 보조이기 때문이다.
        """
        picked: list[EvidenceChunk] = []
        seen: set[str] = set()
        budget = max_chars
        for pattern in title_patterns:
            regex = re.compile(pattern)
            matched = [
                chunk
                for chunk in self.chunks
                if chunk.content_type in content_types
                and regex.search(chunk.section_title)
                and chunk.evidence_id not in seen
            ]
            matched.sort(key=lambda c: (c.section_index, c.is_table, c.order))
            for chunk in matched:
                if len(chunk.content) > budget:
                    continue
                picked.append(chunk)
                seen.add(chunk.evidence_id)
                budget -= len(chunk.content)
            if budget <= 0:
                break
        picked.sort(key=lambda c: (c.section_index, c.is_table, c.order))
        return tuple(picked)

    def source_card(self) -> dict[str, Any]:
        return {
            "rcept_no": self.rcept_no,
            "title": self.report_name or f"사업보고서 ({self.rcept_no[:4]})",
            "published_at": self.published_at,
            "url": DART_VIEWER_URL.format(rcept_no=self.rcept_no),
        }


class BusinessReportRepository(Protocol):
    def latest(self, corp_code: str) -> BusinessReport | None: ...


# --- 행 → 객체 ---------------------------------------------------------------


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_TRAILING_HEADING = re.compile(r"\s*\|?\s*【\s*([^【】]+?)\s*】\s*$")


def _repair_scope(content: str, scope: str | None) -> tuple[str, str | None]:
    """캡션 줄 끝의 【 X 】 는 다음 표의 제목이 이 표 캡션에 섞인 것이다(우리금융지주 실측: 동양생명보험
    총자산 캡션 끝에 【 우리카드 】). 소속이 그 X 와 같으면 잘못 붙은 것이므로 소속을 지우고 제목도 떼어 낸다."""
    lines = content.splitlines()
    if not lines or not lines[0].startswith("표 캡션:"):
        return content, scope
    match = _TRAILING_HEADING.search(lines[0])
    if not match:
        return content, scope
    heading = match.group(1).strip()
    lines[0] = lines[0][: match.start()].rstrip()
    repaired = "\n".join(lines)
    if scope and heading.replace(" ", "") == scope.replace(" ", ""):
        return repaired, None
    return repaired, scope


def chunk_from_row(row: Mapping[str, Any]) -> EvidenceChunk:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    content_type = str(metadata.get("content_type") or "TEXT").upper()
    order_key = "table_index" if content_type == "TABLE" else "chunk_index"
    unit = metadata.get("unit")
    scope = row.get("scope_name")
    scope = str(scope).strip() if isinstance(scope, str) and scope.strip() else None
    content, scope = _repair_scope(str(row["content"]), scope)
    return EvidenceChunk(
        evidence_id=str(row["evidence_id"]),
        corp_code=str(row["corp_code"]),
        rcept_no=str(metadata.get("rcept_no") or row.get("rcept_no") or ""),
        report_name=str(metadata.get("report_name") or row.get("title") or ""),
        published_at=row["published_at"],
        section_index=_int(metadata.get("section_index"), 10**6),
        section_title=str(metadata.get("section_title") or "").strip(),
        content_type=content_type,
        order=_int(metadata.get(order_key)),
        content=content,
        unit=str(unit).strip() if isinstance(unit, str) and unit.strip() else None,
        entity_scope=scope,
        metadata=dict(metadata),
    )


def report_from_rows(rows: Sequence[Mapping[str, Any]]) -> BusinessReport | None:
    chunks = [chunk_from_row(row) for row in rows]
    if not chunks:
        return None
    latest_rcept = max(chunk.rcept_no for chunk in chunks)
    latest = tuple(sorted((c for c in chunks if c.rcept_no == latest_rcept), key=lambda c: (c.section_index, c.is_table, c.order)))
    head = latest[0]
    return BusinessReport(
        corp_code=head.corp_code,
        rcept_no=latest_rcept,
        report_name=head.report_name,
        published_at=max(c.published_at for c in latest),
        chunks=latest,
    )


# --- PostgreSQL --------------------------------------------------------------

LATEST_RCEPT_SQL = """
SELECT max(metadata->>'rcept_no') AS rcept_no
  FROM rag_evidence
 WHERE corp_code = %(corp_code)s AND source_type = %(source_type)s
   AND published_at <= %(as_of)s
"""

CHUNKS_SQL = """
SELECT evidence_id, corp_code, title, published_at, content, metadata
  FROM rag_evidence
 WHERE corp_code = %(corp_code)s AND source_type = %(source_type)s
   AND metadata->>'rcept_no' = %(rcept_no)s
"""

# 소속 법인 보조 테이블(V32)이 있으면 함께 읽는다. 없는 DB 에서는 CHUNKS_SQL 로 물러난다.
CHUNKS_WITH_SCOPE_SQL = """
SELECT e.evidence_id, e.corp_code, e.title, e.published_at, e.content, e.metadata, s.scope_name
  FROM rag_evidence e
  LEFT JOIN rag_evidence_entity_scope s ON s.evidence_id = e.evidence_id
 WHERE e.corp_code = %(corp_code)s AND e.source_type = %(source_type)s
   AND e.metadata->>'rcept_no' = %(rcept_no)s
"""


VECTORS_SQL = """
SELECT e.evidence_id, re.vector_bytes, re.dimension
  FROM rag_evidence e
  JOIN rag_evidence_embedding re
    ON re.evidence_id = e.evidence_id AND re.content_hash = e.content_hash
 WHERE e.corp_code = %(corp_code)s AND e.source_type = %(source_type)s
   AND e.metadata->>'rcept_no' = %(rcept_no)s
   AND re.embedding_model = %(model)s AND re.embedding_version = %(version)s
"""

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
# 적재 쪽 기본값과 같아야 한다(data/pipeline/rag_corpus/embedding_build.py 의 DEFAULT_VERSION).
# 어긋나면 검색이 한 건도 못 찾는다 — 벡터는 (model, version) 으로 고르기 때문이다.
DEFAULT_EMBEDDING_VERSION = "document-v1"


class PostgresBusinessReportRepository:
    def __init__(
        self,
        connect: Callable[[], Any],
        *,
        clock: Callable[[], datetime] | None = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_version: str = DEFAULT_EMBEDDING_VERSION,
    ) -> None:
        self._connect = connect
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._embedding_model = embedding_model
        self._embedding_version = embedding_version

    def load_vectors(self, report: BusinessReport) -> dict[str, Any]:
        """저장된 문서 임베딩(little-endian float32)을 evidence_id → 벡터로. 원문 해시가 바뀐 청크는 뺀다."""
        import numpy as np

        params = {
            "corp_code": report.corp_code,
            "source_type": SOURCE_TYPE,
            "rcept_no": report.rcept_no,
            "model": self._embedding_model,
            "version": self._embedding_version,
        }
        vectors: dict[str, Any] = {}
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(VECTORS_SQL, params)
            for evidence_id, payload, dimension in cursor.fetchall():
                raw = bytes(payload)
                if len(raw) != int(dimension) * 4:
                    continue
                vectors[str(evidence_id)] = np.frombuffer(raw, dtype="<f4").copy()
        return vectors

    def latest(self, corp_code: str) -> BusinessReport | None:
        params = {"corp_code": corp_code, "source_type": SOURCE_TYPE, "as_of": self._clock()}
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(LATEST_RCEPT_SQL, params)
            row = cursor.fetchone()
            rcept_no = row[0] if row else None
            if not rcept_no:
                return None
            chunk_params = {**params, "rcept_no": rcept_no}
            try:
                cursor.execute(CHUNKS_WITH_SCOPE_SQL, chunk_params)
            except Exception as error:  # noqa: BLE001 — 보조 테이블이 없는 DB(UndefinedTable)
                if type(error).__name__ != "UndefinedTable":
                    raise
                connection.rollback()
                cursor.execute(CHUNKS_SQL, chunk_params)
            names = [column.name for column in cursor.description]
            rows = [dict(zip(names, values)) for values in cursor.fetchall()]
        return report_from_rows(rows)
