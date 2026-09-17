from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from ai.news_intelligence.contracts import (
    CoverageAssessment,
    NewsAnalysisRequest,
    NewsCandidate,
    NewsContext,
    SignalDraft,
)
from ai.news_intelligence.model import NewsOutputError
from ai.news_intelligence.repository import NewsSourceUnavailable
from ai.news_intelligence.search_provider import ExternalSearchUnavailable
from ai.news_intelligence.service import NewsIntelligenceService


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
REQUEST = NewsAnalysisRequest(
    instruction="최근 기업과 직무 변화를 알려줘",
    job_context_id="ctx-1",
    corp_code="00126380",
)
CONTEXT = NewsContext(
    corp_code="00126380",
    corp_name="테스트기업",
    industry_name="테스트산업",
    position_name="백엔드 개발자",
    jd_text="API 서비스 개발",
    role_elements=[{"name": "API 개발"}],
)
COVERED = CoverageAssessment(
    company="COVERED", industry="COVERED", role="COVERED",
)
MISSING_INDUSTRY = CoverageAssessment(
    company="COVERED", industry="INSUFFICIENT", role="COVERED",
)


def candidates(
    count: int = 5,
    *,
    days_old: int = 1,
    origin: str = "STORED",
    start: int = 1,
) -> list[NewsCandidate]:
    return [
        NewsCandidate(
            article_id=f"{origin.lower()}:{index}",
            origin=origin,
            title=f"서비스 투자 확대 {index}",
            publisher=f"매체 {index}",
            published_at=NOW - timedelta(days=days_old),
            url=f"https://example.test/{origin.lower()}/{index}",
        )
        for index in range(start, start + count)
    ]


class FakeRepository:
    def __init__(self, stored: list[NewsCandidate], *, error: Exception | None = None) -> None:
        self.stored = stored
        self.error = error
        self.context_calls: list[tuple[str, str]] = []
        self.recent_calls: list[tuple[str, datetime, int]] = []

    def load_context(self, job_context_id: str, corp_code: str) -> NewsContext:
        self.context_calls.append((job_context_id, corp_code))
        if self.error:
            raise self.error
        return CONTEXT

    def list_recent(self, corp_code: str, since: datetime, limit: int) -> list[NewsCandidate]:
        self.recent_calls.append((corp_code, since, limit))
        return self.stored


class FakeProvider:
    def __init__(self, rows: list[NewsCandidate], *, error: Exception | None = None) -> None:
        self.rows = rows
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def search(self, corp_name, position_name, missing_scopes, from_date, to_date, limit):
        self.calls.append((corp_name, position_name, tuple(missing_scopes), from_date, to_date, limit))
        if self.error:
            raise self.error
        return self.rows


class FakeModel:
    def __init__(
        self,
        *,
        coverage: CoverageAssessment = COVERED,
        errors: list[Exception] | None = None,
    ) -> None:
        self.coverage = coverage
        self.errors = list(errors or [])
        self.coverage_calls = 0
        self.extract_calls = 0
        self.extract_candidates: list[list[NewsCandidate]] = []

    def classify_coverage(self, context, rows, instruction):
        self.coverage_calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.coverage

    def extract_signals(self, context, rows, instruction, conversation):
        self.extract_calls += 1
        self.extract_candidates.append(list(rows))
        if self.errors:
            raise self.errors.pop(0)
        return [SignalDraft(
            scope="COMPANY",
            title="서비스 투자 확대",
            summary="서비스 투자 확대",
            jd_relevance="API 서비스 개발",
            preparation_checks=["경험을 확인하세요."],
            source_ids=[rows[0].article_id],
        )]


def build_service(
    *,
    stored: list[NewsCandidate] | None = None,
    external: list[NewsCandidate] | None = None,
    coverage: CoverageAssessment = COVERED,
    model: FakeModel | None = None,
    repository_error: Exception | None = None,
    provider_error: Exception | None = None,
):
    repository = FakeRepository(stored if stored is not None else candidates(), error=repository_error)
    provider = FakeProvider(external or [], error=provider_error)
    model = model or FakeModel(coverage=coverage)
    return (
        NewsIntelligenceService(repository, provider, model, now=lambda: NOW),
        provider,
        repository,
        model,
    )


class NewsIntelligenceServiceTest(unittest.TestCase):
    def test_empty_extracted_signals_are_insufficient_even_with_candidates(self):
        class EmptyModel(FakeModel):
            def extract_signals(self, *args):
                return []

        service, _, _, _ = build_service(model=EmptyModel())
        response = service.analyze(REQUEST)
        self.assertEqual(response.analysis.analysis_status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(response.analysis.signals, [])

    def test_sufficient_stored_news_skips_external_search(self):
        service, provider, repository, model = build_service()

        response = service.analyze(REQUEST)

        self.assertEqual(provider.calls, [])
        self.assertFalse(response.analysis.external_search.used)
        self.assertEqual(model.coverage_calls, 1)
        self.assertEqual(repository.recent_calls[0][1], NOW - timedelta(days=90))
        self.assertEqual(repository.recent_calls[0][2], 20)

    def test_gap_uses_external_search_once_without_saving(self):
        service, provider, repository, model = build_service(
            coverage=MISSING_INDUSTRY,
            external=candidates(1, origin="EXTERNAL", start=11),
        )

        response = service.analyze(REQUEST)

        self.assertEqual(len(provider.calls), 1)
        self.assertFalse(hasattr(repository, "save"))
        self.assertTrue(response.analysis.external_search.used)
        self.assertEqual(provider.calls[0][2], ("INDUSTRY",))
        self.assertEqual(provider.calls[0][5], 20)
        self.assertEqual(model.extract_calls, 1)

    def test_no_evidence_returns_insufficient_without_signal_extraction(self):
        service, provider, _, model = build_service(stored=[], external=[])

        response = service.analyze(REQUEST)

        self.assertEqual(response.analysis.analysis_status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(response.analysis.signals, [])
        self.assertEqual(model.extract_calls, 0)
        self.assertEqual(len(provider.calls), 1)

    def test_future_only_stored_news_is_insufficient_without_signal_extraction(self):
        service, provider, _, model = build_service(
            stored=candidates(1, days_old=-1), external=[],
        )

        response = service.analyze(REQUEST)

        self.assertEqual(response.analysis.analysis_status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(model.extract_calls, 0)
        self.assertEqual(len(provider.calls), 1)

    def test_filters_future_stored_and_external_rows_before_model_extraction(self):
        stored = [
            *candidates(4),
            *candidates(1, days_old=-1, start=5),
        ]
        external = [
            *candidates(1, origin="EXTERNAL", start=101),
            *candidates(1, days_old=-1, origin="EXTERNAL", start=102),
        ]
        service, provider, _, model = build_service(stored=stored, external=external)

        service.analyze(REQUEST)

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(
            [item.article_id for item in model.extract_candidates[0]],
            ["stored:1", "stored:2", "stored:3", "stored:4", "external:101"],
        )

    def test_repository_error_is_not_retried(self):
        service, provider, repository, _ = build_service(
            repository_error=NewsSourceUnavailable(),
        )

        with self.assertRaises(NewsSourceUnavailable):
            service.analyze(REQUEST)

        self.assertEqual(repository.context_calls, [("ctx-1", "00126380")])
        self.assertEqual(repository.recent_calls, [])
        self.assertEqual(provider.calls, [])

    def test_coverage_contract_error_retries_once_then_fails(self):
        model = FakeModel(errors=[NewsOutputError("bad-1"), NewsOutputError("bad-2")])
        service, provider, _, model = build_service(model=model)

        with self.assertRaises(NewsOutputError):
            service.analyze(REQUEST)

        self.assertEqual(model.coverage_calls, 2)
        self.assertEqual(model.extract_calls, 0)
        self.assertEqual(provider.calls, [])

    def test_signal_extraction_contract_error_retries_once_then_fails(self):
        model = FakeModel(errors=[NewsOutputError("bad-1"), NewsOutputError("bad-2")])
        service, _, _, model = build_service(stored=candidates(4), model=model)

        with self.assertRaises(NewsOutputError):
            service.analyze(REQUEST)

        self.assertEqual(model.coverage_calls, 0)
        self.assertEqual(model.extract_calls, 2)

    def test_invalid_extracted_citation_retries_signal_extraction_once(self):
        class InvalidCitationThenValidModel(FakeModel):
            def extract_signals(self, context, rows, instruction, conversation):
                self.extract_calls += 1
                self.extract_candidates.append(list(rows))
                source_id = "unknown:1" if self.extract_calls == 1 else rows[0].article_id
                return [SignalDraft(
                    scope="COMPANY",
                    title="서비스 투자 확대",
                    summary="서비스 투자 확대",
                    jd_relevance="API 서비스 개발",
                    preparation_checks=["경험을 확인하세요."],
                    source_ids=[source_id],
                )]

        model = InvalidCitationThenValidModel()
        service, _, _, model = build_service(stored=candidates(4), model=model)

        response = service.analyze(REQUEST)

        self.assertEqual(model.extract_calls, 2)
        self.assertEqual(response.analysis.signals[0].sources[0].article_id, "stored:1")

    def test_external_search_failure_uses_stored_fallback(self):
        service, provider, _, model = build_service(
            coverage=MISSING_INDUSTRY,
            provider_error=ExternalSearchUnavailable(),
        )

        response = service.analyze(REQUEST)

        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(response.analysis.external_search.used)
        self.assertEqual(model.extract_calls, 1)
        self.assertEqual(response.analysis.signals[0].sources[0].origin, "STORED")

    def test_exact_five_candidates_at_exactly_thirty_days_skips_search_when_covered(self):
        service, provider, _, model = build_service(stored=candidates(days_old=30))

        service.analyze(REQUEST)

        self.assertEqual(provider.calls, [])
        self.assertEqual(model.coverage_calls, 1)

    def test_limits_stored_candidates_to_twenty_before_model_calls(self):
        service, _, _, model = build_service(stored=candidates(21))

        service.analyze(REQUEST)

        self.assertEqual(len(model.extract_candidates[0]), 20)

    def test_stored_candidates_precede_external_candidates_after_merge(self):
        stored = candidates()
        external = candidates(1, origin="EXTERNAL", start=11)
        service, _, _, model = build_service(
            stored=stored,
            coverage=MISSING_INDUSTRY,
            external=external,
        )

        service.analyze(REQUEST)

        self.assertEqual(
            [candidate.article_id for candidate in model.extract_candidates[0]],
            [candidate.article_id for candidate in stored + external],
        )

    def test_search_caps_total_model_candidates_and_reserves_external_evidence(self):
        stored = candidates(20)
        external = candidates(20, origin="EXTERNAL", start=101)
        service, provider, _, model = build_service(
            stored=stored,
            coverage=MISSING_INDUSTRY,
            external=external,
        )

        service.analyze(REQUEST)

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(
            [candidate.article_id for candidate in model.extract_candidates[0]],
            [*(f"stored:{index}" for index in range(1, 16)),
             *(f"external:{index}" for index in range(101, 106))],
        )


if __name__ == "__main__":
    unittest.main()
