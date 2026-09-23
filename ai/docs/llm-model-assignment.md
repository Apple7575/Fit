# 담당별 LLM 모델 배정

2026-09-23. 검토 방 한 턴이 GMS 를 약 15회 부르고 면접 기능까지 같은 모델을 쓰면서
`gemini-2.5-flash-lite` 의 Google 할당량이 소진돼 `RESOURCE_EXHAUSTED` 429 가 났다.
요청 큐(`ai/llm/gms_gate.py`)는 우리 쪽 폭주만 막지 이미 바닥난 할당량은 어쩌지 못한다.
그래서 호출을 공급자 셋(OpenAI·Google·Anthropic)의 여러 모델로 나눴다. 할당량은 모델별로
따로 잡힌다.

## 배정

| 담당 | 접두사 | 1순위(기본) | 호출/턴 | 이유 |
|---|---|---|---|---|
| 채용공고 | `JD` | gpt-4.1-mini | 8~10 | 항목별 병렬 호출로 양이 가장 많다. 싸고 빠르다 |
| 포지션 | `POSITION` | gpt-5.4-mini | 1~2 | 인용 위치·요소 검증이 엄격한데 2초에 통과 |
| 글쓰기 | `WRITING` | gemini-2.5-flash | 1~2 | 한국어 문장 품질. flash-lite 와 별도 할당량 |
| 총괄 계획 | `SUPERVISOR_PLAN` | gpt-5.4-nano | 1 | 담당 고르기 한 번. 가장 가벼운 모델 |
| 총괄 종합 | `SUPERVISOR_AGGREGATE` | claude-haiku-4-5-20251001 | 1 | 판단 품질. gpt-4.1-mini 는 없는 근거 id 를 지어내 탈락 |
| 기업 RAG | `COMPANY_ANALYSIS` | gemini-2.5-flash-lite | 1 | 긴 문맥. flash-lite 에는 이 담당만 남긴다 |
| 뉴스 | `NEWS` | gemini-2.5-flash-lite | - | 폐지 예정. 기존 값 유지 |

면접 기능은 백엔드가 GMS 를 직접 부르며 이 표의 대상이 아니다(`app.ai.gms.model`).

## 설정 우선순위

```
<PREFIX>_LLM_PROVIDER / <PREFIX>_LLM_MODEL   담당 하나만 바꿀 때
AGENT_DEFAULTS[prefix]                         코드 기본 배정 (ai/llm/config.py)
LLM_PROVIDER / GMS_MODEL / QWEN_MODEL          접두사가 없거나 기본 배정이 없는 호출부
```

`<PREFIX>_LLM_PROVIDER` 만 바꾸고 모델을 비우면 그 공급자의 기본 모델
(gms→gemini-2.5-flash-lite, openai→gpt-4.1-mini, anthropic→claude-haiku-4-5-20251001)을 쓴다.
GPT 이름을 Claude 에 보내는 일은 생기지 않는다.

OpenAI·Anthropic 모델도 SSAFY GMS 프록시를 거친다. 키는 `GMS_KEY` 하나다.
`infra/docker-compose.yml` 이 위 변수를 모두 컨테이너에 넘기므로 `.env.<환경>` 에 적으면 된다.

## 공급자별 어댑터가 흡수한 차이

- **OpenAI** (`ai/llm/openai.py`): gpt-5 계열은 `max_completion_tokens` 만 받고 temperature 를
  못 바꾼다. strict 구조화 출력이 스키마를 거절하면(지원 안 하는 키워드) 비strict 로 한 번 더 보낸다.
- **Anthropic** (`ai/llm/anthropic.py`): `response_format` 이 없어 스키마를 도구 하나의
  `input_schema` 로 주고 그 도구를 강제 호출한다. 깊이 중첩된 배열을 JSON 문자열로 싸는 버릇은
  `coerce_json_strings` 로 되돌린다.
- **Gemini** (`ai/llm/gms.py`): `gemini-2.5-flash` 는 생각 토큰이 출력 한도를 먹어 JSON 이
  `MAX_TOKENS` 로 끊기므로 `thinkingBudget: 0` 을 준다(flash-lite·pro 는 제외).
- **공통** (`ai/llm/schema.py`): 담당 스키마의 `allOf/if/then` 조건문과 `$schema/$id/title` 은
  전송용 스키마에서 뗀다. 그 규칙은 파이썬 검증기(pydantic·`validate_*`)가 다시 본다.

## 요청 큐

큐는 `공급자:모델` 마다 하나다(`gate_for`). 한 줄에 다 세우면 flash-lite 의 429 가 GPT·Claude
호출까지 멈추고, 모델을 나눠도 처리량이 한 모델일 때와 같아진다. 설정값(`GMS_*`)은 아직 모델 공통이다.

## 검증 방법

형식 검증은 실제 담당 프롬프트·스키마·파이썬 검증기(재시도 포함)로 후보 모델을 직접 불러 봤다.
탈락한 모델과 이유: gemini-3.5-flash(응답 스키마 무시), gpt-5-mini/nano(추론 토큰으로 느림·빈 응답),
gpt-4.1-mini 의 총괄 종합(없는 근거 id). 배정을 바꿀 때는 같은 방식으로 다시 확인한다 —
`ai/tests/llm/` 의 단위 테스트는 어댑터 형식만 보고 모델 응답은 가짜다.
