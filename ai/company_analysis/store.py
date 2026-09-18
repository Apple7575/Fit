"""리포트 저장소. 만들어 둔 리포트를 corp_code 로 찾아 즉시 돌려준다.

PostgreSQL 구현은 company_analysis_report(V29) 를 쓰고, 메모리 구현은 테스트용이다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .contracts import CompanyReport, ReportStatus, ReportStatusValue


@dataclass(frozen=True)
class StoredReport:
    status: ReportStatus
    report: CompanyReport | None


class ReportStore(Protocol):
    def get(self, corp_code: str) -> StoredReport | None: ...

    def mark(self, corp_code: str, status: ReportStatusValue, *, error: str | None = None) -> ReportStatus: ...

    def save_ready(self, corp_code: str, report: CompanyReport) -> ReportStatus: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryReportStore:
    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        self._rows: dict[str, StoredReport] = {}
        self._clock = clock

    def get(self, corp_code: str) -> StoredReport | None:
        return self._rows.get(corp_code)

    def mark(self, corp_code: str, status: ReportStatusValue, *, error: str | None = None) -> ReportStatus:
        previous = self._rows.get(corp_code)
        report = previous.report if previous and status != "FAILED" else None
        row = ReportStatus(
            corp_code=corp_code,
            status=status,
            updated_at=self._clock(),
            fiscal_year=report.fiscal_year if report else None,
            error=error,
        )
        self._rows[corp_code] = StoredReport(status=row, report=report)
        return row

    def save_ready(self, corp_code: str, report: CompanyReport) -> ReportStatus:
        row = ReportStatus(
            corp_code=corp_code, status="READY", updated_at=self._clock(), fiscal_year=report.fiscal_year
        )
        self._rows[corp_code] = StoredReport(status=row, report=report)
        return row


UPSERT_STATUS_SQL = """
INSERT INTO company_analysis_report (corp_code, status, error, requested_at, updated_at)
VALUES (%(corp_code)s, %(status)s, %(error)s, now(), now())
ON CONFLICT (corp_code) DO UPDATE
   SET status = EXCLUDED.status,
       error = EXCLUDED.error,
       report = CASE WHEN EXCLUDED.status = 'FAILED' THEN NULL ELSE company_analysis_report.report END,
       fiscal_year = CASE WHEN EXCLUDED.status = 'FAILED' THEN NULL ELSE company_analysis_report.fiscal_year END,
       updated_at = now()
RETURNING corp_code, status, fiscal_year, error, updated_at
"""

UPSERT_READY_SQL = """
INSERT INTO company_analysis_report (corp_code, status, fiscal_year, report, error, requested_at, updated_at)
VALUES (%(corp_code)s, 'READY', %(fiscal_year)s, %(report)s::jsonb, NULL, now(), now())
ON CONFLICT (corp_code) DO UPDATE
   SET status = 'READY', fiscal_year = EXCLUDED.fiscal_year, report = EXCLUDED.report,
       error = NULL, updated_at = now()
RETURNING corp_code, status, fiscal_year, error, updated_at
"""

SELECT_SQL = """
SELECT corp_code, status, fiscal_year, error, updated_at, report::text AS report
  FROM company_analysis_report
 WHERE corp_code = %s
"""


class PostgresReportStore:
    def __init__(self, connect: Callable[[], Any]) -> None:
        self._connect = connect

    def get(self, corp_code: str) -> StoredReport | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(SELECT_SQL, (corp_code,))
            row = cursor.fetchone()
        if row is None:
            return None
        corp, status, fiscal_year, error, updated_at, report_json = row
        report = CompanyReport.model_validate_json(report_json) if report_json else None
        return StoredReport(
            status=ReportStatus(
                corp_code=corp, status=status, updated_at=updated_at, fiscal_year=fiscal_year, error=error
            ),
            report=report,
        )

    def mark(self, corp_code: str, status: ReportStatusValue, *, error: str | None = None) -> ReportStatus:
        return self._write(UPSERT_STATUS_SQL, {"corp_code": corp_code, "status": status, "error": error})

    def save_ready(self, corp_code: str, report: CompanyReport) -> ReportStatus:
        return self._write(
            UPSERT_READY_SQL,
            {"corp_code": corp_code, "fiscal_year": report.fiscal_year, "report": report.model_dump_json()},
        )

    def _write(self, sql: str, params: dict[str, Any]) -> ReportStatus:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            corp, status, fiscal_year, error, updated_at = cursor.fetchone()
            connection.commit()
        return ReportStatus(corp_code=corp, status=status, updated_at=updated_at, fiscal_year=fiscal_year, error=error)


def report_to_json(report: CompanyReport) -> dict[str, Any]:
    return json.loads(report.model_dump_json())
