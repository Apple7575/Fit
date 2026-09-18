from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai.company_analysis.claim_check import CitedText, numeric_claim_violations
from ai.company_analysis.contracts import CompanyReport
from ai.company_analysis.deterministic import build_deterministic_report
from ai.company_analysis.evidence import BusinessReport, EvidenceChunk, report_from_rows
from ai.company_analysis.narrative import PLANS, NarrativeEnricher, build_bundle, section_schema
from ai.tests.company_analysis.test_deterministic import _facts

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)
PUBLISHED = datetime(2026, 3, 17, tzinfo=timezone.utc)
RCEPT = "20260317000635"


def _chunk(evidence_id: str, section_index: int, title: str, content: str, *, table: bool = False, order: int = 0, unit: str | None = None, rcept: str = RCEPT) -> EvidenceChunk:
    return EvidenceChunk(
        evidence_id=evidence_id,
        corp_code="00164779",
        rcept_no=rcept,
        report_name="사업보고서 (2025.12)",
        published_at=PUBLISHED,
        section_index=section_index,
        section_title=title,
        content_type="TABLE" if table else "TEXT",
        order=order,
        content=content,
        unit=unit,
    )


CHUNKS = (
    _chunk("e-overview", 10, "1. 사업의 개요", "SK하이닉스는 DRAM 및 NAND를 중심으로 하는 메모리 반도체 기업입니다. 연결 기준 매출액은 2025년 97조 1,468억원입니다."),
    _chunk("e-products", 11, "2. 주요 제품 및 서비스", "2025년 메모리 시장은 AI 확산으로 성장했고 HBM 수요가 크게 증가하였습니다."),
    _chunk("e-share", 16, "7. 기타 참고사항", "표 캡션: 시장점유율\n표 머리글: 구분 | 2025년\nDRAM | 36.0%\nNAND | 20.1%", table=True, order=5),
    _chunk("e-market", 16, "7. 기타 참고사항", "가트너에 따르면 2025년 세계 반도체 시장규모는 US$7,934억이며 메모리는 26% 수준입니다.", order=0),
    _chunk("e-risk", 14, "5. 위험관리 및 파생거래", "연결회사는 달러화 등 환율변동위험에 노출되어 있습니다."),
    _chunk("e-old", 10, "1. 사업의 개요", "2024년 문장", rcept="20250319000665"),
)


def _business_report() -> BusinessReport:
    return BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="사업보고서 (2025.12)", published_at=PUBLISHED, chunks=tuple(c for c in CHUNKS if c.rcept_no == RCEPT))


class FakeReports:
    def __init__(self, report: BusinessReport | None) -> None:
        self._report = report

    def latest(self, corp_code: str):
        return self._report


class ScriptedClient:
    """계획 순서대로 정해진 출력을 돌려준다. 스키마 enum 검사는 테스트가 직접 한다."""

    def __init__(self, outputs: dict[str, dict]) -> None:
        self._outputs = outputs
        self.calls: list[tuple[str, dict, list[str]]] = []

    def complete(self, messages, schema, *, max_tokens):
        import json

        payload = json.loads(messages[1]["content"])
        section = payload["section"]["name"]
        allowed = [e["evidence_id"] for e in payload["evidence"]]
        self.calls.append((section, schema, allowed))
        if section not in self._outputs:
            raise RuntimeError("no scripted output")
        return self._outputs[section]


class ClaimCheckTest(unittest.TestCase):
    def test_amount_must_exist_in_evidence(self):
        cited = [CitedText("a", "매출액 41,216,512백만원")]
        self.assertEqual(numeric_claim_violations("생산실적은 41,216,512백만원입니다.", cited), [])
        codes = [v.code for v in numeric_claim_violations("생산실적은 41,216,999백만원입니다.", cited)]
        self.assertEqual(codes, ["number_not_in_evidence"])

    def test_money_table_number_needs_money_unit(self):
        table = CitedText("t", "표 머리글: 판매경로 | 매출액\n직판 | 4,452,074", is_table=True, unit="천원", header="표 머리글: 판매경로 | 매출액")
        self.assertEqual([v.code for v in numeric_claim_violations("직판으로 4,452,074 단위 판매", [table])], ["amount_as_quantity"])
        self.assertEqual([v.code for v in numeric_claim_violations("직판 매출은 4,452,074입니다", [table])], ["money_unit_missing"])
        self.assertEqual([v.code for v in numeric_claim_violations("직판 매출은 4,452,074억원", [table])], ["unit_mismatch"])
        self.assertEqual(numeric_claim_violations("직판 매출은 4,452,074천원", [table]), [])

    def test_ratio_and_unit_suffixed_numbers(self):
        cited = [CitedText("m", "표 머리글: 항목 | 2025년\n매출액 | 97.1\n영업이익률(%) | 48.6\n직원 수: 34549명")]
        self.assertEqual(numeric_claim_violations("매출 97.1조원, 영업이익률 48.6%, 직원 34549명, 2025년 기준", cited), [])
        codes = [v.code for v in numeric_claim_violations("매출 95.3조원, 영업이익률 50%", cited)]
        self.assertEqual(codes, ["ratio_not_in_evidence", "number_not_in_evidence"])

    def test_share_claims_need_share_evidence(self):
        from ai.company_analysis.claim_check import share_claim_violations

        market = CitedText("m", "DRAM이 전체 메모리 시장의 65%를 차지합니다.")
        share = CitedText("s", "표 머리글: 시장점유율 | 2025년\nDRAM | 36.0%")
        self.assertEqual([v.code for v in share_claim_violations("DRAM 시장 점유율 65%를 기록", [market])], ["share_not_in_evidence"])
        self.assertEqual(share_claim_violations("DRAM 시장 점유율 36.0%를 기록", [market, share]), [])
        self.assertEqual(share_claim_violations("메모리 시장의 65%가 DRAM입니다", [market]), [])

    def test_quantity_copied_verbatim_from_money_table_passes(self):
        table = CitedText(
            "t",
            "표 머리글: 연구과제 | 내용\nHBM4 | 2,048개의 I/O 적용, 11Gbps 구현",
            is_table=True,
            unit="백만원",
            header="표 머리글: 연구과제 | 내용",
        )
        self.assertEqual(numeric_claim_violations("HBM4는 2,048개의 I/O를 적용했습니다.", [table]), [])
        self.assertEqual([v.code for v in numeric_claim_violations("연구비는 2,048입니다.", [table])], ["money_unit_missing"])

    def test_malformed_grouping(self):
        self.assertEqual([v.code for v in numeric_claim_violations("-43,0백만원", [CitedText("x", "43,0")])][0], "malformed_number")


class EvidenceTest(unittest.TestCase):
    def test_report_from_rows_keeps_latest_receipt_only(self):
        rows = [
            {"evidence_id": c.evidence_id, "corp_code": c.corp_code, "title": c.report_name, "published_at": c.published_at, "content": c.content,
             "metadata": {"rcept_no": c.rcept_no, "report_name": c.report_name, "section_index": c.section_index, "section_title": c.section_title,
                          "content_type": c.content_type, "table_index" if c.is_table else "chunk_index": c.order, "unit": c.unit}}
            for c in CHUNKS
        ]
        report = report_from_rows(rows)
        self.assertEqual(report.rcept_no, RCEPT)
        self.assertNotIn("e-old", report.by_id())
        self.assertEqual(report.chunks[0].evidence_id, "e-overview")
        self.assertEqual(report.source_card()["url"], f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={RCEPT}")
        self.assertIsNone(report_from_rows([]))

    def test_select_follows_pattern_priority_and_budget(self):
        report = _business_report()
        picked = report.select((r"기타 참고사항", r"사업의 개요"), content_types=("TEXT",), max_chars=10_000)
        self.assertEqual([c.evidence_id for c in picked], ["e-overview", "e-market"])  # 문서 순서로 정렬
        tight = report.select((r"기타 참고사항", r"사업의 개요"), content_types=("TEXT",), max_chars=60)
        self.assertEqual([c.evidence_id for c in tight], ["e-market"])  # 앞 패턴 우선
        tables = report.select((r"기타 참고사항",), content_types=("TABLE",), max_chars=10_000)
        self.assertEqual([c.evidence_id for c in tables], ["e-share"])


class BundleAndSchemaTest(unittest.TestCase):
    def test_bundle_includes_metric_tables_and_chunks(self):
        report = build_deterministic_report(_facts(), generated_at=NOW)
        bundle = build_bundle(PLANS["FINANCIALS"], _business_report(), report)
        self.assertIn("metrics:00164779:financials", bundle.ids)
        self.assertIn("metrics:00164779:ratios", bundle.ids)
        # 확정 지표 표는 직원 수 같은 열이 섞여 있어 금액 표 규칙을 적용하지 않는다
        self.assertFalse(bundle.cited_texts["metrics:00164779:financials"].is_table)
        competitors = build_bundle(PLANS["COMPETITORS_POSITION"], _business_report(), report)
        self.assertIn("peers:00164779", competitors.ids)
        market = build_bundle(PLANS["COMPETITORS_MARKET"], _business_report(), report)
        self.assertIn("e-share", market.ids)

    def test_bundle_never_exceeds_context_budget(self):
        from ai.company_analysis.narrative import MAX_EVIDENCE_CHARS

        big = tuple(_chunk(f"big-{i}", 16, "7. 기타 참고사항", "가" * 1_200, order=i) for i in range(30))
        report = BusinessReport(corp_code="00164779", rcept_no=RCEPT, report_name="r", published_at=PUBLISHED, chunks=big)
        base = build_deterministic_report(_facts(), generated_at=NOW)
        bundle = build_bundle(PLANS["SWOT"], report, base)
        self.assertLessEqual(sum(len(e["content"]) for e in bundle.payload), MAX_EVIDENCE_CHARS)
        self.assertTrue(any(i.startswith("metrics:") for i in bundle.ids), "확정 지표는 예산 조정에서 살아남아야 한다")

    def test_status_is_last_property_so_items_are_written_first(self):
        schema = section_schema(PLANS["BUSINESS_GROWTH"], ["a"])
        self.assertEqual(list(schema["properties"])[-1], "status")
        self.assertEqual(list(section_schema(PLANS["SWOT"], ["a"])["properties"])[-1], "status")

    def test_title_prefix_is_stripped_from_text(self):
        from ai.company_analysis.narrative import _clean

        self.assertEqual(_clean("산업과 경쟁 구도: 반도체는 핵심 부품이다.", "산업과 경쟁 구도"), "반도체는 핵심 부품이다.")
        self.assertEqual(_clean("**재무 추이 요약**: 성장했다.", "재무 추이 요약"), "성장했다.")
        self.assertEqual(_clean("그대로 둔다.", "산업과 경쟁 구도"), "그대로 둔다.")
        self.assertEqual(_clean("**기업 소개** 주력 사업은 메모리입니다.", "기업 소개"), "주력 사업은 메모리입니다.")
        self.assertEqual(
            _clean("연구개발에 주력합니다. (evidence_id: dart-business-report-d166a28e1ff87946fb4de6e47dfdf54b)"),
            "연구개발에 주력합니다.",
        )
        self.assertEqual(_clean("생산실적은 100%입니다. (dart-business-report-47c3f6c902348e450dea6881aef41497)"), "생산실적은 100%입니다.")
        self.assertEqual(_clean("매출은 97.1조원입니다. (metrics:00164779:financials, peers:00164779)"), "매출은 97.1조원입니다.")
        self.assertEqual(_clean("계약을 체결했습니다. dart-business-report-ec9124fccb97"), "계약을 체결했습니다.")

    def test_schema_restricts_citations_to_bundle_ids(self):
        schema = section_schema(PLANS["BUSINESS_CORE"], ["a", "b"])
        enum = schema["properties"]["units"]["properties"]["items"]["items"]["properties"]["citation_ids"]["items"]["enum"]
        self.assertEqual(enum, ["a", "b"])
        self.assertEqual(set(schema["required"]), {"status", "overview", "units"})
        swot = section_schema(PLANS["SWOT"], ["a"])
        self.assertEqual(set(swot["required"]), {"status", "strengths", "weaknesses", "opportunities", "threats"})


class EnricherTest(unittest.TestCase):
    def _enricher(self, outputs: dict, business_report=None) -> tuple[NarrativeEnricher, ScriptedClient]:
        client = ScriptedClient(outputs)
        reports = FakeReports(_business_report() if business_report is None else business_report)
        return NarrativeEnricher(client, reports), client

    def test_adds_narrative_blocks_and_source_card(self):
        outputs = {
            "INTRO": {"status": "AVAILABLE", "intro": {"text": "SK하이닉스는 메모리 반도체 기업으로 2025년 매출 97.1조원을 기록했습니다.", "citation_ids": ["e-overview", "metrics:00164779:financials"]}},
            "BUSINESS_CORE": {
                "status": "INSUFFICIENT_EVIDENCE",  # 내용이 있으면 status 를 무시해야 한다(실측 버그)
                "overview": {"text": "DRAM과 NAND 중심의 메모리 반도체 사업을 합니다.", "citation_ids": ["e-overview"]},
                "units": {"items": [{"text": "**DRAM**: AI 확산으로 HBM 수요가 증가했습니다.", "citation_ids": ["e-products"]}]},
            },
            "BUSINESS_GROWTH": {"status": "AVAILABLE", "growth": {"items": []}},
            "FINANCIALS": {"status": "INSUFFICIENT_EVIDENCE", "summary": {"text": "", "citation_ids": []}, "growth": {"items": []}, "profitability": {"items": []}, "health": {"items": []}},
            "COMPETITORS_MARKET": {
                "status": "AVAILABLE",
                "landscape": {"text": "2025년 세계 반도체 시장은 US$7,934억 규모이며 메모리는 26% 수준입니다.", "citation_ids": ["e-market"]},
                "edge": {"items": [{"text": "**점유율**: DRAM 시장점유율은 36.0%입니다.", "citation_ids": ["e-share"]}]},
            },
            "COMPETITORS_POSITION": {
                "status": "AVAILABLE",
                "positioning": {"items": [{"text": "**허구**: 시장점유율 57%로 1위입니다.", "citation_ids": ["e-share"]}]},
            },
            "SWOT": {
                "status": "AVAILABLE",
                **{
                    key: {"headline": f"{key} 제목", "summary": "근거에 기반한 요약입니다.", "citation_ids": ["e-overview"],
                          "items": [{"text": "환율변동위험에 노출되어 있습니다.", "citation_ids": ["e-risk"]}]}
                    for key in ("strengths", "weaknesses", "opportunities", "threats")
                },
            },
        }
        enricher, client = self._enricher(outputs)
        base = build_deterministic_report(_facts(), generated_at=NOW)
        report = enricher.enrich(_facts(), base)

        self.assertEqual([c[0] for c in client.calls], list(PLANS))
        self.assertIn("97.1조원", report.intro.text)
        self.assertEqual(report.sources[0].rcept_no, RCEPT)
        business = next(s for s in report.sections if s.type == "BUSINESS")
        self.assertEqual(business.blocks[0].kind, "text")
        self.assertEqual(business.blocks[0].title, "주요 사업 내용")
        self.assertEqual(business.blocks[1].title, "사업 부문별 상세", "서술 항목은 확정 블록보다 앞에 온다")
        self.assertEqual(business.blocks[2].kind, "table", "확정 데이터 블록은 서술 뒤에 온다")
        competitors = next(s for s in report.sections if s.type == "COMPETITORS")
        titles = [getattr(b, "title", None) for b in competitors.blocks]
        self.assertIn("경쟁 요소와 회사의 경쟁력", titles)
        self.assertEqual(competitors.blocks[0].kind, "text", "서술 문장이 항목보다 앞에 온다")
        self.assertEqual(competitors.blocks[-1].kind, "table", "확정 비교표는 맨 뒤에 남는다")
        self.assertNotIn("포지셔닝과 동일 산업 비교", titles, "근거에 없는 57% 항목은 버려져 블록이 비어야 한다")
        self.assertTrue(any("COMPETITORS_POSITION 서술에서 숫자가 근거와 맞지 않는 항목 1건" in w for w in report.warnings))
        self.assertTrue(any("FINANCIALS 서술: 근거 부족" in w for w in report.warnings))
        swot = next(s for s in report.sections if s.type == "SWOT")
        self.assertEqual(swot.blocks[0].kind, "swot")
        self.assertEqual(swot.blocks[0].threats.items[0].citations[0].source_id, "e-risk")
        self.assertEqual([s.type for s in report.sections], ["BUSINESS", "FINANCIALS", "COMPETITORS", "SWOT"])
        CompanyReport.model_validate_json(report.model_dump_json())

    def test_llm_failure_in_one_section_keeps_others(self):
        outputs = {"INTRO": {"status": "AVAILABLE", "intro": {"text": "소개 문장입니다.", "citation_ids": ["e-overview"]}}}
        enricher, _ = self._enricher(outputs)
        base = build_deterministic_report(_facts(), generated_at=NOW)
        report = enricher.enrich(_facts(), base)
        self.assertEqual(report.intro.text, "소개 문장입니다.")
        self.assertTrue(any("BUSINESS_CORE 서술 생성에 실패" in w for w in report.warnings))
        self.assertEqual(len([s for s in report.sections if s.type == "SWOT"]), 0)

    def test_without_business_report_returns_deterministic_with_warning(self):
        enricher, client = self._enricher({}, business_report=None)
        enricher._reports = FakeReports(None)
        base = build_deterministic_report(_facts(), generated_at=NOW)
        report = enricher.enrich(_facts(), base)
        self.assertEqual(client.calls, [])
        self.assertTrue(any("사업보고서 원문 근거가 없어" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
