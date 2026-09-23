"""SSAFY GMS 를 거치는 Anthropic(`/v1/messages`) 어댑터.

Claude 는 `response_format` 이 없다. 대신 스키마를 도구 하나의 `input_schema` 로 주고
그 도구를 반드시 부르게(`tool_choice`) 하면, 도구 입력이 곧 스키마에 맞는 JSON 이다.

system 메시지는 별도 인자로 빠지고, 깊이 중첩된 배열을 문자열로 싸는 버릇은
`coerce_json_strings` 로 되돌린다.
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
from ai.llm.gms_gate import GmsRateLimitSignal, gate_for
from ai.llm.schema import coerce_json_strings, strip_unsupported_keywords

NAME = "anthropic"
_LABEL = "Anthropic"
_API_VERSION = "2023-06-01"


def build_body(
    model: str,
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
) -> dict[str, Any]:
    system = "\n\n".join(
        str(message.get("content", "")) for message in messages if message.get("role") == "system"
    )
    turns = [
        {"role": "assistant" if message.get("role") == "assistant" else "user",
         "content": str(message.get("content", ""))}
        for message in messages
        if message.get("role") != "system" and str(message.get("content", "")).strip()
    ]
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": turns,
        "tools": [{
            "name": schema_name,
            "description": "결과를 이 스키마에 맞춰 낸다.",
            "input_schema": strip_unsupported_keywords(schema),
        }],
        "tool_choice": {"type": "tool", "name": schema_name},
    }
    if system.strip():
        body["system"] = system
    return body


def complete(
    config: dict[str, str],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    timeout_seconds: int,
) -> StructuredCompletion:
    body = build_body(
        config["model"], messages, schema=schema, schema_name=schema_name, max_tokens=max_tokens,
    )
    if not body["messages"]:
        raise LlmResponseError(_LABEL, "보낼 메시지가 없습니다")
    request = urllib.request.Request(
        f"{config['base_url']}/api.anthropic.com/v1/messages",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "x-api-key": config["api_key"],
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    def transmit() -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code == 429:
                raise GmsRateLimitSignal() from error
            raise LlmHttpError(_LABEL, error.code, detail) from error
        except urllib.error.URLError as error:
            raise LlmConnectionError(_LABEL, error.reason) from error

    raw = gate_for(f"{NAME}:{config['model']}").run(transmit, operation_name=schema_name)

    tool_use = next(
        (block for block in raw.get("content", []) if isinstance(block, dict) and block.get("type") == "tool_use"),
        None,
    )
    if tool_use is None or not isinstance(tool_use.get("input"), dict):
        raise LlmResponseError(_LABEL, f"stop_reason={raw.get('stop_reason')}")
    usage = raw.get("usage") or {}
    prompt_tokens = usage.get("input_tokens")
    completion_tokens = usage.get("output_tokens")
    normalized: dict[str, int] = {}
    if isinstance(prompt_tokens, int):
        normalized["prompt_tokens"] = prompt_tokens
    if isinstance(completion_tokens, int):
        normalized["completion_tokens"] = completion_tokens
    if normalized and len(normalized) == 2:
        normalized["total_tokens"] = prompt_tokens + completion_tokens
    return {
        "model": raw.get("model", config["model"]),
        "usage": normalized,
        "output": coerce_json_strings(tool_use["input"], schema),
    }


__all__ = ["NAME", "build_body", "complete"]
