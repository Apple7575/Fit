import unittest

from fastapi.testclient import TestClient

from ai.jd_coaching.api import (
    app,
    get_analysis_service,
    get_stateless_chat_service,
)
from ai.jd_coaching.chat import StatelessChatService


class FakeAnalysisService:
    def get_context(self, context_id):
        if context_id == "missing":
            raise KeyError(context_id)
        return {
            "context_id": context_id,
            "company_name": "테스트기업",
            "position_name": "백엔드",
        }


class StatelessChatApiTest(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_qwen(config, messages, **kwargs):
            self.calls.append(messages)
            return {
                "model": "test-qwen",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "output": {
                    "answer": "배포 성과를 구체적으로 써 주세요.",
                    "referenced_requirement_ids": ["role-001"],
                    "follow_up_questions": ["성과를 수치로 말할 수 있나요?"],
                },
            }

        self.chat_service = StatelessChatService(
            config={"model": "test-qwen"}, qwen_caller=fake_qwen
        )
        app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
        app.dependency_overrides[get_stateless_chat_service] = lambda: self.chat_service
        self.client = TestClient(app)
        self.request = {
            "context_id": "jctx-1",
            "analysis_result": {
                "context_id": "jctx-1",
                "summary": {"partially_supported": 1},
                "requirements": [{"requirement_id": "role-001", "requirement": "배포 경험"}],
            },
            "current_document": {"document_id": "essay-1", "text": "서비스를 배포했습니다."},
            "message": "이 부분을 어떻게 고칠까?",
            "history": [
                {"role": "user", "content": "배포 경험이 부족해?"},
                {"role": "assistant", "content": "결과를 구체화해 주세요."},
            ],
        }

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_answers_from_supplied_document_analysis_and_history(self):
        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "배포 성과를 구체적으로 써 주세요.")
        self.assertEqual(response.json()["referenced_requirement_ids"], ["role-001"])
        self.assertEqual(self.calls[0][-3:], [
            {"role": "user", "content": "배포 경험이 부족해?"},
            {"role": "assistant", "content": "결과를 구체화해 주세요."},
            {"role": "user", "content": "이 부분을 어떻게 고칠까?"},
        ])
        self.assertIn("서비스를 배포했습니다.", self.calls[0][0]["content"])
        self.assertIn("role-001", self.calls[0][0]["content"])

    def test_rejects_analysis_for_another_context(self):
        self.request["analysis_result"]["context_id"] = "jctx-other"

        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.calls, [])

    def test_requires_current_document(self):
        del self.request["current_document"]

        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    def test_rejects_blank_history_message(self):
        self.request["history"][0]["content"] = "   "

        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    def test_missing_context_returns_404(self):
        self.request["context_id"] = "missing"
        self.request["analysis_result"]["context_id"] = "missing"

        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.calls, [])

    def test_malformed_model_response_returns_502_not_missing_context(self):
        class MalformedChatService:
            def respond(self, **kwargs):
                raise KeyError("output")

        app.dependency_overrides[get_stateless_chat_service] = lambda: MalformedChatService()

        response = self.client.post("/internal/messages", json=self.request)

        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
