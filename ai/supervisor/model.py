from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.jd_coaching.baseline import call_qwen
from ai.prompting.common import with_common_rules
from ai.supervisor.contracts import AgentResult, SupervisorPlan


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["selected_agents", "reason"],
    "properties": {
        "selected_agents": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": ["jd", "position", "writing", "news", "company"]},
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


class PlanOutputError(ValueError):
    """The model returned output that does not satisfy the plan contract."""


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
                "jd": "채용 공고 요구사항 하나하나에 대해 지원자 문서에 근거가 있는지 판정",
                "position": "사용자 경험(기술·비기술 모두)에서 문제·행동·검증·결과 등 빠진 요소를 찾고 구체화 질문 제시",
                "writing": "자기소개서 첨삭 또는 작성 방식 설명",
                "news": "기업·산업·직무 변화의 기사 근거와 JD 관련성 분석",
                "company": "공시(사업보고서·확정 재무 지표) 기반 기업 분석 리포트와 기업 관련 질의응답. 뉴스·주가·평판은 다루지 않음",
            },
        }
        if validation_error is not None:
            payload["previous_validation_error"] = validation_error
        try:
            response = self._qwen_caller(
                self._config,
                [
                    {
                        "role": "system",
                        "content": with_common_rules(
                            "사용 가능한 에이전트 안에서 요청 해결에 필요한 최소 집합을 선택하라. "
                            "자기소개서 첨삭·수정 또는 작성 방식 설명 요청은 Writing만 선택하라. "
                            "JD 또는 Position 분석을 첨삭에 반영해 달라고 사용자가 명시한 경우에만 "
                            "Writing과 해당 분석 에이전트를 함께 선택하라. 사용 불가 에이전트는 선택하지 마라."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                max_tokens=600,
                timeout_seconds=30,
                schema=PLAN_SCHEMA,
                schema_name="supervisor_plan_v1",
            )
        except json.JSONDecodeError as error:
            raise PlanOutputError(str(error)) from error
        except ValueError as error:
            # The shared JD caller wraps content parsing errors in this legacy error.
            if str(error) == "Qwen response does not contain valid JSON" and isinstance(
                error.__cause__, (KeyError, IndexError, TypeError, json.JSONDecodeError)
            ):
                raise PlanOutputError(str(error)) from error
            raise
        try:
            return SupervisorPlan.model_validate(response["output"])
        except (ValueError, TypeError, KeyError) as error:
            raise PlanOutputError(str(error)) from error

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
                    "content": with_common_rules(
                        "에이전트 결과의 사실만 사용해 중복 없이 한국어 검토 메시지를 작성하라."
                    ),
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
