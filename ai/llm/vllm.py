"""사내 GPU 서버(OpenAI 호환 `/chat/completions`) 어댑터.

`ai.jd_coaching.baseline.call_qwen` 이 하던 일을 그대로 옮긴 것이다. 본문·헤더·응답 경로를
바꾸지 않았다 — 공급자 전환 작업에서 돌아가던 경로까지 손대면 무엇이 깨졌는지 알기 어렵다.
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

NAME = "vllm"
_LABEL = "Qwen"


def complete(
    config: dict[str, str],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    timeout_seconds: int,
) -> StructuredCompletion:
    body = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": dict(schema)},
        },
    }
    request = urllib.request.Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LlmHttpError(_LABEL, error.code, detail) from error
    except urllib.error.URLError as error:
        raise LlmConnectionError(_LABEL, error.reason) from error
    try:
        output = json.loads(raw["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise LlmResponseError(_LABEL) from error
    return {
        "model": raw.get("model", config["model"]),
        "usage": raw.get("usage", {}),
        "output": output,
    }
