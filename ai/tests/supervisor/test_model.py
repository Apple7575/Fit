import unittest

from ai.supervisor.contracts import AgentResult
from ai.supervisor.model import QwenSupervisorModel


class FakeQwen:
    def __init__(self):
        self.calls = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append({"config": config, "messages": messages, **kwargs})
        if kwargs["schema_name"] == "supervisor_plan_v1":
            return {"output": {"selected_agents": ["jd"], "reason": "JD 검토 요청"}}
        return {"output": {"message": "JD 기준으로 보완이 필요합니다."}}


class QwenSupervisorModelTest(unittest.TestCase):
    def test_uses_structured_schemas_for_plan_and_aggregate(self):
        qwen = FakeQwen()
        model = QwenSupervisorModel(
            config={"base_url": "http://qwen", "model": "qwen", "api_key": "x"},
            qwen_caller=qwen,
        )

        plan = model.create_plan(
            instruction="공고 적합성을 검토해줘",
            documents=[{"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "내용"}],
            conversation=[],
            available_agents=["jd"],
            validation_error=None,
        )
        message = model.aggregate(
            instruction="공고 적합성을 검토해줘",
            plan=plan,
            results=[AgentResult(agent="jd", status="SUCCESS", result={"summary": {}})],
        )

        self.assertEqual(plan.selected_agents, ["jd"])
        self.assertEqual(message, "JD 기준으로 보완이 필요합니다.")
        self.assertEqual(qwen.calls[0]["schema_name"], "supervisor_plan_v1")
        self.assertEqual(qwen.calls[1]["schema_name"], "supervisor_aggregate_v1")

