import unittest

from ai.supervisor.contracts import AgentResult, Evidence
from ai.supervisor.evidence import extract_evidence, extract_usage, merge_evidence


NEWS_RESULT = {
    "message": "AI 인프라 투자 확대가 직무와 연결됩니다.",
    "analysis": {
        "analysis_status": "COMPLETED",
        "signals": [
            {
                "signal_id": "signal-001",
                "summary": "기사 제목에서 AI 인프라 투자 확대를 확인.",
                "sources": [
                    {
                        "article_id": "stored:123",
                        "title": "AI 인프라 투자 확대",
                        "published_at": "2026-09-10T03:00:00Z",
                        "url": "https://example.com/article",
                    },
                    {
                        "article_id": "stored:124",
                        "title": "데이터센터 증설",
                        "published_at": "2026-09-11T03:00:00Z",
                        "url": "https://example.com/article-2",
                    },
                ],
            },
            {
                "signal_id": "signal-002",
                "summary": "같은 기사를 다른 신호에도 사용.",
                "sources": [
                    {
                        "article_id": "stored:123",
                        "title": "AI 인프라 투자 확대",
                        "published_at": "2026-09-10T03:00:00Z",
                        "url": "https://example.com/article",
                    }
                ],
            },
        ],
    },
}

JD_RESULT = {
    "context_id": "jctx",
    "company_name": "삼성전자",
    "position_name": "백엔드",
    "requirements": [
        {
            "requirement_id": "r1",
            "requirement": "대규모 트래픽 처리",
            "present_evidence": [
                {
                    "evidence_quote": "일 1억 건 요청을 처리",
                    "document_id": "doc-1",
                    "start_offset": 10,
                    "end_offset": 24,
                }
            ],
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
}

POSITION_RESULT = {
    "findings": [
        {
            "finding_id": "f1",
            "claim_type": "EXPERIENCE",
            "claim": {
                "quote": "일 1억 건 요청을 처리",
                "document_id": "doc-1",
                "start_offset": 10,
                "end_offset": 24,
            },
        }
    ]
}


class ExtractEvidenceTest(unittest.TestCase):
    def test_news_sources_become_article_evidence_without_duplicates(self):
        evidence = extract_evidence("news", NEWS_RESULT)

        self.assertEqual(
            [item.evidence_id for item in evidence],
            ["news:stored:123", "news:stored:124"],
        )
        self.assertEqual(evidence[0].source_type, "NEWS_ARTICLE")
        self.assertEqual(evidence[0].agent, "news")
        self.assertEqual(evidence[0].url, "https://example.com/article")
        self.assertEqual(evidence[0].date, "2026-09-10T03:00:00Z")

    def test_jd_yields_posting_and_document_quotes(self):
        evidence = extract_evidence("jd", JD_RESULT)

        self.assertEqual(evidence[0].source_type, "JOB_POSTING")
        self.assertEqual(evidence[0].source_id, "jctx")
        self.assertEqual(evidence[0].title, "삼성전자 / 백엔드")
        self.assertEqual(evidence[1].evidence_id, "doc:doc-1:10-24")
        self.assertEqual(evidence[1].source_type, "USER_DOCUMENT")
        self.assertEqual(evidence[1].excerpt, "일 1억 건 요청을 처리")

    def test_position_claims_become_document_evidence(self):
        evidence = extract_evidence("position", POSITION_RESULT)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].evidence_id, "doc:doc-1:10-24")
        self.assertEqual(evidence[0].agent, "position")

    def test_writing_and_malformed_results_yield_nothing(self):
        self.assertEqual(extract_evidence("writing", {"status": "REVISED"}), [])
        self.assertEqual(extract_evidence("news", {"analysis": "broken"}), [])
        self.assertEqual(extract_evidence("jd", {"requirements": [{"present_evidence": [{}]}]}), [])
        self.assertEqual(extract_evidence("jd", None), [])

    def test_usage_keeps_only_integer_counts(self):
        self.assertEqual(
            extract_usage(JD_RESULT),
            {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )
        self.assertIsNone(extract_usage(POSITION_RESULT))
        self.assertIsNone(extract_usage({"usage": {"model": "qwen", "ok": True}}))

    def test_merge_keeps_first_occurrence_across_agents(self):
        jd = AgentResult(agent="jd", status="SUCCESS", result=JD_RESULT,
                         evidence=extract_evidence("jd", JD_RESULT))
        position = AgentResult(agent="position", status="SUCCESS", result=POSITION_RESULT,
                               evidence=extract_evidence("position", POSITION_RESULT))

        merged = merge_evidence([jd, position])

        self.assertEqual(
            [item.evidence_id for item in merged],
            ["jd:jctx", "doc:doc-1:10-24"],
        )
        self.assertEqual(merged[1].agent, "jd")


class AgentResultContractTest(unittest.TestCase):
    def test_defaults_keep_legacy_shape_compatible(self):
        result = AgentResult(agent="jd", status="SUCCESS", result={})

        self.assertEqual(result.evidence, [])
        self.assertEqual(result.needs, [])
        self.assertIsNone(result.usage)
        self.assertIsNone(result.delegated_from)

    def test_needs_and_delegation_are_typed(self):
        result = AgentResult(
            agent="writing",
            status="SUCCESS",
            result={},
            needs=[{"agent": "news", "reason": "회사 변화 근거 없음"}],
            delegated_from="writing",
        )

        self.assertEqual(result.needs[0].agent, "news")
        with self.assertRaises(ValueError):
            AgentResult(agent="writing", status="SUCCESS", needs=[{"agent": "unknown", "reason": "x"}])
        with self.assertRaises(ValueError):
            Evidence(evidence_id="x", source_type="CONVERSATION", source_id="m1", agent="jd")


if __name__ == "__main__":
    unittest.main()
