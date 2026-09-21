import unittest

from ai.supervisor.adapters import (
    AgentRegistry,
    JdAgentAdapter,
    NewsAgentAdapter,
    PositionAgentAdapter,
    WritingAgentAdapter,
)
from ai.supervisor.contracts import AgentResult
from ai.writing_coaching.contracts import WritingMessageResponse


class FakeJdService:
    def __init__(self):
        self.calls = []

    def analyze_documents(self, context_id, documents):
        self.calls.append((context_id, documents))
        return {"context_id": context_id}

    def get_context(self, context_id):
        return {"company_name": "테스트", "position_name": "백엔드", "requirements": []}


class FakeJdChatService:
    def __init__(self, reply=None, error=None):
        self.calls = []
        self._reply = reply or {"answer": "대화 답변"}
        self._error = error

    def respond(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._reply


class FakePositionChatService:
    def __init__(self, reply=None, error=None):
        self.calls = []
        self._reply = reply or {"answer": "직무 설명입니다", "referenced_finding_ids": []}
        self._error = error

    def respond(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._reply


class FakePositionService:
    def __init__(self):
        self.calls = []

    def analyze(self, rubric_id, position_context, documents, conversation):
        self.calls.append((rubric_id, position_context, documents, conversation))
        return {
            "analysis_status": "NO_EXPERIENCE_CLAIM",
            "rubric": {"id": rubric_id},
            "findings": [],
        }


class FakeNewsResponse:
    def model_dump(self, *, mode="python"):
        return {"analysis": {"company": {"corp_code": "00126380"}}}


class FakeNewsService:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def analyze(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return FakeNewsResponse()


class FakeWritingService:
    def __init__(self):
        self.calls = []

    def respond(self, request):
        self.calls.append(request)
        return WritingMessageResponse.model_validate({
            "status": "REVISED",
            "message": "수정했습니다.",
            "revision": {
                "revision_strength": "BALANCED",
                "revised_text": "수정된 초안",
                "char_count": 6,
                "changes": [],
                "warnings": [],
            },
        })


class JdAgentAdapterTest(unittest.TestCase):
    """채용공고 담당은 대조 결과 위에서 대화한다.

    대조만 반복하면 무엇을 묻든 같은 말이 돌아온다 — 입력(공고·자소서)이 그대로이기 때문이다.
    """

    DOCUMENTS = [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}]
    CONTEXT = {"job_context_id": "jctx"}

    def test_question_is_answered_on_top_of_the_analysis(self):
        jd, chat = FakeJdService(), FakeJdChatService()

        result = JdAgentAdapter(lambda: jd, lambda: chat).execute(
            "이 공고에서 뭘 더 준비해야 하나요?",
            self.DOCUMENTS,
            [{"role": "USER", "content": "안녕"}],
            self.CONTEXT,
        )

        self.assertEqual(result["message"], "대화 답변")
        self.assertEqual(result["context_id"], "jctx")  # 대조 결과도 함께 남는다
        self.assertEqual(chat.calls[0]["message"], "이 공고에서 뭘 더 준비해야 하나요?")
        self.assertEqual(chat.calls[0]["history"], [{"role": "user", "content": "안녕"}])

    def test_auto_review_keeps_the_analysis_as_is(self):
        """물어본 것이 없으면 대조 결과가 곧 답이다."""
        jd, chat = FakeJdService(), FakeJdChatService()

        result = JdAgentAdapter(lambda: jd, lambda: chat).execute(
            "", self.DOCUMENTS, [], self.CONTEXT
        )

        self.assertEqual(result, {"context_id": "jctx"})
        self.assertEqual(chat.calls, [])

    def test_chat_failure_falls_back_to_the_analysis(self):
        """대화는 대조 결과 위에 얹는 것이다. 여기서 실패해도 대조 결과는 보여 준다."""
        jd = FakeJdService()
        chat = FakeJdChatService(error=RuntimeError("모델 죽음"))

        result = JdAgentAdapter(lambda: jd, lambda: chat).execute(
            "질문", self.DOCUMENTS, [], self.CONTEXT
        )

        self.assertEqual(result, {"context_id": "jctx"})


class AgentRegistryTest(unittest.TestCase):
    def test_news_adapter_ignores_applicant_documents(self):
        service = FakeNewsService()
        adapter = NewsAgentAdapter(service)

        result = adapter.execute(
            "최근 변화",
            [{"document_id": "resume-1", "document_type": "RESUME", "text": "이력"}],
            [{"message_id": "m1", "role": "USER", "content": "뉴스도 봐줘"}],
            {"job_context_id": "ctx-1", "corp_code": "00126380"},
        )

        self.assertFalse(hasattr(service.calls[0], "documents"))
        self.assertEqual(result["analysis"]["company"]["corp_code"], "00126380")

    def test_resolves_context_backed_agents_and_calls_services_directly(self):
        jd = FakeJdService()
        position = FakePositionService()
        registry = AgentRegistry([JdAgentAdapter(lambda: jd), PositionAgentAdapter(lambda: position)])
        contexts = {
            "jd": {"job_context_id": "jctx_1"},
            "position": {
                "rubric_id": "experience-depth-v1",
                "position_context": {
                    "position_name": "백엔드 개발자",
                    "priority_requirements": ["Spring 기반 API 개발"],
                },
            },
        }
        documents = [
            {"document_id": "resume-1", "document_type": "RESUME", "text": "이력"},
            {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "자소서"},
            {"document_id": "experience-1", "document_type": "EXPERIENCE", "text": "경험"},
            {"document_id": "portfolio-1", "document_type": "PORTFOLIO", "text": "포트폴리오"},
        ]
        position_documents = [documents[1], documents[2]]

        self.assertEqual(registry.available_names(contexts), ["jd", "position"])
        registry.execute("jd", "검토", documents, [], contexts["jd"])
        position_result = registry.execute(
            "position", "검토", documents, [], contexts["position"]
        )

        self.assertEqual(jd.calls[0][0], "jctx_1")
        # 백엔드가 말풍선에 띄우는 message 가 단독 API 와 같은 모양으로 들어 있어야 한다.
        self.assertEqual(position_result["analysis_status"], "NO_EXPERIENCE_CLAIM")
        self.assertIn("구체화할 경험을 찾지 못했습니다", position_result["message"])
        self.assertEqual(position.calls, [(
            "experience-depth-v1",
            {
                "position_name": "백엔드 개발자",
                "priority_requirements": ["Spring 기반 API 개발"],
            },
            position_documents,
            # 이번에 물은 것이 대화 끝에 붙는다. 이력만 넘기면 포지션 담당이 "무엇을 묻는지"
            # 를 몰라 늘 같은 분석을 낸다.
            [{"role": "USER", "content": "검토"}],
        )])

    def test_position_answers_the_question_on_top_of_the_analysis(self):
        """평가 결과만 돌려주면 무엇을 묻든 같은 답이 된다(QA 실측: 12번 중 4종)."""
        position, chat = FakePositionService(), FakePositionChatService()
        context = {
            "rubric_id": "experience-depth-v1",
            "position_context": {"position_name": "백엔드 개발자", "priority_requirements": []},
        }

        result = PositionAgentAdapter(lambda: position, lambda: chat).execute(
            "이 직무는 무슨 일을 해?",
            [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            [{"role": "USER", "content": "안녕"}],
            context,
        )

        self.assertEqual(result["message"], "직무 설명입니다")
        self.assertEqual(result["analysis_status"], "NO_EXPERIENCE_CLAIM")  # 평가도 남는다
        self.assertEqual(chat.calls[0]["message"], "이 직무는 무슨 일을 해?")
        # 이번 질문은 message 로 따로 가므로 이력에 두 번 실리지 않는다.
        self.assertEqual(chat.calls[0]["history"], [{"role": "USER", "content": "안녕"}])

    def test_position_auto_review_keeps_the_analysis(self):
        position, chat = FakePositionService(), FakePositionChatService()
        context = {
            "rubric_id": "experience-depth-v1",
            "position_context": {"position_name": "백엔드 개발자", "priority_requirements": []},
        }

        result = PositionAgentAdapter(lambda: position, lambda: chat).execute(
            "", [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            [], context,
        )

        self.assertNotEqual(result["message"], "직무 설명입니다")
        self.assertEqual(chat.calls, [])

    def test_position_chat_failure_falls_back_to_the_analysis(self):
        position = FakePositionService()
        chat = FakePositionChatService(error=RuntimeError("모델 죽음"))
        context = {
            "rubric_id": "experience-depth-v1",
            "position_context": {"position_name": "백엔드 개발자", "priority_requirements": []},
        }

        result = PositionAgentAdapter(lambda: position, lambda: chat).execute(
            "질문", [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            [], context,
        )

        self.assertEqual(result["analysis_status"], "NO_EXPERIENCE_CLAIM")
        self.assertTrue(result["message"])

    def test_position_rejects_request_without_supported_documents(self):
        position = FakePositionService()
        adapter = PositionAgentAdapter(lambda: position)
        context = {
            "rubric_id": "experience-depth-v1",
            "position_context": {
                "position_name": "백엔드 개발자",
                "priority_requirements": [],
            },
        }

        with self.assertRaisesRegex(
            ValueError, "position agent requires SELF_INTRO or EXPERIENCE document"
        ):
            adapter.execute(
                "검토",
                [{"document_id": "resume-1", "document_type": "RESUME", "text": "이력"}],
                [],
                context,
            )

        self.assertEqual(position.calls, [])

    def test_writing_adapter_builds_request_from_one_draft_and_prior_feedback(self):
        writing_service = FakeWritingService()
        adapter = WritingAgentAdapter(lambda: writing_service)
        prior_result = AgentResult(agent="jd", status="SUCCESS", result={
            "requirements": [{
                "requirement_id": "req-1", "label": "NOT_SUPPORTED",
                "suggested_actions": ["역할을 추가하세요."],
            }]
        })

        result = adapter.execute(
            "두괄식으로 고쳐줘",
            [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "초안"}],
            [],
            {"question": "협업 경험", "char_limit": 700},
            prior_results=[prior_result],
        )

        self.assertEqual(result["status"], "REVISED")
        self.assertEqual(writing_service.calls[0].feedback[0].source, "jd")
        self.assertEqual(writing_service.calls[0].draft, "초안")

    def test_writing_adapter_requires_exactly_one_self_intro_document(self):
        writing_service = FakeWritingService()
        adapter = WritingAgentAdapter(lambda: writing_service)
        context = {"question": "협업 경험", "char_limit": 700}

        for documents in (
            [],
            [
                {"document_id": "one", "document_type": "SELF_INTRO", "text": "초안"},
                {"document_id": "two", "document_type": "SELF_INTRO", "text": "다른 초안"},
            ],
        ):
            with self.subTest(documents=documents), self.assertRaisesRegex(
                ValueError, "exactly one SELF_INTRO"
            ):
                adapter.execute("첨삭", documents, [], context)

        self.assertEqual(writing_service.calls, [])

    def test_availability_does_not_resolve_any_service_provider(self):
        calls = {"jd": 0, "position": 0, "writing": 0}

        def provider(name, service):
            def resolve():
                calls[name] += 1
                return service
            return resolve

        registry = AgentRegistry([
            JdAgentAdapter(provider("jd", FakeJdService())),
            PositionAgentAdapter(provider("position", FakePositionService())),
            WritingAgentAdapter(provider("writing", FakeWritingService())),
        ])

        self.assertEqual(
            registry.available_names({
                "jd": {"job_context_id": "jctx"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {"position_name": "백엔드 개발자"},
                },
                "writing": {"question": "협업 경험", "char_limit": 700},
            }),
            ["jd", "position", "writing"],
        )
        self.assertEqual(calls, {"jd": 0, "position": 0, "writing": 0})


if __name__ == "__main__":
    unittest.main()
