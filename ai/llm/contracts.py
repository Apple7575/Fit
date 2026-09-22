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


# --- 할당량 오류를 사용자에게 알리기 ------------------------------------------------
# GMS 를 거친 Gemini 가 429 를 주면(분당·일일 할당량) 재시도해도 같은 답이 온다. 담당이 조용히
# "답을 만들지 못했습니다" 로 끝나면 사용자는 자소서 탓인지 서버 탓인지 모른다. 코드로 표시하고
# 화면에 그대로 띄울 한 문장을 여기서 한 번만 정한다.
QUOTA_ERROR_CODE = "LLM_QUOTA_EXCEEDED"
QUOTA_USER_MESSAGE = "AI 요청 한도에 잠시 걸렸습니다. 1분쯤 뒤에 다시 시도해 주세요."


def find_quota_error(error: BaseException | None) -> LlmHttpError | None:
    """예외 사슬(__cause__·__context__)을 따라가 429 를 찾는다. 담당들이 LLM 오류를 감싸 올리기 때문이다."""
    seen: set[int] = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, LlmHttpError) and current.status == 429:
            return current
        current = current.__cause__ or current.__context__
    return None
