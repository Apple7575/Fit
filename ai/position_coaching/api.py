import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai.jd_coaching.baseline import load_qwen_config
from ai.position_coaching.chat import PositionChatService
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


class PositionMessageRequest(BaseModel):
    """방에서 사용자가 물은 것. 평가 결과를 들고 와 그 위에서 답한다.

    analysis_result 를 함께 받는 이유는 대화를 저장하지 않기 때문이다. 부르는 쪽이
    직전 분석 결과를 들고 있으므로 다시 평가를 돌릴 이유가 없다 — 45초를 아낀다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=10_000)
    position_context: PositionContextRequest
    documents: list[PositionDocumentRequest] = Field(min_length=1, max_length=21)
    analysis_result: dict[str, object] | None = None
    conversation: list[ConversationMessageRequest] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


@lru_cache(maxsize=1)
def get_position_service() -> PositionAnalysisService:
    env_file = Path(
        os.environ.get("POSITION_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    try:
        config = load_qwen_config(env_file, prefix="POSITION")
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="position Qwen configuration unavailable",
        ) from error
    return PositionAnalysisService(config=config)


@lru_cache(maxsize=1)
def get_position_chat_service() -> PositionChatService:
    env_file = Path(
        os.environ.get("POSITION_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    try:
        config = load_qwen_config(env_file, prefix="POSITION")
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="position Qwen configuration unavailable",
        ) from error
    return PositionChatService(config=config)


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


@app.post("/internal/messages")
def create_message(
    request: PositionMessageRequest,
    service: Annotated[PositionAnalysisService, Depends(get_position_service)],
    chat_service: Annotated[PositionChatService, Depends(get_position_chat_service)],
) -> dict[str, object]:
    position_context = request.position_context.model_dump()
    documents = [document.model_dump() for document in request.documents]
    conversation = [message.model_dump() for message in request.conversation]

    analysis = request.analysis_result
    if analysis is None:
        # 평가 결과를 안 주면 여기서 한 번 돌린다. 근거 없이 답하면 경험에 없는 말을
        # 지어내므로, 느려도 근거를 먼저 만든다.
        try:
            analysis = service.analyze(
                "experience-depth-v1", position_context, documents, conversation
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    try:
        reply = chat_service.respond(
            position_context=position_context,
            analysis_result=analysis,
            documents=documents,
            message=request.message,
            history=conversation,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (KeyError, RuntimeError, TypeError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    # 백엔드 말풍선은 message 를 읽는다. answer 만 주면 성공해도 빈 말풍선이 된다.
    return {"message": reply["answer"], **reply, "analysis": analysis}
