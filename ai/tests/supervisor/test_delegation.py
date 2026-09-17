import unittest

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import AgentResult, NoAvailableAgentError, SupervisorPlan
from ai.supervisor.delegation import (
    extract_needs,
    latest_results,
    order_results,
    select_delegations,
    superseded_results,
)
from ai.supervisor.feedback import normalize_writing_feedback
from ai.supervisor.graph import build_supervisor_graph
from ai.tests.supervisor.test_graph import FakeModel


NEWS_RESULT = {
    "message": "AI 인프라 투자 확대",
    "analysis": {
        "analysis_status": "COMPLETED",
        "signals": [
            {
                "signal_id": "signal-001",
                "scope": "COMPANY",
                "title": "AI 인프라 투자 확대",
                "summary": "데이터센터 증설 계획 발표.",
                "jd_relevance": "대규모 인프라 운영 요구와 연결.",
                "sources": [{"article_id": "stored:1", "title": "삼성전자, AI 인프라 투자", "url": "https://x.test/1"}],
            }
        ],
    },
}

WRITING_MISSING_EVIDENCE = {
    "status": "REVISED",
    "message": "회사 변화 근거가 없어 일반적인 문장으로 수정했습니다.",
    "revision": {
        "revision_strength": "LIGHT",
        "revised_text": "수정문",
        "char_count": 3,
        "changes": [],
        "warnings": [{"code": "MISSING_EVIDENCE", "message": "최근 회사 변화에 대한 근거가 없습니다."}],
    },
}

WRITING_OK = {
    "status": "REVISED",
    "message": "뉴스 근거를 반영해 수정했습니다.",
    "revision": {"revision_strength": "BALANCED", "revised_text": "수정문2", "char_count": 4, "changes": [], "warnings": []},
}


class ScriptedAdapter:
    """호출 순서대로 미리 정한 결과를 돌려준다. prior_results 를 기록한다."""

    def __init__(self, name, results, requires_context=True):
        self.name = name
        self.results = list(results)
        self.calls = []
        self.requires_context = requires_context

    def is_available(self, context):
        return context is not None

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        self.calls.append({"documents": list(documents), "prior": [r.agent for r in prior_results]})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def run_graph(model, adapters, agent_contexts, documents=None):
    graph = build_supervisor_graph(model, AgentRegistry(adapters))
    return graph.invoke({
        "instruction": "지원동기에 최근 회사 변화를 반영해줘",
        "documents": documents if documents is not None else [
            {"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}
        ],
        "conversation": [],
        "agent_contexts": agent_contexts,
        "agent_results": [],
    })


class ExtractNeedsTest(unittest.TestCase):
    def test_explicit_needs_are_read_and_invalid_entries_dropped(self):
        needs = extract_needs("jd", {"needs": [
            {"agent": "news", "reason": "회사 변화 확인"},
            {"agent": "unknown", "reason": "x"},
            "garbage",
            {"agent": "position"},
        ]})
        self.assertEqual([(n.agent, n.reason) for n in needs], [("news", "회사 변화 확인")])

    def test_writing_missing_evidence_warning_requests_news(self):
        needs = extract_needs("writing", WRITING_MISSING_EVIDENCE)
        self.assertEqual(len(needs), 1)
        self.assertEqual(needs[0].agent, "news")
        self.assertIn("근거", needs[0].reason)

    def test_writing_without_warning_has_no_needs(self):
        self.assertEqual(extract_needs("writing", WRITING_OK), [])
        self.assertEqual(extract_needs("writing", {"status": "CLARIFICATION_REQUIRED", "message": "?", "revision": None}), [])
        self.assertEqual(extract_needs("news", None), [])


class SelectDelegationsTest(unittest.TestCase):
    def make(self, agent, needs=(), status="SUCCESS", delegated_from=None):
        return AgentResult(agent=agent, status=status, result={}, needs=list(needs), delegated_from=delegated_from)

    def test_filters_unavailable_executed_self_and_non_analysis_targets(self):
        results = [
            self.make("writing", [{"agent": "news", "reason": "a"}, {"agent": "jd", "reason": "b"}, {"agent": "writing", "reason": "c"}]),
            self.make("jd", [{"agent": "position", "reason": "d"}]),
        ]
        chosen = select_delegations(
            results, available_agents=["jd", "writing", "news"], already_run=["jd", "writing"], round_index=0,
        )
        self.assertEqual(chosen, [{"agent": "news", "requested_by": "writing", "reason": "a"}])

    def test_second_round_and_delegated_results_never_delegate(self):
        results = [self.make("writing", [{"agent": "news", "reason": "a"}])]
        self.assertEqual(select_delegations(results, available_agents=["news"], already_run=["writing"], round_index=1), [])
        delegated = [self.make("news", [{"agent": "jd", "reason": "x"}], delegated_from="writing")]
        self.assertEqual(select_delegations(delegated, available_agents=["jd"], already_run=["news"], round_index=0), [])

    def test_failed_results_and_duplicate_targets_are_ignored_and_capped(self):
        results = [
            self.make("writing", [{"agent": "news", "reason": "a"}], status="FAILED"),
            self.make("jd", [{"agent": "news", "reason": "b"}, {"agent": "position", "reason": "c"}]),
            self.make("position", [{"agent": "news", "reason": "dup"}]),
        ]
        chosen = select_delegations(results, available_agents=["news", "position", "jd"], already_run=["jd", "position", "writing"], round_index=0)
        self.assertEqual(chosen, [{"agent": "news", "requested_by": "jd", "reason": "b"}])


class ResultBookkeepingTest(unittest.TestCase):
    def test_latest_superseded_and_ordering(self):
        first = AgentResult(agent="writing", status="SUCCESS", result={"v": 1})
        news = AgentResult(agent="news", status="SUCCESS", result={}, delegated_from="writing")
        second = AgentResult(agent="writing", status="SUCCESS", result={"v": 2})
        results = [first, news, second]

        latest = latest_results(results)
        self.assertEqual([(r.agent, r.result) for r in latest], [("writing", {"v": 2}), ("news", {})])
        self.assertEqual(superseded_results(results), [first])
        ordered = order_results(latest, ["writing"])
        self.assertEqual([r.agent for r in ordered], ["writing", "news"])


class DelegationGraphTest(unittest.TestCase):
    def test_writing_requests_news_then_reruns_with_news_feedback(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, WRITING_OK])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        model = FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")])

        output = run_graph(model, [writing, news], {
            "writing": {"question": "지원동기", "char_limit": 1000},
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
        })

        results = output["agent_results"]
        self.assertEqual([r.agent for r in results], ["writing", "news", "writing"])
        self.assertEqual(results[0].needs[0].agent, "news")
        self.assertEqual(results[1].delegated_from, "writing")
        self.assertEqual(results[2].needs, [])
        self.assertEqual(results[2].result["message"], "뉴스 근거를 반영해 수정했습니다.")
        # 두 번째 글쓰기 실행은 뉴스 결과를 피드백으로 받았다.
        self.assertEqual(writing.calls[0]["prior"], [])
        self.assertEqual(writing.calls[1]["prior"], ["news"])
        self.assertEqual(len(news.calls), 1)
        self.assertEqual(output["final_message"], "종합 결과")

    def test_no_delegation_when_target_has_no_context(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE])
        news = ScriptedAdapter("news", [NEWS_RESULT])
        model = FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")])

        output = run_graph(model, [writing, news], {"writing": {"question": "q", "char_limit": 100}})

        self.assertEqual([r.agent for r in output["agent_results"]], ["writing"])
        self.assertEqual(news.calls, [])
        self.assertEqual(output["agent_results"][0].needs[0].agent, "news")  # 요청은 남긴다

    def test_delegated_agent_needs_do_not_trigger_second_round(self):
        jd = ScriptedAdapter("jd", [{"context_id": "jctx", "needs": [{"agent": "news", "reason": "회사 변화"}]}, {"context_id": "jctx", "rerun": True}])
        news = ScriptedAdapter("news", [{**NEWS_RESULT, "needs": [{"agent": "position", "reason": "경험 확인"}]}])
        position = ScriptedAdapter("position", [{"findings": []}])
        model = FakeModel([SupervisorPlan(selected_agents=["jd"], reason="JD")])

        output = run_graph(model, [jd, news, position], {
            "jd": {"job_context_id": "jctx"},
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
            "position": {"rubric_id": "experience-depth-v1", "position_context": {"position_name": "백엔드"}},
        })

        agents = [r.agent for r in output["agent_results"]]
        self.assertEqual(agents, ["jd", "news", "jd"])
        self.assertEqual(position.calls, [])
        self.assertEqual(jd.calls[1]["prior"], ["news"])
        self.assertTrue(output["agent_results"][2].result["rerun"])

    def test_failed_delegated_agent_still_reruns_requester_without_it(self):
        writing = ScriptedAdapter("writing", [WRITING_MISSING_EVIDENCE, WRITING_OK])
        news = ScriptedAdapter("news", [RuntimeError("news down")])
        model = FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")])

        output = run_graph(model, [writing, news], {
            "writing": {"question": "q", "char_limit": 100},
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
        })

        results = output["agent_results"]
        self.assertEqual([(r.agent, r.status) for r in results], [("writing", "SUCCESS"), ("news", "FAILED"), ("writing", "SUCCESS")])
        self.assertEqual(writing.calls[1]["prior"], [])


class DocumentFreeRunTest(unittest.TestCase):
    def test_news_only_run_works_without_documents(self):
        news = ScriptedAdapter("news", [NEWS_RESULT])
        jd = ScriptedAdapter("jd", [{"context_id": "jctx"}])
        model = FakeModel([SupervisorPlan(selected_agents=["news"], reason="뉴스")])

        output = run_graph(model, [news, jd], {
            "news": {"job_context_id": "jctx", "corp_code": "00126380"},
            "jd": {"job_context_id": "jctx"},
        }, documents=[])

        self.assertEqual(output["available_agents"], ["news"])
        self.assertEqual([r.agent for r in output["agent_results"]], ["news"])
        self.assertEqual(jd.calls, [])

    def test_document_requiring_agents_without_documents_are_rejected(self):
        jd = ScriptedAdapter("jd", [{"context_id": "jctx"}])
        model = FakeModel([SupervisorPlan(selected_agents=["jd"], reason="JD")])

        with self.assertRaises(NoAvailableAgentError):
            run_graph(model, [jd], {"jd": {"job_context_id": "jctx"}}, documents=[])


class NewsFeedbackTest(unittest.TestCase):
    def test_news_signals_become_writing_feedback_with_sources(self):
        feedback = normalize_writing_feedback([
            AgentResult(agent="news", status="SUCCESS", result=NEWS_RESULT)
        ])
        self.assertEqual(feedback[0]["feedback_id"], "news-signal-001")
        self.assertEqual(feedback[0]["source"], "news")
        self.assertIn("AI 인프라 투자 확대", feedback[0]["content"])
        self.assertIn("출처: 삼성전자, AI 인프라 투자", feedback[0]["content"])

    def test_insufficient_news_yields_no_feedback(self):
        feedback = normalize_writing_feedback([
            AgentResult(agent="news", status="SUCCESS", result={"analysis": {"signals": []}})
        ])
        self.assertEqual(feedback, [])


if __name__ == "__main__":
    unittest.main()
