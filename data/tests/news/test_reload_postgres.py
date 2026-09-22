"""실제 PostgreSQL 에 두 번 적재해도 같은지 본다 (백엔드 2026-09-22 요청).

**DB 가 필요하다.** `CA_TEST_DATABASE_URL` 이 없으면 통째로 건너뛴다. 임시 DB 로
돌리는 법은 `data/docs/S15P21A504-NEWS-ERD-reply.md` 6장에 적어 두었다.

왜 이것이 필요한가
------------------
뉴스 ERD 마이그레이션이 들어오면 중복 방지 키가 **부분 UNIQUE 인덱스**가 된다.
PostgreSQL 은 부분 인덱스를 `ON CONFLICT` 의 중재자로 쓰려면 conflict_target 에
같은 WHERE 조건을 요구한다. 조건을 빼면 컬럼이 정확히 같아도 이렇게 죽는다.

    there is no unique or exclusion constraint matching the ON CONFLICT specification

파서가 인덱스의 WHERE 를 버리면 적재기는 그 조건을 붙일 수 없다. 스키마만 읽는
시험으로는 이 조합을 잡지 못해서 — 문법이 아니라 **PostgreSQL 의 중재자 추론**이
문제이기 때문에 — 진짜 DB 에 넣어 본다.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from pipeline import db  # noqa: E402
from pipeline.news import flyway  # noqa: E402

import load_seed_csv as loader  # noqa: E402

DATABASE_URL = os.getenv("CA_TEST_DATABASE_URL", "").strip()

BEFORE_SQL = """
CREATE TABLE {t} (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code VARCHAR(8) NOT NULL,
    title VARCHAR(500) NOT NULL,
    guid VARCHAR(500),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT {t}_guid_uk UNIQUE (corp_code, guid)
);
"""

AFTER_SQL = """
ALTER TABLE {t} ADD COLUMN provider VARCHAR(50);
ALTER TABLE {t} ADD COLUMN provider_article_id VARCHAR(500);
ALTER TABLE {t} ADD COLUMN normalized_url VARCHAR(1000);
UPDATE {t} SET provider_article_id = guid WHERE guid IS NOT NULL;
UPDATE {t} SET provider = 'google_news_rss' WHERE provider IS NULL;
ALTER TABLE {t} DROP CONSTRAINT {t}_guid_uk;
CREATE UNIQUE INDEX {t}_provider_article_uk
    ON {t} (corp_code, provider, provider_article_id)
    WHERE provider_article_id IS NOT NULL;
ALTER TABLE {t} DROP COLUMN guid;
"""


@unittest.skipUnless(DATABASE_URL, "CA_TEST_DATABASE_URL 이 없어 건너뛴다")
class ReloadTest(unittest.TestCase):
    """마이그레이션 뒤에도 재적재가 멱등인지 본다."""

    def setUp(self):
        self.table = f"news_reload_{uuid.uuid4().hex[:8]}"
        self.addCleanup(self._drop)

    def _drop(self):
        with db.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {self.table}")

    def _rows(self, title: str):
        return [{"corp_code": "00000001", "title": title,
                 "provider": "google_news_rss", "provider_article_id": "g-aaa"},
                {"corp_code": "00000001", "title": title + "2",
                 "provider": "google_news_rss", "provider_article_id": "g-bbb"}]

    def _predicate(self):
        """마이그레이션 뒤 스키마에서 읽는 것과 같은 조건문."""
        return "provider_article_id IS NOT NULL"

    def test_부분_인덱스에_조건_없이_넣으면_죽는다(self):
        """조건을 빼면 어떻게 되는지 고정해 둔다 — 이것이 회귀의 모양이다."""
        with db.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(BEFORE_SQL.format(t=self.table))
                cur.execute(AFTER_SQL.format(t=self.table))
            with self.assertRaises(Exception) as caught:
                db.upsert(conn, self.table, self._rows("첫"),
                          pk=("corp_code", "provider", "provider_article_id"))
            self.assertIn("ON CONFLICT", str(caught.exception))

    def test_조건을_붙이면_두_번_넣어도_같다(self):
        with db.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(BEFORE_SQL.format(t=self.table))
                cur.execute(AFTER_SQL.format(t=self.table))

            key = ("corp_code", "provider", "provider_article_id")
            first = db.upsert(conn, self.table, self._rows("첫"), pk=key,
                              conflict_where=self._predicate())
            second = db.upsert(conn, self.table, self._rows("둘째"), pk=key,
                               conflict_where=self._predicate())

            self.assertEqual(first.inserted, 2)
            self.assertEqual(second.inserted, 0, "두 번째는 전부 갱신이어야 한다")
            self.assertEqual(second.updated, 2)

            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {self.table}")
                self.assertEqual(cur.fetchone()[0], 2, "행이 늘면 멱등이 아니다")
                cur.execute(f"SELECT title FROM {self.table} ORDER BY title")
                self.assertEqual([r[0] for r in cur.fetchall()], ["둘째", "둘째2"])

    def test_마이그레이션_전_스키마에서는_조건_없이_돈다(self):
        """전환 전에는 일반 UNIQUE 제약이라 조건이 없어야 한다."""
        with db.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(BEFORE_SQL.format(t=self.table))
            rows = [{"corp_code": "00000001", "title": "첫", "guid": "g-aaa"}]
            db.upsert(conn, self.table, rows, pk=("corp_code", "guid"))
            again = db.upsert(conn, self.table, rows, pk=("corp_code", "guid"))
            self.assertEqual(again.inserted, 0)
            self.assertEqual(again.updated, 1)


@unittest.skipUnless(DATABASE_URL, "CA_TEST_DATABASE_URL 이 없어 건너뛴다")
class PredicateFromSchemaTest(unittest.TestCase):
    """조건문은 사람이 적지 않고 **스키마에서 읽는다.**"""

    def test_적재기가_스키마에서_같은_조건을_읽어_온다(self):
        import shutil
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "migration"
        shutil.copytree(DATA.parent / "backend/src/main/resources/db/migration", target)
        nxt = max(int(p.name[1:p.name.index("__")])
                  for p in target.glob("V*__*.sql")) + 1
        (target / f"V{nxt}__news_erd.sql").write_text("""
ALTER TABLE news_article ADD COLUMN provider VARCHAR(50);
ALTER TABLE news_article ADD COLUMN provider_article_id VARCHAR(500);
ALTER TABLE news_article DROP CONSTRAINT news_article_guid_uk;
CREATE UNIQUE INDEX news_article_provider_article_uk
    ON news_article (corp_code, provider, provider_article_id)
    WHERE provider_article_id IS NOT NULL;
ALTER TABLE news_article DROP COLUMN source;
ALTER TABLE news_article DROP COLUMN guid;
""", encoding="utf-8")

        schema = flyway.load(target)
        key = loader.natural_key("news_article", schema)
        self.assertEqual(key, ("corp_code", "provider", "provider_article_id"))
        self.assertEqual(loader.conflict_predicate("news_article", key, schema),
                         "provider_article_id IS NOT NULL")


if __name__ == "__main__":
    unittest.main()
