"""리포트 생성·조회 서비스.

생성은 결정적 블록 → (이후 단계) LLM 서술 블록 순서로 한다. 결정적 블록만으로도
리포트는 완전하므로, 서술 단계가 실패하면 결정적 리포트를 그대로 READY 로 저장하고
warnings 에 남긴다. 저장소에 READY 가 있으면 force 가 아닌 한 다시 만들지 않는다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from .contracts import CompanyReport, ReportStatus
from .deterministic import build_deterministic_report
from .facts import CompanyFacts
from .repository import CompanyFactsRepository
from .store import ReportStore, StoredReport

LOGGER = logging.getLogger("ai.company_analysis")


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
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._store = store
        self._enrichers = enrichers
        self._clock = clock

    # --- 조회 ----------------------------------------------------------------

    def status(self, corp_code: str) -> ReportStatus | None:
        stored = self._store.get(corp_code)
        return stored.status if stored else None

    def get_or_generate(self, corp_code: str) -> StoredReport:
        """저장본이 READY 면 그대로, 아니면 지금 만든다. 결정적 생성은 수백 ms 라 동기로 한다."""
        stored = self._store.get(corp_code)
        if stored is not None and stored.status.status == "READY" and stored.report is not None:
            return stored
        self.generate(corp_code, force=True)
        refreshed = self._store.get(corp_code)
        if refreshed is None:  # 저장소가 비정상일 때만 온다
            raise RuntimeError(f"리포트 저장 뒤 조회에 실패했습니다: {corp_code}")
        return refreshed

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

        for enricher in self._enrichers:
            try:
                report = enricher.enrich(facts, report)
            except Exception as error:  # noqa: BLE001 — 서술 실패가 리포트 전체를 막으면 안 된다
                LOGGER.exception("enricher %s failed corp_code=%s", type(enricher).__name__, corp_code)
                report = report.model_copy(
                    update={
                        "warnings": [
                            *report.warnings,
                            f"{type(enricher).__name__} 서술 생성에 실패해 확정 데이터 블록만 제공합니다.",
                        ][:20]
                    }
                )
        return self._store.save_ready(corp_code, report)
