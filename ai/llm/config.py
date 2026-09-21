"""LLM 설정을 환경변수와 .env 에서 읽는다.

공급자를 바꾸는 손잡이는 `LLM_PROVIDER` 하나다. 담당별로 다르게 쓰고 싶으면
`<PREFIX>_LLM_PROVIDER` 로 덮어쓴다 — 예: `COMPANY_ANALYSIS_LLM_PROVIDER=gms` 면 기업 담당만
GMS 로 간다. 옮겨 갈 때 한 담당씩 시험해 보기 위한 자리다.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

VLLM = "vllm"
GMS = "gms"
PROVIDERS = (VLLM, GMS)

DEFAULT_PROVIDER = VLLM
DEFAULT_GMS_BASE_URL = "https://gms.ssafy.io/gmsapi"
DEFAULT_GMS_MODEL = "gemini-2.5-flash-lite"


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


def resolve_provider(values: dict[str, str] | None = None, *, prefix: str = "") -> str:
    """쓸 공급자를 정한다. 담당별 덮어쓰기가 전역 설정보다 우선한다."""
    values = values or {}
    candidates = []
    if prefix:
        candidates.append(f"{prefix}_LLM_PROVIDER")
    candidates.append("LLM_PROVIDER")
    for key in candidates:
        chosen = _value(key, values).lower()
        if chosen:
            if chosen not in PROVIDERS:
                raise ValueError(
                    f"지원하지 않는 LLM 공급자입니다: {chosen} ({', '.join(PROVIDERS)} 중 하나)"
                )
            return chosen
    return DEFAULT_PROVIDER


def load_llm_config(path: Path, *, prefix: str = "") -> LlmConfig:
    """공급자에 맞는 주소·모델·키를 모은다. 없으면 무엇이 빠졌는지 알리고 멈춘다."""
    values = read_env_file(path)
    provider = resolve_provider(values, prefix=prefix)
    if provider == GMS:
        return _gms_config(values)
    return _vllm_config(values)


def _vllm_config(values: dict[str, str]) -> LlmConfig:
    resolved = {key: _value(key, values) for key in ("QWEN_BASE_URL", "QWEN_MODEL", "QWEN_API_KEY")}
    missing = [key for key, value in resolved.items() if not value]
    if missing:
        raise ValueError(f"필수 Qwen 설정 누락: {', '.join(missing)}")
    return LlmConfig(
        provider=VLLM,
        base_url=resolved["QWEN_BASE_URL"].rstrip("/"),
        model=resolved["QWEN_MODEL"],
        api_key=resolved["QWEN_API_KEY"],
    )


def _gms_config(values: dict[str, str]) -> LlmConfig:
    api_key = _value("GMS_KEY", values)
    if not api_key:
        raise ValueError("필수 GMS 설정 누락: GMS_KEY")
    return LlmConfig(
        provider=GMS,
        base_url=(_value("GMS_BASE_URL", values) or DEFAULT_GMS_BASE_URL).rstrip("/"),
        model=_value("GMS_MODEL", values) or DEFAULT_GMS_MODEL,
        api_key=api_key,
    )
