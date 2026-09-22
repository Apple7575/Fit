from __future__ import annotations

from datetime import date, datetime, timezone
import http.client
import io
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import unittest
from unittest.mock import Mock, patch

from ai.news_intelligence.search_provider import (
    ExternalSearchUnavailable,
    GoogleNewsRssProvider,
)


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
URL = "https://news.google.com/rss/search?q=sensitive-query"
REQUEST = dict(
    corp_name="삼성전자",
    position_name="백엔드 개발자",
    missing_scopes=["INDUSTRY"],
    from_date=date(2026, 6, 18),
    to_date=date(2026, 9, 16),
    limit=20,
)
RSS_BYTES = """<?xml version=\"1.0\"?>
<rss><channel>
  <item>
    <title>과거 기사 - 연합뉴스</title>
    <link>https://example.test/older</link>
    <guid>older</guid>
    <pubDate>Mon, 14 Sep 2026 00:00:00 +0000</pubDate>
    <source url=\"https://yna.co.kr\">연합뉴스</source>
  </item>
  <item>
    <title>최신 기사 - 매일경제</title>
    <link>https://example.test/newer</link>
    <guid>newer</guid>
    <pubDate>Tue, 15 Sep 2026 00:00:00 +0000</pubDate>
    <source url=\"https://mk.co.kr\">매일경제</source>
  </item>
  <item>
    <title>시간대 없는 기사</title>
    <link>https://example.test/naive</link>
    <guid>naive</guid>
    <pubDate>Tue, 15 Sep 2026 00:00:00</pubDate>
  </item>
  <item>
    <title>깨진 링크 기사</title>
    <link>javascript:bad</link>
    <guid>broken</guid>
    <pubDate>Tue, 15 Sep 2026 00:00:00 +0000</pubDate>
  </item>
</channel></rss>""".encode()
DUPLICATE_GUID_RSS = """<?xml version=\"1.0\"?>
<rss><channel>
  <item>
    <title>가장 최신 중복 - 연합뉴스</title>
    <link>https://example.test/latest-duplicate</link>
    <guid>same-guid</guid>
    <pubDate>Tue, 15 Sep 2026 00:00:00 +0000</pubDate>
    <source url=\"https://yna.co.kr\">연합뉴스</source>
  </item>
  <item>
    <title>중복 기사 - 연합뉴스</title>
    <link>https://example.test/older-duplicate</link>
    <guid>same-guid</guid>
    <pubDate>Mon, 14 Sep 2026 23:00:00 +0000</pubDate>
    <source url=\"https://yna.co.kr\">연합뉴스</source>
  </item>
  <item>
    <title>고유 기사 - 매일경제</title>
    <link>https://example.test/unique</link>
    <guid>unique-guid</guid>
    <pubDate>Mon, 14 Sep 2026 00:00:00 +0000</pubDate>
    <source url=\"https://mk.co.kr\">매일경제</source>
  </item>
</channel></rss>""".encode()


def _feed(items):
    body = "".join(
        f"<item><title>{title} - 매일경제</title><link>https://example.test/{guid}</link>"
        f"<guid>{guid}</guid><pubDate>Mon, 14 Sep 2026 00:00:00 +0000</pubDate>"
        f"<source url=\"https://mk.co.kr\">매일경제</source></item>"
        for guid, title in items
    )
    return f'<?xml version="1.0"?><rss><channel>{body}</channel></rss>'.encode("utf-8")


class GoogleNewsRssProviderTest(unittest.TestCase):
    def test_google_provider_makes_one_bounded_request(self):
        fetcher = Mock(return_value=RSS_BYTES)
        provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)

        rows = provider.search(**REQUEST)

        self.assertEqual(fetcher.call_count, 1)
        self.assertLessEqual(len(rows), 20)
        self.assertTrue(all(item.origin == "EXTERNAL" for item in rows))

    def test_sends_one_query_per_requested_scope(self):
        fetcher = Mock(return_value=RSS_BYTES)
        provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)

        provider.search(
            corp_name="  삼성전자  ",
            position_name="백엔드 개발자",
            missing_scopes=["ROLE", "INDUSTRY", "COMPANY"],
            from_date=date(2026, 6, 18),
            to_date=date(2026, 9, 16),
            limit=20,
            industry_name="반도체 제조업",
        )

        self.assertEqual(fetcher.call_count, 3)
        queries = []
        for call in fetcher.call_args_list:
            parsed = urlsplit(call.args[0])
            self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                             ("https", "news.google.com", "/rss/search"))
            params = parse_qs(parsed.query)
            self.assertEqual((params["hl"], params["gl"], params["ceid"]), (["ko"], ["KR"], ["KR:ko"]))
            queries.append(params["q"][0])
        # 기업 → 산업 → 직무 순서. 회사명·직무명·범위 단어를 한 질의에 AND 로 섞지 않는다.
        self.assertEqual(queries, [
            '"삼성전자" after:2026-06-18 before:2026-09-16',
            '"반도체 제조업" after:2026-06-18 before:2026-09-16',
            '"백엔드 개발자" after:2026-06-18 before:2026-09-16',
        ])

    def test_industry_query_falls_back_to_company_when_industry_name_is_unknown(self):
        fetcher = Mock(return_value=RSS_BYTES)
        provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)

        provider.search(**{**REQUEST, "missing_scopes": ["INDUSTRY"]})

        query = parse_qs(urlsplit(fetcher.call_args.args[0]).query)["q"][0]
        self.assertTrue(query.startswith('"삼성전자" 업계 after:'))

    def test_empty_scopes_search_company_only(self):
        fetcher = Mock(return_value=RSS_BYTES)
        provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)

        provider.search(**{**REQUEST, "missing_scopes": []})

        self.assertEqual(fetcher.call_count, 1)
        query = parse_qs(urlsplit(fetcher.call_args.args[0]).query)["q"][0]
        self.assertTrue(query.startswith('"삼성전자" after:'))

    def test_interleaves_scopes_and_drops_duplicates_across_scopes(self):
        company_feed = _feed([("A1", "기업 기사 1"), ("A2", "기업 기사 2"), ("A3", "기업 기사 3")])
        role_feed = _feed([("R1", "직무 기사 1"), ("A1", "기업 기사 1")])
        fetcher = Mock(side_effect=[company_feed, role_feed])
        provider = GoogleNewsRssProvider(fetcher=fetcher, now=lambda: NOW)

        rows = provider.search(**{**REQUEST, "missing_scopes": ["COMPANY", "ROLE"], "limit": 3})

        self.assertEqual([row.guid for row in rows], ["A1", "R1", "A2"])

    def test_keeps_valid_rows_sorts_newest_first_and_applies_requested_limit(self):
        provider = GoogleNewsRssProvider(fetcher=Mock(return_value=RSS_BYTES), now=lambda: NOW)

        rows = provider.search(**{**REQUEST, "limit": 1})

        self.assertEqual([row.title for row in rows], ["최신 기사"])
        self.assertTrue(rows[0].article_id.startswith("external:"))
        self.assertEqual(rows[0].published_at, datetime(2026, 9, 15, tzinfo=timezone.utc))

    def test_deduplicates_article_ids_before_applying_limit(self):
        provider = GoogleNewsRssProvider(fetcher=Mock(return_value=DUPLICATE_GUID_RSS), now=lambda: NOW)

        rows = provider.search(**{**REQUEST, "limit": 2})

        self.assertEqual([row.title for row in rows], ["가장 최신 중복", "고유 기사"])
        self.assertEqual(len({row.article_id for row in rows}), 2)

    def test_rejects_invalid_limit_and_date_range_before_request(self):
        fetcher = Mock(return_value=RSS_BYTES)
        provider = GoogleNewsRssProvider(fetcher=fetcher)

        for overrides in (
            {"limit": 0},
            {"limit": 21},
            {"from_date": date(2026, 9, 16), "to_date": date(2026, 9, 16)},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                provider.search(**{**REQUEST, **overrides})

        self.assertEqual(fetcher.call_count, 0)

    def test_rate_limit_is_not_retried_or_leaked(self):
        fetcher = Mock(side_effect=HTTPError(URL, 429, "limited", {}, None))

        with self.assertRaises(ExternalSearchUnavailable) as raised:
            GoogleNewsRssProvider(fetcher=fetcher).search(**REQUEST)

        self.assertEqual(fetcher.call_count, 1)
        self.assertNotIn("sensitive-query", str(raised.exception))
        self.assertNotIn(URL, str(raised.exception))

    def test_default_fetcher_uses_25_second_timeout_and_streams_under_limit(self):
        response = _Response(RSS_BYTES)
        with patch("ai.news_intelligence.search_provider.urlopen", return_value=response) as opener:
            rows = GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)

        self.assertEqual([row.title for row in rows], ["최신 기사", "과거 기사"])
        self.assertEqual(opener.call_args.kwargs["timeout"], 25)
        self.assertTrue(response.read_sizes)
        self.assertLessEqual(max(response.read_sizes), 64 * 1024)

    def test_default_fetcher_accepts_completed_real_http_response(self):
        response, reader, writer = _completed_http_response(RSS_BYTES)
        try:
            with patch("ai.news_intelligence.search_provider.urlopen", return_value=response):
                rows = GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
        finally:
            reader.close()
            writer.close()

        self.assertEqual([row.title for row in rows], ["최신 기사", "과거 기사"])

    def test_default_fetcher_accepts_completed_real_chunked_http_response(self):
        response, reader, writer = _completed_chunked_http_response(RSS_BYTES)
        try:
            with patch("ai.news_intelligence.search_provider.urlopen", return_value=response):
                rows = GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
        finally:
            reader.close()
            writer.close()

        self.assertEqual([row.title for row in rows], ["최신 기사", "과거 기사"])

    def test_default_fetcher_accepts_chunk_size_bad_whitespace_before_extension(self):
        response, reader, writer = _completed_chunked_http_response(
            RSS_BYTES,
            chunk_extension=b" ; foo = bar",
        )
        try:
            with patch("ai.news_intelligence.search_provider.urlopen", return_value=response):
                rows = GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
        finally:
            reader.close()
            writer.close()

        self.assertEqual([row.title for row in rows], ["최신 기사", "과거 기사"])

    def test_default_fetcher_accepts_fragmented_chunk_size_bad_whitespace_before_extension(self):
        response, reader, writer, writer_thread = _fragmented_chunked_http_response(RSS_BYTES)
        try:
            with patch("ai.news_intelligence.search_provider.urlopen", return_value=response):
                rows = GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
        finally:
            response.close()
            reader.close()
            writer.close()
            writer_thread.join(timeout=1)

        self.assertFalse(writer_thread.is_alive())
        self.assertEqual([row.title for row in rows], ["최신 기사", "과거 기사"])

    def test_default_fetcher_rejects_oversized_stream_without_a_second_request(self):
        response = _Response(size=10_000_001)
        with patch("ai.news_intelligence.search_provider.urlopen", return_value=response) as opener:
            with self.assertRaises(ExternalSearchUnavailable):
                GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)

        self.assertEqual(opener.call_count, 1)
        self.assertLessEqual(max(response.read_sizes), 64 * 1024)

    def test_default_fetcher_stops_slow_drip_at_the_total_deadline(self):
        clock = _Clock()
        response = _SlowDripResponse(clock)
        with patch("ai.news_intelligence.search_provider.urlopen", return_value=response) as opener:
            with self.assertRaises(ExternalSearchUnavailable):
                GoogleNewsRssProvider(now=lambda: NOW, monotonic=clock).search(**REQUEST)

        self.assertEqual(opener.call_count, 1)
        self.assertEqual(response.read_count, 3)
        self.assertEqual(response.socket.timeouts, [25, 20, 10])

    def test_default_fetcher_closes_http_error_body_before_wrapping_failure(self):
        body = io.BytesIO(b"rate limited")
        error = HTTPError(URL, 429, "limited", {}, body)
        with patch("ai.news_intelligence.search_provider.urlopen", side_effect=error) as opener:
            with self.assertRaises(ExternalSearchUnavailable):
                GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)

        self.assertEqual(opener.call_count, 1)
        self.assertTrue(body.closed)

    def test_default_fetcher_stops_real_http_response_slow_drip_at_deadline(self):
        reader, writer = socket.socketpair()
        response = http.client.HTTPResponse(reader)
        writer.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\n")
        response.begin()
        writer_thread = threading.Thread(target=_drip_bytes, args=(writer, b"abcdefghijkl"))
        writer_thread.start()
        started = time.monotonic()
        try:
            with patch("ai.news_intelligence.search_provider.PROVIDER_TIMEOUT_SECONDS", 0.15), \
                 patch("ai.news_intelligence.search_provider.urlopen", return_value=response) as opener:
                with self.assertRaises(ExternalSearchUnavailable):
                    GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
            elapsed = time.monotonic() - started
        finally:
            response.close()
            reader.close()
            writer.close()
            writer_thread.join(timeout=1)

        self.assertEqual(opener.call_count, 1)
        self.assertFalse(writer_thread.is_alive())
        self.assertLess(elapsed, 0.30)

    def test_default_fetcher_stops_real_chunked_slow_drip_at_deadline(self):
        reader, writer = socket.socketpair()
        response = http.client.HTTPResponse(reader)
        writer.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        response.begin()
        encoded_body = b"1;aaaaaaaaaa\r\na\r\n0\r\n\r\n"
        writer_thread = threading.Thread(target=_drip_bytes, args=(writer, encoded_body))
        writer_thread.start()
        started = time.monotonic()
        try:
            with patch("ai.news_intelligence.search_provider.PROVIDER_TIMEOUT_SECONDS", 0.15), \
                 patch("ai.news_intelligence.search_provider.urlopen", return_value=response) as opener:
                with self.assertRaises(ExternalSearchUnavailable):
                    GoogleNewsRssProvider(now=lambda: NOW).search(**REQUEST)
            elapsed = time.monotonic() - started
        finally:
            response.close()
            reader.close()
            writer.close()
            writer_thread.join(timeout=1)

        self.assertEqual(opener.call_count, 1)
        self.assertFalse(writer_thread.is_alive())
        self.assertLess(elapsed, 0.30)


class _Response:
    def __init__(self, payload: bytes | None = None, *, size: int | None = None):
        self._payload = payload
        self._remaining = size
        self._offset = 0
        self.read_sizes: list[int] = []
        self.socket = _Socket()
        self.fp = _ResponseFile(self.socket)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if self._payload is not None:
            result = self._payload[self._offset:self._offset + size]
            self._offset += len(result)
            return result
        assert self._remaining is not None
        chunk_size = min(size, self._remaining)
        self._remaining -= chunk_size
        return b"x" * chunk_size


class _ResponseFile:
    def __init__(self, socket):
        self.raw = _ResponseRaw(socket)


class _ResponseRaw:
    def __init__(self, socket):
        self._sock = socket


class _Socket:
    def __init__(self):
        self.timeouts: list[float] = []

    def settimeout(self, timeout: float):
        self.timeouts.append(timeout)


class _Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value

    def advance(self, seconds: int):
        self.value += seconds


class _SlowDripResponse(_Response):
    def __init__(self, clock: _Clock):
        super().__init__()
        self._clock = clock
        self.read_count = 0

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        self.read_count += 1
        self._clock.advance(10)
        return b"x"


def _completed_http_response(payload: bytes):
    reader, writer = socket.socketpair()
    writer.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Length: "
        + str(len(payload)).encode()
        + b"\r\n\r\n"
        + payload
    )
    writer.shutdown(socket.SHUT_WR)
    response = http.client.HTTPResponse(reader)
    response.begin()
    return response, reader, writer


def _completed_chunked_http_response(payload: bytes, *, chunk_extension: bytes = b""):
    reader, writer = socket.socketpair()
    writer.sendall(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        + f"{len(payload):X}".encode()
        + chunk_extension
        + b"\r\n"
        + payload
        + b"\r\n0\r\n\r\n"
    )
    writer.shutdown(socket.SHUT_WR)
    response = http.client.HTTPResponse(reader)
    response.begin()
    return response, reader, writer


def _fragmented_chunked_http_response(payload: bytes):
    reader, writer = socket.socketpair()
    response = http.client.HTTPResponse(reader)
    writer.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
    response.begin()
    encoded = [
        f"{len(payload):X} \t".encode(),
        b"; foo = bar\r\n",
        payload[:100],
        payload[100:],
        b"\r\n0\r",
        b"\n\r\n",
    ]
    writer_thread = threading.Thread(target=_write_fragments, args=(writer, encoded))
    writer_thread.start()
    return response, reader, writer, writer_thread


def _drip_bytes(writer: socket.socket, payload: bytes):
    try:
        for byte in payload:
            writer.sendall(bytes([byte]))
            time.sleep(0.03)
    except OSError:
        pass
    finally:
        writer.close()


def _write_fragments(writer: socket.socket, fragments: list[bytes]):
    try:
        for fragment in fragments:
            writer.sendall(fragment)
            time.sleep(0.005)
    except OSError:
        pass
    finally:
        writer.close()


if __name__ == "__main__":
    unittest.main()
