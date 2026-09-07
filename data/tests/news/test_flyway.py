"""Flyway 스키마 파서. 검증 9·11번이 이 결과를 기준으로 대조한다."""
from __future__ import annotations

import unittest

from pipeline.news import curate, flyway
from pipeline.news.schema import SEED_FIELDS, SEED_TABLE


class SchemaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = flyway.load()

    def test_모든_마이그레이션을_파싱한다(self):
        self.assertGreaterEqual(len(self.schema.applied_files), 12)
        self.assertEqual(self.schema.applied_files[0], "V1__init_schema.sql")

    def test_뉴스_테이블이_존재한다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertIsNotNone(table, "company_news 가 스키마에 없다")
        self.assertEqual([c.name for c in table.ordered()], ["id"] + SEED_FIELDS)

    def test_identity_와_not_null_을_읽는다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertTrue(table.columns["id"].identity)
        self.assertFalse(table.columns["corp_code"].nullable)
        self.assertTrue(table.columns["published_at"].nullable)
        self.assertEqual(table.columns["collected_at"].default, "now()")

    def test_키와_참조를_읽는다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertIn("PK", table.columns["id"].key_type)
        self.assertIn("FK", table.columns["corp_code"].key_type)
        self.assertEqual(table.columns["corp_code"].referenced_table, "company")
        self.assertEqual(table.columns["corp_code"].referenced_column, "corp_code")
        # company_news_url_uk 부분 UNIQUE 인덱스
        self.assertIn("UK", table.columns["original_url"].key_type)

    def test_시드_헤더는_identity_를_제외한다(self):
        self.assertEqual(curate.seed_header(self.schema), SEED_FIELDS)
        self.assertNotIn("id", SEED_FIELDS)

    def test_나중_마이그레이션의_추가_컬럼이_반영된다(self):
        company = self.schema.table("company")
        self.assertIn("induty_code", company.columns)     # V3
        self.assertIn("address", company.columns)         # V8
        self.assertIn("is_core", self.schema.table("metric").columns)  # V7
        self.assertIn("employee_count", self.schema.table("company_segment").columns)  # V11

    def test_주석을_읽는다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertIn("기업별 뉴스", table.comment)
        self.assertIn("NULL", table.columns["importance_score"].comment)

    def test_staging_스키마를_구분한다(self):
        table = self.schema.table("dart_otr_cpr_invstmnt")
        self.assertEqual(table.schema, "staging")
        self.assertEqual(table.qualified, "staging.dart_otr_cpr_invstmnt")

    def test_sql_로_시드되는_테이블을_기록한다(self):
        self.assertEqual(self.schema.seeded_tables, {"industry", "metric"})


if __name__ == "__main__":
    unittest.main()
