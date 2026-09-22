"""부문 매출표에서 **소계 행을 명세 행과 함께 더하지 않는지** 본다.

소계 표시가 첫 라벨에 오면 예전 규칙(`exclude_row`)이 걸러냈다. 그런데 표가
`제품 | 승용 | 합계` 처럼 **안쪽 열**에 소계를 두면 걸리지 않아 명세 행과 소계 행이
함께 더해졌다 — 기아 2022(20230309000734) 는 그래서 제품 매출이 정확히 두 배
(39,853,489 → 79,706,978)가 됐다.

옛 격자에서는 ROWSPAN 이 마지막 행을 못 덮어 셀이 왼쪽으로 밀렸고, 그 바람에
`제품 외 기타` 의 소계 행 이름이 우연히 `합계` 가 되어 걸러졌다. 그래서 합이
DART 연결 매출과 0.34% 로 맞아 `verified` 가 찍혔다 — **맞은 것이 아니라 두 오류가
상쇄된 것이다.** 격자가 고쳐지자 상쇄가 풀려 값이 드러났다.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))

from pipeline.business_report import segments as S  # noqa: E402
from pipeline.business_report.doc import Table  # noqa: E402
from pipeline.patterns import patterns  # noqa: E402

P = patterns()


def table(rows: list[list[str]]) -> Table:
    return Table(idx=0, title="부문별 매출", caption="", m=rows)


class SubtotalTest(unittest.TestCase):
    """기아 2022 표 68 과 같은 모양 — 매출유형 | 품목 | 내수·수출·합계."""

    KIA = [
        ["매출 유형", "품목", "품목", "제79기", "제78기"],
        ["제품", "승용", "내수", "4,301,591", "4,889,833"],
        ["제품", "승용", "수출", "3,520,788", "3,439,935"],
        ["제품", "승용", "합계", "7,822,379", "8,329,768"],
        ["제품", "기타", "내수", "7,157", "8,268"],
        ["제품 외 기타", "제품 외 기타", "내수", "781,130", "682,334"],
        ["제품 외 기타", "제품 외 기타", "수출", "5,767,945", "5,992,228"],
        ["제품 외 기타", "제품 외 기타", "합계", "6,549,075", "6,674,562"],
        ["합계", "합계", "합계", "14,378,611", "14,012,598"],
    ]

    def segments(self, rows):
        segs, _ = S._from_table(None, table(rows), P)
        return {s.name: s.amount_raw for s in segs}

    def test_안쪽_열의_소계는_더하지_않는다(self):
        got = self.segments(self.KIA)
        self.assertEqual(got["제품"], 4_301_591 + 3_520_788 + 7_157)
        self.assertEqual(got["제품 외 기타"], 781_130 + 5_767_945)

    def test_부문_합이_표의_합계_행과_같다(self):
        got = self.segments(self.KIA)
        self.assertEqual(sum(got.values()), 14_378_611,
                         "명세 행만 더하면 표가 스스로 적은 합계와 맞아야 한다")

    def test_맨_앞_열의_합계_행은_예전처럼_빠진다(self):
        """이름이 '합계' 인 행은 원래도 걸렀다. 그 동작이 그대로인지 본다."""
        self.assertNotIn("합계", self.segments(self.KIA))

    def test_소계가_없는_표는_그대로다(self):
        rows = [
            ["부문", "매출액"],
            ["반도체", "1,000"],
            ["디스플레이", "2,000"],
        ]
        self.assertEqual(self.segments(rows), {"반도체": 1000.0, "디스플레이": 2000.0})

    def test_숫자_뒤에_오는_말은_라벨로_보지_않는다(self):
        """라벨은 **첫 숫자 앞까지**다. 뒤에 붙는 비고·단위 칸 때문에 행이 빠지면 안 된다."""
        rows = [
            ["부문", "매출액", "비고"],
            ["반도체", "1,000", "합계"],
        ]
        self.assertEqual(self.segments(rows), {"반도체": 1000.0})


if __name__ == "__main__":
    unittest.main()
