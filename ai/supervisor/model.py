from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.jd_coaching.baseline import call_qwen
from ai.supervisor.contracts import AgentResult, SupervisorPlan


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
    def __init__(
        self,
        config: Mapping[str, str],
        qwen_caller: Callable[..., dict[str, Any]] = call_qwen,
    ) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller

    def create_plan(
        self,
        *,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        available_agents: Sequence[str],
        validation_error: str | None,
    ) -> SupervisorPlan:
        payload: dict[str, Any] = {
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

    def aggregate(
        self,
        *,
        instruction: str,
        plan: SupervisorPlan,
        results: Sequence[AgentResult],
    ) -> str:
        response = self._qwen_caller(
            self._config,
            [
                {
                    "role": "system",
                    "content": "에이전트 결과의 사실만 사용해 중복 없이 한국어 검토 메시지를 작성하라.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": instruction,
                            "plan": plan.model_dump(),
                            "agent_results": [item.model_dump() for item in results],
                        },
                        ensure_ascii=False,
                    ),
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

