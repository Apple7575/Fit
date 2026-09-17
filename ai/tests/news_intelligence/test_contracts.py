import unittest

from pydantic import ValidationError

from ai.news_intelligence.contracts import (
    NewsAnalysisRequest,
    NewsAnalysisResponse,
    NewsCandidate,
)


class NewsContractsTest(unittest.TestCase):
    def test_requires_both_context_identifiers(self):
        with self.assertRaises(ValidationError):
            NewsAnalysisRequest(
                instruction="최근 변화", job_context_id="ctx", corp_code=""
            )

    def test_rejects_non_dart_corp_code(self):
        with self.assertRaises(ValidationError):
            NewsAnalysisRequest(
                instruction="최근 변화", job_context_id="ctx", corp_code="123"
            )

    def test_candidate_keeps_observed_metadata(self):
        candidate = NewsCandidate(
            article_id="stored:1",
            origin="STORED",
            title="투자 확대",
            publisher="연합뉴스",
            published_at="2026-09-10T00:00:00Z",
            url="https://example.com/1",
            guid="g-1",
            importance_score=8.0,
        )

        self.assertEqual(candidate.origin, "STORED")
        self.assertEqual(candidate.importance_score, 8.0)

    def test_response_serializes_window_start_as_from(self):
        response = NewsAnalysisResponse.model_validate(
            {
                "message": "기사 근거를 분석했습니다.",
                "analysis": {
                    "analysis_status": "COMPLETED",
                    "company": {"corp_code": "00126380", "corp_name": "삼성전자"},
                    "window": {"from": "2026-06-18", "to": "2026-09-16"},
                    "signals": [],
                    "coverage": {
                        "company": "COVERED",
                        "industry": "COVERED",
                        "role": "COVERED",
                    },
                    "external_search": {"used": False, "reason": "저장 근거 충분"},
                },
            }
        )

        self.assertEqual(
            response.model_dump(mode="json")["analysis"]["window"],
            {"from": "2026-06-18", "to": "2026-09-16"},
        )

    def test_rejects_timezone_naive_published_at(self):
        with self.assertRaises(ValidationError):
            NewsCandidate(
                article_id="stored:1",
                origin="STORED",
                title="투자 확대",
                published_at="2026-09-10T00:00:00",
                url="https://example.com/1",
            )

    def test_accepts_timezone_aware_published_at(self):
        for published_at in ("2026-09-10T00:00:00Z", "2026-09-10T09:00:00+09:00"):
            with self.subTest(published_at=published_at):
                candidate = NewsCandidate(
                    article_id="stored:1",
                    origin="STORED",
                    title="투자 확대",
                    published_at=published_at,
                    url="https://example.com/1",
                )
                self.assertIsNotNone(candidate.published_at.utcoffset())
