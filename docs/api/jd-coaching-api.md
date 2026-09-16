# JD 코칭 내부 API 명세

## 역할과 연결 경계

JD 담당은 채용공고의 요구사항을 구조화하고, 사용자가 작성한 자소서·이력서 등에서 각 요구사항을 뒷받침하는 근거를 분석한다. URL 본문 추출만 필요한 백엔드를 위해 `job-sources/from-url`을 별도로 제공한다.

```text
브라우저 → Spring Boot → FastAPI JD → 채용공고 URL / PostgreSQL / Qwen
```

Spring은 인증·권한, 지원 세션 및 자소서 연결, 내부 AI ID 보관, 화면용 결과 저장을 담당한다. JD FastAPI는 URL 추출, JD 컨텍스트·분석·JD 후속 대화의 상태를 관리한다. 포지션 API와 달리 **JD 분석·대화 경로는 무상태가 아니다.** 새 추출 전용 경로만 DB와 Qwen을 사용하지 않는다.

## 엔드포인트

| 목적 | 메서드 | 통합 서버 경로 | 성공 |
| --- | --- | --- | --- |
| URL에서 본문·메타데이터만 추출 | `POST` | `/jd/internal/job-sources/from-url` | `200` |
| 추출 결과/직접 입력으로 JD 컨텍스트 등록 | `POST` | `/jd/internal/job-contexts` | `201` |
| URL 추출과 JD 컨텍스트 등록을 한 번에 수행 | `POST` | `/jd/internal/job-contexts/from-url` | `201` |
| 파일에서 JD 컨텍스트 등록 | `POST` | `/jd/internal/job-contexts/from-file` | `201` |
| JD 컨텍스트 조회 | `GET` | `/jd/internal/job-contexts/{context_id}` | `200` |
| JD-사용자 자료 동기 분석 | `POST` | `/jd/internal/job-contexts/{context_id}/analyses` | `200` |
| JD-사용자 자료 비동기 분석 시작 | `POST` | `/jd/internal/job-contexts/{context_id}/analysis-jobs` | `202` |
| 비동기 분석 상태·결과 조회 | `GET` | `/jd/internal/analysis-jobs/{analysis_id}` | `200` |
| JD 후속 대화 생성 | `POST` | `/jd/internal/conversations` | `201` |
| JD 후속 메시지 전송 | `POST` | `/jd/internal/conversations/{conversation_id}/messages` | `200` |
| JD 대화 조회/삭제 | `GET` / `DELETE` | `/jd/internal/conversations/{conversation_id}` | `200` / `204` |
| 프로세스 상태 | `GET` | `/jd/health` | `200` |

JD 앱 자체의 경로는 `/internal/...`, `/health`다. 통합 FastAPI 진입점 `ai/serve.py`가 `/jd`에 마운트한다. 아래는 통합 서버 기준이며 `{AI_SERVICE_BASE_URL}`에는 `/jd`나 `/ai`를 중복해서 붙이지 않는다. 내부 API에 별도 인증 헤더 검사는 없으므로 외부에 직접 공개하지 않아야 한다.

백엔드가 **공고 원문을 먼저 받아야 하는 현재 요청**에는 아래 흐름을 권장한다.

```text
job-sources/from-url → Spring에서 추출 결과·메타데이터 확인/저장
                     → job-contexts → analysis-jobs → analysis-jobs/{analysis_id}
                     → (JD 후속 대화가 필요할 때만) conversations → messages
```

기존 `job-contexts/from-url`은 URL 추출과 등록을 한 번에 처리하는 **대체 경로**다. 위 첫 두 호출 뒤 다시 호출하면 URL을 중복으로 가져오므로 함께 사용할 필요가 없다.

## URL 본문 추출 요청

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/job-sources/from-url
Content-Type: application/json
```

```json
{"url": "https://careers.example.com/jobs/123"}
```

`url`은 필수 1~2,000자 절대 HTTP·HTTPS URL이다. 다른 요청 필드는 `422`로 거절한다. 기존 `ingestor.from_url()`을 호출하므로 HTML·XHTML·일반 텍스트를 최대 10 MiB까지 읽고, 추출 텍스트는 10~50,000자로 제한한다. 로컬·사설 주소와 해당 주소로의 리다이렉트는 차단한다. JavaScript 실행이 필요한 페이지는 본문 추출에 실패할 수 있다.

### 성공 응답 `200`

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

응답은 위 8개 필드다. `source_url`은 리다이렉트 후 최종 URL이며 `content_sha256`은 **원본 응답 바이트**의 SHA-256이다. 기업명·직무명·공고 ID·날짜 등 추출하지 못한 메타데이터는 `null`일 수 있다. 이 API는 `context_id`를 만들지 않으며 JD 구조화, DB 저장, Qwen 호출을 하지 않는다.

## JD 컨텍스트 등록 요청

추출 전용 API의 `jd_text`를 분석에 사용하려면 별도로 컨텍스트를 등록한다.

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

| 필드 | 필수 | 제한·의미 |
| --- | --- | --- |
| `company_name` | 예 | 공백 제외 1~100자 |
| `position_name` | 예 | 공백 제외 1~200자 |
| `jd_text` | 예 | 공백 제외 10~50,000자 |
| `job_posting_id` | 아니오 | 1~200자 |
| `source_url` | 아니오 | 절대 HTTP·HTTPS URL, 최대 2,000자 |
| `published_at`, `valid_until`, `retrieved_at` | 아니오 | `YYYY-MM-DD`; 마감일은 게시일 이전일 수 없음 |
| `source_type` | 아니오 | `USER_PROVIDED_JOB_POSTING`(기본), `OFFICIAL_CAREERS_SITE`, `RECRUITMENT_PLATFORM` |

성공 시 `201`로 `context_id`, 기업·직무·JD 원문, 구조화된 `requirements`, 출처 메타데이터, `cache_hit`, 모델 `usage` 등을 반환한다. `requirements`는 최대 8개다. 동일한 입력에 대한 컨텍스트가 있으면 기존 ID와 `cache_hit: true`가 반환될 수 있다. Spring은 `context_id`를 자기 지원 세션에 연결하고 소유권을 검사해야 한다.

**현재 계약의 주의점:** 추출 전용 API가 반환하는 `content_sha256`은 `POST /job-contexts`의 허용 입력 필드가 아니다. 이 두 단계 흐름을 택한다면 해시는 Spring에서 보관해야 하며, 임의로 `source_content_sha256`을 등록 요청에 넣으면 `422`가 난다. 원본 해시를 AI 컨텍스트에도 저장해야 한다면 별도 API 계약 변경이 필요하다.

대체 경로 `POST /jd/internal/job-contexts/from-url`은 `url`과 선택적 `company_name`, `position_name`, `job_posting_id`, `source_type`을 받는다. 직접 URL을 가져와 구조화·저장하고 `201`로 같은 컨텍스트 형태를 반환한다. URL 메타데이터가 없으면 기업명과 직무명을 요청에 제공해야 한다. 파일 등록 경로는 `multipart/form-data`로 `company_name`, `position_name`, `file`을 필수로 받는다. 두 대체 경로의 자세한 필드는 `ai/docs/jd-coaching-api-spec.md`를 참고한다.

## 분석 요청과 성공 응답

화면용 흐름은 비동기 분석을 권장한다. 동기 분석과 비동기 시작의 요청 본문은 동일하다.

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/job-contexts/{context_id}/analysis-jobs
Content-Type: application/json
```

```json
{
  "documents": [
    {
      "document_id": "cover-letter-item-12",
      "document_type": "SELF_INTRO",
      "text": "FastAPI로 주문 조회 API를 구현하고 응답 시간을 측정했습니다."
    }
  ]
}
```

| 필드 | 필수 | 제한·의미 |
| --- | --- | --- |
| `documents` | 예 | 1~20개. 사용자 원문 근거 |
| `documents[].document_id` | 예 | 요청 안에서 고유한 1~100자 |
| `documents[].document_type` | 예 | `RESUME`, `SELF_INTRO`, `EXPERIENCE`, `PORTFOLIO` |
| `documents[].text` | 예 | 10~50,000자 |

비동기 시작은 `202`로 `analysis_id`, `context_id`, `status: "QUEUED"`, `result: null`, `error: null`, 생성·갱신 시각을 반환한다. `GET /jd/internal/analysis-jobs/{analysis_id}`로 `QUEUED`/`RUNNING`/`COMPLETED`/`FAILED`를 조회한다. `COMPLETED`면 `result`에 JD 요구사항별 분석(`requirements`), 실패한 요구사항(`failed_requirements`), 요약 집계(`summary`), `model`, `usage`가 들어간다. 일부 요구사항 실패가 있어도 `result.failed_requirements`와 `summary.failed`를 확인해야 한다. `FAILED`면 `error.code`, `error.message`를 확인한다.

동기 `POST /jd/internal/job-contexts/{context_id}/analyses`는 같은 요청으로 분석 결과를 바로 `200`으로 반환한다. Spring HTTP 요청을 오래 붙잡지 않으려면 비동기 경로를 사용한다.

## JD 후속 대화 요청과 응답

JD의 후속 대화는 완료된 분석에 묶이는 **상태 저장형 API**다. 필요할 때만 아래 두 호출을 추가한다.

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/conversations
Content-Type: application/json
```

```json
{"context_id": "jctx_abc123", "analysis_id": "analysis_abc123"}
```

`context_id`와 `analysis_id`는 필수이며 서로 일치해야 하고, 분석 상태가 `COMPLETED`여야 한다. 성공 `201` 응답에 `conversation_id`, 두 ID, 생성·갱신 시각, 빈 `messages` 배열이 있다. 이후:

```http
POST {AI_SERVICE_BASE_URL}/jd/internal/conversations/{conversation_id}/messages
Content-Type: application/json
```

```json
{
  "client_message_id": "spring-message-480",
  "content": "제 경험에서 무엇을 먼저 보완해야 하나요?"
}
```

`client_message_id`는 1~100자이며 대화 안에서 중복 전송을 구분한다. `content`는 1~10,000자다. 성공 `200`은 `user_message`와 `assistant_message` 객체를 반환한다. 각 객체에는 `message_id`, `role`, `content`, `reply_to_message_id`, `metadata`, `created_at`, `sequence_no` 등이 있다. 같은 ID·같은 내용 재전송은 기존 답변을 반환하고, 같은 ID·다른 내용은 `409`다. Spring은 `conversation_id`를 지원 세션에 연결하고, 대화 삭제 시 `DELETE /jd/internal/conversations/{conversation_id}` 호출 여부를 정해야 한다.

검토방의 `agent_message`도 대화를 저장하므로, Spring 검토방과 이 상태 저장형 JD 대화를 함께 사용할 경우 **어느 저장소가 대화의 원본인지** 정해야 한다. JD 메시지 API는 이전 대화 배열을 요청마다 받지 않는다. 포지션·글쓰기 API의 무상태 `conversation` 필드와 혼동하면 안 된다.

## 오류와 호출 정책

| 상태 | 의미 |
| --- | --- |
| `200`/`201`/`202`/`204` | 경로별 성공 상태(위 표 참조) |
| `404` | 컨텍스트·분석 작업·대화를 찾을 수 없음 |
| `409` | 미완료 분석으로 대화 생성, ID 관계 불일치, 메시지 ID 충돌 |
| `415` | URL 응답 또는 업로드 파일 형식 미지원 |
| `422` | Pydantic 요청 형식 검증, URL 본문 추출, 날짜 형식 오류 |
| `502` | URL 가져오기, JD 구조화·동기 분석·대화 모델 호출 실패 |

`GET /jd/health`의 `200 {"status":"ok"}`는 프로세스 상태만 뜻한다. DB·Qwen 준비 상태까지 보장하지 않는다. URL 추출 전용 경로는 추출 오류를 `415`/`422`/`502`로 매핑하며 JD 컨텍스트 등록이나 Qwen 오류를 반환하지 않는다.

비동기 분석에서 문서 ID 중복 같은 의미 검증 오류가 작업 시작 후 발견되면 초기 요청은 `202`이고 이후 작업이 `FAILED`가 된다. 동기 분석 경로에서는 서비스의 `ValueError`도 현재 구현상 `502`로 매핑된다. 따라서 Spring은 HTTP 상태뿐 아니라 비동기 작업의 `status`와 `error`를 확인해야 한다.

## Spring 연동 시 필요한 결정

1. 원문 확인이 필요한 현재 요구에는 추출 전용 API → Spring의 기업명·직무명 확인 → 텍스트 등록 API를 사용한다. 추출된 기업명·직무명이 `null`이면 사용자 입력 등으로 채워야 등록할 수 있다.
2. Spring은 로그인 사용자·지원 세션 소유권을 확인하고 `context_id`, `analysis_id`, 필요 시 `conversation_id`를 지원 세션에 연결한다. AI API는 사용자 ID를 받지 않는다.
3. 분석은 비동기 상태를 조회해 완료/실패를 반영한다. `202`는 분석 완료가 아니다.
4. 화면/총괄에서 요구사항별 판정·원문 근거를 사용하려면 `result` 전체를 구조화해 보존한다. JD 분석 결과는 포지션의 `{message, analysis}` 형태가 아니다.
5. JD 후속 대화를 사용할지, 검토방의 Spring 메시지 저장을 원본으로 둘지 결정한다. 두 저장소를 함께 쓰면 메시지 동기화와 삭제 책임을 정해야 한다.

## 관련 구현

- 통합 마운트: `ai/serve.py`
- JD FastAPI 라우트·요청 검증: `ai/jd_coaching/api.py`
- URL 추출·SSRF 방어: `ai/jd_coaching/source_ingestion.py`
- JD 구조화·분석: `ai/jd_coaching/service.py`
- JD 후속 대화: `ai/jd_coaching/chat.py`, `ai/jd_coaching/postgres_conversation_store.py`
- 상세 필드·응답 예시: `ai/docs/jd-coaching-api-spec.md`
- Spring의 JD FastAPI HTTP 클라이언트 및 검토방 연동: 미구현
