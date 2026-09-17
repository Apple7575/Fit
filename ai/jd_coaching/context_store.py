from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class JobContext:
    context_id: str
    source_hash: str
    company_name: str
    position_name: str
    jd_text: str
    role_elements: tuple[dict, ...]
    created_at: str
    job_posting_id: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    valid_until: str | None = None
    retrieved_at: str | None = None
    source_type: str = "USER_PROVIDED_JOB_POSTING"
    version: int = 1
    source_filename: str | None = None
    source_content_sha256: str | None = None


class JobContextStore(Protocol):
    def save(self, context: JobContext) -> JobContext: ...

    def get(self, context_id: str) -> JobContext | None: ...

    def find_by_source_hash(self, source_hash: str) -> JobContext | None: ...

    def latest_version_for_job_posting(self, job_posting_id: str) -> int: ...


def make_source_hash(
    company_name: str,
    position_name: str,
    jd_text: str,
    job_posting_id: str | None = None,
) -> str:
    normalized = "\n".join(
        value.strip()
        for value in (
            company_name,
            position_name,
            jd_text,
            job_posting_id or "",
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class InMemoryJobContextStore:
    def __init__(self) -> None:
        self._by_id: dict[str, JobContext] = {}
        self._id_by_hash: dict[str, str] = {}

    def save(self, context: JobContext) -> JobContext:
        existing = self.find_by_source_hash(context.source_hash)
        if existing is not None:
            return existing
        self._by_id[context.context_id] = context
        self._id_by_hash[context.source_hash] = context.context_id
        return context

    def get(self, context_id: str) -> JobContext | None:
        return self._by_id.get(context_id)

    def find_by_source_hash(self, source_hash: str) -> JobContext | None:
        context_id = self._id_by_hash.get(source_hash)
        return self._by_id.get(context_id) if context_id else None

    def latest_version_for_job_posting(self, job_posting_id: str) -> int:
        return max(
            (
                context.version
                for context in self._by_id.values()
                if context.job_posting_id == job_posting_id
            ),
            default=0,
        )


class SqliteJobContextStore:
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
                CREATE TABLE IF NOT EXISTS job_contexts (
                    context_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL UNIQUE,
                    company_name TEXT NOT NULL,
                    position_name TEXT NOT NULL,
                    jd_text TEXT NOT NULL,
                    role_elements_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    job_posting_id TEXT,
                    source_url TEXT,
                    published_at TEXT,
                    valid_until TEXT,
                    retrieved_at TEXT,
                    source_type TEXT NOT NULL DEFAULT 'USER_PROVIDED_JOB_POSTING',
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(job_contexts)")
            }
            additions = {
                "job_posting_id": "TEXT",
                "source_url": "TEXT",
                "published_at": "TEXT",
                "valid_until": "TEXT",
                "retrieved_at": "TEXT",
                "source_type": "TEXT NOT NULL DEFAULT 'USER_PROVIDED_JOB_POSTING'",
                "version": "INTEGER NOT NULL DEFAULT 1",
                "source_filename": "TEXT",
                "source_content_sha256": "TEXT",
            }
            for name, definition in additions.items():
                if name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE job_contexts ADD COLUMN {name} {definition}"
                    )
            connection.commit()

    def save(self, context: JobContext) -> JobContext:
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO job_contexts (
                        context_id, source_hash, company_name, position_name,
                        jd_text, role_elements_json, created_at, job_posting_id,
                        source_url, published_at, valid_until, retrieved_at,
                        source_type, version, source_filename,
                        source_content_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        context.context_id,
                        context.source_hash,
                        context.company_name,
                        context.position_name,
                        context.jd_text,
                        json.dumps(
                            context.role_elements, ensure_ascii=False
                        ),
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
                connection.commit()
        except sqlite3.IntegrityError:
            existing = self.find_by_source_hash(context.source_hash)
            if existing is None:
                raise
            return existing
        return context

    def get(self, context_id: str) -> JobContext | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM job_contexts WHERE context_id = ?",
                (context_id,),
            ).fetchone()
        return _row_to_context(row)

    def find_by_source_hash(self, source_hash: str) -> JobContext | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM job_contexts WHERE source_hash = ?",
                (source_hash,),
            ).fetchone()
        return _row_to_context(row)

    def latest_version_for_job_posting(self, job_posting_id: str) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT MAX(version) AS version FROM job_contexts WHERE job_posting_id = ?",
                (job_posting_id,),
            ).fetchone()
        return int(row["version"] or 0)


def _row_to_context(row: sqlite3.Row | None) -> JobContext | None:
    if row is None:
        return None
    return JobContext(
        context_id=row["context_id"],
        source_hash=row["source_hash"],
        company_name=row["company_name"],
        position_name=row["position_name"],
        jd_text=row["jd_text"],
        role_elements=tuple(json.loads(row["role_elements_json"])),
        created_at=row["created_at"],
        job_posting_id=row["job_posting_id"],
        source_url=row["source_url"],
        published_at=row["published_at"],
        valid_until=row["valid_until"],
        retrieved_at=row["retrieved_at"],
        source_type=row["source_type"],
        version=row["version"],
        source_filename=row["source_filename"],
        source_content_sha256=row["source_content_sha256"],
    )
