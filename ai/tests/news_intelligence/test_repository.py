from __future__ import annotations

from datetime import datetime, timezone
import unittest

from psycopg import OperationalError
from psycopg.errors import QueryCanceled

from ai.news_intelligence.repository import (
    CompanyNotFound,
    JobContextNotFound,
    NewsSourceUnavailable,
    PostgresNewsRepository,
)


SINCE = datetime(2026, 6, 18, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, *, row=None, rows=None):
        self._row = row
        self._rows = rows or []
        self.closed = False

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, *, context_row=None, company_row=None, news_rows=None):
        self.context_row = context_row
        self.company_row = company_row
        self.news_rows = news_rows or []
        self.calls = []
        self.timeout_calls = []
        self.closed = False

    def execute(self, query, parameters):
        if "set_config('statement_timeout'" in query:
            self.timeout_calls.append((query, parameters))
            return FakeCursor()
        self.calls.append((query, parameters))
        if "FROM ai_job_contexts" in query:
            return FakeCursor(row=self.context_row)
        if "FROM company" in query:
            return FakeCursor(row=self.company_row)
        if "FROM news_article" in query:
            return FakeCursor(rows=self.news_rows)
        raise AssertionError(f"unexpected query: {query}")

    def close(self):
        self.closed = True


class PostgresNewsRepositoryTest(unittest.TestCase):
    def test_statement_timeout_is_transaction_local_and_cancellation_is_safe(self):
        class CanceledConnection(FakeConnection):
            def execute(self, query, parameters):
                if "FROM news_article" in query:
                    self.test.assertEqual(len(self.timeout_calls), 1)
                    raise QueryCanceled("secret SQL details")
                return super().execute(query, parameters)

        connection = CanceledConnection()
        connection.test = self
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)
        with self.assertRaises(NewsSourceUnavailable) as caught:
            repository.list_recent("00126380", SINCE, 20)
        self.assertNotIn("secret", str(caught.exception))
        self.assertTrue(connection.closed)
        query, parameters = connection.timeout_calls[0]
        self.assertIn("true", query.lower())
        self.assertEqual(parameters, ("5000",))

    def test_loads_exact_job_context_and_company_industry(self):
        connection = FakeConnection(
            context_row={
                "context_id": "ctx-1",
                "position_name": "백엔드 개발자",
                "jd_text": "서비스 개발",
                "role_elements": [{"name": "API 개발"}],
            },
            company_row={
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "industry_name": "반도체",
            },
        )
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        context = repository.load_context("ctx-1", "00126380")

        self.assertEqual(context.corp_code, "00126380")
        self.assertEqual(context.corp_name, "삼성전자")
        self.assertEqual(context.industry_name, "반도체")
        self.assertEqual(context.position_name, "백엔드 개발자")
        self.assertEqual(context.jd_text, "서비스 개발")
        self.assertEqual(context.role_elements, [{"name": "API 개발"}])
        self.assertEqual(connection.calls[0][1], ("ctx-1",))
        self.assertEqual(connection.calls[1][1], ("00126380",))
        self.assertIn("LEFT JOIN industry", connection.calls[1][0])
        self.assertTrue(connection.closed)

    def test_decodes_json_role_elements_and_preserves_nullable_industry(self):
        connection = FakeConnection(
            context_row={
                "context_id": "ctx-1",
                "position_name": "백엔드 개발자",
                "jd_text": "서비스 개발",
                "role_elements": '[{"name": "API 개발"}]',
            },
            company_row={
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "industry_name": None,
            },
        )
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        context = repository.load_context("ctx-1", "00126380")

        self.assertEqual(context.role_elements, [{"name": "API 개발"}])
        self.assertIsNone(context.industry_name)

    def test_rejects_missing_job_context_without_returning_partial_context(self):
        connection = FakeConnection(company_row={"corp_code": "00126380", "corp_name": "삼성전자", "industry_name": "반도체"})
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        with self.assertRaisesRegex(JobContextNotFound, "ctx-missing"):
            repository.load_context("ctx-missing", "00126380")

        self.assertEqual(len(connection.calls), 1)

    def test_rejects_missing_company_without_returning_partial_context(self):
        connection = FakeConnection(
            context_row={
                "context_id": "ctx-1",
                "position_name": "백엔드 개발자",
                "jd_text": "서비스 개발",
                "role_elements": [],
            }
        )
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        with self.assertRaisesRegex(CompanyNotFound, "00126380"):
            repository.load_context("ctx-1", "00126380")

        self.assertEqual(len(connection.calls), 2)

    def test_maps_bounded_news_rows_to_stored_candidates(self):
        connection = FakeConnection(
            news_rows=[
                {
                    "id": 17,
                    "title": "AI 투자 확대",
                    "source": None,
                    "published_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                    "original_url": "https://example.test/articles/17",
                    "guid": None,
                    "importance_score": None,
                }
            ]
        )
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        rows = repository.list_recent("00126380", SINCE, 100)

        self.assertEqual(rows[0].article_id, "stored:17")
        self.assertEqual(rows[0].origin, "STORED")
        self.assertEqual(rows[0].publisher, None)
        self.assertEqual(rows[0].importance_score, None)
        self.assertEqual(rows[0].published_at, datetime(2026, 9, 10, tzinfo=timezone.utc))
        query, parameters = connection.calls[0]
        self.assertIn("corp_code = %s", query)
        self.assertIn("published_at >= %s", query)
        self.assertIn("btrim(title) <> ''", query)
        self.assertIn("ORDER BY published_at DESC, importance_score DESC NULLS LAST, id DESC", query)
        self.assertIn("LIMIT %s", query)
        self.assertEqual(parameters, ("00126380", SINCE, 20))

    def test_skips_invalid_required_rows_and_normalizes_blank_optional_fields(self):
        connection = FakeConnection(
            news_rows=[
                {
                    "id": 17,
                    "title": "정상 기사",
                    "source": "",
                    "published_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                    "original_url": "https://example.test/articles/17",
                    "guid": "   ",
                    "importance_score": None,
                },
                {
                    "id": 18,
                    "title": "빈 URL",
                    "source": "매체",
                    "published_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                    "original_url": "",
                    "guid": None,
                    "importance_score": None,
                },
                {
                    "id": 19,
                    "title": "잘못된 URL",
                    "source": "매체",
                    "published_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                    "original_url": "not-a-url",
                    "guid": None,
                    "importance_score": None,
                },
                {
                    "id": 20,
                    "title": "   ",
                    "source": "매체",
                    "published_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                    "original_url": "https://example.test/articles/20",
                    "guid": None,
                    "importance_score": None,
                },
                {
                    "id": 21,
                    "title": "시간대 없는 기사",
                    "source": "매체",
                    "published_at": datetime(2026, 9, 10),
                    "original_url": "https://example.test/articles/21",
                    "guid": None,
                    "importance_score": None,
                },
            ]
        )
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        rows = repository.list_recent("00126380", SINCE, 20)

        self.assertEqual([row.article_id for row in rows], ["stored:17"])
        self.assertIsNone(rows[0].publisher)
        self.assertIsNone(rows[0].guid)
        self.assertTrue(connection.closed)

    def test_rejects_non_positive_news_limit_before_querying(self):
        connection = FakeConnection()
        repository = PostgresNewsRepository("postgresql://unused", connect=lambda: connection)

        with self.assertRaisesRegex(ValueError, "limit must be positive"):
            repository.list_recent("00126380", SINCE, 0)

        self.assertEqual(connection.calls, [])

    def test_wraps_operational_errors_without_leaking_database_url(self):
        database_url = "postgresql://news_user:secret@db.example/news"
        repository = PostgresNewsRepository(
            database_url,
            connect=lambda: (_ for _ in ()).throw(OperationalError("connection refused")),
        )

        with self.assertRaises(NewsSourceUnavailable) as raised:
            repository.list_recent("00126380", SINCE, 20)

        self.assertNotIn(database_url, str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
