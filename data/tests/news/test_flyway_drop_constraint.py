"""키가 **사라지는** 문장을 파서가 읽는지 본다.

`ALTER TABLE ... DROP CONSTRAINT` 는 `ALTER TABLE` 통짜 무시에 걸려 있었다. 그래서
없어진 유일키가 살아 있는 것으로 보였고, **적재기가 그 키로 `ON CONFLICT` 를 걸어
PostgreSQL 이 거부하는데 사전 검사는 초록**이었다 (2026-09-22 실측).

1차/후속으로 쪼개는 마이그레이션에서 바로 걸리는 자리다 — 1차가 `guid` 제약만
지우고 컬럼은 남기면, 적재기는 컬럼이 있으니 `(corp_code, guid)` 를 고르고 그
제약은 이미 없다.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from pipeline.news import flyway  # noqa: E402

import load_seed_csv as loader  # noqa: E402

MIGRATION_DIR = DATA.parent / "backend/src/main/resources/db/migration"


def schema_with(sql: str):
    """실제 마이그레이션 폴더에 문장을 얹어 읽는다."""
    tmp = tempfile.TemporaryDirectory()
    target = Path(tmp.name) / "migration"
    shutil.copytree(MIGRATION_DIR, target)
    nxt = max(flyway._version_of(p) for p in target.glob("V*__*.sql")) + 1
    (target / f"V{nxt}__probe.sql").write_text(sql, encoding="utf-8")
    return flyway.load(target), tmp


class DropConstraintTest(unittest.TestCase):
    def test_유일키_제약을_지우면_키가_사라진다(self):
        schema, tmp = schema_with(
            "ALTER TABLE news_article DROP CONSTRAINT news_article_guid_uk;")
        self.addCleanup(tmp.cleanup)
        table = schema.table("news_article")
        self.assertNotIn(["corp_code", "guid"], table.key_groups())
        # 컬럼 자체는 남아 있다 — 이것이 함정의 모양이다.
        self.assertIn("guid", table.columns)

    def test_IF_EXISTS_도_읽는다(self):
        schema, tmp = schema_with(
            "ALTER TABLE news_article DROP CONSTRAINT IF EXISTS news_article_guid_uk;")
        self.addCleanup(tmp.cleanup)
        self.assertNotIn(["corp_code", "guid"],
                         schema.table("news_article").key_groups())

    def test_모르는_이름은_조용히_넘어간다(self):
        """CHECK·FK 는 키로 모으지 않아 이름을 모른다. 예외가 되면 안 된다."""
        schema, tmp = schema_with(
            "ALTER TABLE news_article "
            "DROP CONSTRAINT news_article_importance_score_check;")
        self.addCleanup(tmp.cleanup)
        self.assertIn(["corp_code", "guid"],
                      schema.table("news_article").key_groups())

    def test_부분_인덱스를_지우면_키가_사라진다(self):
        schema, tmp = schema_with("""
ALTER TABLE news_article ADD COLUMN provider VARCHAR(50);
ALTER TABLE news_article ADD COLUMN provider_article_id VARCHAR(500);
CREATE UNIQUE INDEX news_article_provider_article_uk
    ON news_article (corp_code, provider, provider_article_id)
    WHERE provider_article_id IS NOT NULL;
DROP INDEX news_article_provider_article_uk;
""")
        self.addCleanup(tmp.cleanup)
        groups = schema.table("news_article").key_groups()
        self.assertNotIn(["corp_code", "provider", "provider_article_id"], groups)
        self.assertIn(["corp_code", "guid"], groups, "다른 키까지 지우면 안 된다")

    def test_지우지_않은_키는_남는다(self):
        schema, tmp = schema_with(
            "ALTER TABLE company_metric DROP CONSTRAINT IF EXISTS 없는_이름;")
        self.addCleanup(tmp.cleanup)
        self.assertIn(["corp_code", "fiscal_year", "metric_code"],
                      schema.table("company_metric").key_groups())


class LoaderSeesItTest(unittest.TestCase):
    """이 함정이 실제로 막히는지 — 적재기 관점에서 본다."""

    def test_제약만_지운_1차_마이그레이션을_사전_검사가_잡는다(self):
        schema, tmp = schema_with("""
ALTER TABLE news_article ADD COLUMN provider VARCHAR(50);
ALTER TABLE news_article ADD COLUMN provider_article_id VARCHAR(500);
ALTER TABLE news_article DROP CONSTRAINT news_article_guid_uk;
CREATE UNIQUE INDEX news_article_provider_article_uk
    ON news_article (corp_code, provider, provider_article_id)
    WHERE provider_article_id IS NOT NULL;
""")
        self.addCleanup(tmp.cleanup)
        # guid 컬럼이 남아 있어 적재기는 여전히 그 키를 고른다.
        key = loader.natural_key("news_article", schema)
        self.assertEqual(key, ("corp_code", "guid"))
        # 예전에는 여기가 None(통과)이었다. 이제 무엇이 어긋났는지 말해 준다.
        message = loader._check_keys("news_article", key, schema)
        self.assertIsNotNone(message, "없어진 키로 적재하려는 것을 잡아야 한다")
        self.assertIn("자연키가 스키마와 다르다", message)


if __name__ == "__main__":
    unittest.main()
