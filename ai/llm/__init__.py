"""담당들이 공유하는 LLM 호출 계층.

호출부는 공급자를 모른다. `complete_structured` 에 설정과 메시지를 주면 JSON 스키마에 맞는
출력을 돌려준다. 어느 서버로 나가는지는 설정의 `provider` 가 정하고, 그 값은 환경변수에서 온다.

    from ai.llm import complete_structured, load_llm_config

    config = load_llm_config(Path("ai/.env"))
    result = complete_structured(config, messages, schema=..., max_tokens=1024)
    result["output"]   # 스키마에 맞는 dict
    result["usage"]    # 토큰 사용량
    result["model"]    # 실제 응답한 모델 이름

공급자는 둘이다.

  vllm  사내 GPU 서버(OpenAI 호환 `/chat/completions`). 지금 기본값
  gms   SSAFY GMS 경유 Gemini(`:generateContent`)

둘은 요청·응답 모양이 다르다 — 인증 헤더부터 구조화 출력 지정 방식, 답을 꺼내는 경로까지.
그 차이를 각 어댑터가 흡수하고 바깥에는 같은 dict 를 돌려준다.
"""
from ai.llm.config import LlmConfig, load_llm_config, resolve_provider
from ai.llm.contracts import (
    LlmConnectionError,
    LlmHttpError,
    LlmResponseError,
    StructuredCompletion,
)
from ai.llm.router import complete_structured

__all__ = [
    "LlmConfig",
    "LlmConnectionError",
    "LlmHttpError",
    "LlmResponseError",
    "StructuredCompletion",
    "complete_structured",
    "load_llm_config",
    "resolve_provider",
]
