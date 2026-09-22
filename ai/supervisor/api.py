import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from ai.company_analysis.api import get_company_chat_service
from ai.jd_coaching.api import get_analysis_service, get_stateless_chat_service
from ai.jd_coaching.baseline import load_qwen_config
from ai.llm.contracts import QUOTA_ERROR_CODE, QUOTA_USER_MESSAGE, find_quota_error
from ai.llm.priority import BACKGROUND, INTERACTIVE, priority_scope
from ai.news_intelligence.api import get_news_service
from ai.position_coaching.api import get_position_chat_service, get_position_service
from ai.supervisor.adapters import (
    AgentRegistry,
    CompanyAgentAdapter,
    JdAgentAdapter,
    NewsAgentAdapter,
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
from ai.supervisor.tools import instrument_jd_service, instrument_news_service
from ai.writing_coaching.api import get_writing_service


AI_ROOT = Path(__file__).parents[1]


def assemble_supervisor_service(
    supervisor_model: SupervisorModel,
    jd_provider: Callable[[], Any],
    position_provider: Callable[[], Any],
    writing_provider: Callable[[], Any],
    news_provider: Callable[[], Any] | None = None,
    company_provider: Callable[[], Any] | None = None,
    jd_chat_provider: Callable[[], Any] | None = None,
    position_chat_provider: Callable[[], Any] | None = None,
) -> SupervisorService:
    resolved_news_provider = news_provider or get_news_service
    resolved_company_provider = company_provider or get_company_chat_service
    registry = AgentRegistry(
        [
            # 총괄 아래에서 실행되는 담당의 조회는 모두 도구 프록시를 거친다.
            JdAgentAdapter(
                lambda: instrument_jd_service(jd_provider()),
                jd_chat_provider or get_stateless_chat_service,
            ),
            PositionAgentAdapter(
                position_provider,
                position_chat_provider or get_position_chat_service,
            ),
            WritingAgentAdapter(writing_provider),
            NewsAgentAdapter(lambda: instrument_news_service(resolved_news_provider())),
            CompanyAgentAdapter(resolved_company_provider),
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
        news_provider=get_news_service,
        company_provider=get_company_chat_service,
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
            and request.agent_contexts.news is None
            and request.agent_contexts.company is None
        ):
            raise NoAvailableAgentError("no agent context was provided")
        if request.lead is not None and getattr(request.agent_contexts, request.lead) is None:
            raise NoAvailableAgentError(f"lead agent has no context: {request.lead}")
        # agent_selection=all 은 사용자가 묻기 전에 방을 한 바퀴 도는 자동 검토다. GMS 한도가 찼을 때
        # 사용자가 방금 보낸 질문(auto)이 이 요청보다 먼저 나가야 하므로 뒤 순위로 표시한다.
        level = BACKGROUND if request.agent_selection == "all" else INTERACTIVE
        with priority_scope(level):
            return service_provider().run(request)
    except NoAvailableAgentError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "NO_AVAILABLE_AGENT", "message": str(error)},
        ) from error
    except AllAgentsFailedError as error:
        # 전원이 할당량으로 막혔으면 그것은 담당들의 실패가 아니라 한도 문제다. 사용자에게 그렇게 알린다.
        all_quota = all(item.error_code == QUOTA_ERROR_CODE for item in error.results)
        raise HTTPException(
            status_code=502,
            detail={
                "code": QUOTA_ERROR_CODE if all_quota else "ALL_AGENTS_FAILED",
                "message": QUOTA_USER_MESSAGE if all_quota else str(error),
                "agent_results": [item.model_dump() for item in error.results],
            },
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        # 계획·종합 모델 호출이 할당량에 막힌 경우. 담당이 아니라 총괄 자체가 못 돈 것이라 여기로 온다.
        if find_quota_error(error) is not None:
            raise HTTPException(
                status_code=502,
                detail={"code": QUOTA_ERROR_CODE, "message": QUOTA_USER_MESSAGE},
            ) from error
        # 그 밖의 총괄 자체의 실패. 내부 메시지는 노출하지 않는다.
        raise HTTPException(
            status_code=502,
            detail={"code": "SUPERVISOR_FAILED", "message": type(error).__name__},
        ) from error
