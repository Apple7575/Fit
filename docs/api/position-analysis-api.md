# 포지션 분석 내부 API 명세

## 역할과 연결 경계

포지션 담당은 JD 적합도를 다시 평가하지 않는다. 사용자가 제시한 경험에서 상황, 역할,
행동, 수행 과정, 판단 근거, 검증, 결과, 학습 사이의 빠진 연결고리를 찾는다. 기술·비기술
직무 모두 같은 `experience-depth-v1` 루브릭을 사용한다.

```text
브라우저 → Spring Boot → FastAPI → Qwen
```

Spring은 인증, 권한, 자소서·대화·JD 데이터 조회, 로깅과 결과 저장을 담당한다. FastAPI는
구조화된 입력으로 프롬프트를 만들고 Qwen 출력을 검증한다. 이 브랜치에는 Spring HTTP
클라이언트나 DB 저장 로직이 포함되지 않는다.

## 엔드포인트

| 목적 | 메서드 | 통합 서버 경로 |
| --- | --- | --- |
| 경험 구체성 분석 | `POST` | `/position/internal/analyses` |
| 분석 준비 상태 | `GET` | `/position/ready` |
| 프로세스 상태 | `GET` | `/position/health` |

포지션 FastAPI 앱 내부 경로는 각각 `/internal/analyses`, `/ready`, `/health`이며 통합
FastAPI 진입점이 `/position` 접두어로 마운트한다.

## 분석 요청

```http
POST {AI_SERVICE_BASE_URL}/position/internal/analyses
Content-Type: application/json
```

```json
{
  "rubric_id": "experience-depth-v1",
  "position_context": {
    "position_name": "마케팅 매니저",
    "priority_requirements": ["콘텐츠 캠페인 기획", "성과 지표 분석"]
  },
  "documents": [
    {
      "document_id": "cover-letter",
      "document_type": "SELF_INTRO",
      "text": "SNS 캠페인을 개선해 전환율을 높였습니다."
    },
    {
      "document_id": "message-480",
      "document_type": "EXPERIENCE",
      "text": "광고 문구 두 종류를 일주일간 비교했습니다."
    }
  ],
  "conversation": [
    {
      "message_id": "480",
      "role": "USER",
      "content": "광고 문구 두 종류를 일주일간 비교했습니다."
    },
    {
      "message_id": "481",
      "role": "ASSISTANT",
      "content": "어떤 지표로 비교했나요?"
    }
  ]
}
```

| 필드 | 필수 | 제한 | 의미 |
| --- | --- | --- | --- |
| `rubric_id` | 예 | `experience-depth-v1` | 범용 경험 분석 기준표 |
| `position_context.position_name` | 예 | 공백 제외 1~200자 | 질문 용어와 분석 우선순위 조정용 직무명 |
| `position_context.priority_requirements` | 아니오 | 최대 20개, 항목당 1~500자 | Spring/JD 담당이 추출한 주요 요구사항 |
| `documents` | 예 | 1~21개 | 분석의 유일한 사실 근거 |
| `documents[].document_id` | 예 | 1~100자, 요청 안에서 고유 | 원문 식별자 |
| `documents[].document_type` | 예 | `SELF_INTRO`, `EXPERIENCE` | 자소서 또는 후속 답변 |
| `documents[].text` | 예 | 1~50,000자 | 사용자 원문 |
| `conversation` | 아니오 | 최대 20개, 기본 `[]` | 대화 흐름을 위한 문맥 |
| `conversation[].message_id` | 예 | 1~100자 | 메시지 식별자 |
| `conversation[].role` | 예 | `USER`, `ASSISTANT` | 메시지 작성자 |
| `conversation[].content` | 예 | 1~10,000자 | 메시지 내용 |

명세에 없는 필드와 공백 문자열은 `422`로 거절한다. `position_profile_id`와
`backend-v1`은 더 이상 지원하지 않는다.

`position_context`와 `conversation`은 사실 근거가 아니다. JD 요구사항은 어떤 경험을 먼저
분석하고 어떤 용어로 질문할지에만 영향을 준다. 사용자 후속 답변을 새 근거로 쓰려면 같은
내용을 `EXPERIENCE` 문서에도 넣어야 한다.

## 성공 응답

```json
{
  "message": "\"SNS 캠페인을 개선해 전환율을 높였습니다.\" 경험에서 상황, 담당 역할 설명이 빠져 있습니다.\n- 경험이 발생한 시점, 환경이나 제약을 설명해 주세요.\n- 그 과정에서 본인이 직접 맡은 범위가 무엇이었는지 설명해 주세요.",
  "analysis": {
    "analysis_status": "COMPLETED",
    "rubric": {"id": "experience-depth-v1", "version": 1},
    "findings": [
      {
        "finding_id": "finding-001",
        "claim_type": "ACHIEVEMENT",
        "claim": {
          "quote": "SNS 캠페인을 개선해 전환율을 높였습니다.",
          "document_id": "cover-letter",
          "start_offset": 0,
          "end_offset": 26
        },
        "present_elements": [],
        "missing_elements": ["SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"],
        "verdict": "CLAIM_ONLY",
        "reason": "성과 주장은 있지만 수행 근거를 확인할 수 없습니다.",
        "follow_up_questions": ["전환율을 어떤 기준으로 비교했나요?"]
      }
    ],
    "model_metadata": {
      "base_model": "main",
      "base_revision": "deployment-alias-unresolved",
      "adapter": null,
      "training_dataset": null,
      "prompt_version": "experience-depth-v1"
    }
  }
}
```

`message`는 검증된 구조화 필드로 FastAPI가 다시 조립한다. 모델이 작성한 `reason`과
`follow_up_questions`는 구조화 분석에는 남지만 사용자 표시 문장에 직접 삽입하지 않는다.

### 응답 값

- `analysis_status`: `COMPLETED`, `NO_EXPERIENCE_CLAIM`
- `claim_type`: `PROBLEM_SOLVING`, `ACHIEVEMENT`, `DECISION`, `EXECUTION`,
  `COLLABORATION`, `GROWTH`, `OTHER`
- `verdict`: `SUFFICIENT`, `PARTIAL`, `CLAIM_ONLY`, `NOT_ASSESSABLE`
- 경험 요소: `SITUATION`, `PROBLEM`, `ROLE`, `ACTION`, `REASONING`, `PROCESS`,
  `VERIFICATION`, `RESULT`, `LEARNING`

`claim.quote`는 해당 문서에 존재하는 정확한 연속 문자열이어야 하며 offset은 Python 문자열
인덱스 기준의 시작 포함·끝 제외 값이다. 서버는 주장 유형에 정해진 필수 요소가
`present_elements`와 `missing_elements`에 정확히 한 번씩 나뉘었는지 검증한다.

구체화할 경험 주장을 찾지 못하면 `analysis_status`가 `NO_EXPERIENCE_CLAIM`이고 `findings`는
빈 배열이다. `SUFFICIENT` finding은 누락 요소와 후속 질문이 없어야 한다.

## 오류와 호출 정책

| 상태 | 의미 |
| --- | --- |
| `200` | 검증된 분석 반환 |
| `422` | 요청 형식, 루브릭, 직무 문맥, 문서 또는 대화 오류 |
| `502` | Qwen 호출 실패 또는 두 번 연속 출력 검증 실패 |
| `503` | Qwen 접속 설정 없음 |

Qwen 호출 제한은 시도당 25초다. 출력이 스키마, 원문 인용 또는 판정 규칙을 위반하면 검증
오류를 포함해 한 번만 재시도한다. 일부 finding만 유효한 경우에도 부분 응답을 반환하지 않는다.
FastAPI 내부 API에는 별도 인증 헤더 검사가 없으므로 외부에 직접 공개하지 않아야 한다.

## Spring 연동 시 필요한 결정

질의 엔드포인트의 요청·응답 모양은 위 계약으로 고정한다. Spring은 에이전트 프롬프트를
만들지 않고 `rubric_id`, `position_context`, `documents`, `conversation`만 보낸다.

기업 `ragReady`는 이 API와 무관하다. 기업 선택 목록과 RAG 준비 상태는 Spring의 방 조회
응답에서 관리하며 포지션 분석 요청에 넣지 않는다.

응답 저장은 Spring 구현 범위다. 채팅 표시만 필요하면 `message`를 저장할 수 있지만 총괄
에이전트나 UI가 판정, 누락 요소, 원문 위치를 다시 사용하려면 `analysis`도 구조화해 보존해야 한다.

## 관련 구현

- FastAPI 라우트: `ai/position_coaching/api.py`
- 프롬프트: `ai/position_coaching/prompt.py`
- 분석 서비스: `ai/position_coaching/service.py`
- 계약 검증: `ai/position_coaching/contracts.py`
- 범용 루브릭: `ai/position_coaching/resources/rubrics/experience-depth-v1.json`
- 출력 스키마: `ai/position_coaching/resources/schemas/position-analysis-v2.json`
- Spring HTTP 클라이언트 및 저장 로직: 미구현
