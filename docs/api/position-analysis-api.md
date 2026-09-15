# 포지션 분석 내부 API 명세

## 1. 목적과 호출 경계

이 문서는 포지션 담당 에이전트를 구현하면서 추가한 FastAPI의 HTTP 계약을 다룬다. Spring
연동 코드는 이번 브랜치에 포함하지 않으며, 백엔드 담당자가 연동할 때 사용할 요청·응답 계약을
제공한다.

```text
브라우저 → Spring Boot → FastAPI → Qwen
```

권장 경계상 프론트엔드는 FastAPI를 직접 호출하지 않는다. Spring이 사용자 인증과 권한 검사,
자소서 및 대화 조회, 로깅, 요청 제한, 결과 저장을 담당하고 FastAPI에는 구조화된 분석 입력만
전달한다. FastAPI는 전달받은 데이터로 포지션 프롬프트를 만들고 Qwen 응답을 검증한다.

아래 예시의 `{AI_SERVICE_BASE_URL}`은 배포 환경에서 정할 AI 서버 주소다. 이번 브랜치에는
Spring 프로퍼티나 HTTP 클라이언트 설정을 추가하지 않는다.

## 2. 추가된 엔드포인트

| 목적 | 메서드 | 통합 FastAPI 경로 | 현재 호출 주체 |
| --- | --- | --- | --- |
| 포지션 분석 | `POST` | `/position/internal/analyses` | 백엔드 연동 시 호출 대상. 현재 Spring 호출 코드 없음 |
| 포지션 서비스 준비 상태 | `GET` | `/position/ready` | AI Docker 이미지 healthcheck |
| 포지션 프로세스 상태 | `GET` | `/position/health` | 운영 점검용. Spring은 호출하지 않음 |

`/position`은 통합 FastAPI 진입점에서 마운트되는 도메인 경로다. 포지션 앱 자체의 라우트는
각각 `/internal/analyses`, `/ready`, `/health`다.

## 3. 포지션 분석 요청

```http
POST {AI_SERVICE_BASE_URL}/position/internal/analyses
Content-Type: application/json
```

### 3.1 요청 예시

```json
{
  "position_profile_id": "backend-v1",
  "documents": [
    {
      "document_id": "cover-letter",
      "document_type": "SELF_INTRO",
      "text": "Redis 캐시를 도입해 응답 시간을 40% 줄였습니다."
    },
    {
      "document_id": "message-480",
      "document_type": "EXPERIENCE",
      "text": "상품 조회 API의 DB 부하를 줄이는 역할을 맡았습니다."
    }
  ],
  "conversation": [
    {
      "message_id": "480",
      "role": "USER",
      "content": "상품 조회 API의 DB 부하를 줄이는 역할을 맡았습니다."
    },
    {
      "message_id": "481",
      "role": "ASSISTANT",
      "content": "캐시 적용 전 어떤 문제가 있었나요?"
    }
  ]
}
```

### 3.2 요청 필드

| 필드 | 필수 | 허용값·제한 | 설명 |
| --- | --- | --- | --- |
| `position_profile_id` | 예 | 1~100자 | 현재는 `backend-v1`만 지원 |
| `documents` | 예 | 1~21개 | 분석의 사실 근거 |
| `documents[].document_id` | 예 | 1~100자, 요청 내 고유 | 문서 식별자 |
| `documents[].document_type` | 예 | `SELF_INTRO`, `EXPERIENCE` | 자소서 또는 추가 경험 |
| `documents[].text` | 예 | 1~50,000자 | 문서 원문 |
| `conversation` | 아니오 | 최대 20개, 기본 `[]` | 후속 대화 맥락 |
| `conversation[].message_id` | 예 | 1~100자 | 메시지 식별자 |
| `conversation[].role` | 예 | `USER`, `ASSISTANT` | 메시지 작성자 |
| `conversation[].content` | 예 | 1~10,000자 | 메시지 원문 |

명세에 없는 필드를 추가하면 `422`로 거절한다. 공백 문자열도 허용하지 않는다.

`ASSISTANT` 메시지는 이전 질문의 맥락일 뿐 사용자 경험의 근거가 아니다. `USER` 메시지도
동일한 내용을 `EXPERIENCE` 문서로 함께 보낸 경우에만 분석 근거로 사용할 수 있다. 백엔드
연동 시 최근 사용자 메시지를 `conversation`과 `EXPERIENCE` 양쪽에 넣어야 한다.

## 4. 포지션 분석 응답

### 4.1 성공 응답 예시

```json
{
  "message": "\"Redis 캐시를 도입해 응답 시간을 40% 줄였습니다.\" 경험에서 문제 상황, 구체적인 동작 방식, 검증 방법 설명이 빠져 있습니다.\n- 당시 해결해야 했던 문제나 제약이 무엇이었는지 설명해 주세요.\n- 적용한 방법이 실제로 어떻게 동작했는지 설명해 주세요.",
  "analysis": {
    "analysis_status": "COMPLETED",
    "position_profile": {
      "id": "backend-v1",
      "version": 1
    },
    "findings": [
      {
        "finding_id": "finding-1",
        "experience_type": "CACHE_PERFORMANCE",
        "claim": {
          "quote": "Redis 캐시를 도입해 응답 시간을 40% 줄였습니다.",
          "document_id": "cover-letter",
          "start_offset": 0,
          "end_offset": 31
        },
        "present_elements": [
          {
            "element": "ACTION",
            "quote": "Redis 캐시를 도입"
          },
          {
            "element": "RESULT",
            "quote": "응답 시간을 40% 줄였습니다."
          }
        ],
        "missing_elements": [
          "PROBLEM",
          "MECHANISM",
          "VERIFICATION"
        ],
        "verdict": "PARTIAL",
        "reason": "필수 경험 요소 일부가 원문에서 확인되지 않습니다.",
        "follow_up_questions": [
          "캐시 도입 전 어떤 문제가 있었나요?",
          "캐시가 어떤 방식으로 동작했나요?"
        ]
      }
    ],
    "model_metadata": {
      "base_model": "main",
      "base_revision": "deployment-alias-unresolved",
      "adapter": null,
      "training_dataset": null,
      "prompt_version": "position-depth-v1"
    }
  }
}
```

### 4.2 응답 필드

| 필드 | 설명 |
| --- | --- |
| `message` | 검증된 분석 필드로 FastAPI가 조립한 사용자 표시용 문장 |
| `analysis.analysis_status` | `COMPLETED` 또는 `NO_TECHNICAL_CLAIM` |
| `analysis.position_profile` | 사용한 직무 프로필 ID와 버전 |
| `analysis.findings` | 원문에서 찾은 기술 경험별 분석 |
| `findings[].finding_id` | 분석 내 finding을 식별하는 비어 있지 않은 문자열 |
| `findings[].experience_type` | `API_DESIGN`, `DATABASE`, `CONCURRENCY`, `CACHE_PERFORMANCE`, `MESSAGING`, `RELIABILITY`, `OBSERVABILITY`, `SECURITY`, `OTHER_BACKEND` 중 하나 |
| `findings[].claim` | 원문 인용과 문서 ID, Python 문자열 기준 시작·끝 offset |
| `findings[].present_elements` | 원문에서 확인된 경험 구성 요소와 인용 |
| `findings[].missing_elements` | 보완해야 하는 경험 구성 요소 |
| `findings[].verdict` | `SUFFICIENT`, `PARTIAL`, `CLAIM_ONLY`, `NOT_ASSESSABLE` |
| `findings[].reason` | 모델의 판정 이유인 비어 있지 않은 문자열. 사용자 표시 문장에는 직접 사용하지 않음 |
| `findings[].follow_up_questions` | 누락 요소를 확인하는 질문. 최대 2개 |
| `analysis.model_metadata` | 모델, 어댑터, 학습 데이터, 프롬프트 버전 정보 |

경험 구성 요소의 허용값은 다음과 같다.

- `PROBLEM`: 문제 상황
- `ROLE`: 담당 역할
- `ACTION`: 직접 수행한 행동
- `REASONING`: 선택 이유
- `MECHANISM`: 구체적인 동작 방식
- `VERIFICATION`: 검증 방법
- `RESULT`: 결과

`SUFFICIENT` 판정에는 누락 요소와 후속 질문이 없어야 한다. 기술 경험을 찾지 못하면
`analysis_status`는 `NO_TECHNICAL_CLAIM`, `findings`는 빈 배열이다.

### 4.3 백엔드 DTO 권장 형태와 미구현 범위

백엔드에서는 다음과 같은 DTO로 응답을 받을 수 있다.

```java
public record PositionAnalysisResult(
        String message,
        Map<String, Object> analysis) {
}
```

이 DTO와 Spring HTTP 클라이언트, 채팅 실행 분기, DB 저장은 이번 브랜치에 구현하지 않는다.
연동 시 `message`만 채팅에 저장할지, `analysis`도 구조화해서 보존할지는 백엔드에서 결정해야
한다. UI나 총괄 에이전트가 판정, 누락 요소, 원문 offset을 다시 사용하려면 `analysis` 저장이
필요하다.

## 5. 오류 계약과 시간 제한

| HTTP 상태 | FastAPI에서의 의미 |
| --- | --- |
| `200` | 분석 완료 |
| `422` | 요청 형식 오류, 미지원 프로필, 입력 문서 오류 |
| `502` | Qwen 연결·HTTP·응답 실패 또는 두 차례 출력 검증 실패 |
| `503` | Qwen 접속 설정 없음 |

Qwen 호출 제한은 회당 25초이고 유효하지 않은 출력에 한해 최대 두 번 시도한다. 백엔드 HTTP
제한 시간과 오류 매핑은 이번 브랜치에서 정하지 않는다.

FastAPI 내부 API에는 현재 별도 인증 헤더 검사가 없다. 외부에 공개하지 않고 사내 네트워크에서
백엔드 서버만 접근하도록 배포해야 한다.

## 6. 준비 상태 API

### 6.1 프로세스 상태

```http
GET {AI_SERVICE_BASE_URL}/position/health
```

```json
{
  "status": "ok"
}
```

Qwen 설정과 관계없이 FastAPI 프로세스가 요청에 응답하면 `200`을 반환한다.

### 6.2 분석 준비 상태

```http
GET {AI_SERVICE_BASE_URL}/position/ready
```

설정이 준비된 경우:

```json
{
  "status": "ready"
}
```

Qwen 설정을 읽을 수 없으면 `503`을 반환한다. AI Docker 이미지의 healthcheck는 이 경로를
사용한다.

## 7. 백엔드 연결 담당자가 확인할 세 가지

### 7.1 질의 엔드포인트 요청·응답

- 호출 경로: `POST /position/internal/analyses`
- Spring 구현: 이번 브랜치에 포함하지 않음
- 요청: 프로필 ID, 자소서·경험 문서, 최근 대화
- 응답: 사용자 표시 문장 `message`와 구조화된 `analysis`

### 7.2 `ragReady` 조회 방법

`ragReady`는 포지션 분석 FastAPI의 요청·응답에 포함되지 않는다. 현재 Spring이
`APP_AGENT_RAG_INDEXED_CORP_CODES` 설정을 기준으로 선택된 기업 각각의 값을 계산한다.

```text
GET /api/rooms/{roomId}
  → data.agents[].config.companies[].ragReady
```

따라서 현재 방식은 기업 하나마다 FastAPI를 호출하는 방식이 아니라, **방에 선택된 기업 목록을
Spring 응답으로 한 번에 받는 방식**이다. 기업 검색 결과 전체의 준비 상태를 일괄 조회하는
FastAPI 계약은 이번 작업 범위에 없으며 아직 구현되지 않았다.

설정 목록이 비어 있으면 Spring은 인덱싱 상태를 알 수 없는 것으로 보고 기업 선택을 막지 않으며
`ragReady=true`로 표시한다. 실제 RAG 인덱싱 파이프라인과 연결할 때는 이 임시 정책을 별도
준비 상태 조회 계약으로 교체해야 한다.

### 7.3 프롬프트 생성 위치

포지션 담당 프롬프트는 **FastAPI가 생성한다**. 백엔드 연동 시 Spring은 프롬프트 문자열을
만들거나 보내지 않고 구조화된 입력만 전달한다.

```text
Spring
  └─ position_profile_id + documents + conversation
      → FastAPI
          └─ 직무 프로필 로드 + 프롬프트 생성 + Qwen 호출 + 출력 검증
```

프롬프트 버전은 응답의 `analysis.model_metadata.prompt_version`으로 확인한다. 현재 값은
`position-depth-v1`이다.

## 8. 이번 작업의 JD 경로 변경

JD 분석 기능 자체를 새로 만든 것은 아니며 기존 동기 분석 경로만 리소스형으로 변경했다.

```text
변경 전: POST /jd/internal/jd/analyze
변경 후: POST /jd/internal/analyses
```

이전 경로는 호환 경로로 남기지 않았다. JD FastAPI와 멀티에이전트 Spring 턴의 HTTP 연결은
이번 작업에 포함되지 않았다. 상세 JD 요청·응답은 `ai/docs/jd-coaching-openapi.json`을 따른다.

## 9. 관련 구현

- FastAPI 라우트: `ai/position_coaching/api.py`
- 프롬프트: `ai/position_coaching/prompt.py`
- 분석 서비스: `ai/position_coaching/service.py`
- 출력 검증: `ai/position_coaching/contracts.py`
- 출력 JSON Schema: `ai/position_coaching/resources/schemas/position-analysis-v1.json`
- Spring HTTP 클라이언트와 실행 연결: 이번 브랜치에 포함하지 않음
