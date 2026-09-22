"""PostgreSQL 에서 한 기업의 확정 데이터를 읽어 CompanyFacts 로 만든다.

행 → 객체 변환은 순수 함수로 분리해 DB 없이 테스트한다. 경쟁사는 Spring 산업 비교와
같은 기준 — 같은 KSIC 대분류(company.industry_code) 상장사를 최신 연도 매출 순으로 고른다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from .facts import (
    EMPLOYEE_COUNT,
    MAIN_PRODUCT,
    NET_INCOME,
    OPERATING_PROFIT,
    REVENUE,
    Activity,
    CompanyFacts,
    CompanyProfile,
    MetricPoint,
    PeerFacts,
    SegmentPoint,
    TextAttr,
)

DEFAULT_PEER_LIMIT = 3
PEER_METRICS = (REVENUE, OPERATING_PROFIT, NET_INCOME, EMPLOYEE_COUNT)


class CompanyFactsRepository(Protocol):
    def load(self, corp_code: str) -> CompanyFacts | None: ...


# --- SQL ---------------------------------------------------------------------

OTHER_COMPANY_SQL = """
SELECT corp_name
  FROM company
 WHERE length(corp_name) >= 3
   AND corp_code <> %s
   AND position(corp_name in %s) > 0
 LIMIT 5
"""

PROFILE_SQL = """
SELECT c.corp_code, c.corp_name, c.industry_code, i.industry_name, c.induty_code,
       c.ceo_nm, c.established_date::text AS established_date, c.address, c.homepage_url, c.stock_code
  FROM company c
  LEFT JOIN industry i ON i.industry_code = c.industry_code
 WHERE c.corp_code = %s
"""

METRICS_SQL = """
SELECT fiscal_year, metric_code, metric_value, fs_div
  FROM company_metric
 WHERE corp_code = %s AND metric_value IS NOT NULL
"""

SEGMENTS_SQL = """
SELECT fiscal_year, segment_name, metric_code, metric_value
  FROM segment_metric
 WHERE corp_code = %s AND metric_value IS NOT NULL
"""

ACTIVITIES_SQL = """
SELECT id, fiscal_year, activity_type, field_name, purpose, amount, rcept_no, counterparty
  FROM company_activity
 WHERE corp_code = %s
"""

TEXTS_SQL = """
SELECT fiscal_year, attr_key, seq, value_text
  FROM company_text
 WHERE corp_code = %s AND value_text IS NOT NULL AND btrim(value_text) <> ''
"""

# 같은 산업 상장사 중 최신 연도 매출 상위 N. 연결(CFS) 값을 우선해 순위를 매긴다.
PEERS_SQL = """
WITH latest AS (
    SELECT corp_code, max(fiscal_year) AS fiscal_year
      FROM company_metric
     WHERE metric_code = %(revenue)s AND metric_value IS NOT NULL
     GROUP BY corp_code
),
revenue AS (
    SELECT DISTINCT ON (cm.corp_code) cm.corp_code, cm.metric_value
      FROM company_metric cm
      JOIN latest l ON l.corp_code = cm.corp_code AND l.fiscal_year = cm.fiscal_year
     WHERE cm.metric_code = %(revenue)s
     ORDER BY cm.corp_code,
              CASE cm.fs_div WHEN 'CFS' THEN 0 WHEN 'OFS' THEN 2 ELSE 1 END
),
peers AS (
    SELECT c.corp_code, c.corp_name, l.fiscal_year
      FROM company c
      JOIN latest l ON l.corp_code = c.corp_code
      JOIN revenue r ON r.corp_code = c.corp_code
     WHERE c.industry_code = %(industry_code)s AND c.corp_code <> %(corp_code)s
     ORDER BY r.metric_value DESC NULLS LAST, c.corp_name
     LIMIT %(limit)s
)
SELECT p.corp_code, p.corp_name, p.fiscal_year, cm.metric_code, cm.metric_value, cm.fs_div
  FROM peers p
  JOIN company_metric cm ON cm.corp_code = p.corp_code AND cm.fiscal_year = p.fiscal_year
 WHERE cm.metric_code = ANY(%(metrics)s) AND cm.metric_value IS NOT NULL
"""

PEER_PRODUCTS_SQL = """
SELECT t.corp_code, t.value_text
  FROM company_text t
  JOIN (SELECT corp_code, max(fiscal_year) AS fiscal_year
          FROM company_text
         WHERE attr_key = %(attr)s AND corp_code = ANY(%(codes)s)
         GROUP BY corp_code) latest
    ON latest.corp_code = t.corp_code AND latest.fiscal_year = t.fiscal_year
 WHERE t.attr_key = %(attr)s AND t.corp_code = ANY(%(codes)s)
 ORDER BY t.corp_code, t.seq
"""


# --- 행 → 객체 (순수) ---------------------------------------------------------


def _float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def profile_from_row(row: Mapping[str, Any]) -> CompanyProfile:
    return CompanyProfile(
        corp_code=str(row["corp_code"]),
        corp_name=str(row["corp_name"]),
        industry_code=_text(row.get("industry_code")),
        industry_name=_text(row.get("industry_name")),
        induty_code=_text(row.get("induty_code")),
        ceo_name=_text(row.get("ceo_nm")),
        established_date=_text(row.get("established_date")),
        address=_text(row.get("address")),
        homepage_url=_text(row.get("homepage_url")),
        stock_code=_text(row.get("stock_code")),
    )


def metrics_from_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[MetricPoint, ...]:
    return tuple(
        MetricPoint(
            fiscal_year=int(row["fiscal_year"]),
            metric_code=str(row["metric_code"]),
            value=float(row["metric_value"]),
            fs_div=_text(row.get("fs_div")),
        )
        for row in rows
        if row.get("metric_value") is not None
    )


def segments_from_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[SegmentPoint, ...]:
    return tuple(
        SegmentPoint(
            fiscal_year=int(row["fiscal_year"]),
            segment_name=str(row["segment_name"]).strip(),
            metric_code=str(row["metric_code"]),
            value=float(row["metric_value"]),
        )
        for row in rows
        if row.get("metric_value") is not None
    )


def activities_from_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[Activity, ...]:
    return tuple(
        Activity(
            activity_id=str(row["id"]),
            fiscal_year=int(row["fiscal_year"]),
            activity_type=str(row["activity_type"]),
            field_name=_text(row.get("field_name")),
            purpose=_text(row.get("purpose")),
            amount=_float(row.get("amount")),
            rcept_no=_text(row.get("rcept_no")),
            counterparty=_text(row.get("counterparty")),
        )
        for row in rows
    )


def texts_from_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[TextAttr, ...]:
    return tuple(
        TextAttr(
            fiscal_year=int(row["fiscal_year"]),
            attr_key=str(row["attr_key"]),
            seq=int(row["seq"]),
            value=str(row["value_text"]).strip(),
        )
        for row in rows
        if _text(row.get("value_text"))
    )


def peers_from_rows(
    metric_rows: Sequence[Mapping[str, Any]],
    product_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[PeerFacts, ...]:
    """경쟁사별 지표 행을 모아 PeerFacts 로. 연결(CFS) 우선 규칙은 CompanyFacts 와 같다."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    order: list[str] = []
    for row in metric_rows:
        code = str(row["corp_code"])
        if code not in grouped:
            grouped[code] = []
            order.append(code)
        grouped[code].append(row)
    products: dict[str, list[str]] = {}
    for row in product_rows:
        text = _text(row.get("value_text"))
        if text:
            products.setdefault(str(row["corp_code"]), []).append(text)

    peers: list[PeerFacts] = []
    for code in order:
        rows = grouped[code]
        year = int(rows[0]["fiscal_year"])
        facts = CompanyFacts(
            profile=CompanyProfile(code, str(rows[0]["corp_name"]), None, None, None, None, None, None, None, None),
            metrics=metrics_from_rows(rows),
        )
        peers.append(
            PeerFacts(
                corp_code=code,
                corp_name=str(rows[0]["corp_name"]),
                fiscal_year=year,
                revenue=facts.metric(year, REVENUE),
                operating_profit=facts.metric(year, OPERATING_PROFIT),
                net_income=facts.metric(year, NET_INCOME),
                employee_count=facts.metric(year, EMPLOYEE_COUNT),
                main_products=tuple(products.get(code, ())[:5]),
            )
        )
    return tuple(peers)


# --- PostgreSQL --------------------------------------------------------------


class PostgresCompanyFactsRepository:
    def __init__(self, connect: Callable[[], Any], *, peer_limit: int = DEFAULT_PEER_LIMIT) -> None:
        """connect 는 psycopg 연결(컨텍스트 매니저)을 돌려주는 함수다. dict_row 가 아니어도 된다."""
        self._connect = connect
        self._peer_limit = peer_limit

    def other_company_names(self, corp_code: str, message: str) -> list[str]:
        """질문에 이름이 나오는 다른 상장사. 없으면 빈 목록.

        확정 지표는 이 기업의 값이라, 다른 기업을 물었는데 그 값을 내놓으면 사용자가 그것을
        그 기업의 수치로 받아들인다. 동종업계 목록만으로는 업종이 다른 기업(삼성전자 등)을
        못 걸러 기업 마스터 전체를 본다.

        이름이 두 글자인 회사(DL·SK 등)는 보지 않는다. 평범한 문장에 우연히 들어가 엉뚱하게
        걸린다.
        """
        if not message.strip():
            return []
        with self._connect() as connection:
            rows = _fetchall(connection, OTHER_COMPANY_SQL, (corp_code, message))
        # 이 저장소의 행은 dict 다(_fetchall 이 dict_row 로 받는다).
        return [str(row["corp_name"]) for row in rows]

    def load(self, corp_code: str) -> CompanyFacts | None:
        with self._connect() as connection:
            profile_row = _fetchone(connection, PROFILE_SQL, (corp_code,))
            if profile_row is None:
                return None
            profile = profile_from_row(profile_row)
            metrics = metrics_from_rows(_fetchall(connection, METRICS_SQL, (corp_code,)))
            segments = segments_from_rows(_fetchall(connection, SEGMENTS_SQL, (corp_code,)))
            activities = activities_from_rows(_fetchall(connection, ACTIVITIES_SQL, (corp_code,)))
            texts = texts_from_rows(_fetchall(connection, TEXTS_SQL, (corp_code,)))
            peers: tuple[PeerFacts, ...] = ()
            if profile.industry_code and self._peer_limit > 0:
                peer_rows = _fetchall(
                    connection,
                    PEERS_SQL,
                    {
                        "revenue": REVENUE,
                        "industry_code": profile.industry_code,
                        "corp_code": corp_code,
                        "limit": self._peer_limit,
                        "metrics": list(PEER_METRICS),
                    },
                )
                codes = sorted({str(row["corp_code"]) for row in peer_rows})
                product_rows = (
                    _fetchall(connection, PEER_PRODUCTS_SQL, {"attr": MAIN_PRODUCT, "codes": codes})
                    if codes
                    else []
                )
                peers = peers_from_rows(peer_rows, product_rows)
        return CompanyFacts(
            profile=profile,
            metrics=metrics,
            segments=segments,
            activities=activities,
            texts=texts,
            peers=peers,
        )


def _fetchall(connection: Any, sql: str, params: Any) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        names = [column.name for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def _fetchone(connection: Any, sql: str, params: Any) -> dict[str, Any] | None:
    rows = _fetchall(connection, sql, params)
    return rows[0] if rows else None
