import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from ai.jd_coaching.api import get_analysis_service
from ai.jd_coaching.baseline import load_qwen_config
from ai.position_coaching.api import get_position_service
from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter, PositionAgentAdapter
from ai.supervisor.contracts import (
    AllAgentsFailedError,
    NoAvailableAgentError,
    SupervisorRunRequest,
    SupervisorRunResponse,
)
from ai.supervisor.graph import build_supervisor_graph
from ai.supervisor.model import QwenSupervisorModel
from ai.supervisor.service import SupervisorService


AI_ROOT = Path(__file__).parents[1]


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
    model = QwenSupervisorModel(config)
    registry = AgentRegistry(
        [
            JdAgentAdapter(get_analysis_service()),
            PositionAgentAdapter(get_position_service()),
        ]
    )
    return SupervisorService(build_supervisor_graph(model, registry))


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
