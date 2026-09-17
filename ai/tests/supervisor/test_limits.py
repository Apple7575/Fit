"""실패·한계 케이스: 도구 거부, 병렬 격리, 시간 예산, 재실행 실패, 근거 0건, 총괄 자체 실패."""

import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.serve import build_app
from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter, WritingAgentAdapter
from ai.supervisor.api import get_supervisor_service
from ai.supervisor.contracts import SupervisorPlan, SupervisorRunRequest
from ai.supervisor.graph import build_supervisor_graph, delegation_deadline_from_env
from ai.supervisor.service import SupervisorService
from ai.supervisor.tools import ToolBox, instrument_jd_service
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
from ai.tests.supervisor.test_tools import FakeJobContextStore, InstrumentedJdService

DOCS = [{"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}]
WRITING_CTX = {"question": "지원동기", "char_limit": 1000}
NEWS_CTX = {"job_context_id": "jctx", "corp_code": "00126380"}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def invoke(graph, agent_contexts, lead=None, documents=None):
    return graph.invoke({
        "instruction": "회사 변화를 반영해줘",
        "documents": DOCS if documents is None else documents,
        "conversation": [],
        "agent_contexts": agent_contexts,
        "lead": lead,
        "agent_results": [],
        "trace": [],
    })


class ToolDenialTest(unittest.TestCase):
    def test_worker_calling_disallowed_tool_fails_and_records_denial(self):
        # 글쓰기 담당에 (허용되지 않은) 공고 저장소를 몰래 쥐여 준다.
        store = FakeJobContextStore({"jctx": {"context_id": "jctx"}})
        toolbox = ToolBox(job_context_store=store)

        class SneakyWritingService:
            def respond(self, request):
                toolbox.job_context_store("writing").get("jctx")
                raise AssertionError("must not reach")

        registry = AgentRegistry([WritingAgentAdapter(lambda: SneakyWritingService())])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]), registry
        )

        output = invoke(graph, {"writing": WRITING_CTX})

        result = output["agent_results"][0]
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].status, "DENIED")
        self.assertEqual(result.tool_calls[0].tool, "get_job_context")
        self.assertEqual(store.calls, [])  # 저장소는 건드리지 않았다


class ParallelIsolationTest(unittest.TestCase):
    def test_parallel_workers_record_only_their_own_tool_calls(self):
        barrier = threading.Barrier(2)

        class BarrierJdService(InstrumentedJdService):
            def analyze_documents(self, context_id, documents):
                barrier.wait(timeout=2)
                return super().analyze_documents(context_id, documents)

        jd_store = FakeJobContextStore({"jctx": {"context_id": "jctx"}})
        jd_service = instrument_jd_service(BarrierJdService(jd_store))

        news_store = FakeJobContextStore({"jctx2": {"context_id": "jctx2"}})
        news_toolbox = ToolBox(job_context_store=news_store)

        class BarrierNewsAdapter:
            name = "news"

            def is_available(self, context):
                return context is not None

            def execute(self, instruction, documents, conversation, context, prior_results=()):
                barrier.wait(timeout=2)
                news_toolbox.job_context_store("news").get("jctx2")
                news_toolbox.job_context_store("news").get("jctx2")
                return NEWS_RESULT

        registry = AgentRegistry([JdAgentAdapter(lambda: jd_service), BarrierNewsAdapter()])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["jd", "news"], reason="둘")]), registry
        )

        output = invoke(graph, {"jd": {"job_context_id": "jctx"}, "news": NEWS_CTX})

        by_agent = {r.agent: r for r in output["agent_results"]}
        self.assertEqual([c.arguments["context_id"] for c in by_agent["jd"].tool_calls], ["jctx"])
        self.assertEqual([c.arguments["context_id"] for c in by_agent["news"].tool_calls], ["jctx2", "jctx2"])
        self.assertTrue(all(c.agent == "jd" for c in by_agent["jd"].tool_calls))
        self.assertTrue(all(c.agent == "news" for c in by_agent["news"].tool_calls))


class DelegationBudgetTest(unittest.TestCase):
    def test_delegation_is_skipped_after_deadline_and_recorded_in_trace(self):
        clock = FakeClock()

        class SlowWriting(ScriptedAdapter):
            def execute(self, *args, **kwargs):
                clock.now += 61.0  # 글쓰기 1차가 오래 걸렸다
                return super().execute(*args, **kwargs)

        writing = SlowWriting("writing", [WRITING_MISSING_EVIDENCE])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]),
            AgentRegistry([writing, news]),
            clock=clock,
            delegation_deadline_seconds=60,
        )

        output = invoke(graph, {"writing": WRITING_CTX, "news": NEWS_CTX})

        self.assertEqual([r.agent for r in output["agent_results"]], ["writing"])
        self.assertEqual(news.calls, [])
        skipped = [s for s in output["trace"] if s.status == "SKIPPED" and s.phase == "delegation"]
        self.assertEqual(len(skipped), 1)
        self.assertIn("skipped news", skipped[0].note)
        self.assertEqual(output["final_message"], WRITING_MISSING_EVIDENCE["message"])

    def test_delegation_runs_when_within_deadline(self):
        clock = FakeClock()
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, WRITING_OK])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]),
            AgentRegistry([writing, news]),
            clock=clock,
            delegation_deadline_seconds=60,
        )

        output = invoke(graph, {"writing": WRITING_CTX, "news": NEWS_CTX})

        self.assertEqual([r.agent for r in output["agent_results"]], ["writing", "news", "writing"])

    def test_deadline_env_parsing_falls_back_on_garbage(self):
        with patch.dict("os.environ", {"SUPERVISOR_DELEGATION_DEADLINE_SECONDS": "abc"}):
            self.assertEqual(delegation_deadline_from_env(), 60.0)
        with patch.dict("os.environ", {"SUPERVISOR_DELEGATION_DEADLINE_SECONDS": "-5"}):
            self.assertEqual(delegation_deadline_from_env(), 60.0)
        with patch.dict("os.environ", {"SUPERVISOR_DELEGATION_DEADLINE_SECONDS": "45"}):
            self.assertEqual(delegation_deadline_from_env(), 45.0)


class RerunFailureTest(unittest.TestCase):
    def test_failed_rerun_keeps_first_successful_result(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, RuntimeError("writing down")])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        service = SupervisorService(build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]),
            AgentRegistry([writing, news]),
        ))

        response = service.run(SupervisorRunRequest.model_validate({
            "instruction": "회사 변화 반영",
            "documents": DOCS,
            "agent_contexts": {"writing": WRITING_CTX, "news": NEWS_CTX},
        }))

        self.assertEqual(response.status, "SUCCESS")
        by_agent = {r.agent: r for r in response.agent_results}
        self.assertEqual(by_agent["writing"].status, "SUCCESS")
        self.assertEqual(by_agent["writing"].result["message"], WRITING_MISSING_EVIDENCE["message"])
        rerun_steps = [s for s in response.trace if s.phase == "rerun"]
        self.assertEqual(rerun_steps[0].status, "FAILED")
        self.assertIn("kept previous result", rerun_steps[0].note)
        writing_steps = [s for s in response.trace if s.agent == "writing"]
        self.assertFalse(writing_steps[0].superseded)  # 1차가 최종 결과이므로 대체되지 않았다


class InsufficientEvidenceTest(unittest.TestCase):
    def test_insufficient_news_reruns_writing_with_empty_feedback(self):
        insufficient = {"message": "근거 부족", "analysis": {"analysis_status": "INSUFFICIENT_EVIDENCE", "signals": []}}

        class FirstMissingThenOk:
            def __init__(self):
                self.requests = []

            def respond(self, request):
                self.requests.append(request)
                from ai.writing_coaching.contracts import WritingMessageResponse
                payload = WRITING_MISSING_EVIDENCE if len(self.requests) == 1 else WRITING_OK
                return WritingMessageResponse.model_validate(payload)

        writing_service = FirstMissingThenOk()
        news = ScriptedAdapter("news", [insufficient])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]),
            AgentRegistry([WritingAgentAdapter(lambda: writing_service), news]),
        )

        output = invoke(graph, {"writing": WRITING_CTX, "news": NEWS_CTX})

        self.assertEqual([r.agent for r in output["agent_results"]], ["writing", "news", "writing"])
        self.assertEqual(output["agent_results"][1].evidence, [])
        self.assertEqual(writing_service.requests[1].feedback, [])  # 근거 0건은 피드백도 0건
        self.assertEqual(output["final_message"], "종합 결과")  # 성공 담당 2개 → 모델 종합


class SupervisorFailureApiTest(unittest.TestCase):
    def setUp(self):
        get_supervisor_service.cache_clear()

    def test_planner_transport_error_maps_to_502_without_leaking_details(self):
        class BrokenModel:
            def create_plan(self, **kwargs):
                raise RuntimeError("Qwen API HTTP 500: secret internal detail")

            def aggregate(self, **kwargs):
                raise AssertionError("unreachable")

        with (
            patch("ai.supervisor.api.load_qwen_config", return_value={}),
            patch("ai.supervisor.api.QwenSupervisorModel", return_value=BrokenModel()),
            patch("ai.supervisor.api.get_analysis_service", return_value=FakeJdService()),
            patch("ai.supervisor.api.get_position_service", return_value=FakePositionService()),
            patch("ai.supervisor.api.get_news_service", return_value=FakeNewsService()),
        ):
            response = TestClient(build_app()).post("/supervisor/internal/runs", json={
                "instruction": "검토",
                "documents": DOCS,
                "agent_contexts": {"jd": {"job_context_id": "jctx"}},
            })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], {"code": "SUPERVISOR_FAILED", "message": "RuntimeError"})

    def test_configuration_error_still_returns_503(self):
        with patch("ai.supervisor.api.load_qwen_config", side_effect=ValueError("missing")):
            response = TestClient(build_app()).post("/supervisor/internal/runs", json={
                "instruction": "검토",
                "documents": DOCS,
                "agent_contexts": {"jd": {"job_context_id": "jctx"}},
            })
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
