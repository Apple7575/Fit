import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.serve import build_app
from ai.supervisor.api import (
    app,
    get_analysis_service,
    get_supervisor_service,
    get_supervisor_service_provider,
)
from ai.supervisor.contracts import (
    AgentResult,
    AllAgentsFailedError,
    NoAvailableAgentError,
    SupervisorPlan,
)
from ai.tests.supervisor.test_adapters import FakeJdService, FakePositionService
from ai.tests.supervisor.test_graph import FakeModel


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
        app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service

        response = TestClient(app).post("/internal/runs", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID_RESPONSE)
        self.assertEqual(service.requests[0].instruction, "검토해줘")

    def test_keeps_pydantic_schema_errors_as_default_http_422(self):
        service = FakeService(result=VALID_RESPONSE)
        app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service
        request = {**VALID_REQUEST, "instruction": ""}

        response = TestClient(app).post("/internal/runs", json=request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(service.requests, [])

    def test_maps_no_available_agent_to_422(self):
        service = FakeService(error=NoAvailableAgentError("none"))
        app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service

        response = TestClient(app).post(
            "/internal/runs",
            json=VALID_REQUEST,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "NO_AVAILABLE_AGENT")

    def test_maps_all_failed_to_502(self):
        error = AllAgentsFailedError(
            [AgentResult(agent="jd", status="FAILED", error="RuntimeError: failed")]
        )
        service = FakeService(error=error)
        app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service

        response = TestClient(app).post("/internal/runs", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "ALL_AGENTS_FAILED")
        self.assertEqual(detail["agent_results"][0]["agent"], "jd")

    def test_does_not_map_domain_value_error_to_configuration_503(self):
        service = FakeService(error=ValueError("bad graph output"))
        app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service

        response = TestClient(app, raise_server_exceptions=False).post(
            "/internal/runs", json=VALID_REQUEST
        )

        self.assertEqual(response.status_code, 500)


class SupervisorConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        get_supervisor_service.cache_clear()
        get_analysis_service.cache_clear()
        app.dependency_overrides.clear()

    def test_cached_assembly_runs_both_adapters_through_mounted_api_in_process(self):
        get_supervisor_service.cache_clear()
        jd = FakeJdService()
        position = FakePositionService()
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd", "position"], reason="둘 다 검토")]
        )
        request = {
            **VALID_REQUEST,
            "conversation": [
                {"message_id": "m1", "role": "USER", "content": "백엔드 경험도 검토"}
            ],
            "agent_contexts": {
                "jd": {"job_context_id": "jctx"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": ["Spring 기반 API 개발"],
                    },
                },
            },
        }
        with (
            patch("ai.supervisor.api.load_qwen_config", return_value={}),
            patch("ai.supervisor.api.QwenSupervisorModel", return_value=model),
            patch("ai.supervisor.api.get_analysis_service", return_value=jd),
            patch("ai.supervisor.api.get_position_service", return_value=position),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("unexpected network call"),
            ),
        ):
            response = TestClient(build_app()).post(
                "/supervisor/internal/runs", json=request
            )
            first = get_supervisor_service()
            self.assertIs(first, get_supervisor_service())
            self.assertEqual(get_supervisor_service.cache_info().misses, 1)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["message"], "종합 결과")
        self.assertEqual(body["agent_results"], [
            {
                "agent": "jd", "status": "SUCCESS",
                "result": {"context_id": "jctx"}, "error": None,
            },
            {
                "agent": "position", "status": "SUCCESS",
                "result": {
                    "rubric": {"id": "experience-depth-v1"},
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": ["Spring 기반 API 개발"],
                    },
                },
                "error": None,
            },
        ])
        self.assertEqual(jd.calls, [("jctx", request["documents"])])
        self.assertEqual(position.calls, [
            (
                "experience-depth-v1",
                request["agent_contexts"]["position"]["position_context"],
                request["documents"],
                request["conversation"],
            )
        ])

    def test_malformed_body_is_422_before_unavailable_configuration(self):
        get_supervisor_service.cache_clear()
        with patch(
            "ai.supervisor.api.load_qwen_config",
            side_effect=ValueError("missing configuration"),
        ) as load_config:
            response = TestClient(app).post("/internal/runs", json={})

        self.assertEqual(response.status_code, 422)
        self.assertIsInstance(response.json()["detail"], list)
        load_config.assert_not_called()

    def test_empty_contexts_are_422_before_unavailable_configuration(self):
        get_supervisor_service.cache_clear()
        with patch(
            "ai.supervisor.api.load_qwen_config",
            side_effect=ValueError("missing configuration"),
        ) as load_config:
            response = TestClient(app).post(
                "/internal/runs", json={**VALID_REQUEST, "agent_contexts": {}}
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "NO_AVAILABLE_AGENT")
        load_config.assert_not_called()

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

    def test_missing_jd_qwen_configuration_returns_503(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            supervisor_env = temporary_root / "supervisor.env"
            supervisor_env.write_text(
                "QWEN_BASE_URL=http://qwen.test\n"
                "QWEN_MODEL=qwen-test\n"
                "QWEN_API_KEY=test-key\n",
                encoding="utf-8",
            )
            missing_jd_env = temporary_root / "missing-jd.env"
            environment = {
                "SUPERVISOR_QWEN_ENV_FILE": str(supervisor_env),
                "JD_QWEN_ENV_FILE": str(missing_jd_env),
            }
            with patch.dict(os.environ, environment, clear=True):
                get_supervisor_service.cache_clear()
                get_analysis_service.cache_clear()
                response = TestClient(app, raise_server_exceptions=False).post(
                    "/internal/runs", json=VALID_REQUEST
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "JD Qwen configuration unavailable",
        )


if __name__ == "__main__":
    unittest.main()
