from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import AgentResult, NoAvailableAgentError, SupervisorPlan
from ai.supervisor.model import PlanOutputError, SupervisorModel


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


def validate_selected_agents(
    plan: Any, available_agents: list[str]
) -> SupervisorPlan:
    validated = (
        plan if isinstance(plan, SupervisorPlan) else SupervisorPlan.model_validate(plan)
    )
    selected = validated.selected_agents
    if len(selected) != len(set(selected)):
        raise ValueError("selected_agents must not contain duplicates")
    unavailable = [name for name in selected if name not in available_agents]
    if unavailable:
        raise ValueError(f"selected agent is unavailable: {', '.join(unavailable)}")
    return validated


def build_supervisor_graph(model: SupervisorModel, registry: AgentRegistry):
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

    def create_plan(state: SupervisorState) -> dict[str, Any]:
        validation_error = None
        for _ in range(2):
            try:
                candidate = model.create_plan(
                    instruction=state["instruction"],
                    documents=state["documents"],
                    conversation=state["conversation"],
                    available_agents=state["available_agents"],
                    validation_error=validation_error,
                )
            except PlanOutputError as error:
                validation_error = str(error)
                continue
            try:
                return {
                    "plan": validate_selected_agents(
                        candidate, state["available_agents"]
                    )
                }
            except (ValueError, TypeError, KeyError) as error:
                validation_error = str(error)
        return {
            "plan": SupervisorPlan(
                selected_agents=state["available_agents"],
                reason="계획 검증 실패로 실행 가능한 모든 에이전트를 선택한 fallback 계획",
            )
        }

    def validate_plan(state: SupervisorState) -> dict[str, Any]:
        return {
            "plan": validate_selected_agents(
                state["plan"], state["available_agents"]
            )
        }

    def dispatch_agents(state: SupervisorState) -> list[Send]:
        return [
            Send(
                "run_agent",
                {
                    "agent": name,
                    "instruction": state["instruction"],
                    "documents": state["documents"],
                    "conversation": state["conversation"],
                    "context": state["agent_contexts"][name],
                },
            )
            for name in state["plan"].selected_agents
        ]

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
        order = {
            name: index for index, name in enumerate(state["plan"].selected_agents)
        }
        results = sorted(state["agent_results"], key=lambda item: order[item.agent])
        successes = [item for item in results if item.status == "SUCCESS"]
        if not successes:
            return {"final_message": ""}
        try:
            message = model.aggregate(
                instruction=state["instruction"],
                plan=state["plan"],
                results=successes,
            )
        except Exception:
            message = "\n".join(
                f"[{item.agent}] "
                + json.dumps(item.result, ensure_ascii=False, sort_keys=True)
                for item in successes
            )
        return {"final_message": message}

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
