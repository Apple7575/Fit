# Position Prompt Agent Implementation Plan

> 범위 변경: Spring 연동 작업(Task 3~4)과 Compose 연결은 취소했다. 현재 브랜치에는 FastAPI
> 포지션 분석과 해당 AI 테스트만 남기며, Spring 관련 단계는 향후 연동 참고용이다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백엔드 지원자의 경험에서 빠진 기술적 연결고리를 찾고 대화형 후속 질문을 만드는 Qwen 기반 포지션 에이전트를 기존 멀티에이전트 방에 연결한다.

**Architecture:** Spring은 공개 방·메시지·턴 API와 대화 저장을 유지한다. `/position`에 마운트된 FastAPI가 백엔드 프로필로 프롬프트를 만들고 Qwen 구조화 출력을 기존 계약으로 검증하며, Spring의 position 실행만 이 내부 API로 분기한다.

**Tech Stack:** Python 3, FastAPI, Pydantic, Qwen OpenAI-compatible API, Java 21, Spring Boot 4, RestClient, JUnit 5, Mockito

**Spec:** `docs/superpowers/specs/2026-09-15-position-prompt-agent-design.md`

## Global Constraints

- 1차 지원 프로필은 정확히 `backend-v1` 하나다.
- JD, 기업 자료, 뉴스, 모델의 일반 지식을 사용자 경험의 사실 근거로 사용하지 않는다.
- 모든 인용문과 offset은 `SELF_INTRO` 또는 `EXPERIENCE` 문서와 정확히 일치해야 한다.
- finding당 후속 질문은 최대 2개다.
- 모델 자유서술을 사용자 메시지로 저장하지 않는다.
- LoRA, RAG, 프론트엔드 변경, 스트리밍은 포함하지 않는다.

---

### Task 1: 포지션 프롬프트와 서비스

**Files:**
- Create: `ai/position_coaching/prompt.py`
- Create: `ai/position_coaching/service.py`
- Create: `ai/tests/position_coaching/test_prompt.py`
- Create: `ai/tests/position_coaching/test_service.py`

**Interfaces:**
- Consumes: `load_position_profile`, `validate_analysis_output`, `call_qwen`
- Produces: `build_position_messages(profile, documents, conversation) -> list[dict[str, str]]`, `PositionAnalysisService.analyze(...) -> dict[str, Any]`

- [ ] **Step 1: 프롬프트가 직무 깊이와 근거 제한을 포함하는 실패 테스트를 작성한다**

```python
messages = build_position_messages(PROFILE, DOCUMENTS, [])
self.assertIn("빠진 연결고리", messages[0]["content"])
self.assertIn("JD를 근거로 사용하지 않는다", messages[0]["content"])
self.assertIn("최대 2개", messages[0]["content"])
```

- [ ] **Step 2: 서비스가 Qwen 결과를 검증하고 한 번만 재시도하는 실패 테스트를 작성한다**

```python
service = PositionAnalysisService(config=CONFIG, qwen_caller=fake_invalid_then_valid)
result = service.analyze("backend-v1", DOCUMENTS, [])
self.assertEqual(result["analysis_status"], "COMPLETED")
self.assertEqual(fake_invalid_then_valid.call_count, 2)
```

- [ ] **Step 3: 대상 테스트를 실행해 import 실패를 확인한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.position_coaching.test_prompt ai.tests.position_coaching.test_service`

Expected: `ai.position_coaching.prompt` 또는 `service`가 없어서 실패한다.

- [ ] **Step 4: 시스템 메시지와 입력 JSON을 만드는 최소 구현을 작성한다**

```python
def build_position_messages(profile, documents, conversation):
    system = """너는 직무 경험의 빠진 연결고리를 찾는 포지션 담당이다.
JD, 기업, 뉴스 또는 일반 지식을 사용자 경험의 사실 근거로 사용하지 않는다.
원문에 없는 기술·역할·수치·성과를 만들지 않는다.
각 finding의 질문은 missing_elements를 확인하는 질문으로 최대 2개다.
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({
            "position_profile": profile,
            "documents": documents,
            "conversation": conversation,
        }, ensure_ascii=False)},
    ]
```

- [ ] **Step 5: 서비스에서 프로필 로딩, Qwen 호출, 계약 검증 및 1회 재시도를 구현한다**

```python
PROFILE_PATH = Path(__file__).parent / "resources" / "profiles" / "backend-v1.json"
SCHEMA_PATH = Path(__file__).parent / "resources" / "schemas" / "position-analysis-v1.json"

class PositionAnalysisService:
    def __init__(self, config, qwen_caller=call_qwen):
        self._config = config
        self._qwen_caller = qwen_caller

    def analyze(self, position_profile_id, documents, conversation):
        if position_profile_id != "backend-v1":
            raise ValueError("unsupported position_profile_id")
        profile = load_position_profile(PROFILE_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        messages = build_position_messages(profile, documents, conversation)
        for attempt in range(2):
            response = self._qwen_caller(
                self._config, messages,
                schema=schema,
                schema_name="position_analysis_v1",
            )
            try:
                return validate_analysis_output(response["output"], documents, profile)
            except ValueError as error:
                if attempt == 1:
                    raise RuntimeError("position analysis validation failed") from error
                messages.append({"role": "user", "content": f"검증 오류를 수정하라: {error}"})
```

- [ ] **Step 6: 대상 테스트를 다시 실행한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.position_coaching.test_prompt ai.tests.position_coaching.test_service`

Expected: 모든 테스트가 `OK`다.

- [ ] **Step 7: 변경을 커밋한다**

```bash
git add ai/position_coaching/prompt.py ai/position_coaching/service.py ai/tests/position_coaching/test_prompt.py ai/tests/position_coaching/test_service.py
git commit -m "feat: add position depth prompt service"
```

### Task 2: 사용자 메시지 렌더러와 FastAPI

**Files:**
- Create: `ai/position_coaching/render.py`
- Create: `ai/position_coaching/api.py`
- Create: `ai/tests/position_coaching/test_render.py`
- Create: `ai/tests/position_coaching/test_api.py`
- Modify: `ai/serve.py`

**Interfaces:**
- Consumes: `PositionAnalysisService.analyze`
- Produces: `render_position_message(analysis) -> str`, `POST /position/internal/analyses`

- [ ] **Step 1: 렌더러가 검증된 reason과 질문만 사용하는 실패 테스트를 작성한다**

```python
message = render_position_message(analysis)
self.assertIn("검증 방법이 빠져 있습니다.", message)
self.assertIn("어떻게 검증했나요?", message)
self.assertNotIn("Redis를 사용하세요", message)
```

- [ ] **Step 2: API 성공, 422, 502 테스트를 작성한다**

```python
response = client.post("/internal/analyses", json=VALID_REQUEST)
self.assertEqual(response.status_code, 200)
self.assertEqual(response.json()["analysis"]["position_profile"]["id"], "backend-v1")
self.assertTrue(response.json()["message"])
```

- [ ] **Step 3: 대상 테스트가 실패하는지 확인한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.position_coaching.test_render ai.tests.position_coaching.test_api`

Expected: 렌더러와 API 모듈이 없어서 실패한다.

- [ ] **Step 4: 결정적 메시지 렌더러를 구현한다**

```python
def render_position_message(analysis):
    if analysis["analysis_status"] == "NO_TECHNICAL_CLAIM":
        return "구체화할 기술 경험을 찾지 못했습니다. 맡은 문제와 직접 수행한 행동을 알려 주세요."
    blocks = []
    for finding in analysis["findings"]:
        block = finding["reason"]
        if finding["follow_up_questions"]:
            block += "\n" + "\n".join(finding["follow_up_questions"][:2])
        blocks.append(block)
    return "\n\n".join(blocks)
```

- [ ] **Step 5: Pydantic 요청 모델과 분석 엔드포인트를 구현한다**

```python
@app.post("/internal/analyses")
def create_analysis(request: PositionAnalysisRequest, service=Depends(get_service)):
    try:
        analysis = service.analyze(
            request.position_profile_id,
            [document.model_dump() for document in request.documents],
            [message.model_dump() for message in request.conversation],
        )
        return {"message": render_position_message(analysis), "analysis": analysis}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
```

- [ ] **Step 6: `ai/serve.py`에 `/position` 앱과 lifespan을 추가한다**

```python
from ai.position_coaching.api import app as position_app

root.mount("/jd", jd_app)
root.mount("/position", position_app)
```

- [ ] **Step 7: 대상 테스트와 전체 AI 테스트를 실행한다**

Run: `.\.venv\Scripts\python.exe -m unittest ai.tests.position_coaching.test_render ai.tests.position_coaching.test_api`

Run: `.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -p "test_*.py"`

Expected: 두 명령 모두 `OK`다.

- [ ] **Step 8: 변경을 커밋한다**

```bash
git add ai/position_coaching/render.py ai/position_coaching/api.py ai/serve.py ai/tests/position_coaching/test_render.py ai/tests/position_coaching/test_api.py
git commit -m "feat: expose position analysis internal API"
```

### Task 3: Spring 포지션 AI 클라이언트

**Files:**
- Create: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAiProperties.java`
- Create: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisClient.java`
- Create: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionHistoryMessage.java`
- Create: `backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisResult.java`
- Create: `backend/src/test/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisClientTest.java`
- Modify: `backend/src/main/resources/application.properties`
- Modify: `backend/src/test/resources/application.properties`

**Interfaces:**
- Consumes: `POST /position/internal/analyses`
- Produces: `PositionAnalysisClient.analyze(String profileId, String coverLetter, List<PositionHistoryMessage>) -> PositionAnalysisResult`

- [ ] **Step 1: WireMock 없이 `MockRestServiceServer`로 경로와 응답 매핑 실패 테스트를 작성한다**

```java
server.expect(requestTo("http://ai.test/position/internal/analyses"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(withSuccess("{\"message\":\"질문\",\"analysis\":{}}", MediaType.APPLICATION_JSON));
assertThat(client.analyze("backend-v1", "자소서", List.of()).message()).isEqualTo("질문");
```

- [ ] **Step 2: 대상 테스트를 실행해 컴파일 실패를 확인한다**

Run: `cd backend; .\gradlew.bat test --tests '*PositionAnalysisClientTest' --console=plain`

Expected: 새 클래스가 없어 컴파일에 실패한다.

- [ ] **Step 3: 프로퍼티와 클라이언트를 구현한다**

```java
@ConfigurationProperties(prefix = "app.ai.position")
public record PositionAiProperties(String baseUrl, Duration timeout) {
    public PositionAiProperties {
        baseUrl = baseUrl == null ? "" : baseUrl.replaceAll("/+$", "");
        timeout = timeout == null ? Duration.ofSeconds(60) : timeout;
    }
}
```

```java
public record PositionHistoryMessage(Long messageId, String role, String agentKey, String content) {}
public record PositionAnalysisResult(String message, Map<String, Object> analysis) {}

public PositionAnalysisResult analyze(String profileId,
                                      String coverLetter,
                                      List<PositionHistoryMessage> history) {
    Map<String, Object> body = requestBody(profileId, coverLetter, history);
    try {
        return restClient.post()
                .uri("/position/internal/analyses")
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(PositionAnalysisResult.class);
    } catch (RestClientException error) {
        throw new BusinessException(ErrorCode.AI_FEEDBACK_FAILED);
    }
}
```

`requestBody`는 자소서를 `SELF_INTRO` 문서로, USER history를 `EXPERIENCE` 문서로 만들고
position assistant history는 `conversation`에만 넣는다.

- [ ] **Step 4: 환경 설정을 추가한다**

```properties
app.ai.position.base-url=${AI_SERVICE_BASE_URL:http://localhost:8000}
app.ai.position.timeout=60s
```

테스트 설정에는 `app.ai.position.base-url=http://localhost:8000`을 명시한다.

- [ ] **Step 5: 대상 테스트를 실행한다**

Run: `cd backend; .\gradlew.bat test --tests '*PositionAnalysisClientTest' --console=plain`

Expected: 테스트가 통과한다.

- [ ] **Step 6: 변경을 커밋한다**

```bash
git add backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAiProperties.java backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisClient.java backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionHistoryMessage.java backend/src/main/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisResult.java backend/src/test/java/com/ssafy/companyanalysis/agent/ai/PositionAnalysisClientTest.java backend/src/main/resources/application.properties backend/src/test/resources/application.properties
git commit -m "feat: add position analysis AI client"
```

### Task 4: 포지션 턴에 대화 이력 연결

**Files:**
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/repository/MessageRepository.java`
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/service/TurnContext.java`
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/service/TurnService.java`
- Modify: `backend/src/main/java/com/ssafy/companyanalysis/agent/service/AgentTaskRunner.java`
- Modify: `backend/src/test/java/com/ssafy/companyanalysis/agent/service/TurnServiceTest.java`
- Modify: `backend/src/test/java/com/ssafy/companyanalysis/agent/service/AgentTaskRunnerTest.java`

**Interfaces:**
- Consumes: `PositionAnalysisClient`과 현재 방의 완료 메시지
- Produces: 포지션 첫 턴 및 후속 턴의 검증된 사용자 메시지

- [ ] **Step 1: TurnService가 최근 완료 대화를 시간순으로 TurnContext에 넣는 실패 테스트를 작성한다**

```java
verify(turnExecutor).runTurn(eq(userMessageId), argThat(context ->
        context.history().stream().anyMatch(message -> message.content().equals("이전 답변"))));
```

- [ ] **Step 2: AgentTaskRunner가 POSITION만 PositionAnalysisClient를 사용하는 실패 테스트를 작성한다**

```java
runner.run(positionMessageId, context);
verify(positionClient).analyze(eq("backend-v1"), eq(context.coverLetterText()), anyList());
verifyNoInteractions(llmClient);
```

- [ ] **Step 3: 대상 테스트를 실행해 실패를 확인한다**

Run: `cd backend; .\gradlew.bat test --tests '*TurnServiceTest' --tests '*AgentTaskRunnerTest' --console=plain`

Expected: `history`와 position client 분기가 없어 실패한다.

- [ ] **Step 4: 저장소에 최근 완료 메시지 조회를 추가한다**

```java
List<Message> findTop20ByRoomIdAndStatusOrderByIdDesc(Long roomId, MessageStatus status);
```

`TurnService`는 결과를 역순으로 뒤집어 시간순 history를 만든다. USER 메시지와
`agentKey=position`인 AGENT 메시지만 포지션 클라이언트 요청에 포함하며, 현재 PENDING 슬롯은
제외한다.

- [ ] **Step 5: TurnContext에 불변 HistoryMessage 목록을 추가한다**

```java
public record TurnContext(String coverLetterText,
                          String userMessage,
                          Map<String, Map<String, Object>> agentConfigs,
                          List<PositionHistoryMessage> history) { }
```

- [ ] **Step 6: AgentTaskRunner에 포지션 전용 분기를 구현한다**

```java
if (type == AgentType.POSITION) {
    String profileId = "backend".equals(String.valueOf(context.configOf(type).get("jobRole")))
            ? "backend-v1"
            : String.valueOf(context.configOf(type).get("jobRole")) + "-v1";
    PositionAnalysisResult result = positionClient.analyze(profileId, context.coverLetterText(), context.history());
    message.succeed(result.message(), List.of(), List.of());
    return;
}
```

- [ ] **Step 7: 대상 테스트와 agent 패키지 테스트를 실행한다**

Run: `cd backend; .\gradlew.bat test --tests '*TurnServiceTest' --tests '*AgentTaskRunnerTest' --console=plain`

Run: `cd backend; .\gradlew.bat test --tests 'com.ssafy.companyanalysis.agent.*' --console=plain`

Expected: 모두 통과하고 POSITION만 FastAPI를 사용한다.

- [ ] **Step 8: 변경을 커밋한다**

```bash
git add backend/src/main/java/com/ssafy/companyanalysis/agent backend/src/test/java/com/ssafy/companyanalysis/agent
git commit -m "feat: connect position agent to conversation history"
```

### Task 5: 전체 검증

**Files:**
- Test: `ai/tests`
- Test: `backend/src/test`

**Interfaces:**
- Consumes: Tasks 1-4의 전체 포지션 흐름
- Produces: 병합 가능한 검증 결과

- [ ] **Step 1: 평가셋 구조를 검증한다**

Run:

```powershell
$positionCaseArgs = Get-ChildItem ai/evals/position_coaching/cases/canonical-v1/*.json |
    ForEach-Object { "--case"; $_.FullName }
& .\.venv\Scripts\python.exe -m ai.scripts.validate_position_eval_set `
    --policy ai/evals/position_coaching/evaluation-policy-v1.json `
    @positionCaseArgs `
    --report outputs/position-lora/prompt-v1-validation.json
```

Expected: 60개 DRAFT 케이스가 구조 오류 없이 검증된다.

- [ ] **Step 2: 전체 AI 테스트를 실행한다**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -p "test_*.py"`

Expected: 전체 테스트가 `OK`다.

- [ ] **Step 3: 전체 백엔드 테스트를 실행한다**

Run: `cd backend; .\gradlew.bat test --console=plain`

Expected: 전체 테스트가 성공한다.

- [ ] **Step 4: 변경 범위와 공백 오류를 확인한다**

Run: `git status --short`

Expected: 사용자 소유 untracked 데이터만 남고 계획 밖 추적 파일은 없다.

Run: `git diff --check origin/develop..HEAD`

Expected: 출력이 없다.
