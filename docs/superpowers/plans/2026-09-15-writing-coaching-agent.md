# Writing Coaching Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 자기소개서 문항을 사실에 맞게 대화형으로 첨삭하고, JD·Position 피드백을 받아 총괄 에이전트의 후행 worker로 실행되는 Python 글쓰기 에이전트를 구축한다.

**Architecture:** `ai/writing_coaching`은 무상태 FastAPI와 재사용 가능한 `WritingService`를 제공한다. Qwen은 한 번의 구조화 호출로 대화 상태와 수정안을 만들고 서버 검증 실패 시 한 번만 재시도한다. 총괄 그래프는 JD·Position을 먼저 병렬 실행한 뒤 성공 결과를 결정적으로 정규화해 Writing에 전달한다.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, LangGraph 1.2.x, 기존 Qwen OpenAI-compatible JSON Schema 호출기, `unittest`

**Spec:** `docs/superpowers/specs/2026-09-15-writing-coaching-agent-design.md`

## Global Constraints

- Spring `backend/`, 프런트엔드와 DB 스키마는 수정하지 않는다.
- 문항 선택은 호출자 책임이며 Writing은 문항 한 개와 기준 초안 한 개만 처리한다.
- 초안 없는 신규 작성, 여러 문항 동시 첨삭과 합격 가능성 점수는 구현하지 않는다.
- 사실 근거는 현재 `draft`, 현재 `message`, 과거 `USER` 메시지뿐이다.
- 과거 `ASSISTANT` 메시지와 worker `feedback`은 사실 근거로 사용하지 않는다.
- 첨삭 유형은 `STRUCTURE`, `CLARITY`, `CONCISENESS`, `FLOW`, `TONE`, `LENGTH`만 허용한다.
- 첨삭 강도는 `LIGHT`, `BALANCED`, `REWRITE`이며 불명확하면 `BALANCED`다.
- 대화 상태는 `REVISED`, `ANSWERED`, `CLARIFICATION_REQUIRED`만 허용한다.
- 기본 Qwen 호출 timeout은 호출당 30초이고 검증 오류에 대해서만 한 번 재시도한다.
- 원문, 대화와 수정문을 로그에 기록하지 않는다.
- URL에는 버전을 넣지 않고 통합 경로 `POST /writing/internal/messages`를 사용한다.

---

## File Map

### 새 파일

- `ai/writing_coaching/__init__.py`: 패키지 표시
- `ai/writing_coaching/contracts.py`: 요청·응답 Pydantic 모델과 상태별 교차 검증
- `ai/writing_coaching/prompt.py`: 시스템 규칙과 신뢰 영역이 분리된 Qwen 메시지 생성
- `ai/writing_coaching/validation.py`: 모델 출력, 문자열 위치, feedback 참조와 숫자 사실 검증
- `ai/writing_coaching/service.py`: Qwen 호출, 한 번 재시도와 서버 계산 필드 조립
- `ai/writing_coaching/api.py`: `/internal/messages`, `/health`, `/ready`
- `ai/writing_coaching/evaluation.py`: 고정 평가 사례 로딩과 범위 검증
- `ai/writing_coaching/resources/schemas/writing-message-v1.json`: Qwen 구조화 출력 스키마
- `ai/writing_coaching/resources/rubrics/writing-quality-v1.json`: 여덟 품질 관점과 여섯 변경 유형
- `ai/supervisor/feedback.py`: 분석 결과를 Writing feedback으로 정규화
- `ai/tests/writing_coaching/__init__.py`: 테스트 패키지 표시
- `ai/tests/writing_coaching/test_contracts.py`: 요청·응답 계약 테스트
- `ai/tests/writing_coaching/test_prompt.py`: 사실 근거·대화 직렬화 테스트
- `ai/tests/writing_coaching/test_validation.py`: 결정적 검증 테스트
- `ai/tests/writing_coaching/test_service.py`: Qwen 호출·재시도 테스트
- `ai/tests/writing_coaching/test_api.py`: HTTP 계약과 설정 오류 테스트
- `ai/tests/supervisor/test_feedback.py`: JD·Position 결과의 Writing feedback 변환 테스트
- `docs/api/writing-agent-api.md`: 호출자용 API와 총괄 연동 문서

### 수정 파일

- `ai/serve.py`: Writing FastAPI를 `/writing`에 마운트
- `ai/tests/test_serve.py`: Writing mount 검증
- `ai/supervisor/contracts.py`: Writing context와 `writing` agent enum 추가
- `ai/supervisor/model.py`: 계획 스키마·프롬프트에 Writing 선택 규칙 추가
- `ai/supervisor/adapters.py`: provider 기반 어댑터와 `WritingAgentAdapter` 추가
- `ai/supervisor/graph.py`: 분석 병렬 단계 뒤 Writing 순차 실행
- `ai/supervisor/api.py`: Writing 서비스 조립과 worker별 지연 의존성 해석
- `ai/supervisor/service.py`: 기존 실행 상태와 Writing 대화 상태의 분리 유지
- `ai/tests/supervisor/test_contracts.py`: Writing context 계약
- `ai/tests/supervisor/test_model.py`: 계획 스키마와 선택 규칙
- `ai/tests/supervisor/test_adapters.py`: Writing 입력 변환과 지연 provider
- `ai/tests/supervisor/test_graph.py`: 분석→Writing 순차 실행과 부분 실패
- `ai/tests/supervisor/test_api.py`: Writing-only 설정 격리와 통합 응답

---

### Task 1: Writing 계약과 버전 리소스

**Files:**
- Create: `ai/writing_coaching/__init__.py`
- Create: `ai/writing_coaching/contracts.py`
- Create: `ai/writing_coaching/resources/schemas/writing-message-v1.json`
- Create: `ai/writing_coaching/resources/rubrics/writing-quality-v1.json`
- Create: `ai/tests/writing_coaching/__init__.py`
- Create: `ai/tests/writing_coaching/test_contracts.py`

**Interfaces:**
- Produces: `WritingMessageRequest`, `WritingMessageResponse`, `WritingRevision`, `WritingFeedback`, `WritingConversationMessage`
- Produces: `load_writing_rubric(path: Path) -> dict[str, Any]`
- Consumed later by: prompt, validation, service, API and supervisor adapter

- [ ] **Step 1: Write failing request and response contract tests**

Create `ai/tests/writing_coaching/test_contracts.py` with reusable valid payloads and these concrete assertions:

```python
import unittest
from pydantic import ValidationError

from ai.writing_coaching.contracts import (
    WritingMessageRequest,
    WritingMessageResponse,
)


VALID_REQUEST = {
    "message": "두괄식으로 고쳐줘",
    "question": "협업 경험을 작성해 주세요.",
    "draft": "팀 프로젝트에서 API 개발을 담당했습니다.",
    "char_limit": 700,
    "feedback": [{
        "feedback_id": "position-f1",
        "source": "position",
        "content": "본인의 판단 근거가 부족합니다.",
    }],
    "conversation": [],
}


class WritingContractTest(unittest.TestCase):
    def test_accepts_valid_message_request(self):
        request = WritingMessageRequest.model_validate(VALID_REQUEST)
        self.assertEqual(request.feedback[0].feedback_id, "position-f1")

    def test_rejects_unknown_fields_and_duplicate_feedback_ids(self):
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate({**VALID_REQUEST, "unknown": True})
        duplicated = {**VALID_REQUEST, "feedback": VALID_REQUEST["feedback"] * 2}
        with self.assertRaises(ValidationError):
            WritingMessageRequest.model_validate(duplicated)

    def test_enforces_status_revision_pair(self):
        with self.assertRaises(ValidationError):
            WritingMessageResponse.model_validate({
                "status": "REVISED", "message": "수정했습니다.", "revision": None,
            })
        answered = WritingMessageResponse.model_validate({
            "status": "ANSWERED", "message": "설명입니다.", "revision": None,
        })
        self.assertEqual(answered.status, "ANSWERED")
```

Also cover blank strings, `char_limit` outside 1–50,000, more than 20 feedback items, invalid feedback source, more than 20 conversation messages, invalid conversation role, unsupported change/warning enums, more than 12 changes and more than 10 warnings.

- [ ] **Step 2: Run the contract tests and confirm import failure**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_contracts -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai.writing_coaching'`.

- [ ] **Step 3: Implement strict Pydantic models and cross-field validation**

Create `contracts.py` with `ConfigDict(extra="forbid", str_strip_whitespace=True)` on every external model. Use the exact public shapes below:

```python
class WritingFeedback(StrictModel):
    feedback_id: str = Field(min_length=1, max_length=100)
    source: Literal["jd", "position", "supervisor"]
    content: str = Field(min_length=1, max_length=2_000)


class WritingConversationMessage(StrictModel):
    message_id: str = Field(min_length=1, max_length=100)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=10_000)


class WritingMessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=10_000)
    question: str = Field(min_length=1, max_length=500)
    draft: str = Field(min_length=1, max_length=50_000)
    char_limit: int = Field(strict=True, ge=1, le=50_000)
    feedback: list[WritingFeedback] = Field(default_factory=list, max_length=20)
    conversation: list[WritingConversationMessage] = Field(
        default_factory=list, max_length=20
    )


class WritingChange(StrictModel):
    type: Literal["STRUCTURE", "CLARITY", "CONCISENESS", "FLOW", "TONE", "LENGTH"]
    before: str = Field(min_length=1, max_length=2_000)
    after: str = Field(min_length=1, max_length=2_000)
    reason: str = Field(min_length=1, max_length=1_000)
    applied_feedback_ids: list[str] = Field(default_factory=list, max_length=20)


class WritingWarning(StrictModel):
    code: Literal[
        "MISSING_EVIDENCE", "UNAPPLIED_FEEDBACK",
        "CHAR_LIMIT_CONFLICT", "AMBIGUOUS_INSTRUCTION",
    ]
    message: str = Field(min_length=1, max_length=1_000)


class WritingRevision(StrictModel):
    revision_strength: Literal["LIGHT", "BALANCED", "REWRITE"]
    revised_text: str = Field(min_length=1, max_length=50_000)
    char_count: int = Field(ge=1, le=50_000)
    changes: list[WritingChange] = Field(default_factory=list, max_length=12)
    warnings: list[WritingWarning] = Field(default_factory=list, max_length=10)


class WritingMessageResponse(StrictModel):
    status: Literal["REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"]
    message: str = Field(min_length=1, max_length=2_000)
    revision: WritingRevision | None

    @model_validator(mode="after")
    def validate_status_payload(self):
        if (self.status == "REVISED") != (self.revision is not None):
            raise ValueError("revision must exist exactly when status is REVISED")
        return self
```

Add validators rejecting blank-after-strip strings and duplicate `feedback_id`, `message_id`, and `applied_feedback_ids` values. `bool` must not pass as `char_limit`; use strict integer validation.

- [ ] **Step 4: Add the exact Qwen schema and rubric resources**

Create `writing-message-v1.json` with top-level required fields `status`, `message`, `revision`; `status` uses the three allowed values and `revision` uses JSON Schema type `["object", "null"]`. The revision object requires `revision_strength`, `revised_text`, `char_count`, `changes`, `warnings`; every object has `additionalProperties: false` and the enum/length/item limits match the Pydantic contract.

Create `writing-quality-v1.json` with:

```json
{
  "id": "writing-quality-v1",
  "version": 1,
  "dimensions": [
    "QUESTION_FIT", "CORE_MESSAGE", "EVIDENCE", "AGENCY",
    "JOB_RELEVANCE", "READABILITY", "CREDIBILITY", "CONSTRAINTS"
  ],
  "change_types": [
    "STRUCTURE", "CLARITY", "CONCISENESS", "FLOW", "TONE", "LENGTH"
  ],
  "default_revision_strength": "BALANCED"
}
```

Implement `load_writing_rubric()` to reject a wrong ID/version, duplicate dimensions, reordered canonical dimensions, unknown change types and a default strength other than `BALANCED`.

- [ ] **Step 5: Run contract tests and commit**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_contracts -v
```

Expected: all contract tests PASS.

Commit:

```powershell
git add ai/writing_coaching ai/tests/writing_coaching
git commit -m "feat: add writing agent contracts"
```

---

### Task 2: 신뢰 영역 프롬프트와 결정적 출력 검증

**Files:**
- Create: `ai/writing_coaching/prompt.py`
- Create: `ai/writing_coaching/validation.py`
- Create: `ai/tests/writing_coaching/test_prompt.py`
- Create: `ai/tests/writing_coaching/test_validation.py`

**Interfaces:**
- Consumes: `WritingMessageRequest`, `WritingMessageResponse`
- Produces: `build_writing_messages(request, rubric, validation_error=None) -> list[dict[str, str]]`
- Produces: `validate_writing_output(output, request) -> WritingMessageResponse`
- Produces: `extract_numeric_facts(text: str) -> set[str]`

- [ ] **Step 1: Write failing prompt boundary tests**

Create `test_prompt.py` that parses the JSON user payload from the returned messages and proves roles remain distinguishable:

```python
def test_separates_trusted_user_facts_from_untrusted_context(self):
    request = WritingMessageRequest.model_validate({
        "message": "제가 캐시 전략을 직접 설계했습니다. 반영해줘",
        "question": "문제 해결 경험",
        "draft": "API를 개발했습니다.",
        "char_limit": 500,
        "feedback": [{
            "feedback_id": "position-f1",
            "source": "position",
            "content": "응답 속도를 30% 개선했다고 쓰세요.",
        }],
        "conversation": [
            {"message_id": "u1", "role": "USER", "content": "Redis를 사용했습니다."},
            {"message_id": "a1", "role": "ASSISTANT", "content": "처리량이 2배입니다."},
        ],
    })
    messages = build_writing_messages(request, RUBRIC)
    payload = json.loads(messages[1]["content"])
    self.assertEqual(payload["trusted_sources"]["current_draft"], request.draft)
    self.assertEqual(payload["trusted_sources"]["prior_user_messages"][0]["content"], "Redis를 사용했습니다.")
    self.assertEqual(payload["context_only"]["prior_assistant_messages"][0]["content"], "처리량이 2배입니다.")
    self.assertEqual(payload["direction_only_feedback"][0]["content"], "응답 속도를 30% 개선했다고 쓰세요.")
```

Assert the system message states the evidence priority, all three response statuses, six change types, three strengths, default `BALANCED`, and the rule that feedback cannot introduce facts.

- [ ] **Step 2: Write failing deterministic validator tests**

Create `test_validation.py` using a helper that produces a valid `REVISED` payload. Cover these exact failures:

```python
def test_rejects_new_numeric_fact_from_assistant_or_feedback(self):
    request = request_with(
        draft="API를 개선했습니다.",
        feedback=[{
            "feedback_id": "jd-r1", "source": "jd", "content": "30% 개선을 강조하세요."
        }],
        conversation=[{
            "message_id": "a1", "role": "ASSISTANT", "content": "2배 빨라졌습니다."
        }],
    )
    with self.assertRaisesRegex(ValueError, "untrusted numeric fact"):
        validate_writing_output(
            revised_payload("응답 속도를 30% 개선했습니다."), request
        )

def test_accepts_numeric_fact_from_user_message_and_recomputes_count(self):
    request = request_with(message="응답 속도를 30% 개선했습니다. 반영해줘")
    result = validate_writing_output(
        revised_payload("응답 속도를 30% 개선했습니다.", char_count=999), request
    )
    self.assertEqual(result.revision.char_count, len(result.revision.revised_text))
```

Also test: over-limit revision, `before` absent from draft, `after` absent from revised text, unknown feedback ID, duplicate applied ID, `ANSWERED`/`CLARIFICATION_REQUIRED` with null revision, and invalid model output schema.
Define `request_with(**overrides) -> WritingMessageRequest` by copying `VALID_REQUEST`, applying overrides and calling `WritingMessageRequest.model_validate`. Define `revised_payload(revised_text="API를 개선했습니다.", char_count=1) -> dict[str, Any]` to return a complete `REVISED` response with one valid `CLARITY` change and empty warnings.

- [ ] **Step 3: Run both test modules and confirm missing functions**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_prompt ai.tests.writing_coaching.test_validation -v
```

Expected: FAIL because `prompt.py` and `validation.py` do not exist.

- [ ] **Step 4: Implement prompt construction without string interpolation of untrusted text**

Build the user message with `json.dumps(payload, ensure_ascii=False)` rather than embedding document text into the system instruction. Use this exact signature:

```python
def build_writing_messages(
    request: WritingMessageRequest,
    rubric: Mapping[str, Any],
    validation_error: str | None = None,
) -> list[dict[str, str]]:
```

Partition conversation with list comprehensions by role. Put `draft`, current `message`, and prior USER messages under `trusted_sources`; put prior ASSISTANT messages under `context_only`; put feedback under `direction_only_feedback`. When `validation_error` is present, add it as a separate data field instructing the model to return the entire corrected JSON.

- [ ] **Step 5: Implement output validation and numeric normalization**

Use a regex that captures Arabic numeric values with decimal/group separators and adjacent `%`, `퍼센트`, `년`, `월`, `일`, `명`, `개`, `배`, `초`, `분`, `시간` units. Normalize commas and whitespace but do not translate number words.

```python
def trusted_fact_texts(request: WritingMessageRequest) -> list[str]:
    return [
        request.draft,
        request.message,
        *[item.content for item in request.conversation if item.role == "USER"],
    ]


def validate_writing_output(
    output: Mapping[str, Any], request: WritingMessageRequest
) -> WritingMessageResponse:
    response = WritingMessageResponse.model_validate(output)
    if response.status != "REVISED":
        return response
    revision = response.revision
    if len(revision.revised_text) > request.char_limit:
        raise ValueError("revised_text exceeds char_limit")
    for change in revision.changes:
        if change.before not in request.draft:
            raise ValueError("change before must occur in draft")
        if change.after not in revision.revised_text:
            raise ValueError("change after must occur in revised_text")
    known_ids = {item.feedback_id for item in request.feedback}
    used_ids = {item for change in revision.changes for item in change.applied_feedback_ids}
    if not used_ids <= known_ids:
        raise ValueError("applied_feedback_ids contains unknown feedback_id")
    trusted_numbers = set().union(*(extract_numeric_facts(text) for text in trusted_fact_texts(request)))
    if extract_numeric_facts(revision.revised_text) - trusted_numbers:
        raise ValueError("revised_text contains untrusted numeric fact")
    revision.char_count = len(revision.revised_text)
    return response
```

- [ ] **Step 6: Run prompt and validator tests and commit**

Run the two modules from Step 3. Expected: all tests PASS.

Commit:

```powershell
git add ai/writing_coaching/prompt.py ai/writing_coaching/validation.py ai/tests/writing_coaching/test_prompt.py ai/tests/writing_coaching/test_validation.py
git commit -m "feat: validate grounded writing revisions"
```

---

### Task 3: Qwen 기반 WritingService

**Files:**
- Create: `ai/writing_coaching/service.py`
- Create: `ai/tests/writing_coaching/test_service.py`

**Interfaces:**
- Consumes: `call_qwen`, writing schema/rubric, prompt and validator
- Produces: `WritingService.respond(request: WritingMessageRequest) -> WritingMessageResponse`

- [ ] **Step 1: Write failing service tests with a fake Qwen caller**

Use a caller that records `messages`, `timeout_seconds`, `schema`, and `schema_name`. Add tests proving:

```python
def test_returns_validated_revision_with_server_char_count(self):
    caller = FakeQwenCaller([valid_revised_output(char_count=999)])
    result = WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)
    self.assertEqual(result.status, "REVISED")
    self.assertEqual(result.revision.char_count, len(result.revision.revised_text))
    self.assertEqual(caller.calls[0]["timeout_seconds"], 30)
    self.assertEqual(caller.calls[0]["schema_name"], "writing_message_v1")

def test_retries_one_validation_failure_with_error_context(self):
    caller = FakeQwenCaller([
        valid_revised_output(revised_text="원문에 없는 90% 성과"),
        valid_revised_output(revised_text="API를 개선했습니다."),
    ])
    result = WritingService(CONFIG, qwen_caller=caller).respond(REQUEST)
    self.assertEqual(result.status, "REVISED")
    self.assertEqual(len(caller.calls), 2)
    retry_payload = json.loads(caller.calls[1]["messages"][1]["content"])
    self.assertIn("previous_validation_error", retry_payload)
```

Also assert `ANSWERED` and `CLARIFICATION_REQUIRED` pass without a revision, a second invalid output raises `RuntimeError("writing response validation failed")`, and an operational `RuntimeError("Qwen unavailable")` is not retried.

- [ ] **Step 2: Run the service tests and verify missing service failure**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_service -v
```

Expected: FAIL with missing `ai.writing_coaching.service`.

- [ ] **Step 3: Implement the minimal service with validation-only retry**

```python
RESOURCE_ROOT = Path(__file__).parent / "resources"
RUBRIC_PATH = RESOURCE_ROOT / "rubrics" / "writing-quality-v1.json"
SCHEMA_PATH = RESOURCE_ROOT / "schemas" / "writing-message-v1.json"
PROMPT_VERSION = "writing-quality-v1"
QWEN_TIMEOUT_SECONDS = 30


class WritingService:
    def __init__(self, config: Mapping[str, str], qwen_caller=call_qwen) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller

    def respond(self, request: WritingMessageRequest) -> WritingMessageResponse:
        rubric = load_writing_rubric(RUBRIC_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validation_error = None
        for attempt in range(2):
            messages = build_writing_messages(request, rubric, validation_error)
            response = self._qwen_caller(
                self._config,
                messages,
                timeout_seconds=QWEN_TIMEOUT_SECONDS,
                schema=schema,
                schema_name="writing_message_v1",
            )
            try:
                return validate_writing_output(response["output"], request)
            except (KeyError, TypeError, ValueError) as error:
                validation_error = str(error)
                if attempt == 1:
                    raise RuntimeError("writing response validation failed") from error
        raise RuntimeError("writing response validation failed")
```

Do not catch errors raised by `_qwen_caller`; network/configuration errors must propagate without a second model call.

- [ ] **Step 4: Run service and all Writing unit tests and commit**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests/writing_coaching -t . -v
```

Expected: all Writing tests PASS.

Commit:

```powershell
git add ai/writing_coaching/service.py ai/tests/writing_coaching/test_service.py
git commit -m "feat: add writing response service"
```

---

### Task 4: 독립 Writing FastAPI와 통합 마운트

**Files:**
- Create: `ai/writing_coaching/api.py`
- Create: `ai/tests/writing_coaching/test_api.py`
- Modify: `ai/serve.py`
- Modify: `ai/tests/test_serve.py`

**Interfaces:**
- Produces: `GET /health`, `GET /ready`, `POST /internal/messages`
- Produces: integrated routes `/writing/health`, `/writing/ready`, `/writing/internal/messages`
- Consumes later by: deployment and Spring integration outside this branch

- [ ] **Step 1: Write failing HTTP contract tests**

Create a fake service with `respond(request)` and dependency override. Assert:

```python
def test_creates_writing_message(self):
    response = self.client.post("/internal/messages", json=VALID_REQUEST)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["status"], "REVISED")
    self.assertEqual(self.service.calls[0].question, VALID_REQUEST["question"])

def test_maps_domain_validation_and_model_failures(self):
    self.service.error = ValueError("invalid writing request")
    self.assertEqual(
        self.client.post("/internal/messages", json=VALID_REQUEST).status_code, 422
    )
    self.service.error = RuntimeError("Qwen unavailable")
    self.assertEqual(
        self.client.post("/internal/messages", json=VALID_REQUEST).status_code, 502
    )
```

Add tests for `/health`, `/ready`, malformed Pydantic input remaining 422, and missing `WRITING_QWEN_ENV_FILE` plus empty common Qwen variables returning 503 for `/ready` and `/internal/messages`.

- [ ] **Step 2: Add a failing `/writing` mount test**

Extend `ai/tests/test_serve.py`:

```python
def test_mounts_writing_service(self):
    client = TestClient(build_app())
    health = client.get("/health")
    writing_health = client.get("/writing/health")
    self.assertEqual(health.json()["services"]["writing"], "/writing")
    self.assertEqual(writing_health.status_code, 200)
```

- [ ] **Step 3: Run API tests and confirm route/import failures**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_api ai.tests.test_serve -v
```

Expected: FAIL because Writing API and mount do not exist.

- [ ] **Step 4: Implement API dependency and error mapping**

Use `WRITING_QWEN_ENV_FILE`, falling back to `ai/.env`, and reuse `load_qwen_config`:

```python
@lru_cache(maxsize=1)
def get_writing_service() -> WritingService:
    env_file = Path(os.environ.get("WRITING_QWEN_ENV_FILE", str(AI_ROOT / ".env")))
    try:
        return WritingService(load_qwen_config(env_file))
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="writing Qwen configuration unavailable",
        ) from error


@app.post("/internal/messages", response_model=WritingMessageResponse)
def create_message(
    request: WritingMessageRequest,
    service: Annotated[WritingService, Depends(get_writing_service)],
) -> WritingMessageResponse:
    try:
        return service.respond(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
```

`/health` must not resolve Qwen config; `/ready` must depend on `get_writing_service`.

- [ ] **Step 5: Mount the app and run focused tests**

Import the Writing app in `ai/serve.py`, mount it at `/writing`, and add it to the root health service map. Run the command from Step 3. Expected: all API and mount tests PASS.

- [ ] **Step 6: Commit the standalone API**

```powershell
git add ai/writing_coaching/api.py ai/tests/writing_coaching/test_api.py ai/serve.py ai/tests/test_serve.py
git commit -m "feat: expose writing conversation API"
```

---

### Task 5: Supervisor Writing 계약, feedback 정규화와 어댑터

**Files:**
- Modify: `ai/supervisor/contracts.py`
- Modify: `ai/supervisor/model.py`
- Modify: `ai/supervisor/adapters.py`
- Create: `ai/supervisor/feedback.py`
- Modify: `ai/tests/supervisor/test_contracts.py`
- Modify: `ai/tests/supervisor/test_model.py`
- Modify: `ai/tests/supervisor/test_adapters.py`
- Modify: `ai/tests/supervisor/test_graph.py`
- Create: `ai/tests/supervisor/test_feedback.py`

**Interfaces:**
- Produces: `WritingAgentContext(question: str, char_limit: int)`
- Produces: planner agent literal `Literal["jd", "position", "writing"]`
- Produces: `normalize_writing_feedback(results: Sequence[AgentResult]) -> list[dict[str, str]]`
- Produces: provider-based `WritingAgentAdapter`

- [ ] **Step 1: Write failing supervisor contract and planner tests**

Add a request with:

```python
"agent_contexts": {
    "writing": {"question": "협업 경험을 작성해 주세요.", "char_limit": 700}
}
```

Assert it validates, blank question and boolean/out-of-range `char_limit` fail, `SupervisorPlan(selected_agents=["writing"], reason="첨삭")` validates, and the model JSON schema enum is exactly `{"jd", "position", "writing"}`. Assert the planning prompt describes Writing-only revision and analysis-before-writing requests.

- [ ] **Step 2: Write failing feedback normalizer tests**

Use real-shaped `AgentResult` fixtures. JD input contains `requirements` with stable requirement IDs, labels and suggested actions; Position input contains `findings` with finding IDs, missing elements, reasons and follow-up questions. Assert:

```python
feedback = normalize_writing_feedback([jd_result, position_result, failed_result])
self.assertEqual([item["source"] for item in feedback], ["jd", "position"])
self.assertEqual(feedback[0]["feedback_id"], "jd-req-1")
self.assertEqual(feedback[1]["feedback_id"], "position-finding-1")
self.assertNotIn("failed", json.dumps(feedback, ensure_ascii=False))
```

Add cases proving successful but malformed result fields are ignored, output is capped at 20 items, each content is capped at 2,000 characters, and input order produces deterministic output.

- [ ] **Step 3: Write failing Writing adapter and lazy provider tests**

Use provider call counters and assert:

```python
adapter = WritingAgentAdapter(lambda: writing_service)
result = adapter.execute(
    "두괄식으로 고쳐줘",
    [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "초안"}],
    [],
    {"question": "협업 경험", "char_limit": 700},
    prior_results=[jd_result],
)
self.assertEqual(result["status"], "REVISED")
self.assertEqual(writing_service.calls[0].feedback[0].source, "jd")
```

Assert zero or two `SELF_INTRO` documents raise a clear `ValueError`, and merely constructing/asking availability of JD, Position and Writing adapters does not invoke any service provider.

- [ ] **Step 4: Run focused tests and confirm failures**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.supervisor.test_contracts ai.tests.supervisor.test_model ai.tests.supervisor.test_feedback ai.tests.supervisor.test_adapters -v
```

Expected: FAIL because the Writing supervisor types, mapper and adapter do not exist.

- [ ] **Step 5: Implement contract and planner additions**

Add:

```python
class WritingAgentContext(StrictModel):
    question: str = Field(min_length=1, max_length=500)
    char_limit: int = Field(strict=True, ge=1, le=50_000)


class AgentContexts(StrictModel):
    jd: JdAgentContext | None = None
    position: PositionAgentContext | None = None
    writing: WritingAgentContext | None = None
```

Update all agent literals and `PLAN_SCHEMA`. Add planner instructions: select Writing for revision/explanation requests; select JD/Position with Writing only when the user explicitly asks those analyses to inform the revision; do not select unavailable agents.

- [ ] **Step 6: Implement deterministic feedback normalization**

Create `ai/supervisor/feedback.py`. It must use allowlisted keys only and never ask another LLM to summarize. Prefix IDs with the source; skip failed agents and malformed collections; cap output with slicing after deterministic traversal.

```python
def normalize_writing_feedback(
    results: Sequence[AgentResult],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for result in results:
        if result.status != "SUCCESS" or not isinstance(result.result, Mapping):
            continue
        if result.agent == "jd":
            items.extend(_jd_feedback(result.result))
        elif result.agent == "position":
            items.extend(_position_feedback(result.result))
    return [
        {**item, "content": item["content"][:2_000]}
        for item in items[:20]
    ]
```

- [ ] **Step 7: Convert adapters to providers and add Writing adapter**

Change each adapter constructor to accept `Callable[[], Any]`; call the provider only inside `execute`. Extend the uniform adapter/registry `execute` signature with `prior_results: Sequence[AgentResult] = ()`. JD and Position ignore prior results. Writing normalizes prior results, validates exactly one `SELF_INTRO`, builds `WritingMessageRequest`, calls `WritingService.respond`, and returns `response.model_dump()`. Update every existing supervisor test adapter double, including `RecordingAdapter` in `test_graph.py`, to accept the new optional argument so the complete pre-existing supervisor suite remains green at the end of Task 5.

- [ ] **Step 8: Run focused tests and commit**

Run the command from Step 4. Expected: all focused tests PASS.

Commit:

```powershell
git add ai/supervisor/contracts.py ai/supervisor/model.py ai/supervisor/adapters.py ai/supervisor/feedback.py ai/tests/supervisor
git commit -m "feat: register writing supervisor worker"
```

---

### Task 6: 분석 후 Writing을 실행하는 LangGraph

**Files:**
- Modify: `ai/supervisor/graph.py`
- Modify: `ai/supervisor/service.py`
- Modify: `ai/tests/supervisor/test_graph.py`
- Modify: `ai/tests/supervisor/test_service.py`

**Interfaces:**
- Consumes: registry `execute(name, instruction, documents, conversation, context, prior_results=())`
- Produces: JD·Position 병렬 barrier 뒤 선택적 Writing 실행
- Preserves: top-level `SUCCESS`/`PARTIAL` execution semantics

- [ ] **Step 1: Replace graph test doubles with prior-result-aware adapters**

Update `RecordingAdapter.execute` to accept `prior_results=()` and record agent names from those results. Do not place Writing on the two-party barrier used by analysis workers.

- [ ] **Step 2: Write failing graph ordering tests**

Add these independent cases:

```python
def test_writing_only_skips_analysis_stage(self):
    result = invoke_graph(
        FakeModel([SupervisorPlan(selected_agents=["writing"], reason="첨삭")]),
        registry_with_recorders(),
        {"writing": {"question": "협업 경험", "char_limit": 700}},
    )
    self.assertEqual(executed_agents, ["writing"])

def test_analysis_finishes_before_writing_and_passes_successes(self):
    result = invoke_graph(
        FakeModel([SupervisorPlan(
            selected_agents=["jd", "position", "writing"], reason="분석 후 첨삭"
        )]),
        registry_with_recorders(),
        all_contexts(),
    )
    self.assertTrue(jd.finished_before_writing)
    self.assertTrue(position.finished_before_writing)
    self.assertEqual(writing.prior_agents, ["jd", "position"])
```

Also test: JD fails but Position success is passed to Writing; both analyses fail but Writing still runs with empty prior successes; Writing failure leaves successful analysis results; and an analysis-only plan preserves parallel execution.
Add a clarification case where Writing returns `{"status": "CLARIFICATION_REQUIRED", "message": "본인이 수행한 행동을 알려주세요.", "revision": None}` and assert `final_message` is exactly that question without invoking `model.aggregate`. This prevents the supervisor from paraphrasing or hiding a required user question.

- [ ] **Step 3: Run graph/service tests and verify ordering failures**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.supervisor.test_graph ai.tests.supervisor.test_service -v
```

Expected: FAIL because the current graph dispatches all selected workers in parallel.

- [ ] **Step 4: Implement explicit analysis and writing phases**

Extend state with `analysis_results` only if needed; retain `agent_results` as the reducer-backed canonical list. Partition selected agents while preserving plan order:

```python
def selected_analysis_agents(state: SupervisorState) -> list[str]:
    return [name for name in state["plan"].selected_agents if name in {"jd", "position"}]


def should_run_writing(state: SupervisorState) -> bool:
    return "writing" in state["plan"].selected_agents
```

Build graph branches so `jd` and `position` use `Send("run_analysis_agent", worker_state)`, where `worker_state` contains the agent name, instruction, documents, conversation and matching context. The shared edge after those sends acts as the fan-in barrier. `run_writing_agent` receives only successful analysis results through `prior_results`; it catches its own exception and appends a normal failed `AgentResult`. If there are no analysis agents, route directly to Writing or aggregation. Do not call Writing when it was not selected.

Keep aggregation ordering based on `plan.selected_agents`, not completion order. Include a valid Writing `CLARIFICATION_REQUIRED` result among successes; it is not an execution failure.
Before ordinary aggregation, find the successful Writing result. If its inner status is `CLARIFICATION_REQUIRED`, return its `message` directly as `final_message`. When Writing is the only successful selected worker, also use its `message` directly; call `model.aggregate` only when analysis results and a non-clarification Writing result must be summarized together or when the plan is analysis-only.

- [ ] **Step 5: Run graph, service and existing supervisor tests**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests/supervisor -t . -v
```

Expected: all supervisor tests PASS, including existing JD/Position parallel and fallback behavior.

- [ ] **Step 6: Commit the staged graph**

```powershell
git add ai/supervisor/graph.py ai/supervisor/service.py ai/tests/supervisor/test_graph.py ai/tests/supervisor/test_service.py
git commit -m "feat: run writing after analysis workers"
```

---

### Task 7: Supervisor 조립의 설정 격리

**Files:**
- Modify: `ai/supervisor/api.py`
- Modify: `ai/tests/supervisor/test_api.py`

**Interfaces:**
- Consumes: `get_analysis_service`, `get_position_service`, `get_writing_service`
- Produces: Writing-only supervisor request that does not resolve JD/Position dependencies
- Preserves: `POST /supervisor/internal/runs` and existing error payloads

- [ ] **Step 1: Write failing API configuration isolation tests**

Patch service providers, not constructed services. Assert:

```python
def test_writing_only_run_does_not_resolve_jd_or_position_services(self):
    jd_provider = Mock(side_effect=AssertionError("JD must remain lazy"))
    position_provider = Mock(side_effect=AssertionError("Position must remain lazy"))
    writing = FakeWritingService()
    service = assemble_supervisor_service(
        supervisor_model=FakeModel([
            SupervisorPlan(selected_agents=["writing"], reason="첨삭 요청")
        ]),
        jd_provider=jd_provider,
        position_provider=position_provider,
        writing_provider=lambda: writing,
    )
    response = service.run(writing_only_request())
    self.assertEqual(response.agent_results[0].agent, "writing")
    jd_provider.assert_not_called()
    position_provider.assert_not_called()
```

Add mounted API cases for empty all-three contexts returning `NO_AVAILABLE_AGENT`, Writing-only HTTP 200, missing Writing config becoming a failed Writing worker/502 when it is the only selected worker, and existing JD/Position request behavior remaining unchanged.

- [ ] **Step 2: Run supervisor API tests and verify eager dependency failure**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.supervisor.test_api -v
```

Expected: FAIL because the current `get_supervisor_service` constructs JD and Position services eagerly and does not register Writing.

- [ ] **Step 3: Introduce an explicit assembly function and lazy providers**

Make assembly separately testable:

```python
def assemble_supervisor_service(
    supervisor_model: SupervisorModel,
    jd_provider: Callable[[], Any],
    position_provider: Callable[[], Any],
    writing_provider: Callable[[], Any],
) -> SupervisorService:
    registry = AgentRegistry([
        JdAgentAdapter(jd_provider),
        PositionAgentAdapter(position_provider),
        WritingAgentAdapter(writing_provider),
    ])
    return SupervisorService(build_supervisor_graph(supervisor_model, registry))
```

`get_supervisor_service()` may load only supervisor model configuration eagerly. Pass the cached service functions themselves as providers; do not call them during registry construction. Update the request precheck to include `agent_contexts.writing`.

- [ ] **Step 4: Run supervisor API and full supervisor tests**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests/supervisor -t . -v
```

Expected: all supervisor tests PASS and Writing-only tests show zero JD/Position provider calls.

- [ ] **Step 5: Commit configuration isolation**

```powershell
git add ai/supervisor/api.py ai/tests/supervisor/test_api.py
git commit -m "refactor: resolve supervisor workers lazily"
```

---

### Task 8: API 문서, 사람 평가 가이드와 전체 회귀 검증

**Files:**
- Create: `docs/api/writing-agent-api.md`
- Create: `ai/evals/writing_coaching/writing-quality-v1-review-guide.md`
- Create: `ai/evals/writing_coaching/canonical-v1-cases.json`
- Create: `ai/writing_coaching/evaluation.py`
- Create: `ai/tests/writing_coaching/test_evaluation.py`
- Modify: `ai/requirements.txt` only if an actually imported new package is required

**Interfaces:**
- Produces: Backend/Frontend/Infra integration contract
- Produces: fixed human-review fixtures without automated hiring scores

- [ ] **Step 1: Write a failing evaluation fixture contract test**

Create a loader test requiring at least 12 cases across `LIGHT`, `BALANCED`, `REWRITE`, feedback present/absent, new user fact, untrusted Assistant fact, over-limit draft, explanation and clarification intents. Every case must contain `case_id`, `label_status`, `request`, `review_expectations`, and `forbidden_outputs`; duplicate IDs and non-`DRAFT` labels fail.

```python
def test_repository_cases_cover_required_behaviors(self):
    cases = load_cases(CASE_PATH)
    self.assertGreaterEqual(len(cases), 12)
    self.assertEqual({case["label_status"] for case in cases}, {"DRAFT"})
    self.assertEqual(
        {case["expected_status"] for case in cases},
        {"REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"},
    )
    self.assertEqual(
        {case.get("expected_strength") for case in cases if case["expected_status"] == "REVISED"},
        {"LIGHT", "BALANCED", "REWRITE"},
    )
```

- [ ] **Step 2: Run the evaluation test and confirm missing fixture failure**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_evaluation -v
```

Expected: FAIL because the evaluation fixture and loader do not exist.

- [ ] **Step 3: Implement the fixture loader and add fixed draft cases**

Implement this public loader and validate every case before returning it:

```python
REQUIRED_STATUSES = {"REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"}
REQUIRED_STRENGTHS = {"LIGHT", "BALANCED", "REWRITE"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 12:
        raise ValueError("writing evaluation requires at least 12 cases")
    ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id.strip() for case_id in ids):
        raise ValueError("every writing case requires case_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate writing evaluation case_id")
    for case in cases:
        if case.get("label_status") != "DRAFT":
            raise ValueError("writing cases remain DRAFT until human approval")
        WritingMessageRequest.model_validate(case.get("request"))
        if case.get("expected_status") not in REQUIRED_STATUSES:
            raise ValueError("unknown expected_status")
        if not isinstance(case.get("review_expectations"), list):
            raise ValueError("review_expectations must be a list")
        if not isinstance(case.get("forbidden_outputs"), list):
            raise ValueError("forbidden_outputs must be a list")
    return cases
```

The review guide must score no hiring outcome. For each generated result, reviewers mark these eight dimensions as `PASS`, `FAIL`, or `NOT_ASSESSABLE`: `QUESTION_FIT`, `CORE_MESSAGE`, `EVIDENCE`, `AGENCY`, `JOB_RELEVANCE`, `READABILITY`, `CREDIBILITY`, `CONSTRAINTS`. It must instruct reviewers to fail the whole case for any fabricated user fact even when prose quality improves.

The JSON fixtures must use synthetic Korean drafts and contain no real personal data. `forbidden_outputs` must include invented metrics, employers, technologies or sole-credit claims relevant to each case.

- [ ] **Step 4: Write the API and collaboration document**

Document:

- full request and all three response examples from the spec
- `draft` as the current user-approved factual baseline
- allowed fact sources and forbidden feedback/Assistant facts
- 422/502/503 behavior
- char count as Python Unicode code points including whitespace
- supervisor Writing context and exact-one-`SELF_INTRO` rule
- analysis→Writing execution order and top-level versus Writing status semantics
- Backend responsibility for item selection, auth, conversation assembly and saving
- Frontend responsibility for showing proposed changes/warnings and obtaining acceptance
- Infra variables `WRITING_QWEN_ENV_FILE`, `SUPERVISOR_QWEN_ENV_FILE`, existing Qwen values, and two-call worst-case timeout budgeting

- [ ] **Step 5: Run evaluation, Writing, supervisor and serve tests**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.writing_coaching.test_evaluation -v
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests/writing_coaching -t . -v
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests/supervisor -t . -v
& '..\..\.venv\Scripts\python.exe' -m unittest ai.tests.test_serve -v
```

Expected: all focused suites PASS.

- [ ] **Step 6: Run dependency and full repository verification**

Run:

```powershell
& '..\..\.venv\Scripts\python.exe' -m pip check
& '..\..\.venv\Scripts\python.exe' -m unittest discover -s ai/tests -t . -v
git diff --check
git status --short
```

Expected: `pip check` reports no broken requirements; the full AI suite passes with only the existing PostgreSQL integration test skipped when `JD_TEST_DATABASE_URL` is absent; `git diff --check` prints nothing; status contains only intended plan/implementation files.

- [ ] **Step 7: Commit documentation and evaluation fixtures**

```powershell
git add docs/api/writing-agent-api.md ai/evals/writing_coaching ai/writing_coaching/evaluation.py ai/tests/writing_coaching/test_evaluation.py ai/requirements.txt
git commit -m "docs: document writing agent integration"
```

Do not stage `ai/requirements.txt` when it did not change.

---

## Final Review Checklist

- [ ] Compare every implementation diff against `docs/superpowers/specs/2026-09-15-writing-coaching-agent-design.md`.
- [ ] Confirm no file below `backend/` or frontend directories changed.
- [ ] Confirm no runtime path persists conversations or candidate revisions.
- [ ] Confirm Writing-only supervisor execution does not resolve JD or Position services.
- [ ] Confirm all error messages omit raw user drafts and conversation content.
- [ ] Confirm `agent_results` stay ordered by `plan.selected_agents` despite parallel analysis.
- [ ] Confirm `CLARIFICATION_REQUIRED` is a successful worker execution, not `FAILED`.
- [ ] Run the full verification commands from Task 8 and record exact pass/skip counts in the final handoff.
