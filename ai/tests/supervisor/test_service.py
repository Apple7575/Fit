import unittest

from ai.supervisor.contracts import AllAgentsFailedError, SupervisorRunRequest
from ai.supervisor.service import SupervisorService


REQUEST = SupervisorRunRequest.model_validate(
    {
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
)


class FakeGraph:
    def __init__(self, output):
        self.output = output
        self.states = []

    def invoke(self, state):
        self.states.append(state)
        return self.output


class SupervisorServiceTest(unittest.TestCase):
    def test_maps_all_successful_results_to_success(self):
        graph = FakeGraph(
            {
                "plan": {"selected_agents": ["jd"], "reason": "JD 필요"},
                "agent_results": [
                    {"agent": "jd", "status": "SUCCESS", "result": {"summary": {}}}
                ],
                "final_message": "JD 결과를 반영했습니다.",
            }
        )

        response = SupervisorService(graph).run(REQUEST)

        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(response.message, "JD 결과를 반영했습니다.")
        self.assertEqual(response.plan.selected_agents, ["jd"])
        self.assertEqual(graph.states[0]["agent_results"], [])

    def test_maps_mixed_results_to_partial_in_selected_agent_order(self):
        graph = FakeGraph(
            {
                "plan": {
                    "selected_agents": ["jd", "position"],
                    "reason": "둘 다 필요",
                },
                "agent_results": [
                    {
                        "agent": "position",
                        "status": "FAILED",
                        "error": "RuntimeError: failed",
                    },
                    {
                        "agent": "jd",
                        "status": "SUCCESS",
                        "result": {"summary": {}},
                    },
                ],
                "final_message": "JD 결과만 반영했습니다.",
            }
        )

        response = SupervisorService(graph).run(REQUEST)

        self.assertEqual(response.status, "PARTIAL")
        self.assertEqual(
            [item.agent for item in response.agent_results], ["jd", "position"]
        )

    def test_treats_writing_clarification_as_successful_execution(self):
        clarification = "본인이 수행한 행동을 알려주세요."
        graph = FakeGraph(
            {
                "plan": {
                    "selected_agents": ["writing"],
                    "reason": "추가 정보 필요",
                },
                "agent_results": [
                    {
                        "agent": "writing",
                        "status": "SUCCESS",
                        "result": {
                            "status": "CLARIFICATION_REQUIRED",
                            "message": clarification,
                            "revision": None,
                        },
                    }
                ],
                "final_message": clarification,
            }
        )

        response = SupervisorService(graph).run(REQUEST)

        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(response.message, clarification)
        self.assertEqual(response.agent_results[0].status, "SUCCESS")

    def test_raises_when_all_agents_fail(self):
        graph = FakeGraph(
            {
                "plan": {"selected_agents": ["jd"], "reason": "JD 필요"},
                "agent_results": [
                    {
                        "agent": "jd",
                        "status": "FAILED",
                        "error": "RuntimeError: failed",
                    }
                ],
                "final_message": "",
            }
        )

        with self.assertRaises(AllAgentsFailedError) as raised:
            SupervisorService(graph).run(REQUEST)

        self.assertEqual([item.agent for item in raised.exception.results], ["jd"])


if __name__ == "__main__":
    unittest.main()
