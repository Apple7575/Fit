from __future__ import annotations

from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ai.jd_coaching.analysis_store import AnalysisJob, AnalysisStore
from ai.jd_coaching.context_store import JobContext, JobContextStore


class PostgresJobContextStore(JobContextStore):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _connect(self):
        return psycopg.connect(
            self._database_url,
            connect_timeout=5,
            row_factory=dict_row,
        )

    def save(self, context: JobContext) -> JobContext:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO ai_job_contexts (
                        context_id, source_hash, company_name, position_name,
                        jd_text, role_elements, created_at, job_posting_id,
                        source_url, published_at, valid_until, retrieved_at,
                        source_type, version, source_filename,
                        source_content_sha256
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        context.context_id,
                        context.source_hash,
                        context.company_name,
                        context.position_name,
                        context.jd_text,
                        Jsonb(list(context.role_elements)),
                        context.created_at,
                        context.job_posting_id,
                        context.source_url,
                        context.published_at,
                        context.valid_until,
                        context.retrieved_at,
                        context.source_type,
                        context.version,
                        context.source_filename,
                        context.source_content_sha256,
                    ),
                )
        except UniqueViolation:
            existing = self.find_by_source_hash(context.source_hash)
            if existing is None:
                raise
            return existing
        return context

    def get(self, context_id: str) -> JobContext | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_job_contexts WHERE context_id = %s",
                (context_id,),
            ).fetchone()
        return _context_from_row(row)

    def find_by_source_hash(self, source_hash: str) -> JobContext | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_job_contexts WHERE source_hash = %s",
                (source_hash,),
            ).fetchone()
        return _context_from_row(row)

    def latest_version_for_job_posting(self, job_posting_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS version
                FROM ai_job_contexts
                WHERE job_posting_id = %s
                """,
                (job_posting_id,),
            ).fetchone()
        return int(row["version"])


class PostgresAnalysisStore(AnalysisStore):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _connect(self):
        return psycopg.connect(
            self._database_url,
            connect_timeout=5,
            row_factory=dict_row,
        )

    def create(self, job: AnalysisJob) -> AnalysisJob:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_analysis_jobs (
                    analysis_id, context_id, status, documents,
                    result, error, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    job.analysis_id,
                    job.context_id,
                    job.status,
                    Jsonb(list(job.documents)),
                    Jsonb(job.result) if job.result is not None else None,
                    Jsonb(job.error) if job.error is not None else None,
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job

    def get(self, analysis_id: str) -> AnalysisJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_analysis_jobs WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
        return _analysis_from_row(row)

    def mark_running(self, analysis_id: str, updated_at: str) -> None:
        self._update(
            analysis_id,
            status="RUNNING",
            result=None,
            error=None,
            updated_at=updated_at,
            clear_documents=False,
        )

    def complete(
        self,
        analysis_id: str,
        result: dict[str, Any],
        updated_at: str,
    ) -> None:
        self._update(
            analysis_id,
            status="COMPLETED",
            result=result,
            error=None,
            updated_at=updated_at,
            clear_documents=True,
        )

    def fail(
        self,
        analysis_id: str,
        error: dict[str, str],
        updated_at: str,
    ) -> None:
        self._update(
            analysis_id,
            status="FAILED",
            result=None,
            error=error,
            updated_at=updated_at,
            clear_documents=True,
        )

    def _update(
        self,
        analysis_id: str,
        *,
        status: str,
        result: dict[str, Any] | None,
        error: dict[str, str] | None,
        updated_at: str,
        clear_documents: bool,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_analysis_jobs
                SET status = %s,
                    result = %s,
                    error = %s,
                    updated_at = %s,
                    documents = CASE WHEN %s THEN '[]'::jsonb ELSE documents END
                WHERE analysis_id = %s
                """,
                (
                    status,
                    Jsonb(result) if result is not None else None,
                    Jsonb(error) if error is not None else None,
                    updated_at,
                    clear_documents,
                    analysis_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(analysis_id)


def _context_from_row(row: dict[str, Any] | None) -> JobContext | None:
    if row is None:
        return None
    return JobContext(
        context_id=row["context_id"],
        source_hash=row["source_hash"],
        company_name=row["company_name"],
        position_name=row["position_name"],
        jd_text=row["jd_text"],
        role_elements=tuple(row["role_elements"]),
        created_at=_isoformat(row["created_at"]),
        job_posting_id=row["job_posting_id"],
        source_url=row["source_url"],
        published_at=_isoformat(row["published_at"]),
        valid_until=_isoformat(row["valid_until"]),
        retrieved_at=_isoformat(row["retrieved_at"]),
        source_type=row["source_type"],
        version=row["version"],
        source_filename=row["source_filename"],
        source_content_sha256=row["source_content_sha256"],
    )


def _analysis_from_row(row: dict[str, Any] | None) -> AnalysisJob | None:
    if row is None:
        return None
    return AnalysisJob(
        analysis_id=row["analysis_id"],
        context_id=row["context_id"],
        status=row["status"],
        documents=tuple(row["documents"]),
        result=row["result"],
        error=row["error"],
        created_at=_isoformat(row["created_at"]),
        updated_at=_isoformat(row["updated_at"]),
    )


def _isoformat(value: str | date | datetime | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()
