import unittest
from datetime import date, datetime, timezone

from ai.supervisor.tools import (
    DEFAULT_TOOL_POLICY,
    ToolBox,
    ToolPolicyError,
    current_tool_calls,
    tool_scope,
)


class FakeJobContextStore:
    def __init__(self, contexts=None, error=None):
        self.contexts = contexts or {}
        self.error = error
        self.calls = []

    def get(self, context_id):
        self.calls.append(context_id)
        if self.error is not None:
            raise self.error
        return self.contexts.get(context_id)

    def save(self, context):
        return context


class FakeNewsRepository:
    def load_context(self, job_context_id, corp_code):
        return {"job_context_id": job_context_id, "corp_code": corp_code}

    def list_recent(self, corp_code, since, limit):
        return [{"id": i} for i in range(min(limit, 3))]


class FakeSearchProvider:
    def search(self, corp_name, position_name, missing_scopes, from_date, to_date, limit,
               *, industry_name=None):
        return [{"title": f"{corp_name} {scope}"} for scope in missing_scopes]


class FakeConversationStore:
    def list_messages(self, conversation_id, *, limit=100):
        return [{"id": "m1"}, {"id": "m2"}]


class FakeClock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        self.now += 0.005
        return self.now


def build_toolbox(**overrides):
    kwargs = dict(
        job_context_store=FakeJobContextStore({"jctx": {"context_id": "jctx"}}),
        news_repository=FakeNewsRepository(),
        news_search_provider=FakeSearchProvider(),
        conversation_store=FakeConversationStore(),
        clock=FakeClock(),
    )
    kwargs.update(overrides)
    return ToolBox(**kwargs)


class ToolPolicyTest(unittest.TestCase):
    def test_default_policy_matches_agent_responsibilities(self):
        self.assertEqual(DEFAULT_TOOL_POLICY["jd"], {"get_job_context"})
        self.assertEqual(
            DEFAULT_TOOL_POLICY["news"],
            {"get_job_context", "list_news", "search_news_external"},
        )
        self.assertEqual(DEFAULT_TOOL_POLICY["position"], set())
        self.assertEqual(DEFAULT_TOOL_POLICY["writing"], set())
        self.assertEqual(DEFAULT_TOOL_POLICY["supervisor"], {"get_conversation"})

    def test_denied_call_is_recorded_and_raises_before_touching_store(self):
        store = FakeJobContextStore({"jctx": {}})
        toolbox = build_toolbox(job_context_store=store)

        with tool_scope("writing") as calls:
            with self.assertRaises(ToolPolicyError):
                toolbox.job_context_store("writing").get("jctx")

        self.assertEqual(store.calls, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].status, "DENIED")
        self.assertEqual(calls[0].tool, "get_job_context")
        self.assertEqual(calls[0].agent, "writing")

    def test_unknown_agent_has_no_tools(self):
        toolbox = build_toolbox()
        self.assertEqual(toolbox.allowed_tools("company"), frozenset())
        self.assertFalse(toolbox.is_allowed("company", "list_news"))

    def test_custom_policy_overrides_default(self):
        toolbox = build_toolbox(policy={"writing": {"get_job_context"}})
        with tool_scope("writing"):
            self.assertEqual(
                toolbox.job_context_store("writing").get("jctx"), {"context_id": "jctx"}
            )


class ToolRecordingTest(unittest.TestCase):
    def test_successful_calls_record_arguments_duration_and_count(self):
        toolbox = build_toolbox()
        since = datetime(2026, 6, 18, tzinfo=timezone.utc)

        with tool_scope("news") as calls:
            repository = toolbox.news_repository("news")
            repository.load_context("jctx", "00126380")
            repository.list_recent("00126380", since, 20)
            toolbox.news_search_provider("news").search(
                "삼성전자", "백엔드", ["INDUSTRY", "ROLE"], date(2026, 6, 18), date(2026, 9, 16), 10
            )

        self.assertEqual([c.tool for c in calls], ["get_job_context", "list_news", "search_news_external"])
        self.assertTrue(all(c.status == "SUCCESS" for c in calls))
        self.assertTrue(all(c.agent == "news" for c in calls))
        self.assertEqual(calls[1].arguments, {"corp_code": "00126380", "since": since.isoformat(), "limit": 20})
        self.assertEqual(calls[1].result_count, 3)
        self.assertEqual(calls[2].arguments["missing_scopes"], ["INDUSTRY", "ROLE"])
        self.assertEqual(calls[2].result_count, 2)
        self.assertTrue(all(c.duration_ms >= 5 for c in calls))

    def test_failed_call_records_error_and_reraises(self):
        toolbox = build_toolbox(job_context_store=FakeJobContextStore(error=TimeoutError("db down")))

        with tool_scope("jd") as calls:
            with self.assertRaises(TimeoutError):
                toolbox.job_context_store("jd").get("jctx")

        self.assertEqual(calls[0].status, "FAILED")
        self.assertEqual(calls[0].error, "TimeoutError: db down")

    def test_missing_result_counts_as_zero(self):
        toolbox = build_toolbox()
        with tool_scope("jd") as calls:
            self.assertIsNone(toolbox.job_context_store("jd").get("nope"))
        self.assertEqual(calls[0].result_count, 0)

    def test_calls_outside_scope_still_execute_but_are_not_recorded(self):
        toolbox = build_toolbox()
        self.assertEqual(toolbox.job_context_store("jd").get("jctx"), {"context_id": "jctx"})
        self.assertEqual(current_tool_calls(), [])

    def test_scopes_do_not_leak_between_agents(self):
        toolbox = build_toolbox()
        with tool_scope("jd") as jd_calls:
            toolbox.job_context_store("jd").get("jctx")
            with tool_scope("supervisor") as supervisor_calls:
                toolbox.conversation_store("supervisor").list_messages("conv-1", limit=5)
            toolbox.job_context_store("jd").get("jctx")

        self.assertEqual([c.tool for c in jd_calls], ["get_job_context", "get_job_context"])
        self.assertEqual([c.tool for c in supervisor_calls], ["get_conversation"])
        self.assertEqual(supervisor_calls[0].result_count, 2)

    def test_non_tool_methods_pass_through_to_target(self):
        toolbox = build_toolbox()
        proxy = toolbox.job_context_store("jd")
        self.assertEqual(proxy.save("ctx"), "ctx")

    def test_unconfigured_store_fails_fast(self):
        toolbox = ToolBox()
        with self.assertRaises(RuntimeError):
            toolbox.news_repository("news")


class InstrumentedJdService:
    """실제 JdAnalysisService처럼 _context_store 를 들고 .get() 으로 공고를 읽는다."""

    def __init__(self, store):
        self._context_store = store

    def analyze_documents(self, context_id, documents):
        context = self._context_store.get(context_id)
        if context is None:
            raise LookupError(context_id)
        return {"context_id": context["context_id"], "requirements": []}


class SupervisorIntegrationTest(unittest.TestCase):
    def test_graph_records_tool_calls_made_by_instrumented_service(self):
        from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter
        from ai.supervisor.contracts import SupervisorPlan
        from ai.supervisor.graph import build_supervisor_graph
        from ai.supervisor.tools import instrument_jd_service
        from ai.tests.supervisor.test_graph import FakeModel

        store = FakeJobContextStore({"jctx": {"context_id": "jctx"}})
        service = instrument_jd_service(InstrumentedJdService(store))
        self.assertIs(instrument_jd_service(service), service)  # 두 번 감싸지 않는다
        registry = AgentRegistry([JdAgentAdapter(lambda: service)])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["jd"], reason="JD 검토")]), registry
        )

        output = graph.invoke({
            "instruction": "검토해줘",
            "documents": [{"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}],
            "conversation": [],
            "agent_contexts": {"jd": {"job_context_id": "jctx"}},
            "agent_results": [],
        })

        result = output["agent_results"][0]
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual([c.tool for c in result.tool_calls], ["get_job_context"])
        self.assertEqual(result.tool_calls[0].agent, "jd")
        self.assertEqual(result.tool_calls[0].arguments, {"context_id": "jctx"})
        self.assertEqual(result.tool_calls[0].status, "SUCCESS")
        self.assertEqual(store.calls, ["jctx"])
        self.assertEqual(current_tool_calls(), [])  # 노드 밖으로 새지 않는다

    def test_failed_worker_still_reports_its_tool_calls(self):
        from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter
        from ai.supervisor.contracts import SupervisorPlan
        from ai.supervisor.graph import build_supervisor_graph
        from ai.supervisor.tools import instrument_jd_service
        from ai.tests.supervisor.test_graph import FakeModel

        service = instrument_jd_service(InstrumentedJdService(FakeJobContextStore()))
        registry = AgentRegistry([JdAgentAdapter(lambda: service)])
        graph = build_supervisor_graph(
            FakeModel([SupervisorPlan(selected_agents=["jd"], reason="JD 검토")]), registry
        )

        output = graph.invoke({
            "instruction": "검토해줘",
            "documents": [{"document_id": "d1", "document_type": "SELF_INTRO", "text": "본문"}],
            "conversation": [],
            "agent_contexts": {"jd": {"job_context_id": "missing"}},
            "agent_results": [],
        })

        result = output["agent_results"][0]
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].result_count, 0)


if __name__ == "__main__":
    unittest.main()
