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
