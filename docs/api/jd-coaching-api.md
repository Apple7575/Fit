# JD 분석 내부 API 명세 — 1차 Spring 연동 범위

## 역할과 연결 경계

이번 연동은 **채용공고 URL 추출 → JD 컨텍스트 등록 → 사용자 자료 동기 분석 → 무상태 JD 후속 대화**를 다룬다. 기존 상태 저장형 JD 대화 API는 호환성을 위해 유지하지만, Spring 검토방은 새 무상태 API를 사용한다.

```text
브라우저 → Spring Boot → FastAPI JD → 공고 URL / PostgreSQL / Qwen
```

Spring은 사용자 인증·권한, 지원 세션과 자소서 연결, 추출 결과 및 `context_id` 보관, 분석 결과·대화 이력의 저장과 화면 노출을 담당한다. Spring 검토방은 이미 턴을 백그라운드에서 실행하므로, **Spring 작업 스레드가 JD 분석·후속 대화 API를 동기로 호출**한다. FastAPI의 추출 전용 API는 저장·Qwen 호출을 하지 않는다. JD 컨텍스트 등록과 분석 API는 AI 서버의 PostgreSQL·Qwen을 사용하고, 무상태 대화 API는 AI DB에 메시지를 저장하지 않는다.

## 엔드포인트

| 목적 | 메서드 | 통합 서버 경로 | 성공 |
| --- | --- | --- | --- |
| URL 본문·메타데이터 추출 | `POST` | `/jd/internal/job-sources/from-url` | `200` |
| 추출한 텍스트로 JD 컨텍스트 등록 | `POST` | `/jd/internal/job-contexts` | `201` |
| JD-사용자 자료 동기 분석 | `POST` | `/jd/internal/job-contexts/{context_id}/analyses` | `200` |
| 무상태 JD 후속 메시지 | `POST` | `/jd/internal/messages` | `200` |

JD 앱 자체 경로는 `/internal/...`이고, 통합 FastAPI 진입점 `ai/serve.py`가 `/jd` 접두어로 마운트한다. 아래 `{AI_SERVICE_BASE_URL}`은 통합 서버 주소이며 `/jd`를 포함하지 않는다. 프록시 환경에서는 주소 앞에 `/ai`가 붙을 수 있다. 내부 API는 별도 인증 헤더 검사가 없으므로 외부에 직접 공개하면 안 된다.

## 1. URL 본문·메타데이터 추출

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/job-sources/from-url
Content-Type: application/json
```

```json
{"url": "https://careers.example.com/jobs/123"}
```

| 필드 | 필수 | 제한 | 의미 |
| --- | --- | --- | --- |
| `url` | 예 | 절대 HTTP·HTTPS URL, 1~2,000자 | 사용자가 제공한 공고 주소 |

다른 요청 필드는 `422`로 거절한다. 기존 `ingestor.from_url()`을 사용하며, HTML·XHTML·일반 텍스트 응답만 지원한다. 원본 최대 10 MiB, 추출 본문 10~100,000자다. 로컬·사설망 주소와 그곳으로 향하는 리다이렉트를 차단한다. JavaScript 실행 후 본문이 나타나는 공고는 추출에 실패할 수 있다.

### `200` 응답

```json
{
  "jd_text": "Python 기반 API 개발 경험이 필요합니다.",
  "source_url": "https://careers.example.com/jobs/123",
  "company_name": "예시기업",
  "position_name": "백엔드 개발자",
  "job_posting_id": "123",
  "published_at": "2026-09-01",
  "valid_until": "2026-09-30",
  "content_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

응답 필드는 정확히 위 8개다. 추출하지 못한 기업명·직무명·공고 ID·날짜는 `null`일 수 있다. `source_url`은 리다이렉트 후 최종 URL, `content_sha256`은 **원본 응답 바이트**의 SHA-256이다. 이 호출은 컨텍스트 생성·DB 저장·JD 구조화를 하지 않으므로 `context_id`가 없다.

## 2. JD 컨텍스트 등록

Spring이 추출 결과를 확인하고, 분석에 사용할 JD를 등록한다. `company_name`과 `position_name`이 추출되지 않았다면 사용자 입력 등으로 채워야 한다.

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/job-contexts
Content-Type: application/json
```

```json
{
  "company_name": "예시기업",
  "position_name": "백엔드 개발자",
  "jd_text": "Python 기반 API 개발 경험이 필요합니다.",
  "job_posting_id": "123",
  "source_url": "https://careers.example.com/jobs/123",
  "published_at": "2026-09-01",
  "valid_until": "2026-09-30",
  "source_type": "OFFICIAL_CAREERS_SITE"
}
```

| 필드 | 필수 | 제한 | 의미 |
| --- | --- | --- | --- |
| `company_name` | 예 | 공백 제외 1~100자 | 기업명 |
| `position_name` | 예 | 공백 제외 1~200자 | 직무명 |
| `jd_text` | 예 | 공백 제외 10~100,000자 | 추출한 공고 본문 |
| `job_posting_id` | 아니오 | 1~200자 | 공고 식별자 |
| `source_url` | 아니오 | 절대 HTTP·HTTPS URL, 최대 2,000자 | 추출 결과의 최종 URL |
| `published_at`, `valid_until`, `retrieved_at` | 아니오 | `YYYY-MM-DD` | 게시·마감·수집일; 마감일은 게시일 이전 불가 |
| `source_type` | 아니오 | `USER_PROVIDED_JOB_POSTING`(기본), `OFFICIAL_CAREERS_SITE`, `RECRUITMENT_PLATFORM` | JD 출처 |

### `201` 응답

```json
{
  "context_id": "jctx_abc123",
  "company_name": "예시기업",
  "position_name": "백엔드 개발자",
  "jd_text": "Python 기반 API 개발 경험이 필요합니다.",
  "requirements": [
    {
      "role_element_id": "role-001",
      "name": "Python 기반 API 개발",
      "source_quote": "Python 기반 API 개발 경험이 필요합니다.",
      "evidence_section_ids": ["section-001"],
      "evidence_logic": "ALL",
      "evidence_requirements": [
        {"evidence_requirement_id": "evidence-001", "description": "Python 기반 API 구현 경험"}
      ]
    }
  ],
  "created_at": "2026-09-16T00:00:00+00:00",
  "job_posting_id": "123",
  "source_url": "https://careers.example.com/jobs/123",
  "published_at": "2026-09-01",
  "valid_until": "2026-09-30",
  "retrieved_at": null,
  "source_type": "OFFICIAL_CAREERS_SITE",
  "version": 1,
  "source_filename": null,
  "source_content_sha256": null,
  "cache_hit": false,
  "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
}
```

위 값은 **필드 구조 예시**이며 실제 `requirements`는 구조화된 JD 요구사항(최대 8개), `usage`는 실제 모델 사용량이다. 동일한 컨텍스트가 재사용되면 `cache_hit: true`일 수 있다. Spring은 `context_id`를 자기 지원 세션에 연결하고 접근 권한을 검사한다.

**현재 계약의 제약:** 1번의 `content_sha256`은 이 등록 API의 입력 필드가 아니다. AI 컨텍스트에 전달하려고 `source_content_sha256`을 추가하면 `422`가 나므로, 해시가 필요하면 Spring이 별도로 보관해야 한다.

## 3. JD-사용자 자료 동기 분석

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/job-contexts/{context_id}/analyses
Content-Type: application/json
```

```json
{
  "documents": [
    {
      "document_id": "cover-letter-item-12",
      "document_type": "SELF_INTRO",
      "text": "팀 프로젝트에서 서비스를 개발하고 기능을 개선했습니다."
    }
  ]
}
```

| 필드 | 필수 | 제한 | 의미 |
| --- | --- | --- | --- |
| `context_id` | 예 | URL 경로의 기존 JD 컨텍스트 ID | 분석 기준 JD |
| `documents` | 예 | 1~20개 | 사용자 원문 자료 |
| `documents[].document_id` | 예 | 요청 안에서 고유한 1~100자 | 원문 식별자 |
| `documents[].document_type` | 예 | `RESUME`, `SELF_INTRO`, `EXPERIENCE`, `PORTFOLIO` | 자료 유형 |
| `documents[].text` | 예 | 10~50,000자 | 사용자 원문 |

### `200` 응답

```json
{
  "context_id": "jctx_abc123",
  "company_name": "예시기업",
  "position_name": "백엔드 개발자",
  "requirements": [
    {
      "requirement_id": "role-001",
      "requirement": "Python 기반 API 개발",
      "jd_quote": "Python 기반 API 개발 경험이 필요합니다.",
      "evidence_logic": "ALL",
      "label": "NOT_SUPPORTED",
      "present_evidence": [],
      "missing_evidence": [
        {"evidence_requirement_id": "evidence-001", "description": "Python 기반 API 구현 경험"}
      ],
      "feedback": "Python 기반 API 구현 경험을 확인할 수 없습니다.",
      "suggested_actions": ["직접 구현한 API와 사용한 기술을 구체적으로 작성하세요."],
      "follow_up_questions": ["Python으로 구현한 API가 있나요?"]
    }
  ],
  "failed_requirements": [],
  "summary": {"supported": 0, "partially_supported": 0, "not_supported": 1, "failed": 0},
  "model": "Qwen 모델명",
  "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
}
```

응답에 `analysis_id`나 작업 `status`는 없다. 일부 요구사항만 실패해도 분석 응답은 `200`일 수 있으므로 `failed_requirements`와 `summary.failed`를 확인한다. Spring은 이 결과를 자기 턴 결과로 저장하고 화면에 전달한다. **AI API를 폴링할 필요는 없지만**, 브라우저가 Spring 턴 진행 상태를 확인하는 기존 흐름은 유지된다. JD 요구사항별 Qwen 호출에 시간이 걸릴 수 있으므로 Spring→FastAPI HTTP 타임아웃을 실제 처리 시간에 맞게 설정해야 한다.

## 4. 무상태 JD 후속 메시지

Spring이 저장한 기준 분석 결과, **현재 자소서 원문**, 필요한 이전 사용자·에이전트 발화를 매 요청에 보낸다. 이 API는 `conversation_id`·`analysis_id`를 받지 않고 메시지를 AI DB에 저장하지 않는다. 다만 `context_id`로 JD 컨텍스트는 AI DB에서 조회한다.

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/messages
Content-Type: application/json
```

```json
{
  "context_id": "jctx_abc123",
  "analysis_result": {
    "context_id": "jctx_abc123",
    "summary": {"supported": 0, "partially_supported": 1, "not_supported": 0, "failed": 0},
    "requirements": [{"requirement_id": "role-001", "requirement": "Python 기반 API 개발"}]
  },
  "current_document": {
    "document_id": "cover-letter-item-12",
    "text": "팀 프로젝트에서 Python API를 개발하고 서비스를 배포했습니다."
  },
  "message": "배포 경험을 어떻게 더 구체적으로 쓸까?",
  "history": [
    {"role": "user", "content": "직무 적합성이 드러나?"},
    {"role": "assistant", "content": "배포 결과를 보완하면 좋아요."}
  ]
}
```

| 필드 | 필수 | 제한 | 의미 |
| --- | --- | --- | --- |
| `context_id` | 예 | 1~80자 | 이미 등록된 JD 컨텍스트 ID |
| `analysis_result` | 예 | `context_id`, `summary` 객체, `requirements` 배열 포함 | 앞선 동기 분석 API 응답. 내부 `context_id`가 요청 값과 같아야 함 |
| `current_document.document_id` | 예 | 1~100자 | 현재 자소서 문항 식별자 |
| `current_document.text` | 예 | 공백 제외 10~50,000자 | **현재 버전** 자소서 원문 |
| `message` | 예 | 공백 제외 1~10,000자 | 이번 사용자 질문 |
| `history` | 아니오 | 최대 20개, 기본 `[]` | 이전 발화. 오래된 순서로 `user`·`assistant` 모두 포함 |
| `history[].role` | 예 | `user` 또는 `assistant` | 발화 주체 |
| `history[].content` | 예 | 공백 제외 1~10,000자 | 발화 내용 |

Spring은 분석 응답 전체를 보관하고 `analysis_result`로 다시 보내는 것이 안전하다. 분석 이후 자소서가 수정됐으면 `current_document.text`에는 수정된 원문을 보낸다. 이때 기준 분석은 이전 버전의 결과일 수 있으므로 최신 적합성 판정이 필요하면 분석 API를 다시 호출해야 한다.

### `200` 응답

```json
{
  "answer": "배포에서 맡은 역할과 성과를 구체적으로 적어 보세요.",
  "referenced_requirement_ids": ["role-001"],
  "follow_up_questions": ["배포 후 확인한 성과 지표가 있나요?"],
  "model": "Qwen 모델명",
  "usage": {"prompt_tokens": 1000, "completion_tokens": 300, "total_tokens": 1300}
}
```

Spring이 이 응답과 사용자 질문을 검토방에 저장하고, 다음 요청의 `history`에 필요한 이력만 넣는다. 동일 요청 재시도 시 모델을 다시 호출하므로 턴 중복 저장 방지는 Spring이 맡는다. 기존 `/jd/internal/conversations/...` 경로는 변경하지 않았다.

## 오류와 호출 정책

| 상태 | 의미 |
| --- | --- |
| `200` / `201` | 각 API의 성공 상태 |
| `404` | 존재하지 않는 `context_id` |
| `415` | URL 응답 형식 미지원 |
| `422` | 요청 형식·날짜 검증 또는 URL 본문 추출 실패 |
| `502` | URL 가져오기, JD 컨텍스트 구조화, 동기 분석 또는 대화 모델 처리 실패 |

무상태 대화에서 요청 필드가 없거나 형식이 잘못되면 `422`, 분석 결과의 `context_id`가 다르면 `409`, JD 컨텍스트가 없으면 `404`다. 모델이 알 수 없는 `requirement_id`를 인용하는 등 출력 검증에 실패하면 `502`다.

동기 분석의 요청 스키마 오류는 `422`다. 문서 ID 중복 등 서비스 단계의 의미 검증 오류는 현재 구현상 `502`로 매핑된다. FastAPI 기본 오류 본문은 `{"detail": ...}` 형태다. Spring이 호출 제한 시간을 넘기거나 연결이 끊기면 해당 Spring 턴을 실패 처리할 정책이 필요하다.

## Spring 연동 시 필요한 결정

1. Spring은 1번 결과의 기업명·직무명을 확인하고, 누락 시 사용자 입력으로 채운 다음 2번을 호출한다.
2. `content_sha256`이 필요하면 Spring이 보관한다. 현행 2번 API로는 AI 컨텍스트에 전달할 수 없다.
3. `context_id`를 Spring의 지원 세션에 연결하고 소유권을 확인한다. AI API 자체는 사용자 ID를 받지 않는다.
4. Spring의 백그라운드 턴 안에서 3번을 동기로 호출한다. AI 작업 ID·상태 조회는 필요 없으며, 화면과 총괄에서 JD 근거를 활용할 경우 분석 응답 전체를 보존한다.
5. JD 후속 대화에는 4번 API를 사용한다. Spring이 분석 결과·현재 자소서·이전 사용자 및 에이전트 발화를 전달하고, 반환된 답변을 저장한다.

## 관련 구현

- 통합 마운트: `ai/serve.py`
- 요청·응답 및 라우트: `ai/jd_coaching/api.py`
- URL 추출·SSRF 방어: `ai/jd_coaching/source_ingestion.py`
- JD 구조화·분석: `ai/jd_coaching/service.py`
- 무상태 JD 대화: `ai/jd_coaching/chat.py`
- 상세 JD 응답 스키마: `ai/docs/jd-coaching-api-spec.md`
- Spring의 JD FastAPI HTTP 클라이언트 및 검토방 연동: 미구현
