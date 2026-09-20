"""리포트 생성·조회 서비스.

두 단계로 만든다.
1. 결정적 블록(수백 ms) → 바로 READY 로 저장한다. stage=DETERMINISTIC.
2. LLM 서술 블록(수십 초~수 분) → 백그라운드에서 덧붙여 stage=FULL 로 갱신한다.

그래서 GET 은 첫 요청부터 즉시 응답하고, 프론트는 stage 가 FULL 이 될 때까지 폴링하면 된다.
서술 단계가 실패해도 결정적 리포트는 그대로 남고 warnings 에 사유가 남는다.
READY 저장본이 있으면 force 가 아닌 한 다시 만들지 않는다.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from typing import Protocol

from .contracts import CompanyReport, ReportStatus
from .deterministic import build_deterministic_report
from .facts import CompanyFacts
from .repository import CompanyFactsRepository
from .store import ReportStore, StoredReport

LOGGER = logging.getLogger("ai.company_analysis")
PENDING_NARRATIVE_WARNING = "서술 블록을 생성하는 중입니다. stage 가 FULL 이 되면 완성된 리포트입니다."


class CompanyNotFoundError(LookupError):
    pass


class ReportEnricher(Protocol):
    """결정적 리포트에 서술 블록을 덧붙인다(LLM 단계). 실패하면 예외를 던진다."""

    def enrich(self, facts: CompanyFacts, report: CompanyReport) -> CompanyReport: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyAnalysisService:
    def __init__(
        self,
        *,
        repository: CompanyFactsRepository,
        store: ReportStore,
        enrichers: tuple[ReportEnricher, ...] = (),
        executor: Executor | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """executor 가 있으면 서술 단계를 백그라운드로 돌리고, 없으면 같은 호출 안에서 끝낸다."""
        self._repository = repository
        self._store = store
        self._enrichers = enrichers
        self._executor = executor
        self._clock = clock
        self._in_flight: set[str] = set()
        self._lock = threading.Lock()

    # --- 조회 ----------------------------------------------------------------

    def status(self, corp_code: str) -> ReportStatus | None:
        stored = self._store.get(corp_code)
        return stored.status if stored else None

    def get_or_generate(self, corp_code: str) -> StoredReport:
        """저장본이 READY 면 그대로, 아니면 결정적 리포트를 지금 만들어 돌려준다."""
        stored = self._store.get(corp_code)
        if stored is not None and stored.status.status == "READY" and stored.report is not None:
            return stored
        self.generate(corp_code, force=True)
        refreshed = self._store.get(corp_code)
        if refreshed is None:  # 저장소가 비정상일 때만 온다
            raise RuntimeError(f"리포트 저장 뒤 조회에 실패했습니다: {corp_code}")
        return refreshed

    def is_enriching(self, corp_code: str) -> bool:
        with self._lock:
            return corp_code in self._in_flight

    # --- 생성 ----------------------------------------------------------------

    def generate(self, corp_code: str, *, force: bool = False) -> ReportStatus:
        stored = self._store.get(corp_code)
        if stored is not None and stored.status.status == "READY" and not force:
            return stored.status

        facts = self._repository.load(corp_code)
        if facts is None:
            raise CompanyNotFoundError(f"기업을 찾을 수 없습니다: {corp_code}")

        self._store.mark(corp_code, "RUNNING")
        try:
            report = build_deterministic_report(facts, generated_at=self._clock())
        except ValueError as error:
            LOGGER.warning("deterministic report failed corp_code=%s: %s", corp_code, error)
            return self._store.mark(corp_code, "FAILED", error=str(error)[:500])

        if not self._enrichers:
            return self._store.save_ready(corp_code, report.model_copy(update={"stage": "FULL"}))

        if self._executor is None:
            return self._store.save_ready(corp_code, self._enrich(facts, report))

        status = self._store.save_ready(
            corp_code, report.model_copy(update={"warnings": [PENDING_NARRATIVE_WARNING, *report.warnings][:20]})
        )
        self._schedule(corp_code, facts, report)
        return status

    def _schedule(self, corp_code: str, facts: CompanyFacts, report: CompanyReport) -> None:
        with self._lock:
            if corp_code in self._in_flight:
                return
            self._in_flight.add(corp_code)

        def job() -> None:
            try:
                enriched = self._enrich(facts, report)
                self._store.save_ready(corp_code, enriched)
            except Exception:  # noqa: BLE001 — 백그라운드 실패는 로그로만 남긴다
                LOGGER.exception("background narrative failed corp_code=%s", corp_code)
            finally:
                with self._lock:
                    self._in_flight.discard(corp_code)

        assert self._executor is not None
        self._executor.submit(job)

    def _enrich(self, facts: CompanyFacts, report: CompanyReport) -> CompanyReport:
        """서술 단계를 순서대로 적용한다. 하나가 실패해도 결정적 블록은 살리고 warnings 에 남긴다."""
        for enricher in self._enrichers:
            try:
                report = enricher.enrich(facts, report)
            except Exception as error:  # noqa: BLE001
                LOGGER.exception("enricher %s failed corp_code=%s", type(enricher).__name__, report.corp_code)
                report = report.model_copy(
                    update={
                        "warnings": [
                            *report.warnings,
                            f"{type(enricher).__name__} 서술 생성에 실패해 확정 데이터 블록만 제공합니다.",
                        ][:20]
                    }
                )
        warnings = [w for w in report.warnings if w != PENDING_NARRATIVE_WARNING]
        return report.model_copy(update={"stage": "FULL", "warnings": warnings})
