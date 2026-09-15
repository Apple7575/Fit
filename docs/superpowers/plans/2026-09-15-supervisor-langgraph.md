# LangGraph Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 Spring 백엔드와 개별 에이전트 API를 변경하지 않고, JD와 position 에이전트를 동적으로 선택·병렬 실행·종합하는 동기식 LangGraph 총괄 API를 Python AI 서버에 추가한다.

**Architecture:** `ai/supervisor/` 안에 API 계약, Qwen 모델 포트, 기존 서비스 어댑터, LangGraph 실행기를 분리한다. `StateGraph`는 사용 가능한 에이전트를 계산하고 구조화된 계획을 검증한 뒤 `Send`로 작업을 병렬 분기하며, reducer로 결과를 모아 최종 메시지를 만든다. V1은 checkpointer와 실행 DB 없이 요청 단위로 `invoke()`한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, LangGraph 1.2.x, `unittest`, 기존 Qwen OpenAI-compatible JSON Schema 호출기

**Spec:** `docs/superpowers/specs/2026-09-15-supervisor-langgraph-design.md`

## Global Constraints

- 작업 브랜치는 `feat/supervisor-langgraph`다.
- Spring 백엔드, 프런트엔드, 기존 JD·position 분석 로직과 기존 API 계약은 수정하지 않는다.
- V1 실제 에이전트는 `jd`, `position`뿐이다.
- 총괄 실행은 동기식·무상태이며 checkpointer와 신규 DB를 사용하지 않는다.
- 컨텍스트 존재 여부는 대화에서 추측하지 않고 요청의 `agent_contexts`만 신뢰한다.
- 그래프 단위 테스트는 외부 Qwen과 PostgreSQL 없이 대역으로 실행한다.
- 개별 에이전트 실패는 재시도하지 않으며 다른 분기의 성공 결과를 보존한다.

---

## File Structure

- `ai/supervisor/contracts.py`: 요청·응답 Pydantic 모델, 계획과 실행 결과 타입, 도메인 오류를 정의한다.
- `ai/supervisor/model.py`: `SupervisorModel` 포트와 기존 `call_qwen`을 재사용하는 Qwen 구현을 담당한다.
- `ai/supervisor/adapters.py`: JD·position 서비스 호출 어댑터와 이름 기반 레지스트리를 제공한다.
- `ai/supervisor/graph.py`: 상태, reducer, 노드, 조건부 재계획, `Send` fan-out/fan-in을 구성한다.
- `ai/supervisor/service.py`: 그래프 입력·출력을 API 응답으로 변환하고 전체 실패를 도메인 오류로 바꾼다.
- `ai/supervisor/api.py`: 의존성 조립과 `/internal/runs` HTTP 오류 매핑을 담당한다.
- `ai/supervisor/__init__.py`: 패키지 경계를 만든다.
- `ai/tests/supervisor/`: 계약, 모델, 어댑터, 그래프, API 테스트를 둔다.
- `ai/requirements.txt`: `langgraph>=1.2,<1.3` 의존성을 추가한다.
- `ai/serve.py`: `/supervisor` 하위 앱과 루트 health 서비스 목록을 추가한다.
- `ai/tests/test_serve.py`: 총괄 앱 마운트를 회귀 검증한다.

---

### Task 1: 총괄 API 계약과 도메인 오류

**Files:**
- Create: `ai/supervisor/__init__.py`
- Create: `ai/supervisor/contracts.py`
- Create: `ai/tests/supervisor/__init__.py`
- Create: `ai/tests/supervisor/test_contracts.py`

**Interfaces:**
- Consumes: Pydantic v2의 `BaseModel`, `ConfigDict`, `Field`, `field_validator`.
- Produces: `SupervisorRunRequest`, `SupervisorPlan`, `AgentResult`, `SupervisorRunResponse`, `NoAvailableAgentError`, `AllAgentsFailedError`.

- [ ] **Step 1: 잘못된 요청과 정상 요청을 고정하는 실패 테스트 작성**

```python
import unittest

from pydantic import ValidationError

from ai.supervisor.contracts import SupervisorRunRequest


class SupervisorContractsTest(unittest.TestCase):
    def test_accepts_supported_documents_and_contexts(self):
        request = SupervisorRunRequest.model_validate({
            "instruction": "공고 적합성과 경험 깊이를 검토해줘",
            "documents": [{
                "document_id": "essay-1",
                "document_type": "SELF_INTRO",
                "text": "Spring 기반 주문 API를 구현했습니다.",
            }],
            "conversation": [],
            "agent_contexts": {
                "jd": {"job_context_id": "jctx_1"},
                "position": {"position_profile_id": "backend-v1"},
            },
        })

        self.assertEqual(request.documents[0].document_type, "SELF_INTRO")
        self.assertEqual(request.agent_contexts.jd.job_context_id, "jctx_1")

    def test_rejects_unknown_fields_and_blank_instruction(self):
        with self.assertRaises(ValidationError):
            SupervisorRunRequest.model_validate({
                "instruction": " ",
                "documents": [],
                "conversation": [],
                "agent_contexts": {},
                "unexpected": True,
            })
```

- [ ] **Step 2: 테스트가 계약 모듈 부재로 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_contracts -v`

Expected: `ModuleNotFoundError: No module named 'ai.supervisor'`.

- [ ] **Step 3: Pydantic 계약과 도메인 오류 최소 구현**

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SupervisorDocument(StrictModel):
    document_id: str = Field(min_length=1, max_length=100)
    document_type: Literal["RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"]
    text: str = Field(min_length=1, max_length=50_000)

    @field_validator("document_id", "text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ConversationMessage(StrictModel):
    message_id: str = Field(min_length=1, max_length=100)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("message_id", "content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class JdAgentContext(StrictModel):
    job_context_id: str = Field(min_length=1, max_length=100)

    @field_validator("job_context_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class PositionAgentContext(StrictModel):
    position_profile_id: str = Field(min_length=1, max_length=100)

    @field_validator("position_profile_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class AgentContexts(StrictModel):
    jd: JdAgentContext | None = None
    position: PositionAgentContext | None = None


class SupervisorRunRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    documents: list[SupervisorDocument] = Field(min_length=1, max_length=21)
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)
    agent_contexts: AgentContexts

    @field_validator("instruction")
    @classmethod
    def reject_blank_instruction(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instruction must not be blank")
        return value

    @field_validator("documents")
    @classmethod
    def reject_duplicate_document_ids(
        cls, value: list[SupervisorDocument]
    ) -> list[SupervisorDocument]:
        ids = [document.document_id for document in value]
        if len(ids) != len(set(ids)):
            raise ValueError("documents must not contain duplicate document_id")
        return value


class SupervisorPlan(StrictModel):
    selected_agents: list[Literal["jd", "position"]] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2_000)


class AgentResult(StrictModel):
    agent: Literal["jd", "position"]
    status: Literal["SUCCESS", "FAILED"]
    result: dict[str, Any] | None = None
    error: str | None = None


class SupervisorRunResponse(StrictModel):
    status: Literal["SUCCESS", "PARTIAL"]
    message: str
    plan: SupervisorPlan
    agent_results: list[AgentResult]


class NoAvailableAgentError(RuntimeError):
    pass


class AllAgentsFailedError(RuntimeError):
    def __init__(self, results: list[AgentResult]) -> None:
        super().__init__("all selected agents failed")
        self.results = results
```

- [ ] **Step 4: 계약 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_contracts -v`

Expected: 모든 테스트가 `OK`.

- [ ] **Step 5: 계약 구현 커밋**

```powershell
git add ai/supervisor/__init__.py ai/supervisor/contracts.py ai/tests/supervisor/__init__.py ai/tests/supervisor/test_contracts.py
git commit -m "feat: add supervisor contracts"
```

---

### Task 2: 구조화된 계획·종합 Qwen 모델 포트

**Files:**
- Create: `ai/supervisor/model.py`
- Create: `ai/tests/supervisor/test_model.py`

**Interfaces:**
- Consumes: `call_qwen(config, messages, *, max_tokens, timeout_seconds, schema, schema_name)`와 Task 1의 `SupervisorPlan`, `AgentResult`.
- Produces: `SupervisorModel.create_plan(...) -> SupervisorPlan`, `SupervisorModel.aggregate(...) -> str`, `QwenSupervisorModel`.

- [ ] **Step 1: Qwen 호출 계약을 검증하는 실패 테스트 작성**

```python
import unittest

from ai.supervisor.contracts import AgentResult
from ai.supervisor.model import QwenSupervisorModel


class FakeQwen:
    def __init__(self):
        self.calls = []

    def __call__(self, config, messages, **kwargs):
        self.calls.append({"config": config, "messages": messages, **kwargs})
        if kwargs["schema_name"] == "supervisor_plan_v1":
            return {"output": {"selected_agents": ["jd"], "reason": "JD 검토 요청"}}
        return {"output": {"message": "JD 기준으로 보완이 필요합니다."}}


class QwenSupervisorModelTest(unittest.TestCase):
    def test_uses_structured_schemas_for_plan_and_aggregate(self):
        qwen = FakeQwen()
        model = QwenSupervisorModel(
            config={"base_url": "http://qwen", "model": "qwen", "api_key": "x"},
            qwen_caller=qwen,
        )

        plan = model.create_plan(
            instruction="공고 적합성을 검토해줘",
            documents=[{"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "내용"}],
            conversation=[],
            available_agents=["jd"],
            validation_error=None,
        )
        message = model.aggregate(
            instruction="공고 적합성을 검토해줘",
            plan=plan,
            results=[AgentResult(agent="jd", status="SUCCESS", result={"summary": {}})],
        )

        self.assertEqual(plan.selected_agents, ["jd"])
        self.assertEqual(message, "JD 기준으로 보완이 필요합니다.")
        self.assertEqual(qwen.calls[0]["schema_name"], "supervisor_plan_v1")
        self.assertEqual(qwen.calls[1]["schema_name"], "supervisor_aggregate_v1")
```

- [ ] **Step 2: 테스트가 모델 모듈 부재로 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_model -v`

Expected: `ModuleNotFoundError: No module named 'ai.supervisor.model'`.

- [ ] **Step 3: 모델 포트, 프롬프트, JSON Schema 구현**

```python
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.jd_coaching.baseline import call_qwen
from ai.supervisor.contracts import AgentResult, SupervisorPlan


class SupervisorModel(Protocol):
    def create_plan(
        self,
        *,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        available_agents: Sequence[str],
        validation_error: str | None,
    ) -> SupervisorPlan: ...

    def aggregate(
        self,
        *,
        instruction: str,
        plan: SupervisorPlan,
        results: Sequence[AgentResult],
    ) -> str: ...


class QwenSupervisorModel:
    def __init__(self, config: Mapping[str, str], qwen_caller: Callable[..., dict[str, Any]] = call_qwen) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller
```

`create_plan`은 에이전트 설명(`jd`: 공고 요구사항 대비 근거 검토, `position`: 백엔드 경험의 구체성 검토), 문서 메타데이터, 대화, `available_agents`만 모델에 보낸다. `validation_error`가 있으면 마지막 사용자 메시지에 검증 실패 이유를 포함한다. 반환 `output`은 다음 스키마로 호출 후 `SupervisorPlan.model_validate()`한다.

```python
PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["selected_agents", "reason"],
    "properties": {
        "selected_agents": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": ["jd", "position"]},
        },
        "reason": {"type": "string", "minLength": 1},
    },
}

AGGREGATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message"],
    "properties": {"message": {"type": "string", "minLength": 1}},
}
```

`QwenSupervisorModel`의 두 메서드는 다음 형태로 구현한다. 기존 `call_qwen`이 `temperature=0`을 강제하므로 별도 temperature 인자를 추가하지 않는다.

```python
def create_plan(
    self,
    *,
    instruction,
    documents,
    conversation,
    available_agents,
    validation_error,
):
    payload = {
        "instruction": instruction,
        "documents": [
            {
                "document_id": item["document_id"],
                "document_type": item["document_type"],
            }
            for item in documents
        ],
        "conversation": list(conversation),
        "available_agents": list(available_agents),
        "agent_capabilities": {
            "jd": "채용 공고 요구사항 대비 지원자 근거 검토",
            "position": "백엔드 경험의 문제·행동·검증·결과 구체성 검토",
        },
    }
    if validation_error is not None:
        payload["previous_validation_error"] = validation_error
    response = self._qwen_caller(
        self._config,
        [
            {
                "role": "system",
                "content": "사용 가능한 에이전트 안에서 요청 해결에 필요한 최소 집합을 선택하라.",
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        max_tokens=600,
        timeout_seconds=30,
        schema=PLAN_SCHEMA,
        schema_name="supervisor_plan_v1",
    )
    return SupervisorPlan.model_validate(response["output"])


def aggregate(self, *, instruction, plan, results):
    response = self._qwen_caller(
        self._config,
        [
            {
                "role": "system",
                "content": "에이전트 결과의 사실만 사용해 중복 없이 한국어 검토 메시지를 작성하라.",
            },
            {
                "role": "user",
                "content": json.dumps({
                    "instruction": instruction,
                    "plan": plan.model_dump(),
                    "agent_results": [item.model_dump() for item in results],
                }, ensure_ascii=False),
            },
        ],
        max_tokens=1600,
        timeout_seconds=30,
        schema=AGGREGATE_SCHEMA,
        schema_name="supervisor_aggregate_v1",
    )
    message = response["output"].get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("aggregate message must not be blank")
    return message.strip()
```

- [ ] **Step 4: 모델 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_model -v`

Expected: 모든 테스트가 `OK`이며 외부 HTTP 호출은 없다.

- [ ] **Step 5: 모델 포트 커밋**

```powershell
git add ai/supervisor/model.py ai/tests/supervisor/test_model.py
git commit -m "feat: add supervisor model port"
```

---

### Task 3: 기존 JD·position 서비스 어댑터와 레지스트리

**Files:**
- Create: `ai/supervisor/adapters.py`
- Create: `ai/tests/supervisor/test_adapters.py`

**Interfaces:**
- Consumes: `JdAnalysisService.analyze_documents(context_id, documents)`, `PositionAnalysisService.analyze(profile_id, documents, conversation)`.
- Produces: `SupervisorAgentAdapter`, `JdAgentAdapter`, `PositionAgentAdapter`, `AgentRegistry.available_names(contexts)`, `AgentRegistry.execute(name, instruction, documents, conversation, context)`.

- [ ] **Step 1: 가용성 판정과 직접 서비스 호출 실패 테스트 작성**

```python
import unittest

from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter, PositionAgentAdapter


class FakeJdService:
    def __init__(self):
        self.calls = []

    def analyze_documents(self, context_id, documents):
        self.calls.append((context_id, documents))
        return {"context_id": context_id}


class FakePositionService:
    def __init__(self):
        self.calls = []

    def analyze(self, profile_id, documents, conversation):
        self.calls.append((profile_id, documents, conversation))
        return {"position_profile": {"id": profile_id}}


class AgentRegistryTest(unittest.TestCase):
    def test_resolves_context_backed_agents_and_calls_services_directly(self):
        jd = FakeJdService()
        position = FakePositionService()
        registry = AgentRegistry([JdAgentAdapter(jd), PositionAgentAdapter(position)])
        contexts = {
            "jd": {"job_context_id": "jctx_1"},
            "position": {"position_profile_id": "backend-v1"},
        }
        documents = [{"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "내용"}]

        self.assertEqual(registry.available_names(contexts), ["jd", "position"])
        registry.execute("jd", "검토", documents, [], contexts["jd"])
        registry.execute("position", "검토", documents, [], contexts["position"])

        self.assertEqual(jd.calls[0][0], "jctx_1")
        self.assertEqual(position.calls[0][0], "backend-v1")
```

- [ ] **Step 2: 테스트가 어댑터 모듈 부재로 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_adapters -v`

Expected: `ModuleNotFoundError: No module named 'ai.supervisor.adapters'`.

- [ ] **Step 3: 어댑터와 레지스트리 최소 구현**

```python
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class SupervisorAgentAdapter(Protocol):
    name: str

    def is_available(self, context: Mapping[str, Any] | None) -> bool: ...

    def execute(
        self,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
    ) -> dict[str, Any]: ...


class JdAgentAdapter:
    name = "jd"

    def __init__(self, service: Any) -> None:
        self._service = service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("job_context_id"))

    def execute(self, instruction, documents, conversation, context):
        return self._service.analyze_documents(context["job_context_id"], list(documents))


class PositionAgentAdapter:
    name = "position"

    def __init__(self, service: Any) -> None:
        self._service = service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("position_profile_id"))

    def execute(self, instruction, documents, conversation, context):
        return self._service.analyze(
            context["position_profile_id"], list(documents), list(conversation)
        )


class AgentRegistry:
    def __init__(self, adapters: Sequence[SupervisorAgentAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("agent names must be unique")

    def available_names(self, contexts: Mapping[str, Any]) -> list[str]:
        return [
            name
            for name, adapter in self._adapters.items()
            if adapter.is_available(contexts.get(name))
        ]

    def execute(
        self,
        name: str,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        if name not in self._adapters:
            raise KeyError(f"unknown agent: {name}")
        return self._adapters[name].execute(
            instruction, documents, conversation, context
        )
```

Python dict의 삽입 순서로 어댑터 전달 순서를 유지한다. `instruction`은 V1 기존 서비스 시그니처에는 전달되지 않지만 공통 포트에 남겨 신규 에이전트가 사용할 수 있게 한다.

- [ ] **Step 4: 어댑터 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_adapters -v`

Expected: 모든 테스트가 `OK`.

- [ ] **Step 5: 어댑터 구현 커밋**

```powershell
git add ai/supervisor/adapters.py ai/tests/supervisor/test_adapters.py
git commit -m "feat: adapt existing analysis services"
```

---

### Task 4: LangGraph 동적 계획·병렬 실행·실패 격리

**Files:**
- Modify: `ai/requirements.txt`
- Create: `ai/supervisor/graph.py`
- Create: `ai/tests/supervisor/test_graph.py`

**Interfaces:**
- Consumes: Task 1의 계약, Task 2의 `SupervisorModel`, Task 3의 `AgentRegistry`.
- Produces: `SupervisorState`, `validate_selected_agents(plan, available_agents)`, `build_supervisor_graph(model, registry)`가 반환하는 checkpointer 없는 compiled graph.

- [ ] **Step 1: LangGraph 의존성 범위 추가 및 설치**

`ai/requirements.txt`에 다음 한 줄을 추가한다.

```text
langgraph>=1.2,<1.3
```

Run: `.venv\Scripts\python.exe -m pip install -r ai/requirements-dev.txt`

Expected: `langgraph` 1.2.x가 설치되고 명령이 exit code 0으로 끝난다.

- [ ] **Step 2: 선택 검증, 재계획 fallback, 병렬 결과 병합 실패 테스트 작성**

```python
import threading
import time
import unittest

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import SupervisorPlan
from ai.supervisor.graph import build_supervisor_graph, validate_selected_agents


class FakeModel:
    def __init__(self, plans):
        self.plans = list(plans)
        self.plan_errors = []

    def create_plan(self, **kwargs):
        self.plan_errors.append(kwargs["validation_error"])
        return self.plans.pop(0)

    def aggregate(self, **kwargs):
        return "종합 결과"


class RecordingAdapter:
    def __init__(self, name, barrier, fail=False):
        self.name = name
        self.barrier = barrier
        self.fail = fail
        self.threads = []

    def is_available(self, context):
        return context is not None

    def execute(self, instruction, documents, conversation, context):
        self.threads.append(threading.get_ident())
        self.barrier.wait(timeout=1)
        time.sleep(0.01)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        return {"agent": self.name}


class SupervisorGraphTest(unittest.TestCase):
    def test_rejects_duplicate_unknown_and_unavailable_selections(self):
        with self.assertRaises(ValueError):
            validate_selected_agents(SupervisorPlan(selected_agents=["jd", "jd"], reason="중복"), ["jd"])
        with self.assertRaises(ValueError):
            validate_selected_agents({"selected_agents": ["unknown"], "reason": "오류"}, ["jd"])
        with self.assertRaises(ValueError):
            validate_selected_agents(SupervisorPlan(selected_agents=["position"], reason="불가"), ["jd"])

    def test_retries_bad_plan_then_falls_back_to_all_available_agents(self):
        model = FakeModel([
            {"selected_agents": ["unknown"], "reason": "오류"},
            {"selected_agents": ["jd", "jd"], "reason": "중복"},
        ])
        barrier = threading.Barrier(2)
        registry = AgentRegistry([
            RecordingAdapter("jd", barrier),
            RecordingAdapter("position", barrier),
        ])
        result = build_supervisor_graph(model, registry).invoke({
            "instruction": "둘 다 검토",
            "documents": [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            "conversation": [],
            "agent_contexts": {"jd": {"job_context_id": "jctx"}, "position": {"position_profile_id": "backend-v1"}},
            "agent_results": [],
        })

        self.assertEqual(result["plan"].selected_agents, ["jd", "position"])
        self.assertEqual(len(model.plan_errors), 2)
        self.assertIsNotNone(model.plan_errors[1])
        self.assertEqual({item.agent for item in result["agent_results"]}, {"jd", "position"})
```

같은 파일에 다음 사례를 별도 테스트로 추가한다.

- 컨텍스트가 하나면 `available_agents`에도 하나만 포함된다.
- 컨텍스트가 전혀 없으면 `NoAvailableAgentError`가 발생한다.
- 유효한 계획은 모델을 한 번만 호출한다.
- 한 worker 예외는 다른 worker를 중단시키지 않고 `FAILED` 결과로 저장한다.
- 두 `RecordingAdapter`가 서로 다른 thread ID에서 barrier를 통과해 실제 병렬 실행된다.
- aggregate 모델 예외 시 성공 결과를 에이전트 선택 순서대로 직렬화한 결정적 메시지가 생성된다.

- [ ] **Step 3: 새 그래프 테스트가 모듈 부재로 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_graph -v`

Expected: `ModuleNotFoundError: No module named 'ai.supervisor.graph'`.

- [ ] **Step 4: 상태, reducer, 노드와 `Send` 그래프 구현**

```python
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ai.supervisor.contracts import AgentResult, NoAvailableAgentError, SupervisorPlan


class SupervisorState(TypedDict, total=False):
    instruction: str
    documents: list[dict[str, Any]]
    conversation: list[dict[str, Any]]
    agent_contexts: dict[str, dict[str, Any]]
    available_agents: list[str]
    plan: SupervisorPlan
    agent_results: Annotated[list[AgentResult], operator.add]
    final_message: str


class WorkerState(TypedDict):
    agent: str
    instruction: str
    documents: list[dict[str, Any]]
    conversation: list[dict[str, Any]]
    context: dict[str, Any]


def validate_selected_agents(plan: Any, available_agents: list[str]) -> SupervisorPlan:
    validated = plan if isinstance(plan, SupervisorPlan) else SupervisorPlan.model_validate(plan)
    selected = validated.selected_agents
    if len(selected) != len(set(selected)):
        raise ValueError("selected_agents must not contain duplicates")
    unavailable = [name for name in selected if name not in available_agents]
    if unavailable:
        raise ValueError(f"selected agent is unavailable: {', '.join(unavailable)}")
    return validated
```

`build_supervisor_graph(model, registry)`는 closure 노드로 아래 정책을 구현한다.

```python
def create_plan(state: SupervisorState) -> dict[str, Any]:
    validation_error = None
    for _ in range(2):
        candidate = model.create_plan(
            instruction=state["instruction"],
            documents=state["documents"],
            conversation=state["conversation"],
            available_agents=state["available_agents"],
            validation_error=validation_error,
        )
        try:
            return {"plan": validate_selected_agents(candidate, state["available_agents"])}
        except (ValueError, TypeError) as error:
            validation_error = str(error)
    return {"plan": SupervisorPlan(
        selected_agents=state["available_agents"],
        reason="계획 검증 실패로 실행 가능한 모든 에이전트를 선택한 fallback 계획",
    )}


def dispatch_agents(state: SupervisorState) -> list[Send]:
    return [
        Send("run_agent", {
            "agent": name,
            "instruction": state["instruction"],
            "documents": state["documents"],
            "conversation": state["conversation"],
            "context": state["agent_contexts"][name],
        })
        for name in state["plan"].selected_agents
    ]
```

나머지 노드는 다음 동작을 그대로 사용한다.

```python
def validate_input(state: SupervisorState) -> dict[str, Any]:
    if not state.get("instruction", "").strip():
        raise ValueError("instruction must not be blank")
    if not state.get("documents"):
        raise ValueError("documents must not be empty")
    return {}


def resolve_available_agents(state: SupervisorState) -> dict[str, Any]:
    names = registry.available_names(state["agent_contexts"])
    if not names:
        raise NoAvailableAgentError("no agent context was provided")
    return {"available_agents": names}


def validate_plan(state: SupervisorState) -> dict[str, Any]:
    return {"plan": validate_selected_agents(
        state["plan"], state["available_agents"]
    )}


def run_agent(state: WorkerState) -> dict[str, Any]:
    try:
        result = registry.execute(
            state["agent"],
            state["instruction"],
            state["documents"],
            state["conversation"],
            state["context"],
        )
        agent_result = AgentResult(
            agent=state["agent"], status="SUCCESS", result=result
        )
    except Exception as error:
        agent_result = AgentResult(
            agent=state["agent"],
            status="FAILED",
            error=f"{type(error).__name__}: {error}",
        )
    return {"agent_results": [agent_result]}


def aggregate_results(state: SupervisorState) -> dict[str, Any]:
    order = {name: index for index, name in enumerate(state["plan"].selected_agents)}
    results = sorted(state["agent_results"], key=lambda item: order[item.agent])
    successes = [item for item in results if item.status == "SUCCESS"]
    if not successes:
        return {"final_message": ""}
    try:
        message = model.aggregate(
            instruction=state["instruction"], plan=state["plan"], results=successes
        )
    except Exception:
        message = "\n".join(
            f"[{item.agent}] "
            + json.dumps(item.result, ensure_ascii=False, sort_keys=True)
            for item in successes
        )
    return {"final_message": message}
```

그래프 조립은 다음 edge를 사용하고 `compile()`에 checkpointer를 전달하지 않는다.

```python
builder = StateGraph(SupervisorState)
builder.add_node("validate_input", validate_input)
builder.add_node("resolve_available_agents", resolve_available_agents)
builder.add_node("create_plan", create_plan)
builder.add_node("validate_plan", validate_plan)
builder.add_node("run_agent", run_agent)
builder.add_node("aggregate_results", aggregate_results)
builder.add_edge(START, "validate_input")
builder.add_edge("validate_input", "resolve_available_agents")
builder.add_edge("resolve_available_agents", "create_plan")
builder.add_edge("create_plan", "validate_plan")
builder.add_conditional_edges("validate_plan", dispatch_agents, ["run_agent"])
builder.add_edge("run_agent", "aggregate_results")
builder.add_edge("aggregate_results", END)
return builder.compile()
```

- [ ] **Step 5: 그래프 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_graph -v`

Expected: 가용성, 두 번의 계획 시도, fallback, 병렬 fan-out, 부분 실패, 종합 fallback 테스트가 모두 `OK`.

- [ ] **Step 6: 그래프 구현 커밋**

```powershell
git add ai/requirements.txt ai/supervisor/graph.py ai/tests/supervisor/test_graph.py
git commit -m "feat: orchestrate agents with LangGraph"
```

---

### Task 5: 실행 서비스와 HTTP 오류 정책

**Files:**
- Create: `ai/supervisor/service.py`
- Create: `ai/supervisor/api.py`
- Create: `ai/tests/supervisor/test_service.py`
- Create: `ai/tests/supervisor/test_api.py`

**Interfaces:**
- Consumes: `build_supervisor_graph(model, registry)`, `SupervisorRunRequest`.
- Produces: `SupervisorService.run(request) -> SupervisorRunResponse`, FastAPI `app`, `get_supervisor_service()`, `POST /internal/runs`.

- [ ] **Step 1: 성공·부분 실패·전체 실패 서비스 테스트 작성**

```python
import unittest

from ai.supervisor.contracts import AllAgentsFailedError, SupervisorRunRequest
from ai.supervisor.service import SupervisorService


REQUEST = SupervisorRunRequest.model_validate({
    "instruction": "검토해줘",
    "documents": [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
    "conversation": [],
    "agent_contexts": {"jd": {"job_context_id": "jctx"}},
})


class FakeGraph:
    def __init__(self, output):
        self.output = output

    def invoke(self, state):
        return self.output


class SupervisorServiceTest(unittest.TestCase):
    def test_maps_mixed_results_to_partial(self):
        graph = FakeGraph({
            "plan": {"selected_agents": ["jd", "position"], "reason": "둘 다 필요"},
            "agent_results": [
                {"agent": "jd", "status": "SUCCESS", "result": {"summary": {}}},
                {"agent": "position", "status": "FAILED", "error": "RuntimeError: failed"},
            ],
            "final_message": "JD 결과만 반영했습니다.",
        })

        response = SupervisorService(graph).run(REQUEST)

        self.assertEqual(response.status, "PARTIAL")

    def test_raises_when_all_agents_fail(self):
        graph = FakeGraph({
            "plan": {"selected_agents": ["jd"], "reason": "JD 필요"},
            "agent_results": [{"agent": "jd", "status": "FAILED", "error": "RuntimeError: failed"}],
            "final_message": "",
        })

        with self.assertRaises(AllAgentsFailedError):
            SupervisorService(graph).run(REQUEST)
```

- [ ] **Step 2: 422·502 HTTP 매핑 실패 테스트 작성**

```python
import unittest

from fastapi.testclient import TestClient

from ai.supervisor.api import app, get_supervisor_service
from ai.supervisor.contracts import AllAgentsFailedError, AgentResult, NoAvailableAgentError


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def run(self, request):
        if self.error is not None:
            raise self.error
        return self.result


class SupervisorApiTest(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_maps_no_available_agent_to_422(self):
        app.dependency_overrides[get_supervisor_service] = lambda: FakeService(error=NoAvailableAgentError("none"))
        response = TestClient(app).post("/internal/runs", json={
            "instruction": "검토해줘",
            "documents": [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            "conversation": [],
            "agent_contexts": {},
        })

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "NO_AVAILABLE_AGENT")

    def test_maps_all_failed_to_502(self):
        error = AllAgentsFailedError([AgentResult(agent="jd", status="FAILED", error="RuntimeError: failed")])
        app.dependency_overrides[get_supervisor_service] = lambda: FakeService(error=error)
        response = TestClient(app).post("/internal/runs", json={
            "instruction": "검토해줘",
            "documents": [{"document_id": "essay", "document_type": "SELF_INTRO", "text": "내용"}],
            "conversation": [],
            "agent_contexts": {"jd": {"job_context_id": "jctx"}},
        })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "ALL_AGENTS_FAILED")
```

정상 응답이 HTTP 200이며 응답 모델과 일치하는 테스트, Pydantic 스키마 오류가 기본 HTTP 422인 테스트도 추가한다.

- [ ] **Step 3: 서비스와 API 모듈 부재로 테스트가 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_service ai.tests.supervisor.test_api -v`

Expected: `ModuleNotFoundError`로 실패한다.

- [ ] **Step 4: 그래프 응답 변환 서비스 구현**

```python
from typing import Any, Protocol

from ai.supervisor.contracts import (
    AgentResult,
    AllAgentsFailedError,
    SupervisorPlan,
    SupervisorRunRequest,
    SupervisorRunResponse,
)


class InvokableGraph(Protocol):
    def invoke(self, state: dict[str, Any]) -> dict[str, Any]: ...


class SupervisorService:
    def __init__(self, graph: InvokableGraph) -> None:
        self._graph = graph

    def run(self, request: SupervisorRunRequest) -> SupervisorRunResponse:
        state = request.model_dump()
        state["agent_results"] = []
        output = self._graph.invoke(state)
        plan = SupervisorPlan.model_validate(output["plan"])
        order = {name: index for index, name in enumerate(plan.selected_agents)}
        results = sorted(
            [AgentResult.model_validate(item) for item in output["agent_results"]],
            key=lambda item: order[item.agent],
        )
        successes = [item for item in results if item.status == "SUCCESS"]
        if not successes:
            raise AllAgentsFailedError(results)
        status = "SUCCESS" if len(successes) == len(results) else "PARTIAL"
        return SupervisorRunResponse(
            status=status,
            message=output["final_message"],
            plan=plan,
            agent_results=results,
        )
```

- [ ] **Step 5: 실제 의존성 조립과 API 구현**

`get_supervisor_service()`는 `@lru_cache(maxsize=1)`로 아래 객체를 조립한다.

```python
env_file = Path(os.environ.get("SUPERVISOR_QWEN_ENV_FILE", str(AI_ROOT / ".env")))
model = QwenSupervisorModel(load_qwen_config(env_file))
registry = AgentRegistry([
    JdAgentAdapter(get_analysis_service()),
    PositionAgentAdapter(get_position_service()),
])
return SupervisorService(build_supervisor_graph(model, registry))
```

FastAPI 앱과 endpoint는 다음 오류 형태를 고정한다.

```python
app = FastAPI(title="Supervisor API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/runs", response_model=SupervisorRunResponse)
def create_run(
    request: SupervisorRunRequest,
    service: Annotated[SupervisorService, Depends(get_supervisor_service)],
) -> SupervisorRunResponse:
    try:
        return service.run(request)
    except NoAvailableAgentError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "NO_AVAILABLE_AGENT", "message": str(error)},
        ) from error
    except AllAgentsFailedError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ALL_AGENTS_FAILED",
                "message": str(error),
                "agent_results": [item.model_dump() for item in error.results],
            },
        ) from error
```

Qwen 설정 누락은 기존 서비스들과 같은 방식으로 HTTP 503으로 매핑한다. 실제 endpoint가 자기 서버의 `/jd`나 `/position` URL로 HTTP 요청하지 않는다는 점을 API 테스트에서 dependency override로 확인한다.

- [ ] **Step 6: 서비스와 API 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.supervisor.test_service ai.tests.supervisor.test_api -v`

Expected: 성공, `PARTIAL`, 기본 schema 422, `NO_AVAILABLE_AGENT` 422, `ALL_AGENTS_FAILED` 502, 설정 누락 503 테스트가 모두 `OK`.

- [ ] **Step 7: 서비스와 API 커밋**

```powershell
git add ai/supervisor/service.py ai/supervisor/api.py ai/tests/supervisor/test_service.py ai/tests/supervisor/test_api.py
git commit -m "feat: expose supervisor run API"
```

---

### Task 6: 루트 앱 마운트와 전체 회귀 검증

**Files:**
- Modify: `ai/serve.py`
- Modify: `ai/tests/test_serve.py`

**Interfaces:**
- Consumes: Task 5의 `ai.supervisor.api.app`.
- Produces: `/supervisor/health`, `/supervisor/internal/runs`, 루트 `/health`의 `services.supervisor`.

- [ ] **Step 1: supervisor 마운트 실패 테스트 작성**

`AiServeTest`에 다음 테스트를 추가한다.

```python
def test_mounts_supervisor_service(self):
    client = TestClient(build_app())

    health = client.get("/health")
    supervisor_health = client.get("/supervisor/health")

    self.assertEqual(health.status_code, 200)
    self.assertEqual(health.json()["services"]["supervisor"], "/supervisor")
    self.assertEqual(supervisor_health.status_code, 200)
```

- [ ] **Step 2: 테스트가 404 또는 누락 key로 실패하는지 확인**

Run: `.venv\Scripts\python.exe -m unittest ai.tests.test_serve.AiServeTest.test_mounts_supervisor_service -v`

Expected: `/supervisor/health`가 404이거나 `services["supervisor"]`가 없어 실패한다.

- [ ] **Step 3: 루트 FastAPI 앱에 supervisor 추가**

`build_app()`에서 총괄 앱을 import하고 health 응답 및 mount를 추가한다.

```python
from ai.supervisor.api import app as supervisor_app

return {
    "status": "ok",
    "services": {
        "jd": "/jd",
        "position": "/position",
        "supervisor": "/supervisor",
    },
}

root.mount("/supervisor", supervisor_app)
```

모듈 docstring의 경로 목록에도 `/supervisor/...`를 추가한다. supervisor 앱에는 lifespan 자원이 없으므로 기존 JD lifespan 중첩 구조는 변경하지 않는다.

- [ ] **Step 4: 마운트와 supervisor 전체 테스트 실행**

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests/supervisor -t . -v`

Expected: supervisor 테스트 전체가 `OK`.

Run: `.venv\Scripts\python.exe -m unittest ai.tests.test_serve -v`

Expected: 기존 position 마운트와 신규 supervisor 마운트 테스트가 모두 `OK`.

- [ ] **Step 5: 기존 JD·position 회귀 테스트 실행**

Run: `.venv\Scripts\python.exe -m unittest discover -s ai/tests -t . -v`

Expected: 외부 통합 환경을 요구하지 않는 AI 단위 테스트 전체가 `OK`. 환경 의존 테스트가 skip되면 skip 사유를 최종 보고에 기록한다.

- [ ] **Step 6: 코드 형식과 변경 범위 확인**

Run: `git diff --check`

Expected: 출력 없이 exit code 0.

Run: `git status --short`

Expected: 이번 작업 파일만 수정·추가 상태이며 기존 사용자 미추적 파일은 stage되지 않는다.

- [ ] **Step 7: 루트 마운트 커밋**

```powershell
git add ai/serve.py ai/tests/test_serve.py
git commit -m "feat: mount supervisor API"
```

---

## 완료 기준

- `POST /supervisor/internal/runs`가 전달된 컨텍스트 안에서만 JD·position을 동적으로 선택한다.
- 선택된 두 에이전트는 LangGraph `Send` 분기로 병렬 실행되고 reducer로 결과가 합쳐진다.
- 계획 오류는 한 번 재시도한 뒤 모든 가용 에이전트 fallback으로 끝난다.
- 일부 실패는 HTTP 200 `PARTIAL`, 전체 실패는 HTTP 502 `ALL_AGENTS_FAILED`다.
- 종합 모델 실패에도 결정적 fallback 메시지를 반환한다.
- 개별 JD·position API와 Spring 백엔드 코드는 변경되지 않는다.
- checkpointer와 신규 실행 DB가 추가되지 않는다.
- AI 전체 테스트와 `git diff --check`가 통과한다.
