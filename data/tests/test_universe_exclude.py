"""기업인수목적회사(스팩)를 모집단에서 빼는 규칙을 고정한다.

유니버스를 읽는 자리가 넷이다 — `load_universe` · 시드 빌더 · 뉴스 매핑
(`corpmap`) · 뉴스 수집 드라이버(`collect_news.company_names`). **한 곳만 고치면
나머지로 샌다.** 특히 수집과 매핑이 어긋나면 기사를 받아 놓고 붙일 기업이 없어
staged 에서 통째로 버려진다.

근거는 `pipeline/universe.py` 주석에 있다 (매출 0 · 직원 1~2명 · 산업 평균 15배 왜곡).
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from pipeline.news import corpmap  # noqa: E402
from pipeline.universe import is_excluded, load_universe  # noqa: E402

COLUMNS = ["corp_code", "corp_name", "stock_code", "dart_corp_name",
           "corp_cls", "induty_code", "ksic_division", "status", "division_name"]

ROWS = [
    ("00000001", "삼성전자", "005930", "삼성전자", "Y", "26410"),
    ("00000002", "교보15호스팩", "465320", "교보15호스팩", "K", "66199"),
    ("00000003", "신한제12호스팩", "482520", "신한제12호스팩", "K", "66199"),
    ("00000004", "하나31호스팩", "489210", "하나31호스팩", "K", "66199"),
    ("00000005", "비상장회사", "", "비상장회사", "E", "26410"),
]


def universe_csv(tmp: Path) -> Path:
    path = tmp / "company_universe.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for code, name, stock, dart, cls, induty in ROWS:
            w.writerow([code, name, stock, dart, cls, induty, "26", "000", "업종"])
    return path


class RuleTest(unittest.TestCase):
    def test_스팩_이름을_잡는다(self):
        for name in ("교보15호스팩", "신한제12호스팩", "SK증권제11호스팩",
                     "키움히어로제1호스팩", "IBKS제24호스팩"):
            self.assertTrue(is_excluded(name), name)

    def test_사업하는_회사는_잡지_않는다(self):
        """실제 유니버스에 있는 이름들이다. 오탐이 나면 기업이 통째로 사라진다."""
        for name in ("삼성전자", "동국홀딩스", "효성", "HDC", "다올투자증권",
                     "아주IB투자", "우리기술투자", "해성산업"):
            self.assertFalse(is_excluded(name), name)

    def test_빈_이름도_안전하다(self):
        self.assertFalse(is_excluded(""))
        self.assertFalse(is_excluded(None))


class LoadUniverseTest(unittest.TestCase):
    def test_모집단에서_빠진다(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = load_universe(universe_csv(Path(tmp)))
            names = [c.corp_name for c in got]
            self.assertEqual(names, ["삼성전자"], "스팩 셋과 E 하나가 빠져야 한다")


class CorpMapTest(unittest.TestCase):
    """수집 드라이버와 **같은 규칙**이어야 한다."""

    def test_스팩은_색인에_없다(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapper = corpmap.load(universe_csv(Path(tmp)))
            self.assertEqual(mapper.resolve("교보15호스팩").corp_code, "")
            self.assertEqual(mapper.resolve("교보15호스팩").reason,
                             "not_in_company_universe")

    def test_사업하는_회사는_그대로_붙는다(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapper = corpmap.load(universe_csv(Path(tmp)))
            self.assertEqual(mapper.resolve("삼성전자").corp_code, "00000001")


class CollectDriverTest(unittest.TestCase):
    def test_검색어에서_빠진다(self):
        import collect_news

        with tempfile.TemporaryDirectory() as tmp:
            names = collect_news.company_names(universe_csv(Path(tmp)), aliases=False)
            self.assertEqual(names, ["삼성전자"])

    def test_매핑과_수집이_같은_집합을_본다(self):
        """어긋나면 기사를 받아 놓고 붙일 기업이 없어 버려진다."""
        import collect_news

        with tempfile.TemporaryDirectory() as tmp:
            path = universe_csv(Path(tmp))
            names = collect_news.company_names(path, aliases=False)
            mapper = corpmap.load(path)
            for name in names:
                self.assertNotEqual(mapper.resolve(name).corp_code, "",
                                    f"{name} 을 수집하는데 붙일 기업이 없다")


if __name__ == "__main__":
    unittest.main()
