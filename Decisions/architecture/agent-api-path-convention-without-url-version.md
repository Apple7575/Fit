---
type: decision
status: active
date: 2026-09-15
project: S15P21A504 멀티에이전트 자소서 분석
supersedes: [architecture/agent-api-path-convention]
superseded_by: []
---

# URL 버전 없는 에이전트 API 경로 규칙

## 문제

이전 결정은 AI 내부 API에 `/internal/v1`을 사용하도록 정했다. 그러나 아직 Spring과
FastAPI의 연동이 배포되지 않았고, 현재 프로젝트의 공개 API도 URL 버전을 사용하지 않는다.
이 단계에서 URL 버전을 추가하면 실제로 공존하는 계약 없이 경로만 길어진다.

## 검토한 선택지

1. 공개 API와 내부 API 모두 URL 버전을 사용한다.
2. 내부 API에만 `/v1`을 사용한다.
3. URL 버전을 사용하지 않고 요청·응답 스키마와 직무 프로필만 버전 관리한다.

## 결정

- 브라우저용 공개 API는 기존 `/api/{plural-resource}` 형식을 유지한다.
- AI FastAPI는 `/{domain}/internal/{plural-resource}` 형식을 사용한다.
- 포지션 분석은 `POST /position/internal/analyses`로 실행한다.
- JD 내부 API도 `/jd/internal/...` 아래에서 리소스형 이름만 사용한다.
- `/jd/internal/jd/analyze`는 `/jd/internal/analyses`로 변경하고 호환 경로를 남기지 않는다.
- URL에는 버전을 넣지 않는다.
- `position-analysis-v1.json`, `backend-v1`, `prompt_version`처럼 데이터 계약, 직무 프로필,
  프롬프트 버전은 계속 명시한다.

## 이유

현재 내부 API 호출자는 같은 저장소의 Spring 하나이며 아직 연동 전이므로 URL 버전으로
보호해야 할 기존 소비자가 없다. 반면 모델 출력 계약은 평가 재현성과 검증 호환성 때문에
버전이 필요하다. URL과 데이터 계약의 버전 필요성을 분리하는 편이 현재 단계에 맞다.

## 재검토 조건

- 서로 다른 API 계약을 사용하는 Spring 버전이 동시에 배포되는 경우
- FastAPI를 외부 클라이언트가 직접 호출하게 되는 경우
- 무중단 마이그레이션을 위해 구형·신형 내부 API를 동시에 운영해야 하는 경우

## 관련 문서

- [[architecture/agent-api-path-convention]]
- [[product/jd-api-boundary]]
- [[docs/superpowers/specs/2026-09-15-position-prompt-agent-design]]
