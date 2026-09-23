"""공급자별 구조화 출력 규격에 맞춘 스키마 손질."""
from __future__ import annotations

import json
import unittest

from ai.llm.schema import coerce_json_strings, strip_unsupported_keywords

WRITING_LIKE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "writing",
    "title": "Writing",
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "revision"],
    "properties": {
        "status": {"type": "string", "enum": ["REVISED", "ANSWERED"]},
        "revision": {
            "type": ["object", "null"],
            "properties": {"changes": {"type": "array", "items": {"type": "object", "properties": {"before": {"type": "string"}}}}},
        },
    },
    "allOf": [{"if": {"properties": {"status": {"const": "REVISED"}}}, "then": {"properties": {"revision": {"type": "object"}}}}],
}


class StripUnsupportedKeywordsTest(unittest.TestCase):
    def test_drops_conditionals_and_meta_but_keeps_structure(self):
        """OpenAI·Anthropic 은 allOf/if/then 을 거절한다. 그 규칙은 파이썬 검증기가 본다."""
        stripped = strip_unsupported_keywords(WRITING_LIKE)

        self.assertNotIn("allOf", stripped)
        self.assertNotIn("$schema", stripped)
        self.assertNotIn("title", stripped)
        self.assertEqual(stripped["properties"]["status"]["enum"], ["REVISED", "ANSWERED"])
        self.assertEqual(stripped["properties"]["revision"]["type"], ["object", "null"])

    def test_does_not_mutate_input(self):
        before = json.dumps(WRITING_LIKE, sort_keys=True)
        strip_unsupported_keywords(WRITING_LIKE)
        self.assertEqual(json.dumps(WRITING_LIKE, sort_keys=True), before)


class CoerceJsonStringsTest(unittest.TestCase):
    def test_parses_stringified_array_where_schema_expects_array(self):
        """Claude 도구 호출이 중첩 배열을 문자열로 싼 경우."""
        output = {"status": "REVISED", "revision": {"changes": '[{"before": "a"}]'}}

        fixed = coerce_json_strings(output, WRITING_LIKE)

        self.assertEqual(fixed["revision"]["changes"], [{"before": "a"}])

    def test_leaves_real_strings_and_invalid_json_alone(self):
        output = {"status": "REVISED", "revision": {"changes": "not json"}}
        self.assertEqual(coerce_json_strings(output, WRITING_LIKE), output)
        self.assertEqual(coerce_json_strings("plain", {"type": "string"}), "plain")


if __name__ == "__main__":
    unittest.main()
