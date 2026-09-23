"""JSON Schema 를 공급자별 구조화 출력 규격에 맞게 다듬는다.

담당들의 스키마는 JSON Schema 초안 표준을 그대로 쓴다 — `allOf/if/then` 으로 "status 가
REVISED 일 때만 revision 이 있다" 같은 교차 필드 규칙까지 적는다. OpenAI 와 Anthropic 의
구조화 출력은 그런 조건문을 받지 않는다. 그 규칙은 어차피 파이썬 검증기가 다시 보므로,
전송용 스키마에서만 떼어 낸다.
"""
from __future__ import annotations

import json
from typing import Any

# 구조화 출력 API 가 거절하는 메타·조건문 키. 검증은 파이썬 쪽(pydantic·validate_*)이 맡는다.
_DROP_KEYS = frozenset({"$schema", "$id", "title", "allOf", "if", "then", "else"})


def strip_unsupported_keywords(schema: Any) -> Any:
    """조건문·메타 키를 뗀 사본을 돌려준다. 원본은 건드리지 않는다."""
    if isinstance(schema, dict):
        return {
            key: strip_unsupported_keywords(value)
            for key, value in schema.items()
            if key not in _DROP_KEYS
        }
    if isinstance(schema, list):
        return [strip_unsupported_keywords(item) for item in schema]
    return schema


def coerce_json_strings(value: Any, schema: Any) -> Any:
    """스키마가 배열·객체를 기대하는 자리에 JSON 문자열이 오면 파싱해 되돌린다.

    Claude 의 도구 호출은 깊이 중첩된 배열을 가끔 `"[{...}]"` 처럼 문자열로 싼다. 그대로
    두면 검증기가 `'str' object has no attribute 'get'` 로 넘어진다.
    """
    if not isinstance(schema, dict):
        return value
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected]
    if isinstance(value, str) and ("array" in types or "object" in types):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    properties = schema.get("properties")
    if isinstance(value, dict) and isinstance(properties, dict):
        return {
            key: coerce_json_strings(item, properties.get(key, {}))
            for key, item in value.items()
        }
    items = schema.get("items")
    if isinstance(value, list) and isinstance(items, dict):
        return [coerce_json_strings(item, items) for item in value]
    return value
