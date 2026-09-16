import unittest

from pydantic import ValidationError

from ai.supervisor.contracts import SupervisorPlan, SupervisorRunRequest


class SupervisorContractsTest(unittest.TestCase):
    def test_accepts_supported_documents_and_contexts(self):
        request = SupervisorRunRequest.model_validate({
            "instruction": "공고 적합성과 경험 깊이를 검토해줘",
            "documents": [{
                "document_id": "essay-1",
                "document_type": "SELF_INTRO",
                "text": "Spring 기반 주문 API를 구현했습니다.",
            }],
            "conversation": [],
            "agent_contexts": {
                "jd": {"job_context_id": "jctx_1"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": ["Spring 기반 API 개발"],
                    },
                },
            },
        })

        self.assertEqual(request.documents[0].document_type, "SELF_INTRO")
        self.assertEqual(request.agent_contexts.jd.job_context_id, "jctx_1")
        self.assertEqual(
            request.agent_contexts.position.position_context.position_name,
            "백엔드 개발자",
        )

    def test_rejects_legacy_position_profile_context(self):
        with self.assertRaises(ValidationError):
            SupervisorRunRequest.model_validate({
                "instruction": "경험 깊이를 검토해줘",
                "documents": [{
                    "document_id": "essay-1",
                    "document_type": "SELF_INTRO",
                    "text": "Spring 기반 주문 API를 구현했습니다.",
                }],
                "conversation": [],
                "agent_contexts": {
                    "position": {"position_profile_id": "backend-v1"},
                },
            })

    def test_rejects_unknown_fields_and_blank_instruction(self):
        with self.assertRaises(ValidationError):
            SupervisorRunRequest.model_validate({
                "instruction": " ",
                "documents": [],
                "conversation": [],
                "agent_contexts": {},
                "unexpected": True,
            })

    def test_accepts_writing_context_and_writing_plan(self):
        request = SupervisorRunRequest.model_validate({
            "instruction": "협업 경험을 두괄식으로 첨삭해줘",
            "documents": [{
                "document_id": "essay-1",
                "document_type": "SELF_INTRO",
                "text": "협업 경험 초안입니다.",
            }],
            "agent_contexts": {
                "writing": {
                    "question": "협업 경험을 작성해 주세요.",
                    "char_limit": 700,
                }
            },
        })

        self.assertEqual(request.agent_contexts.writing.question, "협업 경험을 작성해 주세요.")
        self.assertEqual(request.agent_contexts.writing.char_limit, 700)
        self.assertEqual(
            SupervisorPlan(selected_agents=["writing"], reason="첨삭").selected_agents,
            ["writing"],
        )

    def test_rejects_invalid_writing_context(self):
        base = {
            "instruction": "첨삭해줘",
            "documents": [{
                "document_id": "essay-1",
                "document_type": "SELF_INTRO",
                "text": "초안",
            }],
            "agent_contexts": {"writing": {"question": "협업 경험", "char_limit": 700}},
        }
        for value in (" ",):
            with self.subTest(field="question", value=value), self.assertRaises(ValidationError):
                SupervisorRunRequest.model_validate({
                    **base, "agent_contexts": {"writing": {"question": value, "char_limit": 700}}
                })
        for value in (True, 0, 50_001):
            with self.subTest(field="char_limit", value=value), self.assertRaises(ValidationError):
                SupervisorRunRequest.model_validate({
                    **base, "agent_contexts": {"writing": {"question": "협업 경험", "char_limit": value}}
                })
