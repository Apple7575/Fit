import unittest

from ai.jd_coaching.chat import ChatService
from ai.jd_coaching.conversation_store import (
    Conversation,
    InMemoryConversationStore,
)


class ChatServiceTest(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_qwen(config, messages, **kwargs):
            self.calls.append(messages)
            return {
                "model": "test-qwen",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "output": {
                    "answer": "배포 과정과 결과를 추가해 주세요.",
                    "referenced_requirement_ids": ["role-001"],
                    "follow_up_questions": ["배포 과정에서 맡은 역할은 무엇인가요?"],
                },
            }

        self.store = InMemoryConversationStore()
        self.conversation = Conversation(
            conversation_id="conv-1",
            context_id="jctx-1",
            analysis_id="analysis-1",
            created_at="2026-09-13T00:00:00+00:00",
            updated_at="2026-09-13T00:00:00+00:00",
        )
        self.store.create_conversation(self.conversation)
        self.service = ChatService(
            config={"model": "test-qwen"},
            store=self.store,
            qwen_caller=fake_qwen,
        )
        self.context = {"company_name": "테스트기업", "position_name": "백엔드"}
        self.analysis = {
            "requirements": [
                {
                    "requirement_id": "role-001",
                    "requirement": "서비스 배포 경험",
                    "label": "PARTIALLY_SUPPORTED",
                    "feedback": "배포 과정이 부족합니다.",
                }
            ]
        }

    def test_answers_with_analysis_and_persists_exchange(self):
        result = self.service.respond(
            conversation=self.conversation,
            context=self.context,
            analysis_result=self.analysis,
            client_message_id="client-1",
            content="무엇을 보완해야 해?",
        )

        self.assertEqual(result["assistant_message"]["content"], "배포 과정과 결과를 추가해 주세요.")
        self.assertEqual(len(self.store.list_messages("conv-1")), 2)
        self.assertIn("role-001", str(self.calls[0]))

    def test_same_client_message_id_returns_saved_reply_without_second_call(self):
        first = self.service.respond(
            conversation=self.conversation,
            context=self.context,
            analysis_result=self.analysis,
            client_message_id="client-1",
            content="무엇을 보완해야 해?",
        )
        second = self.service.respond(
            conversation=self.conversation,
            context=self.context,
            analysis_result=self.analysis,
            client_message_id="client-1",
            content="무엇을 보완해야 해?",
        )

        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 1)

    def test_next_turn_contains_previous_exchange(self):
        self.service.respond(
            conversation=self.conversation,
            context=self.context,
            analysis_result=self.analysis,
            client_message_id="client-1",
            content="무엇을 보완해야 해?",
        )
        self.service.respond(
            conversation=self.conversation,
            context=self.context,
            analysis_result=self.analysis,
            client_message_id="client-2",
            content="그 내용을 더 설명해줘.",
        )

        second_call = self.calls[1]
        self.assertEqual(second_call[-3]["content"], "무엇을 보완해야 해?")
        self.assertEqual(
            second_call[-2]["content"], "배포 과정과 결과를 추가해 주세요."
        )
        self.assertEqual(second_call[-1]["content"], "그 내용을 더 설명해줘.")

    def test_rejects_unknown_requirement_reference(self):
        def invalid_qwen(config, messages, **kwargs):
            return {
                "model": "test-qwen",
                "usage": {},
                "output": {
                    "answer": "답변",
                    "referenced_requirement_ids": ["unknown"],
                    "follow_up_questions": [],
                },
            }

        service = ChatService(
            config={"model": "test-qwen"},
            store=self.store,
            qwen_caller=invalid_qwen,
        )

        with self.assertRaisesRegex(ValueError, "unknown requirement"):
            service.respond(
                conversation=self.conversation,
                context=self.context,
                analysis_result=self.analysis,
                client_message_id="client-2",
                content="근거가 뭐야?",
            )


if __name__ == "__main__":
    unittest.main()
