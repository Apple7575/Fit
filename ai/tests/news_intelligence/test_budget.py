import io
import unittest
from unittest.mock import patch

from ai.news_intelligence.model import NewsModelUnavailable, NewsOutputError, QwenNewsModel
from ai.news_intelligence.repository import NewsSourceUnavailable, PostgresNewsRepository
from ai.news_intelligence.search_provider import GoogleNewsRssProvider
from ai.news_intelligence.service import NewsIntelligenceService
from ai.tests.news_intelligence.test_repository import FakeConnection
from ai.tests.news_intelligence.test_search_provider import RSS_BYTES
from ai.tests.news_intelligence.test_service import (
    CONTEXT, NOW, REQUEST, FakeModel, FakeProvider, FakeRepository, candidates,
)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class NewsBudgetTest(unittest.TestCase):
    def service(self, clock, *, repository=None, provider=None, model=None):
        return NewsIntelligenceService(
            repository or FakeRepository(candidates()), provider or FakeProvider([]),
            model or FakeModel(), now=lambda: NOW, monotonic=clock,
        )

    def test_remaining_budget_bounds_rss_and_qwen_after_coverage_retry(self):
        clock = Clock()

        class Repository(FakeRepository):
            def load_context(self, *args):
                clock.advance(10)
                return super().load_context(*args)

        model_timeouts = []
        def qwen(config, messages, **kwargs):
            model_timeouts.append(kwargs["timeout_seconds"])
            if len(model_timeouts) <= 2:
                clock.advance(30)
                if len(model_timeouts) == 1:
                    return {"output": {}}
                return {"output": {
                    "company": "COVERED", "industry": "INSUFFICIENT", "role": "COVERED",
                    "requested_scopes": ["COMPANY", "INDUSTRY", "ROLE"],
                }}
            clock.advance(9)
            return {"output": {"signals": []}}

        rss_timeouts = []
        def urlopen(request, *, timeout):
            rss_timeouts.append(timeout)
            clock.advance(10)
            return io.BytesIO(RSS_BYTES)

        service = self.service(
            clock, repository=Repository(candidates()), model=QwenNewsModel({}, qwen),
            provider=GoogleNewsRssProvider(now=lambda: NOW, monotonic=clock),
        )
        with patch("ai.news_intelligence.search_provider.urlopen", urlopen):
            response = service.analyze(REQUEST)

        self.assertEqual(model_timeouts, [45, 45, 10])
        self.assertEqual(rss_timeouts, [20])
        self.assertEqual(response.analysis.analysis_status, "INSUFFICIENT_EVIDENCE")

    def test_expired_model_output_suppresses_retry_and_late_success(self):
        for malformed in (True, False):
            with self.subTest(malformed=malformed):
                clock = Clock()
                calls = []
                def qwen(config, messages, **kwargs):
                    calls.append(kwargs)
                    clock.advance(90)
                    return {"output": {} if malformed else {"signals": []}}

                service = self.service(
                    clock, repository=FakeRepository(candidates(4)),
                    model=QwenNewsModel({}, qwen),
                )
                with self.assertRaises(NewsModelUnavailable):
                    service.analyze(REQUEST)
                self.assertEqual(len(calls), 1)

    def test_custom_model_cannot_retry_after_deadline(self):
        clock = Clock()
        class Model(FakeModel):
            def classify_coverage(self, *args):
                self.coverage_calls += 1
                clock.advance(90)
                raise NewsOutputError("invalid")

        model = Model()
        with self.assertRaises(NewsModelUnavailable):
            self.service(clock, model=model).analyze(REQUEST)
        self.assertEqual(model.coverage_calls, 1)

        # A failed request must not leave an expired deadline on this worker thread.
        timeouts = []
        def qwen(config, messages, **kwargs):
            timeouts.append(kwargs["timeout_seconds"])
            return {"output": {"signals": []}}
        QwenNewsModel({}, qwen).extract_signals(CONTEXT, candidates(), "news", [])
        self.assertEqual(timeouts, [45])

    def test_source_deadline_exhaustion_is_not_insufficient_or_completed(self):
        for phase in ("repository", "provider"):
            with self.subTest(phase=phase):
                clock = Clock()
                class Repository(FakeRepository):
                    def load_context(self, *args):
                        if phase == "repository":
                            clock.advance(90)
                        return super().load_context(*args)

                class Provider(FakeProvider):
                    def search(self, *args, **kwargs):
                        clock.advance(90)
                        return []

                provider, model = Provider([]), FakeModel()
                with self.assertRaises(NewsSourceUnavailable):
                    self.service(clock, repository=Repository([]), provider=provider,
                                 model=model).analyze(REQUEST)
                self.assertEqual(model.extract_calls, 0)

    def test_sql_timeout_shrinks_with_remaining_budget_and_prevents_next_connect(self):
        clock = Clock()
        connection = FakeConnection(
            context_row={"position_name": CONTEXT.position_name, "jd_text": CONTEXT.jd_text,
                         "role_elements": []},
            company_row={"corp_code": CONTEXT.corp_code, "corp_name": CONTEXT.corp_name,
                         "industry_name": CONTEXT.industry_name},
        )
        connects = []
        def connect():
            connects.append(True)
            clock.advance(88)
            return connection

        repository = PostgresNewsRepository("postgresql://unused", connect=connect)
        with self.assertRaises(NewsSourceUnavailable):
            self.service(clock, repository=repository).analyze(REQUEST)
        self.assertEqual(len(connects), 1)
        self.assertEqual([params for _, params in connection.timeout_calls], [("2000",), ("2000",)])
