from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ai.jd_coaching.baseline import load_qwen_config

from .contracts import WritingMessageRequest, WritingMessageResponse
from .service import WritingService


AI_ROOT = Path(__file__).parents[1]


@lru_cache(maxsize=1)
def get_writing_service() -> WritingService:
    env_file = Path(
        os.environ.get("WRITING_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    try:
        return WritingService(load_qwen_config(env_file, prefix="WRITING"))
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="writing Qwen configuration unavailable",
        ) from error


app = FastAPI(title="Writing Coaching API")


_SAFE_VALIDATION_CONTEXT_KEYS = {
    "actual_length",
    "ge",
    "gt",
    "le",
    "lt",
    "max_length",
    "min_length",
    "multiple_of",
}


def _safe_validation_details(error: RequestValidationError) -> list[dict[str, object]]:
    """Keep useful schema metadata while dropping Pydantic's raw ``input`` field."""
    details: list[dict[str, object]] = []
    for item in error.errors():
        detail: dict[str, object] = {
            "type": item.get("type", "value_error"),
            "loc": list(item.get("loc", ())),
            "msg": item.get("msg", "Invalid request"),
        }
        context = item.get("ctx")
        if isinstance(context, dict):
            safe_context = {
                key: value
                for key, value in context.items()
                if key in _SAFE_VALIDATION_CONTEXT_KEYS
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            }
            if safe_context:
                detail["ctx"] = safe_context
        details.append(detail)
    return details


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": _safe_validation_details(error)},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness(
    _: Annotated[WritingService, Depends(get_writing_service)],
) -> dict[str, str]:
    return {"status": "ready"}


@app.post("/internal/messages", response_model=WritingMessageResponse)
def create_message(
    request: WritingMessageRequest,
    service: Annotated[WritingService, Depends(get_writing_service)],
) -> WritingMessageResponse:
    try:
        return service.respond(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid writing request") from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail="writing generation failed") from error
