"""시드 행수가 직전보다 급감하면 생성이 멈추는지 본다.

검증은 시드에 *들어간* 행만 봐서 **사라진 값을 못 잡는다** — 부문매출이 24%
사라져도 "5/7 통과" 가 나왔다 (docs/S15P21A504-SEGMENT-TABLE-REGRESSION.md).
그 자리를 메우는 것이 `pipeline/seed_guard.py` 이고, 여기서 동작을 고정한다.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

from pipeline import seed_guard  # noqa: E402


def rows_of(**kinds: int) -> list[dict]:
    """metric_code 별 행수만 맞춘 segment_metric 모양의 가짜 행."""
    out = []
    for code, n in kinds.items():
        out.extend({"corp_code": f"{i:08d}", "metric_code": code} for i in range(n))
    return out


class SeedGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def baseline(self, table: str, seed_rows: int, **breakdown: int) -> None:
        body: dict = {"table": table, "seed_rows": seed_rows}
        if breakdown:
            body["row_breakdown"] = breakdown
        (self.dir / f"{table}.json").write_text(
            json.dumps(body, ensure_ascii=False), encoding="utf-8")

    def check(self, rows: list[dict], table: str = "segment_metric", **kw):
        seed_guard.check(table, rows, manifest_dir=self.dir,
                         fields=["corp_code", "metric_code"], **kw)

    def test_갈래가_줄면_전체_행수가_같아도_멈춘다(self):
        """이것이 실제로 놓쳤던 모양이다 — 부문매출이 빠진 만큼 다른 갈래가
        늘면 표 전체 행수로는 드러나지 않는다."""
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        with self.assertRaises(SystemExit) as e:
            self.check(rows_of(segment_revenue=20621, segment_employee_count=27195))
        self.assertIn("segment_metric", str(e.exception))

    def test_표_전체가_급감해도_멈춘다(self):
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        with self.assertRaises(SystemExit):
            self.check(rows_of(segment_revenue=20621, segment_employee_count=20804))

    def test_허용선_안쪽이면_지나간다(self):
        """줄어드는 것이 늘 오류는 아니다 — 합계 행을 걷어내면 조금씩 준다."""
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        self.check(rows_of(segment_revenue=26800, segment_employee_count=20804))

    def test_늘면_지나간다(self):
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        self.check(rows_of(segment_revenue=30000, segment_employee_count=20804))

    def test_allow_shrink_면_지나간다(self):
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        self.check(rows_of(segment_revenue=20621, segment_employee_count=20804),
                   allow_shrink=True)

    def test_허용선을_바꿀_수_있다(self):
        self.baseline("segment_metric", 47816,
                      segment_revenue=27012, segment_employee_count=20804)
        self.check(rows_of(segment_revenue=26000, segment_employee_count=20804),
                   max_drop=0.5)

    def test_직전_계보가_없으면_지나간다(self):
        self.check(rows_of(segment_revenue=1))

    def test_작은_무리는_보지_않는다(self):
        """몇 행짜리 갈래는 정상 변동에도 비율이 크게 흔들린다."""
        self.baseline("segment_metric", 1040,
                      segment_revenue=40, segment_employee_count=1000)
        self.check(rows_of(segment_revenue=10, segment_employee_count=1000))

    def test_갈래가_통째로_사라지면_멈춘다(self):
        self.baseline("company_text", 98848, main_product=61211, main_business=2953)
        rows = [{"corp_code": "00000001", "attr_key": "main_product"}] * 61211
        with self.assertRaises(SystemExit):
            seed_guard.check("company_text", rows, manifest_dir=self.dir,
                             fields=["corp_code", "attr_key"])

    def test_뉴스는_갈래_칸이_없어_전체와_기업수로_본다(self):
        """뉴스 시드는 증분 수집이라 staged 가 일부만 있으면 조용히 작아진다."""
        (self.dir / "news_article.json").write_text(
            json.dumps({"table": "news_article", "seed_rows": 500,
                        "distinct_corp_codes": 100}), encoding="utf-8")
        rows = [{"corp_code": f"{i % 100:08d}"} for i in range(500)]
        seed_guard.check("news_article", rows, manifest_dir=self.dir)  # 그대로면 통과
        with self.assertRaises(SystemExit):
            seed_guard.check("news_article", rows[:300], manifest_dir=self.dir)

    def test_기업_수가_줄면_행수가_같아도_멈춘다(self):
        (self.dir / "news_article.json").write_text(
            json.dumps({"table": "news_article", "seed_rows": 500,
                        "distinct_corp_codes": 100}), encoding="utf-8")
        rows = [{"corp_code": f"{i % 50:08d}"} for i in range(500)]
        with self.assertRaises(SystemExit):
            seed_guard.check("news_article", rows, manifest_dir=self.dir)

    def test_계보에_갈래별_행수가_남는다(self):
        self.assertEqual(
            seed_guard.breakdown("segment_metric", rows_of(segment_revenue=2, x=1)),
            {"segment_revenue": 2, "x": 1})
        self.assertEqual(seed_guard.breakdown("company", [{"corp_code": "1"}]), {})


if __name__ == "__main__":
    unittest.main()
