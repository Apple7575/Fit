"""같은 버전의 마이그레이션이 둘이면 파서가 멈추는지 본다.

Flyway 는 버전이 겹치면 마이그레이션을 아예 시작하지 않는다. 우리 파서가 둘 다
적용해 스키마를 만들면 **실제로는 뜨지도 못할 DB 를 기준으로 검증이 통과한다.**

2026-09-22 에 실제로 났다 — develop 이 `V34` 를 임베딩 float16 에 내주는 사이
MR !209 가 같은 번호로 `news_article` 을 고치고 있었는데, 검증 어디에서도
걸리지 않았다.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATA))

from pipeline.news import flyway  # noqa: E402

MIGRATION_DIR = DATA.parent / "backend/src/main/resources/db/migration"


def copied_migrations():
    tmp = tempfile.TemporaryDirectory()
    target = Path(tmp.name) / "migration"
    shutil.copytree(MIGRATION_DIR, target)
    return target, tmp


class DuplicateVersionTest(unittest.TestCase):
    def test_지금_저장소는_겹치는_번호가_없다(self):
        versions = [flyway._version_of(p) for p in MIGRATION_DIR.glob("V*__*.sql")]
        self.assertEqual(len(versions), len(set(versions)),
                         "저장소 안에서 이미 번호가 겹쳤다")

    def test_번호가_겹치면_멈춘다(self):
        target, tmp = copied_migrations()
        self.addCleanup(tmp.cleanup)
        existing = max(flyway._version_of(p) for p in target.glob("V*__*.sql"))
        (target / f"V{existing}__another_branch_took_this_number.sql").write_text(
            "ALTER TABLE news_article ADD COLUMN spurious VARCHAR(10);", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            flyway.load(target)
        message = str(caught.exception)
        self.assertIn("같은 버전", message)
        self.assertIn(f"V{existing}", message)
        # 어느 파일들이 겹쳤는지 알려 줘야 고칠 수 있다.
        self.assertIn("another_branch_took_this_number", message)

    def test_겹치지_않으면_그대로_읽는다(self):
        target, tmp = copied_migrations()
        self.addCleanup(tmp.cleanup)
        free = max(flyway._version_of(p) for p in target.glob("V*__*.sql")) + 1
        (target / f"V{free}__news_article_note.sql").write_text(
            "ALTER TABLE news_article ADD COLUMN note VARCHAR(10);", encoding="utf-8")
        schema = flyway.load(target)
        self.assertIn("note", schema.table("news_article").columns)

    def test_폴더가_비면_예전처럼_FileNotFound(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with self.assertRaises(FileNotFoundError):
            flyway.load(Path(tmp.name))


if __name__ == "__main__":
    unittest.main()
