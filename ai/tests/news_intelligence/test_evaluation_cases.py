import json
import unittest
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from ai.news_intelligence.contracts import (
    NewsAnalysisRequest,
    NewsAnalysisResponse,
    NewsCandidate,
)
from ai.news_intelligence.evidence import calculate_evidence_level
from ai.news_intelligence.render import render_news_message


EVALUATION_ROOT = Path(__file__).parents[2] / "evals" / "news_intelligence"
SCHEMA = EVALUATION_ROOT / "schema.json"
CASES = EVALUATION_ROOT / "cases"
EXPECTED_CASES = {
    "company-change-001.json",
    "industry-gap-001.json",
    "role-change-001.json",
    "insufficient-001.json",
    "conflicting-sources-001.json",
}


class NewsIntelligenceEvaluationCasesTest(unittest.TestCase):
    def test_all_evaluation_cases_match_contracts(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "news-intelligence-evaluation-v1")
        self.assertEqual(
            schema["required"],
            ["status", "request", "stored_candidates", "external_candidates", "expected_response"],
        )

        paths = sorted(CASES.glob("*.json"))
        self.assertEqual({path.name for path in paths}, EXPECTED_CASES)
        for path in paths:
            with self.subTest(case=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(set(schema["required"]) - payload.keys(), set())
                self.assertEqual(payload["status"], "DRAFT")
                NewsAnalysisRequest.model_validate(payload["request"])
                for candidate in payload["stored_candidates"] + payload["external_candidates"]:
                    NewsCandidate.model_validate(candidate)
                response = NewsAnalysisResponse.model_validate(payload["expected_response"])
                candidates = [
                    NewsCandidate.model_validate(candidate)
                    for candidate in payload["stored_candidates"] + payload["external_candidates"]
                ]
                candidates_by_id = {
                    candidate.article_id: candidate for candidate in candidates
                }
                analysis_now = datetime.combine(
                    response.analysis.window.to, time.max, tzinfo=timezone.utc,
                )
                for signal in response.analysis.signals:
                    for source in signal.sources:
                        self.assertIn(source.article_id, candidates_by_id)
                        self.assertEqual(source, candidates_by_id[source.article_id])
                    self.assertEqual(
                        signal.evidence_level,
                        calculate_evidence_level(signal.sources, analysis_now),
                    )

                stored_valid_count = sum(
                    candidate.origin == "STORED"
                    and timedelta(0) <= analysis_now - candidate.published_at <= timedelta(days=90)
                    for candidate in candidates
                )
                if stored_valid_count < 5:
                    self.assertEqual(
                        response.analysis.coverage.model_dump(),
                        {"company": "INSUFFICIENT", "industry": "INSUFFICIENT", "role": "INSUFFICIENT", "requested_scopes": ["COMPANY", "INDUSTRY", "ROLE"]},
                    )
                    self.assertEqual(response.analysis.external_search.used, True)
                    self.assertEqual(response.analysis.external_search.reason, "유효 기사 5건 미만")

                expected_status = "COMPLETED" if candidates else "INSUFFICIENT_EVIDENCE"
                self.assertEqual(response.analysis.analysis_status, expected_status)
                self.assertEqual(response.message, render_news_message(response.analysis))
                self.assertEqual(
                    response.analysis.window.from_date.toordinal(),
                    response.analysis.window.to.toordinal() - 90,
                )


if __name__ == "__main__":
    unittest.main()
