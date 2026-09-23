"""LLM 설정을 환경변수와 .env 에서 읽는다.

담당마다 다른 모델을 쓴다. 한 모델(gemini-2.5-flash-lite)에 검토 방 한 턴의 호출 15건과
면접 기능까지 몰려 Google 할당량이 소진되던 것을, 공급자 셋(OpenAI·Google·Anthropic)의
여러 모델로 나눈 것이다(2026-09-23). 기본 배정은 `AGENT_DEFAULTS` 에 있고, 형식 검증을
통과한 모델만 적었다.

손잡이는 세 층이다. 위가 아래를 덮어쓴다.

    <PREFIX>_LLM_PROVIDER / <PREFIX>_LLM_MODEL   담당 하나만 바꿀 때 (예: WRITING_LLM_MODEL)
    AGENT_DEFAULTS[prefix]                         코드에 적힌 담당별 기본 배정
    LLM_PROVIDER / GMS_MODEL / QWEN_MODEL          접두사가 없거나 기본 배정이 없는 호출부

OpenAI·Anthropic 모델도 SSAFY GMS 를 거쳐 부르므로 키는 `GMS_KEY` 하나다.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

VLLM = "vllm"
GMS = "gms"
OPENAI = "openai"
ANTHROPIC = "anthropic"
PROVIDERS = (VLLM, GMS, OPENAI, ANTHROPIC)
# GMS 프록시를 거치는 공급자. 모두 GMS_KEY 로 인증한다.
GMS_PROXIED = (GMS, OPENAI, ANTHROPIC)

DEFAULT_PROVIDER = VLLM
DEFAULT_GMS_BASE_URL = "https://gms.ssafy.io/gmsapi"
DEFAULT_GMS_MODEL = "gemini-2.5-flash-lite"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# 담당별 기본 배정. (공급자, 모델). 2026-09-23 형식 검증(실제 프롬프트 + 파이썬 검증기) 통과분.
#   JD                    항목별 병렬 호출로 양이 가장 많다 → 싸고 빠른 모델
#   POSITION              인용 위치·요소 검증이 엄격하다 → 2초에 통과한 모델
#   WRITING               한국어 문장 품질. Google 이지만 flash-lite 와 별도 할당량
#   SUPERVISOR_PLAN       담당 고르기 한 번 → 가장 가벼운 모델
#   SUPERVISOR_AGGREGATE  판단 품질이 중요. gpt-4.1-mini 는 없는 근거 id 를 지어내 탈락
#   COMPANY_ANALYSIS      긴 문맥. flash-lite 에는 이 담당만 남긴다
#   NEWS                  폐지 예정. 기존 값 유지
AGENT_DEFAULTS: dict[str, tuple[str, str]] = {
    "JD": (OPENAI, "gpt-4.1-mini"),
    "POSITION": (OPENAI, "gpt-5.4-mini"),
    "WRITING": (GMS, "gemini-2.5-flash"),
    "SUPERVISOR_PLAN": (OPENAI, "gpt-5.4-nano"),
    "SUPERVISOR_AGGREGATE": (ANTHROPIC, "claude-haiku-4-5-20251001"),
    "COMPANY_ANALYSIS": (GMS, "gemini-2.5-flash-lite"),
    "NEWS": (GMS, "gemini-2.5-flash-lite"),
}


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    base_url: str
    model: str
    api_key: str

    def as_dict(self) -> dict[str, str]:
        """기존 호출부가 넘기던 dict 모양. `call_qwen(config, ...)` 가 이것을 받는다."""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
        }


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _value(key: str, values: dict[str, str]) -> str:
    """환경변수가 먼저다. 컨테이너는 compose 로 주입하고 .env 는 개발 PC 용이다."""
    return os.environ.get(key, values.get(key, "")).strip()


def _check_provider(chosen: str) -> str:
    if chosen not in PROVIDERS:
        raise ValueError(
            f"지원하지 않는 LLM 공급자입니다: {chosen} ({', '.join(PROVIDERS)} 중 하나)"
        )
    return chosen


def resolve_provider(values: dict[str, str] | None = None, *, prefix: str = "") -> str:
    """쓸 공급자를 정한다. 담당별 덮어쓰기 > 담당별 기본 배정 > 전역 설정 > vllm."""
    values = values or {}
    if prefix:
        chosen = _value(f"{prefix}_LLM_PROVIDER", values).lower()
        if chosen:
            return _check_provider(chosen)
        if prefix in AGENT_DEFAULTS:
            return AGENT_DEFAULTS[prefix][0]
    chosen = _value("LLM_PROVIDER", values).lower()
    if chosen:
        return _check_provider(chosen)
    return DEFAULT_PROVIDER


def resolve_model(provider: str, values: dict[str, str] | None = None, *, prefix: str = "") -> str:
    """쓸 모델을 정한다. 담당별 덮어쓰기 > (공급자가 같을 때) 담당별 기본 배정 > 공급자 기본값."""
    values = values or {}
    if prefix:
        chosen = _value(f"{prefix}_LLM_MODEL", values)
        if chosen:
            return chosen
        default = AGENT_DEFAULTS.get(prefix)
        if default is not None and default[0] == provider:
            return default[1]
    if provider == VLLM:
        return _value("QWEN_MODEL", values)
    if provider == GMS:
        return _value("GMS_MODEL", values) or DEFAULT_GMS_MODEL
    if provider == OPENAI:
        return _value("OPENAI_MODEL", values) or DEFAULT_OPENAI_MODEL
    return _value("ANTHROPIC_MODEL", values) or DEFAULT_ANTHROPIC_MODEL


def load_llm_config(path: Path, *, prefix: str = "") -> LlmConfig:
    """공급자에 맞는 주소·모델·키를 모은다. 없으면 무엇이 빠졌는지 알리고 멈춘다."""
    values = read_env_file(path)
    provider = resolve_provider(values, prefix=prefix)
    model = resolve_model(provider, values, prefix=prefix)
    if provider in GMS_PROXIED:
        return _gms_proxied_config(provider, model, values)
    return _vllm_config(model, values)


def _vllm_config(model: str, values: dict[str, str]) -> LlmConfig:
    resolved = {
        "QWEN_BASE_URL": _value("QWEN_BASE_URL", values),
        "QWEN_MODEL": model,
        "QWEN_API_KEY": _value("QWEN_API_KEY", values),
    }
    missing = [key for key, value in resolved.items() if not value]
    if missing:
        raise ValueError(f"필수 Qwen 설정 누락: {', '.join(missing)}")
    return LlmConfig(
        provider=VLLM,
        base_url=resolved["QWEN_BASE_URL"].rstrip("/"),
        model=model,
        api_key=resolved["QWEN_API_KEY"],
    )


def _gms_proxied_config(provider: str, model: str, values: dict[str, str]) -> LlmConfig:
    api_key = _value("GMS_KEY", values)
    if not api_key:
        raise ValueError("필수 GMS 설정 누락: GMS_KEY")
    return LlmConfig(
        provider=provider,
        base_url=(_value("GMS_BASE_URL", values) or DEFAULT_GMS_BASE_URL).rstrip("/"),
        model=model,
        api_key=api_key,
    )
