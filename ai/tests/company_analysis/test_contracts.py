from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from ai.company_analysis.contracts import (
    SECTION_TITLES,
    BulletsBlock,
    ChartBlock,
    ChatRequest,
    ChatResponse,
    Citation,
    CompanyReport,
    KpiBlock,
    ReportSection,
    ReportStatus,
    SwotBlock,
    TableBlock,
    TextBlock,
)

NOW = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
DART = Citation(
    source_type="DART_BUSINESS_REPORT",
    source_id="dart-business-report-abc",
    rcept_no="20260310000123",
)
METRIC = Citation(source_type="COMPANY_METRIC", source_id="00164779:2025:revenue")


def _text(title: str | None = None) -> TextBlock:
    return TextBlock(title=title, text="설명", citations=[DART])


def _bullets() -> BulletsBlock:
    return BulletsBlock(items=[{"text": "항목", "citations": [DART]}])


def _quadrant() -> dict:
    return {
        "headline": "제목",
        "summary": "요약",
        "items": [{"text": "근거 항목", "citations": [DART], "perspective": "JOB"}],
    }


def _report(sections: list[ReportSection] | None = None) -> CompanyReport:
    if sections is None:
        sections = [
            ReportSection(type="BUSINESS", title=SECTION_TITLES["BUSINESS"], blocks=[_text()]),
            ReportSection(
                type="FINANCIALS",
                title=SECTION_TITLES["FINANCIALS"],
                blocks=[
                    TableBlock(
                        title="재무 추이",
                        columns=["항목", "2023년", "2024년", "2025년"],
                        rows=[["매출액", 32.8, 66.2, 97.1]],
                        unit="조원",
                        citations=[METRIC],
                    ),
                    KpiBlock(items=[{"label": "2025년 매출", "value": 97.1, "unit": "조원", "delta_pct": 46.8}]),
                ],
            ),
            ReportSection(type="COMPETITORS", title=SECTION_TITLES["COMPETITORS"], blocks=[_bullets()]),
            ReportSection(
                type="SWOT",
                title=SECTION_TITLES["SWOT"],
                blocks=[
                    SwotBlock(
                        strengths=_quadrant(),
                        weaknesses=_quadrant(),
                        opportunities=_quadrant(),
                        threats=_quadrant(),
                    )
                ],
            ),
        ]
    return CompanyReport(
        corp_code="00164779",
        corp_name="SK하이닉스",
        fiscal_year=2025,
        generated_at=NOW,
        intro=_text(),
        sections=sections,
        sources=[
            {
                "rcept_no": "20260310000123",
                "title": "사업보고서 (2025.12)",
                "published_at": NOW,
                "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310000123",
            }
        ],
    )


class ContractsTest(unittest.TestCase):
    def test_full_report_round_trips_through_json(self):
        report = _report()
        restored = CompanyReport.model_validate_json(report.model_dump_json())
        self.assertEqual(restored, report)
        self.assertEqual([s.type for s in restored.sections], ["BUSINESS", "FINANCIALS", "COMPETITORS", "SWOT"])

    def test_block_kind_discriminates_union(self):
        section = ReportSection.model_validate(
            {
                "type": "BUSINESS",
                "title": "사업 내용",
                "blocks": [
                    {"kind": "text", "text": "설명", "citations": [DART.model_dump()]},
                    {"kind": "kpi", "items": [{"label": "매출", "value": 1}]},
                ],
            }
        )
        self.assertIsInstance(section.blocks[0], TextBlock)
        self.assertIsInstance(section.blocks[1], KpiBlock)

    def test_narrative_blocks_require_citations(self):
        with self.assertRaises(ValidationError):
            TextBlock(text="근거 없는 문장", citations=[])
        with self.assertRaises(ValidationError):
            BulletsBlock(items=[{"text": "근거 없는 항목", "citations": []}])

    def test_table_rows_must_match_columns(self):
        with self.assertRaises(ValidationError):
            TableBlock(title="표", columns=["a", "b"], rows=[["only one"]])

    def test_chart_series_must_match_categories(self):
        ChartBlock(
            title="추이",
            chart="bar",
            categories=["2023", "2024"],
            series=[{"name": "매출", "values": [1, 2]}],
        )
        with self.assertRaises(ValidationError):
            ChartBlock(
                title="추이",
                chart="bar",
                categories=["2023", "2024"],
                series=[{"name": "매출", "values": [1]}],
            )

    def test_sections_must_be_unique_and_ordered(self):
        business = ReportSection(type="BUSINESS", title="사업", blocks=[_text()])
        financials = ReportSection(type="FINANCIALS", title="재무", blocks=[_text()])
        with self.assertRaises(ValidationError):
            _report([financials, business])
        with self.assertRaises(ValidationError):
            _report([business, business])
        _report([business, financials])  # 일부 섹션만 있어도 순서만 맞으면 허용

    def test_news_is_not_a_citation_source(self):
        with self.assertRaises(ValidationError):
            Citation(source_type="NEWS_ARTICLE", source_id="1")

    def test_corp_code_and_rcept_no_formats(self):
        with self.assertRaises(ValidationError):
            ReportStatus(corp_code="1234", status="READY", updated_at=NOW)
        with self.assertRaises(ValidationError):
            Citation(source_type="DART_BUSINESS_REPORT", source_id="x", rcept_no="123")

    def test_chat_request_and_response(self):
        request = ChatRequest(corp_code="00164779", message="  HBM 매출 비중은?  ")
        self.assertEqual(request.message, "HBM 매출 비중은?")
        with self.assertRaises(ValidationError):
            ChatRequest(corp_code="00164779", message="   ")
        message = {"message_id": "m1", "role": "ASSISTANT", "content": "답", "created_at": NOW.isoformat()}
        response = ChatResponse(
            conversation_id="c1", corp_code="00164779", report_stage="FULL",
            user_message={**message, "role": "USER"},
            assistant_message={**message, "needs": [{"agent": "news", "reason": "최근 뉴스가 필요합니다."}]},
        )
        self.assertEqual(response.assistant_message.needs[0].agent, "news")
        with self.assertRaises(ValidationError):
            ChatResponse(
                conversation_id="c1", corp_code="00164779", report_stage="FULL",
                user_message={**message, "role": "USER"},
                assistant_message={**message, "needs": [{"agent": "weather", "reason": "x"}]},
            )


if __name__ == "__main__":
    unittest.main()
