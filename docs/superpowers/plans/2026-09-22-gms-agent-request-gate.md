# GMS 에이전트 요청 게이트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검토방 에이전트의 GMS 호출을 프로세스 공용 FIFO 게이트로 제어하고, 429를 내부 재대기 또는 사용자용 재시도 안내로 처리한다.

**Architecture:** `ai.llm.gms`의 실제 HTTP 전송을 `GmsRequestGate`로 감싼다. 게이트는 단일 AI 프로세스에서 FIFO 순서, 동시성 상한, 최소 호출 간격, 429 냉각과 최대 대기를 제어한다. 만료된 429는 Python 오류 → FastAPI 429 → Spring `AI_RATE_LIMITED` → 검토방 실패 말풍선으로 보존한다.

**Tech Stack:** Python 3.12 stdlib `threading`·`time`·`email.utils`, FastAPI, pytest, Java 21/Spring Boot, JUnit 5/Mockito, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-22-gms-agent-request-gate-design.md`

## Global Constraints

- Redis, RabbitMQ, Celery, 새 영속 큐를 추가하지 않는다.
- 첫 적용 대상은 AI 서버를 통과하는 검토방 에이전트 GMS 호출이다.
- 기본값은 동시 1건, 최소 간격 1초, 대기열 최대 40건, 최대 큐 대기 45초, 429 기본 냉각 10초, 재시도 1회다.
- API key, 프롬프트, 사용자 문서, GMS 원문 응답을 로그에 기록하지 않는다.
- 429가 아닌 vLLM 오류, GMS 4xx/5xx, `too many states` fallback의 의미를 바꾸지 않는다.
- Spring 직접 GMS 호출은 큐에 넣지 않고 429 오류 안내만 맞춘다.

---

## File Structure

- Create `ai/llm/gms_gate.py`: 환경 설정, FIFO 대기, 429 냉각, 재시도, 구조화 로그.
- Create `ai/tests/llm/test_gms_gate.py`: 주입 가능한 clock/sleeper를 쓰는 단위 테스트.
- Modify `ai/llm/contracts.py`, `ai/llm/gms.py`, `ai/llm/__init__.py`: 공용 오류와 전송 경계.
- Modify `ai/company_analysis/llm.py` 및 AI 담당 API: 제한 초과를 HTTP 429로 보존.
- Modify Spring `ErrorCode`, `AgentAiCall`, `AgentLlmClient`: 사용자 오류 코드·직접 GMS 429 처리.
- Modify AI/Java 테스트와 `ai/.env.example`, `infra/docker-compose.yml`, `infra/.env.prod.example`.

### Task 1: FIFO GMS 요청 게이트

**Files:**
- Create: `ai/llm/gms_gate.py`
- Create: `ai/tests/llm/test_gms_gate.py`

**Interfaces:**
- Produces: `GmsGateSettings.from_env(values: Mapping[str, str])`, `GmsRequestGate(settings, *, clock, sleeper, logger)`, `run(operation: Callable[[], T], *, operation_name: str) -> T`, `rate_limited(retry_after_seconds: float | None) -> None`.

- [ ] **Step 1: FIFO·간격·동시성 실패 테스트를 작성한다.**

```python
def test_runs_operations_in_ticket_order_and_respects_minimum_interval():
    clock = FakeClock()
    gate = GmsRequestGate(GmsGateSettings(1, 1.0, 45.0, 10.0, 1),
                          clock=clock.now, sleeper=clock.sleep)
    seen = []
    assert gate.run(lambda: seen.append("first") or "one", operation_name="plan") == "one"
    assert gate.run(lambda: seen.append("second") or "two", operation_name="aggregate") == "two"
    assert seen == ["first", "second"]
    assert clock.sleeps == [1.0]
```

별도 테스트는 `threading.Barrier`와 두 operation으로 실행 중 수가 절대 1을 넘지 않는지 확인한다.

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `python -m pytest ai/tests/llm/test_gms_gate.py -v`

Expected: FAIL — `GmsRequestGate`를 찾지 못한다.

- [ ] **Step 3: 최소 구현을 작성한다.**

```python
@dataclass(frozen=True)
class GmsGateSettings:
    max_concurrent_requests: int = 1
    min_interval_seconds: float = 1.0
    queue_timeout_seconds: float = 45.0
    rate_limit_cooldown_seconds: float = 10.0
    rate_limit_retry_count: int = 1

class GmsRequestGate:
    def run(self, operation, *, operation_name):
        # Condition 아래에서 ticket 순서와 deadline을 기다리고 operation은 lock 밖에서 실행한다.
        ...
```

`from_env`는 다섯 변수의 기본값을 적용하고 동시성 1 미만, timeout 0 이하, 음수 간격, 음수 retry를 `ValueError`로 거절한다. `Condition.wait(남은 시간)`만 사용하며 로그에는 operation name, queue length, wait seconds, retry count만 기록한다.

- [ ] **Step 4: 테스트를 통과시킨다.**

Run: `python -m pytest ai/tests/llm/test_gms_gate.py -v`

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

Run: `git add ai/llm/gms_gate.py ai/tests/llm/test_gms_gate.py && git commit -m "feat: add in-process GMS request gate"`

### Task 2: 429 냉각·재대기와 공용 오류 계약

**Files:**
- Modify: `ai/llm/contracts.py`
- Modify: `ai/llm/gms_gate.py`
- Modify: `ai/tests/llm/test_gms_gate.py`

**Interfaces:**
- Produces: `LlmRateLimitedError(provider: str, retry_after_seconds: int | None)`와 429 뒤 한 번 재대기하는 `run` 동작.

- [ ] **Step 1: 429 냉각과 만료 실패 테스트를 작성한다.**

```python
def test_rate_limit_blocks_next_request_then_retries_once():
    attempts = 0
    def call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Upstream429(retry_after_seconds=7)
        return "ok"
    assert gate.run(call, operation_name="plan") == "ok"
    assert attempts == 2
    assert 7.0 in clock.sleeps

def test_queue_timeout_raises_rate_limited_error_without_sending():
    with pytest.raises(LlmRateLimitedError):
        expired_gate.run(lambda: pytest.fail("must not send"), operation_name="chat")
```

추가 테스트는 Retry-After 미제공 시 10초 fallback, 더 짧은 새 cooldown이 기존 `blocked_until`을 줄이지 않음, retry count 소진을 확인한다.

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `python -m pytest ai/tests/llm/test_gms_gate.py -v`

Expected: FAIL — 제한 초과 재대기와 전용 오류가 없다.

- [ ] **Step 3: 오류와 냉각 로직을 구현한다.**

```python
class LlmRateLimitedError(LlmError):
    def __init__(self, provider: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(f"{provider} rate limit exceeded")
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds
```

429만 잡아 `blocked_until = max(blocked_until, clock() + cooldown)`으로 갱신하고 `notify_all()`한다. 요청별 deadline 또는 재시도 횟수를 넘기면 위 오류를 올리고 다른 예외는 바꾸거나 재시도하지 않는다.

- [ ] **Step 4: 테스트를 통과시킨다.**

Run: `python -m pytest ai/tests/llm/test_gms_gate.py -v`

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

Run: `git add ai/llm/contracts.py ai/llm/gms_gate.py ai/tests/llm/test_gms_gate.py && git commit -m "feat: retry GMS rate limits through request gate"`

### Task 3: GMS 어댑터를 게이트와 429 헤더에 연결한다

**Files:**
- Modify: `ai/llm/gms.py`
- Modify: `ai/llm/__init__.py`
- Modify: `ai/tests/llm/test_gms.py`

**Interfaces:**
- Consumes: `GmsRequestGate.run`, `LlmRateLimitedError`.
- Produces: `complete_structured()`가 429에 대해 재대기하고 Retry-After를 보존한 오류를 반환한다.

- [ ] **Step 1: 어댑터 통합 실패 테스트를 작성한다.**

```python
def test_429_retries_once_using_retry_after_header(self):
    opener.return_value.open.side_effect = [_HttpError(429, "busy", {"Retry-After": "7"}), _Response(OK)]
    result = complete_structured(self.CONFIG, [{"role": "user", "content": "x"}],
                                 schema=self.SCHEMA, schema_name="x", max_tokens=100)
    assert result["output"] == {"answer": "ok"}
    assert opener.return_value.open.call_count == 2
```

두 번째 테스트는 재시도 뒤 429일 때 `LlmRateLimitedError.retry_after_seconds == 7`인지, 세 번째 테스트는 `too many states` 400 fallback의 두 전송이 모두 gate를 지나는지 확인한다. `_HttpError` helper는 headers를 받는다.

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `python -m pytest ai/tests/llm/test_gms.py -v`

Expected: FAIL — 첫 429가 일반 `LlmHttpError`로 끝난다.

- [ ] **Step 3: 실제 전송을 게이트로 감싼다.**

`gms.py`에 환경 기반 `@lru_cache(maxsize=1)` gate factory를 둔다. `send()`의 `opener.open()`을 operation으로 넘긴다. HTTP 429이면 `Retry-After`를 초 또는 `parsedate_to_datetime`로 해석한 내부 rate-limit 신호로 바꾸며, 끝내 실패할 때만 `LlmRateLimitedError(_LABEL, retry_after_seconds)`를 올린다. 400 schema fallback은 `send()`를 다시 부르므로 두 번째 HTTP 요청도 게이트를 지난다.

- [ ] **Step 4: 회귀 테스트를 통과시킨다.**

Run: `python -m pytest ai/tests/llm/test_gms.py ai/tests/llm/test_config.py -v`

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

Run: `git add ai/llm/gms.py ai/llm/__init__.py ai/tests/llm/test_gms.py && git commit -m "feat: gate GMS adapter requests"`

### Task 4: AI API에서 429 계약을 보존한다

**Files:**
- Modify: `ai/company_analysis/llm.py`
- Modify: `ai/company_analysis/api.py`, `ai/news_intelligence/api.py`, `ai/position_coaching/api.py`, `ai/writing_coaching/api.py`, `ai/jd_coaching/api.py`, `ai/supervisor/api.py`
- Modify: 해당 `ai/tests/**/test_api.py`

**Interfaces:**
- Produces: `HTTPException(status_code=429, detail={"code": "GMS_RATE_LIMITED"})`.

- [ ] **Step 1: API 오류 계약 실패 테스트를 작성한다.**

```python
def test_supervisor_rate_limit_returns_sanitized_429(self):
    service = FakeService(error=LlmRateLimitedError("GMS", 10))
    app.dependency_overrides[get_supervisor_service_provider] = lambda: lambda: service
    response = TestClient(app, raise_server_exceptions=False).post("/internal/runs", json=VALID_REQUEST)
    assert response.status_code == 429
    assert response.json()["detail"] == {"code": "GMS_RATE_LIMITED"}
```

각 앱에서 실제 모델 endpoint 한 개씩 같은 응답을 확인하고 worker 내부 제한 초과가 원본 GMS 본문을 노출하지 않는지 확인한다.

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `python -m pytest ai/tests/supervisor/test_api.py ai/tests/news_intelligence/test_api.py ai/tests/position_coaching/test_api.py -v`

Expected: FAIL — 현재는 502 또는 일반 오류다.

- [ ] **Step 3: 예외 경계를 구현한다.**

`GmsStructuredClient.complete()`은 `LlmRateLimitedError`를 `ModelRateLimitedError`로 보존한다. 각 API는 broad `RuntimeError`보다 먼저 제한 초과를 잡아 HTTP 429와 고정 코드만 반환한다. supervisor는 계획·종합의 제한 초과도 429로 바꾸며 이미 성공한 worker 결과는 기존 fallback으로 보존한다.

- [ ] **Step 4: Python 회귀 테스트를 통과시킨다.**

Run: `python -m pytest ai/tests/llm ai/tests/supervisor ai/tests/news_intelligence ai/tests/position_coaching ai/tests/company_analysis -v`

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

Run: `git add ai/company_analysis/llm.py ai/company_analysis/api.py ai/news_intelligence/api.py ai/position_coaching/api.py ai/writing_coaching/api.py ai/jd_coaching/api.py ai/supervisor/api.py ai/tests && git commit -m "feat: expose GMS rate limits from AI services"`

### Task 5: Spring 오류 변환과 검토방 안내

**Files:**
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/global/error/ErrorCode.java`
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/AgentAiCall.java`
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/AgentLlmClient.java`
- Create: `backend/src/test/java/com/ssafy/companyanalysis/agent/ai/AgentAiCallTest.java`
- Modify: `backend/src/test/java/com/ssafy/companyanalysis/agent/service/SupervisorTurnRunnerTest.java`

**Interfaces:**
- Produces: `ErrorCode.AI_RATE_LIMITED` (HTTP 429)와 `"AI 요청이 몰려 답변을 준비하지 못했습니다. 잠시 후 다시 시도해 주세요."` 안내.

- [ ] **Step 1: Spring 매핑 실패 테스트를 작성한다.**

```java
@Test
void translatesAiServer429ToRateLimited() {
    var response = new HttpClientErrorException.TooManyRequests("limited", HttpHeaders.EMPTY, new byte[0], StandardCharsets.UTF_8);
    BusinessException error = AgentAiCall.translate(response, "총괄");
    assertThat(error.getErrorCode()).isEqualTo(ErrorCode.AI_RATE_LIMITED);
}
```

`SupervisorTurnRunnerTest`에는 `supervisorClient.run()`이 `BusinessException(AI_RATE_LIMITED, ErrorCode.AI_RATE_LIMITED.getDefaultMessage())`를 던질 때 모든 slot이 FAILED이고 고정 안내를 가진 케이스를 추가한다.

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `./gradlew test --tests "*AgentAiCallTest" --tests "*SupervisorTurnRunnerTest"`

Expected: FAIL — 429가 `AI_FAILED`로 변환되거나 코드가 없다.

- [ ] **Step 3: 최소 오류 변환을 구현한다.**

`ErrorCode`에 `AI_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "AI 요청이 몰려 답변을 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.")`를 추가한다. `AgentAiCall.translate`를 package-private로 두고 429 분기를 추가한다. `AgentLlmClient.generate`는 `RestClientResponseException`을 `RestClientException`보다 먼저 잡아 직접 GMS 429도 같은 코드로 바꾼다. 나머지 502/503/422 분기는 유지한다.

- [ ] **Step 4: Spring 테스트를 통과시킨다.**

Run: `./gradlew test --tests "*AgentAiCallTest" --tests "*SupervisorTurnRunnerTest"`

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

Run: `git add backend/src/main/java/com/ssafy/companyanalysis/global/error/ErrorCode.java backend/src/main/java/com/ssafy/companyanalysis/agent/ai/AgentAiCall.java backend/src/main/java/com/ssafy/companyanalysis/agent/ai/AgentLlmClient.java backend/src/test/java/com/ssafy/companyanalysis/agent/ai/AgentAiCallTest.java backend/src/test/java/com/ssafy/companyanalysis/agent/service/SupervisorTurnRunnerTest.java && git commit -m "feat: show GMS rate limits in agent rooms"`

### Task 6: 운영 설정과 최종 검증

**Files:**
- Modify: `ai/.env.example`
- Modify: `infra/docker-compose.yml`
- Modify: `infra/.env.prod.example`
- Modify: `ai/tests/llm/test_gms_gate.py`

**Interfaces:**
- Consumes: `GmsGateSettings.from_env`의 여섯 변수.
- Produces: 모든 환경에서 같은 기본값을 AI 컨테이너에 전달한다.

- [ ] **Step 1: 설정 검증 실패 테스트를 작성한다.**

```python
def test_rejects_invalid_queue_timeout_from_environment():
    with pytest.raisesRegex(ValueError, "GMS_QUEUE_TIMEOUT_SECONDS"):
        GmsGateSettings.from_env({"GMS_QUEUE_TIMEOUT_SECONDS": "0"})
```

- [ ] **Step 2: 테스트가 실패함을 확인한다.**

Run: `python -m pytest ai/tests/llm/test_gms_gate.py::test_rejects_invalid_queue_timeout_from_environment -v`

Expected: FAIL until settings validation is wired into the gate factory.

- [ ] **Step 3: 환경 예시와 Compose 전달을 추가한다.**

`ai/.env.example`과 `infra/.env.prod.example`에 여섯 변수의 주석·기본값을 적고, `infra/docker-compose.yml`의 `ai.environment`에 `${GMS_*:-기본값}`으로 모두 전달한다. `GMS_MAX_QUEUED_REQUESTS`는 실행 중인 요청을 제외한 대기열 상한이다. AI 앱 시작의 singleton gate factory가 설정을 읽으므로 잘못된 값은 readiness 전에 실패한다.

- [ ] **Step 4: 전체 검증을 실행한다.**

Run: `python -m pytest ai/tests/llm ai/tests/supervisor ai/tests/news_intelligence ai/tests/position_coaching ai/tests/company_analysis -v`

Expected: PASS.

Run: `./gradlew test --tests "*AgentAiCallTest" --tests "*SupervisorTurnRunnerTest" --tests "*JobPostingParseServiceTest"`

Expected: PASS.

Run: `docker compose --env-file infra/.env.prod.example -f infra/docker-compose.yml config`

Expected: Compose configuration renders; deployment-specific secrets remain supplied by its normal environment.

- [ ] **Step 5: 커밋한다.**

Run: `git add ai/.env.example infra/docker-compose.yml infra/.env.prod.example ai/tests/llm/test_gms_gate.py && git commit -m "docs: configure GMS request gate"`

## Self-Review

- Spec coverage: Tasks 1–3 cover FIFO, concurrency, spacing, 429 cooling, Retry-After, one retry, queue timeout, and schema fallback gating. Task 4 preserves the Python API contract. Task 5 carries it to Spring and the existing failed-slot UI. Task 6 covers configuration and regressions. Redis, replica coordination, and durable recovery remain out of scope.
- Placeholder scan: 미완성 표시, 모호한 오류 처리, 미룬 구현 단계가 없다.
- Type consistency: `GmsRequestGate.run`, `GmsGateSettings`, `LlmRateLimitedError`, and `ErrorCode.AI_RATE_LIMITED` are defined before later tasks use them.
