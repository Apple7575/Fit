"""시설투자 표의 2단 헤더 아랫단을 데이터로 읽지 않는지 본다.

아랫단을 못 걷어내면 **머리말이 항목이 되고 연도·각주가 금액이 된다.** 억원·
백만원 표에서는 자릿수까지 그럴듯해 F축이 못 잡고 그대로 시드에 들어간다.

여기서 고정하는 것은 판정 규칙 하나다 — 아랫단은 "머리말 어휘가 둘 이상이고,
머리말이 아닌 칸에 금액이 없다" 로 가린다. 각주 표시(`(주1)`)는 금액으로 세지
않는다: `to_num` 이 문자열 어디서든 숫자를 찾으므로 `총소요 자금(주1)` 이 1 로
읽혀 HEM파마 2024 의 아랫단이 데이터로 남았다 (3차 확대에서 실측).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))

from pipeline.business_report.facility import _data_start  # noqa: E402
from pipeline.patterns import patterns  # noqa: E402

FP = patterns().business_report.facility

# HEM파마 2024 사업보고서 표 46. 병합 셀이 펼쳐지지 않아 헤더가 두 행이다.
HEM = [
    ["구분", "설비능력", "총소요 자금(주1)", "기 지출액",
     "지출예정", "지출예정", "지출예정", "지출예정"],
    ["구분", "설비능력", "총소요 자금(주1)", "기 지출액",
     "2024년", "2025년", "2026년", "2026년 이후"],
    ["토지 (주2)", "-", "6,935,726", "4,934,055", "2,001,671", "-", "-", "-"],
    ["건물", "-", "3,301,878", "3,301,878", "-", "-", "-", "-"],
]


class SubheaderTest(unittest.TestCase):
    def test_각주가_붙은_아랫단을_걷어낸다(self):
        """`(주1)` 의 1 을 금액으로 세면 아랫단이 데이터로 남는다."""
        self.assertEqual(_data_start(HEM, 0, FP), 2,
                         "데이터는 '토지' 행부터다")

    def test_금액이_있는_행은_데이터로_남긴다(self):
        """진짜 값이 든 행을 헤더로 지우면 투자액을 잃는다."""
        m = [
            ["구분", "금액", "비고"],
            ["토지", "791", "-"],
        ]
        self.assertEqual(_data_start(m, 0, FP), 1)

    def test_연도만_있는_아랫단은_걷어낸다(self):
        """연도는 금액이 아니다 (하이트진로 2023 의 모양)."""
        m = [
            ["사업부문", "계획명칭", "예상투자총액", "연도별 예상투자액", "비고"],
            ["자산형태", "금액", "2023년", "2024년", "이후"],
            ["토지", "1,200", "300", "400", "500"],
        ]
        self.assertEqual(_data_start(m, 0, FP), 2)

    def test_각주만으로는_행을_지우지_않는다(self):
        """각주가 있어도 **머리말 어휘가 둘 미만**이면 데이터 행이다."""
        m = [
            ["구분", "금액", "비고"],
            ["토지 (주1)", "6,935,726", "-"],
        ]
        self.assertEqual(_data_start(m, 0, FP), 1)


if __name__ == "__main__":
    unittest.main()
