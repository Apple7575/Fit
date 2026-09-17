import unittest

from ai.jd_coaching.conversation_store import (
    ChatMessage,
    Conversation,
    InMemoryConversationStore,
)


class ConversationStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryConversationStore()
        self.conversation = Conversation(
            conversation_id="conv-1",
            context_id="jctx-1",
            analysis_id="analysis-1",
            created_at="2026-09-13T00:00:00+00:00",
            updated_at="2026-09-13T00:00:00+00:00",
        )
        self.store.create_conversation(self.conversation)

    def test_persists_conversation_and_ordered_messages(self):
        user = ChatMessage(
            message_id="msg-user",
            conversation_id="conv-1",
            role="USER",
            content="어떤 경험을 보완해야 해?",
            client_message_id="client-1",
            reply_to_message_id=None,
            metadata={},
            created_at="2026-09-13T00:01:00+00:00",
        )
        assistant = ChatMessage(
            message_id="msg-assistant",
            conversation_id="conv-1",
            role="ASSISTANT",
            content="배포 경험을 보완하세요.",
            client_message_id=None,
            reply_to_message_id="msg-user",
            metadata={"referenced_requirement_ids": ["role-001"]},
            created_at="2026-09-13T00:02:00+00:00",
        )

        self.store.append_message(user)
        self.store.append_message(assistant)

        self.assertEqual(self.store.get_conversation("conv-1"), self.conversation)
        messages = self.store.list_messages("conv-1")
        self.assertEqual([item.role for item in messages], ["USER", "ASSISTANT"])
        self.assertEqual([item.sequence_no for item in messages], [1, 2])
        self.assertEqual(
            self.store.find_user_message("conv-1", "client-1").message_id,
            user.message_id,
        )
        self.assertEqual(
            self.store.find_assistant_reply("msg-user").message_id,
            assistant.message_id,
        )

    def test_rejects_duplicate_client_message_id(self):
        message = ChatMessage(
            message_id="msg-user",
            conversation_id="conv-1",
            role="USER",
            content="질문",
            client_message_id="client-1",
            reply_to_message_id=None,
            metadata={},
            created_at="2026-09-13T00:01:00+00:00",
        )
        self.store.append_message(message)

        with self.assertRaisesRegex(ValueError, "client_message_id"):
            self.store.append_message(
                ChatMessage(**{**message.__dict__, "message_id": "msg-other"})
            )

    def test_deletes_conversation_and_messages(self):
        self.store.append_message(
            ChatMessage(
                message_id="msg-user",
                conversation_id="conv-1",
                role="USER",
                content="질문",
                client_message_id="client-1",
                reply_to_message_id=None,
                metadata={},
                created_at="2026-09-13T00:01:00+00:00",
            )
        )

        self.store.delete_conversation("conv-1")

        self.assertIsNone(self.store.get_conversation("conv-1"))
        self.assertEqual(self.store.list_messages("conv-1"), [])


if __name__ == "__main__":
    unittest.main()
