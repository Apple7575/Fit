from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
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
_SCOPE_TERMS: frozenset[Scope] = frozenset(_SCOPE_ORDER)  # 허용 범위 집합


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
        """범위(기업·산업·직무)마다 질의를 따로 보내고 결과를 번갈아 섞는다.

        구글 뉴스 RSS는 띄어쓰기를 AND 로 처리하므로 회사명·직무명·범위 단어를 한 질의에
        모두 넣으면 거의 아무것도 돌아오지 않는다(2026-09 실측: 회사명만 77~100건,
        전부 넣으면 0~9건). 범위별로 나누면 각 범위의 기사가 고르게 들어온다.
        """
        canonical_corp_name = _require_text(corp_name, "corp_name")
        canonical_position_name = _require_text(position_name, "position_name")
        canonical_industry_name = _optional_text(industry_name)
        scopes = _normalize_scopes(missing_scopes) or ["COMPANY"]
        _validate_range(from_date, to_date)
        _validate_limit(limit)

        deadline = self._monotonic() + remaining_timeout(
            PROVIDER_TIMEOUT_SECONDS, ExternalSearchUnavailable,
        )
        try:
            per_scope: list[list[NewsCandidate]] = []
            for scope in scopes:
                url = _search_url(
                    scope_query(
                        scope,
                        corp_name=canonical_corp_name,
                        position_name=canonical_position_name,
                        industry_name=canonical_industry_name,
                    ),
                    from_date,
                    to_date,
                )
                if self._fetcher is None:
                    payload = _fetch_rss(url, deadline=deadline, monotonic_clock=self._monotonic)
                else:
                    payload = self._fetcher(url)
                _require_before_deadline(deadline, self._monotonic)
                accepted, _ = screen_quality(parse_feed(payload))
                _require_before_deadline(deadline, self._monotonic)
                per_scope.append(_candidates_from_rows(
                    accepted,
                    from_date=from_date,
                    to_date=to_date,
                    now=self._now(),
                    limit=limit,
                ))
            _require_before_deadline(deadline, self._monotonic)
            return _interleave(per_scope, limit)
        except Exception as error:
            raise ExternalSearchUnavailable() from error


def scope_query(
    scope: Scope,
    *,
    corp_name: str,
    position_name: str,
    industry_name: str | None,
) -> str:
    """범위별 검색어. 날짜 조건은 _search_url 이 붙인다."""
    if scope == "COMPANY":
        return _quote_query_term(corp_name)
    if scope == "INDUSTRY":
        if industry_name:
            return _quote_query_term(industry_name)
        # 업종명을 모르면 회사명과 '업계'를 함께 검색해 산업 기사에 가깝게 맞춘다.
        return f"{_quote_query_term(corp_name)} 업계"
    return _quote_query_term(position_name)


def _interleave(groups: Sequence[Sequence[NewsCandidate]], limit: int) -> list[NewsCandidate]:
    """범위별 결과를 한 건씩 번갈아 뽑아 특정 범위가 목록을 독점하지 않게 한다. 중복 기사는 한 번만."""
    merged: list[NewsCandidate] = []
    seen: set[str] = set()
    for index in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if index >= len(group):
                continue
            candidate = group[index]
            if candidate.article_id in seen:
                continue
            seen.add(candidate.article_id)
            merged.append(candidate)
            if len(merged) >= limit:
                return merged
    return merged


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


def _search_url(query: str, from_date: date, to_date: date) -> str:
    return "https://news.google.com/rss/search?" + urlencode(
        {
            "q": f"{query} after:{from_date.isoformat()} before:{to_date.isoformat()}",
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko",
        }
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
    if not provided.issubset(_SCOPE_TERMS):
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
