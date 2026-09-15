import unittest

from pydantic import ValidationError

from ai.supervisor.contracts import SupervisorRunRequest


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
