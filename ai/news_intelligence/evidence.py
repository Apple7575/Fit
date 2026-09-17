from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from ai.news_intelligence.contracts import EvidenceLevel, NewsCandidate


def deduplicate_candidates(candidates: Sequence[NewsCandidate]) -> list[NewsCandidate]:
    """Keep the first article for each observed URL, guid, or title identity."""
    seen_urls: set[str] = set()
    seen_guids: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[NewsCandidate] = []

    for candidate in candidates:
        url = _normalize_url(str(candidate.url))
        guid = _normalize_text(candidate.guid)
        title = _normalize_text(candidate.title)
        if url in seen_urls or (guid and guid in seen_guids) or title in seen_titles:
            continue
        unique.append(candidate)
        seen_urls.add(url)
        if guid:
            seen_guids.add(guid)
        seen_titles.add(title)
    return unique


def calculate_evidence_level(
    sources: Sequence[NewsCandidate], now: datetime
) -> EvidenceLevel:
    _require_timezone_aware(now)
    valid = [item for item in sources if _is_within_window(item.published_at, now, 90)]
    recent = [item for item in valid if _is_within_window(item.published_at, now, 30)]
    recent_publishers = {
        publisher
        for item in recent
        if (publisher := normalize_publisher(item.publisher))
    }
    all_publishers = {
        publisher
        for item in valid
        if (publisher := normalize_publisher(item.publisher))
    }
    if len(recent_publishers) >= 2:
        return "HIGH"
    if recent or len(all_publishers) >= 2:
        return "MEDIUM"
    if valid:
        return "LOW"
    return "INSUFFICIENT"


def normalize_publisher(value: str | None) -> str:
    return _normalize_text(value)


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _is_within_window(published_at: datetime, now: datetime, days: int) -> bool:
    _require_timezone_aware(published_at)
    age = now - published_at
    return timedelta(0) <= age <= timedelta(days=days)


def _require_timezone_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
