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
            # 사실 잠금은 그대로다. 문구가 바뀌어도 이 뜻은 남아야 한다.
            "Never invent a metric, date, employer, technology",
            "introduce facts",
        ):
            with self.subTest(value=value):
                self.assertIn(value, system)

    def test_system_message_opens_judgment_and_keeps_facts_locked(self):
        """사실과 판단을 한 문장으로 묶어 두면 초안을 되읊는 앵무새가 된다(실측).

        판단(구조·표현·독자 시각)은 첫 도구로 열고, 사실은 그대로 잠근다. 판단은 message 에만
        두고 revised_text 에는 사용자가 준 사실만 들어간다 — 여기가 자소서가 오염되는 지점이다.
        """
        request = WritingMessageRequest.model_validate({
            "message": "고쳐줘",
            "question": "협업 경험",
            "draft": "API를 개발했습니다.",
            "char_limit": 500,
        })

        system = build_writing_messages(request, RUBRIC)[0]["content"]

        for value in (
            "Facts and judgment are different things",
            "your first tool, not your last",
            "the way its reader will",
            # 자기가 낸 제안을 이어서 쓸 수 있어야 "두 번째 걸로" 가 통한다.
            "legitimate material for\nexpression and structure",
            "still not a source of facts",
            "one thing the user did not ask about",
            "Do not repeat a point you already made",
            '"revised_text" may contain only facts already present',
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
        self.assertIn("entire corrected JSON", payload["retry_instruction"])


if __name__ == "__main__":
    unittest.main()
