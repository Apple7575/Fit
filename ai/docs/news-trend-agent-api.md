# News trend agent API handoff

AI 통합 앱의 직접 경로는 `POST /ai/news/internal/analyses`이고, 단독 news 앱에서는 `POST /internal/analyses`다. 여러 에이전트를 함께 실행할 때는 `POST /ai/supervisor/internal/runs`를 사용한다.

`job_context_id`와 8자리 숫자 `corp_code`는 모두 필수다. Spring은 호출 전에 로그인 사용자가 해당 `job_context_id`의 `cover_letter`를 읽을 권한이 있는지 검증하고, 검증된 `cover_letter`/컨텍스트 식별자만 AI 요청으로 넘긴다. AI 워커는 사용자 인증·소유권 확인이나 `cover_letter` 조회를 하지 않는다.

## Direct news request

```http
POST /ai/news/internal/analyses
Content-Type: application/json

{
  "instruction": "최근 기업·산업·직무 변화가 백엔드 지원 준비에 미치는 영향을 알려줘",
  "job_context_id": "job-context-123",
  "corp_code": "00126380",
  "conversation": [
    {"message_id": "m-1", "role": "USER", "content": "근거 중심으로 정리해줘"}
  ]
}
```

성공 응답은 HTTP 200이며 다음 구조다. `signals`의 각 `sources`는 실제로 사용한 기사이며, `evidence_level`은 `HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT` 중 하나다.

```json
{
  "message": "[COMPANY] 반도체 생산능력 확대\n생산라인 투자 확대와 직무 연관성을 확인한다.",
  "analysis": {
    "analysis_status": "COMPLETED",
    "company": {"corp_code": "00126380", "corp_name": "삼성전자"},
    "window": {"from": "2026-06-18", "to": "2026-09-16"},
    "signals": [{
      "signal_id": "signal-001",
      "scope": "COMPANY",
      "title": "반도체 생산능력 확대",
      "summary": "생산라인 투자 계획이 공개됐다.",
      "jd_relevance": "생산 자동화 경험을 직무 요구와 연결한다.",
      "preparation_checks": ["해당 기업 변화와 관련된 본인 경험이 있는지 확인하세요.", "JD 요구사항과 연결할 수 있는 사실 근거를 정리하세요."],
      "evidence_level": "MEDIUM",
      "sources": [{
        "article_id": "stored:42",
        "origin": "STORED",
        "title": "삼성전자, 생산능력 확대 발표",
        "publisher": "전자신문",
        "published_at": "2026-09-10T09:00:00+09:00",
        "url": "https://news.example.test/articles/42",
        "guid": null,
        "importance_score": 8.2
      }]
    }],
    "coverage": {"company": "COVERED", "industry": "INSUFFICIENT", "role": "INSUFFICIENT", "requested_scopes": ["COMPANY", "INDUSTRY", "ROLE"]},
    "external_search": {"used": true, "reason": "요청 범위 근거 부족"}
  }
}
```

근거가 없으면 HTTP 200과 `analysis.analysis_status: "INSUFFICIENT_EVIDENCE"`, 빈 `signals`를 반환한다. 이는 실패가 아니라 안전한 분석 결과다.

## Supervisor request

Supervisor는 `agent_contexts.news`에 같은 두 식별자를 넣는다. 문서는 supervisor의 일반 계약상 필수지만 news 워커에는 전달되지 않는다.

```http
POST /ai/supervisor/internal/runs
Content-Type: application/json

{
  "instruction": "최근 변화와 지원 준비 포인트를 검토해줘",
  "documents": [{"document_id": "cover-letter-7", "document_type": "SELF_INTRO", "text": "Spring 기반 API 개발 경험"}],
  "conversation": [],
  "agent_contexts": {
    "news": {"job_context_id": "job-context-123", "corp_code": "00126380"}
  }
}
```

```json
{
  "status": "SUCCESS",
  "message": "종합 결과",
  "plan": {"selected_agents": ["news"], "reason": "최신 기업 변화 확인"},
  "agent_results": [{
    "agent": "news",
    "status": "SUCCESS",
    "result": {"message": "확인 가능한 최신 기사 근거가 부족해 기업·산업·직무 변화를 판단하지 않았습니다.", "analysis": {"analysis_status": "INSUFFICIENT_EVIDENCE", "company": {"corp_code": "00126380", "corp_name": "삼성전자"}, "window": {"from": "2026-06-18", "to": "2026-09-16"}, "signals": [], "coverage": {"company": "INSUFFICIENT", "industry": "INSUFFICIENT", "role": "INSUFFICIENT", "requested_scopes": ["COMPANY", "INDUSTRY", "ROLE"]}, "external_search": {"used": true, "reason": "유효 기사 5건 미만"}}},
    "error": null
  }]
}
```

Supervisor 결과 `SUCCESS`는 선택된 워커가 모두 성공했음을, `PARTIAL`은 하나 이상 성공하고 하나 이상 실패했음을 뜻한다. news 단독이 실패하면 supervisor는 HTTP 502 `ALL_AGENTS_FAILED`를 반환한다.

## Errors and timeout

- 형식 오류(빈 `job_context_id`, 8자리가 아닌 `corp_code` 포함)는 HTTP 422다.
- 직접 news 호출에서 컨텍스트 또는 기업을 찾지 못하면 HTTP 404 (`JOB_CONTEXT_NOT_FOUND`, `COMPANY_NOT_FOUND`)다.
- 뉴스 저장소/검색 원천을 사용할 수 없으면 HTTP 503 `NEWS_SOURCE_UNAVAILABLE`이고, 모델 출력 또는 모델 연결 실패는 HTTP 502 `NEWS_MODEL_UNAVAILABLE`이다.
- Spring 호출자는 전체 요청에 120초 타임아웃을 적용해야 한다(호출자 구현 범위). 타임아웃·5xx에 대해 워커 호출을 자동 재시도하지 않는다.

뉴스 worker는 요청마다 monotonic 시계로 90초 누적 예산을 시작한다. Qwen의 각 호출은
`min(45초, 남은 예산)`을 전달하고, 출력 검증 재시도도 같은 예산을 사용한다. RSS provider는
`min(30초, 남은 예산)`의 deadline을 사용하며 연결·읽기 timeout도 그 안으로 줄인다.
DB 연결 timeout은 5초이고 남은 예산이 5초보다 작으면 새 연결을 시작하지 않는다.
각 조회 전 transaction-local `statement_timeout`을 `min(5초, 남은 예산)`으로 설정한다.
예산이 소진되면 원천 단계는 `NEWS_SOURCE_UNAVAILABLE`, 모델 단계는
`NEWS_MODEL_UNAVAILABLE`로 끝나며 늦게 반환된 결과를 `COMPLETED`로 처리하지 않는다.

이 제한은 동기 실행의 best-effort 예산이다. urllib의 Qwen timeout은 소켓 대기 제한이므로
조금씩 계속 도착하는 응답 전체를 강제 중단하지 못하고, DNS·다중 주소 연결·DB 네트워크
대기·주입한 사용자 구현도 deadline을 넘길 수 있다. 총괄의 계획·집계와 다른 worker까지
합친 120초 hard wall-clock 종료를 보장하지 않는다. Spring의 HTTP timeout 역시 이미
실행 중인 AI 작업을 취소하지 않는다. 엄격한 전체 종료에는 별도의 취소 가능한 실행 경계가 필요하다.

외부 검색 결과는 이 응답을 만들기 위한 일회성 후보이며 `news_article` 등 영속 저장소에 자동 저장하지 않는다. Spring도 응답을 표시하거나 자체 정책에 따라 별도 저장할 수 있을 뿐, 외부 기사 결과를 원본 뉴스 데이터로 승격해서는 안 된다.
