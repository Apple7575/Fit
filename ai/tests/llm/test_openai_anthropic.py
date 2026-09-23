"""GMS 를 거치는 OpenAI·Anthropic 어댑터."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from ai.llm import anthropic, openai
from ai.llm.contracts import LlmHttpError, LlmResponseError
from ai.llm.gms_gate import reset_gates
from ai.llm.router import complete_structured

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
    "allOf": [{"if": {"properties": {"answer": {"const": "x"}}}, "then": {}}],
}
MESSAGES = [{"role": "system", "content": "지침"}, {"role": "user", "content": "질문"}]


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(body.encode("utf-8")))


class OpenAiBodyTest(unittest.TestCase):
    def test_gpt5_uses_completion_tokens_and_no_temperature(self):
        body = openai.build_body("gpt-5.4-mini", MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=100, strict=True)
        self.assertEqual(body["max_completion_tokens"], 100)
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("temperature", body)

    def test_gpt4_keeps_legacy_arguments(self):
        body = openai.build_body("gpt-4.1-mini", MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=100, strict=True)
        self.assertEqual(body["max_tokens"], 100)
        self.assertEqual(body["temperature"], 0)

    def test_schema_is_stripped_of_conditionals(self):
        body = openai.build_body("gpt-4.1-mini", MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=1, strict=True)
        self.assertNotIn("allOf", body["response_format"]["json_schema"]["schema"])
        self.assertTrue(body["response_format"]["json_schema"]["strict"])


class OpenAiCompleteTest(unittest.TestCase):
    CONFIG = {"provider": "openai", "base_url": "https://gms.test/gmsapi", "model": "gpt-5.4-mini", "api_key": "k"}

    def setUp(self):
        reset_gates()

    def test_parses_content_and_routes_via_gms_path(self):
        payload = {"model": "gpt-5.4-mini-2026", "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                   "choices": [{"message": {"content": '{"answer": "ok"}'}}]}
        with patch("ai.llm.openai.urllib.request.urlopen", return_value=_Response(payload)) as urlopen:
            result = complete_structured(self.CONFIG, MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=50)
            request = urlopen.call_args[0][0]

        self.assertEqual(result["output"], {"answer": "ok"})
        self.assertEqual(result["model"], "gpt-5.4-mini-2026")
        self.assertEqual(request.full_url, "https://gms.test/gmsapi/api.openai.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer k")

    def test_strict_schema_rejection_falls_back_to_non_strict(self):
        """strict 는 지원하지 않는 키워드 하나에도 400 이다. 비strict 로 한 번 더 보낸다."""
        rejection = _http_error(400, '{"error":{"message":"Invalid schema for response_format: minLength not permitted"}}')
        payload = {"choices": [{"message": {"content": '{"answer": "ok"}'}}]}
        with patch("ai.llm.openai.urllib.request.urlopen", side_effect=[rejection, _Response(payload)]) as urlopen:
            result = complete_structured(self.CONFIG, MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=50)
            bodies = [json.loads(c[0][0].data.decode("utf-8")) for c in urlopen.call_args_list]

        self.assertEqual(result["output"], {"answer": "ok"})
        self.assertEqual([b["response_format"]["json_schema"]["strict"] for b in bodies], [True, False])

    def test_other_http_errors_surface(self):
        with patch("ai.llm.openai.urllib.request.urlopen", side_effect=_http_error(401, "no")):
            with self.assertRaises(LlmHttpError) as caught:
                complete_structured(self.CONFIG, MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=50)
        self.assertEqual(caught.exception.status, 401)

    def test_non_json_content_is_response_error(self):
        payload = {"choices": [{"message": {"content": "그냥 글"}}]}
        with patch("ai.llm.openai.urllib.request.urlopen", return_value=_Response(payload)):
            with self.assertRaises(LlmResponseError):
                complete_structured(self.CONFIG, MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=50)


class AnthropicBodyTest(unittest.TestCase):
    def test_system_moves_out_and_schema_becomes_forced_tool(self):
        body = anthropic.build_body("claude-haiku-4-5-20251001", MESSAGES, schema=SCHEMA, schema_name="emit", max_tokens=100)
        self.assertEqual(body["system"], "지침")
        self.assertEqual(body["messages"], [{"role": "user", "content": "질문"}])
        self.assertEqual(body["tool_choice"], {"type": "tool", "name": "emit"})
        self.assertNotIn("allOf", body["tools"][0]["input_schema"])


class AnthropicCompleteTest(unittest.TestCase):
    CONFIG = {"provider": "anthropic", "base_url": "https://gms.test/gmsapi",
              "model": "claude-haiku-4-5-20251001", "api_key": "k"}

    def setUp(self):
        reset_gates()

    def test_reads_tool_input_and_coerces_stringified_nested_json(self):
        schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object"}}}}
        payload = {"model": "claude-haiku-4-5-20251001", "stop_reason": "tool_use",
                   "usage": {"input_tokens": 5, "output_tokens": 7},
                   "content": [{"type": "text", "text": "..."},
                               {"type": "tool_use", "name": "emit", "input": {"items": '[{"a": 1}]'}}]}
        with patch("ai.llm.anthropic.urllib.request.urlopen", return_value=_Response(payload)) as urlopen:
            result = complete_structured(self.CONFIG, MESSAGES, schema=schema, schema_name="emit", max_tokens=50)
            request = urlopen.call_args[0][0]

        self.assertEqual(result["output"], {"items": [{"a": 1}]})
        self.assertEqual(result["usage"], {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12})
        self.assertEqual(request.full_url, "https://gms.test/gmsapi/api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "k")

    def test_missing_tool_use_is_response_error(self):
        payload = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "말로만 답함"}]}
        with patch("ai.llm.anthropic.urllib.request.urlopen", return_value=_Response(payload)):
            with self.assertRaises(LlmResponseError):
                complete_structured(self.CONFIG, MESSAGES, schema=SCHEMA, schema_name="emit", max_tokens=50)


class GeminiThinkingBudgetTest(unittest.TestCase):
    """gemini-2.5-flash 는 생각 토큰이 출력 한도를 먹어 JSON 이 끊긴다. flash(비 lite)에만 끈다."""

    def _body_for(self, model: str) -> dict:
        payload = {"candidates": [{"content": {"parts": [{"text": '{"answer": "x"}'}]}}]}
        config = {"provider": "gms", "base_url": "https://gms.test/gmsapi", "model": model, "api_key": "k"}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            complete_structured(config, MESSAGES, schema=SCHEMA, schema_name="s", max_tokens=10)
            request = opener.return_value.open.call_args[0][0]
        return json.loads(request.data.decode("utf-8"))

    def setUp(self):
        reset_gates()

    def test_flash_disables_thinking_but_lite_does_not(self):
        self.assertEqual(self._body_for("gemini-2.5-flash")["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})
        self.assertNotIn("thinkingConfig", self._body_for("gemini-2.5-flash-lite")["generationConfig"])


class GateRegistryTest(unittest.TestCase):
    def test_gates_are_per_model(self):
        from ai.llm.gms_gate import gate_for
        reset_gates()
        self.assertIs(gate_for("gms:a"), gate_for("gms:a"))
        self.assertIsNot(gate_for("gms:a"), gate_for("openai:b"))


if __name__ == "__main__":
    unittest.main()
