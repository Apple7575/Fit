from __future__ import annotations

import unittest

from ai.company_analysis.deterministic import build_deterministic_report
from ai.company_analysis.evidence import BusinessReport, EvidenceChunk
from ai.company_analysis.narrative import PLANS, NarrativeEnricher, _check, build_bundle
from ai.company_analysis.table_facts import PLAN_FORMS, TableFactRow, covered_tables, render_blocks
from ai.tests.company_analysis.test_api import _facts
from ai.tests.company_analysis.test_narrative import NOW, PUBLISHED, RCEPT, _chunk

CHUNK_ID = "dart-business-report-0000000000000000000000000000abcd"


def _row(labels, column, text, num, *, year=2025, table=7, scope=None, evidence=CHUNK_ID, form="SALES_BY_PRODUCT", unit="백만원", matrix_row=1):
    return TableFactRow(RCEPT, table, form, "4. 매출 및 수주상황", scope, unit, matrix_row, tuple(labels), column, year, num, text, "NUMBER" if num is not None else "TEXT", evidence)


ROWS = (
    _row(["반도체 부문", "제품 외", "DRAM, NAND Flash 등"], "제78기", "97,146,675", 97146675.0, year=2025, matrix_row=1),
    _row(["반도체 부문", "제품 외", "DRAM, NAND Flash 등"], "제77기", "66,192,960", 66192960.0, year=2024, matrix_row=1),
    _row(["합계", "합계", "합계"], "제78기", "97,146,675", 97146675.0, year=2025, matrix_row=2),
    _row(["합계", "합계", "합계"], "제77기", "-", None, year=2024, matrix_row=2),
)


def _raw_table(table_index: int, evidence_id: str = "e-sales") -> EvidenceChunk:
    chunk = _chunk(evidence_id, 13, "4. 매출 및 수주상황", "표 머리글: 사업부문 | 매출유형 | 품목 | 제78기 | 제77기\n반도체 부문 | 제품 외 | DRAM | 97,146,675 | 66,192,960", table=True, unit="백만원")
    return EvidenceChunk(**{**chunk.__dict__, "metadata": {"table_index": table_index, "rcept_no": RCEPT}})


class RenderTest(unittest.TestCase):
    def test_blocks_carry_values_years_unit_and_chunk_citation(self):
        blocks = render_blocks(ROWS, PLAN_FORMS["BUSINESS_CORE"])
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block.evidence_id, f"facts:SALES_BY_PRODUCT:{RCEPT}:7")
        self.assertIn("표 단위: 백만원", block.content)
        self.assertIn("반도체 부문 > 제품 외 > DRAM, NAND Flash 등 | 제78기(2025년): 97,146,675백만원 · 제77기(2024년): 66,192,960백만원", block.content)
        self.assertIn("합계 > 합계 > 합계 | 제78기(2025년): 97,146,675백만원", block.content)
        self.assertNotIn("제77기(2024년): -", block.content, "빈 값은 넣지 않는다")
        self.assertEqual(block.citation.source_id, CHUNK_ID, "인용은 그 표의 원문 청크")
        self.assertEqual(block.citation.rcept_no, RCEPT)
        self.assertEqual(covered_tables(blocks), {(RCEPT, 7)})

    def test_rows_without_linked_chunk_or_other_forms_are_skipped(self):
        pending = _row(["A"], "제78기", "1", 1.0, evidence=None)
        other = _row(["B"], "인원수", "10", 10.0, form="EXECUTIVE_PAY")
        self.assertEqual(render_blocks([pending, other], PLAN_FORMS["BUSINESS_CORE"]), [])

    def test_subsidiary_scope_is_announced(self):
        block = render_blocks([_row(["은행"], "제78기", "3,520,741", 3520741.0, scope="우리은행")], ("SALES_BY_PRODUCT",))[0]
        self.assertIn("소속 법인: 우리은행", block.content)
        self.assertEqual(block.entity_scope, "우리은행")


class BundleTest(unittest.TestCase):
    def _report(self):
        return build_deterministic_report(_facts(), generated_at=NOW)

    def test_fact_block_replaces_raw_chunk_of_the_same_table(self):
        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7), _raw_table(9, "e-other")))
        bundle = build_bundle(PLANS["BUSINESS_GROWTH"], business, self._report(), ROWS)
        self.assertIn(f"facts:SALES_BY_PRODUCT:{RCEPT}:7", bundle.ids)
        self.assertNotIn("e-sales", bundle.ids, "정형화된 표의 원문 청크는 뺀다")
        self.assertIn("e-other", bundle.ids, "정형화되지 않은 표는 그대로 둔다")
        self.assertTrue(bundle.cited_texts[f"facts:SALES_BY_PRODUCT:{RCEPT}:7"].is_table)

    def test_without_facts_bundle_is_unchanged(self):
        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))
        bundle = build_bundle(PLANS["BUSINESS_GROWTH"], business, self._report())
        self.assertIn("e-sales", bundle.ids)

    def test_numbers_from_fact_block_pass_the_claim_check(self):
        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))
        bundle = build_bundle(PLANS["BUSINESS_GROWTH"], business, self._report(), ROWS)
        facts_id = f"facts:SALES_BY_PRODUCT:{RCEPT}:7"
        self.assertTrue(_check("반도체 부문 매출은 2025년 97,146,675백만원입니다.", [facts_id], bundle))
        self.assertEqual(_check("반도체 부문 매출은 2025년 97,146,675억원입니다.", [facts_id], bundle), [], "단위가 틀리면 버린다")
        self.assertEqual(_check("반도체 부문 매출은 2025년 12,345,678백만원입니다.", [facts_id], bundle), [], "없는 숫자는 버린다")

    def test_enricher_falls_back_when_facts_repository_fails(self):
        class Broken:
            def rows(self, corp_code, rcept_no):
                raise RuntimeError("db down")

        class Silent:
            def complete(self, messages, schema, *, max_tokens):
                return {"status": "INSUFFICIENT_EVIDENCE"}

        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))

        class Reports:
            def latest(self, corp_code):
                return business

        enricher = NarrativeEnricher(Silent(), Reports(), plans=[PLANS["BUSINESS_GROWTH"]], table_facts=Broken())
        report = enricher.enrich(_facts(), self._report())
        self.assertTrue(any("정형 표를 읽지 못해" in w for w in report.warnings))


class FinancialsFactsTest(unittest.TestCase):
    def test_financials_bundle_gets_employee_and_pay_tables(self):
        rows = [
            _row(["전사", "남"], "직원>직원수>합계", "2,897", 2897.0, form="EMPLOYEE_STATUS", table=21, unit="백만원", year=None),
            _row(["전사", "남"], "직원>1인평균급여액", "160", 160.0, form="EMPLOYEE_STATUS", table=21, unit="백만원", year=None),
            _row(["미등기임원"], "인원수", "136", 136.0, form="EXECUTIVE_PAY", table=23, unit="백만원", year=None),
            _row(["반도체 부문"], "제78기", "97,146,675", 97146675.0),
        ]
        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))
        bundle = build_bundle(PLANS["FINANCIALS"], business, build_deterministic_report(_facts(), generated_at=NOW), rows)
        self.assertIn(f"facts:EMPLOYEE_STATUS:{RCEPT}:21", bundle.ids)
        self.assertIn(f"facts:EXECUTIVE_PAY:{RCEPT}:23", bundle.ids)
        self.assertNotIn(f"facts:SALES_BY_PRODUCT:{RCEPT}:7", bundle.ids, "재무 섹션에는 매출실적 표를 넣지 않는다")
        contents = bundle.payload[-2]["content"] + bundle.payload[-1]["content"]
        self.assertIn("직원>직원수>합계: 2,897명", contents, "인원 열에는 표 단위(백만원)를 붙이지 않는다")
        self.assertIn("직원>1인평균급여액: 160백만원", contents)
        self.assertIn("인원수: 136명", contents)
        outsourced = _row(["전사", "남"], "소속외근로자>계", "530", 530.0, form="EMPLOYEE_STATUS", table=21, unit="백만원", year=None)
        self.assertIn("소속외근로자>계: 530명", render_blocks([outsourced], ("EMPLOYEE_STATUS",))[0].content, "NAVER 실측: 소속 외 근로자 수에 백만원이 붙었다")


class RetryTest(unittest.TestCase):
    def test_truncated_output_is_retried_once_with_compact_note(self):
        from ai.company_analysis.llm import InvalidModelResponse

        class Flaky:
            def __init__(self):
                self.calls = []

            def complete(self, messages, schema, *, max_tokens):
                self.calls.append(messages[1]["content"])
                if len(self.calls) == 1:
                    raise InvalidModelResponse("Qwen JSON 파싱 실패: finish_reason=length content_length=9826")
                return {"status": "INSUFFICIENT_EVIDENCE"}

        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))

        class Reports:
            def latest(self, corp_code):
                return business

        client = Flaky()
        enricher = NarrativeEnricher(client, Reports(), plans=[PLANS["BUSINESS_GROWTH"]])
        report = enricher.enrich(_facts(), build_deterministic_report(_facts(), generated_at=NOW))
        self.assertEqual(len(client.calls), 2)
        self.assertIn("항목당 2문장 이내", client.calls[1])
        self.assertNotIn("항목당 2문장 이내", client.calls[0])
        self.assertFalse(any("생성에 실패" in w for w in report.warnings))

    def test_other_model_errors_are_not_retried(self):
        from ai.company_analysis.llm import InvalidModelResponse

        class Broken:
            def __init__(self):
                self.calls = 0

            def complete(self, messages, schema, *, max_tokens):
                self.calls += 1
                raise InvalidModelResponse("Qwen 응답 구조에서 content 를 찾을 수 없습니다")

        business = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=(_raw_table(7),))

        class Reports:
            def latest(self, corp_code):
                return business

        client = Broken()
        report = NarrativeEnricher(client, Reports(), plans=[PLANS["BUSINESS_GROWTH"]]).enrich(_facts(), build_deterministic_report(_facts(), generated_at=NOW))
        self.assertEqual(client.calls, 1)
        self.assertTrue(any("생성에 실패" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
