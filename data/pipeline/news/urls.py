"""중복 판정용 URL 정규화.

주소가 조금 달라도 같은 기사인 경우를 잡기 위한 것이고, 접속해서 확인하지 않는다.
쿼리스트링을 통째로 버리지는 않는다 — 언론사에 따라 쿼리가 기사 식별자다
(`?idxno=12345`). 추적 파라미터만 떼고 나머지는 남긴다.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 같은 기사에 다르게 붙는 유입 추적 파라미터. 값이 달라도 같은 기사다.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {
    "fbclid", "gclid", "igshid", "ref", "referer", "referrer",
    "cid", "spm", "from", "sc", "at_medium", "at_campaign",
}


def normalize(value: str) -> str:
    """스킴·호스트 소문자화, fragment 제거, 추적 파라미터 제거, 끝 슬래시 정리."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        url = urlsplit(text)
    except ValueError:
        return text
    if not url.hostname:
        return text
    host = url.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host if url.port in (None, 80, 443) else f"{host}:{url.port}"
    path = url.path.rstrip("/") or "/"
    query = urlencode(sorted(
        (key, val) for key, val in parse_qsl(url.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_KEYS
        and not any(key.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ))
    return urlunsplit((url.scheme.lower(), netloc, path, query, ""))
