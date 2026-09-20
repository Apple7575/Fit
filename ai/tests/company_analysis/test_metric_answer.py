from __future__ import annotations

import unittest

from ai.company_analysis.metric_answer import (
    DEBT_RATIO,
    OPERATING_MARGIN,
    MetricQuery,
    answer_matches,
    deterministic_answer,
    detect_metric_query,
    expected_value,
    money_values_in,
)
from ai.tests.company_analysis.test_deterministic import _facts, _metric

T = 1_000_000_000_000


class DetectTest(unittest.TestCase):
    def test_single_metric_with_year(self):
        q = detect_metric_query("SK하이닉스의 2025년 당기순이익은 얼마야?", _facts())
        self.assertEqual((q.code, q.fiscal_year, q.kind, q.year_in_question), ("net_income", 2025, "money", True))

    def test_defaults_to_latest_year(self):
        q = detect_metric_query("SK하이닉스 직원 수는 몇 명이야?", _facts())
        self.assertEqual((q.code, q.fiscal_year, q.year_in_question), ("employee_count", 2025, False))

    def test_longer_label_wins(self):
        self.assertEqual(detect_metric_query("2025년 영업이익률은?", _facts()).code, OPERATING_MARGIN)
        self.assertEqual(detect_metric_query("2025년 부채비율은 어느 정도야?", _facts()).code, DEBT_RATIO)
        self.assertEqual(detect_metric_query("ROE 알려줘", _facts()).code, "roe")

    def test_not_a_single_fact(self):
        self.assertIsNone(detect_metric_query("매출액과 영업이익을 알려줘", _facts()), "지표 둘")
        self.assertIsNone(detect_metric_query("최근 3년 매출 추이는?", _facts()), "흐름 질문")
        self.assertIsNone(detect_metric_query("2024년 대비 2025년 영업이익은?", _facts()), "연도 둘")
        self.assertIsNone(detect_metric_query("주력 제품이 뭐야?", _facts()), "지표 아님")
        self.assertIsNone(detect_metric_query("매출 비중이 가장 큰 사업은?", _facts()), "매출 비중은 지표가 아니다")


class ExpectedValueTest(unittest.TestCase):
    def test_direct_and_derived(self):
        facts = _facts()
        self.assertAlmostEqual(expected_value(facts, MetricQuery("revenue", "매출액", "money", 2025, True)), 97.147 * T)
        self.assertEqual(expected_value(facts, MetricQuery(DEBT_RATIO, "부채비율", "pct", 2025, True)), 45.9)
        self.assertIsNone(expected_value(facts, MetricQuery("revenue", "매출액", "money", 2019, True)))


class MoneyParseTest(unittest.TestCase):
    def test_formats_and_sign(self):
        self.assertEqual(money_values_in("97.1조원"), [97.1 * T])
        self.assertEqual(money_values_in("97조 1,468억원"), [97 * T + 1468 * 100_000_000])
        self.assertEqual(money_values_in("97,146,675백만원"), [97_146_675 * 1_000_000])
        self.assertEqual(money_values_in("-1,055.5억원"), [-1055.5 * 100_000_000])
        self.assertEqual(money_values_in("마이너스 1,055.5억원"), [-1055.5 * 100_000_000])
        self.assertEqual(money_values_in("2조 478억원"), [2 * T + 478 * 100_000_000])


class MatchTest(unittest.TestCase):
    def test_money_count_pct(self):
        money = MetricQuery("net_income", "당기순이익", "money", 2025, True)
        self.assertTrue(answer_matches("당기순이익은 2.0조원입니다.", money, 2_020_287_132_255))
        self.assertFalse(answer_matches("당기순이익은 2조 478억원입니다. FY'24 기준.", money, 2_020_287_132_255), "삼성화재 실측 오답")
        self.assertFalse(answer_matches("당기순이익은 -105,550억원입니다.", money, -105_550_462_258), "덕산테코피아 실측 단위 오류")
        self.assertTrue(answer_matches("당기순이익은 -1,055.5억원입니다.", money, -105_550_462_258))
        count = MetricQuery("employee_count", "직원 수", "count", 2025, True)
        self.assertTrue(answer_matches("34,549명입니다.", count, 34549))
        self.assertFalse(answer_matches("32,065명입니다.", count, 34549))
        ratio = MetricQuery(DEBT_RATIO, "부채비율", "pct", 2025, True)
        self.assertFalse(answer_matches("부채비율은 0.2932입니다.", ratio, 41.9), "NAVER 실측 오답")
        self.assertTrue(answer_matches("부채비율은 41.9%입니다.", ratio, 41.9))
        self.assertTrue(answer_matches("부채비율은 42.0% 수준입니다.", ratio, 41.9))


class DeterministicAnswerTest(unittest.TestCase):
    def test_answer_from_facts(self):
        facts = _facts()
        out = deterministic_answer(facts, MetricQuery("revenue", "매출액", "money", 2025, True))
        self.assertTrue(out.matched)
        self.assertIn("SK하이닉스의 2025년 매출액은 97.1조원입니다", out.text)
        self.assertEqual([c.source_id for c in out.citations], ["00164779:2025:revenue"])
        ratio = deterministic_answer(facts, MetricQuery(DEBT_RATIO, "부채비율", "pct", 2025, True))
        self.assertIn("45.9%", ratio.text)
        self.assertEqual(len(ratio.citations), 2, "파생 지표는 분자·분모 확정값을 인용")

    def test_negative_money_in_small_company_unit(self):
        small = _facts(metrics=(_metric(2025, "revenue", 350 * 100_000_000), _metric(2025, "net_income", -105_550_462_258)))
        out = deterministic_answer(small, MetricQuery("net_income", "당기순이익", "money", 2025, True))
        self.assertIn("-1,055.5억원", out.text)

    def test_missing_year_tells_available_years(self):
        out = deterministic_answer(_facts(), MetricQuery("revenue", "매출액", "money", 2019, True))
        self.assertFalse(out.matched)
        self.assertEqual(out.citations, [])
        self.assertIn("2019년 매출액은 확정 지표에 없습니다", out.text)
        self.assertIn("2023년~2025년", out.text)


if __name__ == "__main__":
    unittest.main()
