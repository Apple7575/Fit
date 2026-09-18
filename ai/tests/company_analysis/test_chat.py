from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

import numpy as np
from fastapi.testclient import TestClient

from ai.company_analysis.api import create_app
from ai.company_analysis.chat import CompanyChatService, ConversationMismatchError, ConversationNotFoundError, INSUFFICIENT_ANSWER, chat_schema
from ai.company_analysis.chat_store import InMemoryConversationStore
from ai.company_analysis.contracts import ChatRequest
from ai.company_analysis.retrieval import BM25Index, CompanyRetriever, VectorIndex, fuse, tokenize
from ai.company_analysis.service import CompanyAnalysisService
from ai.company_analysis.store import InMemoryReportStore
from ai.tests.company_analysis.test_api import FakeRepository, _facts
from ai.tests.company_analysis.test_narrative import CHUNKS, RCEPT, FakeReports, _business_report

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


class ScriptedChatClient:
    def __init__(self, outputs: list[dict]) -> None:
        self._outputs = list(outputs)
        self.calls: list[dict] = []
        self.last_usage = {"prompt_tokens": 10, "completion_tokens": 5}

    def complete(self, messages, schema, *, max_tokens):
        self.calls.append({"messages": messages, "schema": schema})
        return self._outputs.pop(0)


def _service(outputs: list[dict], *, with_report_chunks: bool = True) -> tuple[CompanyChatService, ScriptedChatClient, InMemoryConversationStore]:
    analysis = CompanyAnalysisService(repository=FakeRepository({"00164779": _facts()}), store=InMemoryReportStore(clock=lambda: NOW), clock=lambda: NOW)
    client = ScriptedChatClient(outputs)
    store = InMemoryConversationStore()
    counter = iter(range(1, 100))
    service = CompanyChatService(
        analysis=analysis,
        reports=FakeReports(_business_report() if with_report_chunks else None),
        retriever=CompanyRetriever(),
        client=client,
        store=store,
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(counter)}",
    )
    return service, client, store


def _payload(client: ScriptedChatClient, call: int = 0) -> dict:
    user = client.calls[call]["messages"][1]["content"]
    return json.loads(user[: user.rindex("\n\n질문:")])


class RetrievalTest(unittest.TestCase):
    def test_tokenize_adds_korean_ngrams(self):
        tokens = tokenize("반도체는 HBM 97.1조원")
        self.assertIn("반도체는", tokens)
        self.assertIn("c3:반도체", tokens)
        self.assertIn("hbm", tokens)

    def test_bm25_finds_relevant_chunk(self):
        hits = BM25Index(_business_report().chunks).search("시장점유율 DRAM", top_k=3)
        self.assertEqual(hits[0].chunk.evidence_id, "e-share")

    def test_vector_index_and_fusion(self):
        chunks = _business_report().chunks
        vectors = {c.evidence_id: np.eye(len(chunks), dtype=np.float32)[i] for i, c in enumerate(chunks)}
        index = VectorIndex(chunks, vectors)
        query = vectors["e-risk"]
        self.assertEqual(index.search(query, top_k=1)[0].chunk.evidence_id, "e-risk")
        bm25 = BM25Index(chunks).search("환율변동위험", top_k=3)
        fused = fuse([bm25, index.search(query, top_k=3)], top_k=2)
        self.assertEqual(fused[0].chunk.evidence_id, "e-risk")
        self.assertEqual(fused[0].retrievers, ("bm25", "vector"))

    def test_retriever_falls_back_to_bm25_without_encoder(self):
        hits = CompanyRetriever().search(_business_report(), "환율 위험", top_k=2)
        self.assertEqual(hits[0].chunk.evidence_id, "e-risk")


class ChatServiceTest(unittest.TestCase):
    def test_answer_with_citations_and_persistence(self):
        service, client, store = _service([
            {"answer": "SK하이닉스의 2025년 매출은 97.1조원입니다. 주력은 DRAM과 NAND입니다.",
             "citation_ids": ["report:intro", "report:financials:0", "e-overview"], "needs_news": False, "needs_reason": "",
             "follow_up_questions": ["영업이익률은 어떤가요?"]},
        ])
        response = service.respond(ChatRequest(corp_code="00164779", message="매출이 얼마야?"))
        self.assertEqual(response.assistant_message.content, "SK하이닉스의 2025년 매출은 97.1조원입니다. 주력은 DRAM과 NAND입니다.")
        self.assertEqual([c.source_type for c in response.assistant_message.citations], ["COMPANY_PROFILE", "COMPANY_METRIC", "DART_BUSINESS_REPORT"])
        self.assertEqual(response.assistant_message.citations[2].rcept_no, RCEPT)
        self.assertEqual(response.follow_up_questions, ["영업이익률은 어떤가요?"])
        self.assertEqual(response.report_stage, "FULL")
        history = service.history(response.conversation_id)
        self.assertEqual([m.role for m in history.messages], ["USER", "ASSISTANT"])
        # 스키마 enum 은 이번에 넣은 근거 ID 만 허용한다
        enum = client.calls[0]["schema"]["properties"]["citation_ids"]["items"]["enum"]
        self.assertIn("report:intro", enum)
        self.assertIn("e-overview", enum)
        self.assertNotIn("e-old", enum)
        payload = _payload(client)
        self.assertEqual(payload["company"]["name"], "SK하이닉스")
        self.assertEqual(payload["history"], [])

    def test_history_is_passed_on_second_turn(self):
        service, client, _ = _service([
            {"answer": "첫 답입니다.", "citation_ids": ["report:intro"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
            {"answer": "둘째 답입니다.", "citation_ids": ["report:intro"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
        ])
        first = service.respond(ChatRequest(corp_code="00164779", message="첫 질문"))
        service.respond(ChatRequest(corp_code="00164779", message="둘째 질문", conversation_id=first.conversation_id))
        history = _payload(client, 1)["history"]
        self.assertEqual([h["role"] for h in history], ["user", "assistant"])
        self.assertEqual(history[0]["content"], "첫 질문")

    def test_numbers_not_in_evidence_trigger_retry_then_insufficient(self):
        service, client, _ = _service([
            {"answer": "매출은 95.3조원입니다.", "citation_ids": ["report:intro"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
            {"answer": "매출은 96조원입니다.", "citation_ids": ["report:intro"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
        ])
        response = service.respond(ChatRequest(corp_code="00164779", message="매출?"))
        self.assertEqual(len(client.calls), 2)
        self.assertIn("근거와 맞지 않았다", client.calls[1]["messages"][0]["content"])
        self.assertEqual(response.assistant_message.content, INSUFFICIENT_ANSWER)
        self.assertEqual(response.assistant_message.citations, [])

    def test_needs_news_is_recorded(self):
        service, _, _ = _service([
            {"answer": "공시에는 최근 주가 정보가 없습니다.", "citation_ids": [], "needs_news": True,
             "needs_reason": "최근 주가와 뉴스 동향이 필요합니다.", "follow_up_questions": []},
        ])
        response = service.respond(ChatRequest(corp_code="00164779", message="최근 주가 어때?"))
        self.assertEqual(response.assistant_message.needs[0].agent, "news")
        self.assertEqual(response.assistant_message.needs[0].reason, "최근 주가와 뉴스 동향이 필요합니다.")
        self.assertEqual(response.assistant_message.content, "공시에는 최근 주가 정보가 없습니다.")

    def test_id_leak_is_stripped(self):
        service, _, _ = _service([
            {"answer": "주력 제품은 DRAM입니다. (evidence_id: dart-business-report-abc123, report:intro)", "citation_ids": ["report:intro"],
             "needs_news": False, "needs_reason": "", "follow_up_questions": []},
        ])
        response = service.respond(ChatRequest(corp_code="00164779", message="주력 제품?"))
        self.assertEqual(response.assistant_message.content, "주력 제품은 DRAM입니다.")

    def test_conversation_errors(self):
        service, _, _ = _service([])
        with self.assertRaises(ConversationNotFoundError):
            service.respond(ChatRequest(corp_code="00164779", message="?", conversation_id="missing"))
        service2, _, store = _service([
            {"answer": "답", "citation_ids": ["report:intro"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
        ])
        first = service2.respond(ChatRequest(corp_code="00164779", message="질문"))
        with self.assertRaises(ConversationMismatchError):
            service2.respond(ChatRequest(corp_code="00126380", message="?", conversation_id=first.conversation_id))

    def test_works_without_business_report_chunks(self):
        service, client, _ = _service([
            {"answer": "매출은 97.1조원입니다.", "citation_ids": ["report:financials:0"], "needs_news": False, "needs_reason": "", "follow_up_questions": []},
        ], with_report_chunks=False)
        response = service.respond(ChatRequest(corp_code="00164779", message="매출?"))
        self.assertTrue(all(e["evidence_id"].startswith("report:") for e in _payload(client)["evidence"]))
        self.assertEqual(response.assistant_message.content, "매출은 97.1조원입니다.")


class ChatApiTest(unittest.TestCase):
    def test_chat_and_history_endpoints(self):
        service, _, _ = _service([
            {"answer": "주력 제품은 DRAM과 NAND입니다.", "citation_ids": ["e-overview"], "needs_news": False, "needs_reason": "", "follow_up_questions": ["재무는?"]},
        ])
        analysis = service._analysis  # noqa: SLF001 — 테스트에서 같은 인스턴스를 주입한다
        client = TestClient(create_app(lambda: analysis, lambda: service))
        response = client.post("/internal/chat", json={"corp_code": "00164779", "message": "DRAM과 NAND 메모리 반도체 사업을 설명해줘"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["assistant_message"]["content"], "주력 제품은 DRAM과 NAND입니다.")
        self.assertEqual(body["assistant_message"]["citations"][0]["source_type"], "DART_BUSINESS_REPORT")
        history = client.get(f"/internal/conversations/{body['conversation_id']}")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["messages"]), 2)
        self.assertEqual(client.get("/internal/conversations/nope").status_code, 404)
        self.assertEqual(client.post("/internal/chat", json={"corp_code": "00164779", "message": " "}).status_code, 422)
        self.assertEqual(client.post("/internal/chat", json={"corp_code": "00164779", "message": "?", "conversation_id": "nope"}).status_code, 404)

    def test_schema_shape(self):
        schema = chat_schema(["a"])
        self.assertEqual(schema["properties"]["citation_ids"]["items"]["enum"], ["a"])
        self.assertIn("needs_news", schema["required"])


if __name__ == "__main__":
    unittest.main()
