"""metric 카탈로그 사본이 마이그레이션과 어긋나지 않는지 본다.

`build_curated_seed.py` 의 `METRIC_CATALOG` 는 SQL 의 사본이라 낡는다. 실제로
V17 이 `rd_cost` 를 `rd_expense` 로 옮기고 지표 셋을 더했을 때 목록이 그대로여서,
이미 머지된 시드가 없는 코드를 들고 있었다. `--verify-db` 는 DB 가 최신일 때만
잡아서 놓쳤다 — 그래서 생성 시점에 파일만 보고 대조하는 길을 따로 두었다.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from build_curated_seed import METRIC_CATALOG, _codes_from_flyway  # noqa: E402


class MetricCatalogTest(unittest.TestCase):
    def setUp(self):
        self.migrations = _codes_from_flyway()
        self.catalog = {row[0] for row in METRIC_CATALOG}

    def test_사본이_마이그레이션과_같다(self):
        self.assertEqual(
            self.catalog, self.migrations,
            "METRIC_CATALOG 를 마이그레이션에 맞춰야 한다 — "
            f"마이그레이션에만 {sorted(self.migrations - self.catalog)}, "
            f"카탈로그에만 {sorted(self.catalog - self.migrations)}")

    def test_개명된_옛_코드는_빠진다(self):
        """V4 는 avg_salary·avg_tenure 를, V17 은 rd_cost 를 INSERT…SELECT 로 옮기고
        옛 이름을 DELETE 한다. 넣은 것만 세고 뺀 것을 반영하지 않으면 남는다."""
        for gone in ("rd_cost", "avg_salary", "avg_tenure"):
            self.assertNotIn(gone, self.migrations, gone)
        for kept in ("rd_expense", "average_salary", "average_tenure"):
            self.assertIn(kept, self.migrations, kept)

    def test_V17_이_더한_지표가_들어_있다(self):
        for code in ("total_assets", "regular_employee_count", "contract_employee_count"):
            self.assertIn(code, self.migrations, code)

    def test_카탈로그에_중복된_코드가_없다(self):
        codes = [row[0] for row in METRIC_CATALOG]
        self.assertEqual(len(codes), len(set(codes)))


class ParserTest(unittest.TestCase):
    """파서 자체를 고정 입력으로 본다.

    실제 마이그레이션만 보면 로직이 맞아서 통과하는지, 우연히 통과하는지 가릴 수
    없다. 아래 셋은 처음에 실제로 틀렸던 경우다 (MR !86 리뷰) — `split(";")` 로
    자르고 주석을 지우지 않으면 전부 잘못 읽는다.
    """

    def codes(self, sql: str) -> set[str]:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "V1__test.sql").write_text(sql, encoding="utf-8")
            return _codes_from_flyway(Path(directory))

    def test_주석_속_INSERT_는_세지_않는다(self):
        self.assertEqual(self.codes(
            "-- INSERT INTO metric (metric_code) VALUES ('ghost');\n"
            "INSERT INTO metric (metric_code) VALUES ('real');"), {"real"})

    def test_주석_속_DELETE_는_지우지_않는다(self):
        """제일 위험한 경우다 — 되돌리기 DDL 을 주석에 적어 두는 습관이 있는데,
        그것을 실행된 것으로 세면 멀쩡한 코드가 사라져 가드가 헛되이 멈춘다."""
        self.assertEqual(self.codes(
            "INSERT INTO metric (metric_code) VALUES ('keep');\n"
            "-- 되돌리려면: DELETE FROM metric WHERE metric_code = 'keep';"), {"keep"})

    def test_문자열_안의_세미콜론에서_문장을_자르지_않는다(self):
        self.assertEqual(self.codes(
            "INSERT INTO metric (metric_code, name_ko) VALUES ('a', '가; 나');\n"
            "INSERT INTO metric (metric_code) VALUES ('b');"), {"a", "b"})

    def test_INSERT_SELECT_개명과_DELETE_를_순서대로_반영한다(self):
        self.assertEqual(self.codes(
            "INSERT INTO metric (metric_code) VALUES ('old');\n"
            "INSERT INTO metric (metric_code) SELECT 'new' FROM metric"
            " WHERE metric_code = 'old';\n"
            "DELETE FROM metric WHERE metric_code = 'old';"), {"new"})


if __name__ == "__main__":
    unittest.main()
