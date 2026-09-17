import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.serve import build_app
from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.api import get_supervisor_service
from ai.supervisor.contracts import NoAvailableAgentError, SupervisorRunRequest
from ai.supervisor.graph import build_supervisor_graph
from ai.tests.supervisor.test_adapters import (
    FakeJdService,
    FakeNewsService,
    FakePositionService,
)
from ai.tests.supervisor.test_delegation import (
    NEWS_RESULT,
    WRITING_MISSING_EVIDENCE,
    WRITING_OK,
    ScriptedAdapter,
)
from ai.tests.supervisor.test_graph import FakeModel


def run_lead(model, adapters, agent_contexts, lead, documents=None):
    graph = build_supervisor_graph(model, AgentRegistry(adapters))
    return graph.invoke({
        "instruction": "지원동기에 최근 회사 변화를 반영해줘",
        "documents": documents if documents is not None else [
            {"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}
        ],
        "conversation": [],
        "agent_contexts": agent_contexts,
        "lead": lead,
        "agent_results": [],
    })


class LeadModeGraphTest(unittest.TestCase):
    def test_lead_skips_planner_and_uses_lead_message_after_delegation(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, WRITING_OK])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        model = FakeModel([])  # 계획 모델이 호출되면 pop 에서 실패한다

        output = run_lead(model, [writing, news], {
            "writing": {"question": "지원동기", "char_limit": 1000},
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
        }, lead="writing")

        self.assertEqual(output["plan"].selected_agents, ["writing"])
        self.assertEqual([r.agent for r in output["agent_results"]], ["writing", "news", "writing"])
        self.assertEqual(output["agent_results"][1].delegated_from, "writing")
        self.assertEqual(output["final_message"], "뉴스 근거를 반영해 수정했습니다.")
        self.assertEqual(model.aggregate_calls, [])
        self.assertEqual(model.plan_errors, [])

    def test_lead_analysis_agent_with_message_field(self):
        news = ScriptedAdapter("news", [NEWS_RESULT])
        model = FakeModel([])

        output = run_lead(model, [news], {
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
        }, lead="news", documents=[])

        self.assertEqual([r.agent for r in output["agent_results"]], ["news"])
        self.assertEqual(output["final_message"], "AI 인프라 투자 확대")
        self.assertEqual(model.aggregate_calls, [])

    def test_lead_without_message_field_aggregates_only_lead_result(self):
        jd = ScriptedAdapter("jd", [{"context_id": "jctx", "requirements": []}])
        model = FakeModel([])

        output = run_lead(model, [jd], {"jd": {"job_context_id": "jctx"}}, lead="jd")

        self.assertEqual(output["final_message"], "종합 결과")
        self.assertEqual(len(model.aggregate_calls), 1)
        self.assertEqual([r.agent for r in model.aggregate_calls[0]["results"]], ["jd"])

    def test_lead_without_context_is_rejected(self):
        jd = ScriptedAdapter("jd", [{"context_id": "jctx"}])
        with self.assertRaises(NoAvailableAgentError):
            run_lead(FakeModel([]), [jd], {"jd": {"job_context_id": "jctx"}}, lead="news")


class LeadModeContractTest(unittest.TestCase):
    def test_lead_is_optional_and_typed(self):
        base = {
            "instruction": "검토",
            "documents": [{"document_id": "d", "document_type": "SELF_INTRO", "text": "t"}],
            "agent_contexts": {"jd": {"job_context_id": "jctx"}},
        }
        self.assertIsNone(SupervisorRunRequest.model_validate(base).lead)
        self.assertEqual(SupervisorRunRequest.model_validate({**base, "lead": "jd"}).lead, "jd")
        with self.assertRaises(ValueError):
            SupervisorRunRequest.model_validate({**base, "lead": "company"})


class LeadModeApiTest(unittest.TestCase):
    def setUp(self):
        get_supervisor_service.cache_clear()

    def post(self, request, news=None):
        model = FakeModel([])
        with (
            patch("ai.supervisor.api.load_qwen_config", return_value={}),
            patch("ai.supervisor.api.QwenSupervisorModel", return_value=model),
            patch("ai.supervisor.api.get_analysis_service", return_value=FakeJdService()),
            patch("ai.supervisor.api.get_position_service", return_value=FakePositionService()),
            patch("ai.supervisor.api.get_news_service", return_value=news or FakeNewsService()),
        ):
            return TestClient(build_app()).post("/supervisor/internal/runs", json=request)

    def test_lead_news_run_returns_lead_in_response(self):
        response = self.post({
            "instruction": "회사 변화 알려줘",
            "documents": [],
            "agent_contexts": {"news": {"job_context_id": "jctx", "corp_code": "00126380"}},
            "lead": "news",
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["lead"], "news")
        self.assertEqual(body["plan"]["selected_agents"], ["news"])
        self.assertIn("lead 모드", body["plan"]["reason"])

    def test_lead_without_matching_context_is_422(self):
        response = self.post({
            "instruction": "회사 변화 알려줘",
            "documents": [],
            "agent_contexts": {"news": {"job_context_id": "jctx", "corp_code": "00126380"}},
            "lead": "writing",
        })

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "NO_AVAILABLE_AGENT")


if __name__ == "__main__":
    unittest.main()
