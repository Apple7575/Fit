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
# 실측 생성 시간이 약 19초라 모델 서버가 동시 요청으로 느려지면 30초를 넘겼다.
QWEN_TIMEOUT_SECONDS = 45

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
                return validate_writing_output(_normalize_output(response["output"], request), request)
            except (KeyError, TypeError, ValueError) as error:
                validation_error = str(error)
                if attempt == 1:
                    raise RuntimeError(
                        "writing response validation failed"
                    ) from error

        raise RuntimeError("writing response validation failed")


def _normalize_output(output: object, request: WritingMessageRequest | None = None) -> object:
    """모델의 흔한 형식 실수를 검증 전에 바로잡는다.

    - 빈 배열 자리에 null 을 넣는다 → [] 로.
    - 받은 피드백에 없는 feedback_id 를 applied_feedback_ids 에 지어 넣는다(특히 피드백이 하나도
      없는 전담 방에서 gemini-2.5-flash 가 그랬다) → 아는 id 만 남긴다. 어떤 피드백을 반영했다는
      표시일 뿐 문장 내용에는 영향이 없어, 거절해 턴 전체를 실패시키는 것보다 낫다.
    """
    if not isinstance(output, dict):
        return output
    known_ids = {item.feedback_id for item in request.feedback} if request is not None else None
    revision = output.get("revision")
    if isinstance(revision, dict):
        for key in ("changes", "warnings"):
            if revision.get(key) is None:
                revision[key] = []
        for change in revision.get("changes") or []:
            if not isinstance(change, dict):
                continue
            ids = change.get("applied_feedback_ids")
            if ids is None:
                change["applied_feedback_ids"] = []
            elif known_ids is not None and isinstance(ids, list):
                change["applied_feedback_ids"] = [item for item in ids if item in known_ids]
    return output
