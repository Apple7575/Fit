"""설정의 `provider` 를 보고 어댑터를 고른다."""
from __future__ import annotations

from typing import Any, Mapping

from ai.llm import anthropic, gms, openai, vllm
from ai.llm.config import ANTHROPIC, DEFAULT_PROVIDER, GMS, OPENAI, PROVIDERS, VLLM
from ai.llm.contracts import StructuredCompletion

_ADAPTERS = {
    VLLM: vllm.complete,
    GMS: gms.complete,
    OPENAI: openai.complete,
    ANTHROPIC: anthropic.complete,
}


def complete_structured(
    config: Mapping[str, str],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int = 4096,
    timeout_seconds: int = 180,
) -> StructuredCompletion:
    """스키마에 맞는 JSON 출력을 받는다.

    `config` 에 `provider` 가 없으면 vLLM 으로 본다. 공급자 계층이 들어오기 전부터 있던
    호출부가 `{base_url, model, api_key}` 만 넘기기 때문이다 — 그 코드가 계속 돌아야 한다.
    """
    provider = str(config.get("provider") or DEFAULT_PROVIDER).lower()
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        raise ValueError(
            f"지원하지 않는 LLM 공급자입니다: {provider} ({', '.join(PROVIDERS)} 중 하나)"
        )
    return adapter(
        dict(config),
        messages,
        schema=schema,
        schema_name=schema_name,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
