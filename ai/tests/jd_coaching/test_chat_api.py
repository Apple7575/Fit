import unittest

from fastapi.testclient import TestClient

from ai.jd_coaching.analysis_store import AnalysisJob, InMemoryAnalysisStore
from ai.jd_coaching.api import (
    app,
    get_analysis_service,
    get_analysis_store,
    get_chat_service,
    get_conversation_store,
)
from ai.jd_coaching.conversation_store import InMemoryConversationStore


class FakeAnalysisService:
    def get_context(self, context_id):
        if context_id == "missing":
            raise KeyError(context_id)
        return {
            "context_id": context_id,
            "company_name": "테스트기업",
            "position_name": "백엔드",
        }


class FakeChatService:
    def respond(self, **kwargs):
        return {
            "user_message": {
                "message_id": "msg-user",
                "role": "USER",
                "content": kwargs["content"],
                "client_message_id": kwargs["client_message_id"],
                "reply_to_message_id": None,
                "metadata": {},
                "created_at": "2026-09-13T00:01:00+00:00",
            },
            "assistant_message": {
                "message_id": "msg-assistant",
                "role": "ASSISTANT",
                "content": "배포 경험을 보완하세요.",
                "client_message_id": None,
                "reply_to_message_id": "msg-user",
                "metadata": {},
                "created_at": "2026-09-13T00:01:01+00:00",
            },
        }


class ChatApiTest(unittest.TestCase):
    def setUp(self):
        self.analysis_store = InMemoryAnalysisStore()
        self.conversation_store = InMemoryConversationStore()
        self.analysis_store.create(
            AnalysisJob(
                analysis_id="analysis-1",
                context_id="jctx-1",
                status="COMPLETED",
                documents=(),
                result={"requirements": [], "summary": {}},
                error=None,
                created_at="2026-09-13T00:00:00+00:00",
                updated_at="2026-09-13T00:00:10+00:00",
            )
        )
        app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
        app.dependency_overrides[get_analysis_store] = lambda: self.analysis_store
        app.dependency_overrides[get_conversation_store] = (
            lambda: self.conversation_store
        )
        app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_creates_reads_and_messages_conversation(self):
        created = self.client.post(
            "/internal/conversations",
            json={"context_id": "jctx-1", "analysis_id": "analysis-1"},
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["conversation_id"]

        sent = self.client.post(
            f"/internal/conversations/{conversation_id}/messages",
            json={
                "client_message_id": "spring-message-1",
                "content": "어떤 경험을 보완해야 해?",
            },
        )
        fetched = self.client.get(
            f"/internal/conversations/{conversation_id}"
        )

        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()["assistant_message"]["role"], "ASSISTANT")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["analysis_id"], "analysis-1")

    def test_rejects_conversation_for_incomplete_analysis(self):
        self.analysis_store.create(
            AnalysisJob(
                analysis_id="analysis-running",
                context_id="jctx-1",
                status="RUNNING",
                documents=(),
                result=None,
                error=None,
                created_at="2026-09-13T00:00:00+00:00",
                updated_at="2026-09-13T00:00:00+00:00",
            )
        )

        response = self.client.post(
            "/internal/conversations",
            json={"context_id": "jctx-1", "analysis_id": "analysis-running"},
        )

        self.assertEqual(response.status_code, 409)

    def test_rejects_analysis_from_other_context(self):
        response = self.client.post(
            "/internal/conversations",
            json={"context_id": "jctx-other", "analysis_id": "analysis-1"},
        )

        self.assertEqual(response.status_code, 409)

    def test_deletes_conversation(self):
        created = self.client.post(
            "/internal/conversations",
            json={"context_id": "jctx-1", "analysis_id": "analysis-1"},
        )
        conversation_id = created.json()["conversation_id"]

        deleted = self.client.delete(
            f"/internal/conversations/{conversation_id}"
        )
        fetched = self.client.get(
            f"/internal/conversations/{conversation_id}"
        )

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(fetched.status_code, 404)


if __name__ == "__main__":
    unittest.main()
