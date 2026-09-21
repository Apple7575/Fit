from __future__ import annotations

import json
import logging
import operator
import os
import time
from collections.abc import Callable, Sequence
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import (
    AgentResult,
    NoAvailableAgentError,
    SupervisorPlan,
    TraceStep,
)
from ai.supervisor.delegation import (
    ANALYSIS_AGENT_NAMES,
    DOCUMENT_FREE_AGENTS,
    extract_needs,
    latest_results,
    select_delegations,
)
from ai.supervisor.evidence import extract_evidence, extract_usage
from ai.supervisor.model import PlanOutputError, SupervisorModel
from ai.supervisor.tools import tool_scope


CLARIFICATION_HEADING = "덧붙여, 더 고치려면 이것을 알려 주세요"


def _with_clarification(message: str, clarification: str) -> str:
    """종합 끝에 글쓰기 담당의 되물음을 붙인다.

    되물음은 사용자가 답해야 답이 나오는 질문이라 묻히면 안 된다. 그렇다고 종합 안에 섞으면
    다른 담당이 낸 답까지 질문처럼 읽힌다. 그래서 종합을 먼저 내고 끝에 따로 세운다.
    """
    text = (message or "").strip()
    tail = (clarification or "").strip()
    if not tail:
        return text
    if not text:
        return tail
    if tail in text:
        # 종합 모델이 이미 같은 말을 적었다. 두 번 쓰지 않는다.
        return text
    return f"{text}\n\n{CLARIFICATION_HEADING}\n{tail}"



class SupervisorState(TypedDict, total=False):
    instruction: str
    documents: list[dict[str, Any]]
    conversation: list[dict[str, Any]]
    agent_contexts: dict[str, dict[str, Any]]
    available_agents: list[str]
    plan: SupervisorPlan
    lead: str | None
    agent_selection: str
    agent_results: Annotated[list[AgentResult], operator.add]
    # 위임: resolve_needs 가 채우고 rerun_requesters 가 소비한다.
    delegation_round: int
    delegations: list[dict[str, str]]
    # 추적: 각 노드가 실행 단계를 덧붙인다. step 번호와 superseded 는 서비스가 마지막에 매긴다.
    trace: Annotated[list[TraceStep], operator.add]
    started_at: float
    final_message: str


class WorkerState(TypedDict, total=False):
    agent: str
    instruction: str
    documents: list[dict[str, Any]]
    conversation: list[dict[str, Any]]
    context: dict[str, Any]
    delegated_from: str | None


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


def success_result(
    agent: str,
    result: dict[str, Any],
    tool_calls: Sequence[Any] = (),
    delegated_from: str | None = None,
) -> AgentResult:
    """담당 결과를 공통 규격으로 감싼다. 근거·사용량·위임 요청은 여기서 한 번만 추출한다."""
    return AgentResult(
        agent=agent,
        status="SUCCESS",
        result=result,
        evidence=extract_evidence(agent, result),
        needs=extract_needs(agent, result)[:4],
        tool_calls=list(tool_calls),
        usage=extract_usage(result),
        delegated_from=delegated_from,
    )


def trace_step(
    phase: str,
    agent: str,
    called_by: str,
    result: AgentResult | None,
    started: float,
    *,
    status: str | None = None,
    note: str | None = None,
) -> TraceStep:
    return TraceStep(
        step=1,  # 서비스가 최종 순서로 다시 매긴다
        phase=phase,
        agent=agent,
        called_by=called_by,
        status=status or (result.status if result is not None else "SUCCESS"),
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        tool_calls=list(result.tool_calls) if result is not None else [],
        evidence_ids=[item.evidence_id for item in result.evidence] if result is not None else [],
        usage=result.usage if result is not None else None,
        note=note if note is not None else (result.error if result is not None else None),
    )


LOGGER = logging.getLogger("ai.supervisor.graph")

DEFAULT_DELEGATION_DEADLINE_SECONDS = 60.0


def delegation_deadline_from_env() -> float:
    """위임 라운드를 시작할 수 있는 요청 경과 시간 상한(초). Spring 타임아웃 120초의 절반."""
    raw = os.environ.get("SUPERVISOR_DELEGATION_DEADLINE_SECONDS", "").strip()
    try:
        value = float(raw) if raw else DEFAULT_DELEGATION_DEADLINE_SECONDS
    except ValueError:
        return DEFAULT_DELEGATION_DEADLINE_SECONDS
    return value if value > 0 else DEFAULT_DELEGATION_DEADLINE_SECONDS


def build_supervisor_graph(
    model: SupervisorModel,
    registry: AgentRegistry,
    *,
    clock: Callable[[], float] = time.monotonic,
    delegation_deadline_seconds: float | None = None,
):
    deadline_seconds = (
        delegation_deadline_seconds
        if delegation_deadline_seconds is not None
        else delegation_deadline_from_env()
    )

    def validate_input(state: SupervisorState) -> dict[str, Any]:
        if not state.get("instruction", "").strip():
            raise ValueError("instruction must not be blank")
        return {"started_at": clock()}

    def resolve_available_agents(state: SupervisorState) -> dict[str, Any]:
        names = registry.available_names(state["agent_contexts"])
        if not names:
            raise NoAvailableAgentError("no agent context was provided")
        if not state.get("documents"):
            # 제출 문서가 없으면 문서 없이 동작하는 담당(뉴스)만 실행할 수 있다.
            names = [name for name in names if name in DOCUMENT_FREE_AGENTS]
            if not names:
                raise NoAvailableAgentError(
                    "documents are required for the available agents"
                )
        return {"available_agents": names}

    def create_plan(state: SupervisorState) -> dict[str, Any]:
        started = time.monotonic()
        lead = state.get("lead")
        if lead:
            # 담당 직접 호출: 계획 모델을 부르지 않고 lead 담당만 선택한다.
            if lead not in state["available_agents"]:
                raise NoAvailableAgentError(f"lead agent is unavailable: {lead}")
            plan = SupervisorPlan(
                selected_agents=[lead], reason=f"lead 모드: {lead} 담당 직접 호출"
            )
            return {"plan": plan, "trace": [plan_trace(plan, "lead", started)]}
        if state.get("agent_selection") == "all":
            # 부르는 쪽이 이미 "전부 봐 달라" 고 정했다. 고를 질문이 없으므로 계획 모델을
            # 부르지 않는다 — 부르면 담당 대부분이 "이 관점은 필요 없다" 로 남는다.
            plan = SupervisorPlan(
                selected_agents=state["available_agents"],
                reason="전원 실행: 부르는 쪽이 담당을 고르지 않는다",
            )
            return {"plan": plan, "trace": [plan_trace(plan, "all", started)]}
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
                plan = validate_selected_agents(candidate, state["available_agents"])
                return {"plan": plan, "trace": [plan_trace(plan, "request", started)]}
            except (ValueError, TypeError, KeyError) as error:
                validation_error = str(error)
        plan = SupervisorPlan(
            selected_agents=state["available_agents"],
            reason="계획 검증 실패로 실행 가능한 모든 에이전트를 선택한 fallback 계획",
        )
        return {"plan": plan, "trace": [plan_trace(plan, "request", started)]}

    def plan_trace(plan: SupervisorPlan, called_by: str, started: float) -> TraceStep:
        return trace_step(
            "plan", "supervisor", called_by, None, started,
            note=f"selected={','.join(plan.selected_agents)}; {plan.reason}"[:1_000],
        )

    def validate_plan(state: SupervisorState) -> dict[str, Any]:
        return {
            "plan": validate_selected_agents(
                state["plan"], state["available_agents"]
            ),
            "delegation_round": 0,
            "delegations": [],
        }

    def selected_analysis_agents(state: SupervisorState) -> list[str]:
        return [
            name
            for name in state["plan"].selected_agents
            if name in ANALYSIS_AGENT_NAMES
        ]

    def should_run_writing(state: SupervisorState) -> bool:
        return "writing" in state["plan"].selected_agents

    def executed_agents(state: SupervisorState) -> set[str]:
        return {item.agent for item in state.get("agent_results", [])}

    def send_analysis(
        state: SupervisorState, name: str, delegated_from: str | None
    ) -> Send:
        return Send(
            "run_analysis_agent",
            {
                "agent": name,
                "instruction": state["instruction"],
                "documents": state["documents"],
                "conversation": state["conversation"],
                "context": state["agent_contexts"][name],
                "delegated_from": delegated_from,
            },
        )

    def dispatch_initial_phase(state: SupervisorState) -> list[Send] | str:
        analysis_agents = selected_analysis_agents(state)
        if analysis_agents:
            return [send_analysis(state, name, None) for name in analysis_agents]
        if should_run_writing(state):
            return "run_writing_agent"
        return "aggregate_results"

    def execute_analysis(
        agent: str,
        state: SupervisorState | WorkerState,
        context: dict[str, Any],
        *,
        delegated_from: str | None,
        prior_results: Sequence[AgentResult] = (),
    ) -> AgentResult:
        with tool_scope(agent) as tool_calls:
            try:
                result = registry.execute(
                    agent,
                    state["instruction"],
                    state["documents"],
                    state["conversation"],
                    context,
                    prior_results=prior_results,
                )
                return success_result(agent, result, tool_calls, delegated_from)
            except Exception as error:
                return AgentResult(
                    agent=agent,
                    status="FAILED",
                    error=f"{type(error).__name__}: {error}",
                    tool_calls=list(tool_calls),
                    delegated_from=delegated_from,
                )

    def run_analysis_agent(state: WorkerState) -> dict[str, Any]:
        started = time.monotonic()
        delegated_from = state.get("delegated_from")
        agent_result = execute_analysis(
            state["agent"],
            state,
            state["context"],
            delegated_from=delegated_from,
        )
        step = trace_step(
            "delegation" if delegated_from else "analysis",
            state["agent"],
            delegated_from or "plan",
            agent_result,
            started,
        )
        return {"agent_results": [agent_result], "trace": [step]}

    def successful_results_except(
        state: SupervisorState, exclude: str
    ) -> list[AgentResult]:
        order = {
            name: index for index, name in enumerate(state["plan"].selected_agents)
        }
        return sorted(
            [
                item
                for item in latest_results(state.get("agent_results", []))
                if item.agent != exclude
                and item.status == "SUCCESS"
                and isinstance(item.result, dict)
            ],
            key=lambda item: order.get(item.agent, len(order)),
        )

    def execute_writing(state: SupervisorState) -> AgentResult:
        with tool_scope("writing") as tool_calls:
            try:
                result = registry.execute(
                    "writing",
                    state["instruction"],
                    state["documents"],
                    state["conversation"],
                    state["agent_contexts"]["writing"],
                    prior_results=successful_results_except(state, "writing"),
                )
                return success_result("writing", result, tool_calls)
            except Exception as error:
                # 응답에는 사유를 가리지만(사용자 문서 유출 방지) 운영 로그에는 원인을 남긴다.
                LOGGER.warning(
                    "writing worker failed: %s: %s (cause: %s)",
                    type(error).__name__, str(error)[:300],
                    f"{type(error.__cause__).__name__}: {str(error.__cause__)[:500]}" if error.__cause__ else "-",
                )
                return AgentResult(
                    agent="writing",
                    status="FAILED",
                    error="writing worker failed",
                    tool_calls=list(tool_calls),
                )

    def run_writing_agent(state: SupervisorState) -> dict[str, Any]:
        started = time.monotonic()
        agent_result = execute_writing(state)
        return {
            "agent_results": [agent_result],
            "trace": [trace_step("writing", "writing", "plan", agent_result, started)],
        }

    def route_after_analysis(state: SupervisorState) -> str:
        if state.get("delegation_round", 0) >= 1:
            return "rerun_requesters"
        if should_run_writing(state):
            return "run_writing_agent"
        return "resolve_needs"

    def after_analysis(_: SupervisorState) -> dict[str, Any]:
        return {}

    def resolve_needs(state: SupervisorState) -> dict[str, Any]:
        delegations = select_delegations(
            latest_results(state.get("agent_results", [])),
            available_agents=state["available_agents"],
            already_run=executed_agents(state),
            round_index=state.get("delegation_round", 0),
        )
        if not delegations:
            return {}
        elapsed = clock() - state.get("started_at", clock())
        if elapsed > deadline_seconds:
            # 시간 예산을 넘긴 요청은 위임을 시작하지 않는다. 요청은 trace 에만 남긴다.
            skipped = ",".join(item["agent"] for item in delegations)
            step = trace_step(
                "delegation", "supervisor", "request", None, clock(),
                status="SKIPPED",
                note=f"budget exceeded ({elapsed:.1f}s > {deadline_seconds:.0f}s): skipped {skipped}",
            )
            return {"trace": [step]}
        return {"delegations": delegations, "delegation_round": 1}

    def dispatch_delegations(state: SupervisorState) -> list[Send] | str:
        delegations = state.get("delegations") or []
        if not delegations:
            return "aggregate_results"
        return [
            send_analysis(state, item["agent"], item["requested_by"])
            for item in delegations
        ]

    def rerun_requesters(state: SupervisorState) -> dict[str, Any]:
        """위임 결과를 받은 요청 담당을 한 번씩 다시 실행한다."""
        requesters: list[str] = []
        for item in state.get("delegations") or []:
            if item["requested_by"] not in requesters:
                requesters.append(item["requested_by"])
        results: list[AgentResult] = []
        steps: list[TraceStep] = []
        for requester in requesters:
            started = time.monotonic()
            if requester == "writing":
                rerun = execute_writing(state)
            else:
                rerun = execute_analysis(
                    requester,
                    state,
                    state["agent_contexts"][requester],
                    delegated_from=None,
                    prior_results=successful_results_except(state, requester),
                )
            # 재실행 결과는 위임 요청을 더 내지 못한다(1홉 제한).
            rerun = rerun.model_copy(update={"needs": []})
            delegated = [
                item["agent"] for item in state.get("delegations") or []
                if item["requested_by"] == requester
            ]
            note = f"after={','.join(delegated)}"
            previous = next(
                (item for item in latest_results(state.get("agent_results", []))
                 if item.agent == requester),
                None,
            )
            if rerun.status == "FAILED" and previous is not None and previous.status == "SUCCESS":
                # 재실행이 실패하면 1차 결과를 그대로 유지한다. 실패는 trace 에만 남긴다.
                note += f"; rerun failed, kept previous result ({rerun.error})"
            else:
                results.append(rerun)
            steps.append(trace_step("rerun", requester, "delegation", rerun, started, note=note))
        return {"agent_results": results, "trace": steps}

    def lead_message(
        state: SupervisorState, lead: str, successes: list[AgentResult]
    ) -> str:
        """lead 담당의 message 를 그대로 쓴다. 없으면 lead 결과만 종합한다."""
        lead_result = next((item for item in successes if item.agent == lead), None)
        if lead_result is None or not isinstance(lead_result.result, dict):
            return ""
        message = lead_result.result.get("message")
        if isinstance(message, str) and message.strip():
            return message
        try:
            return model.aggregate(
                instruction=state["instruction"],
                plan=SupervisorPlan(selected_agents=[lead], reason="lead 모드"),
                results=[lead_result],
            )
        except Exception:
            return json.dumps(lead_result.result, ensure_ascii=False, sort_keys=True)

    def aggregate_results(state: SupervisorState) -> dict[str, Any]:
        started = time.monotonic()
        update = aggregate_message(state)
        used_model = update.pop("_used_model", False)
        step = trace_step(
            "aggregate", "supervisor", "request", None, started,
            status="SUCCESS" if update.get("final_message") else "SKIPPED",
            note="model" if used_model else "passthrough",
        )
        return {**update, "trace": [step]}

    def aggregate_message(state: SupervisorState) -> dict[str, Any]:
        order = {
            name: index for index, name in enumerate(state["plan"].selected_agents)
        }
        results = sorted(
            latest_results(state.get("agent_results", [])),
            key=lambda item: order.get(item.agent, len(order)),
        )
        successes = [item for item in results if item.status == "SUCCESS"]
        if not successes:
            return {"final_message": ""}
        lead = state.get("lead")
        if lead:
            return {"final_message": lead_message(state, lead, successes)}
        writing_result = next(
            (
                item
                for item in successes
                if item.agent == "writing" and isinstance(item.result, dict)
            ),
            None,
        )
        clarification = ""
        if writing_result is not None:
            writing_message = writing_result.result.get("message")
            writing_text = writing_message if isinstance(writing_message, str) else ""
            if len(successes) == 1:
                # 글쓰기 혼자 답했다. 종합할 것이 없으니 그 말을 그대로 쓴다.
                return {"final_message": writing_text}
            if writing_result.result.get("status") == "CLARIFICATION_REQUIRED":
                # 되물음은 답이 아니라 사용자에게 던지는 질문이다. 이것만 내보내면 다른 담당이
                # 낸 답이 묻히므로, 종합을 먼저 내고 끝에 따로 붙인다.
                clarification = writing_text
        try:
            message = model.aggregate(
                instruction=state["instruction"],
                plan=state["plan"],
                results=successes,
            )
            return {
                "final_message": _with_clarification(message, clarification),
                "_used_model": True,
            }
        except Exception:
            message = "\n".join(
                f"[{item.agent}] "
                + json.dumps(item.result, ensure_ascii=False, sort_keys=True)
                for item in successes
            )
        return {"final_message": _with_clarification(message, clarification)}

    builder = StateGraph(SupervisorState)
    builder.add_node("validate_input", validate_input)
    builder.add_node("resolve_available_agents", resolve_available_agents)
    builder.add_node("create_plan", create_plan)
    builder.add_node("validate_plan", validate_plan)
    builder.add_node("run_analysis_agent", run_analysis_agent)
    builder.add_node("after_analysis", after_analysis)
    builder.add_node("run_writing_agent", run_writing_agent)
    builder.add_node("resolve_needs", resolve_needs)
    builder.add_node("rerun_requesters", rerun_requesters)
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
        ["run_writing_agent", "resolve_needs", "rerun_requesters"],
    )
    builder.add_edge("run_writing_agent", "resolve_needs")
    builder.add_conditional_edges(
        "resolve_needs",
        dispatch_delegations,
        ["run_analysis_agent", "aggregate_results"],
    )
    builder.add_edge("rerun_requesters", "aggregate_results")
    builder.add_edge("aggregate_results", END)
    return builder.compile()
