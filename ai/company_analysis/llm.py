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

from ai.llm import LlmConnectionError, LlmHttpError, LlmResponseError, complete_structured
from ai.llm.config import GMS, VLLM, load_llm_config


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
    """LLM 접속 설정. 이름은 Qwen 이지만 `provider` 가 gms 면 GMS 설정이 담긴다."""

    base_url: str
    model: str
    api_key: str
    timeout_seconds: int = 180
    provider: str = VLLM

    @classmethod
    def from_env_file(cls, path: Path, *, timeout_seconds: int = 180) -> "QwenConfig":
        """`LLM_PROVIDER`(또는 `COMPANY_ANALYSIS_LLM_PROVIDER`)에 맞는 설정을 읽는다."""
        try:
            config = load_llm_config(path, prefix="COMPANY_ANALYSIS")
        except ValueError as error:
            # 이 모듈의 호출부는 설정 누락을 RuntimeError 로 잡는다(api.py 의 503 변환).
            raise RuntimeError(str(error)) from error
        return cls(
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key,
            timeout_seconds=timeout_seconds,
            provider=config.provider,
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


class GmsStructuredClient:
    """GMS(Gemini) 로 나가는 같은 모양의 클라이언트.

    `QwenStructuredClient` 와 달리 transport 를 주입받지 않는다. 요청·응답 변환이 `ai.llm.gms`
    에 있어 여기서는 오류 종류만 이 모듈의 것으로 옮긴다 — 서비스 코드가 잡는 예외가 공급자에
    따라 달라지면 안 된다.
    """

    def __init__(self, config: QwenConfig) -> None:
        self._config = config
        self.last_usage: dict[str, int] | None = None

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
        try:
            result = complete_structured(
                self._config.__dict__ | {"provider": GMS},
                messages,
                schema=schema,
                schema_name="company_analysis_output",
                max_tokens=max_tokens,
                timeout_seconds=self._config.timeout_seconds,
            )
        except LlmConnectionError as error:
            reason = getattr(error, "__cause__", None)
            if isinstance(getattr(reason, "reason", None), (TimeoutError, socket.timeout)):
                raise ModelTimeoutError("GMS 응답 시간이 초과되었습니다") from error
            raise ModelUpstreamError("GMS 호출 실패") from error
        except LlmHttpError as error:
            raise ModelUpstreamError(f"GMS 호출 실패: http_status={error.status}") from error
        except LlmResponseError as error:
            raise InvalidModelResponse(str(error)) from error
        except (TimeoutError, socket.timeout) as error:
            raise ModelTimeoutError("GMS 응답 시간이 초과되었습니다") from error

        usage = result.get("usage")
        self.last_usage = (
            {k: int(v) for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
            if isinstance(usage, dict)
            else None
        )
        return result["output"]


def build_structured_client(config: QwenConfig) -> StructuredCompletionClient:
    """설정이 가리키는 공급자의 클라이언트를 만든다. 호출부는 어느 쪽인지 몰라도 된다."""
    if config.provider == GMS:
        return GmsStructuredClient(config)
    return QwenStructuredClient(config)

