from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from ai.news_intelligence.contracts import CoverageAssessment, NewsCandidate
from ai.news_intelligence.coverage import decide_external_search


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def candidate(article_id: str, *, days_old: int = 1) -> NewsCandidate:
    return NewsCandidate(
        article_id=article_id,
        origin="STORED",
        title=f"기사 {article_id}",
        publisher="매체",
        published_at=NOW - timedelta(days=days_old),
        url=f"https://example.test/{article_id}",
    )


COVERED = CoverageAssessment(company="COVERED", industry="COVERED", role="COVERED")


class CoverageRulesTest(unittest.TestCase):
    def test_fewer_than_five_candidates_requires_search(self):
        decision = decide_external_search([candidate(f"stored:{index}") for index in range(4)], COVERED, {"ROLE"}, NOW)

        self.assertTrue(decision.required)
        self.assertEqual(decision.reason, "유효 기사 5건 미만")
        self.assertEqual(decision.missing_scopes, [])

    def test_future_candidates_do_not_count_toward_search_gate(self):
        decision = decide_external_search(
            [candidate(f"stored:future:{index}", days_old=-1) for index in range(5)],
            COVERED,
            {"ROLE"},
            NOW,
        )

        self.assertTrue(decision.required)
        self.assertEqual(decision.reason, "유효 기사 5건 미만")

    def test_expired_candidates_do_not_count_toward_search_gate(self):
        candidates = [candidate(f"stored:expired:{index}", days_old=91) for index in range(4)]
        candidates.append(candidate("stored:recent", days_old=1))

        decision = decide_external_search(candidates, COVERED, {"ROLE"}, NOW)

        self.assertTrue(decision.required)
        self.assertEqual(decision.reason, "유효 기사 5건 미만")

    def test_newest_candidate_older_than_thirty_days_requires_search(self):
        decision = decide_external_search([candidate(f"stored:{index}", days_old=31) for index in range(5)], COVERED, {"ROLE"}, NOW)

        self.assertTrue(decision.required)
        self.assertEqual(decision.reason, "최신 기사가 30일 초과")

    def test_exact_thirty_day_newest_candidate_does_not_require_search(self):
        decision = decide_external_search([candidate(f"stored:{index}", days_old=30) for index in range(5)], COVERED, {"ROLE"}, NOW)

        self.assertFalse(decision.required)
        self.assertEqual(decision.reason, "검색 불필요")

    def test_missing_requested_scope_triggers_one_search_in_sorted_order(self):
        coverage = CoverageAssessment(company="INSUFFICIENT", industry="INSUFFICIENT", role="COVERED")
        decision = decide_external_search(
            [candidate(f"stored:{index}", days_old=index) for index in range(5)],
            coverage,
            {"ROLE", "INDUSTRY", "COMPANY"},
            NOW,
        )

        self.assertTrue(decision.required)
        self.assertEqual(decision.reason, "요청 범위 근거 부족")
        self.assertEqual(decision.missing_scopes, ["COMPANY", "INDUSTRY"])

    def test_reason_priority_is_stable_when_multiple_gates_apply(self):
        coverage = CoverageAssessment(company="INSUFFICIENT", industry="COVERED", role="COVERED")
        decision = decide_external_search([candidate("stored:1", days_old=31)], coverage, {"COMPANY"}, NOW)

        self.assertEqual(decision.reason, "유효 기사 5건 미만")
        self.assertEqual(decision.missing_scopes, ["COMPANY"])

    def test_rejects_naive_now(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            decide_external_search([candidate(f"stored:{index}") for index in range(5)], COVERED, {"ROLE"}, NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
