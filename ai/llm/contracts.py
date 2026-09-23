"""공급자가 공유하는 결과 모양과 오류 종류."""
from __future__ import annotations

from typing import Any, Protocol, TypedDict


class StructuredCompletion(TypedDict):
    """공급자가 무엇이든 호출부가 받는 것은 이 셋이다."""

    model: str
    usage: dict[str, Any]
    output: dict[str, Any]


class LlmError(RuntimeError):
    """LLM 호출 실패의 공통 조상. 호출부는 대개 이것만 잡으면 된다."""


class LlmHttpError(LlmError):
    """서버가 2xx 가 아닌 응답을 줬다. 키·할당량·모델 이름 문제가 여기로 온다."""

    def __init__(self, provider: str, status: int, detail: str) -> None:
        super().__init__(f"{provider} API HTTP {status}: {detail}")
        self.provider = provider
        self.status = status
        self.detail = detail


class LlmRateLimitedError(LlmError):
    """공급자가 호출 한도를 넘겼거나 게이트 대기 시간이 만료됐다."""

    def __init__(self, provider: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(f"{provider} rate limit exceeded")
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds


class LlmConnectionError(LlmError):
    """서버에 닿지 못했다. GPU 서버가 죽어 있을 때 주로 온다."""

    def __init__(self, provider: str, reason: object) -> None:
        super().__init__(f"{provider} API connection failed: {reason}")
        self.provider = provider


class LlmResponseError(ValueError):
    """응답은 왔는데 스키마에 맞는 JSON 을 꺼낼 수 없다.

    ValueError 를 물려받는다 — 기존 호출부가 이 경우를 ValueError 로 잡고 있어서,
    공급자를 바꿨다고 그 처리가 조용히 빠지면 안 된다.
    """

    def __init__(self, provider: str, reason: str = "") -> None:
        message = f"{provider} response does not contain valid JSON"
        super().__init__(f"{message}: {reason}" if reason else message)
        self.provider = provider


class StructuredClient(Protocol):
    """공급자 어댑터가 지켜야 할 모양."""

    name: str

    def complete(
        self,
        config: Any,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int,
        timeout_seconds: int,
    ) -> StructuredCompletion: ...
