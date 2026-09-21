"""시드에서 **빠진 기업**의 행을 적재가 정리하는지 본다.

지금까지 정리는 "시드에 든 기업" 안에서만 했다. 그래서 파싱이 표를 버리거나
유니버스가 줄어 **시드에서 빠진 기업**의 옛 행은 DB 에 남았다. 2026-09-21 하루에만
세 번 나왔고(아침 dev 24행 · 저녁 dev·prod 각 131행) 그때마다 사람이 찾아 지웠다.

DB 없이 판단만 시험한다 — `prune_plan` 을 순수 함수로 떼어 둔 이유다.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

import load_seed_csv as loader  # noqa: E402


class PrunePlanTest(unittest.TestCase):
    def test_시드에_없는_기업을_고른다(self):
        db = {"A": 10, "B": 5, "C": 3}
        victims, doomed, ratio, over = loader.prune_plan(
            "company_activity", db, {"A", "B"})
        self.assertEqual(victims, ["C"])
        self.assertEqual(doomed, 3)
        self.assertAlmostEqual(ratio, 3 / 18)

    def test_시드가_유일_생산자가_아닌_표는_손대지_않는다(self):
        """company_metric 의 rd_ratio 는 다른 경로가 넣는다 — 시드 밖 행이 정상이다."""
        db = {"A": 10, "C": 3}
        self.assertEqual(loader.prune_plan("company_metric", db, {"A"}),
                         ([], 0, 0.0, False))

    def test_뉴스는_뺀다(self):
        """시드가 기업 100곳으로 좁다. 실험용 시드를 잘못 적재하면 나머지가 날아간다."""
        self.assertEqual(loader.prune_plan("news_article", {"A": 5}, set())[0], [])

    def test_허용선을_넘으면_알린다(self):
        """좁은 시드를 잘못 적재하는 사고를 막는 자리다."""
        db = {"A": 10, "B": 90}
        *_, over = loader.prune_plan("company_text", db, {"A"})
        self.assertTrue(over)

    def test_허용선_안쪽이면_그냥_지운다(self):
        db = {f"c{i}": 10 for i in range(100)}
        db["gone"] = 3
        *_, over = loader.prune_plan("segment_metric", db, {f"c{i}" for i in range(100)})
        self.assertFalse(over)

    def test_지울_것이_없으면_비율은_0_이다(self):
        db = {"A": 10}
        self.assertEqual(loader.prune_plan("company_text", db, {"A"}),
                         ([], 0, 0.0, False))

    def test_빈_DB_에서_0으로_나누지_않는다(self):
        self.assertEqual(loader.prune_plan("company_text", {}, {"A"}),
                         ([], 0, 0.0, False))

    def test_오늘_실제_사고와_같은_규모는_통과한다(self):
        """저녁 운영 적재: company_activity 442곳 8,334행 중 18곳 96행이 시드 밖이었다."""
        db = {f"c{i}": 19 for i in range(424)}
        db.update({f"x{i}": 5 for i in range(18)})
        victims, doomed, ratio, over = loader.prune_plan(
            "company_activity", db, {f"c{i}" for i in range(424)})
        self.assertEqual(len(victims), 18)
        self.assertFalse(over, f"{ratio:.1%} 는 허용선 안이어야 한다")


class OwnershipTest(unittest.TestCase):
    def test_소유_표_목록이_적재_대상_안에_있다(self):
        for table in loader.SEED_OWNS_ALL:
            self.assertIn(table, loader.TABLES, table)

    def test_company_metric_은_빠져_있다(self):
        self.assertNotIn("company_metric", loader.SEED_OWNS_ALL)


if __name__ == "__main__":
    unittest.main()
