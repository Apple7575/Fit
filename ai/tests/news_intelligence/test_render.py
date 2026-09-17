import unittest

from ai.news_intelligence.contracts import NewsAnalysis
from ai.news_intelligence.render import render_news_message


def analysis(status="INSUFFICIENT_EVIDENCE", signals=None):
    return NewsAnalysis.model_validate({
        "analysis_status": status,
        "company": {"corp_code": "00126380", "corp_name": "삼성전자"},
        "window": {"from": "2026-06-18", "to": "2026-09-16"},
        "signals": signals or [],
        "coverage": {"company": "INSUFFICIENT", "industry": "INSUFFICIENT", "role": "INSUFFICIENT"},
        "external_search": {"used": True, "reason": "내부 검색 진단"},
    })


class NewsRenderTest(unittest.TestCase):
    def test_insufficient_analysis_explicitly_declines_to_infer_changes(self):
        self.assertEqual(render_news_message(analysis()),
                         "확인 가능한 최신 기사 근거가 부족해 기업·산업·직무 변화를 판단하지 않았습니다.")

    def test_completed_analysis_renders_only_validated_signal_fields(self):
        result = render_news_message(analysis("COMPLETED", [{
            "signal_id": "signal-001", "scope": "COMPANY", "title": "서비스 투자 확대",
            "summary": "제목에서 투자 확대가 확인됩니다.", "jd_relevance": "JD의 서비스 운영과 관련됩니다.",
            "preparation_checks": ["관련 경험 근거를 정리했는지 확인"], "evidence_level": "MEDIUM",
            "sources": [{"article_id": "stored:1", "origin": "STORED", "title": "서비스 투자 확대 기사",
                         "publisher": "언론사", "published_at": "2026-09-10T00:00:00Z", "url": "https://example.com/1"}],
        }]))
        self.assertIn("[COMPANY] 서비스 투자 확대", result)
        self.assertIn("JD의 서비스 운영과 관련됩니다.", result)
        self.assertNotIn("내부 검색 진단", result)

    def test_empty_completed_analysis_does_not_render_an_empty_success(self):
        self.assertIn("근거가 부족", render_news_message(analysis("COMPLETED")))
