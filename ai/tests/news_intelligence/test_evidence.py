from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from ai.news_intelligence.contracts import NewsCandidate
from ai.news_intelligence.evidence import calculate_evidence_level, deduplicate_candidates


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def candidate(
    article_id: str,
    *,
    url: str = "https://example.test/article",
    guid: str | None = None,
    title: str = "기사 제목",
    publisher: str | None = "매체",
    days_old: int = 1,
) -> NewsCandidate:
    return NewsCandidate(
        article_id=article_id,
        origin="STORED",
        title=title,
        publisher=publisher,
        published_at=NOW - timedelta(days=days_old),
        url=url,
        guid=guid,
    )


class EvidenceRulesTest(unittest.TestCase):
    def test_deduplicates_by_url_then_guid_then_normalized_title(self):
        result = deduplicate_candidates([
            candidate("stored:1", url="https://a.test/1#summary", guid=" g1 ", title="AI 투자 확대"),
            candidate("external:1", url="https://a.test/1", guid=None, title="다른 표기"),
            candidate("external:2", url="https://b.test/2", guid="G1", title="재전송"),
            candidate("external:3", url="https://c.test/3", guid=None, title="  ai   투자 확대 "),
        ])

        self.assertEqual([item.article_id for item in result], ["stored:1"])

    def test_deduplicates_nfkc_equivalent_titles(self):
        result = deduplicate_candidates([
            candidate("stored:1", url="https://a.test/1", title="ＡＩ　투자 확대"),
            candidate("external:1", url="https://b.test/2", title="AI 투자 확대"),
        ])

        self.assertEqual([item.article_id for item in result], ["stored:1"])

    def test_recent_independent_publishers_are_high_evidence(self):
        sources = [
            candidate("stored:1", publisher="A", days_old=5),
            candidate("stored:2", publisher=" b ", days_old=12),
        ]

        self.assertEqual(calculate_evidence_level(sources, NOW), "HIGH")

    def test_exact_thirty_day_boundary_is_recent(self):
        sources = [candidate("stored:1", publisher="A", days_old=30)]

        self.assertEqual(calculate_evidence_level(sources, NOW), "MEDIUM")

    def test_exact_ninety_day_boundary_is_valid_but_not_recent(self):
        sources = [candidate("stored:1", publisher=None, days_old=90)]

        self.assertEqual(calculate_evidence_level(sources, NOW), "LOW")

    def test_future_and_expired_articles_are_insufficient(self):
        future = candidate("stored:future", days_old=-1)
        expired = candidate("stored:expired", days_old=91)

        self.assertEqual(calculate_evidence_level([future, expired], NOW), "INSUFFICIENT")

    def test_rejects_naive_now(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            calculate_evidence_level([candidate("stored:1")], NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
