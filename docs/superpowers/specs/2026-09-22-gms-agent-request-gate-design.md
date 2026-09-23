---
title: GMS 에이전트 요청 게이트 설계
status: proposed
date: 2026-09-22
scope: AI 서버를 통과하는 검토방 에이전트의 GMS 호출
---

# GMS 에이전트 요청 게이트 설계

## 목표

검토방 에이전트가 동시에 여러 GMS 호출을 보내 429(요청 횟수 초과)를 만드는 일을 줄인다.
일시적인 폭주는 사용자에게 실패로 보이지 않게 대기열에서 흡수한다. 한도를 넘은 상태가
지속되어 정해진 대기 시간 안에 처리할 수 없을 때만, 사용자가 이해할 수 있는 재시도 안내를
보여 준다.

이 설계의 첫 적용 대상은 Python AI 서버를 통과하는 총괄·JD·포지션·글쓰기·뉴스·기업 분석
에이전트의 GMS 호출이다. 현재 배포는 AI 컨테이너 한 개, Python 프로세스 한 개로 구성되어
있으므로 외부 큐 없이도 이 호출 집합에는 하나의 공용 게이트를 적용할 수 있다.

## 현재 원인과 제약

- 총괄 자동 검토는 계획 수립, 여러 담당의 병렬 실행, 결과 종합을 한 요청에 포함한다.
  각 단계가 GMS를 사용하면 짧은 시간에 여러 호출이 쌓인다.
- `ai.llm.gms.complete()`는 429를 일반 HTTP 오류로 전파한다. 담당과 API 계층이 이를
  일반 502 실패로 바꾸기 때문에, Spring과 화면은 요청 초과인지 알 수 없다.
- 현재 `infra/docker-compose.yml`에는 AI 서비스의 replica 설정이 없고, `ai.serve`는
  단일 Python 프로세스로 시작한다. 따라서 프로세스 메모리의 동기화 객체가 검토방 GMS
  호출 전체를 제어할 수 있다.
- Spring에는 공고 파싱을 위한 직접 GMS 호출 경로도 있다. 이것은 AI 서버 게이트를 통과하지
  않는다. 이번 슬라이스에서는 해당 경로의 429 사용자 안내만 맞추고, 호출 큐 통합은 하지
  않는다.

## 선택한 접근

`ai.llm` 패키지에 프로세스 공용의 동기식 `GmsRequestGate`를 둔다. 모든 실제 GMS HTTP
요청은 이 게이트에서 순서를 기다린 뒤 전송한다. 게이트는 다음 상태를 가진다.

- FIFO 대기 순서
- 현재 실행 중인 호출 수
- 마지막 전송 시각
- 다음 전송이 허용되는 시각(`blocked_until`)

호출은 세 조건이 모두 충족될 때만 전송한다.

1. 자신의 FIFO 차례다.
2. 실행 중인 호출 수가 `GMS_MAX_CONCURRENT_REQUESTS`보다 작다.
3. 현재 시각이 마지막 전송 시각 + `GMS_MIN_INTERVAL_SECONDS` 및 `blocked_until` 이후다.

기본값은 보수적으로 동시 1건, 호출 간 1초, 실행 중 요청을 제외한 대기열 최대 40건, 큐 최대
대기 45초, 429 뒤 기본 냉각 10초, 429 재시도 1회다. 대기열이 가득 찬 새 요청은 즉시
`LlmRateLimitedError`로 끝내고 사용자에게 재시도 안내를 보인다. 운영 환경에서는 환경 변수로
조절하며, 실제 GMS 한도와 QA 계측 결과가
확인되기 전에는 기본값을 공격적으로 올리지 않는다.

## 흐름

```text
에이전트 모델 호출
  -> ai.llm.gms.complete
      -> GmsRequestGate.run(send)
          -> FIFO 대기 / 최소 간격 대기 / 429 냉각 대기
          -> GMS generateContent
              -> 성공: 결과 반환
              -> 429: blocked_until 갱신, 같은 작업을 한 번 재대기
              -> 대기 한도 초과: LlmRateLimitedError
  -> 담당 API
      -> HTTP 429 { code: "GMS_RATE_LIMITED", retry_after_seconds? }
  -> Spring AI client
      -> ErrorCode.AI_RATE_LIMITED 및 사용자용 실패 메시지
  -> 검토방 말풍선
      -> "AI 요청이 몰려 답변을 준비하지 못했습니다. 잠시 후 다시 시도해 주세요."
```

429 응답에 `Retry-After`가 있으면 초 단위 또는 HTTP-date를 해석해 그 시각까지 큐를
막는다. 헤더가 없거나 유효하지 않으면 설정된 냉각 시간을 사용한다. 더 긴 냉각이 이미
설정되어 있으면 짧게 덮어쓰지 않는다. 재시도는 생성 API가 외부 상태를 바꾸지 않는다는
전제에서 같은 요청에 한 번만 허용한다.

큐 대기 시간은 모델 호출자가 준 timeout과 별도로 무한정 늘어나지 않는다. 호출이 큐에
들어온 때부터 `GMS_QUEUE_TIMEOUT_SECONDS`가 지나면 HTTP 요청을 시작하지 않고
`LlmRateLimitedError`로 종료한다. 호출을 시작한 뒤의 네트워크 timeout은 남은 예산과 기존
호출 timeout 중 작은 값으로 제한한다.

## 오류 계약

### Python 공통 계층

`ai.llm.contracts`에 `LlmRateLimitedError`를 추가한다. 이 예외는 공급자 이름과 선택적
`retry_after_seconds`를 가지며, GMS HTTP 429와 게이트 대기 만료만 이 예외로 변환한다.
다른 4xx/5xx, 연결 오류, 구조화 출력 오류의 기존 의미는 바꾸지 않는다.

기업 분석의 `GmsStructuredClient`처럼 기존 공통 예외를 서비스별 예외로 옮기는 경로도
이 오류를 보존하는 전용 예외를 사용한다. 각 AI FastAPI 앱은 이를 일관되게 HTTP 429와
`GMS_RATE_LIMITED` 코드로 반환한다. 내부 상세 원인과 GMS 응답 본문은 노출하지 않는다.

### Spring 및 검토방

`AgentAiCall`은 AI 서버의 HTTP 429를 `AI_RATE_LIMITED`로 매핑한다. 기존 사용자별
`ANALYSIS_RATE_LIMITED`와 구분한다. 전자는 서비스 자체가 GMS 공급자 한도에 막힌 경우이고,
후자는 해당 사용자의 검토방 발화 한도를 넘긴 경우다.

`SupervisorTurnRunner`는 이미 담당별 실패 자리에 오류를 남기는 구조를 사용한다. 따라서
429가 전체 총괄 실패로 오든 특정 담당 실패 결과로 오든 동일한 고정 안내를 해당 자리에
남긴다. `Retry-After`를 사용자에게 정확한 시간으로 약속하지 않는다. 큐가 내부에서
재시도해도 끝내 만료된 경우에만 이 안내가 보인다.

공고 URL 파싱의 Spring 직접 GMS 호출은 이번에 큐에 넣지 않는다. 다만 직접 GMS가 429를
돌려주면 해당 화면도 `AI_RATE_LIMITED`에 준하는 재시도 안내를 반환하도록 오류 변환을
보완한다.

## 관측성

민감한 프롬프트나 응답 본문 없이 다음 구조화 로그 이벤트를 남긴다.

- `gms_gate_queued`: 대기열 길이, 호출 종류, deadline
- `gms_gate_started`: 실제 대기 시간, 실행 중 수
- `gms_gate_rate_limited`: Retry-After 유무, 적용 냉각 시간, 재시도 횟수
- `gms_gate_succeeded`: 대기 시간, 총 소요 시간, 재시도 여부
- `gms_gate_expired`: 대기 시간, 만료 사유

호출 종류는 스키마 이름 또는 서비스 이름처럼 제한된 내부 분류만 사용한다. API key,
사용자 문서, 프롬프트, 원본 GMS 응답은 로그에 넣지 않는다.

QA는 자동 검토를 동시에 여러 건 시작해 다음을 확인한다.

- 동시에 GMS로 나가는 수가 설정 상한을 넘지 않는다.
- 최소 간격이 지켜진다.
- 첫 429 뒤 새 호출이 즉시 외부로 나가지 않고 냉각 대기한다.
- 냉각 뒤 재시도에 성공하면 사용자 말풍선이 실패 상태가 되지 않는다.
- 최대 대기 시간을 넘긴 요청만 `AI_RATE_LIMITED` 안내를 보인다.
- 429가 아닌 400 schema fallback, 5xx, 연결 실패의 기존 동작이 바뀌지 않는다.

## 구성

AI 컨테이너 환경 변수:

| 변수 | 기본값 | 의미 |
| --- | ---: | --- |
| `GMS_MAX_CONCURRENT_REQUESTS` | `1` | 동시에 전송할 GMS HTTP 요청 수 |
| `GMS_MIN_INTERVAL_SECONDS` | `1` | 두 GMS 요청 시작 간 최소 간격 |
| `GMS_QUEUE_TIMEOUT_SECONDS` | `45` | 큐에서 기다릴 수 있는 최대 시간 |
| `GMS_RATE_LIMIT_COOLDOWN_SECONDS` | `10` | Retry-After가 없을 때 429 뒤 멈출 시간 |
| `GMS_RATE_LIMIT_RETRY_COUNT` | `1` | 429 후 같은 요청에 허용할 재대기 횟수 |
| `GMS_MAX_QUEUED_REQUESTS` | `40` | 실행 중 요청을 제외하고 FIFO로 대기시킬 최대 요청 수 |

값은 애플리케이션 시작 시 검증한다. 음수, 0 이하의 timeout, 동시성 0, 정수가 아닌 값은
설정 오류로 AI 서비스를 시작하지 않는다. 호출 중 환경 변수를 다시 읽어 동작을 바꾸지 않는다.

## 구현 경계

변경 대상:

- `ai/llm/gms.py`, `ai/llm/contracts.py`, 새 `ai/llm/gms_gate.py`
- GMS 예외를 API 오류로 바꾸는 AI 담당 API와 기업 분석 GMS 어댑터
- 검토방 AI 호출의 HTTP 오류를 바꾸는 Spring `AgentAiCall` 및 관련 테스트
- AI·backend의 환경 예시와 Docker Compose 환경 전달
- Python 단위 테스트, AI API 테스트, Spring 단위 테스트

이번 범위 밖:

- Redis, RabbitMQ, Celery 등 새 인프라 또는 영속 큐
- AI 서버 replica 확장
- 서버 재시작 뒤 대기열·실행 작업 복구
- Spring 직접 GMS 호출을 Python 공용 큐로 우회시키는 API 신설
- 사용자에게 큐 순번이나 정확한 완료 시각 제공

## 실패와 복구

프로세스가 재시작되면 메모리 큐는 사라진다. 현재 검토방도 작업 실행을 별도 영속 큐에
저장하지 않으므로, 이 경우 기존과 같이 해당 턴은 완료 보장이 없다. 사용자는 새 요청으로
다시 시도할 수 있다. 이 제한은 무시하지 않고 운영 로그로 재시작과 만료의 상관관계를
관찰한다.

AI 서버가 여러 인스턴스로 늘어나거나, 대기 중인 요청의 재시작 복구가 제품 요구가 되면
이 게이트를 Redis 기반 토큰 버킷과 영속 작업 큐로 교체한다. 공용 인터페이스를
`GmsRequestGate.run(...)`으로 제한해 그 전환 시 공급자 호출부를 다시 고치지 않게 한다.

## 테스트

시간은 주입 가능한 clock과 sleeper로 제어해 실제 대기 없이 검증한다.

- FIFO 순서와 동시성 상한
- 최소 간격 강제
- 429의 `Retry-After` 적용과 기본 냉각 fallback
- 재시도 성공, 재시도 횟수 소진, 큐 timeout
- 400 `too many states` schema fallback 요청도 게이트를 통과하는지
- 429가 AI API에서 `GMS_RATE_LIMITED` HTTP 429로 바뀌는지
- Spring이 이를 `AI_RATE_LIMITED`와 고정 사용자 안내로 바꾸는지
- 기존 vLLM과 GMS 비-429 오류 동작 회귀

