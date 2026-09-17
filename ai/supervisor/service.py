from typing import Any, Protocol

from ai.supervisor.contracts import (
    AgentResult,
    AllAgentsFailedError,
    SupervisorPlan,
    SupervisorRunRequest,
    SupervisorRunResponse,
    TraceStep,
)
from ai.supervisor.delegation import latest_results, order_results
from ai.supervisor.evidence import merge_evidence


class InvokableGraph(Protocol):
    def invoke(self, state: dict[str, Any]) -> dict[str, Any]: ...


class SupervisorService:
    def __init__(self, graph: InvokableGraph) -> None:
        self._graph = graph

    def run(self, request: SupervisorRunRequest) -> SupervisorRunResponse:
        state = request.model_dump()
        state["agent_results"] = []
        state["trace"] = []
        output = self._graph.invoke(state)
        plan = SupervisorPlan.model_validate(output["plan"])
        all_results = [AgentResult.model_validate(item) for item in output["agent_results"]]
        # 담당별 마지막 실행만 응답에 싣는다(위임 후 재실행이 이전 결과를 대체).
        results = order_results(latest_results(all_results), plan.selected_agents)
        successes = [item for item in results if item.status == "SUCCESS"]
        if not successes:
            raise AllAgentsFailedError(results)
        status = "SUCCESS" if len(successes) == len(results) else "PARTIAL"
        return SupervisorRunResponse(
            status=status,
            message=output["final_message"],
            plan=plan,
            agent_results=results,
            evidence=merge_evidence(successes),
            lead=request.lead,
            trace=finalize_trace(output.get("trace", [])),
        )


def finalize_trace(steps: list[Any]) -> list[TraceStep]:
    """실행 순서대로 번호를 매기고, 같은 담당의 뒤 실행이 있으면 앞 실행을 superseded 로 표시한다."""
    parsed = [
        item if isinstance(item, TraceStep) else TraceStep.model_validate(item)
        for item in steps
    ]
    later_success: set[str] = set()
    later_any: set[str] = set()
    finalized: list[TraceStep] = []
    for item in reversed(parsed):
        is_agent_step = item.phase in {"analysis", "writing", "delegation", "rerun"}
        # 뒤에 같은 담당의 성공 실행이 있으면 대체된 것. 뒤 실행이 실패만 했다면
        # 이 결과가 성공인 경우 그대로 최종 결과로 남는다(재실행 실패 시 1차 유지).
        superseded = is_agent_step and (
            item.agent in later_success
            or (item.agent in later_any and item.status != "SUCCESS")
        )
        if is_agent_step:
            later_any.add(item.agent)
            if item.status == "SUCCESS":
                later_success.add(item.agent)
        finalized.append(item.model_copy(update={"superseded": superseded}))
    finalized.reverse()
    return [
        item.model_copy(update={"step": index})
        for index, item in enumerate(finalized, start=1)
    ]
