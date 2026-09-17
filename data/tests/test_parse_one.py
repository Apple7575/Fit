"""`parse_one` 이 파일과 바이트에서 같은 결과를 내는지 (S15P21A504-73 0차).

0차 실험의 전제가 이것이다 — 로컬 실행기는 파일 경로를 넘기고 Spark 태스크는
WebHDFS 로 받은 바이트를 넘기는데, **둘이 같은 값을 내야** "인프라를 바꿔도 결과가
같다" 를 확인할 수 있다. 클러스터 없이 여기서 못 박아 둔다.

원문이 있어야 도는 테스트다. `.cache/document_*.xml` 이 없으면 건너뛴다 —
CI 에는 2.95GB 원문이 없다.

    python -m unittest tests.test_parse_one -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.business_report import extract as ex  # noqa: E402
from pipeline.paths import cache_dir  # noqa: E402

# 표 모양이 서로 다른 것으로 고른다. 전부 같은 포맷이면 통과해도 의미가 약하다.
#   삼성전자 2024   부문표 + 시설투자표 + 제품표가 모두 있다
#   SK하이닉스 2024 단일 부문 · 단위가 십억원
#   크래프톤 2024   부문을 지역으로 쪼갠 표 · 8,189행 병합 표가 섞여 있다
SAMPLES = [
    ("00126380", 2024, "20250311001085"),
    ("00164779", 2024, "20250319000665"),
    ("00760971", 2024, "20250318001121"),
]


def _doc(rcept_no: str) -> Path | None:
    p = cache_dir() / f"document_{rcept_no}.xml"
    return p if p.exists() else None


class ParseOneTest(unittest.TestCase):

    def _run_both(self, corp, year, rcept):
        path = _doc(rcept)
        if path is None:
            self.skipTest(f"원문 없음: document_{rcept}.xml")
        from_path = ex.parse_one(path, corp_code=corp, fiscal_year=year,
                                 rcept_no=rcept)
        from_bytes = ex.parse_one(path.read_bytes(), corp_code=corp,
                                  fiscal_year=year, rcept_no=rcept,
                                  size_bytes=path.stat().st_size)
        return from_path, from_bytes

    def test_파일과_바이트가_같은_결과를_낸다(self):
        for corp, year, rcept in SAMPLES:
            with self.subTest(corp=corp, year=year):
                a, b = self._run_both(corp, year, rcept)
                self.assertEqual(a.segments, b.segments, "부문별 매출이 다르다")
                self.assertEqual(a.facilities, b.facilities, "시설투자가 다르다")
                self.assertEqual(a.products, b.products, "주요 제품이 다르다")
                self.assertEqual(a.rnd, b.rnd, "R&D 가 다르다")
                self.assertEqual(a.passages, b.passages, "LLM 구간이 다르다")

    def test_요약도_같다_시간만_빼고(self):
        """seconds 는 실행마다 다르다. 나머지는 같아야 한다."""
        for corp, year, rcept in SAMPLES:
            with self.subTest(corp=corp, year=year):
                a, b = self._run_both(corp, year, rcept)
                sa = {k: v for k, v in a.summary.items() if k != "seconds"}
                sb = {k: v for k, v in b.summary.items() if k != "seconds"}
                self.assertEqual(sa, sb)

    def test_파손된_입력이_예외를_던지지_않는다(self):
        """11,395건을 도는 중에 한 건이 터져서 잡 전체가 죽으면 안 된다.

        Spark 에서는 더 나쁘다 — 태스크 실패가 재시도를 부르는데 파손된 문서는
        몇 번 다시 해도 파손이다.
        """
        r = ex.parse_one(b"<<< not xml at all", corp_code="00000000",
                         fiscal_year=2024, rcept_no="00000000000000")
        self.assertTrue(r.failed)
        self.assertTrue(r.summary["error"])
        self.assertEqual(r.segments, [])
        self.assertIsNone(r.rnd)

    def test_헤더_상수가_실제_행의_키와_맞는다(self):
        """부르는 쪽이 이 상수로 CSV·Parquet 를 쓴다. 어긋나면 열이 빈다."""
        corp, year, rcept = SAMPLES[0]
        if _doc(rcept) is None:
            self.skipTest("원문 없음")
        r = ex.parse_one(_doc(rcept), corp_code=corp, fiscal_year=year,
                         rcept_no=rcept)
        for rows, fields, name in (
                (r.segments, ex.SEGMENT_FIELDS, "segment"),
                (r.facilities, ex.FACILITY_FIELDS, "facility"),
                (r.products, ex.PRODUCT_FIELDS, "product")):
            for row in rows:
                self.assertEqual(set(row), set(fields), f"{name} 키가 헤더와 다르다")
        if r.rnd:
            self.assertEqual(set(r.rnd), set(ex.RND_FIELDS))
        self.assertLessEqual(set(r.summary), set(ex.SUMMARY_FIELDS))


if __name__ == "__main__":
    unittest.main()
