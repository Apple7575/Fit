from __future__ import annotations

import unittest

import json
import tempfile
from pathlib import Path

from ai.scripts.evaluate_company_analysis import RetrievalCase, fact_cases, judge, load_gold, rank_of, recall_table
from ai.tests.company_analysis.test_deterministic import _facts


class FactCasesTest(unittest.TestCase):
    def test_cases_cover_core_metrics_with_db_truth(self):
        cases = fact_cases(_facts())
        by_metric = {c.metric: c for c in cases}
        self.assertEqual(set(by_metric), {"revenue", "operating_profit", "net_income", "employee_count", "operating_margin", "debt_ratio"})
        self.assertEqual(by_metric["revenue"].expected_tokens, ["97.1조원"])
        self.assertEqual(by_metric["revenue"].kind, "money")
        self.assertEqual(by_metric["employee_count"].expected_tokens, ["34,549명"])
        self.assertEqual(by_metric["operating_margin"].expected_tokens, ["48.6%"])
        self.assertEqual(by_metric["debt_ratio"].expected_tokens, ["45.9%"])
        self.assertIn("SK하이닉스", by_metric["revenue"].question)

    def test_judge_is_value_based(self):
        revenue = 97.147 * 1_000_000_000_000
        self.assertEqual(judge("2025년 매출은 97.1조원입니다.", "money", revenue, ["97.1조원"]), "correct")
        self.assertEqual(judge("매출은 97조 1,468억원입니다.", "money", revenue, ["97.1조원"]), "correct", "원문 표기도 값이 같으면 정답")
        self.assertEqual(judge("매출은 97,146,675백만원입니다.", "money", revenue, ["97.1조원"]), "correct")
        self.assertEqual(judge("매출은 66.2조원입니다.", "money", revenue, ["97.1조원"]), "wrong")
        self.assertEqual(judge("공시 자료(사업보고서·확정 지표)에서 이 질문에 답할 근거를 찾지 못했습니다.", "money", revenue, ["97.1조원"]), "abstain")
        self.assertEqual(judge("직원 수는 34,549명입니다.", "count", 34549, ["34,549명"]), "correct")
        self.assertEqual(judge("직원 수는 32,065명입니다.", "count", 34549, ["34,549명"]), "wrong")
        self.assertEqual(judge("영업이익률은 48.6%입니다.", "pct", 48.6, ["48.6%"]), "correct")
        self.assertEqual(judge("영업이익률은 48.7% 수준입니다.", "pct", 48.6, ["48.6%"]), "correct", "반올림 차이 0.1 은 허용")
        self.assertEqual(judge("영업이익률은 35.5%입니다.", "pct", 48.6, ["48.6%"]), "wrong")


class RecallTableTest(unittest.TestCase):
    def test_recall_and_mrr(self):
        cases = [
            RetrievalCase("c", "a", "s", "q1", {"bm25": 1, "hybrid": 2}),
            RetrievalCase("c", "b", "s", "q2", {"bm25": None, "hybrid": 4}),
            RetrievalCase("c", "d", "s", "q3", {"bm25": 8, "hybrid": None}),
        ]
        table = recall_table(cases, ["bm25", "hybrid"])
        self.assertEqual(table["bm25"]["recall@1"], round(1 / 3, 3))
        self.assertEqual(table["bm25"]["recall@8"], round(2 / 3, 3))
        self.assertEqual(table["hybrid"]["recall@3"], round(1 / 3, 3))
        self.assertEqual(table["hybrid"]["recall@5"], round(2 / 3, 3))
        self.assertEqual(table["bm25"]["mrr"], round((1 + 1 / 8) / 3, 3))


class GoldTest(unittest.TestCase):
    def test_rank_of_accepts_any_of_several_answers(self):
        class Hit:
            def __init__(self, i):
                self.chunk = type("C", (), {"evidence_id": i})()

        hits = [Hit("x"), Hit("b"), Hit("a")]
        self.assertEqual(rank_of(hits, "a"), 3)
        self.assertEqual(rank_of(hits, {"a", "b"}), 2, "여러 정답 중 먼저 나온 것의 순위")
        self.assertIsNone(rank_of(hits, {"z"}))

    def test_load_gold_keeps_only_gold_rows(self):
        rows = [
            {"corp_code": "c1", "question": "q1", "evidence_id": "a", "accepted_evidence_ids": ["a", "b"], "section_title": "s", "status": "GOLD"},
            {"corp_code": "c1", "question": "q2", "accepted_evidence_ids": ["d"], "status": "DROP"},
            {"corp_code": "c2", "question": "q3", "accepted_evidence_ids": ["e"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gold.jsonl"
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
            gold = load_gold(path)
        self.assertEqual(sorted(gold), ["c1", "c2"])
        self.assertEqual([c.question for c in gold["c1"]], ["q1"], "DROP 은 제외")
        self.assertEqual(gold["c1"][0].accepted(), {"a", "b"})
        self.assertEqual(gold["c2"][0].evidence_id, "e", "대표 문단이 없으면 첫 인정 문단")
        self.assertEqual(gold["c2"][0].source, "gold")


if __name__ == "__main__":
    unittest.main()
