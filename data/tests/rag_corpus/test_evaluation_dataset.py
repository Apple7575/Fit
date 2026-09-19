import unittest

from pipeline.business_report.doc import Document
from pipeline.rag_corpus.evaluation_dataset import extract_source_units, validate_candidate


class EvaluationDatasetTest(unittest.TestCase):
    def setUp(self):
        xml = """<DOCUMENT><TITLE>II. 사업의 내용</TITLE>
        <P>반도체 사업 매출액은 2024년 100억원입니다.</P>
        <TABLE><TR><TD>구분</TD><TD>2024년</TD></TR>
        <TR><TD>매출액</TD><TD>100억원</TD></TR></TABLE></DOCUMENT>""".encode()
        self.document = Document.from_bytes(xml, rcept_no="20250318000001")
        self.units = extract_source_units(self.document)

    def test_extracts_stable_original_coordinates_without_chunk_id(self):
        self.assertEqual(self.units[0]["section_index"], 1)
        self.assertEqual(self.units[0]["section_title"], "II. 사업의 내용")
        self.assertEqual(self.units[0]["kind"], "paragraph")
        self.assertEqual(self.units[0]["source_index"], 0)
        self.assertIn("2024년 100억원", self.units[0]["text"])
        self.assertTrue(any(unit["kind"] == "table_row" for unit in self.units))
        self.assertFalse(any("evidence_id" in unit for unit in self.units))

    def test_rejects_quote_not_found_in_original_unit(self):
        candidate = self._candidate(source_quote="영업이익은 200억원입니다")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("quote_not_in_source", result["reasons"])
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_wrong_company_and_receipt(self):
        candidate = self._candidate(corp_code="99999999", rcept_no="20250318000002")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("company_mismatch", result["reasons"])
        self.assertIn("receipt_mismatch", result["reasons"])

    def test_numeric_answer_requires_year_unit_basis_and_source_numbers(self):
        candidate = self._candidate(answer="매출액 200억원", fiscal_year="", unit="", accounting_basis="")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("number_not_in_quote", result["reasons"])
        self.assertIn("missing_numeric_context", result["reasons"])

    def test_rejects_numeric_year_or_unit_not_present_in_quote(self):
        candidate = self._candidate(fiscal_year="2023", unit="백만원")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("numeric_context_not_in_quote", result["reasons"])

    def test_grounded_candidate_stays_unapproved(self):
        candidate = self._candidate()
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertEqual(result["status"], "AUTO_VALIDATED")
        self.assertEqual(result["review_status"], "PENDING_HUMAN_REVIEW")

    def test_table_row_keeps_all_header_rows_and_explicit_unit(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <DOCUMENT><TITLE>타법인출자</TITLE><P>(단위 : 백만원)</P>
        <TABLE><THEAD><TR><TH>법인명</TH><TH>금액</TH></TR>
        <TR><TH>법인명</TH><TH>최초취득금액</TH></TR></THEAD>
        <TBODY><TR><TE>현대아산</TE><TE>22,500</TE></TR></TBODY></TABLE>
        </DOCUMENT>""".encode()
        document = Document.from_bytes(xml, rcept_no="20260318001394")
        unit = next(item for item in extract_source_units(document)
                    if item["kind"] == "table_row" and item["source_index"] == "0:2")
        self.assertIn("금액", unit["text"])
        self.assertIn("최초취득금액", unit["text"])
        self.assertIn("단위 : 백만원", unit["text"])
        self.assertIn("현대아산 | 22,500", unit["text"])

    def test_numeric_table_answer_requires_full_context_in_quote(self):
        units = [{"section_index": 1, "section_title": "타법인출자", "kind": "table_row",
                  "source_index": "0:2", "text": "단위 : 백만원\n법인명 | 최초취득금액\n현대아산 | 22,500",
                  "table_unit_text": "단위 : 백만원", "table_header_text": "법인명 | 최초취득금액"}]
        candidate = {"corp_code": "00126380", "rcept_no": "20250318000001",
                     "category": "INVESTMENT_STRATEGY", "question": "현대아산 최초취득금액은?",
                     "answer": "22,500백만원", "section_index": 1, "kind": "table_row",
                     "source_index": "0:2", "source_quote": "현대아산 | 22,500",
                     "unit": "백만원"}
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("table_context_not_in_quote", result["reasons"])

    def test_table_answer_unit_must_match_declared_unit_and_source(self):
        source = "단위 : 백만원\n법인명 | 최초취득금액\n현대아산 | 22,500"
        units = [{"section_index": 1, "section_title": "타법인출자", "kind": "table_row",
                  "source_index": "0:1", "text": source, "table_unit_text": "단위 : 백만원",
                  "table_header_text": "법인명 | 최초취득금액"}]
        candidate = {"corp_code": "00126380", "rcept_no": "20250318000001",
                     "category": "INVESTMENT_STRATEGY", "question": "최초취득금액은?",
                     "answer": "22,500원", "section_index": 1, "kind": "table_row",
                     "source_index": "0:1", "source_quote": source, "unit": "백만원"}
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("table_answer_unit_mismatch", result["reasons"])

    def test_percent_share_needs_explicit_denominator_even_with_table_header(self):
        source = "단위 : 백만원\n제품명 | 2023년 매출액(비율)\nPS 제품 | 397(2.33)"
        units = [{"section_index": 1, "section_title": "주요 제품", "kind": "table_row",
                  "source_index": "0:1", "text": source, "table_unit_text": "단위 : 백만원",
                  "table_header_text": "제품명 | 2023년 매출액(비율)"}]
        candidate = {"corp_code": "00126380", "rcept_no": "20250318000001",
                     "category": "BUSINESS", "question": "PS 제품은 전체 매출액 중 몇 퍼센트인가?",
                     "answer": "전체 매출액 중 2.33%", "section_index": 1,
                     "kind": "table_row", "source_index": "0:1", "source_quote": source,
                     "unit": "백만원"}
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("denominator_not_explicit", result["reasons"])

    def test_rejects_year_or_accounting_basis_added_outside_quote(self):
        candidate = self._candidate(category="INVESTMENT_STRATEGY",
                                    question="2023년도 연결 기준 투자금액은?",
                                    answer="100억원", fiscal_year="2023",
                                    accounting_basis="CONSOLIDATED")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("claim_year_not_in_quote", result["reasons"])
        self.assertIn("accounting_basis_not_in_quote", result["reasons"])

    def test_rejects_comparison_not_stated_in_quote(self):
        candidate = self._candidate(question="전년 대비 매출 변화는?", answer="100억원")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("comparison_not_in_quote", result["reasons"])

    def test_rejects_heading_only_question(self):
        units = [{"section_index": 1, "section_title": "사업", "kind": "paragraph",
                  "source_index": 0, "text": "1) 주요 원재료 현황"}]
        candidate = self._candidate(category="DISCLOSED_RISKS", question="원재료 현황 항목은?",
                                    answer="주요 원재료 현황", source_quote="1) 주요 원재료 현황",
                                    fiscal_year="", unit="", accounting_basis="")
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("heading_only_source", result["reasons"])

    def test_rejects_market_narrative_without_company_fact(self):
        units = [{"section_index": 1, "section_title": "사업", "kind": "paragraph",
                  "source_index": 0, "text": "2025년 메모리 시장은 AI 확산으로 성장하였습니다."}]
        candidate = self._candidate(category="BUSINESS", question="2025년 메모리 시장은 어떻게 변했나?",
                                    answer="2025년 메모리 시장은 성장하였습니다.",
                                    source_quote=units[0]["text"], fiscal_year="2025")
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("market_context_not_company_fact", result["reasons"])

    def test_rejects_missing_answer_and_unstated_percent_unit(self):
        units = [{"section_index": 1, "section_title": "제품", "kind": "table_row",
                  "source_index": "0:1", "text": "제품 | 매출액(비율)\nPS | 397(2.33)",
                  "table_header_text": "제품 | 매출액(비율)", "table_unit_text": ""}]
        candidate = self._candidate(category="BUSINESS", question="PS 비율은?", answer="2.33%",
                                    kind="table_row", source_index="0:1", source_quote=units[0]["text"],
                                    fiscal_year="", unit="", accounting_basis="")
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("percent_unit_not_in_quote", result["reasons"])
        candidate["answer"] = "금액은 명시되지 않았습니다."
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("missing_value_answer", result["reasons"])

    def test_rejects_table_header_used_as_answer(self):
        units = [{"section_index": 1, "section_title": "출자", "kind": "table_row",
                  "source_index": "0:1", "text": "법인명 | 출자목적\n- | -",
                  "table_header_text": "법인명 | 출자목적", "table_unit_text": ""}]
        candidate = self._candidate(category="INVESTMENT_STRATEGY", question="출자 목적은?",
                                    answer="출자목적", kind="table_row", source_index="0:1",
                                    source_quote=units[0]["text"], fiscal_year="", unit="", accounting_basis="")
        result = validate_candidate(candidate, units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("header_as_answer", result["reasons"])

    def test_rejects_accounting_basis_in_question_even_without_basis_metadata(self):
        candidate = self._candidate(category="PERFORMANCE", question="제20기 연결 재무제표 기준 매출액은?",
                                    answer="100억원", accounting_basis="UNSPECIFIED")
        result = validate_candidate(candidate, self.units, corp_code="00126380", rcept_no="20250318000001")
        self.assertIn("accounting_basis_not_in_quote", result["reasons"])

    def _candidate(self, **changes):
        candidate = {
            "corp_code": "00126380", "rcept_no": "20250318000001",
            "category": "PERFORMANCE", "question": "2024년 매출액은 얼마인가?",
            "answer": "매출액은 100억원", "section_index": 1,
            "kind": "paragraph", "source_index": 0,
            "source_quote": "매출액은 2024년 100억원입니다",
            "fiscal_year": "2024", "unit": "억원", "accounting_basis": "UNSPECIFIED",
        }
        candidate.update(changes)
        return candidate


if __name__ == "__main__":
    unittest.main()
