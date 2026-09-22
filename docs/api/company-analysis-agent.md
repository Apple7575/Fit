# 기업 분석 담당 API

공시(DART 사업보고서)와 확정 지표만으로 기업 분석 리포트를 만들고, 그 위에서 대화한다.
뉴스는 리포트 근거에 넣지 않는다. 대화 중 뉴스가 필요하면 `needs` 로 총괄에 알린다.

- 코드: `ai/company_analysis/`
- 마운트: `ai/serve.py` 의 `/company` → 프록시 뒤 외부 주소는 `/ai/company/...`
- 스키마: `company-report-v1` (`ai/company_analysis/contracts.py`)
- 저장: `company_analysis_report` (V29), `company_analysis_conversation`·`company_analysis_message` (V30)

## 리포트

### `GET /ai/company/internal/reports/{corp_code}`

저장된 리포트를 돌려준다. 없으면 **확정 데이터 블록만 든 리포트를 지금 만들어** 즉시 돌려주고(수백 ms),
LLM 서술 블록은 백그라운드에서 붙인다(기업당 약 3~4분). 응답의 `stage` 로 구분한다.

| stage | 뜻 | 프론트 처리 |
| --- | --- | --- |
| `DETERMINISTIC` | 재무 표·차트·KPI·투자 표·경쟁사 표만 있음. `warnings` 에 "서술 블록을 생성하는 중" | "분석 중" 표시, 15~30초 간격 폴링 |
| `FULL` | 소개·사업 서술·재무 해설·경쟁 구도·SWOT 까지 완료 | 완성본 표시 |

응답 예(요약):

```json
{
  "schema_version": "company-report-v1",
  "stage": "FULL",
  "corp_code": "00164779",
  "corp_name": "SK하이닉스",
  "fiscal_year": 2025,
  "generated_at": "2026-09-18T10:32:10+09:00",
  "intro": { "kind": "text", "text": "...", "citations": [ { "source_type": "DART_BUSINESS_REPORT", "source_id": "dart-business-report-…", "rcept_no": "20260317000635" } ] },
  "sections": [
    { "type": "BUSINESS",    "title": "사업 내용",           "blocks": [ … ] },
    { "type": "FINANCIALS",  "title": "재무 분석",           "blocks": [ … ] },
    { "type": "COMPETITORS", "title": "경쟁사 및 포지셔닝",   "blocks": [ … ] },
    { "type": "SWOT",        "title": "SWOT 분석 및 활용점",  "blocks": [ { "kind": "swot", … } ] }
  ],
  "sources": [ { "rcept_no": "20260317000635", "title": "사업보고서 (2025.12)", "published_at": "…", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260317000635" } ],
  "warnings": []
}
```

블록은 `kind` 로 구분하며 여섯 종류다.

| kind | 필드 | 렌더링 |
| --- | --- | --- |
| `text` | `title?`, `text`, `citations` | 문단 |
| `bullets` | `title?`, `items[{text, citations, perspective?}]` | 항목 목록. `**핵심어**: 설명` 형식 |
| `table` | `title`, `columns`, `rows`, `unit?`, `chart?`(donut) , `citations` | 표. `chart` 가 있으면 도넛도 |
| `kpi` | `items[{label, value, unit, delta_pct?, note?}]` | 카드. `note` 는 "흑전/적전" |
| `chart` | `title`, `chart`(bar/line), `categories`, `series[{name, values}]`, `unit` | 차트 |
| `swot` | `strengths/weaknesses/opportunities/threats{headline, summary, items}` | 4분면 |

숫자 블록(`table`·`kpi`·`chart`)은 DB 확정 지표로만 만들어 LLM 이 손대지 않는다. 서술 블록(`text`·`bullets`·`swot`)의
모든 문장은 `citations` 를 갖고, 생성 뒤 숫자·점유율을 근거와 대조해 어긋난 문장은 버린다(`warnings` 에 건수).

오류: `404 COMPANY_NOT_FOUND`, `422 INVALID_CORP_CODE`, `422 REPORT_UNAVAILABLE`(확정 데이터도 없는 기업).

### `GET /ai/company/internal/reports/{corp_code}/status`

`{corp_code, status(PENDING|RUNNING|READY|FAILED), fiscal_year, updated_at, error}`. 요청된 적 없으면 404.

### `POST /ai/company/internal/reports`

`{"corp_code": "00164779", "force": false}`. 미리 만들어 두는 용도(배치). 서술까지 끝났으면 200, 진행 중이면 202.

## 대화

### `POST /ai/company/internal/chat`

```json
{ "corp_code": "00164779", "message": "HBM 관련해서 뭘 하고 있어?", "conversation_id": null, "job_context_id": null }
```

`conversation_id` 가 없으면 새 대화를 만든다. 있으면 같은 기업의 대화여야 한다(아니면 409).

```json
{
  "conversation_id": "…",
  "corp_code": "00164779",
  "user_message":      { "message_id": "…", "role": "USER",      "content": "…", "created_at": "…" },
  "assistant_message": { "message_id": "…", "role": "ASSISTANT", "content": "…", "created_at": "…",
                         "citations": [ { "source_type": "DART_BUSINESS_REPORT", "source_id": "dart-…", "rcept_no": "…", "excerpt": "…" } ],
                         "needs": [ { "agent": "news", "reason": "최근 뉴스는 공시 자료에 포함되지 않아 확인할 수 없습니다." } ] },
  "follow_up_questions": [ "…", "…" ],
  "report_stage": "FULL",
  "usage": { "prompt_tokens": 4510, "completion_tokens": 178 }
}
```

- 답은 저장된 리포트 블록 + 질문으로 검색한 사업보고서 원문(BM25 + 벡터, 8건)만 근거로 쓴다.
- 답의 숫자가 근거와 어긋나면 한 번 다시 묻고, 그래도 어긋나면 "근거를 찾지 못했습니다" 로 답한다.
- 공시로 답할 수 없는 질문(뉴스·주가·평판)은 `needs: [{agent: "news", …}]` 를 함께 돌려준다. 총괄이 이 값을 보고
  뉴스 담당에 1홉 위임하면 된다. 담당끼리 직접 부르지 않는다.
- 응답 시간: 6~10초(한 번에 답할 때), 20~30초(다시 물을 때).

### `GET /ai/company/internal/conversations/{conversation_id}`

`{conversation_id, corp_code, job_context_id, messages[]}`. 없으면 404.

## 환경변수 (`ai/.env`)

| 키 | 필수 | 뜻 |
| --- | --- | --- |
| `COMPANY_ANALYSIS_DATABASE_URL` | 아니오 | 확정 데이터·리포트·대화 DB. 없으면 `JD_DATABASE_URL` |
| `COMPANY_ANALYSIS_RAG_DATABASE_URL` | 아니오 | `rag_evidence` 가 다른 DB 에 있을 때. 없으면 위와 같은 DB |
| `QWEN_BASE_URL` / `QWEN_MODEL` / `QWEN_API_KEY` | 서술·대화에 필요 | GPU 서버 Qwen. 없으면 확정 블록만 만든다 |
| `COMPANY_ANALYSIS_NARRATIVE` | 아니오 | `off` 면 서술 생성 안 함 |
| `COMPANY_ANALYSIS_MODEL_TIMEOUT_SECONDS` | 아니오 | 기본 180 |
| `COMPANY_ANALYSIS_EMBEDDING_BASE_URL` / `_API_KEY` / `_MODEL` | 아니오 | 질의 임베딩 서버. 없으면 대화 검색은 BM25 만 |

## 데이터 전제

- 확정 지표(`company_metric` 등)는 시드 CSV 로 2,703개사 적재 → 모든 기업에서 확정 블록이 나온다.
- 사업보고서 청크(`rag_evidence`, `DART_BUSINESS_REPORT`)가 있는 기업만 서술 블록·대화 원문 검색이 된다.
  2026-09-18 기준 실험 DB 에 100개사. 나머지는 `data/scripts/build_rag_corpus.py` 로 만들어 넣어야 한다.
- 모델 컨텍스트가 12,288 토큰이라 한 호출에 근거를 6,500자 안팎만 넣는다. 섹션을 7개 호출로 나눈 이유다.
