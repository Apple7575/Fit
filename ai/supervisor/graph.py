from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import AgentResult, NoAvailableAgentError, SupervisorPlan
from ai.supervisor.model import PlanOutputError, SupervisorModel


ANALYSIS_AGENT_NAMES = {"jd", "position"}


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

    def selected_analysis_agents(state: SupervisorState) -> list[str]:
        return [
            name
            for name in state["plan"].selected_agents
            if name in ANALYSIS_AGENT_NAMES
        ]

    def should_run_writing(state: SupervisorState) -> bool:
        return "writing" in state["plan"].selected_agents

    def dispatch_initial_phase(state: SupervisorState) -> list[Send] | str:
        analysis_agents = selected_analysis_agents(state)
        if analysis_agents:
            return [
                Send(
                    "run_analysis_agent",
                    {
                        "agent": name,
                        "instruction": state["instruction"],
                        "documents": state["documents"],
                        "conversation": state["conversation"],
                        "context": state["agent_contexts"][name],
                    },
                )
                for name in analysis_agents
            ]
        if should_run_writing(state):
            return "run_writing_agent"
        return "aggregate_results"

    def run_analysis_agent(state: WorkerState) -> dict[str, Any]:
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

    def successful_analysis_results(state: SupervisorState) -> list[AgentResult]:
        order = {
            name: index for index, name in enumerate(state["plan"].selected_agents)
        }
        return sorted(
            [
                item
                for item in state.get("agent_results", [])
                if item.agent in ANALYSIS_AGENT_NAMES
                and item.status == "SUCCESS"
                and isinstance(item.result, dict)
            ],
            key=lambda item: order[item.agent],
        )

    def run_writing_agent(state: SupervisorState) -> dict[str, Any]:
        try:
            result = registry.execute(
                "writing",
                state["instruction"],
                state["documents"],
                state["conversation"],
                state["agent_contexts"]["writing"],
                prior_results=successful_analysis_results(state),
            )
            agent_result = AgentResult(
                agent="writing", status="SUCCESS", result=result
            )
        except Exception:
            agent_result = AgentResult(
                agent="writing",
                status="FAILED",
                error="writing worker failed",
            )
        return {"agent_results": [agent_result]}

    def route_after_analysis(state: SupervisorState) -> str:
        if should_run_writing(state):
            return "run_writing_agent"
        return "aggregate_results"

    def after_analysis(_: SupervisorState) -> dict[str, Any]:
        return {}

    def aggregate_results(state: SupervisorState) -> dict[str, Any]:
        order = {
            name: index for index, name in enumerate(state["plan"].selected_agents)
        }
        results = sorted(
            state.get("agent_results", []), key=lambda item: order[item.agent]
        )
        successes = [item for item in results if item.status == "SUCCESS"]
        if not successes:
            return {"final_message": ""}
        writing_result = next(
            (
                item
                for item in successes
                if item.agent == "writing" and isinstance(item.result, dict)
            ),
            None,
        )
        if writing_result is not None:
            writing_message = writing_result.result.get("message")
            if writing_result.result.get("status") == "CLARIFICATION_REQUIRED":
                return {
                    "final_message": (
                        writing_message if isinstance(writing_message, str) else ""
                    )
                }
            if len(successes) == 1:
                return {
                    "final_message": (
                        writing_message if isinstance(writing_message, str) else ""
                    )
                }
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
    builder.add_node("run_analysis_agent", run_analysis_agent)
    builder.add_node("after_analysis", after_analysis)
    builder.add_node("run_writing_agent", run_writing_agent)
    builder.add_node("aggregate_results", aggregate_results)
    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "resolve_available_agents")
    builder.add_edge("resolve_available_agents", "create_plan")
    builder.add_edge("create_plan", "validate_plan")
    builder.add_conditional_edges(
        "validate_plan",
        dispatch_initial_phase,
        ["run_analysis_agent", "run_writing_agent", "aggregate_results"],
    )
    builder.add_edge("run_analysis_agent", "after_analysis")
    builder.add_conditional_edges(
        "after_analysis",
        route_after_analysis,
        ["run_writing_agent", "aggregate_results"],
    )
    builder.add_edge("run_writing_agent", "aggregate_results")
    builder.add_edge("aggregate_results", END)
    return builder.compile()
