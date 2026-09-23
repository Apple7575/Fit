"""GMS 어댑터 — 스키마·메시지 변환과 응답 해석."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from ai.llm import complete_structured
from ai.llm.contracts import LlmHttpError, LlmResponseError
from ai.llm.gms import GmsRateLimitSignal, to_gemini_contents, to_gemini_schema


class ToGeminiSchemaTest(unittest.TestCase):
    def test_types_become_uppercase(self):
        converted = to_gemini_schema({
            "type": "object",
            "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["name"],
        })

        self.assertEqual(converted["type"], "OBJECT")
        self.assertEqual(converted["properties"]["name"]["type"], "STRING")
        self.assertEqual(converted["properties"]["count"]["type"], "INTEGER")
        self.assertEqual(converted["required"], ["name"])

    def test_drops_keywords_gemini_does_not_know(self):
        """additionalProperties 를 그대로 보내면 400 이 온다."""
        converted = to_gemini_schema({
            "type": "object",
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#",
            "properties": {"name": {"type": "string", "additionalProperties": False}},
        })

        self.assertNotIn("additionalProperties", converted)
        self.assertNotIn("$schema", converted)
        self.assertNotIn("additionalProperties", converted["properties"]["name"])

    def test_array_bounds_survive(self):
        """떨구면 담당들의 "1~3개" 제약이 사라져 모델이 넘게 낸다 — JD 구조화가 이걸로 깨졌다."""
        converted = to_gemini_schema({
            "type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"},
        })

        self.assertEqual(converted["minItems"], 1)
        self.assertEqual(converted["maxItems"], 3)

    def test_nullable_type_array_becomes_nullable_flag(self):
        converted = to_gemini_schema({"type": ["string", "null"]})

        self.assertEqual(converted["type"], "STRING")
        self.assertTrue(converted["nullable"])

    def test_nested_arrays_are_converted(self):
        converted = to_gemini_schema({
            "type": "array",
            "items": {"type": "object", "properties": {"text": {"type": "string"}}},
        })

        self.assertEqual(converted["type"], "ARRAY")
        self.assertEqual(converted["items"]["type"], "OBJECT")
        self.assertEqual(converted["items"]["properties"]["text"]["type"], "STRING")

    def test_any_of_with_null_becomes_nullable(self):
        converted = to_gemini_schema({"anyOf": [{"type": "string"}, {"type": "null"}]})

        self.assertEqual(converted["type"], "STRING")
        self.assertTrue(converted["nullable"])

    def test_enum_and_description_survive(self):
        converted = to_gemini_schema({
            "type": "string", "enum": ["A", "B"], "description": "고른다",
        })

        self.assertEqual(converted["enum"], ["A", "B"])
        self.assertEqual(converted["description"], "고른다")


class ToGeminiContentsTest(unittest.TestCase):
    def test_system_messages_merge_into_system_instruction(self):
        system, contents = to_gemini_contents([
            {"role": "system", "content": "너는 분석가다."},
            {"role": "system", "content": "한국어로 답해라."},
            {"role": "user", "content": "매출은?"},
        ])

        self.assertEqual(system["parts"][0]["text"], "너는 분석가다.\n\n한국어로 답해라.")
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "user")

    def test_assistant_becomes_model(self):
        _, contents = to_gemini_contents([
            {"role": "user", "content": "매출은?"},
            {"role": "assistant", "content": "186조원입니다."},
            {"role": "user", "content": "작년은?"},
        ])

        self.assertEqual([item["role"] for item in contents], ["user", "model", "user"])

    def test_blank_messages_are_dropped(self):
        system, contents = to_gemini_contents([
            {"role": "system", "content": "   "},
            {"role": "user", "content": "매출은?"},
        ])

        self.assertIsNone(system)
        self.assertEqual(len(contents), 1)


class GmsCompleteTest(unittest.TestCase):
    CONFIG = {
        "provider": "gms",
        "base_url": "https://gms.example/gmsapi",
        "model": "gemini-2.5-flash-lite",
        "api_key": "key",
    }
    SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}

    def test_reads_answer_and_normalises_usage(self):
        """토큰 이름을 vLLM 쪽에 맞춘다 — 사용량을 쓰는 곳이 한 가지만 알면 된다."""
        payload = {
            "candidates": [{"content": {"parts": [{"text": '{"answer": "186조원"}'}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14},
            "modelVersion": "gemini-2.5-flash-lite-001",
        }
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            result = complete_structured(
                self.CONFIG, [{"role": "user", "content": "매출은?"}],
                schema=self.SCHEMA, schema_name="x", max_tokens=100,
            )

        self.assertEqual(result["output"], {"answer": "186조원"})
        self.assertEqual(result["model"], "gemini-2.5-flash-lite-001")
        self.assertEqual(result["usage"], {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})

    def test_sends_converted_schema_and_key_header(self):
        payload = {"candidates": [{"content": {"parts": [{"text": '{"answer": "x"}'}]}}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            complete_structured(
                self.CONFIG, [{"role": "system", "content": "지침"}, {"role": "user", "content": "매출은?"}],
                schema={"type": "object", "additionalProperties": False, "properties": {}},
                schema_name="x", max_tokens=100,
            )
            request = opener.return_value.open.call_args[0][0]

        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["generationConfig"]["responseSchema"]["type"], "OBJECT")
        self.assertNotIn("additionalProperties", body["generationConfig"]["responseSchema"])
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "지침")
        self.assertEqual(request.headers["X-goog-api-key"], "key")
        self.assertTrue(request.full_url.endswith(":generateContent"))

    def test_retries_without_array_bounds_when_schema_is_too_complex(self):
        """중첩 배열에 길이가 붙으면 Gemini 가 400 을 준다. 제약을 빼고 한 번 더 보낸다."""
        bounded = {
            "type": "object",
            "properties": {"items": {"type": "array", "maxItems": 12, "items": {"type": "string"}}},
        }
        ok = {"candidates": [{"content": {"parts": [{"text": '{"items": []}'}]}}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = [
                _HttpError(400, '{"error":{"message":"The specified schema produces a constraint that has too many states for serving."}}'),
                _Response(ok),
            ]
            result = complete_structured(
                self.CONFIG, [{"role": "user", "content": "x"}],
                schema=bounded, schema_name="x", max_tokens=100,
            )
            second = opener.return_value.open.call_args_list[1][0][0]

        self.assertEqual(result["output"], {"items": []})
        body = json.loads(second.data.decode("utf-8"))
        self.assertNotIn("maxItems", json.dumps(body["generationConfig"]["responseSchema"]))

    def test_other_http_errors_are_not_retried(self):
        """키가 틀렸을 때까지 두 번 부르면 원인이 가려진다."""
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = _HttpError(401, "unauthorized")
            with self.assertRaises(LlmHttpError):
                complete_structured(
                    self.CONFIG, [{"role": "user", "content": "x"}],
                    schema=self.SCHEMA, schema_name="x", max_tokens=100,
                )

        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_429_is_retried_through_request_gate(self):
        ok = {"candidates": [{"content": {"parts": [{"text": '{"answer": "ok"}'}]}}]}
        with (
            patch("ai.llm.gms.urllib.request.build_opener") as opener,
            patch("ai.llm.gms._get_gate", return_value=_RetryingGate()) as get_gate,
        ):
            opener.return_value.open.side_effect = [
                _HttpError(429, "busy", {"Retry-After": "7"}),
                _Response(ok),
            ]
            result = complete_structured(
                self.CONFIG, [{"role": "user", "content": "x"}],
                schema=self.SCHEMA, schema_name="x", max_tokens=100,
            )

        self.assertEqual(result["output"], {"answer": "ok"})
        self.assertEqual(opener.return_value.open.call_count, 2)
        self.assertEqual(get_gate.return_value.rate_limits, [7.0])

    def test_safety_block_reports_finish_reason(self):
        """안전 필터에 걸리면 parts 가 없다. 원인을 남겨야 추적된다."""
        payload = {"candidates": [{"finishReason": "SAFETY"}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            with self.assertRaises(LlmResponseError) as caught:
                complete_structured(
                    self.CONFIG, [{"role": "user", "content": "x"}],
                    schema=self.SCHEMA, schema_name="x", max_tokens=100,
                )

        self.assertIn("SAFETY", str(caught.exception))


class _HttpError(urllib.error.HTTPError):
    def __init__(self, code: int, body: str, headers: dict[str, str] | None = None) -> None:
        super().__init__("https://gms.example", code, "err", headers or {}, io.BytesIO(body.encode("utf-8")))


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _RetryingGate:
    def __init__(self) -> None:
        self.rate_limits: list[float | None] = []

    def run(self, operation, *, operation_name):
        try:
            return operation()
        except GmsRateLimitSignal as error:
            self.rate_limits.append(error.retry_after_seconds)
            return operation()


if __name__ == "__main__":
    unittest.main()
