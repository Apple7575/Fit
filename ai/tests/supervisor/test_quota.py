"""LLM 할당량(429)에 막혔을 때 사용자에게 무슨 말이 가는지.

GMS 를 거친 Gemini 가 할당량으로 429 를 주면 재시도해도 같은 답이 온다(2026-09-22 QA). 그때 담당이
"답을 만들지 못했습니다" 로 끝나면 사용자는 자소서 탓인지 서버 탓인지 모른다. 그래서 담당·총괄·뉴스
어디서 막히든 같은 코드(LLM_QUOTA_EXCEEDED)와 같은 한 문장을 낸다.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.llm.contracts import (
    QUOTA_ERROR_CODE,
    QUOTA_USER_MESSAGE,
    LlmHttpError,
    find_quota_error,
)
from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import SupervisorPlan
from ai.supervisor.graph import build_supervisor_graph, failure_fields
from ai.supervisor.service import SupervisorService
from ai.supervisor import api as supervisor_api


def _quota() -> LlmHttpError:
    return LlmHttpError("GMS", 429, '{"error":{"code":429,"status":"RESOURCE_EXHAUSTED"}}')


class FindQuotaErrorTest(unittest.TestCase):
    def test_finds_direct_429(self):
        self.assertIsNotNone(find_quota_error(_quota()))

    def test_ignores_other_statuses_and_types(self):
        self.assertIsNone(find_quota_error(LlmHttpError("GMS", 401, "unauthorized")))
        self.assertIsNone(find_quota_error(ValueError("x")))
        self.assertIsNone(find_quota_error(None))

    def test_walks_cause_chain(self):
        """글쓰기 담당은 LLM 오류를 WritingProviderError 로 감싸 올린다. 안쪽까지 봐야 한다."""
        try:
            try:
                raise _quota()
            except LlmHttpError as inner:
                raise RuntimeError("writing provider request failed") from inner
        except RuntimeError as outer:
            self.assertIsNotNone(find_quota_error(outer))

    def test_walks_context_chain(self):
        try:
            try:
                raise _quota()
            except LlmHttpError:
                raise RuntimeError("cleanup failed")  # from 없이 — __context__ 로만 이어진다
        except RuntimeError as outer:
            self.assertIsNotNone(find_quota_error(outer))


class FailureFieldsTest(unittest.TestCase):
    def test_quota_gets_user_message_and_code(self):
        self.assertEqual(
            failure_fields(_quota(), "ignored"),
            {"error": QUOTA_USER_MESSAGE, "error_code": QUOTA_ERROR_CODE},
        )

    def test_other_errors_keep_default_message(self):
        self.assertEqual(
            failure_fields(ValueError("bad"), "ValueError: bad"),
            {"error": "ValueError: bad", "error_code": None},
        )


class _Adapter:
    def __init__(self, name, behaviour):
        self.name = name
        self._behaviour = behaviour

    def is_available(self, context):
        return context is not None

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        return self._behaviour()


class _Model:
    def __init__(self, plan_error=None):
        self._plan_error = plan_error

    def create_plan(self, **_):
        if self._plan_error is not None:
            raise self._plan_error
        return SupervisorPlan(selected_agents=["position", "writing"], reason="둘 다")

    def aggregate(self, **_):
        return "종합"


def _client(model, adapters) -> TestClient:
    service = SupervisorService(build_supervisor_graph(model, AgentRegistry(adapters)))
    app = supervisor_api.app
    app.dependency_overrides[supervisor_api.get_supervisor_service_provider] = lambda: (lambda: service)
    return TestClient(app)


REQUEST = {
    "instruction": "검토해 주세요",
    "documents": [{"document_id": "d1", "document_type": "SELF_INTRO", "text": "초안"}],
    "agent_contexts": {
        "position": {"rubric_id": "experience-depth-v1", "position_context": {"position_name": "백엔드"}},
        "writing": {"question": "지원동기", "char_limit": 500},
    },
}


class SupervisorQuotaResponseTest(unittest.TestCase):
    def tearDown(self):
        supervisor_api.app.dependency_overrides.clear()

    def test_one_agent_blocked_by_quota_reports_message_on_that_agent_only(self):
        def blocked():
            raise _quota()

        client = _client(_Model(), [
            _Adapter("position", blocked),
            _Adapter("writing", lambda: {"status": "ANSWERED", "message": "답", "revision": None}),
        ])
        response = client.post("/internal/runs", json=REQUEST)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "PARTIAL")
        by_agent = {item["agent"]: item for item in body["agent_results"]}
        self.assertEqual(by_agent["position"]["error"], QUOTA_USER_MESSAGE)
        self.assertEqual(by_agent["position"]["error_code"], QUOTA_ERROR_CODE)
        self.assertEqual(by_agent["writing"]["status"], "SUCCESS")
        self.assertIsNone(by_agent["writing"]["error_code"])

    def test_writing_wrapped_quota_is_still_recognised(self):
        """글쓰기는 원인을 감싸고 문구를 가리는데, 할당량만은 가리지 않고 알려야 한다."""
        def blocked():
            try:
                raise _quota()
            except LlmHttpError as inner:
                raise RuntimeError("writing provider request failed") from inner

        client = _client(_Model(), [
            _Adapter("position", lambda: {"analysis_status": "NO_EXPERIENCE_CLAIM", "findings": [], "message": "없음"}),
            _Adapter("writing", blocked),
        ])
        body = client.post("/internal/runs", json=REQUEST).json()
        writing = next(item for item in body["agent_results"] if item["agent"] == "writing")
        self.assertEqual(writing["error"], QUOTA_USER_MESSAGE)
        self.assertEqual(writing["error_code"], QUOTA_ERROR_CODE)

    def test_all_agents_blocked_by_quota_is_a_quota_error_not_agent_failure(self):
        def blocked():
            raise _quota()

        client = _client(_Model(), [_Adapter("position", blocked), _Adapter("writing", blocked)])
        response = client.post("/internal/runs", json=REQUEST)

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], QUOTA_ERROR_CODE)
        self.assertEqual(detail["message"], QUOTA_USER_MESSAGE)

    def test_mixed_failures_stay_all_agents_failed(self):
        def blocked():
            raise _quota()

        def broken():
            raise ValueError("bad output")

        client = _client(_Model(), [_Adapter("position", blocked), _Adapter("writing", broken)])
        detail = client.post("/internal/runs", json=REQUEST).json()["detail"]
        self.assertEqual(detail["code"], "ALL_AGENTS_FAILED")

    def test_planner_blocked_by_quota_is_reported_as_quota(self):
        client = _client(_Model(plan_error=_quota()), [
            _Adapter("position", lambda: {}),
            _Adapter("writing", lambda: {}),
        ])
        response = client.post("/internal/runs", json=REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], {"code": QUOTA_ERROR_CODE, "message": QUOTA_USER_MESSAGE})


class NewsQuotaResponseTest(unittest.TestCase):
    def test_news_direct_path_reports_quota(self):
        from ai.news_intelligence import api as news_api

        class _Service:
            def analyze(self, request):
                raise _quota()

        news_api.app.dependency_overrides[news_api.get_news_service] = lambda: _Service()
        try:
            response = TestClient(news_api.app).post("/internal/analyses", json={
                "instruction": "최근 소식",
                "job_context_id": "ctx-1",
                "corp_code": "00126380",
            })
        finally:
            news_api.app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], {"code": QUOTA_ERROR_CODE, "message": QUOTA_USER_MESSAGE})
