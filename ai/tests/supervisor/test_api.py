import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.supervisor.api import app, get_supervisor_service
from ai.supervisor.contracts import (
    AgentResult,
    AllAgentsFailedError,
    NoAvailableAgentError,
)


VALID_REQUEST = {
    "instruction": "검토해줘",
    "documents": [
        {
            "document_id": "essay",
            "document_type": "SELF_INTRO",
            "text": "내용",
        }
    ],
    "conversation": [],
    "agent_contexts": {"jd": {"job_context_id": "jctx"}},
}
VALID_RESPONSE = {
    "status": "SUCCESS",
    "message": "JD 결과를 반영했습니다.",
    "plan": {"selected_agents": ["jd"], "reason": "JD 필요"},
    "agent_results": [
        {
            "agent": "jd",
            "status": "SUCCESS",
            "result": {"summary": {}},
            "error": None,
        }
    ],
}


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class SupervisorApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_returns_response_model_with_http_200(self):
        service = FakeService(result=VALID_RESPONSE)
        app.dependency_overrides[get_supervisor_service] = lambda: service

        response = TestClient(app).post("/internal/runs", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID_RESPONSE)
        self.assertEqual(service.requests[0].instruction, "검토해줘")

    def test_keeps_pydantic_schema_errors_as_default_http_422(self):
        service = FakeService(result=VALID_RESPONSE)
        app.dependency_overrides[get_supervisor_service] = lambda: service
        request = {**VALID_REQUEST, "instruction": ""}

        response = TestClient(app).post("/internal/runs", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(service.requests, [])

    def test_maps_no_available_agent_to_422(self):
        service = FakeService(error=NoAvailableAgentError("none"))
        app.dependency_overrides[get_supervisor_service] = lambda: service

        response = TestClient(app).post(
            "/internal/runs",
            json={**VALID_REQUEST, "agent_contexts": {}},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "NO_AVAILABLE_AGENT")

    def test_maps_all_failed_to_502(self):
        error = AllAgentsFailedError(
            [AgentResult(agent="jd", status="FAILED", error="RuntimeError: failed")]
        )
        app.dependency_overrides[get_supervisor_service] = lambda: FakeService(
            error=error
        )

        response = TestClient(app).post("/internal/runs", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "ALL_AGENTS_FAILED")
        self.assertEqual(detail["agent_results"][0]["agent"], "jd")

    def test_does_not_map_domain_value_error_to_configuration_503(self):
        app.dependency_overrides[get_supervisor_service] = lambda: FakeService(
            error=ValueError("bad graph output")
        )

        response = TestClient(app, raise_server_exceptions=False).post(
            "/internal/runs", json=VALID_REQUEST
        )

        self.assertEqual(response.status_code, 500)


class SupervisorConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        get_supervisor_service.cache_clear()
        app.dependency_overrides.clear()

    def test_missing_supervisor_qwen_configuration_returns_503(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_env = Path(temporary_directory) / "missing.env"
            environment = {
                "SUPERVISOR_QWEN_ENV_FILE": str(missing_env),
                "QWEN_BASE_URL": "",
                "QWEN_MODEL": "",
                "QWEN_API_KEY": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                get_supervisor_service.cache_clear()
                response = TestClient(app, raise_server_exceptions=False).post(
                    "/internal/runs", json=VALID_REQUEST
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "supervisor Qwen configuration unavailable",
        )


if __name__ == "__main__":
    unittest.main()
