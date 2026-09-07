"""실제 네트워크 없이 검색 구간과 서버 오류 처리 규칙을 검증한다."""
import sys
import unittest
import tempfile
import contextlib
import io
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from data.news_poc.pipeline.collect import build_plan, fetch, main
from data.news_poc.pipeline import collect


class CollectionTests(unittest.TestCase):
    """기간을 빠뜨리지 않고, 제한 응답을 재시도로 우회하지 않는지 확인한다."""

    def test_quality_gate_keeps_relevance_decisions_out(self):
        """회사명만 있는 제목·부고·약칭을 관련성 규칙으로 임의 제외하지 않는다."""
        rows = [dict(title=t, rss_link='https://news.google.com/rss/articles/test')
                for t in ['삼성전자', '[부고] 전직 직원 모친상', '삼전 신제품 공개']]
        ready, rejected = collect.screen_quality(rows)
        self.assertEqual(ready, rows)
        self.assertEqual(rejected, [])

    def test_quality_gate_separates_missing_title_and_broken_link(self):
        """결함이 있는 행은 원본을 유지하면서 사유와 함께 별도 출력한다."""
        rows = [dict(title=' ',rss_link='https://example.com/a'), dict(title='기사',rss_link='javascript:bad')]
        ready, rejected = collect.screen_quality(rows)
        self.assertEqual(ready, [])
        self.assertEqual(rejected[0]['quality_issues'], ['missing_title'])
        self.assertEqual(rejected[1]['quality_issues'], ['invalid_link'])

    def test_quality_gate_only_recognizes_verified_listing_url(self):
        """확보된 종목 뉴스 목록 URL만 제외하고 같은 매체의 개별 기사는 유지한다."""
        rows = [dict(title='삼성전자',rss_link='https://stock.mk.co.kr/price/news/KRG610000397'),
                dict(title='기사',rss_link='https://stock.mk.co.kr/news/view/123')]
        ready, rejected = collect.screen_quality(rows)
        self.assertEqual(ready, rows[1:])
        self.assertEqual(rejected[0]['quality_issues'], ['known_listing_page'])

    def test_daily_ranges_cover_requested_period(self):
        """종료일 미포함인 날짜 구간을 하루씩 정확히 생성한다."""
        plan = build_plan(date(2026, 8, 6), date(2026, 9, 5))
        daily = [p for p in plan if p['kind'] == 'daily']
        self.assertEqual(len(daily), 31)
        self.assertIn('after:2026-08-05 before:2026-08-06', daily[0]['query'])
        self.assertIn('before:2026-09-05', daily[-1]['query'])
        self.assertEqual(len({p['id'] for p in plan}), len(plan))
        self.assertEqual(len(plan), len(daily))

    def test_company_name_is_the_only_search_term(self):
        """기업이 달라도 날짜 외에 사업·언론사 조건은 추가하지 않는다."""
        plan = build_plan(date(2026, 9, 4), date(2026, 9, 5), 'SK하이닉스')
        self.assertEqual(len(plan), 2)
        self.assertTrue(all(p['query'].startswith('SK하이닉스 after:') for p in plan))

    def test_snapshot_comparison_does_not_call_absent_deleted(self):
        """재조회 차이는 관측 차이로 기록하고 기사 삭제나 신규 발행으로 단정하지 않는다."""
        old=[dict(article_key='same',title='전 제목'),dict(article_key='absent',title='미관측')]
        new=[dict(article_key='same',title='수정 제목'),dict(article_key='added',title='추가')]
        result=collect.compare_snapshots(old,new)
        self.assertEqual(result['newly_observed_keys'],['added'])
        self.assertEqual(result['not_reobserved_keys'],['absent'])
        self.assertEqual(result['changed'][0]['fields'],['title'])

    def test_kst_filter_dedup_and_saturation(self):
        """UTC 날짜가 달라도 KST 경계를 적용하고 원본 100건 포화는 필터 전에 표시한다."""
        plan = build_plan(date(2026, 9, 4), date(2026, 9, 5))
        def row(key, stamp):
            return dict(article_key=key, published_at=stamp, title=key)
        first = [row('start', '2026-09-03T15:00:00+00:00')] * 98 + [
            row('before', '2026-09-03T14:59:59+00:00'), row('missing', None)]
        second = [row('start', '2026-09-03T15:00:00+00:00'),
                  row('last', '2026-09-04T14:59:59+00:00'),
                  row('end', '2026-09-04T15:00:00+00:00')]
        rows, report = collect.summarize([(plan[0], first), (plan[1], second)],
                                        date(2026, 9, 4), date(2026, 9, 5), plan)
        self.assertEqual({r['article_key'] for r in rows}, {'start', 'last'})
        self.assertEqual(report['saturated_queries'], [plan[0]['query']])
        self.assertEqual(report['invalid_date_observations'], 1)
        self.assertTrue(report['all_queries_succeeded'])
        self.assertFalse(collect.summarize([], date(2026, 9, 4), date(2026, 9, 5), plan)[1]['all_queries_succeeded'])

    def test_reversed_range_rejected(self):
        """잘못된 구간은 요청 전에 거부한다."""
        with self.assertRaises(ValueError):
            build_plan(date(2026, 9, 5), date(2026, 8, 6))

    def test_rate_limit_is_not_retried(self):
        """429는 한 번의 요청 후 호출자에게 전달한다."""
        error = HTTPError('https://news.google.com', 429, 'limited', {}, None)
        self.addCleanup(error.close)
        opener = Mock(side_effect=error)
        with self.assertRaises(HTTPError):
            fetch('https://news.google.com', opener=opener, sleep=Mock())
        self.assertEqual(opener.call_count, 1)

    def test_server_failure_has_bounded_backoff(self):
        """5xx가 지속되면 총 3회 시도 후 실패를 반환한다."""
        error = HTTPError('https://news.google.com', 503, 'unavailable', {}, None)
        self.addCleanup(error.close)
        opener = Mock(side_effect=error)
        sleep = Mock()
        with self.assertRaises(HTTPError):
            fetch('https://news.google.com', opener=opener, sleep=sleep)
        self.assertEqual(opener.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 10])

    def test_resume_reuses_verified_xml_without_network(self):
        """해시가 일치하는 성공 응답은 재개 실행 시 새로 요청하지 않는다."""
        payload = b'<rss><channel><item><title>synthetic</title></item></channel></rss>'
        with tempfile.TemporaryDirectory() as temp:
            argv = ['collect', '--start', '2026-08-06', '--end', '2026-08-07',
                    '--out', temp, '--limit', '1']
            with patch('sys.argv', argv), patch('data.news_poc.pipeline.collect.fetch', return_value=(payload, 200, 'https://news.google.com')) as request:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 0)
                    self.assertEqual(main(), 0)
                self.assertEqual(request.call_count, 1)
