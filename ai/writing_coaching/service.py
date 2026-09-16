from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ai.jd_coaching.baseline import call_qwen

from .contracts import (
    WritingMessageRequest,
    WritingMessageResponse,
    load_writing_rubric,
)
from .prompt import build_writing_messages
from .validation import validate_writing_output


RESOURCE_ROOT = Path(__file__).parent / "resources"
RUBRIC_PATH = RESOURCE_ROOT / "rubrics" / "writing-quality-v1.json"
SCHEMA_PATH = RESOURCE_ROOT / "schemas" / "writing-message-v1.json"
PROMPT_VERSION = "writing-quality-v1"
QWEN_TIMEOUT_SECONDS = 30

QwenCaller = Callable[..., dict[str, Any]]


class WritingProviderError(RuntimeError):
    """A Qwen call failed before output validation; the cause stays internal."""


class WritingService:
    def __init__(
        self,
        config: Mapping[str, str],
        qwen_caller: QwenCaller = call_qwen,
    ) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller

    def respond(self, request: WritingMessageRequest) -> WritingMessageResponse:
        rubric = load_writing_rubric(RUBRIC_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validation_error = None

        for attempt in range(2):
            messages = build_writing_messages(request, rubric, validation_error)
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    timeout_seconds=QWEN_TIMEOUT_SECONDS,
                    schema=schema,
                    schema_name="writing_message_v1",
                )
            except Exception as error:
                raise WritingProviderError("writing provider request failed") from error
            try:
                return validate_writing_output(response["output"], request)
            except (KeyError, TypeError, ValueError) as error:
                validation_error = str(error)
                if attempt == 1:
                    raise RuntimeError(
                        "writing response validation failed"
                    ) from error

        raise RuntimeError("writing response validation failed")
