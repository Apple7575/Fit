from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from ai.company_analysis.api import create_app
from ai.company_analysis.facts import CompanyFacts, CompanyProfile, MetricPoint, TextAttr
from ai.company_analysis.repository import peers_from_rows, profile_from_row
from ai.company_analysis.service import CompanyAnalysisService
from ai.company_analysis.store import InMemoryReportStore

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)
T = 1_000_000_000_000


def _facts(corp_code: str = "00164779") -> CompanyFacts:
    return CompanyFacts(
        profile=CompanyProfile(corp_code, "SK하이닉스", "26", "전자", "2612", None, "1949-10-15", None, None, None),
        metrics=(
            MetricPoint(2024, "revenue", 66.19 * T, "CFS"),
            MetricPoint(2025, "revenue", 97.147 * T, "CFS"),
            MetricPoint(2025, "operating_profit", 47.2 * T, "CFS"),
        ),
        texts=(TextAttr(2025, "main_business", 0, "메모리 반도체를 주력으로 생산합니다."),),
    )


class FakeRepository:
    def __init__(self, facts: dict[str, CompanyFacts]) -> None:
        self._facts = facts
        self.loads = 0

    def load(self, corp_code: str) -> CompanyFacts | None:
        self.loads += 1
        return self._facts.get(corp_code)


class FailingEnricher:
    def enrich(self, facts, report):
        raise RuntimeError("LLM down")


class MarkingEnricher:
    def enrich(self, facts, report):
        return report.model_copy(update={"corp_name": report.corp_name + " (서술 완료)"})


class ImmediateExecutor:
    """제출 즉시 같은 스레드에서 실행한다. 백그라운드 경로를 결정적으로 테스트하기 위한 것."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


def _service(enrichers=(), executor=None) -> tuple[CompanyAnalysisService, FakeRepository, InMemoryReportStore]:
    repository = FakeRepository({"00164779": _facts()})
    store = InMemoryReportStore(clock=lambda: NOW)
    service = CompanyAnalysisService(
        repository=repository, store=store, enrichers=enrichers, executor=executor, clock=lambda: NOW
    )
    return service, repository, store


def _client(service: CompanyAnalysisService) -> TestClient:
    return TestClient(create_app(lambda: service))


class ServiceTest(unittest.TestCase):
    def test_generate_then_cached(self):
        service, repository, _ = _service()
        first = service.generate("00164779")
        self.assertEqual(first.status, "READY")
        self.assertEqual(first.fiscal_year, 2025)
        second = service.generate("00164779")
        self.assertEqual(repository.loads, 1, "READY 저장본이 있으면 다시 만들지 않는다")
        self.assertEqual(second, first)
        service.generate("00164779", force=True)
        self.assertEqual(repository.loads, 2)

    def test_enricher_failure_keeps_deterministic_report(self):
        service, _, store = _service(enrichers=(FailingEnricher(),))
        status = service.generate("00164779")
        self.assertEqual(status.status, "READY")
        report = store.get("00164779").report
        self.assertEqual(report.stage, "FULL")
        self.assertTrue(any("FailingEnricher" in w for w in report.warnings))
        self.assertEqual([s.type for s in report.sections], ["BUSINESS", "FINANCIALS"])

    def test_no_enrichers_is_full_immediately(self):
        service, _, store = _service()
        service.generate("00164779")
        self.assertEqual(store.get("00164779").report.stage, "FULL")

    def test_background_enrichment_upgrades_stage(self):
        class RecordingStore(InMemoryReportStore):
            def __init__(self):
                super().__init__(clock=lambda: NOW)
                self.saved = []

            def save_ready(self, corp_code, report):
                self.saved.append(report)
                return super().save_ready(corp_code, report)

        repository = FakeRepository({"00164779": _facts()})
        store = RecordingStore()
        service = CompanyAnalysisService(
            repository=repository, store=store, enrichers=(MarkingEnricher(),), executor=ImmediateExecutor(), clock=lambda: NOW
        )
        service.generate("00164779")
        self.assertEqual([r.stage for r in store.saved], ["DETERMINISTIC", "FULL"], "결정적 리포트를 먼저 저장하고 서술 뒤 갱신한다")
        self.assertTrue(any("생성하는 중" in w for w in store.saved[0].warnings))
        final = store.get("00164779").report
        self.assertEqual(final.corp_name, "SK하이닉스 (서술 완료)")
        self.assertFalse(any("생성하는 중" in w for w in final.warnings))
        self.assertFalse(service.is_enriching("00164779"))


class ApiTest(unittest.TestCase):
    def test_get_report_generates_on_first_call(self):
        service, repository, _ = _service()
        client = _client(service)
        response = client.get("/internal/reports/00164779")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema_version"], "company-report-v1")
        self.assertEqual(body["corp_name"], "SK하이닉스")
        self.assertEqual(body["intro"]["citations"][0]["source_type"], "COMPANY_PROFILE")
        financials = next(s for s in body["sections"] if s["type"] == "FINANCIALS")
        table = financials["blocks"][0]
        self.assertEqual(table["kind"], "table")
        self.assertEqual(table["rows"][0], ["매출액", 66.2, 97.1])
        client.get("/internal/reports/00164779")
        self.assertEqual(repository.loads, 1)

    def test_status_and_post(self):
        service, _, _ = _service()
        client = _client(service)
        self.assertEqual(client.get("/internal/reports/00164779/status").status_code, 404)
        created = client.post("/internal/reports", json={"corp_code": "00164779"})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["status"], "READY")
        status = client.get("/internal/reports/00164779/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["fiscal_year"], 2025)

    def test_unknown_company_and_bad_code(self):
        service, _, _ = _service()
        client = _client(service)
        self.assertEqual(client.get("/internal/reports/00000001").status_code, 404)
        self.assertEqual(client.get("/internal/reports/abc").status_code, 422)
        self.assertEqual(client.post("/internal/reports", json={"corp_code": "00000001"}).status_code, 404)
        self.assertEqual(client.post("/internal/reports", json={"corp_code": "1"}).status_code, 422)

    def test_health(self):
        service, _, _ = _service()
        self.assertEqual(_client(service).get("/health").json(), {"status": "ok"})


class RepositoryRowsTest(unittest.TestCase):
    def test_profile_from_row_strips_blank(self):
        profile = profile_from_row(
            {"corp_code": "00164779", "corp_name": "SK하이닉스", "industry_code": "26", "industry_name": None,
             "induty_code": "2612", "ceo_nm": " ", "established_date": "1949-10-15", "address": None,
             "homepage_url": "www.skhynix.com", "stock_code": "000660"}
        )
        self.assertIsNone(profile.ceo_name)
        self.assertEqual(profile.homepage_url, "www.skhynix.com")

    def test_peers_from_rows_prefers_consolidated(self):
        rows = [
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025, "metric_code": "revenue", "metric_value": 300 * T, "fs_div": "OFS"},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025, "metric_code": "revenue", "metric_value": 333 * T, "fs_div": "CFS"},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025, "metric_code": "employee_count", "metric_value": 128881, "fs_div": None},
        ]
        products = [{"corp_code": "00126380", "value_text": "TV"}, {"corp_code": "00126380", "value_text": " "}]
        peers = peers_from_rows(rows, products)
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0].revenue, 333 * T)
        self.assertEqual(peers[0].employee_count, 128881)
        self.assertEqual(peers[0].main_products, ("TV",))


if __name__ == "__main__":
    unittest.main()
