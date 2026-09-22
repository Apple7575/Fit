"""스키마가 바뀌는 날에도 시드·적재가 멈추지 않는지 본다.

확정 ERD 대조(MR !209)가 `news_article` 의 `source`·`guid` 를 지우고
`publisher`·`provider`·`provider_article_id` 등을 더한다. 그대로 들어오면 예전
코드에서는 **적재가 통째로 멈췄다** — 자연키 검사가 두 부분 UNIQUE 인덱스를 한
뭉치로 합쳐 읽어 코드의 자연키와 어느 쪽도 맞지 않았다.

여기서는 그 마이그레이션을 임시 폴더에 흉내 내고, 지금 스키마와 바뀐 스키마
**양쪽에서** 같은 코드가 도는지 고정한다. 실제 마이그레이션이 저장소에 들어와도
이 시험은 그대로 통과한다 — **번호가 아니라 컬럼으로 판단하기 때문이다**
(2026-09-22 에 develop 이 V34 를 다른 마이그레이션에 내주면서, 번호로 판단하던
예전 방식은 복사본 폴더에 V34 를 둘 만들고 있었다).
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from pipeline.news import curate, flyway  # noqa: E402
from pipeline.news.schema import SEED_COLUMN_FILL  # noqa: E402
from tests.news.test_curate import staged  # noqa: E402

import load_seed_csv as loader  # noqa: E402

NEWS_ERD_SQL = """
ALTER TABLE news_article ADD COLUMN provider VARCHAR(50);
ALTER TABLE news_article ADD COLUMN provider_url VARCHAR(1000);
ALTER TABLE news_article ADD COLUMN normalized_url VARCHAR(1000);
ALTER TABLE news_article ADD COLUMN body_text TEXT;
ALTER TABLE news_article ADD COLUMN publisher VARCHAR(100);
ALTER TABLE news_article ADD COLUMN provider_article_id VARCHAR(500);
ALTER TABLE news_article DROP CONSTRAINT news_article_guid_uk;
CREATE UNIQUE INDEX news_article_provider_article_uk
ON news_article (corp_code, provider, provider_article_id)
WHERE provider_article_id IS NOT NULL;
CREATE UNIQUE INDEX news_article_normalized_url_uk
ON news_article (corp_code, normalized_url)
WHERE normalized_url IS NOT NULL;
ALTER TABLE news_article
    DROP COLUMN source,
    DROP COLUMN guid;
"""


def schema_with_news_erd():
    """실제 마이그레이션 폴더를 복사하고 뉴스 ERD 마이그레이션을 얹어 읽는다.

    번호는 **비어 있는 다음 번호**를 쓴다. 이름을 박아 두면 그 번호를 남이
    가져갔을 때 같은 버전이 둘인 폴더가 만들어진다.
    """
    tmp = tempfile.TemporaryDirectory()
    target = Path(tmp.name) / "migration"
    shutil.copytree(DATA.parent / "backend/src/main/resources/db/migration", target)
    if "provider_article_id" not in flyway.load(target).table("news_article").columns:
        version = max(int(re.match(r"V(\d+)__", p.name).group(1))
                      for p in target.glob("V*__*.sql")) + 1
        (target / f"V{version}__news_article_provider_columns.sql").write_text(
            NEWS_ERD_SQL, encoding="utf-8")
    return flyway.load(target), tmp


class KeyGroupTest(unittest.TestCase):
    """유일키는 **묶음**으로 읽어야 한다."""

    def test_지금_스키마는_guid_키_하나다(self):
        table = flyway.load().table("news_article")
        self.assertIn(["corp_code", "guid"], table.key_groups())

    def test_뉴스_ERD_뒤에는_유일키가_둘이고_합쳐지지_않는다(self):
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        groups = [g for g in schema.table("news_article").key_groups() if g != ["id"]]
        self.assertIn(["corp_code", "provider", "provider_article_id"], groups)
        self.assertIn(["corp_code", "normalized_url"], groups)

    def test_컬럼이_사라지면_그_컬럼이_낀_키도_사라진다(self):
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        groups = schema.table("news_article").key_groups()
        self.assertNotIn(["corp_code", "guid"], groups)

    def test_복합_기본키도_자연키로_읽는다(self):
        """company_metric 은 UNIQUE 가 아니라 PK 가 자연키다."""
        table = flyway.load().table("company_metric")
        self.assertIn(["corp_code", "fiscal_year", "metric_code"], table.key_groups())


class LoaderKeyTest(unittest.TestCase):
    def test_지금은_guid_키를_고른다(self):
        schema = flyway.load()
        key = loader.natural_key("news_article", schema)
        self.assertEqual(key, ("corp_code", "guid"))
        self.assertIsNone(loader._check_keys("news_article", key, schema))

    def test_뉴스_ERD_뒤에는_제공처_키를_고른다(self):
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        key = loader.natural_key("news_article", schema)
        self.assertEqual(key, ("corp_code", "provider", "provider_article_id"))
        self.assertIsNone(loader._check_keys("news_article", key, schema),
                          "뉴스 ERD 가 들어와도 적재가 멈추면 안 된다")

    def test_엉뚱한_키는_여전히_막는다(self):
        schema = flyway.load()
        message = loader._check_keys("news_article", ("corp_code", "title"), schema)
        self.assertIn("자연키가 스키마와 다르다", message)

    def test_다른_표들도_지금_스키마에서_통과한다(self):
        schema = flyway.load()
        for table in loader.NATURAL_KEY_CANDIDATES:
            key = loader.natural_key(table, schema)
            self.assertIsNone(loader._check_keys(table, key, schema), table)


class SeedShapeTest(unittest.TestCase):
    def test_뉴스_ERD_헤더로_시드가_만들어진다(self):
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        result = curate.build([staged()], schema)
        (row,) = result.rows
        # 밑줄로 시작하는 칸은 집계용이라 CSV 로 나가지 않는다.
        self.assertEqual(result.summary["header"],
                         [c for c in row if not c.startswith("_")])
        self.assertNotIn("guid", row)
        self.assertNotIn("source", row)

    def test_옮겨간_값이_새_자리에_들어간다(self):
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        (row,) = curate.build([staged()], schema).rows
        self.assertEqual(row["publisher"], "테스트일보")       # source 가 담던 값
        self.assertEqual(row["provider_article_id"], "g1")     # guid 가 담던 값
        self.assertEqual(row["provider"], "google_news_rss")
        self.assertEqual(row["provider_url"], "https://news.google.com/x")

    def test_못_채우는_값은_비운다(self):
        """원문 주소를 풀지 못하고(2026-09-21 실측) 본문은 저장 근거가 없다."""
        schema, tmp = schema_with_news_erd()
        self.addCleanup(tmp.cleanup)
        (row,) = curate.build([staged()], schema).rows
        self.assertEqual(row["normalized_url"], "")
        self.assertEqual(row["body_text"], "")
        self.assertEqual(row["importance_score"], "")

    def test_모르는_컬럼이_생기면_시드를_만들지_않는다(self):
        """새 컬럼을 조용히 빈 칸으로 내보내지 않는다."""
        schema = flyway.load()
        table = schema.table("news_article")
        table.columns["mystery_column"] = flyway.Column(
            table="news_article", name="mystery_column",
            ordinal=99, data_type="TEXT", nullable=True)
        with self.assertRaises(ValueError) as error:
            curate.build([staged()], schema)
        self.assertIn("mystery_column", str(error.exception))

    def test_채우는_방법을_한자리에_적어_둔다(self):
        for column in ("publisher", "provider_article_id", "normalized_url", "body_text"):
            self.assertIn(column, SEED_COLUMN_FILL)


if __name__ == "__main__":
    unittest.main()
