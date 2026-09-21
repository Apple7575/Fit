from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from pydantic import Field

from ai.jd_coaching.baseline import load_qwen_config
from ai.news_intelligence.chat import NewsChatService
from ai.news_intelligence.contracts import (
    NewsAnalysisRequest,
    NewsAnalysisResponse,
    StrictModel,
)
from ai.news_intelligence.model import (
    NewsModelUnavailable,
    NewsOutputError,
    QwenNewsModel,
)
from ai.news_intelligence.repository import (
    CompanyNotFound,
    JobContextNotFound,
    NewsSourceUnavailable,
    PostgresNewsRepository,
)
from ai.news_intelligence.search_provider import GoogleNewsRssProvider
from ai.news_intelligence.service import NewsIntelligenceService
from ai.supervisor.contracts import ConversationMessage


AI_ROOT = Path(__file__).parents[1]


def _news_env_file() -> Path:
    return Path(os.environ.get("NEWS_QWEN_ENV_FILE", str(AI_ROOT / ".env")))


def _required_database_url() -> str:
    value = os.environ.get("JD_DATABASE_URL", "").strip()
    if not value:
        value = _read_env_value(_news_env_file(), "JD_DATABASE_URL")
    if not value:
        raise RuntimeError("JD_DATABASE_URL is required")
    if not value.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("JD_DATABASE_URL must be a PostgreSQL URL")
    return value


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip() == key:
            return value.strip()
    return ""


@lru_cache(maxsize=1)
def get_news_service() -> NewsIntelligenceService:
    try:
        config = load_qwen_config(_news_env_file())
        database_url = _required_database_url()
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "NEWS_CONFIGURATION_UNAVAILABLE"},
        ) from error
    return NewsIntelligenceService(
        repository=PostgresNewsRepository(database_url),
        search_provider=GoogleNewsRssProvider(),
        model=QwenNewsModel(config),
        chat=NewsChatService(config),
    )


class NewsMessageRequest(StrictModel):
    """방에서 사용자가 물은 것. 다른 담당의 `/internal/messages` 와 이름을 맞춘다.

    뉴스는 분석과 대화가 한 호출 안에서 이어지므로(신호를 뽑고 그 위에서 답한다) 몸체는
    분석 요청과 같다. `message` 가 곧 `instruction` 이다.
    """

    message: str = Field(min_length=1, max_length=10_000)
    job_context_id: str = Field(min_length=1, max_length=80)
    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)


app = FastAPI(title="News Intelligence API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness(
    _: Annotated[NewsIntelligenceService, Depends(get_news_service)],
) -> dict[str, str]:
    return {"status": "ready"}


@app.post("/internal/messages")
def create_message(
    request: NewsMessageRequest,
    service: Annotated[NewsIntelligenceService, Depends(get_news_service)],
) -> NewsAnalysisResponse:
    return create_analysis(
        NewsAnalysisRequest(
            instruction=request.message,
            job_context_id=request.job_context_id,
            corp_code=request.corp_code,
            conversation=request.conversation,
        ),
        service,
    )


@app.post("/internal/analyses")
def create_analysis(
    request: NewsAnalysisRequest,
    service: Annotated[NewsIntelligenceService, Depends(get_news_service)],
) -> NewsAnalysisResponse:
    try:
        return service.analyze(request)
    except JobContextNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_CONTEXT_NOT_FOUND"},
        ) from error
    except CompanyNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "COMPANY_NOT_FOUND"},
        ) from error
    except NewsSourceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "NEWS_SOURCE_UNAVAILABLE"},
        ) from error
    except (NewsOutputError, NewsModelUnavailable) as error:
        raise HTTPException(
            status_code=502,
            detail={"code": "NEWS_MODEL_UNAVAILABLE"},
        ) from error
