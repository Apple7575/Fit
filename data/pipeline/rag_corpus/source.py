from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CompanySourceRows:
    """RAG 재구축에 쓰는 한 기업의 정본 행 묶음이다."""

    profile: Mapping[str, object] | None
    metrics: list[Mapping[str, object]]
    texts: list[Mapping[str, object]]
    segments: list[Mapping[str, object]]
    activities: list[Mapping[str, object]]


def load_company_source_rows(conn: Any, corp_code: str) -> CompanySourceRows:
    """정본 테이블을 기업 하나로만 좁혀 읽는다."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.corp_code, c.corp_name, c.corp_cls, c.industry_code, c.ceo_nm,
                   c.established_date, c.listed_date, c.dart_modify_date,
                   c.homepage_url, c.updated_at AS source_updated_at
              FROM company c
             WHERE c.corp_code = %s
        """, (corp_code,))
        profile = _fetch_one(cur)
        if profile is None:
            raise ValueError(f"기업을 찾을 수 없습니다: {corp_code}")

        cur.execute("""
            SELECT cm.corp_code, c.corp_name, cm.fiscal_year, cm.metric_code,
                   m.name_ko AS metric_name, m.unit, cm.metric_value,
                   me.verdict, me.rcept_no, cm.updated_at AS source_updated_at
              FROM company_metric cm
              JOIN company c ON c.corp_code = cm.corp_code
              JOIN metric m ON m.metric_code = cm.metric_code
              LEFT JOIN metric_evidence me
                ON me.corp_code = cm.corp_code
               AND me.fiscal_year = cm.fiscal_year
               AND me.metric_code = cm.metric_code
             WHERE cm.corp_code = %s
             ORDER BY cm.fiscal_year, cm.metric_code
        """, (corp_code,))
        metrics = _fetch_all(cur)

        cur.execute("""
            SELECT ct.corp_code, c.corp_name, ct.fiscal_year, ct.attr_key, ct.seq,
                   ct.value_text, ct.generated_at, ct.updated_at AS source_updated_at
              FROM company_text ct
              JOIN company c ON c.corp_code = ct.corp_code
             WHERE ct.corp_code = %s
             ORDER BY ct.fiscal_year, ct.attr_key, ct.seq
        """, (corp_code,))
        texts = _fetch_all(cur)

        cur.execute("""
            SELECT sm.corp_code, c.corp_name, sm.fiscal_year, sm.segment_name,
                   sm.metric_code, m.name_ko AS metric_name, m.unit, sm.metric_value,
                   me.verdict, me.rcept_no, sm.updated_at AS source_updated_at
              FROM segment_metric sm
              JOIN company c ON c.corp_code = sm.corp_code
              JOIN metric m ON m.metric_code = sm.metric_code
              LEFT JOIN metric_evidence me
                ON me.corp_code = sm.corp_code
               AND me.fiscal_year = sm.fiscal_year
               AND me.metric_code = sm.metric_code
             WHERE sm.corp_code = %s
             ORDER BY sm.fiscal_year, sm.segment_name, sm.metric_code
        """, (corp_code,))
        segments = _fetch_all(cur)

        cur.execute("""
            SELECT ca.id, ca.corp_code, c.corp_name, ca.fiscal_year, ca.activity_type,
                   ca.field_name, ca.purpose, ca.amount, ca.counterparty, ca.rcept_no,
                   ca.updated_at AS source_updated_at
              FROM company_activity ca
              JOIN company c ON c.corp_code = ca.corp_code
             WHERE ca.corp_code = %s
             ORDER BY ca.fiscal_year, ca.activity_type, ca.id
        """, (corp_code,))
        activities = _fetch_all(cur)

    return CompanySourceRows(profile, metrics, texts, segments, activities)


def _fetch_one(cursor: Any) -> Mapping[str, object] | None:
    row = cursor.fetchone()
    return _mapping(cursor, row) if row is not None else None


def _fetch_all(cursor: Any) -> list[Mapping[str, object]]:
    return [_mapping(cursor, row) for row in cursor.fetchall()]


def _mapping(cursor: Any, row: object) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    names = [column.name for column in cursor.description]
    return dict(zip(names, row, strict=True))  # type: ignore[arg-type]
