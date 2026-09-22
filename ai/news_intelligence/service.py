from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
import logging
from time import monotonic as system_monotonic
from typing import Any

from ai.news_intelligence.budget import news_budget, remaining_timeout

from ai.news_intelligence.contracts import (
    CompanyReference,
    CoverageAssessment,
    ExternalSearch,
    NewsAnalysis,
    NewsAnalysisRequest,
    NewsAnalysisResponse,
    NewsCandidate,
    NewsSignal,
    SignalDraft,
)
from ai.news_intelligence.coverage import decide_external_search
from ai.news_intelligence.evidence import calculate_evidence_level, deduplicate_candidates
from ai.news_intelligence.model import NewsModel, NewsModelUnavailable, NewsOutputError, resolve_sources
from ai.news_intelligence.render import render_news_message
from ai.news_intelligence.repository import MAX_STORED_CANDIDATES, NewsRepository, NewsSourceUnavailable
from ai.news_intelligence.search_provider import (
    MAX_EXTERNAL_CANDIDATES,
    ExternalSearchUnavailable,
    NewsSearchProvider,
)


LOGGER = logging.getLogger(__name__)

_WINDOW_DAYS = 90
_MAX_MODEL_CANDIDATES = 20
_EXTERNAL_RESERVE = 5
_WORKER_BUDGET_SECONDS = 90


class NewsIntelligenceService:
    def __init__(
        self,
        repository: NewsRepository,
        search_provider: NewsSearchProvider,
        model: NewsModel,
        *,
        chat: Any | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._repository = repository
        self._search_provider = search_provider
        self._model = model
        # 신호 목록 위에서 이번 질문에 답하는 대화 서비스. 없으면 예전처럼 목록만 낸다.
        self._chat = chat
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or system_monotonic

    def analyze(self, request: NewsAnalysisRequest) -> NewsAnalysisResponse:
        with news_budget(_WORKER_BUDGET_SECONDS, self._monotonic):
            return self._analyze(request)

    def _analyze(self, request: NewsAnalysisRequest) -> NewsAnalysisResponse:
        now = self._now()
        _require_timezone_aware(now)
        since = now - timedelta(days=_WINDOW_DAYS)
        context = self._repository.load_context(request.job_context_id, request.corp_code)
        remaining_timeout(_WORKER_BUDGET_SECONDS, NewsSourceUnavailable)
        stored = deduplicate_candidates(_within_window(
            self._repository.list_recent(request.corp_code, since, MAX_STORED_CANDIDATES), now,
        ))[:MAX_STORED_CANDIDATES]
        remaining_timeout(_WORKER_BUDGET_SECONDS, NewsSourceUnavailable)

        coverage = _insufficient_coverage()
        deterministic_search = decide_external_search(
            stored, coverage, set(coverage.requested_scopes), now,
        )
        if deterministic_search.required and deterministic_search.reason in {
            "유효 기사 5건 미만", "최신 기사가 30일 초과",
        }:
            decision = deterministic_search
        else:
            coverage = _retry_news_output(
                lambda: self._model.classify_coverage(context, stored, request.instruction)
            )
            decision = decide_external_search(
                stored, coverage, set(coverage.requested_scopes), now,
            )

        external_search = ExternalSearch(used=False, reason=decision.reason)
        candidates = stored
        if decision.required:
            remaining_timeout(_WORKER_BUDGET_SECONDS, NewsSourceUnavailable)
            external_search = ExternalSearch(used=True, reason=decision.reason)
            try:
                external = self._search_provider.search(
                    context.corp_name,
                    context.position_name,
                    decision.missing_scopes,
                    since.date(),
                    now.date(),
                    MAX_EXTERNAL_CANDIDATES,
                    industry_name=context.industry_name,
                )
            except ExternalSearchUnavailable as error:
                # 응답에 남긴다. used=True 만 보면 검색이 잘 된 줄 안다.
                LOGGER.warning("external news search unavailable: %s", error.__cause__ or error)
                external_search = ExternalSearch(used=True, reason=f"{decision.reason}; 외부 검색 실패")
                external = []
            remaining_timeout(_WORKER_BUDGET_SECONDS, NewsSourceUnavailable)
            candidates = _merge_for_model(stored, _within_window(external, now))

        if not candidates:
            return self._response(
                context.corp_code,
                context.corp_name,
                since,
                now,
                [],
                coverage,
                external_search,
                status="INSUFFICIENT_EVIDENCE",
            )

        signals = _retry_news_output(
            lambda: _build_signals(
                self._model.extract_signals(
                    context, candidates, request.instruction, request.conversation,
                ),
                candidates,
                now,
            )
        )
        response = self._response(
            context.corp_code,
            context.corp_name,
            since,
            now,
            signals,
            coverage,
            external_search,
            status="COMPLETED" if signals else "INSUFFICIENT_EVIDENCE",
        )
        if signals and self._chat is not None:
            response = self._converse(response, context, request)
        return response

    def _converse(
        self, response: NewsAnalysisResponse, context: NewsContext, request: NewsAnalysisRequest,
    ) -> NewsAnalysisResponse:
        """신호 목록을 근거로 이번 질문에 답한 문장으로 message 를 바꾼다.

        `[COMPANY] 제목 / JD의 ~와 관련됩니다` 목록은 무엇을 물어도 같아서 방에서 대화가
        되지 않았다. 여기서 실패하면 그 목록으로 되돌아간다 — 대화는 신호 위에 얹는 것이고,
        답을 못 만들었다고 기사까지 숨길 이유는 없다.
        """
        try:
            reply = self._chat.respond(
                context=context,
                analysis=response.analysis,
                message=request.instruction,
                history=[turn.model_dump() for turn in request.conversation],
                timeout_seconds=remaining_timeout(_WORKER_BUDGET_SECONDS, NewsModelUnavailable),
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("news chat failed; falling back to the signal list")
            return response
        answer = str(reply.get("answer") or "").strip()
        if not answer:
            return response
        return response.model_copy(update={"message": answer})

    @staticmethod
    def _response(
        corp_code: str,
        corp_name: str,
        since: datetime,
        now: datetime,
        signals: Sequence[NewsSignal],
        coverage: CoverageAssessment,
        external_search: ExternalSearch,
        *,
        status: str,
    ) -> NewsAnalysisResponse:
        analysis = NewsAnalysis(
            analysis_status=status,
            company=CompanyReference(corp_code=corp_code, corp_name=corp_name),
            window={"from": since.date(), "to": now.date()},
            signals=list(signals),
            coverage=coverage,
            external_search=external_search,
        )
        return NewsAnalysisResponse(message=render_news_message(analysis), analysis=analysis)


def _insufficient_coverage() -> CoverageAssessment:
    return CoverageAssessment(
        company="INSUFFICIENT",
        industry="INSUFFICIENT",
        role="INSUFFICIENT",
    )


def _retry_news_output(operation: Callable[[], object]):
    for attempt in range(2):
        remaining_timeout(_WORKER_BUDGET_SECONDS, NewsModelUnavailable)
        try:
            result = operation()
        except NewsOutputError:
            remaining_timeout(_WORKER_BUDGET_SECONDS, NewsModelUnavailable)
            if attempt == 1:
                raise
        else:
            remaining_timeout(_WORKER_BUDGET_SECONDS, NewsModelUnavailable)
            return result


def _build_signals(
    drafts: Sequence[SignalDraft],
    candidates: Sequence[NewsCandidate],
    now: datetime,
) -> list[NewsSignal]:
    signals: list[NewsSignal] = []
    for index, draft in enumerate(drafts, start=1):
        sources = resolve_sources(draft.source_ids, candidates)
        signals.append(NewsSignal(
            signal_id=f"signal-{index:03d}",
            scope=draft.scope,
            title=draft.title,
            summary=draft.summary,
            jd_relevance=draft.jd_relevance,
            preparation_checks=draft.preparation_checks,
            evidence_level=calculate_evidence_level(sources, now),
            sources=sources,
        ))
    return signals


def _within_window(
    candidates: Sequence[NewsCandidate], now: datetime,
) -> list[NewsCandidate]:
    return [
        candidate
        for candidate in candidates
        if timedelta(0) <= now - candidate.published_at <= timedelta(days=_WINDOW_DAYS)
    ]


def _merge_for_model(
    stored: Sequence[NewsCandidate], external: Sequence[NewsCandidate],
) -> list[NewsCandidate]:
    unique_stored = deduplicate_candidates(stored)
    merged = deduplicate_candidates([*unique_stored, *external])
    unique_external = merged[len(unique_stored):]
    reserved_external = min(_EXTERNAL_RESERVE, len(unique_external))
    selected_stored = unique_stored[:_MAX_MODEL_CANDIDATES - reserved_external]
    remaining_capacity = _MAX_MODEL_CANDIDATES - len(selected_stored)
    return [*selected_stored, *unique_external[:remaining_capacity]]


def _require_timezone_aware(value: datetime) -> None:
    if value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
