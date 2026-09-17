"""Google News RSS 파싱과 품질 선별.

`data/news_poc/pipeline/{collect,normalize}.py`의 `parse_feed`·`screen_quality`·
`valid_url`(및 그 내부 의존 함수)을 그대로 복제했다. `ai/`는 서비스 런타임이고
`data/`는 별도의 오프라인 데이터 파이프라인이라, 런타임이 파이프라인 모듈을
직접 import하면 배포·변경 범위가 얽힌다. 원본과 동작이 달라지면 각자 따로
검증해야 한다.
"""
from __future__ import annotations

import hashlib
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET


class _TextOnly(HTMLParser):
    """HTML 태그를 제외한 텍스트 조각을 수집한다. HTML 정화 도구는 아니다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain(value: str | None) -> str:
    """HTML 문자열 또는 None을 공백이 정리된 일반 텍스트로 반환한다."""
    parser = _TextOnly()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


def valid_url(value: str) -> bool:
    """호스트가 있고 사용자명이 없는 HTTP(S) URL인지 검사한다.

    문자열 형식만 확인한다. 실제 접근 가능 여부나 원문 기사 여부는 검증하지 않는다.
    """
    try:
        url = urlsplit(value)
        return url.scheme in ("https", "http") and bool(url.hostname) and not url.username
    except ValueError:
        return False


def _is_google(value: str) -> bool:
    """파싱 가능한 URL의 호스트가 google.com 또는 그 하위 도메인인지 반환한다."""
    host = (urlsplit(value).hostname or "").lower()
    return host == "google.com" or host.endswith(".google.com")


def _identity_link(value: str) -> str:
    """중복 식별용으로 Google URL의 쿼리와 fragment를 제거한다.

    외부 URL은 쿼리가 기사 식별자일 수 있어 그대로 유지한다.
    원문 URL을 찾거나 링크를 방문하는 함수는 아니다.
    """
    if valid_url(value) and _is_google(value):
        url = urlsplit(value)
        return urlunsplit((url.scheme, url.netloc, url.path, "", ""))
    return value


def parse_feed(payload: bytes) -> list[dict[str, Any]]:
    """RSS XML 바이트를 뉴스 필드와 검토 정보가 포함된 dict 목록으로 변환한다.

    Args:
        payload: RSS 응답의 원본 bytes.

    Returns:
        뉴스 6개 컬럼, article_key, 출처·링크·설명 상태, issues를 담은 목록.
        항목의 제목·날짜·링크 오류는 행을 버리는 대신 issues에 기록한다.
        description과 AI 필드는 검토/실행 전이므로 항상 None이다.

    Raises:
        ValueError: 용량 제한 초과, DTD/ENTITY 선언 탐지, RSS 구조 불일치.
        ET.ParseError: XML 구문을 파싱할 수 없는 경우.
    """
    # 예상 밖의 대용량 응답과 명시적인 DTD/ENTITY 선언을 파싱 전에 거른다.
    if len(payload) > 10_000_000:
        raise ValueError("RSS exceeds 10 MB limit")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("DTD/entities are not accepted")
    root = ET.fromstring(payload)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Expected RSS channel; possibly HTML/consent response")
    rows = []
    for element in root.findall("./channel/item"):
        issues = []
        raw_title = _plain(element.findtext("title"))
        publisher = _plain(element.findtext("source"))
        title = raw_title
        # 제목 본문에 포함된 언론사명까지 지우지 않도록 끝의 정확한 접미사만 제거한다.
        if publisher and title.endswith(" - " + publisher):
            title = title[: -(len(publisher) + 3)].strip()
        if not title:
            issues.append("missing_title")
        description_text = _plain(element.findtext("description"))
        # HTML을 벗겨도 제목·언론사만 남을 수 있다. 문장부호 차이를 제거해 비교한다.
        canonical = lambda text: re.sub(r"[\W_]+", "", text).casefold()  # noqa: E731
        repeats = {canonical(raw_title), canonical(title), canonical(title + publisher)}
        description_status = (
            "missing"
            if not description_text
            else "title_repeat" if canonical(description_text) in repeats else "needs_review"
        )
        published = None
        try:
            value = parsedate_to_datetime(element.findtext("pubDate") or "")
            if value.tzinfo is None:
                # 로컬 컴퓨터의 시간대를 임의 적용하면 기사 시각이 달라질 수 있다.
                raise ValueError("Timezone is missing")
            published = value.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            issues.append("invalid_date")
        link = (element.findtext("link") or "").strip()
        good_link = valid_url(link)
        # 외부 링크도 원문 '후보'일 뿐이다. 언론사 홈페이지(source url)는 대체하지 않는다.
        original = link if good_link and not _is_google(link) else None
        if not good_link:
            issues.append("invalid_link")
        guid = (element.findtext("guid") or "").strip()
        # GUID → 링크 → 제목·언론사·날짜 순으로 안정적인 중복 식별 키를 만든다.
        key = guid or _identity_link(link) or "|".join([title, publisher, published or ""])
        source = element.find("source")
        rows.append(
            dict(
                article_key=hashlib.sha256(key.encode()).hexdigest(),
                title=title,
                description=None,
                published_at=published,
                original_url=original,
                related_business=None,
                importance_score=None,
                google_url=link if good_link and _is_google(link) else None,
                rss_link=link,
                guid=guid,
                publisher=publisher,
                publisher_url=source.get("url") if source is not None else None,
                description_text=description_text,
                description_status=description_status,
                original_url_status="rss_direct_unverified" if original else "unresolved",
                issues=issues,
            )
        )
    return rows


def screen_quality(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """명확한 입력 결함만 분리한다. 기업 관련성·중요도·제목 키워드는 판정하지 않는다.

    Google 경유 URL만으로는 목록 페이지를 판별할 수 없다. 확보된 실제 URL이
    검증한 목록 경로일 때만 제외한다. 분리된 행도 사유와 함께 보관해 복구할 수 있다.
    """
    ready, rejected = [], []
    for row in rows:
        issues = []
        if not (row.get("title") or "").strip():
            issues.append("missing_title")
        if not any(valid_url(row.get(key) or "") for key in ("rss_link", "original_url", "google_url")):
            issues.append("invalid_link")
        for key in ("original_url", "rss_link"):
            value = row.get(key) or ""
            if valid_url(value):
                url = urlsplit(value)
                if url.hostname == "stock.mk.co.kr" and url.path.startswith("/price/news/"):
                    issues.append("known_listing_page")
                    break
        if issues:
            rejected.append(dict(row, quality_issues=issues))
        else:
            ready.append(row)
    return ready, rejected
