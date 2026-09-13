from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import EvidenceRecord
from .source import CompanySourceRows
from .transform import activity_record, metric_record, profile_record, segment_records, text_records


@dataclass(frozen=True)
class BuildResult:
    records: list[EvidenceRecord]
    input_counts: dict[str, int]
    excluded_counts: dict[str, int]


def build_company_records(rows: CompanySourceRows) -> BuildResult:
    """정본 행을 RAG 레코드로 바꾸고 제외 사유를 함께 남긴다."""
    input_counts = {
        "profile": 1 if rows.profile is not None else 0,
        "metrics": len(rows.metrics),
        "texts": len(rows.texts),
        "segments": len(rows.segments),
        "activities": len(rows.activities),
    }
    excluded_counts: dict[str, int] = {}
    records: list[EvidenceRecord] = []

    if rows.profile is not None:
        records.append(profile_record(rows.profile))

    for row in rows.metrics:
        item = metric_record(row)
        if item is not None:
            records.append(item)
        elif _blank(row.get("metric_value")):
            _exclude(excluded_counts, "blank_content")
        else:
            _exclude(excluded_counts, "metric_rejected")

    for row in rows.texts:
        if _blank(row.get("value_text")):
            _exclude(excluded_counts, "blank_content")
        elif not _blank(row.get("generated_at")):
            _exclude(excluded_counts, "generated_text")
    records.extend(text_records(rows.texts))

    segment_candidates: list[Mapping[str, object]] = []
    for row in rows.segments:
        if _blank(row.get("metric_value")):
            _exclude(excluded_counts, "blank_content")
        elif str(row.get("verdict") or "").strip() in ("rejected", "not_found"):
            _exclude(excluded_counts, "metric_rejected")
        else:
            segment_candidates.append(row)
    records.extend(segment_records(segment_candidates))

    for row in rows.activities:
        if _blank(row.get("activity_type")):
            _exclude(excluded_counts, "blank_content")
        else:
            records.append(activity_record(row))

    return BuildResult(
        records=sorted(records, key=lambda item: (item.source_identity, item.evidence_id)),
        input_counts=input_counts,
        excluded_counts=dict(sorted(excluded_counts.items())),
    )


def replace_company(conn: Any, corp_code: str, records: Iterable[EvidenceRecord]) -> int:
    """호출자가 소유한 트랜잭션 안에서 한 기업의 RAG 레코드를 완전히 교체한다."""
    replacement = list(records)
    if any(item.corp_code != corp_code for item in replacement):
        raise ValueError("다른 기업 레코드는 함께 교체할 수 없습니다")

    columns = (
        "evidence_id", "corp_code", "source_type", "source_identity", "title", "content",
        "reference_period", "published_at", "source_url", "quality", "metadata", "content_hash",
        "source_updated_at",
    )
    with conn.cursor() as cur:
        cur.execute("DELETE FROM rag_evidence WHERE corp_code = %s", (corp_code,))
        for item in replacement:
            row = item.as_db_row()
            cur.execute("""
                INSERT INTO rag_evidence (
                    evidence_id, corp_code, source_type, source_identity, title, content,
                    reference_period, published_at, source_url, quality, metadata, content_hash,
                    source_updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, tuple(row[column] for column in columns))
    return len(replacement)


def _exclude(counts: dict[str, int], reason: str) -> None:
    counts[reason] = counts.get(reason, 0) + 1


def _blank(value: object) -> bool:
    return value is None or not str(value).strip()
