import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from ai.writing_coaching.contracts import (
    WritingConversationMessage,
    WritingFeedback,
    WritingMessageRequest,
    WritingMessageResponse,
    WritingRevision,
    load_writing_rubric,
)


VALID_REQUEST = {
    "message": "두괄식으로 고쳐줘",
    "question": "협업 경험을 작성해 주세요.",
    "draft": "팀 프로젝트에서 API 개발을 담당했습니다.",
    "char_limit": 700,
    "feedback": [{
        "feedback_id": "position-f1",
        "source": "position",
        "content": "본인의 판단 근거가 부족합니다.",
    }],
    "conversation": [],
}


def response_payload(**overrides):
    payload = {
        "status": "ANSWERED",
        "message": "설명입니다.",
        "revision": None,
    }
    payload.update(overrides)
    return payload


def revision_payload(**overrides):
    payload = {
        "revision_strength": "BALANCED",
        "revised_text": "결론부터 설명했습니다.",
        "char_count": 13,
        "changes": [],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class WritingContractTest(unittest.TestCase):
    def test_accepts_valid_message_request(self):
        request = WritingMessageRequest.model_validate(VALID_REQUEST)
        self.assertEqual(request.feedback[0].feedback_id, "position-f1")

    def test_rejects_unknown_fields_and_duplicate_feedback_ids(self):
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "unknown": True})
        duplicated = {**VALID_REQUEST, "feedback": VALID_REQUEST["feedback"] * 2}
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate(duplicated)

    def test_enforces_status_revision_pair(self):
        with self.assertRaises(ValidationError):
            WritingMessageResponse.model_validate({
                "status": "REVISED", "message": "수정했습니다.", "revision": None,
            })
        answered = WritingMessageResponse.model_validate(response_payload())
        self.assertEqual(answered.status, "ANSWERED")
        with self.assertRaises(ValidationError):
            WritingMessageResponse.model_validate(response_payload(
                status="ANSWERED", revision=revision_payload()
            ))
        clarification = WritingMessageResponse.model_validate(response_payload(
            status="CLARIFICATION_REQUIRED"
        ))
        self.assertIsNone(clarification.revision)
        revised = WritingMessageResponse.model_validate(response_payload(
            status="REVISED", revision=revision_payload()
        ))
        self.assertEqual(revised.revision.revision_strength, "BALANCED")

    def test_schema_enforces_status_revision_pair(self):
        schema_path = Path(__file__).parents[2] / "writing_coaching" / "resources" / "schemas" / "writing-message-v1.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        conditions = schema["allOf"]
        self.assertEqual(len(conditions), 1)
        condition = conditions[0]
        self.assertEqual(
            condition["if"]["properties"]["status"]["const"], "REVISED"
        )
        self.assertEqual(
            condition["then"]["properties"]["revision"]["type"], "object"
        )
        self.assertEqual(
            condition["else"]["properties"]["revision"]["const"], None
        )

    def test_rejects_blank_strings(self):
        for field in ("message", "question", "draft"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                WritingMessageRequest.model_validate({
                    **VALID_REQUEST, field: "   "
                })
        with self.assertRaises(ValidationError):
            WritingFeedback.model_validate({
                "feedback_id": " ", "source": "position", "content": "내용"
            })
        with self.assertRaises(ValidationError):
            WritingConversationMessage.model_validate({
                "message_id": "m1", "role": "USER", "content": "\t"
            })

    def test_char_limit_is_strict_and_bounded(self):
        for value in (0, 50_001, True, "700"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                WritingMessageRequest.model_validate({**VALID_REQUEST, "char_limit": value})

    def test_rejects_too_many_feedback_items_and_invalid_feedback_source(self):
        feedback = [
            {"feedback_id": f"f{i}", "source": "position", "content": "내용"}
            for i in range(21)
        ]
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "feedback": feedback})
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({
                **VALID_REQUEST,
                "feedback": [{"feedback_id": "f1", "source": "other", "content": "내용"}],
            })

    def test_rejects_duplicate_feedback_ids_and_too_many_conversation_messages(self):
        feedback = [
            {"feedback_id": "f1", "source": "jd", "content": "내용"},
            {"feedback_id": "f1", "source": "supervisor", "content": "다른 내용"},
        ]
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "feedback": feedback})
        conversation = [
            {"message_id": f"m{i}", "role": "USER", "content": "메시지"}
            for i in range(21)
        ]
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "conversation": conversation})

    def test_rejects_invalid_conversation_role_and_duplicate_message_ids(self):
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({
                **VALID_REQUEST,
                "conversation": [{"message_id": "m1", "role": "SYSTEM", "content": "메시지"}],
            })
        conversation = [
            {"message_id": "m1", "role": "USER", "content": "첫 메시지"},
            {"message_id": "m1", "role": "ASSISTANT", "content": "두 번째 메시지"},
        ]
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "conversation": conversation})

    def test_rejects_unsupported_revision_change_and_warning_enums(self):
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(revision_strength="HEAVY"))
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(changes=[{
                "type": "GRAMMAR", "before": "전", "after": "후", "reason": "이유"
            }]))
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(warnings=[{
                "code": "UNKNOWN", "message": "경고"
            }]))

    def test_rejects_duplicate_applied_feedback_ids_and_change_warning_limits(self):
        change = {
            "type": "CLARITY", "before": "전", "after": "후", "reason": "이유",
            "applied_feedback_ids": ["f1", "f1"],
        }
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(changes=[change]))
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(changes=[{
                **change, "applied_feedback_ids": ["   "]
            }]))
        too_many_changes = [
            {"type": "CLARITY", "before": "전", "after": "후", "reason": "이유"}
            for _ in range(13)
        ]
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(changes=too_many_changes))
        too_many_warnings = [
            {"code": "MISSING_EVIDENCE", "message": "경고"}
            for _ in range(11)
        ]
        with self.assertRaises(ValidationError):
            WritingRevision.model_validate(revision_payload(warnings=too_many_warnings))

    def test_loads_canonical_rubric(self):
        rubric_path = Path(__file__).parents[2] / "writing_coaching" / "resources" / "rubrics" / "writing-quality-v1.json"
        rubric = load_writing_rubric(rubric_path)
        self.assertEqual(rubric["id"], "writing-quality-v1")
        self.assertEqual(rubric["version"], 1)

    def test_rejects_invalid_rubric_metadata_and_order(self):
        rubric_path = Path(__file__).parents[2] / "writing_coaching" / "resources" / "rubrics" / "writing-quality-v1.json"
        canonical = json.loads(rubric_path.read_text(encoding="utf-8"))
        invalids = []
        invalids.append({**canonical, "id": "wrong"})
        invalids.append({**canonical, "version": 2})
        invalids.append({**canonical, "version": True})
        invalids.append({**canonical, "version": 1.0})
        invalids.append({**canonical, "dimensions": canonical["dimensions"] + ["EVIDENCE"]})
        invalids.append({**canonical, "dimensions": list(reversed(canonical["dimensions"]))})
        invalids.append({**canonical, "change_types": ["UNKNOWN"]})
        invalids.append({**canonical, "default_revision_strength": "LIGHT"})
        for invalid in invalids:
            with self.subTest(invalid=invalid):
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as handle:
                    json.dump(invalid, handle, ensure_ascii=False)
                    path = Path(handle.name)
                try:
                    with self.assertRaises(ValueError):
                        load_writing_rubric(path)
                finally:
                    path.unlink()


if __name__ == "__main__":
    unittest.main()
