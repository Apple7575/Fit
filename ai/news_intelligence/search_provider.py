from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
import logging
import re
from time import monotonic as system_monotonic
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import ValidationError

from ai.news_intelligence.budget import remaining_timeout
from ai.news_intelligence.contracts import NewsCandidate, Scope
from ai.news_intelligence.rss_feed import parse_feed, screen_quality, valid_url


MAX_EXTERNAL_CANDIDATES = 20
MAX_RESPONSE_BYTES = 10_000_000
MAX_CHUNKED_OVERHEAD_BYTES = 1_000_000
MAX_CHUNKED_RESPONSE_BYTES = MAX_RESPONSE_BYTES + MAX_CHUNKED_OVERHEAD_BYTES
FETCH_TIMEOUT_SECONDS = 25
PROVIDER_TIMEOUT_SECONDS = 30
_READ_CHUNK_BYTES = 64 * 1024
_SCOPE_ORDER: tuple[Scope, ...] = ("COMPANY", "INDUSTRY", "ROLE")

# 직무명을 검색어로 쪼갤 때 버리는 말. "설계", "개발" 같은 낱말 하나로는 기사가 끝없이 나온다.
_ROLE_STOPWORDS = frozenset({
    "및", "등", "관련", "담당", "업무", "직무", "분야", "부문", "경력", "신입", "채용",
    "개발자", "엔지니어", "매니저", "설계", "개발", "운영", "관리", "지원", "시스템",
})
_MAX_ROLE_TERMS = 3

LOGGER = logging.getLogger(__name__)


class NewsSearchProvider(Protocol):
    def search(
        self,
        corp_name: str,
        position_name: str,
        missing_scopes: Sequence[Scope],
        from_date: date,
        to_date: date,
        limit: int,
        *,
        industry_name: str | None = None,
    ) -> list[NewsCandidate]: ...


class ExternalSearchUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("external news search is unavailable")


class GoogleNewsRssProvider:
    def __init__(
        self,
        *,
        fetcher: Callable[[str], bytes] | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or system_monotonic

    def search(
        self,
        corp_name: str,
        position_name: str,
        missing_scopes: Sequence[Scope],
        from_date: date,
        to_date: date,
        limit: int,
        *,
        industry_name: str | None = None,
    ) -> list[NewsCandidate]:
        """부족한 범위마다 넓은 질의를 하나씩 보내고 결과를 합친다.

        예전에는 회사명·직무명·범위 이름을 한 질의에 전부 넣었다. 구글 뉴스는 그것을 AND 로
        읽어서, 범위가 셋 다 부족하면 0건이 나왔다(실측: 회사명만 100건, 셋 다 붙이면 0건).
        근거가 부족할수록 질의가 좁아져 더 못 찾는 구조였다. 지금은 범위별로 따로 묻고
        합집합을 만든다. 무엇이 지원자와 관련 있는지는 모델이 제목을 보고 고른다.
        """
        canonical_corp_name = _require_text(corp_name, "corp_name")
        canonical_position_name = _require_text(position_name, "position_name")
        scopes = _normalize_scopes(missing_scopes) or ["COMPANY"]
        _validate_range(from_date, to_date)
        _validate_limit(limit)

        queries = _scope_queries(
            canonical_corp_name, canonical_position_name, industry_name, scopes,
        )
        deadline = self._monotonic() + remaining_timeout(
            PROVIDER_TIMEOUT_SECONDS, ExternalSearchUnavailable,
        )
        per_scope: list[list[NewsCandidate]] = []
        last_error: Exception | None = None
        for scope, query in queries:
            url = _search_url(query, from_date, to_date)
            try:
                if self._fetcher is None:
                    payload = _fetch_rss(url, deadline=deadline, monotonic_clock=self._monotonic)
                else:
                    payload = self._fetcher(url)
                _require_before_deadline(deadline, self._monotonic)
                accepted, _ = screen_quality(parse_feed(payload))
                per_scope.append(_candidates_from_rows(
                    accepted, from_date=from_date, to_date=to_date, now=self._now(), limit=limit,
                ))
            except Exception as error:  # noqa: BLE001
                # 한 범위가 실패해도 나머지는 살린다. 이유는 남긴다 — 전에는 통째로 삼켜서
                # 응답만 보면 "검색했는데 없더라" 로 보였다.
                LOGGER.warning(
                    "news search failed: scope=%s query=%r cause=%s: %s",
                    scope, query, type(error).__name__, error,
                )
                last_error = error
                if isinstance(error, TimeoutError):
                    break
        if not per_scope:
            raise ExternalSearchUnavailable() from last_error
        return _interleave(per_scope, limit)


def _fetch_rss(
    url: str,
    *,
    deadline: float,
    monotonic_clock: Callable[[], float],
) -> bytes:
    request = Request(url, headers={"User-Agent": "SSAFYNewsAgent/1.0"})
    try:
        with urlopen(
            request,
            timeout=_remaining_timeout(deadline, monotonic_clock),
        ) as response:
            return _read_response(response, deadline=deadline, monotonic_clock=monotonic_clock)
    except HTTPError as error:
        error.close()
        raise


def _read_response(
    response,
    *,
    deadline: float,
    monotonic_clock: Callable[[], float],
) -> bytes:
    if getattr(response, "chunked", False):
        return _read_chunked_response(
            response,
            deadline=deadline,
            monotonic_clock=monotonic_clock,
        )
    chunks: list[bytes] = []
    total = 0
    while True:
        if _response_is_complete(response):
            return b"".join(chunks)
        _set_response_timeout(response, _remaining_timeout(deadline, monotonic_clock))
        chunk = _read_once(response, min(_READ_CHUNK_BYTES, MAX_RESPONSE_BYTES - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise ValueError("RSS exceeds 10 MB limit")
        chunks.append(chunk)


def _read_chunked_response(
    response,
    *,
    deadline: float,
    monotonic_clock: Callable[[], float],
) -> bytes:
    if getattr(response, "fp", None) is None:
        raise ValueError("incomplete chunked response")

    encoded_total = 0
    decoded_total = 0
    buffer = bytearray()
    decoded_chunks: list[bytes] = []
    state = "size"
    chunk_size = 0

    while True:
        while True:
            if state == "size":
                line = _pop_chunk_line(buffer)
                if line is None:
                    break
                chunk_size = _parse_chunk_size(line)
                state = "trailers" if chunk_size == 0 else "data"
                continue

            if state == "data":
                if len(buffer) < chunk_size + 2:
                    break
                if buffer[chunk_size:chunk_size + 2] != b"\r\n":
                    raise ValueError("malformed chunk terminator")
                decoded_total += chunk_size
                if decoded_total > MAX_RESPONSE_BYTES:
                    raise ValueError("RSS exceeds 10 MB limit")
                decoded_chunks.append(bytes(buffer[:chunk_size]))
                del buffer[:chunk_size + 2]
                state = "size"
                continue

            line = _pop_chunk_line(buffer)
            if line is None:
                break
            if not line:
                if buffer:
                    raise ValueError("unexpected bytes after chunked response")
                return b"".join(decoded_chunks)
            if b":" not in line or line.startswith(b":"):
                raise ValueError("malformed chunk trailer")

        encoded_chunk = _read_chunked_wire_once(response, deadline, monotonic_clock)
        encoded_total += len(encoded_chunk)
        if encoded_total > MAX_CHUNKED_RESPONSE_BYTES:
            raise ValueError("chunked RSS exceeds encoded response limit")
        buffer.extend(encoded_chunk)


def _read_chunked_wire_once(
    response,
    deadline: float,
    monotonic_clock: Callable[[], float],
) -> bytes:
    fp = getattr(response, "fp", None)
    if fp is None:
        raise ValueError("incomplete chunked response")
    _set_response_timeout(response, _remaining_timeout(deadline, monotonic_clock))
    read1 = getattr(fp, "read1", None)
    if not callable(read1):
        raise ValueError("chunked response does not support bounded reads")
    chunk = read1(_READ_CHUNK_BYTES)
    _require_before_deadline(deadline, monotonic_clock)
    if not chunk:
        raise ValueError("incomplete chunked response")
    return chunk


def _pop_chunk_line(buffer: bytearray) -> bytes | None:
    marker = buffer.find(b"\r\n")
    if marker < 0:
        return None
    line = bytes(buffer[:marker])
    del buffer[:marker + 2]
    return line


def _parse_chunk_size(line: bytes) -> int:
    size, delimiter, _ = line.partition(b";")
    if delimiter:
        size = size.rstrip(b" \t")
    if not size or any(byte not in b"0123456789abcdefABCDEF" for byte in size):
        raise ValueError("malformed chunk size")
    return int(size, 16)


def _remaining_timeout(deadline: float, monotonic_clock: Callable[[], float]) -> float:
    remaining = deadline - monotonic_clock()
    if remaining <= 0:
        raise TimeoutError("external news search exceeded its deadline")
    return min(FETCH_TIMEOUT_SECONDS, remaining)


def _require_before_deadline(deadline: float, monotonic_clock: Callable[[], float]) -> None:
    _remaining_timeout(deadline, monotonic_clock)


def _set_response_timeout(response, timeout: float) -> None:
    fp = getattr(response, "fp", None)
    raw = getattr(fp, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is not None:
        sock.settimeout(timeout)


def _response_is_complete(response) -> bool:
    return hasattr(response, "fp") and response.fp is None


def _read_once(response, size: int) -> bytes:
    read1 = getattr(response, "read1", None)
    if callable(read1):
        return read1(size)
    return response.read(size)


def _scope_queries(
    corp_name: str,
    position_name: str,
    industry_name: str | None,
    scopes: Sequence[Scope],
) -> list[tuple[Scope, str]]:
    """범위마다 질의 하나. 회사명은 회사 범위에만 붙인다.

    산업·직무 기사는 회사명이 안 들어간 것이 대부분이라, 회사명을 붙이면 그 범위가 통째로
    빈다. 같은 질의가 두 범위에서 나오면 한 번만 보낸다.
    """
    queries: list[tuple[Scope, str]] = []
    seen: set[str] = set()
    for scope in scopes:
        if scope == "COMPANY":
            query = _quote_query_term(corp_name)
        elif scope == "INDUSTRY":
            industry = (industry_name or "").strip()
            # 산업명이 없으면 회사 기사로 대신한다. 아무것도 안 보내는 것보다 낫다.
            query = _quote_query_term(industry) if industry else _quote_query_term(corp_name)
        else:
            terms = _role_terms(position_name)
            if not terms:
                continue
            query = " ".join(terms)
        if query in seen:
            continue
        seen.add(query)
        queries.append((scope, query))
    return queries


def _role_terms(position_name: str) -> list[str]:
    """직무명에서 검색어로 쓸 낱말만 고른다. '액추에이터 시스템/기구 설계' → 액추에이터, 기구."""
    terms: list[str] = []
    for token in re.split(r"[\s/·,()\[\]]+", position_name):
        token = token.strip()
        if len(token) < 2 or token in _ROLE_STOPWORDS or token in terms:
            continue
        terms.append(token)
        if len(terms) == _MAX_ROLE_TERMS:
            break
    return terms


def _interleave(per_scope: Sequence[Sequence[NewsCandidate]], limit: int) -> list[NewsCandidate]:
    """범위별 목록을 번갈아 뽑는다. 회사 기사가 많다고 직무 기사가 밀려나지 않게."""
    out: list[NewsCandidate] = []
    seen: set[str] = set()
    for index in range(max((len(rows) for rows in per_scope), default=0)):
        for rows in per_scope:
            if index >= len(rows):
                continue
            candidate = rows[index]
            if candidate.article_id in seen:
                continue
            seen.add(candidate.article_id)
            out.append(candidate)
            if len(out) == limit:
                return out
    return out


def _search_url(query: str, from_date: date, to_date: date) -> str:
    full_query = " ".join([query, f"after:{from_date.isoformat()}", f"before:{to_date.isoformat()}"])
    return "https://news.google.com/rss/search?" + urlencode(
        {"q": full_query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    )


def _candidates_from_rows(
    rows: Sequence[dict[str, object]],
    *,
    from_date: date,
    to_date: date,
    now: datetime,
    limit: int,
) -> list[NewsCandidate]:
    _require_timezone_aware(now)
    candidates: list[NewsCandidate] = []
    for row in rows:
        candidate = _candidate_from_row(row)
        if candidate is None:
            continue
        if not from_date <= candidate.published_at.date() < to_date:
            continue
        if candidate.published_at > now:
            continue
        candidates.append(candidate)
    candidates.sort(key=lambda candidate: candidate.published_at, reverse=True)
    unique: list[NewsCandidate] = []
    seen_article_ids: set[str] = set()
    for candidate in candidates:
        if candidate.article_id in seen_article_ids:
            continue
        seen_article_ids.add(candidate.article_id)
        unique.append(candidate)
    return unique[:limit]


def _candidate_from_row(row: dict[str, object]) -> NewsCandidate | None:
    published_at = _parse_published_at(row.get("published_at"))
    url = _candidate_url(row)
    article_key = row.get("article_key")
    if published_at is None or url is None or not isinstance(article_key, str) or not article_key:
        return None
    try:
        return NewsCandidate(
            article_id=f"external:{article_key}",
            origin="EXTERNAL",
            title=row.get("title"),
            publisher=_optional_text(row.get("publisher")),
            published_at=published_at,
            url=url,
            guid=_optional_text(row.get("guid")),
        )
    except ValidationError:
        return None


def _parse_published_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


def _candidate_url(row: dict[str, object]) -> str | None:
    for key in ("original_url", "rss_link", "google_url"):
        value = row.get(key)
        if isinstance(value, str) and valid_url(value):
            return value
    return None


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a non-blank string")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{name} must be a non-blank string")
    return normalized


def _normalize_scopes(scopes: Sequence[Scope]) -> list[Scope]:
    if isinstance(scopes, (str, bytes)):
        raise ValueError("missing_scopes must be a sequence of scopes")
    provided = set(scopes)
    if not provided.issubset(_SCOPE_ORDER):
        raise ValueError("missing_scopes contains an unsupported scope")
    return [scope for scope in _SCOPE_ORDER if scope in provided]


def _validate_range(from_date: date, to_date: date) -> None:
    if not isinstance(from_date, date) or not isinstance(to_date, date):
        raise ValueError("search dates must be dates")
    if from_date >= to_date:
        raise ValueError("from_date must precede to_date")
    if (to_date - from_date).days > 90:
        raise ValueError("search range must not exceed 90 days")


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_EXTERNAL_CANDIDATES:
        raise ValueError("limit must be between 1 and 20")


def _quote_query_term(value: str) -> str:
    return '"' + value.replace('"', r'\"') + '"'


def _require_timezone_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
