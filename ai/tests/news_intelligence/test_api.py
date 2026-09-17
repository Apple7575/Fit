import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.news_intelligence.api import app, get_news_service
from ai.news_intelligence.contracts import NewsAnalysisResponse, NewsContext
from ai.news_intelligence.model import NewsOutputError, QwenNewsModel
from ai.news_intelligence.repository import (
    CompanyNotFound,
    JobContextNotFound,
    NewsSourceUnavailable,
)


VALID_REQUEST = {
    "instruction": "최근 기업과 직무 변화를 알려줘",
    "job_context_id": "ctx-1",
    "corp_code": "00126380",
    "conversation": [],
}
RESPONSE = NewsAnalysisResponse.model_validate({
    "message": "확인된 변화가 있습니다.",
    "analysis": {
        "analysis_status": "INSUFFICIENT_EVIDENCE",
        "company": {"corp_code": "00126380", "corp_name": "테스트기업"},
        "window": {"from": "2026-06-18", "to": "2026-09-16"},
        "signals": [],
        "coverage": {
            "company": "INSUFFICIENT",
            "industry": "INSUFFICIENT",
            "role": "INSUFFICIENT",
        },
        "external_search": {"used": False, "reason": "근거 부족"},
    },
})


class FakeNewsService:
    def __init__(self, result=RESPONSE, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class QwenFailureService:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def analyze(self, request):
        return QwenNewsModel(
            {"base_url": "https://qwen.example.test", "model": "test", "api_key": "test"},
            self._call_qwen,
        ).classify_coverage(
            NewsContext(
                corp_code=request.corp_code,
                corp_name="테스트기업",
                position_name="백엔드 개발자",
                jd_text="API 서비스 개발",
            ),
            [],
            request.instruction,
        )

    def _call_qwen(self, *args, **kwargs):
        raise self._error


class NewsApiTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeNewsService()
        app.dependency_overrides[get_news_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        get_news_service.cache_clear()

    def test_returns_structured_analysis(self):
        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), RESPONSE.model_dump(mode="json"))
        self.assertEqual(self.service.requests[0].model_dump(), VALID_REQUEST)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_uses_cached_service(self):
        response = self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_rejects_invalid_request_without_calling_service(self):
        response = self.client.post("/internal/analyses", json={
            **VALID_REQUEST,
            "corp_code": "not-a-corp-code",
        })

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.requests, [])

    def test_maps_job_context_not_found_to_contract_code(self):
        self.service.error = JobContextNotFound("ctx-1")

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": {"code": "JOB_CONTEXT_NOT_FOUND"}})

    def test_maps_company_not_found_to_contract_code(self):
        self.service.error = CompanyNotFound("00126380")

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": {"code": "COMPANY_NOT_FOUND"}})

    def test_maps_unavailable_repository_to_safe_contract_code(self):
        self.service.error = NewsSourceUnavailable()

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "NEWS_SOURCE_UNAVAILABLE"}})

    def test_maps_exhausted_model_to_safe_contract_code(self):
        self.service.error = NewsOutputError("contains a secret model error")

        response = self.client.post("/internal/analyses", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": {"code": "NEWS_MODEL_UNAVAILABLE"}})

    def test_maps_qwen_boundary_failures_to_safe_contract_code(self):
        for error in (
            RuntimeError("contains a secret endpoint"),
            ValueError("contains a secret configuration"),
            TimeoutError("contains a secret endpoint"),
            ConnectionRefusedError("contains a secret endpoint"),
        ):
            with self.subTest(error=type(error).__name__):
                app.dependency_overrides[get_news_service] = lambda error=error: QwenFailureService(error)

                response = TestClient(app, raise_server_exceptions=False).post(
                    "/internal/analyses", json=VALID_REQUEST,
                )

                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"detail": {"code": "NEWS_MODEL_UNAVAILABLE"}})

    def test_does_not_map_arbitrary_service_errors_to_model_unavailable(self):
        for error in (RuntimeError("unexpected"), ValueError("unexpected")):
            with self.subTest(error=type(error).__name__):
                self.service.error = error

                response = TestClient(app, raise_server_exceptions=False).post(
                    "/internal/analyses", json=VALID_REQUEST,
                )

                self.assertEqual(response.status_code, 500)

class NewsConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()
        get_news_service.cache_clear()

    def test_missing_database_configuration_returns_safe_503(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / "qwen.env"
            env_file.write_text(
                "QWEN_BASE_URL=https://qwen.example.test\\nQWEN_MODEL=test\\nQWEN_API_KEY=test\\n",
                encoding="utf-8",
            )
            environment = {
                "JD_DATABASE_URL": "",
                "NEWS_QWEN_ENV_FILE": str(env_file),
                "QWEN_BASE_URL": "",
                "QWEN_MODEL": "",
                "QWEN_API_KEY": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                get_news_service.cache_clear()
                response = TestClient(app, raise_server_exceptions=False).get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "NEWS_CONFIGURATION_UNAVAILABLE"}})

    def test_missing_qwen_configuration_returns_safe_503(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = {
                "JD_DATABASE_URL": "postgresql://user:secret@db.example.test:5432/news",
                "NEWS_QWEN_ENV_FILE": str(Path(temporary_directory) / "missing.env"),
                "QWEN_BASE_URL": "",
                "QWEN_MODEL": "",
                "QWEN_API_KEY": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                get_news_service.cache_clear()
                response = TestClient(app, raise_server_exceptions=False).get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "NEWS_CONFIGURATION_UNAVAILABLE"}})


if __name__ == "__main__":
    unittest.main()
