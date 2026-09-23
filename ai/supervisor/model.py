from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.jd_coaching.baseline import call_qwen
from ai.prompting.common import with_common_rules
from ai.supervisor.aggregate import (
    AGGREGATE_SCHEMA,
    AGGREGATE_SCHEMA_VERSION,
    FORMAT_INSTRUCTION,
    AggregateOutputError,
    available_evidence_ids,
    render_aggregate,
    successful_agents,
    validate_aggregate,
)
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

# 종합 형식·스키마·검증은 ai/supervisor/aggregate.py 에 있다.


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
        agent_capabilities: Mapping[str, str] | None = None,
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
        aggregate_config: Mapping[str, str] | None = None,
    ) -> None:
        """
        @param config           계획(담당 고르기)에 쓰는 모델 설정. 분류 한 번이라 가벼운 모델
        @param aggregate_config 종합에 쓰는 모델 설정. 판단 품질이 중요해 다른 모델을 둘 수 있다.
                                없으면 계획과 같은 모델을 쓴다
        """
        self._config = dict(config)
        self._aggregate_config = dict(aggregate_config) if aggregate_config is not None else self._config
        self._qwen_caller = qwen_caller

    def create_plan(
        self,
        *,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        available_agents: Sequence[str],
        validation_error: str | None,
        agent_capabilities: Mapping[str, str] | None = None,
    ) -> SupervisorPlan:
        """agent_capabilities 는 어댑터가 스스로 밝힌 소개문(AgentRegistry.describe). 총괄은 이것만 보고 고른다."""
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
                name: (agent_capabilities or {}).get(name, name) for name in available_agents
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
        """네 칸(answer·judgments·conflicts·next_action)을 받아 검증하고 문장으로 조립한다.

        검증에 걸리면 오류 문구를 붙여 한 번 다시 묻는다. 두 번째도 실패하면 예외를 올려
        그래프의 fallback(담당 결과 나열)으로 넘긴다.
        """
        validation_error: str | None = None
        for attempt in range(2):
            payload: dict[str, Any] = {
                "instruction": instruction,
                "plan": plan.model_dump(),
                "successful_agents": successful_agents(results),
                "available_evidence_ids": available_evidence_ids(results),
                "agent_results": [item.model_dump() for item in results],
            }
            if validation_error is not None:
                payload["previous_validation_error"] = validation_error
                payload["retry_instruction"] = (
                    "위 검증 오류를 고쳐 네 칸 전체를 다시 반환한다. 담당 문장을 옮기지 말고 "
                    "담당 결과들을 연결한 판단으로 쓴다."
                )
            response = self._qwen_caller(
                self._aggregate_config,
                [
                    {"role": "system", "content": with_common_rules(FORMAT_INSTRUCTION)},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                max_tokens=2400,
                timeout_seconds=45,
                schema=AGGREGATE_SCHEMA,
                schema_name=AGGREGATE_SCHEMA_VERSION,
            )
            try:
                output = validate_aggregate(response["output"], results)
            except (AggregateOutputError, KeyError, TypeError) as error:
                validation_error = str(error)
                if attempt == 1:
                    raise ValueError(f"aggregate output rejected twice: {error}") from error
                continue
            return render_aggregate(output)
        raise ValueError("aggregate did not produce output")  # pragma: no cover
