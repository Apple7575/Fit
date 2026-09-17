# 뉴스·트렌드 에이전트 설계

## 1. 목표

현재 지원 중인 채용공고와 기업을 기준으로 기업·산업·직무 변화를 근거와 함께 설명하는
`news` 에이전트를 Python AI 서버에 추가한다. 단순 기사 요약이 아니라 변화 신호를 JD와
연결하고, 지원자가 추가로 확인하거나 준비할 항목을 제시하는 것이 핵심 가치다.

에이전트의 책임은 다음으로 제한한다.

- 기업 변화, 산업 변화, 직무 변화를 구분한다.
- 각 변화에 실제 기사 근거와 근거 수준을 붙인다.
- 분석된 JD의 직무·요구사항과 변화의 관련성을 설명한다.
- 사용자가 사실관계를 확인하거나 준비할 항목을 제시한다.

자소서 문장 작성, 면접 답변 생성, 최종 지원 전략 결정, 근거 없는 미래 예측은 하지 않는다.

## 2. 데이터 연결과 서비스 경계

Spring 백엔드는 `cover_letter`에 `job_context_id`와 `corp_code` 외래키를 추가할 예정이다.
검토방 요청 시 `agent_room.cover_letter_id`로 자소서를 조회하고 두 값을 총괄 에이전트에
전달한다.

```text
agent_room
  -> cover_letter
       |- job_context_id -> ai_job_contexts
       `- corp_code      -> company -> news_article
```

AI 서비스는 `cover_letter`나 `agent_room`을 직접 조회하지 않는다. 사용자·자소서 소유권,
기존 데이터 보정, 필수 외래키 누락 처리는 Spring의 책임이다. AI는 전달받은 식별자를
검증하고 분석에만 사용한다.

`cover_letter.target_company`는 표시용 문자열이다. 저장 뉴스 조회의 기준은 기업명이 아닌
`corp_code`다. 외부 검색에 필요한 기업명은 `corp_code`로 `company.corp_name`을 조회해 얻고,
이름으로 기업 코드를 역추정하지 않는다.

관련 결정:

- [[Decisions/product/jd-api-boundary]]
- [[Decisions/architecture/agent-api-path-convention-without-url-version]]
- [[Decisions/architecture/news-agent-context-contract]]
- [[Decisions/ai/rag-mvp-feature-contracts]]

## 3. API 계약

URL 버전 없는 기존 내부 API 규칙에 따라 FastAPI 앱을 `/news`에 마운트하고 동기식
`POST /news/internal/analyses`를 제공한다. Spring이 사용자용 공개 API와 대화 저장을
담당하며, 뉴스 API는 한 요청의 분석 결과만 반환하는 무상태 서비스다.

직접 호출 요청 예시는 다음과 같다.

```json
{
  "instruction": "최근 변화가 이 공고의 백엔드 직무에 어떤 영향을 주는지 알려줘",
  "job_context_id": "jctx_abc123",
  "corp_code": "00126380",
  "conversation": []
}
```

- `instruction`: 사용자의 현재 질문
- `job_context_id`: `ai_job_contexts.context_id`; JD 원문, 직무명, 요구사항 조회에 사용
- `corp_code`: `company.corp_code`; 기업과 저장 뉴스 조회에 사용
- `conversation`: Spring이 전달하는 최근 대화 최대 20개; 사실 근거로 사용하지 않음

응답의 `analysis`는 다음 구조를 사용한다.

```json
{
  "message": "AI 인프라 투자 확대가 현재 지원 직무와 연결됩니다.",
  "analysis": {
    "analysis_status": "COMPLETED",
    "company": {
      "corp_code": "00126380",
      "corp_name": "삼성전자"
    },
    "window": {
      "from": "2026-06-18",
      "to": "2026-09-16"
    },
    "signals": [
      {
        "signal_id": "signal-001",
        "scope": "COMPANY",
        "title": "AI 인프라 투자 확대",
        "summary": "기사 제목에서 AI 인프라 투자 확대를 확인할 수 있습니다.",
        "jd_relevance": "대규모 서비스와 인프라 운영 요구사항과 관련됩니다.",
        "preparation_checks": [
          "해당 기업 변화와 관련된 본인 경험이 있는지 확인하세요.",
          "JD 요구사항과 연결할 수 있는 사실 근거를 정리하세요."
        ],
        "evidence_level": "MEDIUM",
        "sources": [
          {
            "article_id": "stored:123",
            "origin": "STORED",
            "title": "AI 인프라 투자 확대",
            "publisher": "언론사",
            "published_at": "2026-09-10T03:00:00Z",
            "url": "https://example.com/article"
          }
        ]
      }
    ],
    "coverage": {
      "company": "COVERED",
      "industry": "INSUFFICIENT",
      "role": "COVERED"
    },
    "external_search": {
      "used": true,
      "reason": "산업 변화 근거 부족"
    }
  }
}
```

`scope`은 `COMPANY`, `INDUSTRY`, `ROLE`만 허용한다. `analysis_status`는 `COMPLETED`,
`INSUFFICIENT_EVIDENCE`를 허용한다. 근거가 없을 때 빈 내용을 추정해 채우지 않는다.

## 4. 저장 뉴스 우선 검색

`PostgresNewsRepository`는 프로젝트 PostgreSQL에서 다음 데이터를 읽는다.

- `ai_job_contexts`: 회사명, 직무명, JD 원문, 구조화된 요구사항
- `company`, `industry`: `corp_code`에 대응하는 정식 기업명과 산업명
- `news_article`: 해당 기업의 저장 기사

기본 조회 기간은 최근 90일, 후보 상한은 20건이다. `published_at`, 유효한 제목과 URL을
가진 기사를 우선하며 URL, `guid`, 정규화된 제목 순서로 중복을 제거한다.

저장 근거가 부족한 조건은 다음과 같다.

- 유효 후보가 5건 미만이다.
- 최신 유효 기사가 30일보다 오래됐다.
- 의미 분류 결과 `COMPANY`, `INDUSTRY`, `ROLE` 중 사용자 요청과 JD에 필요한 범위가
  `INSUFFICIENT`다.

건수, 날짜, 중복은 결정적 코드가 판정한다. 기사의 의미와 JD 관련 범위는 LLM이 구조화된
출력으로 분류한다. V1에서는 임베딩이나 벡터 검색을 도입하지 않는다.

현재 `news_article`에는 기사 본문이 없으므로 제목, 출처, 발행일, URL을 근거로 사용한다.
제목에서 확인할 수 없는 세부 사실을 생성하지 않는다.

## 5. 제한된 외부 검색

저장 뉴스가 부족할 때만 `NewsSearchProvider`를 한 번 호출한다. 이 인터페이스는 기존
`data/news_poc/pipeline/collect.py`의 Google News RSS 요청, 파싱, 품질 검사와 정규화 규칙을
재사용하되 CLI, 일별 수집 계획, 파일 체크포인트를 호출 경로에 포함하지 않는다.

```text
NewsSearchProvider.search(query, from_date, to_date, limit)
```

한 실행의 제한은 다음과 같다.

- 외부 검색 시도 최대 1회
- RSS 요청 최대 1개
- 결과 후보 최대 20건
- 최근 90일 범위
- provider 전체 제한시간 30초
- 403, 429, 비 RSS 응답은 즉시 중단

검색 질의는 정식 기업명과 부족한 범위, JD 직무명을 조합한다. LLM은 검색 범위를 고르지만
임의 URL을 만들 수 없으며 provider가 만든 Google News RSS URL만 호출한다.

외부 결과는 현재 응답에만 사용하고 `news_article`이나 다른 DB에 저장하지 않는다. 저장
뉴스와 합친 뒤 같은 중복 제거 규칙을 적용한다. 외부 검색이 실패해도 저장 근거가 있으면
그 근거만으로 계속 분석한다.

## 6. 분석과 근거 수준

LLM은 후보 기사를 기업·산업·직무 범위로 분류하고 변화 신호별로 묶으며, 각 신호에 사용할
기사 ID와 JD 관련성을 구조화해 반환한다. 서버는 다음을 검증한다.

- 모든 인용 기사 ID가 실제 후보에 존재하는가
- 제목, URL, 발행일, 출처가 후보 메타데이터와 일치하는가
- JD 관련성이 실제 `ai_job_contexts`의 직무명·요구사항을 참조하는가
- 준비 항목이 사실 확인이나 경험 점검에 머물고 글쓰기·면접 답안을 생성하지 않는가
- 기업·산업·직무 변화가 근거 없이 생성되지 않았는가

근거 수준은 모델이 자유롭게 정하지 않는다. 모델이 묶은 신호에 대해 서버가 인용 수,
독립 출처 수, 최신성으로 계산한다.

- `HIGH`: 최근 30일 안의 독립 출처 2개 이상
- `MEDIUM`: 최근 30일 출처 1개 또는 90일 안의 독립 출처 2개 이상
- `LOW`: 90일 안의 출처 1개
- `INSUFFICIENT`: 유효한 출처 없음

서버가 계산한 등급과 출처 메타데이터만 최종 응답에 노출한다. LLM은 등급의 의미를 설명할
수는 있지만 상향할 수 없다.

## 7. 총괄 에이전트 연동

총괄 요청의 `agent_contexts`에 `news` 컨텍스트를 추가한다.

```json
{
  "agent_contexts": {
    "jd": {
      "job_context_id": "jctx_abc123"
    },
    "news": {
      "job_context_id": "jctx_abc123",
      "corp_code": "00126380"
    }
  }
}
```

`news` worker가 단독으로 실행될 수 있도록 자신의 컨텍스트에 두 식별자를 모두 둔다.
`job_context_id`가 `jd`와 `news`에 반복되는 것은 영속 데이터 중복이 아니라 worker별 명시적
호출 계약이며, 기존 어댑터 격리를 유지한다.

`NewsAgentAdapter`는 두 값이 모두 있을 때만 사용 가능하다. 뉴스 worker는 자소서, 이력서,
경험, 포트폴리오 문서를 읽지 않는다. JD, position, news worker가 함께 선택되면 병렬 실행하고
총괄 에이전트가 결과를 조합한다.

계획과 결과 계약은 `news`를 허용하도록 확장한다. 사용자 지시가 최근 이슈, 기업 변화,
산업 변화, 직무 트렌드나 그 영향을 요구할 때 선택한다. 문장 첨삭이나 경험 구체화만 요구할
때는 선택하지 않는다.

## 8. 컴포넌트

구현 위치는 `ai/news_intelligence/`다.

```text
api.py                 직접 분석 API와 오류 변환
contracts.py           요청·응답 및 모델 출력 스키마
service.py             전체 분석 순서
repository.py          PostgreSQL JD·기업·저장 뉴스 조회
search_provider.py     제한된 외부 검색 인터페이스와 Google RSS 구현
coverage.py            건수·최신성·범위 충분성 판정
evidence.py            중복 제거와 근거 수준 계산
prompt.py              범위 분류·신호 추출 프롬프트
model.py               Qwen 호출 경계
render.py              검증된 구조로 사용자 메시지 생성
```

`ai/serve.py`는 `/news` 앱을 추가한다. `ai/supervisor/contracts.py`, `adapters.py`, 그래프의
허용 에이전트 계약은 `news`를 추가하되 기존 JD·position 서비스 내부 로직은 변경하지 않는다.

## 9. 처리 흐름

```text
validate_request
  -> load_job_and_company
  -> load_stored_news
  -> deduplicate_candidates
  -> classify_coverage
  -> search_external_if_needed
  -> merge_and_deduplicate
  -> extract_signals
  -> validate_citations_and_boundaries
  -> calculate_evidence_levels
  -> render_response
```

신호 추출과 범위 분류의 모델 출력이 스키마·인용 검증에 실패하면 검증 피드백을 포함해 한 번
재시도한다. 두 번째도 실패하면 `502`로 처리하며 검증되지 않은 부분 결과는 반환하지 않는다.

## 10. 실패 처리

- 요청 형식, 빈 식별자: `422`
- 존재하지 않는 `job_context_id`: `404 JOB_CONTEXT_NOT_FOUND`
- 존재하지 않는 `corp_code`: `404 COMPANY_NOT_FOUND`
- PostgreSQL 조회 실패: `503 NEWS_SOURCE_UNAVAILABLE`
- 외부 검색 실패 + 저장 근거 있음: 저장 근거로 `200`
- 외부 검색 실패 + 저장 근거 없음: `200`, `INSUFFICIENT_EVIDENCE`
- 모델 연결 또는 검증 재시도 실패: `502`
- 총괄 실행에서 news만 실패: 기존 규칙대로 `200`, `PARTIAL`
- 총괄에서 선택된 모든 worker 실패: 기존 규칙대로 `502 ALL_AGENTS_FAILED`

Spring이 필수 컨텍스트 누락을 검토방 진입 전에 처리한다. AI의 요청 검증은 잘못된 내부 호출을
막는 방어선이며, 누락을 `PARTIAL`로 숨기지 않는다.

## 11. 실행과 시간 제한

V1은 총괄 에이전트와 동일하게 동기식·무상태로 실행한다. checkpointer나 뉴스 전용 실행
테이블을 추가하지 않는다. 총괄 요청 전체 목표 제한시간은 120초다. 뉴스 worker는 요청별
monotonic 90초 누적 예산을 사용하고, Qwen 각 호출과 RSS provider는 30초와 남은 예산 중
작은 값을 제한시간으로 사용한다. DB 연결은 5초이며 남은 예산이 부족하면 시작하지 않는다.
DB 각 조회의 transaction-local statement_timeout도 5초와 남은 예산 중 작은 값이다.
모델 출력 재시도는 같은 예산을 소비하고, 만료 뒤 재시도와 성공 반환을 차단한다.

이는 best-effort 제한이며 hard wall-clock 보장이 아니다. DNS·다중 주소 연결·네트워크 대기와
urllib Qwen 응답의 점진적 전송은 동기 호출을 deadline 이후까지 붙잡을 수 있다. 총괄의
계획·집계와 다른 worker의 실행도 뉴스 예산에 포함되지 않는다. 엄격한 전체 취소에는 별도의
취소 가능한 실행 경계가 필요하며, Spring HTTP timeout은 실행 중인 AI 작업을 중단하지 않는다.

Spring은 HTTP 제한시간과 호출 재시도 정책을 정한다. AI 총괄 계층은 같은 worker를 자동
재실행하지 않는다.

## 12. 테스트와 평가

단위 테스트는 외부 Qwen, Google RSS, PostgreSQL 없이 대역으로 실행한다.

- 요청이 `job_context_id`, `corp_code`를 필수로 검증하는가
- 저장 뉴스가 충분할 때 외부 provider를 호출하지 않는가
- 건수, 최신성, 범위가 부족할 때만 provider를 한 번 호출하는가
- URL, guid, 정규화 제목 중복이 제거되는가
- 외부 결과가 저장소에 기록되지 않는가
- 존재하지 않는 기사 인용과 메타데이터 변조가 거절되는가
- 근거 등급이 출처 수와 날짜로 결정적으로 계산되는가
- 기사 제목과 JD에 없는 기업·산업·직무 주장을 거절하는가
- 외부 검색 실패 시 저장 근거 fallback과 `INSUFFICIENT_EVIDENCE`가 구분되는가
- 직접 API가 `/news`에 마운트되는가
- 총괄 계획이 `news`를 선택하고 JD·position과 병렬 실행하는가
- news 단독 실패가 `PARTIAL`, 전체 실패가 `502`가 되는가
- 기존 JD·position·supervisor 테스트가 그대로 통과하는가

평가 fixture는 기업 변화, 산업 변화, 직무 변화, 근거 부족, 상충 기사 사례를 포함한다.
사람이 기사 근거와 JD 관련성을 검수하기 전에는 자동 점수를 제품 품질 수치로 발표하지 않는다.

## 13. 구현 범위 밖

- Spring의 `cover_letter` 마이그레이션과 컨텍스트 조립 구현
- 프론트엔드 표시 방식
- 외부 검색 결과의 DB 적재
- 기사 본문 크롤링
- 임베딩·벡터 검색
- 뉴스 수집 배치 수정
- 자소서 문장이나 면접 답변 생성
- 총괄 에이전트의 checkpointer와 별도 실행 DB
- 비동기 작업 큐와 스트리밍 응답

## 14. 재검토 조건

- 기사 제목만으로 변화 신호를 검증하기 어려워 본문 수집 계약을 확보한 경우
- 저장 뉴스의 누락률이 높아 외부 검색이 대부분의 요청에서 실행되는 경우
- 기업·산업·직무를 한 번의 외부 질의로 보완하지 못하는 경우
- 동기 요청이 Spring HTTP 제한시간을 반복적으로 초과하는 경우
- 여러 기업이나 여러 JD를 한 실행에서 비교해야 하는 경우
- 백엔드의 `job_context_id`, `corp_code` 전달 계약이 변경되는 경우
