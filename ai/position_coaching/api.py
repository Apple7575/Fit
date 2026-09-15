import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai.jd_coaching.baseline import load_qwen_config
from ai.position_coaching.render import render_position_message
from ai.position_coaching.service import PositionAnalysisService


AI_ROOT = Path(__file__).parents[1]


class PositionDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: str = Field(min_length=1, max_length=100)
    document_type: Literal["SELF_INTRO", "EXPERIENCE"]
    text: str = Field(min_length=1, max_length=50_000)

    @field_validator("document_id", "text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ConversationMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message_id: str = Field(min_length=1, max_length=100)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("message_id", "content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class PositionContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    position_name: str = Field(min_length=1, max_length=200)
    priority_requirements: list[
        Annotated[str, Field(min_length=1, max_length=500)]
    ] = Field(default_factory=list, max_length=20)

    @field_validator("position_name")
    @classmethod
    def reject_blank_position_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("priority_requirements")
    @classmethod
    def reject_blank_priorities(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("priority requirement must not be blank")
        return values


class PositionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rubric_id: Literal["experience-depth-v1"]
    position_context: PositionContextRequest
    documents: list[PositionDocumentRequest] = Field(min_length=1, max_length=21)
    conversation: list[ConversationMessageRequest] = Field(default_factory=list, max_length=20)


@lru_cache(maxsize=1)
def get_position_service() -> PositionAnalysisService:
    env_file = Path(
        os.environ.get("POSITION_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    try:
        config = load_qwen_config(env_file)
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="position Qwen configuration unavailable",
        ) from error
    return PositionAnalysisService(config=config)


app = FastAPI(title="Position Coaching API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness(
    _: Annotated[PositionAnalysisService, Depends(get_position_service)],
) -> dict[str, str]:
    return {"status": "ready"}


@app.post("/internal/analyses")
def create_analysis(
    request: PositionAnalysisRequest,
    service: Annotated[PositionAnalysisService, Depends(get_position_service)],
) -> dict[str, object]:
    try:
        analysis = service.analyze(
            request.rubric_id,
            request.position_context.model_dump(),
            [document.model_dump() for document in request.documents],
            [message.model_dump() for message in request.conversation],
        )
        return {
            "message": render_position_message(analysis),
            "analysis": analysis,
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
