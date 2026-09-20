import unittest

from pipeline.rag_corpus.evaluation_numeric import performance_candidate


class NumericEvaluationTest(unittest.TestCase):
    def _table(self, header, row, *, unit="단위 : 백만원"):
        return {"section_index": 1, "section_title": "재무상태", "kind": "table_row",
                "source_index": "1:2", "text": f"{unit}\n{header}\n{row}",
                "table_header_text": header, "table_unit_text": unit}

    def test_chooses_latest_explicit_year_not_first_column(self):
        candidate = performance_candidate(self._table(
            "구분 | 2023년도 | 2024년도 | 2025년도", "매출액 | 100 | 200 | 300",
        ))
        self.assertEqual(candidate["question"], "2025년 매출액은 얼마인가?")
        self.assertEqual(candidate["answer"], "300백만원")

    def test_rejects_forecast_and_actual_columns_as_ambiguous(self):
        self.assertIsNone(performance_candidate(self._table(
            "계정과목 | 2022년예측 | 2022년 실적 | 차이", "매출액 | 16,483 | 17,250 | 767",
        )))

    def test_rejects_duplicate_year_columns_from_restatement(self):
        self.assertIsNone(performance_candidate(self._table(
            "구분 | 2022년 수정 전 | 2022년 수정 후 | 차이", "영업이익 | 100 | 120 | 20",
        )))

    def test_rejects_segment_value_when_question_does_not_name_segment(self):
        self.assertIsNone(performance_candidate(self._table(
            "구분 | 사업부문 | 2025년 | 2024년", "영업이익 | 식품 및 식품서비스 | 674,987 | 755,481",
        )))

    def test_rejects_quarter_cumulative_as_annual(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "2025년 4분기(누계) 매출액은 100억원입니다."}
        self.assertIsNone(performance_candidate(unit))

    def test_rejects_forecast_deviation_paragraph(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "2025년 매출액은 78,650백만원으로 추정했고 실제 매출액은 23백만원입니다."}
        self.assertIsNone(performance_candidate(unit))

    def test_rejects_named_affiliate_revenue_as_target_company_revenue(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "※ HD현대인프라코어의 2025년 매출액은 45,478억원을 기록하였습니다."}
        self.assertIsNone(performance_candidate(unit))

    def test_rejects_company_marker_in_unrelated_sentence(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "당사는 건설기계를 제조합니다. HD현대인프라코어의 2025년 매출액은 45,478억원입니다."}
        self.assertIsNone(performance_candidate(unit))

    def test_marks_explicit_consolidated_basis_in_question_and_metadata(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "당사 연결재무기준 2025년 매출액은 100억원입니다."}
        candidate = performance_candidate(unit)
        self.assertEqual(candidate["question"], "2025년 연결 기준 매출액은 얼마인가?")
        self.assertEqual(candidate["accounting_basis"], "CONSOLIDATED")

    def test_rejects_mixed_consolidated_and_separate_paragraph(self):
        unit = {"section_index": 1, "section_title": "실적", "kind": "paragraph",
                "source_index": 0, "text": "2025년 연결 기준 매출액은 100억원입니다. 별도 기준에 따르면 해당 연도의 매출액은 90억원입니다."}
        self.assertIsNone(performance_candidate(unit))

    def test_marks_separate_basis_in_table_header(self):
        unit = self._table("구분 | 2025년 | 2024년\n[별도] | [별도] | [별도]",
                           "매출액 | 100 | 90")
        candidate = performance_candidate(unit)
        self.assertEqual(candidate["question"], "2025년 별도 기준 매출액은 얼마인가?")
        self.assertEqual(candidate["accounting_basis"], "SEPARATE")


if __name__ == "__main__":
    unittest.main()
