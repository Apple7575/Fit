from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import os
import unittest
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ai.news_intelligence.repository import PostgresNewsRepository


class SharedTransactionConnection:
    """Prevents the repository from closing the integration test transaction."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, parameters):
        return self._connection.execute(query, parameters)

    def close(self):
        pass


@unittest.skipUnless(
    os.environ.get("JD_TEST_DATABASE_URL"),
    "JD_TEST_DATABASE_URL is not set",
)
class PostgresNewsRepositoryIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.database_url = os.environ["JD_TEST_DATABASE_URL"]
        suffix = uuid4().hex
        self.corp_code = f"9{int(suffix[:7], 16) % 10_000_000:07d}"
        self.context_id = f"jctx_news_{suffix}"
        self.industry_code = f"test-{suffix[:4]}"
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.connection = psycopg.connect(self.database_url, row_factory=dict_row)
        self.transaction = self.connection.transaction()
        self.transaction.__enter__()
        self.addCleanup(self._rollback_and_close)

        self.connection.execute(
            "INSERT INTO industry (industry_code, industry_name) VALUES (%s, %s)",
            (self.industry_code, "통합테스트 산업"),
        )
        self.connection.execute(
            "INSERT INTO company (corp_code, corp_name, industry_code) VALUES (%s, %s, %s)",
            (self.corp_code, "통합테스트 기업", self.industry_code),
        )
        self.connection.execute(
            """
            INSERT INTO ai_job_contexts (
                context_id, source_hash, company_name, position_name, jd_text,
                role_elements, created_at, source_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                self.context_id,
                hashlib.sha256(self.context_id.encode()).hexdigest(),
                "통합테스트 기업",
                "통합테스트 직무",
                "통합테스트 JD",
                Jsonb([{"name": "API 개발"}]),
                self.now,
                "USER_PROVIDED_JOB_POSTING",
            ),
        )
        cursor = self.connection.execute(
            """
            INSERT INTO news_article (
                corp_code, title, published_at, original_url, source, guid,
                importance_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                self.corp_code,
                "통합테스트 뉴스",
                self.now - timedelta(days=1),
                f"https://example.test/news/{suffix}",
                "통합테스트 매체",
                f"guid-{suffix}",
                8.0,
            ),
        )
        self.news_id = cursor.fetchone()["id"]

    def _rollback_and_close(self):
        self.transaction.__exit__(Exception, Exception("rollback test data"), None)
        self.connection.close()

    def test_reads_context_and_recent_news_from_postgres(self):
        repository = PostgresNewsRepository(
            self.database_url,
            connect=lambda: SharedTransactionConnection(self.connection),
        )

        context = repository.load_context(self.context_id, self.corp_code)
        rows = repository.list_recent(self.corp_code, self.now - timedelta(days=90), 20)

        self.assertEqual(context.position_name, "통합테스트 직무")
        self.assertEqual(context.role_elements, [{"name": "API 개발"}])
        self.assertEqual([row.article_id for row in rows], [f"stored:{self.news_id}"])
        self.assertEqual(rows[0].origin, "STORED")


if __name__ == "__main__":
    unittest.main()
