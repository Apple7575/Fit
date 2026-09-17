"""staged → curated. 헤더가 DB 와 같고, 못 넣는 행은 사유와 함께 빠져야 한다."""
from __future__ import annotations

import unittest

from pipeline.news import curate, flyway
from pipeline.news.schema import PROVIDER, SEED_FIELDS


def staged(**overrides):
    row = {
        "article_key": "k1", "collection_run_id": "run1", "source_raw_file": "day1.xml",
        "source_record_index": "0", "corp_code": "00126380", "query_company_name": "삼성전자",
        "corp_map_method": "exact_name", "corp_map_reason": "",
        "title": "삼성전자 신규 투자", "title_checksum": "c1",
        "description": "", "description_raw": "본문", "description_status": "needs_review",
        "original_url": "https://a.test/1", "original_url_norm": "https://a.test/1",
        "original_url_status": "rss_direct_unverified",
        "rss_link": "https://news.google.com/x", "google_url": "https://news.google.com/x",
        "guid": "g1", "image_url": "", "provider": PROVIDER,
        "publisher": "테스트일보", "publisher_url": "https://news.example.test",
        "published_at": "2026-09-05T23:30:00+00:00", "published_at_raw": "raw",
        "published_date_kst": "2026-09-06", "collected_at": "2026-09-06T00:10:00+00:00",
        "language": "ko", "country": "KR", "stage_status": "staged",
        "is_duplicate": "false", "duplicate_of": "", "duplicate_rule": "",
        "quality_issues": "", "stage_schema_version": "news-staged-v1",
    }
    row.update(overrides)
    return row


class CurateTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = flyway.load()

    def build(self, rows, **kwargs):
        return curate.build(rows, self.schema, **kwargs)

    def test_헤더가_DB_컬럼과_같고_id_는_없다(self):
        result = self.build([staged()])
        self.assertEqual(result.summary["header"], SEED_FIELDS)
        self.assertNotIn("id", result.rows[0])

    def test_source_는_기본적으로_publisher_다(self):
        result = self.build([staged()])
        self.assertEqual(result.rows[0]["source"], "테스트일보")
        self.assertEqual(result.summary["source_column_maps_to"], "publisher")

    def test_source_를_provider_로_바꿀_수_있다(self):
        result = self.build([staged()], source_column="provider")
        self.assertEqual(result.rows[0]["source"], PROVIDER)

    def test_AI_컬럼은_비운다(self):
        # V16 이 news_category · related_business · analyzed_at 을 지워 하나만 남았다.
        row = self.build([staged()]).rows[0]
        self.assertEqual(row["importance_score"], "")
        for column in ("news_category", "related_business", "analyzed_at", "description"):
            self.assertNotIn(column, row, f"{column} 은 V16 이 지운 컬럼이다")

    def test_guid_를_시드로_옮긴다(self):
        """V17 이 더한 확정 ERD 의 중복 방지 키. staged 의 값을 그대로 넘긴다."""
        self.assertEqual(self.build([staged()]).rows[0]["guid"], "g1")

    def test_guid_가_없으면_빈_칸이다(self):
        """RSS 가 guid 를 주지 않는 경우가 있다. 지어내지 않고 NULL 로 둔다 —
        UNIQUE 가 (corp_code, guid) 라 NULL 인 행끼리는 서로 충돌하지 않는다."""
        self.assertEqual(self.build([staged(guid="")]).rows[0]["guid"], "")

    def test_기업코드_없는_행은_넣지_않고_사유를_남긴다(self):
        result = self.build([staged(corp_code="", corp_map_reason="not_in_company_universe",
                                    stage_status="unresolved_corp")])
        self.assertEqual(result.rows, [])
        self.assertTrue(result.dropped[0]["drop_reason"].startswith("corp_code_unresolved:"))

    def test_중복_행은_넣지_않는다(self):
        result = self.build([staged(is_duplicate="true", stage_status="duplicate")])
        self.assertEqual(result.summary["drop_reasons"], {"staged_duplicate": 1})

    def test_같은_기업_같은_URL_은_한_번만(self):
        result = self.build([staged(article_key="k1"), staged(article_key="k2")])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.dropped[0]["drop_reason"], "duplicate_corp_url")

    def test_URL_이_없으면_중복으로_막지_않는다(self):
        # DB 의 부분 UNIQUE 인덱스도 original_url IS NOT NULL 일 때만 걸린다.
        # 언론사 주소가 없으면 구글 뉴스 링크로 채우므로, "URL 이 없다" 를 만들려면
        # rss_link·google_url 까지 비워야 한다.
        result = self.build([staged(article_key="k1", original_url="", rss_link="", google_url=""),
                             staged(article_key="k2", original_url="", rss_link="", google_url="")])
        self.assertEqual(len(result.rows), 2)

    def test_언론사_주소가_없으면_구글_링크를_쓴다(self):
        # 팀장 판단 2026-09-15. RSS 가 언론사 주소를 주지 않아 화면에서 기사로
        # 보낼 방법이 없었다. 구글 링크도 클릭하면 기사로 간다.
        result = self.build([staged(original_url="", rss_link="https://news.google.com/rss/articles/AAA")])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["original_url"], "https://news.google.com/rss/articles/AAA")
        self.assertEqual(result.summary["url_publisher_rows"], 0)
        self.assertEqual(result.summary["url_google_news_rows"], 1)

    def test_언론사_주소가_있으면_그것을_쓴다(self):
        result = self.build([staged(original_url="https://example.com/news/1",
                                    rss_link="https://news.google.com/rss/articles/AAA")])
        self.assertEqual(result.rows[0]["original_url"], "https://example.com/news/1")
        self.assertEqual(result.summary["url_publisher_rows"], 1)
        self.assertEqual(result.summary["url_google_news_rows"], 0)

    def test_길이_위반은_자르지_않고_뺀다(self):
        result = self.build([staged(title="가" * 501)])
        self.assertEqual(result.rows, [])
        self.assertIn("title_exceeds_500", result.dropped[0]["drop_reason"])

    def test_collected_at_이_없으면_NOT_NULL_위반으로_뺀다(self):
        result = self.build([staged(collected_at="")])
        self.assertEqual(result.summary["drop_reasons"],
                         {"collected_at_missing_violates_not_null": 1})

    def test_collected_at_대체값을_줄_수_있다(self):
        result = self.build([staged(collected_at="")],
                            collected_at_fallback="2026-09-06T00:00:00+00:00")
        self.assertEqual(result.rows[0]["collected_at"], "2026-09-06T00:00:00+00:00")

    def test_published_at_이_null_이어도_넣는다(self):
        # DB 가 NULL 을 허용하고, 그 경우 어떤 API 에도 나가지 않는다는 사실이 V12 에 적혀 있다.
        result = self.build([staged(published_at="", published_date_kst="")])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.summary["published_at_null_rows"], 1)

    def test_정렬이_결정적이다(self):
        rows = [
            staged(article_key="k2", corp_code="00126380", original_url="https://a.test/2",
                   published_at="2026-09-05T23:30:00+00:00"),
            staged(article_key="k1", corp_code="00126380", original_url="https://a.test/1",
                   published_at="2026-09-05T23:30:00+00:00"),
            staged(article_key="k3", corp_code="00000000", original_url="https://a.test/3"),
        ]
        first = [r["_article_key"] for r in self.build(rows).rows]
        second = [r["_article_key"] for r in self.build(list(reversed(rows))).rows]
        self.assertEqual(first, second)
        self.assertEqual(first[0], "k3")     # corp_code 오름차순

    def test_입력이_없으면_행이_없다(self):
        result = self.build([])
        self.assertEqual(result.rows, [])
        self.assertEqual(result.summary["seed_rows"], 0)


if __name__ == "__main__":
    unittest.main()
