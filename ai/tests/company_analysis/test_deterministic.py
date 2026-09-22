from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai.company_analysis.contracts import CompanyReport
from ai.company_analysis.deterministic import (
    build_deterministic_report,
    financial_table,
    growth,
    intro_text,
    investment_table,
    kpi_block,
    money_unit,
    peer_table,
    ratio_table,
    segment_share_table,
)
from ai.company_analysis.facts import (
    Activity,
    CompanyFacts,
    CompanyProfile,
    MetricPoint,
    PeerFacts,
    SegmentPoint,
    TextAttr,
)

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)
T = 1_000_000_000_000  # 1조원

PROFILE = CompanyProfile(
    corp_code="00164779",
    corp_name="SK하이닉스",
    industry_code="26",
    industry_name="전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업",
    induty_code="2612",
    ceo_name="곽노정",
    established_date="1949-10-15",
    address="경기도 이천시",
    homepage_url="www.skhynix.com",
    stock_code="000660",
)


def _metric(year: int, code: str, value: float, fs_div: str | None = "CFS") -> MetricPoint:
    return MetricPoint(fiscal_year=year, metric_code=code, value=value, fs_div=fs_div)


# 시드와 같은 자릿수: 2023 적자 → 2024 흑자 → 2025 최대 실적
HYNIX_METRICS = (
    _metric(2023, "revenue", 32.77 * T),
    _metric(2023, "operating_profit", -7.73 * T),
    _metric(2023, "net_income", -9.14 * T),
    _metric(2023, "total_liabilities", 46.8 * T),
    _metric(2023, "total_equity", 53.5 * T),
    _metric(2023, "employee_count", 32065, None),
    _metric(2024, "revenue", 66.19 * T),
    _metric(2024, "operating_profit", 23.47 * T),
    _metric(2024, "net_income", 19.8 * T),
    _metric(2024, "total_liabilities", 45.9 * T),
    _metric(2024, "total_equity", 73.9 * T),
    _metric(2024, "employee_count", 32390, None),
    _metric(2025, "revenue", 97.147 * T),
    _metric(2025, "operating_profit", 47.2 * T),
    _metric(2025, "net_income", 42.9 * T),
    _metric(2025, "total_liabilities", 55.4 * T),
    _metric(2025, "total_equity", 120.7 * T),
    _metric(2025, "employee_count", 34549, None),
    _metric(2025, "rd_ratio", 6.9, None),
    # 별도(OFS) 값이 함께 있어도 연결(CFS)을 우선해야 한다.
    _metric(2025, "revenue", 90.0 * T, "OFS"),
)

TEXTS = (
    TextAttr(2025, "main_business", 0, "당사는 DRAM 및 NAND를 중심으로 하는 메모리반도체를 주력으로 생산합니다."),
    TextAttr(2024, "main_business", 0, "오래된 문장"),
    TextAttr(2025, "main_product", 1, "NAND Flash"),
    TextAttr(2025, "main_product", 0, "DRAM"),
    TextAttr(2025, "main_product", 2, "CIS"),
    TextAttr(2025, "rd_field", 0, "메모리연구소"),
)

ACTIVITIES = (
    Activity("a1", 2025, "facility", "청주 P&T7", "패키징 공장", 19 * T, "20260310002821", None),
    Activity("a2", 2021, "corporate_invest", None, "일반투자", 3.8 * T, "20220322000590", "BCPE Pangea"),
    Activity("a3", 2021, "corporate_invest", None, "일반투자", 0.0, "20220322000590", "Inpria"),
)

PEERS = (
    PeerFacts("00126380", "삼성전자", 2025, 333.6 * T, 40.0 * T, 30.0 * T, 125000, ("반도체", "스마트폰")),
)


def _facts(**overrides) -> CompanyFacts:
    values = dict(profile=PROFILE, metrics=HYNIX_METRICS, texts=TEXTS, activities=ACTIVITIES, peers=PEERS)
    values.update(overrides)
    return CompanyFacts(**values)


class FactsTest(unittest.TestCase):
    def test_prefers_consolidated_and_derives_total_assets(self):
        facts = _facts()
        self.assertAlmostEqual(facts.metric(2025, "revenue"), 97.147 * T)
        self.assertAlmostEqual(facts.metric(2025, "total_assets"), (55.4 + 120.7) * T)
        self.assertEqual(facts.latest_year(), 2025)
        self.assertEqual(facts.texts_for("main_product"), ("DRAM", "NAND Flash", "CIS"))


class HelpersTest(unittest.TestCase):
    def test_growth_marks_sign_changes(self):
        self.assertEqual(growth(23.47 * T, -7.73 * T), "흑전")
        self.assertEqual(growth(-1.0, 2.0), "적전")
        self.assertEqual(growth(150.0, 100.0), 50.0)
        self.assertIsNone(growth(1.0, None))
        self.assertIsNone(growth(1.0, 0.0))

    def test_money_unit_by_company_size(self):
        self.assertEqual(money_unit(_facts())[0], "조원")
        small = _facts(metrics=(_metric(2025, "revenue", 350 * 100_000_000),))
        self.assertEqual(money_unit(small)[0], "억원")


class FinancialBlocksTest(unittest.TestCase):
    def test_financial_table_three_years_in_trillion_won(self):
        table = financial_table(_facts())
        self.assertEqual(table.columns, ["항목", "2023년", "2024년", "2025년"])
        self.assertEqual(table.unit, "조원")
        by_label = {row[0]: row[1:] for row in table.rows}
        self.assertEqual(by_label["매출액"], [32.8, 66.2, 97.1])
        self.assertEqual(by_label["영업이익"], [-7.7, 23.5, 47.2])
        self.assertEqual(by_label["자산총계"], [100.3, 119.8, 176.1])
        self.assertTrue(all(c.source_type == "COMPANY_METRIC" for c in table.citations))

    def test_ratio_table_matches_hand_calculation(self):
        table = ratio_table(_facts())
        by_label = {row[0]: row[1:] for row in table.rows}
        self.assertEqual(by_label["영업이익률(%)"], [-23.6, 35.5, 48.6])
        self.assertEqual(by_label["부채비율(%)"], [87.5, 62.1, 45.9])
        self.assertEqual(by_label["매출 성장률(%)"][1:], [102.0, 46.8])
        self.assertIsNone(by_label["매출 성장률(%)"][0])  # 2022 매출 없음
        self.assertEqual(by_label["영업이익 성장률(%)"][1], "흑전")
        self.assertEqual(by_label["R&D/매출(%)"], [None, None, 6.9])

    def test_kpi_block_has_yoy_and_note_for_sign_change(self):
        kpi = kpi_block(_facts())
        by_label = {item.label: item for item in kpi.items}
        self.assertEqual(by_label["2025년 매출"].value, 97.1)
        self.assertEqual(by_label["2025년 매출"].delta_pct, 46.8)
        self.assertEqual(by_label["직원 수"].value, 34549)
        self.assertEqual(by_label["직원 수"].unit, "명")
        kpi_2024 = kpi_block(_facts(metrics=tuple(m for m in HYNIX_METRICS if m.fiscal_year <= 2024)))
        profit = {item.label: item for item in kpi_2024.items}["2024년 영업이익"]
        self.assertIsNone(profit.delta_pct)
        self.assertEqual(profit.note, "흑전")


class BusinessBlocksTest(unittest.TestCase):
    def test_intro_uses_latest_main_business_sentence(self):
        intro = intro_text(_facts())
        self.assertIn("메모리반도체", intro.text)
        self.assertEqual(intro.citations[0].source_id, "00164779:main_business:2025")

    def test_intro_falls_back_to_profile_template(self):
        intro = intro_text(_facts(texts=()))
        self.assertIn("SK하이닉스", intro.text)
        self.assertIn("1949년", intro.text)
        self.assertEqual(intro.citations[0].source_type, "COMPANY_PROFILE")

    def test_segment_share_needs_two_segments(self):
        single = _facts(segments=(SegmentPoint(2025, "반도체 부문", "segment_revenue", 97 * T),))
        self.assertIsNone(segment_share_table(single))
        multi = _facts(
            segments=(
                SegmentPoint(2025, "DRAM", "segment_revenue", 65 * T),
                SegmentPoint(2025, "NAND", "segment_revenue", 30 * T),
                SegmentPoint(2025, "기타", "segment_revenue", 5 * T),
                SegmentPoint(2024, "DRAM", "segment_revenue", 40 * T),
            )
        )
        table = segment_share_table(multi)
        self.assertEqual(table.chart, "donut")
        self.assertEqual([row[0] for row in table.rows], ["DRAM", "NAND", "기타"])
        self.assertEqual([row[2] for row in table.rows], [65.0, 30.0, 5.0])

    def test_investment_table_skips_zero_amounts_and_orders_recent_first(self):
        table = investment_table(_facts())
        self.assertEqual(len(table.rows), 2)
        self.assertEqual(table.rows[0][0], "청주 P&T7")
        self.assertEqual(table.rows[0][1], "시설 투자")
        self.assertEqual(table.rows[1][0], "BCPE Pangea")
        self.assertEqual(table.citations[0].rcept_no, "20260310002821")


class PeerTest(unittest.TestCase):
    def test_peer_table_puts_company_first(self):
        table = peer_table(_facts())
        self.assertEqual(table.rows[0][0], "SK하이닉스")
        self.assertEqual(table.rows[1][0], "삼성전자")
        self.assertEqual(table.rows[1][2], 333.6)
        self.assertEqual(table.rows[1][3], 12.0)
        self.assertIsNone(peer_table(_facts(peers=())))


class AssembleTest(unittest.TestCase):
    def test_full_report_validates_and_round_trips(self):
        report = build_deterministic_report(_facts(), generated_at=NOW)
        self.assertEqual(report.fiscal_year, 2025)
        self.assertEqual([s.type for s in report.sections], ["BUSINESS", "FINANCIALS", "COMPETITORS"])
        kinds = [block.kind for block in report.sections[1].blocks]
        self.assertEqual(kinds, ["table", "table", "chart", "chart"])
        restored = CompanyReport.model_validate_json(report.model_dump_json())
        self.assertEqual(restored, report)

    def test_missing_data_becomes_warnings_not_errors(self):
        report = build_deterministic_report(_facts(activities=(), peers=(), segments=()), generated_at=NOW)
        self.assertEqual([s.type for s in report.sections], ["BUSINESS", "FINANCIALS"])
        self.assertTrue(any("비교 대상" in w for w in report.warnings))

    def test_no_data_at_all_raises(self):
        with self.assertRaises(ValueError):
            build_deterministic_report(_facts(metrics=(), texts=(), activities=(), peers=()), generated_at=NOW)


if __name__ == "__main__":
    unittest.main()
