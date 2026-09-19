import unittest

from pipeline.rag_corpus.evaluation_generation import (
    choose_report, choose_tuning_companies, generate_cases, select_parseable_report, select_source_units,
)
from pipeline.raw_sources.dart_archive import DartDocumentRef


class EvaluationGenerationTest(unittest.TestCase):
    def test_performance_uses_later_explicit_paragraph_fact_without_llm_generation(self):
        units = [
            {"section_index": 1, "section_title": "재무상태 및 영업실적", "kind": "paragraph",
             "source_index": 0, "text": "당기말 매출액은 전년 대비 10억원 증가했습니다."},
            {"section_index": 1, "section_title": "재무상태 및 영업실적", "kind": "paragraph",
             "source_index": 1, "text": "2025년 당사 매출액은 100억원입니다."},
        ]
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20260318000001", published_at="2026-03-18",
            categories=("PERFORMANCE",),
            generate=lambda *_: self.fail("실적 수치 문항에 LLM 생성을 사용하면 안 됩니다"),
            judge=lambda _candidate, _source: {"supported": True, "reason": "direct"},
        )
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["question"], "2025년 매출액은 얼마인가?")
        self.assertEqual(cases[0]["answer"], "100억원")
        self.assertEqual(cases[0]["gold_evidence"]["source_index"], 1)
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")
        self.assertEqual(cases[0]["generation_method"], "EXTRACTIVE_NUMERIC")

    def test_performance_table_uses_single_explicit_unit_and_year(self):
        quote = "단위 : 백만원\n구분 | 2023연도 | 2022연도\n매출액 | 2,172 | 219"
        units = [{"section_index": 1, "section_title": "요약재무정보", "kind": "table_row",
                  "source_index": "4:2", "text": quote, "table_header_text": "구분 | 2023연도 | 2022연도",
                  "table_unit_text": "단위 : 백만원"}]
        cases = generate_cases(
            units, corp_code="01466832", rcept_no="20260318000001", published_at="2026-03-18",
            categories=("PERFORMANCE",), generate=lambda *_: self.fail("수치 생성 호출 금지"),
            judge=lambda _candidate, _source: {"supported": True, "reason": "direct"},
        )
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["question"], "2023년 매출액은 얼마인가?")
        self.assertEqual(cases[0]["answer"], "2,172백만원")
        self.assertEqual(cases[0]["gold_evidence"]["fiscal_year"], "2023")
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")

    def test_performance_omits_unverified_compound_unit_and_implicit_year(self):
        units = [
            {"section_index": 1, "section_title": "실적", "kind": "table_row", "source_index": "1:2",
             "text": "단위 : 백만원,%\n구분 | 2025년 | 증가율\n매출액 | 1,000 | 10",
             "table_header_text": "구분 | 2025년 | 증가율", "table_unit_text": "단위 : 백만원,%"},
            {"section_index": 1, "section_title": "실적", "kind": "paragraph", "source_index": 2,
             "text": "당사 매출액은 100억원입니다."},
        ]
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20260318000001", published_at="2026-03-18",
            categories=("PERFORMANCE",), generate=lambda *_: self.fail("근거 없는 생성 호출 금지"),
            judge=lambda *_: self.fail("생성된 후보가 없어야 합니다"),
        )
        self.assertEqual(cases, [])

    def test_performance_does_not_mislabel_rnd_revenue_ratio_as_revenue(self):
        header = "과 목 | 2025년(제58기) | 2024년(제57기)"
        units = [
            {"section_index": 1, "section_title": "실적", "kind": "table_row", "source_index": "1:2",
             "text": "단위 : 백만원\n" + header + "\n연구개발비/매출액 비율 | 0.18 | 0.25",
             "table_header_text": header, "table_unit_text": "단위 : 백만원"},
            {"section_index": 1, "section_title": "실적", "kind": "table_row", "source_index": "1:3",
             "text": "단위 : 백만원\n" + header + "\n매출액 | 1,000 | 900",
             "table_header_text": header, "table_unit_text": "단위 : 백만원"},
        ]
        cases = generate_cases(
            units, corp_code="00145552", rcept_no="20260318000001", published_at="2026-03-18",
            categories=("PERFORMANCE",), generate=lambda *_: self.fail("수치 생성 호출 금지"),
            judge=lambda *_: {"supported": True, "reason": "direct"},
        )
        self.assertEqual(cases[0]["answer"], "1,000백만원")
        self.assertEqual(cases[0]["gold_evidence"]["source_index"], "1:3")

    def test_source_selection_skips_headings_but_keeps_short_facts(self):
        units = [
            {"section_index": 1, "section_title": "연구개발", "kind": "paragraph",
             "source_index": 0, "text": "1) 주요 연구개발 현황"},
            {"section_index": 1, "section_title": "연구개발", "kind": "paragraph",
             "source_index": 1, "text": "당사는 5실 6팀의 연구개발 조직을 운영하고 있습니다."},
        ]
        selected = select_source_units(units, "TECHNOLOGY_RND", limit=2)
        self.assertEqual([unit["source_index"] for unit in selected], [1])

    def test_revised_question_from_same_source_gets_new_case_id(self):
        units = [{"section_index": 1, "section_title": "사업", "kind": "paragraph",
                  "source_index": 0, "text": "DX 매출은 187조원(56.3%)입니다."}]

        def build(question):
            return generate_cases(
                units, corp_code="00126380", rcept_no="20260310002820", published_at="2026-03-10",
                categories=("BUSINESS",),
                generate=lambda _category, _units: {"question": question, "answer": "187조원, 56.3%",
                    "section_index": 1, "kind": "paragraph", "source_index": 0,
                    "source_quote": "DX 매출은 187조원(56.3%)입니다."},
                judge=lambda _candidate, _source: {"supported": True, "reason": "direct"},
            )[0]

        self.assertNotEqual(build("DX 매출과 공시 비율은?")["case_id"],
                            build("DX 매출이 전체 매출에서 차지하는 비중은?")["case_id"])

    def test_table_case_preserves_header_and_unit_metadata(self):
        source_text = "단위 : 백만원\n법인명 | 최초취득금액\n현대아산 | 22,500"
        units = [{"section_index": 1, "section_title": "출자", "kind": "table_row",
                  "source_index": "0:1", "text": source_text,
                  "table_header_text": "법인명 | 최초취득금액", "table_unit_text": "단위 : 백만원"}]
        case = generate_cases(
            units, corp_code="00164742", rcept_no="20260318001394", published_at="2026-03-18",
            categories=("INVESTMENT_STRATEGY",),
            generate=lambda _category, _units: {"question": "최초취득금액은?", "answer": "22,500백만원",
                "section_index": 1, "kind": "table_row", "source_index": "0:1",
                "source_quote": "현대아산 | 22,500", "unit": "백만원"},
            judge=lambda _candidate, _source: {"supported": True, "reason": "direct"},
        )[0]
        self.assertEqual(case["validation_status"], "AUTO_VALIDATED")
        self.assertEqual(case["gold_evidence"]["table_unit_text"], "단위 : 백만원")
        self.assertEqual(case["gold_evidence"]["table_header_text"], "법인명 | 최초취득금액")
        self.assertIn("최초취득금액", case["gold_evidence"]["source_quote"])

    def test_evaluation_parse_keeps_tu_cells_in_their_original_columns(self):
        ref = DartDocumentRef("00164742", "현대자동차", 2025, "20260318001394", "20260318",
                              "사업보고서", "report.xml", 100)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <DOCUMENT><TITLE>타법인출자</TITLE><TABLE><THEAD>
        <TR><TH>법인명</TH><TH>상장여부</TH><TH>최초취득금액</TH></TR>
        </THEAD><TBODY><TR><TE>현대아산</TE><TU>상장</TU><TE>22,500</TE></TR></TBODY>
        </TABLE></DOCUMENT>""".encode()

        class Archive:
            def documents(self, _corp_code):
                return (ref,)

            def read(self, _ref):
                return xml

        _, document, _ = select_parseable_report(Archive(), "00164742", as_of="2026-09-16")
        self.assertEqual(document.tables[0].m[1][:3], ["현대아산", "상장", "22,500"])

    def test_uses_previous_report_only_when_latest_xml_is_broken_and_records_it(self):
        older = DartDocumentRef("00126380", "삼성전자", 2024, "20250318000001", "20250318", "사업보고서", "older.xml", 50)
        latest = DartDocumentRef("00126380", "삼성전자", 2025, "20260318000001", "20260318", "사업보고서", "latest.xml", 50)

        class Archive:
            def documents(self, corp_code):
                self.assert_code(corp_code)
                return (older, latest)

            def assert_code(self, corp_code):
                if corp_code != "00126380":
                    raise AssertionError(corp_code)

            def read(self, ref):
                if ref == latest:
                    return b"<DOCUMENT><TITLE>broken</TITLE>"
                return b"<DOCUMENT><TITLE>business</TITLE><P>source</P></DOCUMENT>"

        ref, document, skipped = select_parseable_report(Archive(), "00126380", as_of="2026-09-16")
        self.assertEqual(ref.rcept_no, older.rcept_no)
        self.assertEqual(document.sections[1].title, "business")
        self.assertEqual(skipped, [{"rcept_no": latest.rcept_no, "rcept_dt": latest.rcept_dt,
                                    "reason": "invalid_xml"}])

    def test_generator_sees_one_source_to_prevent_cross_source_answers(self):
        units = [
            {"section_index": 1, "section_title": "사업", "kind": "paragraph", "source_index": 0,
             "text": "반도체 사업을 운영합니다."},
            {"section_index": 1, "section_title": "사업", "kind": "paragraph", "source_index": 1,
             "text": "스마트폰 사업을 운영합니다."},
        ]
        def generate(_category, presented):
            self.assertEqual(len(presented), 1)
            return {"question": "주요 사업은?", "answer": "반도체 사업", "section_index": 1,
                    "kind": "paragraph", "source_index": 0, "source_quote": "반도체 사업을 운영합니다"}
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20250318000001", published_at="2025-03-18",
            categories=("BUSINESS",), generate=generate,
            judge=lambda _case, _source: {"supported": True, "reason": "confirmed"},
        )
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")

    def test_expands_short_quote_only_when_answer_number_exists_in_same_source(self):
        units = [{"section_index": 1, "section_title": "연구개발", "kind": "paragraph",
                  "source_index": 0, "text": "2024년 연구개발비는 100억원입니다."}]
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20250318000001", published_at="2025-03-18",
            categories=("TECHNOLOGY_RND",),
            generate=lambda _category, _units: {"question": "2024년 연구개발비는?", "answer": "100억원",
                "section_index": 1, "kind": "paragraph", "source_index": 0,
                "source_quote": "연구개발비는", "fiscal_year": "2024", "unit": "억원",
                "accounting_basis": "UNSPECIFIED"},
            judge=lambda _case, _source: {"supported": True, "reason": "confirmed"},
        )
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")
        self.assertEqual(cases[0]["gold_evidence"]["source_quote"], "2024년 연구개발비는 100억원입니다.")
        self.assertEqual(cases[0]["quote_resolution"], "EXPANDED_TO_SOURCE_UNIT")

    def test_recovers_wrong_llm_coordinate_only_from_unique_exact_quote(self):
        units = [{"section_index": 1, "section_title": "사업의 내용", "kind": "paragraph",
                  "source_index": 0, "text": "반도체 사업을 운영합니다."}]
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20250318000001", published_at="2025-03-18",
            categories=("BUSINESS",),
            generate=lambda _category, _units: {"question": "주요 사업은?", "answer": "반도체 사업",
                "section_index": 1, "kind": "BUSINESS", "source_index": 7,
                "source_quote": "반도체 사업을 운영합니다"},
            judge=lambda _case, _source: {"supported": True, "reason": "confirmed"},
        )
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")
        self.assertEqual(cases[0]["gold_evidence"]["kind"], "paragraph")
        self.assertEqual(cases[0]["coordinate_resolution"], "UNIQUE_QUOTE_MATCH")

    def test_report_choice_excludes_future_and_uses_latest_eligible(self):
        refs = [DartDocumentRef("00126380", "삼성전자", 2024, receipt, date, "사업보고서", "x.xml", 10)
                for receipt, date in (("20250318000001", "20250318"),
                                      ("20260318000001", "20260318"))]
        chosen = choose_report(refs, as_of="2025-12-31")
        self.assertEqual(chosen.rcept_no, "20250318000001")

    def test_default_selection_never_uses_holdout(self):
        selected = choose_tuning_companies({"companies": [
            {"corp_code": "00000001", "group": "holdout"},
            {"corp_code": "00000002", "group": "tuning"},
            {"corp_code": "00000003", "group": "tuning"},
        ]}, limit=1)
        self.assertEqual(selected, ["00000002"])

    def test_generation_rejects_ungrounded_and_judge_disagreement(self):
        units = [{"section_index": 1, "section_title": "사업의 내용", "kind": "paragraph",
                  "source_index": 0, "text": "반도체 매출액은 2024년 100억원입니다."}]
        def generate(_category, _units):
            return {"question": "매출액은?", "answer": "100억원", "source_index": 0,
                    "section_index": 1, "kind": "paragraph", "source_quote": "2024년 100억원",
                    "fiscal_year": "2024", "unit": "억원", "accounting_basis": "UNSPECIFIED"}
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20250318000001", published_at="2025-03-18",
            categories=("BUSINESS",), generate=generate,
            judge=lambda _case, _source: {"supported": False, "reason": "ambiguous"},
        )
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["validation_status"], "REJECTED")
        self.assertIn("judge_rejected", cases[0]["validation_reasons"])
        self.assertEqual(cases[0]["review_status"], "PENDING_HUMAN_REVIEW")

    def test_generation_keeps_original_coordinates_and_never_approves_automatically(self):
        units = [{"section_index": 1, "section_title": "사업의 내용", "kind": "paragraph",
                  "source_index": 0, "text": "반도체 사업을 운영합니다."}]
        cases = generate_cases(
            units, corp_code="00126380", rcept_no="20250318000001", published_at="2025-03-18",
            categories=("BUSINESS",),
            generate=lambda _category, _units: {"question": "주요 사업은?", "answer": "반도체 사업",
                "section_index": 1, "kind": "paragraph", "source_index": 0,
                "source_quote": "반도체 사업을 운영합니다"},
            judge=lambda _case, _source: {"supported": True, "reason": "source confirms"},
        )
        self.assertEqual(cases[0]["validation_status"], "AUTO_VALIDATED")
        self.assertEqual(cases[0]["review_status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual(cases[0]["generation_method"], "LLM_GENERATED")
        self.assertEqual(cases[0]["gold_evidence"]["section_index"], 1)
        self.assertNotIn("evidence_id", cases[0]["gold_evidence"])


if __name__ == "__main__":
    unittest.main()
