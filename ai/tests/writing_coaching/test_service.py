import json
import unittest
from typing import Any

from ai.writing_coaching.contracts import WritingMessageRequest
from ai.writing_coaching.service import WritingService


CONFIG = {"model": "qwen-test"}
REQUEST = WritingMessageRequest.model_validate({
    "message": "두괄식으로 고쳐줘",
    "question": "협업 경험을 작성해 주세요.",
    "draft": "API를 개선했습니다.",
    "char_limit": 700,
    "feedback": [],
    "conversation": [],
})


def valid_revised_output(
    *, revised_text: str = "API를 개선했습니다.", char_count: int = 1
) -> dict[str, Any]:
    return {
        "status": "REVISED",
        "message": "수정했습니다.",
        "revision": {
            "revision_strength": "BALANCED",
            "revised_text": revised_text,
            "char_count": char_count,
            "changes": [],
            "warnings": [],
        },
    }


class FakeQwenCaller:
    def __init__(self, outputs: list[Any]) -> None:
        self._outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append({"config": config, "messages": messages, **kwargs})
        output = self._outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return {"output": output}


class WritingServiceTest(unittest.TestCase):
    def test_returns_validated_revision_with_server_char_count(self):
        caller = FakeQwenCaller([valid_revised_output(char_count=999)])

        result = WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)

        self.assertEqual(result.status, "REVISED")
        self.assertIsNotNone(result.revision)
        self.assertEqual(
            result.revision.char_count, len(result.revision.revised_text)
        )
        self.assertEqual(caller.calls[0]["timeout_seconds"], 45)
        self.assertEqual(caller.calls[0]["schema_name"], "writing_message_v1")
        self.assertIsInstance(caller.calls[0]["schema"], dict)

    def test_retries_one_validation_failure_with_error_context(self):
        caller = FakeQwenCaller([
            valid_revised_output(revised_text="원문에 없는 90% 성과"),
            valid_revised_output(revised_text="API를 개선했습니다."),
        ])

        result = WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)

        self.assertEqual(result.status, "REVISED")
        self.assertEqual(len(caller.calls), 2)
        retry_payload = json.loads(caller.calls[1]["messages"][1]["content"])
        self.assertIn("previous_validation_error", retry_payload)

    def test_accepts_answered_and_clarification_without_revision(self):
        for status in ("ANSWERED", "CLARIFICATION_REQUIRED"):
            with self.subTest(status=status):
                caller = FakeQwenCaller([{
                    "status": status,
                    "message": "설명입니다.",
                    "revision": None,
                }])

                result = WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)

                self.assertEqual(result.status, status)
                self.assertIsNone(result.revision)
                self.assertEqual(len(caller.calls), 1)

    def test_raises_after_second_invalid_output(self):
        caller = FakeQwenCaller([
            valid_revised_output(revised_text="원문에 없는 90% 성과"),
            valid_revised_output(revised_text="또 다른 80% 성과"),
        ])

        with self.assertRaisesRegex(
            RuntimeError, "^writing response validation failed$"
        ):
            WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)
        self.assertEqual(len(caller.calls), 2)

    def test_preserves_operational_qwen_error_as_cause_without_retry(self):
        error = RuntimeError("Qwen unavailable")
        caller = FakeQwenCaller([error])

        with self.assertRaisesRegex(
            RuntimeError, "^writing provider request failed$"
        ) as caught:
            WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(len(caller.calls), 1)

    def test_preserves_qwen_json_parse_value_error_as_cause_without_retry(self):
        error = ValueError("Qwen response does not contain valid JSON")
        caller = FakeQwenCaller([error])

        with self.assertRaisesRegex(
            RuntimeError, "^writing provider request failed$"
        ) as caught:
            WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(len(caller.calls), 1)


if __name__ == "__main__":
    unittest.main()
