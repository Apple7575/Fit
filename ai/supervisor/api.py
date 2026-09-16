import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from ai.jd_coaching.api import get_analysis_service
from ai.jd_coaching.baseline import load_qwen_config
from ai.position_coaching.api import get_position_service
from ai.supervisor.adapters import (
    AgentRegistry,
    JdAgentAdapter,
    PositionAgentAdapter,
    WritingAgentAdapter,
)
from ai.supervisor.contracts import (
    AllAgentsFailedError,
    NoAvailableAgentError,
    SupervisorRunRequest,
    SupervisorRunResponse,
)
from ai.supervisor.graph import build_supervisor_graph
from ai.supervisor.model import QwenSupervisorModel, SupervisorModel
from ai.supervisor.service import SupervisorService
from ai.writing_coaching.api import get_writing_service


AI_ROOT = Path(__file__).parents[1]


def assemble_supervisor_service(
    supervisor_model: SupervisorModel,
    jd_provider: Callable[[], Any],
    position_provider: Callable[[], Any],
    writing_provider: Callable[[], Any],
) -> SupervisorService:
    registry = AgentRegistry(
        [
            JdAgentAdapter(jd_provider),
            PositionAgentAdapter(position_provider),
            WritingAgentAdapter(writing_provider),
        ]
    )
    return SupervisorService(build_supervisor_graph(supervisor_model, registry))


@lru_cache(maxsize=1)
def get_supervisor_service() -> SupervisorService:
    env_file = Path(
        os.environ.get("SUPERVISOR_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    try:
        config = load_qwen_config(env_file)
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="supervisor Qwen configuration unavailable",
        ) from error
    return assemble_supervisor_service(
        supervisor_model=QwenSupervisorModel(config),
        jd_provider=get_analysis_service,
        position_provider=get_position_service,
        writing_provider=get_writing_service,
    )


def get_supervisor_service_provider() -> Callable[[], SupervisorService]:
    return get_supervisor_service


app = FastAPI(title="Supervisor API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/runs", response_model=SupervisorRunResponse)
def create_run(
    request: SupervisorRunRequest,
    service_provider: Annotated[
        Callable[[], SupervisorService], Depends(get_supervisor_service_provider)
    ],
) -> SupervisorRunResponse:
    try:
        if (
            request.agent_contexts.jd is None
            and request.agent_contexts.position is None
            and request.agent_contexts.writing is None
        ):
            raise NoAvailableAgentError("no agent context was provided")
        return service_provider().run(request)
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
