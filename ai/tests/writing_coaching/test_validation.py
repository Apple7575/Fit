import unittest
from typing import Any

from pydantic import ValidationError

from ai.writing_coaching.contracts import WritingMessageRequest
from ai.writing_coaching.validation import extract_numeric_facts, validate_writing_output


VALID_REQUEST = {
    "message": "두괄식으로 고쳐줘",
    "question": "협업 경험을 작성해 주세요.",
    "draft": "API를 개선했습니다.",
    "char_limit": 700,
    "feedback": [{
        "feedback_id": "position-f1",
        "source": "position",
        "content": "본인의 판단 근거가 부족합니다.",
    }],
    "conversation": [],
}


def request_with(**overrides: Any) -> WritingMessageRequest:
    payload = {**VALID_REQUEST, **overrides}
    return WritingMessageRequest.model_validate(payload)


def revised_payload(
    revised_text: str = "API를 개선했습니다.", char_count: int = 1
) -> dict[str, Any]:
    return {
        "status": "REVISED",
        "message": "수정했습니다.",
        "revision": {
            "revision_strength": "BALANCED",
            "revised_text": revised_text,
            "char_count": char_count,
            "changes": [{
                "type": "CLARITY",
                "before": "API를 개선했습니다.",
                "after": "API를 개선했습니다.",
                "reason": "행동이 드러나도록 고쳤습니다.",
                "applied_feedback_ids": [],
            }],
            "warnings": [],
        },
    }


class WritingValidationTest(unittest.TestCase):
    def test_rejects_new_numeric_fact_from_assistant_or_feedback(self):
        request = request_with(
            draft="API를 개선했습니다.",
            feedback=[{
                "feedback_id": "jd-r1", "source": "jd", "content": "30% 개선을 강조하세요."
            }],
            conversation=[{
                "message_id": "a1", "role": "ASSISTANT", "content": "2배 빨라졌습니다."
            }],
        )

        with self.assertRaisesRegex(ValueError, "untrusted numeric fact"):
            payload = revised_payload("응답 속도를 30% 개선했습니다.")
            payload["revision"]["changes"] = []
            validate_writing_output(payload, request)

    def test_accepts_numeric_fact_from_user_message_and_recomputes_count(self):
        request = request_with(message="응답 속도를 30% 개선했습니다. 반영해줘")

        payload = revised_payload("응답 속도를 30% 개선했습니다.", char_count=999)
        payload["revision"]["changes"] = []
        result = validate_writing_output(payload, request)

        self.assertEqual(result.revision.char_count, len(result.revision.revised_text))

    def test_rejects_revision_over_char_limit(self):
        request = request_with(char_limit=3)
        with self.assertRaisesRegex(ValueError, "exceeds char_limit"):
            validate_writing_output(revised_payload("API를 개선했습니다."), request)

    def test_rejects_change_before_absent_from_draft(self):
        request = request_with()
        payload = revised_payload()
        payload["revision"]["changes"][0]["before"] = "없는 원문"
        with self.assertRaisesRegex(ValueError, "before must occur"):
            validate_writing_output(payload, request)

    def test_rejects_change_after_absent_from_revised_text(self):
        request = request_with()
        payload = revised_payload()
        payload["revision"]["changes"][0]["after"] = "없는 수정문"
        with self.assertRaisesRegex(ValueError, "after must occur"):
            validate_writing_output(payload, request)

    def test_rejects_unknown_feedback_id(self):
        request = request_with()
        payload = revised_payload()
        payload["revision"]["changes"][0]["applied_feedback_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "unknown feedback_id"):
            validate_writing_output(payload, request)

    def test_rejects_duplicate_applied_feedback_id(self):
        request = request_with()
        payload = revised_payload()
        payload["revision"]["changes"][0]["applied_feedback_ids"] = [
            "position-f1", "position-f1"
        ]
        with self.assertRaises(ValidationError):
            validate_writing_output(payload, request)

    def test_accepts_answered_and_clarification_without_revision(self):
        request = request_with()
        for status in ("ANSWERED", "CLARIFICATION_REQUIRED"):
            with self.subTest(status=status):
                result = validate_writing_output({
                    "status": status,
                    "message": "설명입니다.",
                    "revision": None,
                }, request)
                self.assertEqual(result.status, status)
                self.assertIsNone(result.revision)

    def test_rejects_invalid_model_output_schema(self):
        request = request_with()
        with self.assertRaises(ValidationError):
            validate_writing_output({
                "status": "REVISED",
                "message": "수정했습니다.",
                "revision": None,
            }, request)

    def test_extracts_and_normalizes_arabic_numeric_facts_with_units(self):
        text = "30%, 1,200명, 3.5배, 2 년, 4개월, 5일, 6개, 7초, 8분, 9시간"
        self.assertEqual(
            extract_numeric_facts(text),
            {"30%", "1200명", "3.5배", "2년", "4개월", "5일", "6개", "7초", "8분", "9시간"},
        )

    def test_accepts_whitespace_after_grouping_comma_as_same_numeric_fact(self):
        self.assertEqual(extract_numeric_facts("1,200명"), extract_numeric_facts("1, 200명"))
        request = request_with(draft="API 성과는 1,200명입니다.")
        payload = revised_payload("API 성과는 1, 200명입니다.")
        payload["revision"]["changes"] = []
        result = validate_writing_output(payload, request)
        self.assertEqual(result.revision.char_count, len(result.revision.revised_text))

    def test_does_not_translate_number_words(self):
        self.assertEqual(extract_numeric_facts("삼십 퍼센트와 두 배"), set())


if __name__ == "__main__":
    unittest.main()
