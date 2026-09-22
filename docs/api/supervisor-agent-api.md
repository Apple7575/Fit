# Supervisor Agent API v1

이 문서는 Spring 백엔드가 호출하는 Python 총괄(supervisor) 에이전트의 계약이다.
총괄은 한 요청 안에서 `jd`, `position`, `writing`, `news`, `company` 담당 중 필요한 것을 선택해
실행하고 결과를 종합한다. 총괄은 대화·문서·결과를 저장하지 않는 무상태 서비스다.

> **버전 안정성**: 요청 형식과 응답의 기존 필드는 고정이다. 이후 작업에서 응답에
> 필드가 **추가**될 수 있으니(`trace` 등), Spring은 알 수 없는 응답 필드를 무시하도록
> 파싱해야 한다(Jackson `FAIL_ON_UNKNOWN_PROPERTIES=false`). 기존 필드의 삭제·의미
> 변경은 하지 않는다.

## 경로와 기본 원칙

독립 앱의 엔드포인트는 `POST /internal/runs`이고, 통합 `ai/serve.py`에서는
`/supervisor` 아래에 마운트된다. 프록시가 `/ai/`를 떼고 넘기므로 외부 주소는
`/ai/supervisor/internal/runs`다.

```http
POST /supervisor/internal/runs
Content-Type: application/json
```

- 모든 질문이 총괄을 거칠 필요는 없다. 담당 하나만 필요하면 Spring이 담당 API를
  직접 호출한다(`/jd`, `/position`, `/writing`, `/news`).
- Spring은 호출 전에 로그인 사용자가 `job_context_id`·`cover_letter` 등에 접근할 권한이
  있는지 검증하고, 검증된 식별자만 넘긴다. 총괄과 담당은 인증·소유권 확인을 하지 않는다.
- 어떤 담당을 실행할 수 있는지는 `agent_contexts`에 어떤 키를 넣었는지로 결정된다.
  컨텍스트를 넣지 않은 담당은 총괄이 선택하지 않는다.

## 요청

모든 객체는 알 수 없는 필드를 거부한다(HTTP 422).

| 필드 | 필수 | 제한 |
|---|---:|---|
| `instruction` | 예 | 사용자의 현재 질문. 1~10,000자 |
| `documents` | 조건부 | 0~21개. `document_id` 중복 불가. **비어 있으면 `news`만 실행 가능**하고, 다른 담당 컨텍스트만 있으면 422 `NO_AVAILABLE_AGENT` |
| `conversation` | 아니오 | 최근 대화 최대 20개, 기본값 `[]` |
| `agent_contexts` | 예 | 아래 4개 키 중 **최소 1개** |
| `lead` | 아니오 | `jd`, `position`, `writing`, `news` 중 하나. **담당 직접 호출 모드**(아래) |

### documents[]

| 필드 | 제한 |
|---|---|
| `document_id` | 1~100자, 요청 안에서 고유 |
| `document_type` | `RESUME`, `SELF_INTRO`, `EXPERIENCE`, `PORTFOLIO` |
| `text` | 1~50,000자 |

담당별 문서 요구: `position`은 `SELF_INTRO` 또는 `EXPERIENCE`가 1개 이상,
`writing`은 `SELF_INTRO`가 **정확히 1개** 필요하다. 조건이 안 맞으면 그 담당만
`FAILED`로 기록되고 나머지는 진행된다.

### conversation[]

| 필드 | 제한 |
|---|---|
| `message_id` | 1~100자, 요청 안에서 고유 |
| `role` | `USER`, `ASSISTANT` |
| `content` | 1~10,000자 |

대화는 담당의 맥락 이해에만 쓰이고 **사실 근거로는 사용하지 않는다.**

### agent_contexts

| 키 | 필드 | 설명 |
|---|---|---|
| `jd` | `job_context_id` (1~100자) | `/jd/internal/job-contexts`로 등록한 공고 컨텍스트 |
| `position` | `rubric_id` = `"experience-depth-v1"`, `position_context.position_name` (1~200자), `position_context.priority_requirements[]` (최대 20개, 각 1~500자) | 직무 경험 구체성 검토 |
| `writing` | `question` (1~500자), `char_limit` (정수 1~50,000) | 자소서 첨삭. 다른 담당 결과를 피드백으로 받아 **분석 담당 뒤에** 실행 |
| `news` | `job_context_id` (1~80자), `corp_code` (숫자 8자리) | 기업·산업·직무 변화의 기사 근거 분석 |
| `company` | `corp_code` (숫자 8자리), `job_context_id` (선택) | 공시(사업보고서·확정 지표) 기반 기업 분석 리포트와 질의응답. 제출 문서 없이 실행 가능. 뉴스가 필요하면 `needs: news` 를 내어 총괄이 뉴스 담당에 1홉 위임. 상세: `docs/api/company-analysis-agent.md` |

```json
{
  "instruction": "지원동기 문단에 최근 회사 변화를 반영해서 고쳐줘",
  "documents": [
    {"document_id": "cover-letter-7", "document_type": "SELF_INTRO", "text": "저는 Spring 기반 API를 ..."}
  ],
  "conversation": [
    {"message_id": "m-1", "role": "USER", "content": "근거 중심으로 정리해줘"}
  ],
  "agent_contexts": {
    "jd": {"job_context_id": "job-context-123"},
    "news": {"job_context_id": "job-context-123", "corp_code": "00126380"},
    "writing": {"question": "지원동기를 작성하세요", "char_limit": 1000}
  }
}
```

### 담당 직접 호출 (`lead`)

사용자가 특정 담당에게 직접 물을 때 Spring은 담당 API 대신 **같은 총괄 엔드포인트에
`lead`를 지정**해 호출한다. 총괄의 계획 단계를 건너뛰고 그 담당부터 실행하되,
위임·재실행·근거·도구 기록은 총괄 경로와 똑같이 동작한다. 최종 `message`는 lead
담당의 것이다.

```json
{
  "instruction": "이 문단 더 설득력 있게 고쳐줘",
  "documents": [{"document_id": "cover-letter-7", "document_type": "SELF_INTRO", "text": "..."}],
  "agent_contexts": {
    "writing": {"question": "지원동기를 작성하세요", "char_limit": 1000},
    "news": {"job_context_id": "job-context-123", "corp_code": "00126380"}
  },
  "lead": "writing"
}
```

- `lead` 담당의 컨텍스트는 필수다. 없으면 422 `NO_AVAILABLE_AGENT`.
- 다른 담당의 컨텍스트를 함께 넣으면 lead가 필요할 때 위임할 수 있다(위 예시: 글쓰기가
  근거 부족을 알리면 뉴스가 실행되고 글쓰기가 다시 돈다). 안 넣으면 위임은 일어나지 않는다.
- 기존 담당 API(`/writing/internal/messages` 등)는 그대로 있고 위임 기능은 없다.
  위임이 필요한 화면은 `lead` 모드로 옮기면 된다.

## 실행 순서

1. 총괄 모델이 `agent_contexts`에 있는 담당 중 질문에 필요한 것을 선택한다(`plan`).
   `lead`가 있으면 모델을 부르지 않고 `[lead]`를 계획으로 쓴다.
2. 분석 담당(`jd`, `position`, `news`)을 **병렬**로 실행한다.
3. `writing`이 선택됐으면 분석 담당의 성공 결과를 피드백으로 넘겨 **그 뒤에** 실행한다.
4. 실행된 담당이 `needs`로 다른 담당을 요청하면 **위임 라운드**를 1회 수행한다(아래).
5. 성공 결과를 종합해 `message`를 만든다. `writing` 단독이거나 `writing`이
   추가 정보를 요청(`CLARIFICATION_REQUIRED`)하면 `writing`의 메시지를 그대로 쓴다.

### 위임 (담당 → 총괄 → 담당)

담당은 서로를 직접 부르지 않는다. 담당이 결과에 `needs`를 남기면 총괄이 대신 실행하고,
요청한 담당을 **한 번** 다시 실행해 결과를 반영한다.

```text
writing(1차) ─needs: news─▶ 총괄 ─▶ news(delegated_from=writing) ─▶ writing(2차, 뉴스 피드백 반영)
```

- 위임 라운드는 요청당 **1회**, 라운드당 추가 실행 담당은 **최대 2개**.
- 위임 대상은 `jd`, `position`, `news` 중 `agent_contexts`가 있고 아직 실행되지 않은 담당만.
- 위임으로 실행된 담당과 재실행된 담당의 `needs`는 무시한다(연쇄 위임 없음).
- `agent_results`에는 담당별 **마지막 실행**만 들어간다. 재실행된 `writing`은 한 번만 보인다.
- 현재 `needs`를 만드는 규칙: `writing`이 `warnings[].code == "MISSING_EVIDENCE"`를
  반환하면 `news`를 요청한다. 담당 결과에 명시적 `needs` 배열이 있으면 그것도 읽는다.

## 응답

HTTP 200.

| 필드 | 설명 |
|---|---|
| `status` | `SUCCESS`(선택 담당 전부 성공) 또는 `PARTIAL`(일부 실패) |
| `message` | 사용자에게 보여줄 종합 메시지 |
| `plan.selected_agents` | 총괄이 선택한 담당 목록(실행 순서) |
| `plan.reason` | 선택 이유 |
| `agent_results[]` | 담당별 결과. 아래 참조 |
| `evidence[]` | 모든 담당이 사용한 근거의 합집합(중복 제거). 아래 참조 |
| `lead` | 요청의 `lead`를 그대로 반환. 총괄 모드면 `null` |
| `trace[]` | 실행 단계 전체 기록(계획 → 담당 실행 → 위임 → 재실행 → 종합). 아래 참조 |

### agent_results[]

| 필드 | 설명 |
|---|---|
| `agent` | `jd`, `position`, `writing`, `news` |
| `status` | `SUCCESS`, `FAILED` |
| `result` | 담당 API의 응답 본문과 같은 구조(각 담당 문서 참조). 실패 시 `null` |
| `error` | 실패 사유 문자열. 성공 시 `null` |
| `error_code` | 실패 종류. LLM 할당량(429)에 막혔으면 `LLM_QUOTA_EXCEEDED`, 그 밖에는 `null`. 이 값이면 `error`는 사용자에게 그대로 보여도 되는 한 문장이다 |
| `evidence[]` | 이 담당이 사용한 근거 |
| `needs[]` | 담당이 총괄에 요청한 추가 담당 호출. `{agent, reason}`. 아래 "위임" 참조 |
| `tool_calls[]` | 이 담당이 실행 중 호출한 조회 도구 기록. 아래 참조 |
| `usage` | 토큰 사용량 `{prompt_tokens, completion_tokens, total_tokens}` 또는 `null` |
| `delegated_from` | 다른 담당의 `needs`로 실행된 경우 요청한 담당. 계획으로 실행됐으면 `null` |

### tool_calls[]

담당은 자료를 **허용된 조회 도구로만** 읽는다. 허용 목록은 코드에 고정돼 있고
(`jd`: 공고 조회 / `news`: 공고·저장 기사·외부 검색 / `position`·`writing`: 없음),
목록 밖 호출은 실행되지 않고 `DENIED`로 기록된다.

| 필드 | 설명 |
|---|---|
| `tool` | `get_job_context`, `list_news`, `search_news_external`, `get_conversation` |
| `agent` | 호출한 담당 |
| `arguments` | 식별자·숫자 등 요약된 인자. 본문은 담지 않음 |
| `status` | `SUCCESS`, `FAILED`, `DENIED` |
| `duration_ms` | 소요 시간 |
| `result_count` | 조회 결과 건수. 알 수 없으면 `null` |
| `error` | 실패·거부 사유. 성공 시 `null` |

### trace[]

"누가 누굴 불렀고, 어떤 도구와 근거를 썼는지"를 실행 순서대로 담는다. `agent_results`는
담당별 마지막 실행만 보여주지만, `trace`에는 재실행으로 대체된 1차 실행도 남는다.

| 필드 | 설명 |
|---|---|
| `step` | 1부터 실행 순서 |
| `phase` | `plan`(계획), `analysis`(분석 담당), `writing`(글쓰기), `delegation`(위임으로 실행), `rerun`(위임 후 재실행), `aggregate`(종합) |
| `agent` | 실행 주체. 계획·종합은 `supervisor` |
| `called_by` | `request`(요청 자체), `plan`(계획으로 선택), `lead`(직접 호출), 또는 위임을 요청한 담당 이름. 재실행은 `delegation` |
| `status` | `SUCCESS`, `FAILED`, `SKIPPED`(종합할 결과 없음) |
| `duration_ms` | 소요 시간 |
| `tool_calls[]` | 그 단계의 도구 호출(위 `tool_calls` 형식) |
| `evidence_ids[]` | 그 단계가 등록한 근거 id |
| `usage` | 토큰 사용량 또는 `null` |
| `superseded` | 같은 담당이 뒤에 재실행되어 대체된 결과면 `true` |
| `note` | 계획: `selected=...; 이유`, 재실행: `after=위임담당`, 종합: `model`/`passthrough`, 실패: 오류 메시지 |

```json
"trace": [
  {"step": 1, "phase": "plan", "agent": "supervisor", "called_by": "request", "status": "SUCCESS", "duration_ms": 820, "tool_calls": [], "evidence_ids": [], "usage": null, "superseded": false, "note": "selected=writing; 첨삭 요청"},
  {"step": 2, "phase": "writing", "agent": "writing", "called_by": "plan", "status": "SUCCESS", "duration_ms": 4100, "tool_calls": [], "evidence_ids": [], "usage": null, "superseded": true, "note": null},
  {"step": 3, "phase": "delegation", "agent": "news", "called_by": "writing", "status": "SUCCESS", "duration_ms": 6200, "tool_calls": ["..."], "evidence_ids": ["news:stored:42"], "usage": null, "superseded": false, "note": null},
  {"step": 4, "phase": "rerun", "agent": "writing", "called_by": "delegation", "status": "SUCCESS", "duration_ms": 3900, "tool_calls": [], "evidence_ids": [], "usage": null, "superseded": false, "note": "after=news"},
  {"step": 5, "phase": "aggregate", "agent": "supervisor", "called_by": "request", "status": "SUCCESS", "duration_ms": 3, "tool_calls": [], "evidence_ids": [], "usage": null, "superseded": false, "note": "passthrough"}
]
```

### evidence[]

담당이 판단에 **실제로 사용한** 자료만 담는다. 대화 내용은 근거로 등록하지 않는다.

| 필드 | 설명 |
|---|---|
| `evidence_id` | 응답 안에서 고유. `news:<article_id>`, `jd:<job_context_id>`, `doc:<document_id>:<start>-<end>` 형식 |
| `source_type` | `NEWS_ARTICLE`(기사), `JOB_POSTING`(공고 컨텍스트), `USER_DOCUMENT`(제출 문서 인용 구간), `COMPANY_REPORT`(기업 공시, 예정) |
| `source_id` | 원본 식별자(기사 id, 공고 컨텍스트 id, 문서 id) |
| `agent` | 이 근거를 처음 등록한 담당 |
| `title` | 기사 제목, 공고의 `기업 / 직무`, 또는 인용과 연결된 요구사항명. 없으면 `null` |
| `date` | 기사 발행 시각(ISO 8601). 없으면 `null` |
| `url` | 기사 URL. 없으면 `null` |
| `excerpt` | 인용 구간 원문 또는 신호 요약(최대 1,000자). 없으면 `null` |

```json
{
  "status": "SUCCESS",
  "message": "AI 인프라 투자 확대를 지원동기와 연결해 문단을 수정했습니다. ...",
  "plan": {"selected_agents": ["jd", "news", "writing"], "reason": "회사 변화 반영 첨삭"},
  "agent_results": [
    {
      "agent": "jd", "status": "SUCCESS",
      "result": {"context_id": "job-context-123", "company_name": "삼성전자", "position_name": "백엔드", "requirements": ["..."], "summary": {"supported": 2, "partially_supported": 1, "not_supported": 0, "failed": 0}, "usage": {"prompt_tokens": 2100, "completion_tokens": 340, "total_tokens": 2440}},
      "error": null,
      "evidence": [
        {"evidence_id": "jd:job-context-123", "source_type": "JOB_POSTING", "source_id": "job-context-123", "agent": "jd", "title": "삼성전자 / 백엔드", "date": null, "url": null, "excerpt": null},
        {"evidence_id": "doc:cover-letter-7:120-146", "source_type": "USER_DOCUMENT", "source_id": "cover-letter-7", "agent": "jd", "title": "대규모 트래픽 처리", "date": null, "url": null, "excerpt": "일 1억 건 요청을 처리하는 API를 운영"}
      ],
      "needs": [],
      "tool_calls": [
        {"tool": "get_job_context", "agent": "jd", "arguments": {"context_id": "job-context-123"}, "status": "SUCCESS", "duration_ms": 12, "result_count": 1, "error": null}
      ],
      "usage": {"prompt_tokens": 2100, "completion_tokens": 340, "total_tokens": 2440}, "delegated_from": null
    },
    {
      "agent": "news", "status": "SUCCESS",
      "result": {"message": "...", "analysis": {"analysis_status": "COMPLETED", "signals": ["..."]}},
      "error": null,
      "evidence": [
        {"evidence_id": "news:stored:42", "source_type": "NEWS_ARTICLE", "source_id": "stored:42", "agent": "news", "title": "삼성전자, AI 인프라 투자 확대", "date": "2026-09-10T09:00:00+09:00", "url": "https://news.example.test/articles/42", "excerpt": "AI 인프라 투자 확대 계획이 공개됐다."}
      ],
      "needs": [],
      "tool_calls": [
        {"tool": "get_job_context", "agent": "news", "arguments": {"context_id": "job-context-123", "corp_code": "00126380"}, "status": "SUCCESS", "duration_ms": 9, "result_count": 1, "error": null},
        {"tool": "list_news", "agent": "news", "arguments": {"corp_code": "00126380", "since": "2026-06-18T00:00:00+00:00", "limit": 20}, "status": "SUCCESS", "duration_ms": 31, "result_count": 7, "error": null}
      ],
      "usage": null, "delegated_from": null
    },
    {
      "agent": "writing", "status": "SUCCESS",
      "result": {"status": "REVISED", "message": "...", "revision": {"revision_strength": "BALANCED", "revised_text": "...", "char_count": 812, "changes": ["..."], "warnings": []}},
      "error": null,
      "evidence": [], "needs": [], "tool_calls": [], "usage": null, "delegated_from": null
    }
  ],
  "evidence": [
    {"evidence_id": "jd:job-context-123", "source_type": "JOB_POSTING", "source_id": "job-context-123", "agent": "jd", "title": "삼성전자 / 백엔드", "date": null, "url": null, "excerpt": null},
    {"evidence_id": "doc:cover-letter-7:120-146", "source_type": "USER_DOCUMENT", "source_id": "cover-letter-7", "agent": "jd", "title": "대규모 트래픽 처리", "date": null, "url": null, "excerpt": "일 1억 건 요청을 처리하는 API를 운영"},
    {"evidence_id": "news:stored:42", "source_type": "NEWS_ARTICLE", "source_id": "stored:42", "agent": "news", "title": "삼성전자, AI 인프라 투자 확대", "date": "2026-09-10T09:00:00+09:00", "url": "https://news.example.test/articles/42", "excerpt": "AI 인프라 투자 확대 계획이 공개됐다."}
  ]
}
```

`result` 안의 `"..."`는 지면상 생략 표시이며, 실제 구조는 각 담당 문서를 따른다:
`jd-coaching-api.md`, `position-analysis-api.md`, `writing-agent-api.md`,
`ai/docs/news-trend-agent-api.md`.

## 오류

| HTTP | `detail.code` | 상황 |
|---:|---|---|
| 422 | (FastAPI 기본 형식) | 요청 형식 오류, 알 수 없는 필드, 빈 값 |
| 422 | `NO_AVAILABLE_AGENT` | `agent_contexts`에 담당이 하나도 없음 |
| 502 | `ALL_AGENTS_FAILED` | 선택된 담당이 전부 실패. `detail.agent_results`에 담당별 실패 사유 포함 |
| 502 | `SUPERVISOR_FAILED` | 계획·종합 모델 연결 실패 등 총괄 자체의 오류. `message`는 오류 유형명만 |
| 502 | `LLM_QUOTA_EXCEEDED` | 계획·종합 모델 호출이 LLM 할당량(429)에 막혔거나, 선택된 담당이 **전부** 할당량으로 실패. `message`는 사용자에게 보일 문장("AI 요청 한도에 잠시 걸렸습니다. 1분쯤 뒤에 다시 시도해 주세요."). Spring 은 이 코드를 보고 같은 문장을 말풍선에 띄운다 |
| 503 | (문자열) | 총괄 모델(Qwen) 설정을 읽을 수 없음 |

담당 일부만 실패하면 HTTP 200 + `status: "PARTIAL"`이다. 실패한 담당의 `error`를
보고 사용자에게 어떤 관점이 빠졌는지 알릴 수 있다.

## 타임아웃과 재시도

- Spring은 전체 요청에 **120초** 타임아웃을 적용한다. 총괄 계획·종합 각 30초,
  담당별 예산은 각 담당 문서를 따른다.
- 타임아웃·5xx에 대해 Spring이 자동 재시도하지 않는다. 담당 호출은 모델 비용이 든다.
- Spring의 HTTP 타임아웃은 이미 실행 중인 AI 작업을 취소하지 않는다.
- **위임 시간 예산**: 요청 시작 후 `SUPERVISOR_DELEGATION_DEADLINE_SECONDS`(기본 60초)를
  넘긴 시점에는 위임 라운드를 시작하지 않는다. 요청은 `trace`에 `SKIPPED`로 남고
  1차 결과로 응답한다.
- **재실행 실패**: 위임 후 재실행이 실패하면 1차 결과를 그대로 응답에 쓰고 실패는
  `trace`에만 남긴다.

## 예정된 변경 (전부 추가만)

| 시점 | 내용 |
|---|---|
| 기업 RAG 담당 | `agent_contexts.company` 키와 `COMPANY_REPORT` 근거 추가 |
