import json
import unittest

from ai.writing_coaching.contracts import WritingMessageRequest
from ai.writing_coaching.prompt import build_writing_messages


RUBRIC = {
    "id": "writing-quality-v1",
    "version": 1,
    "dimensions": [
        "QUESTION_FIT", "CORE_MESSAGE", "EVIDENCE", "AGENCY",
        "JOB_RELEVANCE", "READABILITY", "CREDIBILITY", "CONSTRAINTS",
    ],
    "change_types": [
        "STRUCTURE", "CLARITY", "CONCISENESS", "FLOW", "TONE", "LENGTH",
    ],
    "default_revision_strength": "BALANCED",
}


class WritingPromptTest(unittest.TestCase):
    def test_separates_trusted_user_facts_from_untrusted_context(self):
        request = WritingMessageRequest.model_validate({
            "message": "제가 캐시 전략을 직접 설계했습니다. 반영해줘",
            "question": "문제 해결 경험",
            "draft": "API를 개발했습니다.",
            "char_limit": 500,
            "feedback": [{
                "feedback_id": "position-f1",
                "source": "position",
                "content": "응답 속도를 30% 개선했다고 쓰세요.",
            }],
            "conversation": [
                {"message_id": "u1", "role": "USER", "content": "Redis를 사용했습니다."},
                {"message_id": "a1", "role": "ASSISTANT", "content": "처리량이 2배입니다."},
            ],
        })

        messages = build_writing_messages(request, RUBRIC)
        payload = json.loads(messages[1]["content"])

        self.assertEqual(payload["trusted_sources"]["current_draft"], request.draft)
        self.assertEqual(payload["trusted_sources"]["current_message"], request.message)
        self.assertEqual(
            payload["trusted_sources"]["prior_user_messages"][0]["content"],
            "Redis를 사용했습니다.",
        )
        self.assertEqual(
            payload["context_only"]["prior_assistant_messages"][0]["content"],
            "처리량이 2배입니다.",
        )
        self.assertEqual(
            payload["direction_only_feedback"][0]["content"],
            "응답 속도를 30% 개선했다고 쓰세요.",
        )
        self.assertNotIn("처리량이 2배입니다.", messages[0]["content"])

    def test_system_message_describes_contract_and_evidence_priority(self):
        request = WritingMessageRequest.model_validate({
            "message": "고쳐줘",
            "question": "협업 경험",
            "draft": "API를 개발했습니다.",
            "char_limit": 500,
        })

        system = build_writing_messages(request, RUBRIC)[0]["content"]

        for value in (
            "trusted",
            "feedback",
            "REVISED",
            "ANSWERED",
            "CLARIFICATION_REQUIRED",
            "STRUCTURE",
            "CLARITY",
            "CONCISENESS",
            "FLOW",
            "TONE",
            "LENGTH",
            "LIGHT",
            "BALANCED",
            "REWRITE",
            "BALANCED",
            "사실을 추가할 수 없다",
        ):
            with self.subTest(value=value):
                self.assertIn(value, system)

    def test_validation_error_is_data_and_requests_complete_json_retry(self):
        request = WritingMessageRequest.model_validate({
            "message": "고쳐줘",
            "question": "협업 경험",
            "draft": "API를 개발했습니다.",
            "char_limit": 500,
        })

        messages = build_writing_messages(request, RUBRIC, "change before must occur in draft")
        payload = json.loads(messages[1]["content"])

        self.assertEqual(
            payload["previous_validation_error"],
            "change before must occur in draft",
        )
        self.assertIn("JSON 객체 전체", payload["retry_instruction"])


if __name__ == "__main__":
    unittest.main()
