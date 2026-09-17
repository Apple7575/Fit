import os
import unittest
from datetime import date, datetime, timezone
from uuid import uuid4

import psycopg

from ai.jd_coaching.analysis_store import AnalysisJob
from ai.jd_coaching.context_store import JobContext, make_source_hash
from ai.jd_coaching.postgres_store import (
    PostgresAnalysisStore,
    PostgresJobContextStore,
    _analysis_from_row,
    _context_from_row,
)


class FakeCursor:
    rowcount = 1


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters):
        self.calls.append((query, parameters))
        return FakeCursor()


class PostgresStoreTest(unittest.TestCase):
    def test_converts_postgres_job_context_row(self):
        row = {
            "context_id": "jctx-1",
            "source_hash": "a" * 64,
            "company_name": "기업",
            "position_name": "직무",
            "jd_text": "Python API 개발 경험",
            "role_elements": [{"role_element_id": "role-001"}],
            "created_at": datetime(2026, 9, 13, tzinfo=timezone.utc),
            "job_posting_id": "posting-1",
            "source_url": None,
            "published_at": date(2026, 9, 1),
            "valid_until": date(2026, 9, 30),
            "retrieved_at": date(2026, 9, 13),
            "source_type": "USER_PROVIDED_JOB_POSTING",
            "version": 1,
            "source_filename": "posting.pdf",
            "source_content_sha256": "b" * 64,
        }

        context = _context_from_row(row)

        self.assertEqual(context.created_at, "2026-09-13T00:00:00+00:00")
        self.assertEqual(context.published_at, "2026-09-01")
        self.assertEqual(context.role_elements[0]["role_element_id"], "role-001")

    def test_converts_postgres_analysis_row(self):
        row = {
            "analysis_id": "analysis-1",
            "context_id": "jctx-1",
            "status": "COMPLETED",
            "documents": [],
            "result": {"summary": {"supported": 1}},
            "error": None,
            "created_at": datetime(2026, 9, 13, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 9, 13, 0, 1, tzinfo=timezone.utc),
        }

        job = _analysis_from_row(row)

        self.assertEqual(job.documents, ())
        self.assertEqual(job.result["summary"]["supported"], 1)
        self.assertEqual(job.updated_at, "2026-09-13T00:01:00+00:00")

    def test_clears_input_documents_after_completed_job(self):
        connection = FakeConnection()
        store = PostgresAnalysisStore("postgresql://unused")
        store._connect = lambda: connection

        store.complete(
            "analysis-1",
            {"summary": {"supported": 1}},
            "2026-09-13T00:01:00+00:00",
        )

        query, parameters = connection.calls[0]
        self.assertIn("documents = CASE", query)
        self.assertIs(parameters[4], True)


@unittest.skipUnless(
    os.environ.get("JD_TEST_DATABASE_URL"),
    "JD_TEST_DATABASE_URL is not configured",
)
class PostgresStoreIntegrationTest(unittest.TestCase):
    def test_persists_context_and_clears_completed_job_documents(self):
        database_url = os.environ["JD_TEST_DATABASE_URL"]
        suffix = uuid4().hex
        context_id = f"jctx_test_{suffix}"
        analysis_id = f"analysis_test_{suffix}"
        context_store = PostgresJobContextStore(database_url)
        analysis_store = PostgresAnalysisStore(database_url)
        context = JobContext(
            context_id=context_id,
            source_hash=make_source_hash("테스트기업", "테스트직무", suffix),
            company_name="테스트기업",
            position_name="테스트직무",
            jd_text=f"Python API 개발 경험 {suffix}",
            role_elements=({"role_element_id": "role-001"},),
            created_at="2026-09-13T00:00:00+00:00",
        )
        job = AnalysisJob(
            analysis_id=analysis_id,
            context_id=context_id,
            status="QUEUED",
            documents=({"document_id": "essay-1", "text": "사용자 원문"},),
            result=None,
            error=None,
            created_at="2026-09-13T00:00:00+00:00",
            updated_at="2026-09-13T00:00:00+00:00",
        )

        try:
            context_store.save(context)
            analysis_store.create(job)
            analysis_store.complete(
                analysis_id,
                {"summary": {"supported": 1}},
                "2026-09-13T00:01:00+00:00",
            )

            stored_context = context_store.get(context_id)
            stored_job = analysis_store.get(analysis_id)
            self.assertEqual(stored_context, context)
            self.assertEqual(stored_job.documents, ())
            self.assertEqual(stored_job.status, "COMPLETED")
        finally:
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    "DELETE FROM ai_job_contexts WHERE context_id = %s",
                    (context_id,),
                )


if __name__ == "__main__":
    unittest.main()
