"""'주요 제품' 추출.

리포트 첫 화면과 경쟁사 표에 그대로 실리는 값이다. 잘못 뽑히면 "현대자동차는 금액,
차량부문, 내부매출액을 주요 제품으로 하며…" 같은 문장이 사용자에게 나간다.
"""
from __future__ import annotations

import unittest

from pipeline.business_report.doc import Table
from pipeline.business_report.texts import main_products
from pipeline.patterns import load_patterns


class FakeDocument:
    """main_products 는 문서에서 tables 만 본다. XML 을 만들 필요가 없다."""

    def __init__(self, tables: list[Table]) -> None:
        self.tables = tables


class MainProductsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.patterns = load_patterns()

    def extract(self, matrix: list[list[str]]) -> list[str]:
        table = Table(idx=1, title="2. 주요 제품 및 서비스", caption="", m=matrix)
        return main_products(FakeDocument([table]), self.patterns)[0]

    def test_two_row_header_is_skipped(self):
        """머리글이 두 줄인 표가 있다. 한 줄만 건너뛰면 '금액'·'비중'이 제품으로 들어간다.

        현대자동차 2025년 사업보고서의 실제 모양이다.
        """
        products = self.extract([
            ["주요제품", "주요제품", "구분", "2025년(제58기)", "2025년(제58기)"],
            ["주요제품", "주요제품", "구분", "금액", "비중"],
            ["차량부문", "자동차 등", "매출액", "145,631,818", "78.2"],
            ["기타부문", "부품 등", "매출액", "10,389,879", "5.6"],
        ])

        self.assertEqual(products, ["차량부문", "기타부문"])
        self.assertNotIn("금액", products)
        self.assertNotIn("비중", products)

    def test_single_row_header_still_works(self):
        products = self.extract([
            ["부문", "주요 제품", "매출액"],
            ["반도체", "DRAM, NAND Flash", "1,000"],
        ])

        self.assertEqual(products, ["DRAM", "NAND Flash"])

    def test_slash_separates_but_keeps_glued_terms(self):
        """슬래시는 대개 나열이지만("제동/조향") 한 낱말인 것도 있다("A/S")."""
        products = self.extract([
            ["부문", "주요 제품", "매출액"],
            ["모듈", "샤시/칵핏모듈", "1,000"],
            ["보수용", "A/S 보수용품", "500"],
        ])

        self.assertIn("샤시", products)
        self.assertIn("칵핏모듈", products)
        self.assertIn("A/S 보수용품", products)
        self.assertNotIn("A", products)

    def test_single_character_fragments_are_dropped(self):
        products = self.extract([
            ["부문", "주요 제품", "매출액"],
            ["기타", "A, TV, B", "100"],
        ])

        self.assertEqual(products, ["TV"])


if __name__ == "__main__":
    unittest.main()
