from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Any, Protocol


@dataclass(frozen=True)
class AnalysisJob:
    analysis_id: str
    context_id: str
    status: str
    documents: tuple[dict[str, Any], ...]
    result: dict[str, Any] | None
    error: dict[str, str] | None
    created_at: str
    updated_at: str


class AnalysisStore(Protocol):
    def create(self, job: AnalysisJob) -> AnalysisJob: ...

    def get(self, analysis_id: str) -> AnalysisJob | None: ...

    def mark_running(self, analysis_id: str, updated_at: str) -> None: ...

    def complete(
        self, analysis_id: str, result: dict[str, Any], updated_at: str
    ) -> None: ...

    def fail(
        self, analysis_id: str, error: dict[str, str], updated_at: str
    ) -> None: ...


class InMemoryAnalysisStore:
    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = Lock()

    def create(self, job: AnalysisJob) -> AnalysisJob:
        with self._lock:
            if job.analysis_id in self._jobs:
                raise ValueError(f"duplicate analysis_id: {job.analysis_id}")
            self._jobs[job.analysis_id] = job
        return job

    def get(self, analysis_id: str) -> AnalysisJob | None:
        with self._lock:
            return self._jobs.get(analysis_id)

    def mark_running(self, analysis_id: str, updated_at: str) -> None:
        self._update(analysis_id, status="RUNNING", updated_at=updated_at)

    def complete(
        self, analysis_id: str, result: dict[str, Any], updated_at: str
    ) -> None:
        self._update(
            analysis_id,
            status="COMPLETED",
            result=result,
            error=None,
            updated_at=updated_at,
        )

    def fail(
        self, analysis_id: str, error: dict[str, str], updated_at: str
    ) -> None:
        self._update(
            analysis_id,
            status="FAILED",
            result=None,
            error=error,
            updated_at=updated_at,
        )

    def _update(self, analysis_id: str, **changes: Any) -> None:
        with self._lock:
            current = self._jobs.get(analysis_id)
            if current is None:
                raise KeyError(analysis_id)
            self._jobs[analysis_id] = replace(current, **changes)


class SqliteAnalysisStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    analysis_id TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    documents_json TEXT NOT NULL,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def create(self, job: AnalysisJob) -> AnalysisJob:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO analysis_jobs (
                    analysis_id, context_id, status, documents_json,
                    result_json, error_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.analysis_id,
                    job.context_id,
                    job.status,
                    json.dumps(job.documents, ensure_ascii=False),
                    None,
                    None,
                    job.created_at,
                    job.updated_at,
                ),
            )
            connection.commit()
        return job

    def get(self, analysis_id: str) -> AnalysisJob | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM analysis_jobs WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        return AnalysisJob(
            analysis_id=row["analysis_id"],
            context_id=row["context_id"],
            status=row["status"],
            documents=tuple(json.loads(row["documents_json"])),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def mark_running(self, analysis_id: str, updated_at: str) -> None:
        self._update(
            analysis_id,
            status="RUNNING",
            result=None,
            error=None,
            updated_at=updated_at,
        )

    def complete(
        self, analysis_id: str, result: dict[str, Any], updated_at: str
    ) -> None:
        self._update(
            analysis_id,
            status="COMPLETED",
            result=result,
            error=None,
            updated_at=updated_at,
        )

    def fail(
        self, analysis_id: str, error: dict[str, str], updated_at: str
    ) -> None:
        self._update(
            analysis_id,
            status="FAILED",
            result=None,
            error=error,
            updated_at=updated_at,
        )

    def _update(
        self,
        analysis_id: str,
        *,
        status: str,
        result: dict[str, Any] | None,
        error: dict[str, str] | None,
        updated_at: str,
    ) -> None:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, result_json = ?, error_json = ?, updated_at = ?
                WHERE analysis_id = ?
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False)
                    if result is not None
                    else None,
                    json.dumps(error, ensure_ascii=False)
                    if error is not None
                    else None,
                    updated_at,
                    analysis_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(analysis_id)
            connection.commit()
