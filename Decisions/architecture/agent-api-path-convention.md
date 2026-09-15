---
type: decision
status: superseded
date: 2026-09-15
project: S15P21A504 멀티에이전트 자소서 분석
supersedes: []
superseded_by: [architecture/agent-api-path-convention-without-url-version]
---

# 에이전트 API 경로 규칙

## 문제

Spring의 채팅 API는 방과 메시지를 중심으로 구성되어 있지만, AI FastAPI에는
`/jd/internal/job-contexts`와 `/jd/internal/jd/analyze`처럼 리소스형 경로와
동사형·도메인 중복 경로가 함께 존재한다. 포지션 에이전트를 추가하면서 별도 공개 채팅
경로까지 만들면 같은 사용자 동작을 여러 API가 표현하게 된다.

## 검토한 선택지

1. 에이전트마다 `/jd/chat`, `/position/chat` 같은 공개 API를 만든다.
2. 공개 채팅은 Spring의 방 API로 통일하고, AI 내부 API만 에이전트 도메인별로 둔다.
3. Spring과 FastAPI를 구분하지 않고 하나의 공통 경로 체계를 사용한다.

## 트레이드오프

- 에이전트별 공개 API는 단일 에이전트 구현은 단순하지만 멀티에이전트 방에서 대화 저장,
  인증, 턴 상태를 중복 구현하게 된다.
- 공개 채팅과 AI 내부 실행을 분리하면 경계가 명확하지만 Spring과 FastAPI 사이의 요청
  계약을 별도로 관리해야 한다.
- 하나의 경로 체계는 겉보기에는 단순하지만 사용자 리소스와 내부 모델 실행의 권한 및
  수명주기가 섞인다.

## 결정

- 브라우저가 사용하는 공개 채팅 API는 Spring의 `/api/rooms` 계층으로 통일한다.
- 에이전트별 `/chat` 공개 경로는 만들지 않는다.
- 방의 에이전트 설정은 `PATCH /api/rooms/{roomId}/agents/{agentKey}`로 변경한다.
- 사용자 발화는 `POST /api/rooms/{roomId}/messages`, 조회는 같은 경로의 `GET`을 사용한다.
- 비동기 실행 상태는 `GET /api/rooms/{roomId}/turns/{turnId}`로 조회한다.
- AI FastAPI의 내부 경로는 `/{domain}/internal/v1/{plural-resource}` 형식을 사용한다.
- 경로에는 동사를 넣지 않고, 생성·조회·수정·삭제는 HTTP 메서드로 구분한다.
- 포지션 에이전트의 한 턴은 `POST /position/internal/v1/analyses`로 실행한다. 첫 분석과
  후속 답변 반영을 별도 경로로 나누지 않는다.
- 미연동 상태인 JD 내부 API도 `/jd/internal/v1/...`로 변경하며
  `/jd/internal/jd/analyze` 호환 경로는 남기지 않는다.

## 이유

사용자는 어떤 에이전트와 대화하더라도 동일한 방·메시지 API를 사용해야 한다. Spring은
인증, 방 소유권, 대화 저장과 멀티에이전트 턴 조정을 담당하고, FastAPI는 모델 실행과 출력
검증만 담당하면 각 시스템의 책임이 겹치지 않는다. 버전을 내부 경로에 명시하면 모델 입력과
출력 계약을 변경할 때 기존 호출자와 충돌하지 않는다.

## 재검토 조건

- AI 서비스가 단일 배포 단위에서 도메인별 독립 서비스로 분리되는 경우
- 메시지 스트리밍을 도입해 현재 비동기 턴 조회 방식으로 표현할 수 없는 경우
- 외부 클라이언트가 AI FastAPI를 직접 호출해야 하는 제품 요구가 생기는 경우

## 관련 문서

- [[product/jd-api-boundary]]
- [[docs/superpowers/specs/2026-09-15-position-prompt-agent-design]]
