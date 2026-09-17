from __future__ import annotations

from collections.abc import Sequence, Set
from datetime import datetime, timedelta

from ai.news_intelligence.contracts import CoverageAssessment, NewsCandidate, Scope, SearchDecision


_MINIMUM_CANDIDATES = 5
_FRESHNESS_WINDOW = timedelta(days=30)
_SCOPE_ORDER = ("COMPANY", "INDUSTRY", "ROLE")


def decide_external_search(
    candidates: Sequence[NewsCandidate],
    coverage: CoverageAssessment,
    requested_scopes: Set[Scope],
    now: datetime,
) -> SearchDecision:
    _require_timezone_aware(now)
    valid_candidates = [item for item in candidates if _is_valid_candidate(item, now)]
    missing_scopes = _missing_scopes(coverage, requested_scopes)
    if len(valid_candidates) < _MINIMUM_CANDIDATES:
        reason = "유효 기사 5건 미만"
    elif _newest_candidate_is_older_than(valid_candidates, now, _FRESHNESS_WINDOW):
        reason = "최신 기사가 30일 초과"
    elif missing_scopes:
        reason = "요청 범위 근거 부족"
    else:
        return SearchDecision(required=False, reason="검색 불필요", missing_scopes=[])
    return SearchDecision(required=True, reason=reason, missing_scopes=missing_scopes)


def _missing_scopes(
    coverage: CoverageAssessment, requested_scopes: Set[Scope]
) -> list[Scope]:
    return [
        scope
        for scope in _SCOPE_ORDER
        if scope in requested_scopes and getattr(coverage, scope.lower()) == "INSUFFICIENT"
    ]


def _newest_candidate_is_older_than(
    candidates: Sequence[NewsCandidate], now: datetime, window: timedelta
) -> bool:
    newest = max(item.published_at for item in candidates)
    _require_timezone_aware(newest)
    return now - newest > window


def _is_valid_candidate(candidate: NewsCandidate, now: datetime) -> bool:
    _require_timezone_aware(candidate.published_at)
    age = now - candidate.published_at
    return timedelta(0) <= age <= timedelta(days=90)


def _require_timezone_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
