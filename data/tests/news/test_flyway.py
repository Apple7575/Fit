"""Flyway 스키마 파서. 검증 9·11번이 이 결과를 기준으로 대조한다."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.news import curate, flyway
from pipeline.news.schema import SEED_FIELDS, SEED_TABLE


class SchemaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = flyway.load()

    def test_모든_마이그레이션을_파싱한다(self):
        self.assertGreaterEqual(len(self.schema.applied_files), 13)
        self.assertEqual(self.schema.applied_files[0], "V1__init_schema.sql")

    def test_뉴스_테이블이_존재한다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertIsNotNone(table, "news_article 이 스키마에 없다")
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
        # V12 의 부분 UNIQUE 인덱스 company_news_url_uk 를 V13 이 다시 만들지 않아
        # 지금은 UK 가 없다. 복원을 요청해 두었고(docs/S15P21A504-v13-followup.md 2장)
        # 복원되면 이 단정을 되돌린다. 스키마 사실을 그대로 적어 둔다.
        self.assertNotIn("UK", table.columns["original_url"].key_type)

    def test_시드_헤더는_identity_를_제외한다(self):
        self.assertEqual(curate.seed_header(self.schema), SEED_FIELDS)
        self.assertNotIn("id", SEED_FIELDS)

    def test_나중_마이그레이션의_추가_컬럼이_반영된다(self):
        company = self.schema.table("company")
        self.assertIn("induty_code", company.columns)     # V3
        self.assertIn("address", company.columns)         # V8
        self.assertIn("is_core", self.schema.table("metric").columns)  # V7
        self.assertIn("counterparty", self.schema.table("company_activity").columns)  # V13

    def test_주석을_읽는다(self):
        table = self.schema.table(SEED_TABLE)
        self.assertIn("기업별 뉴스", table.comment)
        self.assertIn("수집 출처", table.columns["source"].comment)
        # V13 이 V12 의 컬럼 주석 다섯 개(title · description · published_at ·
        # related_business · importance_score)를 옮기지 않았다. 복원을 요청해 두었고
        # (docs/S15P21A504-v13-followup.md 2장) 그때까지는 데이터 사전이
        # build_data_fields.py 의 DESC 로 설명을 채운다.
        self.assertEqual(table.columns["importance_score"].comment, "")

    def test_DROP_COLUMN_을_읽는다(self):
        """V16 이 한 ALTER 에서 콤마로 지운 네 컬럼이 스키마에 남지 않아야 한다.

        읽지 않으면 데이터 사전이 없는 컬럼을 문서화한 채로 9번이 통과한다 —
        대조가 있으나 마나 해진다.
        """
        table = self.schema.table(SEED_TABLE)
        for column in ("description", "news_category", "related_business", "analyzed_at"):
            self.assertNotIn(column, table.columns, column)
        # 같은 표의 나머지는 그대로다
        for column in ("id", "corp_code", "title", "importance_score", "collected_at"):
            self.assertIn(column, table.columns, column)

    def test_ADD_CONSTRAINT_UNIQUE_를_읽는다(self):
        """V17 의 news_article_guid_uk 처럼 나중에 붙는 유일성 제약도 키로 잡아야 한다.

        CREATE TABLE 안의 UNIQUE 와 CREATE UNIQUE INDEX 는 읽고 있었는데 이 형태만
        빠져 있었다. 읽지 않으면 확정 ERD 의 중복 방지 키가 사전에 그냥 널 허용
        컬럼으로 남는다 — 9번은 컬럼 이름만 대조하므로 잡지 못한다.
        """
        table = self.schema.table(SEED_TABLE)
        self.assertIn("UK", table.columns["guid"].key_type)
        self.assertIn("UK", table.columns["corp_code"].key_type)
        # 제약에 없는 컬럼까지 UK 가 되지는 않는다
        self.assertNotIn("UK", table.columns["title"].key_type)

    def test_staging_스키마를_구분한다(self):
        table = self.schema.table("dart_otr_cpr_invstmnt")
        self.assertEqual(table.schema, "staging")
        self.assertEqual(table.qualified, "staging.dart_otr_cpr_invstmnt")

    def test_지워진_테이블은_스키마에_남지_않는다(self):
        """V13 이 DROP 한 일곱 개다. 남으면 데이터 사전 대조가 거꾸로 판정한다."""
        for name in ("company_news", "company_segment", "company_business",
                     "company_product", "company_rnd_field",
                     "company_focus_direction", "company_focus_direction_item"):
            self.assertIsNone(self.schema.table(name), f"{name} 이 아직 남아 있다")
        self.assertIsNotNone(self.schema.table("news_article"))
        self.assertIsNotNone(self.schema.table("company_text"))
        self.assertIsNotNone(self.schema.table("segment_metric"))

    def test_set_schema_가_스키마를_옮긴다(self):
        """정리 마이그레이션이 collection_run·dart_employee_status 를 staging 으로 옮긴다.

        아직 그런 마이그레이션이 없어 임시 디렉터리로 파서만 확인한다.
        """
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "V1__init.sql").write_text(
                "CREATE TABLE t (id BIGINT PRIMARY KEY);", encoding="utf-8")
            (directory / "V2__move.sql").write_text(
                "CREATE SCHEMA staging;\nALTER TABLE t SET SCHEMA staging;",
                encoding="utf-8")
            schema = flyway.load(directory)
        self.assertEqual(schema.table("t").schema, "staging")
        self.assertEqual(schema.table("t").qualified, "staging.t")

    def test_INT_별칭을_INTEGER로_읽는다(self):
        """PostgreSQL INT는 INTEGER의 별칭이므로 데이터 사전에 INTEGER로 남겨야 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "V1__init.sql").write_text(
                "CREATE TABLE t (id INT PRIMARY KEY);", encoding="utf-8")
            schema = flyway.load(directory)

        self.assertEqual(schema.table("t").columns["id"].data_type, "INTEGER")

    def test_sql_로_시드되는_테이블을_기록한다(self):
        self.assertEqual(self.schema.seeded_tables, {"industry", "metric"})


if __name__ == "__main__":
    unittest.main()
