# JD 직무 분석·코칭 내부 API 명세

## 1. 문서 정보

| 항목 | 값 |
|---|---|
| API 이름 | JD Essay Coaching Internal API |
| 버전 | `v1` |
| 기본 경로 | `/internal` |
| 호출 주체 | Spring 백엔드 |
| 인증 | 아직 구현되지 않음. 배포 시 내부망 제한 또는 서비스 인증 필요 |
| 기본 요청 형식 | `application/json` |
| 파일 요청 형식 | `multipart/form-data` |
| 문자 인코딩 | UTF-8 |

브라우저가 FastAPI를 직접 호출하지 않는다. Spring이 사용자 인증, 지원 세션 소유권, 원본 파일 저장과 공개 API를 담당하고 FastAPI의 내부 API를 호출한다.

## 2. 전체 호출 흐름

```text
1. JD 등록
   POST /job-contexts
   또는 /job-contexts/from-url
   또는 /job-contexts/from-file
       ↓ context_id

2. 비동기 직무 연결 분석
   POST /job-contexts/{context_id}/analysis-jobs
       ↓ analysis_id, QUEUED

3. 분석 상태 조회
   GET /analysis-jobs/{analysis_id}
       ↓ COMPLETED + result

4. 지속 대화 생성
   POST /conversations
       ↓ conversation_id

5. 후속 대화
   POST /conversations/{conversation_id}/messages
```

서비스 화면에서는 비동기 분석 API 사용을 권장한다. 동기 분석 API는 내부 확인이나 처리 시간이 짧은 요청에만 사용한다.

## 3. 식별자와 저장 책임

| 식별자 | 생성 주체 | Spring에서 할 일 |
|---|---|---|
| `context_id` | FastAPI | 지원 세션의 JD 컨텍스트로 저장 |
| `analysis_id` | FastAPI | 분석 이력 또는 최신 분석 ID로 저장 |
| `conversation_id` | FastAPI | 지원 세션의 대화 ID로 저장 |
| `client_message_id` | Spring | 메시지 재전송 중복 방지를 위한 고유 ID 생성 |

FastAPI에는 `user_id`를 전달하지 않는다. ID가 현재 사용자의 지원 세션에 속하는지는 Spring이 검사한다.

## 4. 공통 열거형

### JD 출처 유형

| 값 | 의미 |
|---|---|
| `USER_PROVIDED_JOB_POSTING` | 사용자가 직접 제공한 공고 |
| `OFFICIAL_CAREERS_SITE` | 기업 공식 채용 사이트 |
| `RECRUITMENT_PLATFORM` | 외부 채용 플랫폼 |

### 사용자 문서 유형

| 값 | 의미 |
|---|---|
| `RESUME` | 이력서 |
| `SELF_INTRO` | 자기소개서 |
| `EXPERIENCE` | 별도 경험 기술 |
| `PORTFOLIO` | 포트폴리오 텍스트 |

### 연결 라벨

| 값 | 의미 |
|---|---|
| `SUPPORTED` | 요구사항을 입증할 필요 근거가 모두 확인됨 |
| `PARTIALLY_SUPPORTED` | 일부 필요 근거만 확인됨 |
| `NOT_SUPPORTED` | 확인할 수 있는 필요 근거가 없음 |

### 비동기 분석 상태

| 값 | 의미 |
|---|---|
| `QUEUED` | 실행 대기 |
| `RUNNING` | 분석 중 |
| `COMPLETED` | 분석 완료 |
| `FAILED` | 분석 실패 |

## 5. 공통 응답 구조

### JD 컨텍스트

```json
{
  "context_id": "jctx_abc123",
  "company_name": "삼성전자",
  "position_name": "백엔드 개발",
  "jd_text": "Python 기반 API 개발 경험...",
  "requirements": [
    {
      "role_element_id": "role-001",
      "name": "Python 기반 API 개발",
      "source_quote": "Python 기반 API 개발 경험이 필요합니다.",
      "evidence_section_ids": ["section-001"],
      "evidence_logic": "ALL",
      "evidence_requirements": [
        {
          "evidence_requirement_id": "evidence-001",
          "description": "Python을 사용해 API를 구현한 행동"
        }
      ]
    }
  ],
  "created_at": "2026-09-14T00:00:00+00:00",
  "job_posting_id": "posting-123",
  "source_url": "https://careers.example.com/jobs/123",
  "published_at": "2026-09-01",
  "valid_until": "2026-09-30",
  "retrieved_at": "2026-09-14",
  "source_type": "OFFICIAL_CAREERS_SITE",
  "version": 1,
  "source_filename": null,
  "source_content_sha256": "64자리 SHA-256 또는 null",
  "cache_hit": false,
  "usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total_tokens": 1500
  }
}
```

`requirements`는 JD에서 추출된 최대 8개 요구사항이다. 동일한 JD 원문이 이미 등록되어 있으면 기존 `context_id`를 반환하고 `cache_hit`가 `true`가 된다.

### 직무 연결 분석 결과

```json
{
  "context_id": "jctx_abc123",
  "company_name": "삼성전자",
  "position_name": "백엔드 개발",
  "requirements": [
    {
      "requirement_id": "role-001",
      "requirement": "Python 기반 API 개발",
      "jd_quote": "Python 기반 API 개발 경험이 필요합니다.",
      "evidence_logic": "ALL",
      "label": "PARTIALLY_SUPPORTED",
      "present_evidence": [
        {
          "evidence_requirement_id": "evidence-001",
          "evidence_quote": "FastAPI로 주문 조회 API를 구현했습니다.",
          "document_id": "essay-1",
          "document_type": "SELF_INTRO",
          "start_offset": 10,
          "end_offset": 34
        }
      ],
      "missing_evidence": [
        {
          "evidence_requirement_id": "evidence-002",
          "description": "API 운영 또는 개선 결과"
        }
      ],
      "feedback": "API 운영 또는 개선 결과를 보완해 주세요.",
      "suggested_actions": [
        "API 운영 또는 개선 결과를 보여주는 행동이나 성과를 추가하세요."
      ],
      "follow_up_questions": [
        "배포 후 오류나 성능 문제를 해결한 경험이 있나요?"
      ]
    }
  ],
  "failed_requirements": [],
  "summary": {
    "supported": 0,
    "partially_supported": 1,
    "not_supported": 0,
    "failed": 0
  },
  "model": "Qwen 모델명",
  "usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total_tokens": 1500
  }
}
```

`start_offset`은 0부터 시작하고 `end_offset`은 인용문 다음 위치다. 원문 강조 범위는 `text[start_offset:end_offset]`로 계산한다.

## 6. API 상세

### 6.1 상태 확인

```http
GET /health
```

응답 `200 OK`:

```json
{"status": "ok"}
```

현재 응답은 FastAPI 프로세스 상태만 의미한다. PostgreSQL과 Qwen 연결 상태까지 검사하지 않는다.

### 6.2 JD 텍스트 등록

```http
POST /internal/job-contexts
Content-Type: application/json
```

요청:

```json
{
  "company_name": "삼성전자",
  "position_name": "백엔드 개발",
  "jd_text": "Python과 FastAPI를 활용한 API 개발 경험이 필요합니다.",
  "job_posting_id": "posting-123",
  "source_url": "https://careers.example.com/jobs/123",
  "published_at": "2026-09-01",
  "valid_until": "2026-09-30",
  "retrieved_at": "2026-09-14",
  "source_type": "OFFICIAL_CAREERS_SITE"
}
```

| 필드 | 필수 | 제한 |
|---|---|---|
| `company_name` | 예 | 1~100자 |
| `position_name` | 예 | 1~200자 |
| `jd_text` | 예 | 10~50,000자 |
| `job_posting_id` | 아니오 | 최대 200자 |
| `source_url` | 아니오 | 절대 HTTP·HTTPS URL, 최대 2,000자 |
| `published_at` | 아니오 | `YYYY-MM-DD` |
| `valid_until` | 아니오 | `YYYY-MM-DD`, 게시일 이전 불가 |
| `retrieved_at` | 아니오 | `YYYY-MM-DD` |
| `source_type` | 아니오 | 기본값 `USER_PROVIDED_JOB_POSTING` |

성공: `201 Created`, JD 컨텍스트 반환.

### 6.3 URL에서 JD 등록

```http
POST /internal/job-contexts/from-url
Content-Type: application/json
```

요청:

```json
{
  "url": "https://careers.example.com/jobs/123",
  "company_name": "삼성전자",
  "position_name": "백엔드 개발",
  "job_posting_id": "posting-123",
  "source_type": "OFFICIAL_CAREERS_SITE"
}
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `url` | 예 | 외부 HTTP·HTTPS URL, 최대 2,000자 |
| `company_name` | 조건부 | JSON-LD에서 추출하지 못하면 필요 |
| `position_name` | 조건부 | JSON-LD에서 추출하지 못하면 필요 |
| `job_posting_id` | 아니오 | 요청값이 URL 메타데이터보다 우선 |
| `source_type` | 아니오 | 기본값 `USER_PROVIDED_JOB_POSTING` |

URL 응답은 최대 10MiB이며 HTML, XHTML, 일반 텍스트만 지원한다. Schema.org `JobPosting` JSON-LD가 있으면 기업명, 직무명, 공고 ID, 게시일과 마감일을 추출한다.

JavaScript 실행 후 본문이 나타나는 페이지는 지원하지 않는다. 이런 경우 파일 또는 직접 입력을 사용한다.

성공: `201 Created`, JD 컨텍스트 반환.

### 6.4 파일에서 JD 등록

```http
POST /internal/job-contexts/from-file
Content-Type: multipart/form-data
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `company_name` | 예 | 1~100자 |
| `position_name` | 예 | 1~200자 |
| `file` | 예 | 최대 10MiB |
| `job_posting_id` | 아니오 | 최대 200자 |
| `published_at` | 아니오 | `YYYY-MM-DD` |
| `valid_until` | 아니오 | `YYYY-MM-DD` |

사용자에게 공개할 파일 형식은 PDF, DOCX, TXT다. MD와 HTML은 내부 호환 형식으로만 사용한다. 이미지 기반 스캔 PDF는 OCR이 없어 처리할 수 없다.

성공: `201 Created`, JD 컨텍스트 반환. AI 서비스는 원본 파일을 저장하지 않고 추출된 텍스트, 파일명과 SHA-256만 저장한다.

### 6.5 JD 컨텍스트 조회

```http
GET /internal/job-contexts/{context_id}
```

성공: `200 OK`, JD 컨텍스트 반환.

존재하지 않으면 `404 Not Found`:

```json
{"detail": "지원 컨텍스트가 없습니다."}
```

### 6.6 동기 직무 연결 분석

```http
POST /internal/job-contexts/{context_id}/analyses
Content-Type: application/json
```

요청:

```json
{
  "documents": [
    {
      "document_id": "essay-1",
      "document_type": "SELF_INTRO",
      "text": "FastAPI로 주문 조회 API를 구현했습니다."
    }
  ]
}
```

| 필드 | 제한 |
|---|---|
| `documents` | 1~20개 |
| `document_id` | 요청 안에서 고유, 1~100자 |
| `document_type` | 사용자 문서 유형 열거형 |
| `text` | 10~50,000자 |

성공: `200 OK`, 직무 연결 분석 결과 반환.

### 6.7 비동기 직무 연결 분석 생성

```http
POST /internal/job-contexts/{context_id}/analysis-jobs
Content-Type: application/json
```

요청은 동기 분석과 동일하다.

응답 `202 Accepted`:

```json
{
  "analysis_id": "analysis_abc123",
  "context_id": "jctx_abc123",
  "status": "QUEUED",
  "result": null,
  "error": null,
  "created_at": "2026-09-14T00:00:00+00:00",
  "updated_at": "2026-09-14T00:00:00+00:00"
}
```

### 6.8 분석 상태 조회

```http
GET /internal/analysis-jobs/{analysis_id}
```

분석 중 응답:

```json
{
  "analysis_id": "analysis_abc123",
  "context_id": "jctx_abc123",
  "status": "RUNNING",
  "result": null,
  "error": null,
  "created_at": "2026-09-14T00:00:00+00:00",
  "updated_at": "2026-09-14T00:00:01+00:00"
}
```

완료되면 `status`가 `COMPLETED`가 되고 `result`에 직무 연결 분석 결과가 들어간다.

실패 응답의 `error` 예시:

```json
{
  "code": "ANALYSIS_FAILED",
  "message": "실패 원인"
}
```

### 6.9 지속 대화 생성

```http
POST /internal/conversations
Content-Type: application/json
```

요청:

```json
{
  "context_id": "jctx_abc123",
  "analysis_id": "analysis_abc123"
}
```

완료된 분석만 사용할 수 있으며 `analysis_id`와 `context_id`가 서로 일치해야 한다.

응답 `201 Created`:

```json
{
  "conversation_id": "conv_abc123",
  "context_id": "jctx_abc123",
  "analysis_id": "analysis_abc123",
  "created_at": "2026-09-14T00:00:00+00:00",
  "updated_at": "2026-09-14T00:00:00+00:00",
  "messages": []
}
```

### 6.10 대화 메시지 전송

```http
POST /internal/conversations/{conversation_id}/messages
Content-Type: application/json
```

요청:

```json
{
  "client_message_id": "spring-message-123",
  "content": "내 경험에서 무엇을 먼저 보완해야 해?"
}
```

| 필드 | 제한 |
|---|---|
| `client_message_id` | 대화 안에서 고유, 1~100자 |
| `content` | 1~10,000자 |

같은 `client_message_id`와 같은 내용을 재전송하면 기존 답변을 반환한다. 같은 ID로 다른 내용을 보내면 `409 Conflict`다.

응답 `200 OK`:

```json
{
  "user_message": {
    "message_id": "msg_user",
    "role": "USER",
    "content": "내 경험에서 무엇을 먼저 보완해야 해?",
    "client_message_id": "spring-message-123",
    "reply_to_message_id": null,
    "metadata": {},
    "created_at": "2026-09-14T00:01:00+00:00",
    "sequence_no": 1
  },
  "assistant_message": {
    "message_id": "msg_assistant",
    "role": "ASSISTANT",
    "content": "API 운영 결과를 먼저 보완해 주세요.",
    "client_message_id": null,
    "reply_to_message_id": "msg_user",
    "metadata": {
      "referenced_requirement_ids": ["role-001"],
      "follow_up_questions": [
        "배포 후 문제를 해결한 경험이 있나요?"
      ],
      "model": "Qwen 모델명",
      "usage": {"total_tokens": 500}
    },
    "created_at": "2026-09-14T00:01:05+00:00",
    "sequence_no": 2
  }
}
```

### 6.11 대화 조회

```http
GET /internal/conversations/{conversation_id}
```

대화 정보와 `messages`를 `sequence_no` 오름차순으로 반환한다.

### 6.12 대화 삭제

```http
DELETE /internal/conversations/{conversation_id}
```

성공: `204 No Content`. 대화에 속한 AI 메시지도 함께 삭제한다.

Spring에서 지원 세션이나 채팅방을 삭제할 때 호출한다.

### 6.13 단일 호출 호환 API

```http
POST /internal/jd/analyze
Content-Type: application/json
```

```json
{
  "company_name": "삼성전자",
  "position_name": "백엔드 개발",
  "jd_text": "Python 기반 API 개발 경험이 필요합니다.",
  "applicant_text": "FastAPI로 주문 조회 API를 구현했습니다."
}
```

JD 등록과 단일 사용자 글 분석을 한 번에 수행한다. 서비스 화면에서는 컨텍스트와 비동기 분석 API를 권장한다.

## 7. 오류 응답

FastAPI 오류는 기본적으로 다음 형태다.

```json
{"detail": "오류 설명"}
```

| 상태 코드 | 의미 | 대표 상황 |
|---:|---|---|
| `404` | 리소스 없음 | `context_id`, `analysis_id`, `conversation_id`가 없음 |
| `409` | 현재 상태와 충돌 | 미완료 분석으로 대화 생성, ID 관계 불일치, 메시지 ID 재사용 |
| `415` | 지원하지 않는 입력 형식 | 이미지 파일, 지원하지 않는 URL 응답 형식 |
| `422` | 요청 검증 또는 추출 실패 | 필수 필드 누락, 날짜 오류, 본문 부족, 스캔 PDF |
| `502` | AI 또는 외부 입력 처리 실패 | Qwen 호출 실패, URL 다운로드 실패, JD 구조화 실패 |

`422`는 Pydantic 필드 검증 오류일 경우 다음 배열 형태를 사용할 수 있다.

```json
{
  "detail": [
    {
      "loc": ["body", "company_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

## 8. Spring 연동 요구사항

Spring은 다음 사항을 구현해야 한다.

1. 로그인 사용자와 지원 세션의 소유권을 확인한다.
2. 원본 JD 파일과 사용자 문서를 관리한다.
3. FastAPI가 반환한 `context_id`, `analysis_id`, `conversation_id`를 지원 세션에 연결한다.
4. 비동기 분석이 `COMPLETED` 또는 `FAILED`가 될 때까지 상태를 조회한다.
5. 브라우저에 내부 AI ID를 그대로 노출할지 별도 공개 ID로 감쌀지 결정한다.
6. 메시지마다 고유한 `client_message_id`를 생성한다.
7. 지원 세션 삭제 시 대화 삭제 API를 호출한다.
8. FastAPI 호출 타임아웃과 재시도 정책을 둔다.

## 9. 현재 운영 제한

- 분석 작업은 FastAPI `BackgroundTasks`를 사용하므로 프로세스 재시작 후 자동 복구되지 않는다.
- `/health`는 PostgreSQL과 Qwen 상태를 확인하지 않는다.
- 내부 API 인증이 아직 없다.
- URL 입력은 JavaScript 렌더링을 지원하지 않는다.
- 스캔 PDF OCR을 지원하지 않는다.
- 지속 대화는 최근 20개 메시지만 Qwen에 전달하며 대화 요약 기능은 없다.
- 실제 PostgreSQL에 V20·V21을 적용한 통합 테스트는 아직 완료되지 않았다.
- 일부 응답이 FastAPI 코드에서 명시적 Pydantic 응답 모델로 선언되지 않아 자동 OpenAPI 문서의 응답 스키마가 상세하지 않다.

## 10. 관련 문서

- [JD 입력 방식](./jd-input-sources.md)
- [JD 코칭 지속 대화](./jd-coaching-conversation-api.md)
- [JD 분석 기준선과 평가 결과](./jd-essay-coaching-baseline.md)
- [Spring과 FastAPI 경계](../../Decisions/product/jd-api-boundary.md)
