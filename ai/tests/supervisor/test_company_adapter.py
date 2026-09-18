import unittest

from ai.supervisor.adapters import AgentRegistry, CompanyAgentAdapter
from ai.supervisor.contracts import AgentContexts, AgentResult, SupervisorRunRequest
from ai.supervisor.delegation import ANALYSIS_AGENT_NAMES, DOCUMENT_FREE_AGENTS, extract_needs, select_delegations
from ai.supervisor.evidence import extract_evidence
from ai.supervisor.model import PLAN_SCHEMA
from ai.supervisor.tools import DEFAULT_TOOL_POLICY


class FakeCompanyChatService:
    def __init__(self):
        self.calls = []

    def answer(self, *, corp_code, message, history=None):
        self.calls.append((corp_code, message, history))
        return {
            "corp_code": corp_code,
            "corp_name": "SK하이닉스",
            "message": "2025년 매출은 97.1조원입니다.",
            "citations": [
                {"source_type": "COMPANY_METRIC", "source_id": "00164779:report:financials:0"},
                {"source_type": "DART_BUSINESS_REPORT", "source_id": "dart-business-report-abc", "rcept_no": "20260317000635", "excerpt": "매출액 97조 1,468억원"},
            ],
            "needs": [{"agent": "news", "reason": "최근 뉴스는 공시에 없습니다."}],
            "follow_up_questions": ["영업이익은?"],
            "report_stage": "FULL",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


class CompanyAdapterTest(unittest.TestCase):
    def test_available_only_with_corp_code(self):
        adapter = CompanyAgentAdapter(FakeCompanyChatService())
        self.assertTrue(adapter.is_available({"corp_code": "00164779"}))
        self.assertFalse(adapter.is_available({"job_context_id": "j"}))
        self.assertFalse(adapter.is_available(None))

    def test_execute_passes_instruction_and_conversation_as_history(self):
        service = FakeCompanyChatService()
        registry = AgentRegistry([CompanyAgentAdapter(service)])
        result = registry.execute(
            "company",
            "매출이 얼마야?",
            [],
            [{"message_id": "m1", "role": "USER", "content": "안녕"}],
            {"corp_code": "00164779"},
        )
        self.assertEqual(service.calls[0][0], "00164779")
        self.assertEqual(service.calls[0][1], "매출이 얼마야?")
        self.assertEqual(service.calls[0][2], [{"role": "USER", "content": "안녕"}])
        self.assertEqual(result["message"], "2025년 매출은 97.1조원입니다.")
        self.assertEqual(registry.available_names({"company": {"corp_code": "00164779"}}), ["company"])

    def test_evidence_and_needs_are_converted_to_supervisor_shapes(self):
        result = FakeCompanyChatService().answer(corp_code="00164779", message="?")
        evidence = extract_evidence("company", result)
        self.assertEqual([e.source_type for e in evidence], ["COMPANY_REPORT", "COMPANY_REPORT"])
        self.assertEqual(evidence[0].evidence_id, "company:company_metric:00164779:report:financials:0")
        self.assertEqual(evidence[1].url, "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260317000635")
        self.assertEqual(evidence[1].excerpt, "매출액 97조 1,468억원")
        self.assertTrue(all(e.agent == "company" for e in evidence))
        needs = extract_needs("company", result)
        self.assertEqual([(n.agent, n.reason) for n in needs], [("news", "최근 뉴스는 공시에 없습니다.")])

    def test_company_can_request_news_delegation(self):
        result = AgentResult(agent="company", status="SUCCESS", result={}, needs=extract_needs("company", FakeCompanyChatService().answer(corp_code="00164779", message="?")))
        delegations = select_delegations([result], available_agents=["company", "news"], already_run={"company"}, round_index=0)
        self.assertEqual(delegations, [{"agent": "news", "requested_by": "company", "reason": "최근 뉴스는 공시에 없습니다."}])
        # 뉴스 컨텍스트가 없으면 위임하지 않는다
        self.assertEqual(select_delegations([result], available_agents=["company"], already_run={"company"}, round_index=0), [])

    def test_company_is_registered_everywhere(self):
        self.assertIn("company", ANALYSIS_AGENT_NAMES)
        self.assertIn("company", DOCUMENT_FREE_AGENTS, "제출 문서 없이도 기업 질문에 답할 수 있어야 한다")
        self.assertIn("company", PLAN_SCHEMA["properties"]["selected_agents"]["items"]["enum"])
        self.assertEqual(DEFAULT_TOOL_POLICY["company"], frozenset())
        request = SupervisorRunRequest(
            instruction="SK하이닉스 재무 어때?",
            agent_contexts=AgentContexts(company={"corp_code": "00164779"}),
            lead="company",
        )
        self.assertEqual(request.agent_contexts.company.corp_code, "00164779")
        self.assertIsNone(request.agent_contexts.company.job_context_id)


if __name__ == "__main__":
    unittest.main()
