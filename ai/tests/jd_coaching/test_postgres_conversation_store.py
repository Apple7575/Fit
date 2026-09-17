import unittest
from datetime import datetime, timezone

from ai.jd_coaching.conversation_store import ChatMessage
from ai.jd_coaching.postgres_conversation_store import (
    PostgresConversationStore,
    _conversation_from_row,
    _message_from_row,
)


class FakeCursor:
    rowcount = 1

    def fetchone(self):
        return {"sequence_no": 1}


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters):
        self.calls.append((query, parameters))
        return FakeCursor()


class PostgresConversationStoreTest(unittest.TestCase):
    def test_converts_conversation_and_message_rows(self):
        conversation = _conversation_from_row(
            {
                "conversation_id": "conv-1",
                "context_id": "jctx-1",
                "analysis_id": "analysis-1",
                "created_at": datetime(2026, 9, 13, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 9, 13, 0, 1, tzinfo=timezone.utc),
            }
        )
        message = _message_from_row(
            {
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "role": "ASSISTANT",
                "content": "답변",
                "client_message_id": None,
                "reply_to_message_id": "msg-user",
                "metadata": {"model": "qwen"},
                "created_at": datetime(2026, 9, 13, 0, 2, tzinfo=timezone.utc),
                "sequence_no": 7,
            }
        )

        self.assertEqual(conversation.analysis_id, "analysis-1")
        self.assertEqual(message.reply_to_message_id, "msg-user")
        self.assertEqual(message.metadata["model"], "qwen")
        self.assertEqual(message.sequence_no, 7)

    def test_inserts_conversation_message_as_jsonb(self):
        connection = FakeConnection()
        store = PostgresConversationStore("postgresql://unused")
        store._connect = lambda: connection
        message = ChatMessage(
            message_id="msg-1",
            conversation_id="conv-1",
            role="USER",
            content="질문",
            client_message_id="client-1",
            reply_to_message_id=None,
            metadata={"key": "value"},
            created_at="2026-09-13T00:01:00+00:00",
        )

        store.append_message(message)

        query, parameters = connection.calls[0]
        self.assertIn("ai_conversation_messages", query)
        self.assertIn("RETURNING sequence_no", query)
        self.assertEqual(parameters[4], "client-1")

    def test_deletes_conversation(self):
        connection = FakeConnection()
        store = PostgresConversationStore("postgresql://unused")
        store._connect = lambda: connection

        store.delete_conversation("conv-1")

        query, parameters = connection.calls[0]
        self.assertIn("DELETE FROM ai_conversations", query)
        self.assertEqual(parameters, ("conv-1",))


if __name__ == "__main__":
    unittest.main()
