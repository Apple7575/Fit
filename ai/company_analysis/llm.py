"""GPU 서버의 OpenAI 호환 Qwen 에 JSON 스키마 출력을 요청하는 얇은 클라이언트.

설정은 ai/.env 의 QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY 를 다른 담당과 똑같이 쓴다.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ModelTimeoutError(RuntimeError):
    pass


class ModelUpstreamError(RuntimeError):
    pass


class InvalidModelResponse(ValueError):
    pass


class StructuredCompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, max_tokens: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class QwenConfig:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int = 180

    @classmethod
    def from_env_file(cls, path: Path, *, timeout_seconds: int = 180) -> "QwenConfig":
        values: dict[str, str] = {}
        if path.exists():
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
        import os

        resolved = {key: os.environ.get(key, "").strip() or values.get(key, "") for key in ("QWEN_BASE_URL", "QWEN_MODEL", "QWEN_API_KEY")}
        missing = [key for key, value in resolved.items() if not value]
        if missing:
            raise RuntimeError(f"Qwen 설정이 비어 있습니다: {', '.join(missing)}")
        return cls(
            base_url=resolved["QWEN_BASE_URL"].rstrip("/"),
            model=resolved["QWEN_MODEL"],
            api_key=resolved["QWEN_API_KEY"],
            timeout_seconds=timeout_seconds,
        )


Transport = Callable[[urllib.request.Request, int], dict[str, Any]]


def _default_transport(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (TimeoutError, socket.timeout) as error:
        raise ModelTimeoutError("Qwen 응답 시간이 초과되었습니다") from error
    except urllib.error.HTTPError as error:
        raise ModelUpstreamError(f"Qwen 호출 실패: http_status={error.code}") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise ModelTimeoutError("Qwen 응답 시간이 초과되었습니다") from error
        raise ModelUpstreamError(f"Qwen 호출 실패: reason_type={type(error.reason).__name__}") from error
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidModelResponse(f"Qwen HTTP 응답 JSON 파싱 실패: body_length={len(body)}") from error


class QwenStructuredClient:
    def __init__(self, config: QwenConfig, *, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or _default_transport
        self.last_usage: dict[str, int] | None = None

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
        body = {
            "model": self._config.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "company_analysis_output", "strict": True, "schema": schema},
            },
        }
        request = urllib.request.Request(
            f"{self._config.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._config.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        payload = self._transport(request, self._config.timeout_seconds)
        usage = payload.get("usage") if isinstance(payload, dict) else None
        self.last_usage = (
            {k: int(v) for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
            if isinstance(usage, dict)
            else None
        )
        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise InvalidModelResponse("Qwen 응답 구조에서 content 를 찾을 수 없습니다") from error
        try:
            output = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise InvalidModelResponse(
                f"Qwen JSON 파싱 실패: finish_reason={choice.get('finish_reason', 'missing')} "
                f"content_length={len(content) if isinstance(content, str) else -1}"
            ) from error
        if not isinstance(output, dict):
            raise InvalidModelResponse("Qwen JSON 결과는 객체여야 합니다")
        return output
