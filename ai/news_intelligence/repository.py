from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
from typing import Any, Callable, Mapping, Protocol

import psycopg
from pydantic import ValidationError
from psycopg.rows import dict_row

from ai.news_intelligence.budget import remaining_timeout
from ai.news_intelligence.contracts import NewsCandidate, NewsContext


MAX_STORED_CANDIDATES = 20
_CONNECT_TIMEOUT_SECONDS = 5
_STATEMENT_TIMEOUT_SECONDS = 5


class NewsRepository(Protocol):
    def load_context(self, job_context_id: str, corp_code: str) -> NewsContext: ...

    def list_recent(
        self, corp_code: str, since: datetime, limit: int
    ) -> list[NewsCandidate]: ...


class JobContextNotFound(LookupError):
    def __init__(self, job_context_id: str) -> None:
        super().__init__(f"job context not found: {job_context_id}")


class CompanyNotFound(LookupError):
    def __init__(self, corp_code: str) -> None:
        super().__init__(f"company not found: {corp_code}")


class NewsSourceUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("news source is unavailable")


class PostgresNewsRepository:
    def __init__(
        self,
        database_url: str,
        *,
        connect: Callable[[], Any] | None = None,
    ) -> None:
        self._database_url = database_url
        self._connect = connect or self._default_connect

    def _default_connect(self):
        return psycopg.connect(
            self._database_url,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            row_factory=dict_row,
        )

    def load_context(self, job_context_id: str, corp_code: str) -> NewsContext:
        try:
            self._require_connect_budget()
            with closing(self._connect()) as connection:
                context_row = self._fetchone(
                    connection,
                    """
                    SELECT context_id, position_name, jd_text, role_elements
                    FROM ai_job_contexts
                    WHERE context_id = %s
                    """,
                    (job_context_id,),
                )
                if context_row is None:
                    raise JobContextNotFound(job_context_id)

                company_row = self._fetchone(
                    connection,
                    """
                    SELECT company.corp_code, company.corp_name, industry.industry_name
                    FROM company
                    LEFT JOIN industry
                        ON industry.industry_code = company.industry_code
                    WHERE company.corp_code = %s
                    """,
                    (corp_code,),
                )
                if company_row is None:
                    raise CompanyNotFound(corp_code)
        except (psycopg.OperationalError, psycopg.errors.QueryCanceled) as error:
            raise NewsSourceUnavailable() from error

        return NewsContext(
            corp_code=company_row["corp_code"],
            corp_name=company_row["corp_name"],
            industry_name=company_row["industry_name"],
            position_name=context_row["position_name"],
            jd_text=context_row["jd_text"],
            role_elements=_role_elements_from_row(context_row["role_elements"]),
        )

    def list_recent(
        self, corp_code: str, since: datetime, limit: int
    ) -> list[NewsCandidate]:
        if isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be positive")
        _require_timezone_aware(since, "since")
        bounded_limit = min(limit, MAX_STORED_CANDIDATES)

        try:
            self._require_connect_budget()
            with closing(self._connect()) as connection:
                rows = self._fetchall(
                    connection,
                    """
                    SELECT id, title, source, published_at, original_url, guid,
                           importance_score
                    FROM news_article
                    WHERE corp_code = %s
                      AND published_at >= %s
                      AND title IS NOT NULL
                      AND btrim(title) <> ''
                      AND original_url IS NOT NULL
                    ORDER BY published_at DESC, importance_score DESC NULLS LAST, id DESC
                    LIMIT %s
                    """,
                    (corp_code, since, bounded_limit),
                )
        except (psycopg.OperationalError, psycopg.errors.QueryCanceled) as error:
            raise NewsSourceUnavailable() from error

        return [
            candidate
            for row in rows
            if (candidate := _candidate_from_row(row)) is not None
        ]

    @staticmethod
    def _require_connect_budget() -> None:
        # libpq has an integer connect timeout; do not start when it cannot fit.
        if remaining_timeout(_CONNECT_TIMEOUT_SECONDS, NewsSourceUnavailable) < _CONNECT_TIMEOUT_SECONDS:
            raise NewsSourceUnavailable()

    @staticmethod
    def _set_statement_timeout(connection: Any) -> None:
        milliseconds = int(1000 * remaining_timeout(_STATEMENT_TIMEOUT_SECONDS, NewsSourceUnavailable))
        if milliseconds < 1:
            raise NewsSourceUnavailable()
        # true scopes the setting to this transaction, never to a pooled session.
        with closing(connection.execute(
            "SELECT set_config('statement_timeout', %s, true)", (str(milliseconds),),
        )):
            pass

    @staticmethod
    def _fetchone(connection: Any, query: str, parameters: tuple[Any, ...]):
        PostgresNewsRepository._set_statement_timeout(connection)
        with closing(connection.execute(query, parameters)) as cursor:
            return cursor.fetchone()

    @staticmethod
    def _fetchall(connection: Any, query: str, parameters: tuple[Any, ...]):
        PostgresNewsRepository._set_statement_timeout(connection)
        with closing(connection.execute(query, parameters)) as cursor:
            return cursor.fetchall()


def _role_elements_from_row(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise NewsSourceUnavailable() from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise NewsSourceUnavailable()
    return value


def _candidate_from_row(row: Mapping[str, Any]) -> NewsCandidate | None:
    published_at = row["published_at"]
    if not isinstance(published_at, datetime) or published_at.utcoffset() is None:
        return None
    try:
        return NewsCandidate(
            article_id=f"stored:{row['id']}",
            origin="STORED",
            title=row["title"],
            publisher=_normalize_optional_text(row["source"]),
            published_at=published_at,
            url=row["original_url"],
            guid=_normalize_optional_text(row["guid"]),
            importance_score=row["importance_score"],
        )
    except ValidationError:
        return None


def _normalize_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
