"""합성 RSS로 정규화 규칙과 로컬 파일 출력을 검증한다. 실제 기사는 수집하지 않는다."""
import sys
import unittest
import tempfile
import csv
import json
from pathlib import Path

from data.news_poc.pipeline.normalize import parse_feed, merge_articles, safe_cell, export


def feed(items):
    """테스트용 item XML 문자열을 RSS channel로 감싸 UTF-8 bytes로 반환한다."""
    return ('<rss version="2.0"><channel>' + items + '</channel></rss>').encode()


def item(title='삼성전자 테스트 - 테스트신문', description='삼성전자 테스트 테스트신문',
         date='Fri, 04 Sep 2026 05:52:09 GMT', guid='one', link='https://news.google.com/rss/articles/one'):
    """오류 조건을 필드별로 바꿀 수 있는 합성 기사 XML을 만든다.

    테스트에서 제어하는 문자열만 받는다. XML 이스케이프를 제공하는 범용 생성기는 아니다.
    """
    return f'''<item><title>{title}</title><description>{description}</description>
    <pubDate>{date}</pubDate><guid>{guid}</guid><link>{link}</link>
    <source url="https://example.com">테스트신문</source></item>'''


class NormalizeTests(unittest.TestCase):
    """요약·원문 오인 방지, 중복 식별, CSV 출력 계약의 회귀 검증."""

    def test_title_repeat_is_not_summary_and_google_is_not_original(self):
        """제목 반복과 Google 경유 링크를 요약·원문으로 채우지 않는다."""
        row = parse_feed(feed(item()))[0]
        self.assertEqual(row['title'], '삼성전자 테스트')
        self.assertIsNone(row['description'])
        self.assertIsNone(row['original_url'])
        self.assertEqual(row['published_at'], '2026-09-04T05:52:09+00:00')
        self.assertEqual(row['publisher_url'], 'https://example.com')

    def test_unknown_description_needs_review(self):
        """제목 반복이 아니더라도 검토 전 설명은 요약으로 확정하지 않는다."""
        row = parse_feed(feed(item(description='알 수 없는 설명 문자열')))[0]
        self.assertIsNone(row['description'])
        self.assertEqual(row['description_status'], 'needs_review')

    def test_invalid_date_and_missing_title_are_explicit(self):
        """잘못된 날짜와 빈 제목을 행의 오류 목록으로 추적할 수 있다."""
        row = parse_feed(feed(item(date='bad', title='')))[0]
        self.assertIsNone(row['published_at'])
        self.assertIn('invalid_date', row['issues'])
        self.assertIn('missing_title', row['issues'])

    def test_duplicate_guid_merges_queries_but_not_different_articles(self):
        """같은 식별자의 출처는 합치되 다른 식별자의 기사는 유지한다."""
        rows = parse_feed(feed(item() + item(guid='two', link='https://example.com/article/2')))
        merged = merge_articles([(rows, 'query-1'), (rows, 'query-2')])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]['queries'], ['query-1', 'query-2'])

    def test_only_http_links_and_no_publisher_homepage_substitution(self):
        """잘못된 기사 링크를 언론사 홈페이지로 대신 채우지 않는다."""
        row = parse_feed(feed(item(link='javascript:alert(1)')))[0]
        self.assertIsNone(row['original_url'])
        self.assertIn('invalid_link', row['issues'])

    def test_google_url_query_does_not_create_duplicate(self):
        """GUID가 없을 때 Google URL의 부가 쿼리 차이는 같은 기사로 처리한다."""
        rows = parse_feed(feed(item(guid='', link='https://news.google.com/rss/articles/one?oc=5') +
                               item(guid='', link='https://news.google.com/rss/articles/one?oc=3')))
        self.assertEqual(len(merge_articles([(rows, 'q')])), 1)

    def test_reject_html_response_and_dtd(self):
        """동의 화면 등 HTML과 DTD 선언을 정상 RSS로 처리하지 않는다."""
        for payload in (b'<html><body>Consent</body></html>', b'<!DOCTYPE rss><rss><channel/></rss>'):
            with self.assertRaises(ValueError):
                parse_feed(payload)

    def test_spreadsheet_formula_is_escaped(self):
        """수식 문자열은 표시용으로 이스케이프하고 None은 빈 셀로 변환한다."""
        self.assertEqual(safe_cell('=HYPERLINK("bad")'), '\'=HYPERLINK("bad")')
        self.assertEqual(safe_cell(None), '')

    def test_export_and_repeat_are_idempotent_without_fake_ai_fields(self):
        """반복 출력 CSV가 같고 미실행 AI 값과 카테고리가 섞이지 않는다."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rss = root / 'synthetic.xml'
            rss.write_bytes(feed(item() + item()))
            out = root / 'out'
            first = export([rss], out)
            before = (out / 'news_samples.csv').read_bytes()
            second = export([rss], out)
            self.assertEqual(before, (out / 'news_samples.csv').read_bytes())
            self.assertEqual(first['unique_items'], 1)
            self.assertEqual(second['total_items'], 2)
            with (out / 'news_samples.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertNotIn('news_category', rows[0])
            self.assertEqual(rows[0]['related_business'], '')
            self.assertEqual(rows[0]['importance_score'], '')
            metadata = json.loads((out / 'collection_metadata.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata[0]['csv_row'], 2)

    def test_empty_input_does_not_create_sample_csv(self):
        """실제 입력이 없으면 샘플 CSV를 생성한 것처럼 보이게 하지 않는다."""
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                export([], Path(temp))
            self.assertFalse((Path(temp) / 'news_samples.csv').exists())


if __name__ == '__main__':
    unittest.main()
