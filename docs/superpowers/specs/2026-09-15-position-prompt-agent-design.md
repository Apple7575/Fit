# 포지션 프롬프트 에이전트 설계

> 구현 범위 변경: 현재 브랜치에는 FastAPI 포지션 분석 기능만 포함한다. 이 문서의 Spring
> 연동 내용은 향후 백엔드 담당자가 검토할 목표 구조이며 구현 완료 상태를 뜻하지 않는다.

## 목표

포지션 에이전트는 자소서가 특정 채용공고와 일치하는지 다시 검사하지 않는다. 사용자가
서술한 경험이 선택한 직무의 역량을 입증할 만큼 구체적인지 확인하고, 빠진 연결고리를
후속 질문으로 보완한다. 1차 범위는 `backend-v1` 직무 프로필이다.

## 시스템 경계

- 브라우저는 Spring의 `/api/rooms` API만 호출한다.
- Spring은 인증, 방 소유권, 에이전트 선택, 자소서 조회, 대화 저장, 비동기 턴 상태를 맡는다.
- FastAPI는 포지션 분석 프롬프트 구성, Qwen 호출, JSON 계약 및 원문 인용 검증을 맡는다.
- 포지션 에이전트용 별도 공개 `/chat` API는 만들지 않는다.
- 현재 Spring의 `AgentLlmClient` 직접 호출은 다른 에이전트에 유지하되, `position` 실행만
  FastAPI 클라이언트로 분기한다.

관련 결정: [[Decisions/architecture/agent-api-path-convention-without-url-version]]

## API 규칙

### 공개 API

기존 API를 그대로 사용한다.

| 목적 | 메서드와 경로 |
|---|---|
| 에이전트 목록 | `GET /api/agents` |
| 직무 목록 | `GET /api/job-roles` |
| 방 생성 | `POST /api/rooms` |
| 포지션 선택 | `PATCH /api/rooms/{roomId}/agents/position` |
| 발화 및 분석 시작 | `POST /api/rooms/{roomId}/messages` |
| 대화 조회 | `GET /api/rooms/{roomId}/messages` |
| 턴 상태 조회 | `GET /api/rooms/{roomId}/turns/{turnId}` |

### AI 내부 API

FastAPI 앱은 `/position`에 마운트하고 한 턴을 다음 경로로 실행한다.

```http
POST /position/internal/analyses
```

첫 분석과 후속 답변 반영은 같은 경로를 사용한다. 요청에 이전 사용자·포지션 에이전트
대화가 있으면 후속 턴이고, 없으면 첫 턴이다.

요청 계약:

```json
{
  "position_profile_id": "backend-v1",
  "documents": [
    {
      "document_id": "cover-letter",
      "document_type": "SELF_INTRO",
      "text": "문항 1. ...\n답변: ..."
    },
    {
      "document_id": "message-41",
      "document_type": "EXPERIENCE",
      "text": "DB 조회가 800ms에서 120ms로 줄었습니다."
    }
  ],
  "conversation": [
    {
      "message_id": "40",
      "role": "ASSISTANT",
      "content": "적용 전후 성능은 어떻게 검증했나요?"
    },
    {
      "message_id": "41",
      "role": "USER",
      "content": "DB 조회가 800ms에서 120ms로 줄었습니다."
    }
  ]
}
```

- `documents`만 분석 근거로 인정한다. 기존 계약의 `SELF_INTRO`를 자소서에,
  `EXPERIENCE`를 채팅으로 보완한 경험에 사용한다.
- `conversation`의 assistant 메시지는 질문의 맥락으로만 사용하며 사실 근거로 인정하지 않는다.
- Spring은 현재 사용자 메시지와 이전 사용자 메시지를 `EXPERIENCE` 문서로 전달한다.
- `document_id`는 한 요청 안에서 유일해야 한다.

응답 계약:

```json
{
  "message": "구체화할 기술 경험을 찾지 못했습니다. 맡은 문제와 직접 수행한 행동을 알려 주세요.",
  "analysis": {
    "analysis_status": "NO_TECHNICAL_CLAIM",
    "position_profile": {"id": "backend-v1", "version": 1},
    "findings": [],
    "model_metadata": {
      "base_model": "main",
      "base_revision": "configured",
      "adapter": null,
      "training_dataset": null,
      "prompt_version": "position-depth-v1"
    }
  }
}
```

`analysis`는 기존 `position-analysis-v1.json` 계약을 그대로 사용한다. `message`는 검증된
finding의 이유와 후속 질문만으로 서버가 결정적으로 렌더링하며, 모델의 별도 자유서술을
받지 않는다.

## 분석 규칙

포지션 프로필은 경험 유형별 필수 연결고리를 정의한다. 백엔드 v1은 API 설계, 데이터베이스,
동시성, 캐시·성능, 메시징, 신뢰성, 관측성, 보안, 기타 백엔드 경험을 구분한다.

각 기술 주장에 대해 다음을 수행한다.

1. 사용자 원문에서 연속된 정확한 인용문을 추출한다.
2. 경험 유형을 하나 선택한다.
3. 프로필이 요구하는 `PROBLEM`, `ROLE`, `ACTION`, `REASONING`, `MECHANISM`,
   `VERIFICATION`, `RESULT` 중 실제로 존재하는 요소와 빠진 요소를 구분한다.
4. `SUFFICIENT`, `PARTIAL`, `CLAIM_ONLY`, `NOT_ASSESSABLE` 중 하나로 판정한다.
5. 가장 중요한 누락 요소를 확인하는 질문을 finding당 최대 2개 생성한다.

질문은 “Redis를 사용했나요?”처럼 사실을 유도하지 않는다. “어떤 병목을 확인했고 해결책을
어떤 기준으로 선택했나요?”처럼 사용자가 실제 경험을 설명하게 해야 한다.

## 후속 턴

- 매 턴마다 자소서와 사용자 답변 전체를 다시 분석한다.
- 이전 모델 판정을 사실처럼 재사용하지 않는다.
- 사용자 답변으로 확인된 요소는 해당 답변의 정확한 인용문을 근거로 추가한다.
- 확인되지 않은 기술, 역할, 수치, 성과는 채우지 않는다.
- 모든 finding이 `SUFFICIENT`이면 추가 질문을 만들지 않는다.
- 기술 주장이 없으면 `NO_TECHNICAL_CLAIM`과 안내 메시지를 반환한다.

## 실패 처리

- 지원하지 않는 `position_profile_id`: `422`
- 중복되거나 비어 있는 문서, 잘못된 대화 역할: `422`
- Qwen 연결 또는 응답 실패: `502`
- JSON 스키마 불일치: 검증 오류를 포함해 한 번만 재요청하고 다시 실패하면 `502`
- 인용문 또는 offset이 원문과 일치하지 않음: 응답을 저장하지 않고 `502`

Spring은 FastAPI 실패 시 해당 포지션 메시지만 `FAILED`로 남긴다. 같은 턴의 다른 에이전트와
총괄 흐름은 기존 격리 규칙을 유지한다.

## JD 내부 경로 정규화

JD FastAPI는 아직 외부 연동 전이므로 호환 경로를 유지하지 않고 다음처럼 변경한다.

- `/jd/internal/job-contexts` → 유지
- `/jd/internal/job-contexts/{id}/analyses` → 유지
- `/jd/internal/job-contexts/{id}/analysis-jobs` → 유지
- `/jd/internal/analysis-jobs/{id}` → 유지
- `/jd/internal/conversations...` → 유지
- `/jd/internal/jd/analyze` → `/jd/internal/analyses`

`/health`와 `/docs`는 버전 리소스가 아니므로 각 앱 루트에 유지한다.

## 검증 범위

- FastAPI 요청 검증 및 경로 테스트
- 프롬프트가 JD·기업·뉴스를 근거로 요구하지 않는지 단위 테스트
- 원문 인용과 offset 위조 거부 테스트
- 첫 턴과 후속 턴 메시지 구성 테스트
- Qwen 잘못된 JSON에 대한 1회 재시도 테스트
- Spring 포지션 분기, 대화 이력 전달, 성공·실패 저장 테스트
- 기존 멀티에이전트 턴 격리 회귀 테스트
- 기존 60개 DRAFT 평가 케이스는 회귀 자료로만 사용하고 공식 성능 수치로 발표하지 않는다.

## 제외 범위

- LoRA 학습 및 어댑터 병합
- `recuse/resume-jd-match-kr`를 온라인 RAG로 사용
- 프론트엔드 화면 변경
- 백엔드 이외 직무 프로필 추가
- 스트리밍 응답
- 전체 JD 분석 파이프라인의 기능 변경

## 재검토 조건

프롬프트 기반 구현이 사람이 승인한 평가셋에서 반복적으로 일반적인 질문만 만들거나,
누락 요소 판정 정확도가 목표에 못 미치고 프롬프트 수정으로 개선되지 않을 때 LoRA를
재검토한다. 그때도 기업·JD 에이전트와 모델 가중치를 공유하지 않고 요청별 포지션
어댑터를 선택한다.
