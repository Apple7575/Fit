import unittest

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import SupervisorPlan, SupervisorRunRequest, TraceStep
from ai.supervisor.graph import build_supervisor_graph
from ai.supervisor.service import SupervisorService, finalize_trace
from ai.tests.supervisor.test_delegation import (
    NEWS_RESULT,
    WRITING_MISSING_EVIDENCE,
    WRITING_OK,
    ScriptedAdapter,
)
from ai.tests.supervisor.test_graph import FakeModel


def make_service(model, adapters):
    return SupervisorService(build_supervisor_graph(model, AgentRegistry(adapters)))


def request(agent_contexts, lead=None, documents=None):
    return SupervisorRunRequest.model_validate({
        "instruction": "지원동기에 최근 회사 변화를 반영해줘",
        "documents": documents if documents is not None else [
            {"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}
        ],
        "agent_contexts": agent_contexts,
        "lead": lead,
    })


class FinalizeTraceTest(unittest.TestCase):
    def step(self, phase, agent, called_by="plan"):
        return TraceStep(step=1, phase=phase, agent=agent, called_by=called_by, status="SUCCESS", duration_ms=0)

    def test_numbers_steps_and_marks_superseded_first_runs(self):
        steps = [
            self.step("plan", "supervisor", "request"),
            self.step("writing", "writing"),
            self.step("delegation", "news", "writing"),
            self.step("rerun", "writing", "delegation"),
            self.step("aggregate", "supervisor", "request"),
        ]
        finalized = finalize_trace(steps)

        self.assertEqual([s.step for s in finalized], [1, 2, 3, 4, 5])
        self.assertEqual([s.superseded for s in finalized], [False, True, False, False, False])

    def test_accepts_dict_input(self):
        finalized = finalize_trace([self.step("plan", "supervisor", "request").model_dump()])
        self.assertEqual(finalized[0].phase, "plan")


class TraceThroughServiceTest(unittest.TestCase):
    def test_delegation_run_produces_full_trace(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, WRITING_OK])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        model = FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")])
        service = make_service(model, [writing, news])

        response = service.run(request({
            "writing": {"question": "지원동기", "char_limit": 1000},
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
        }))

        trace = response.trace
        self.assertEqual(
            [(s.phase, s.agent, s.called_by) for s in trace],
            [
                ("plan", "supervisor", "request"),
                ("writing", "writing", "plan"),
                ("delegation", "news", "writing"),
                ("rerun", "writing", "delegation"),
                ("aggregate", "supervisor", "request"),
            ],
        )
        self.assertEqual([s.step for s in trace], [1, 2, 3, 4, 5])
        self.assertTrue(trace[1].superseded)
        self.assertFalse(trace[3].superseded)
        self.assertEqual(trace[2].evidence_ids, ["news:stored:1"])
        self.assertEqual(trace[3].note, "after=news")
        self.assertIn("selected=writing", trace[0].note)
        self.assertEqual(trace[4].note, "model")
        # 응답 본문의 agent_results 는 여전히 담당별 마지막 실행만 담는다.
        self.assertEqual([r.agent for r in response.agent_results], ["writing", "news"])

    def test_failed_worker_and_passthrough_aggregate_are_traced(self):
        writing = ScriptedAdapter("writing", [WRITING_OK])
        jd = ScriptedAdapter("jd", [RuntimeError("jd down")])
        model = FakeModel([SupervisorPlan(selected_agents=["jd", "writing"], reason="검토")])
        service = make_service(model, [writing, jd])

        response = service.run(request({
            "jd": {"job_context_id": "jctx"},
            "writing": {"question": "q", "char_limit": 100},
        }))

        by_agent = {(s.phase, s.agent): s for s in response.trace}
        self.assertEqual(by_agent[("analysis", "jd")].status, "FAILED")
        self.assertIn("jd down", by_agent[("analysis", "jd")].note)
        self.assertEqual(by_agent[("aggregate", "supervisor")].note, "passthrough")
        self.assertEqual(response.status, "PARTIAL")

    def test_lead_mode_marks_plan_as_lead(self):
        news = ScriptedAdapter("news", [NEWS_RESULT])
        service = make_service(FakeModel([]), [news])

        response = service.run(request(
            {"news": {"job_context_id": "jctx", "corp_code": "00126380"}}, lead="news", documents=[]
        ))

        self.assertEqual(response.trace[0].called_by, "lead")
        self.assertEqual([s.phase for s in response.trace], ["plan", "analysis", "aggregate"])
        self.assertEqual(response.trace[2].note, "passthrough")


if __name__ == "__main__":
    unittest.main()
