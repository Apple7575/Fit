"""SSAFY GMS 경유 Gemini(`:generateContent`) 어댑터.

vLLM 과 주고받는 모양이 전부 다르다. 그 차이를 여기서 흡수해 바깥에는 같은 dict 를 돌려준다.

| | vLLM | GMS |
| --- | --- | --- |
| 인증 | `Authorization: Bearer` | `x-goog-api-key` |
| 대화 | `messages[{role, content}]` | `systemInstruction` + `contents[{role, parts}]` |
| 구조화 출력 | `response_format.json_schema` | `generationConfig.responseSchema` |
| 답 꺼내기 | `choices[0].message.content` | `candidates[0].content.parts[0].text` |

스키마도 그대로 넘기지 못한다. Gemini 는 타입을 대문자로 쓰고 `additionalProperties` 같은
JSON Schema 키워드를 모른다 — 그대로 보내면 400 이 온다. `to_gemini_schema` 가 옮긴다.
"""
from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.request

from ai.llm.contracts import (
    LlmConnectionError,
    LlmHttpError,
    LlmResponseError,
    StructuredCompletion,
)

NAME = "gms"
_LABEL = "GMS"

# Gemini responseSchema 가 아는 키만 남긴다. 나머지는 보내면 400 이다.
_KEPT_KEYS = frozenset({
    "type", "format", "description", "nullable", "enum", "items", "properties", "required",
    # 배열 길이는 Gemini 도 지킨다. 떨구면 담당들의 "1~3개" 같은 제약이 사라져 모델이 넘게 낸다.
    "minItems", "maxItems",
})
_TYPES = {
    "object": "OBJECT",
    "array": "ARRAY",
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
}


class _NoRedirectOpener(urllib.request.HTTPRedirectHandler):
    """인증 헤더(x-goog-api-key)가 다른 호스트로 새지 않도록 리다이렉트를 막는다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def to_gemini_schema(schema: Any) -> Any:
    """JSON Schema → Gemini responseSchema.

    타입을 대문자로 올리고, Gemini 가 모르는 키워드를 떨군다. `["string", "null"]` 처럼 타입을
    배열로 쓴 곳은 첫 타입 + `nullable` 로 옮긴다 — 담당들의 스키마가 선택 필드를 이렇게 쓴다.
    """
    if isinstance(schema, list):
        return [to_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        concrete = [item for item in raw_type if item != "null"]
        if concrete:
            out["type"] = _TYPES.get(concrete[0], str(concrete[0]).upper())
        if "null" in raw_type:
            out["nullable"] = True
    elif isinstance(raw_type, str):
        out["type"] = _TYPES.get(raw_type, raw_type.upper())

    for key, value in schema.items():
        if key == "type" or key not in _KEPT_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            out["properties"] = {name: to_gemini_schema(item) for name, item in value.items()}
        elif key == "items":
            out["items"] = to_gemini_schema(value)
        else:
            out[key] = value

    # anyOf/oneOf 로 null 을 표현한 스키마도 있다. Gemini 는 모르므로 첫 갈래만 쓰고 nullable 로 둔다.
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and branches:
            concrete = [b for b in branches if not (isinstance(b, dict) and b.get("type") == "null")]
            chosen = to_gemini_schema(concrete[0] if concrete else branches[0])
            if isinstance(chosen, dict):
                merged = {**chosen, **out}
                if len(concrete) != len(branches):
                    merged["nullable"] = True
                return merged
    return out


def to_gemini_contents(messages: list[dict[str, str]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """OpenAI messages → (systemInstruction, contents).

    system 은 여러 개가 와도 하나로 합친다. Gemini 는 systemInstruction 을 하나만 받는다.
    assistant 는 Gemini 에서 `model` 이다.
    """
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user")).lower()
        content = str(message.get("content", ""))
        if not content.strip():
            continue
        if role == "system":
            system_parts.append(content)
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}],
        })
    system = {"parts": [{"text": "\n\n".join(system_parts)}]} if system_parts else None
    return system, contents


def complete(
    config: dict[str, str],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    timeout_seconds: int,
) -> StructuredCompletion:
    system, contents = to_gemini_contents(messages)
    if not contents:
        raise LlmResponseError(_LABEL, "보낼 메시지가 없습니다")

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": to_gemini_schema(schema),
            "temperature": 0,
            "maxOutputTokens": max_tokens,
        },
    }
    if system is not None:
        body["systemInstruction"] = system

    url = (
        f"{config['base_url']}/generativelanguage.googleapis.com/v1beta/models/"
        f"{config['model']}:generateContent"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": config["api_key"]},
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirectOpener())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LlmHttpError(_LABEL, error.code, detail) from error
    except urllib.error.URLError as error:
        raise LlmConnectionError(_LABEL, error.reason) from error

    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        output = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        # 안전 필터에 걸리면 candidates 가 비고 finishReason 만 온다. 원인을 남겨야 추적된다.
        reason = ""
        candidates = raw.get("candidates") or []
        if candidates and isinstance(candidates[0], dict):
            reason = str(candidates[0].get("finishReason", ""))
        elif raw.get("promptFeedback"):
            reason = str(raw["promptFeedback"])
        raise LlmResponseError(_LABEL, reason) from error
    if not isinstance(output, dict):
        raise LlmResponseError(_LABEL, "최상위가 객체가 아닙니다")

    usage = raw.get("usageMetadata") or {}
    return {
        "model": raw.get("modelVersion", config["model"]),
        # 토큰 이름을 vLLM 쪽에 맞춘다. 사용량을 기록하는 곳이 한 가지만 알면 되게 한다.
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
        "output": output,
    }
