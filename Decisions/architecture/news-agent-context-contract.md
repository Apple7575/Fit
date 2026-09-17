---
type: decision
status: active
date: 2026-09-16
project: S15P21A504 뉴스·트렌드 에이전트
supersedes: []
superseded_by: []
---

# 뉴스 에이전트 컨텍스트 전달 계약

## 문제

뉴스 에이전트가 현재 검토방의 채용공고와 기업을 정확히 식별하려면 `job_context_id`와
`corp_code`가 필요하다. AI가 `cover_letter`를 직접 조회하거나 기업명으로 코드를 추정할지,
Spring이 검증한 식별자를 전달할지 결정해야 했다.

## 검토한 선택지

1. AI가 기업명으로 `company`를 검색해 `corp_code`를 추정한다.
2. AI가 `cover_letter_id`를 받아 Spring 소유 테이블을 직접 조회한다.
3. Spring이 `cover_letter`의 `job_context_id`와 `corp_code`를 조회해 AI 요청에 전달한다.

## 트레이드오프

- 기업명 역검색은 API가 단순하지만 동명이인, 계열사, 표기 차이로 다른 기업을 고를 수 있다.
- AI의 직접 조회는 호출 인자를 줄이지만 사용자·자소서 소유권과 Spring 스키마에 AI가
  결합된다.
- Spring 전달은 요청에 식별자가 명시적으로 반복되지만 소유권과 데이터 경계를 유지하고
  worker를 독립적으로 테스트할 수 있다.

## 결정

- Spring은 `cover_letter`에 `job_context_id`와 `corp_code` 외래키를 관리한다.
- 검토방 요청 시 Spring이 자소서 소유권과 두 식별자를 검증한 뒤 총괄 에이전트에 전달한다.
- 총괄 요청의 `agent_contexts.news`는 `job_context_id`와 `corp_code`를 모두 포함한다.
- AI는 `cover_letter`와 `agent_room`을 직접 조회하지 않고 기업명으로 `corp_code`를 추정하지
  않는다.
- 뉴스 에이전트는 `corp_code`로 저장 뉴스를 조회하고, 외부 검색용 정식 기업명은
  `company`에서 조회한다.
- 필수 식별자 누락과 기존 자소서 보정은 Spring이 처리한다. AI는 잘못된 내부 요청을
  스키마 오류로 거절한다.

## 이유

사용자 소유 데이터와 검토방의 원본 책임은 Spring에 있고 AI는 분석 책임만 가져야 한다.
명시적인 식별자를 전달하면 기업명 추정 오류를 없애고 총괄·단독 뉴스 API가 같은 계약을
사용할 수 있다.

## 재검토 조건

- 한 자소서가 여러 JD 또는 여러 기업을 동시에 비교하게 되는 경우
- Spring과 AI 사이에 공용 지원 세션 리소스나 컨텍스트 조회 API를 도입하는 경우
- `news_article`의 기업 식별 기준이 `corp_code`에서 다른 키로 변경되는 경우
- Spring이 두 식별자를 보장할 수 없는 새로운 작성 흐름을 추가하는 경우

## 관련 문서

- [[Decisions/product/jd-api-boundary]]
- [[Decisions/architecture/agent-api-path-convention-without-url-version]]
- [[docs/superpowers/specs/2026-09-16-news-trend-agent-design]]
