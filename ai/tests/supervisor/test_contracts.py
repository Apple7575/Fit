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
                "position": {"position_profile_id": "backend-v1"},
            },
        })

        self.assertEqual(request.documents[0].document_type, "SELF_INTRO")
        self.assertEqual(request.agent_contexts.jd.job_context_id, "jctx_1")

    def test_rejects_unknown_fields_and_blank_instruction(self):
        with self.assertRaises(ValidationError):
            SupervisorRunRequest.model_validate({
                "instruction": " ",
                "documents": [],
                "conversation": [],
                "agent_contexts": {},
                "unexpected": True,
            })
