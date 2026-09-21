import unittest
import json
from unittest.mock import patch

from ai.supervisor.contracts import AgentResult
from ai.supervisor.model import PLAN_SCHEMA, PlanOutputError, QwenSupervisorModel


class FakeQwen:
    def __init__(self):
        self.calls = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append({"config": config, "messages": messages, **kwargs})
        if kwargs["schema_name"] == "supervisor_plan_v1":
            return {"output": {"selected_agents": ["jd"], "reason": "JD 검토 요청"}}
        return {"output": {"message": "JD 기준으로 보완이 필요합니다."}}


class QwenSupervisorModelTest(unittest.TestCase):
    def test_accepts_news_plan_and_describes_news_capability(self):
        calls = []

        def qwen(config, messages, **kwargs):
            calls.append({"config": config, "messages": messages, **kwargs})
            return {"output": {"selected_agents": ["news"], "reason": "최근 변화 확인"}}

        model = QwenSupervisorModel({}, qwen_caller=qwen)

        plan = model.create_plan(
            instruction="최근 기업 변화를 검토해줘",
            documents=[],
            conversation=[],
            available_agents=["news"],
            validation_error=None,
        )

        payload = json.loads(calls[0]["messages"][1]["content"])
        self.assertEqual(plan.selected_agents, ["news"])
        self.assertEqual(
            payload["agent_capabilities"]["news"],
            "기업·산업·직무 변화의 기사 근거와 JD 관련성 분석",
        )

    def test_position_capability_does_not_assume_backend_role(self):
        qwen = FakeQwen()
        model = QwenSupervisorModel({}, qwen_caller=qwen)

        model.create_plan(
            instruction="디자인 직무 경험을 검토해줘",
            documents=[],
            conversation=[],
            available_agents=["position"],
            validation_error=None,
        )

        payload = json.loads(qwen.calls[0]["messages"][1]["content"])
        capability = payload["agent_capabilities"]["position"]
        self.assertIn("지원 직무", capability)
        self.assertNotIn("백엔드", capability)

    def test_malformed_plan_output_uses_dedicated_contract_error(self):
        for response in (
            {}, None, {"output": None},
            {"output": {"selected_agents": ["unknown"], "reason": "bad"}},
        ):
            with self.subTest(response=response):
                model = QwenSupervisorModel(
                    {}, qwen_caller=lambda *args, **kwargs: response
                )
                with self.assertRaises(PlanOutputError):
                    model.create_plan(
                        instruction="검토", documents=[], conversation=[],
                        available_agents=["jd"], validation_error=None,
                    )

    def test_real_caller_invalid_json_uses_dedicated_contract_error(self):
        model = QwenSupervisorModel(
            {"base_url": "http://qwen.test", "model": "qwen", "api_key": "test"}
        )
        with patch("ai.llm.vllm.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = (
                b'{"choices": [{"message": {"content": "not JSON"}}]}'
            )
            with self.assertRaises(PlanOutputError):
                model.create_plan(
                    instruction="검토", documents=[], conversation=[],
                    available_agents=["jd"], validation_error=None,
                )

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

    def test_plan_schema_and_prompt_explain_writing_selection_rules(self):
        qwen = FakeQwen()
        model = QwenSupervisorModel({}, qwen_caller=qwen)

        model.create_plan(
            instruction="자기소개서를 고쳐줘",
            documents=[],
            conversation=[],
            available_agents=["writing"],
            validation_error=None,
        )

        self.assertEqual(
            set(PLAN_SCHEMA["properties"]["selected_agents"]["items"]["enum"]),
            {"jd", "position", "writing", "news", "company"},
        )
        prompt = qwen.calls[0]["messages"][0]["content"]
        self.assertIn("Writing", prompt)
        self.assertIn("첨삭", prompt)
        self.assertIn("명시", prompt)
