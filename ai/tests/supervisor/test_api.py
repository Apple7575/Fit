import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from ai.serve import build_app
from ai.supervisor.api import (
    assemble_supervisor_service,
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
    SupervisorRunRequest,
)
from ai.tests.supervisor.test_adapters import (
    FakeJdService,
    FakePositionService,
    FakeWritingService,
)
from ai.tests.supervisor.test_graph import FakeModel
from ai.writing_coaching.api import get_writing_service


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
WRITING_ONLY_REQUEST = {
    "instruction": "두괄식으로 고쳐줘",
    "documents": [
        {
            "document_id": "essay",
            "document_type": "SELF_INTRO",
            "text": "프로젝트에서 백엔드 개발을 담당했습니다.",
        }
    ],
    "conversation": [],
    "agent_contexts": {
        "writing": {"question": "협업 경험", "char_limit": 700}
    },
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

    def test_redacts_writing_validation_error_in_failed_worker_responses(self):
        sentinel = "SECRET_Q7"
        request = {
            **WRITING_ONLY_REQUEST,
            "conversation": [
                {"message_id": "m1", "role": "USER", "content": sentinel},
                {"message_id": "m1", "role": "USER", "content": sentinel},
            ],
        }
        for selected_agents in (["writing"], ["jd", "writing"]):
            with self.subTest(selected_agents=selected_agents):
                writing_provider = Mock(
                    side_effect=AssertionError("invalid input must not call Writing")
                )
                service = assemble_supervisor_service(
                    supervisor_model=FakeModel([
                        SupervisorPlan(selected_agents=selected_agents, reason="검토")
                    ]),
                    jd_provider=FakeJdService,
                    position_provider=FakePositionService,
                    writing_provider=writing_provider,
                )
                app.dependency_overrides[get_supervisor_service_provider] = (
                    lambda: lambda: service
                )
                contexts = {**request["agent_contexts"]}
                if "jd" in selected_agents:
                    contexts["jd"] = {"job_context_id": "jctx"}

                response = TestClient(app).post(
                    "/internal/runs", json={**request, "agent_contexts": contexts}
                )

                self.assertNotIn(sentinel, response.text)
                if selected_agents == ["writing"]:
                    self.assertEqual(response.status_code, 502)
                    body = response.json()["detail"]
                    self.assertEqual(body["code"], "ALL_AGENTS_FAILED")
                else:
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["status"], "PARTIAL")
                writing_result = body["agent_results"][-1]
                self.assertEqual(writing_result, {
                    "agent": "writing", "status": "FAILED", "result": None,
                    "error": "writing worker failed",
                })
                writing_provider.assert_not_called()


class SupervisorConfigurationApiTest(unittest.TestCase):
    def tearDown(self):
        get_supervisor_service.cache_clear()
        get_analysis_service.cache_clear()
        get_writing_service.cache_clear()
        app.dependency_overrides.clear()

    def test_writing_only_run_does_not_resolve_jd_or_position_services(self):
        jd_provider = Mock(side_effect=AssertionError("JD must remain lazy"))
        position_provider = Mock(
            side_effect=AssertionError("Position must remain lazy")
        )
        writing = FakeWritingService()
        service = assemble_supervisor_service(
            supervisor_model=FakeModel(
                [SupervisorPlan(selected_agents=["writing"], reason="첨삭 요청")]
            ),
            jd_provider=jd_provider,
            position_provider=position_provider,
            writing_provider=lambda: writing,
        )

        response = service.run(
            SupervisorRunRequest.model_validate(WRITING_ONLY_REQUEST)
        )

        self.assertEqual(response.agent_results[0].agent, "writing")
        jd_provider.assert_not_called()
        position_provider.assert_not_called()

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
                "ai.supervisor.api.get_writing_service",
                side_effect=AssertionError("Writing must remain lazy"),
            ),
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

    def test_writing_only_run_succeeds_through_mounted_api(self):
        writing = FakeWritingService()
        model = FakeModel(
            [SupervisorPlan(selected_agents=["writing"], reason="첨삭 요청")]
        )
        with (
            patch("ai.supervisor.api.load_qwen_config", return_value={}),
            patch("ai.supervisor.api.QwenSupervisorModel", return_value=model),
            patch(
                "ai.supervisor.api.get_analysis_service",
                side_effect=AssertionError("JD must remain lazy"),
            ),
            patch(
                "ai.supervisor.api.get_position_service",
                side_effect=AssertionError("Position must remain lazy"),
            ),
            patch("ai.supervisor.api.get_writing_service", return_value=writing),
        ):
            response = TestClient(build_app()).post(
                "/supervisor/internal/runs", json=WRITING_ONLY_REQUEST
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_results"][0]["agent"], "writing")
        self.assertEqual(writing.calls[0].question, "협업 경험")

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
                "/internal/runs",
                json={
                    **VALID_REQUEST,
                    "agent_contexts": {
                        "jd": None,
                        "position": None,
                        "writing": None,
                    },
                },
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

    def test_missing_writing_configuration_becomes_failed_worker_response(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            supervisor_env = temporary_root / "supervisor.env"
            supervisor_env.write_text(
                "QWEN_BASE_URL=http://qwen.test\n"
                "QWEN_MODEL=qwen-test\n"
                "QWEN_API_KEY=test-key\n",
                encoding="utf-8",
            )
            missing_writing_env = temporary_root / "missing-writing.env"
            environment = {
                "SUPERVISOR_QWEN_ENV_FILE": str(supervisor_env),
                "WRITING_QWEN_ENV_FILE": str(missing_writing_env),
            }
            model = FakeModel(
                [SupervisorPlan(selected_agents=["writing"], reason="첨삭 요청")]
            )
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("ai.supervisor.api.QwenSupervisorModel", return_value=model),
            ):
                get_supervisor_service.cache_clear()
                get_writing_service.cache_clear()
                response = TestClient(app, raise_server_exceptions=False).post(
                    "/internal/runs", json=WRITING_ONLY_REQUEST
                )

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "ALL_AGENTS_FAILED")
        self.assertEqual(detail["agent_results"][0]["agent"], "writing")
        self.assertEqual(detail["agent_results"][0]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
