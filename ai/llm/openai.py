"""SSAFY GMS 를 거치는 OpenAI(`/chat/completions`) 어댑터.

vLLM 어댑터와 같은 OpenAI 호환 형식이지만 세 가지가 다르다.
  - 주소가 `{GMS}/api.openai.com/v1/...` 이고 키는 GMS_KEY 다.
  - gpt-5 계열은 `max_tokens` 대신 `max_completion_tokens` 를 받고 temperature 를 못 바꾼다.
  - strict 구조화 출력이 스키마를 거절하면(지원 안 하는 키워드) 비strict 로 한 번 더 보낸다.
    어느 쪽이든 결과는 파이썬 검증기가 다시 본다.
"""
from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.request

from ai.llm.contracts import (
    LlmConnectionError,
    LlmHttpError,
    LlmRateLimitedError,
    LlmResponseError,
    StructuredCompletion,
)
from ai.llm.gms_gate import GmsRateLimitSignal, gate_for
from ai.llm.schema import strip_unsupported_keywords

NAME = "openai"
_LABEL = "OpenAI"


def _uses_completion_tokens(model: str) -> bool:
    """gpt-4 계열만 예전 인자를 쓴다. 그 뒤 모델(gpt-5·o 시리즈)은 새 인자만 받는다."""
    return not model.startswith("gpt-4")


def build_body(
    model: str,
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    strict: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": strict,
                "schema": strip_unsupported_keywords(schema),
            },
        },
    }
    if _uses_completion_tokens(model):
        body["max_completion_tokens"] = max_tokens
    else:
        body["max_tokens"] = max_tokens
        body["temperature"] = 0
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
    url = f"{config['base_url']}/api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    def send(strict: bool) -> dict[str, Any]:
        body = build_body(
            config["model"], messages,
            schema=schema, schema_name=schema_name, max_tokens=max_tokens, strict=strict,
        )
        request = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST",
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

        return gate_for(f"{NAME}:{config['model']}").run(transmit, operation_name=schema_name)

    try:
        raw = send(strict=True)
    except LlmHttpError as error:
        # strict 모드는 지원하지 않는 키워드가 하나라도 있으면 400 이다. 비strict 는 스키마를
        # 안내로만 쓰므로 통과한다 — 형식은 뒤의 파이썬 검증기가 지킨다.
        if error.status != 400 or "schema" not in error.detail.lower():
            raise
        raw = send(strict=False)

    try:
        content = raw["choices"][0]["message"]["content"]
        output = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise LlmResponseError(_LABEL) from error
    return {
        "model": raw.get("model", config["model"]),
        "usage": raw.get("usage", {}),
        "output": output,
    }


__all__ = ["NAME", "build_body", "complete", "LlmRateLimitedError"]
