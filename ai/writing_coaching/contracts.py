from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CANONICAL_DIMENSIONS = (
    "QUESTION_FIT",
    "CORE_MESSAGE",
    "EVIDENCE",
    "AGENCY",
    "JOB_RELEVANCE",
    "READABILITY",
    "CREDIBILITY",
    "CONSTRAINTS",
)
CANONICAL_CHANGE_TYPES = {
    "STRUCTURE",
    "CLARITY",
    "CONCISENESS",
    "FLOW",
    "TONE",
    "LENGTH",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WritingFeedback(StrictModel):
    feedback_id: str = Field(min_length=1, max_length=100)
    source: Literal["jd", "position", "supervisor"]
    content: str = Field(min_length=1, max_length=2_000)


class WritingConversationMessage(StrictModel):
    message_id: str = Field(min_length=1, max_length=100)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=10_000)


class WritingMessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=10_000)
    question: str = Field(min_length=1, max_length=500)
    draft: str = Field(min_length=1, max_length=50_000)
    char_limit: int = Field(strict=True, ge=1, le=50_000)
    feedback: list[WritingFeedback] = Field(default_factory=list, max_length=20)
    conversation: list[WritingConversationMessage] = Field(
        default_factory=list, max_length=20
    )

    @model_validator(mode="after")
    def validate_unique_ids(self) -> WritingMessageRequest:
        feedback_ids = [item.feedback_id for item in self.feedback]
        if len(feedback_ids) != len(set(feedback_ids)):
            raise ValueError("feedback_id values must be unique")
        message_ids = [item.message_id for item in self.conversation]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("message_id values must be unique")
        return self


class WritingChange(StrictModel):
    type: Literal["STRUCTURE", "CLARITY", "CONCISENESS", "FLOW", "TONE", "LENGTH"]
    before: str = Field(min_length=1, max_length=2_000)
    after: str = Field(min_length=1, max_length=2_000)
    reason: str = Field(min_length=1, max_length=1_000)
    applied_feedback_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("applied_feedback_ids")
    @classmethod
    def validate_feedback_id_text(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("applied_feedback_ids values must be non-blank")
        return values

    @model_validator(mode="after")
    def validate_unique_feedback_ids(self) -> WritingChange:
        if len(self.applied_feedback_ids) != len(set(self.applied_feedback_ids)):
            raise ValueError("applied_feedback_ids values must be unique")
        return self


class WritingWarning(StrictModel):
    code: Literal[
        "MISSING_EVIDENCE", "UNAPPLIED_FEEDBACK",
        "CHAR_LIMIT_CONFLICT", "AMBIGUOUS_INSTRUCTION",
    ]
    message: str = Field(min_length=1, max_length=1_000)


class WritingRevision(StrictModel):
    revision_strength: Literal["LIGHT", "BALANCED", "REWRITE"]
    revised_text: str = Field(min_length=1, max_length=50_000)
    char_count: int = Field(ge=1, le=50_000)
    changes: list[WritingChange] = Field(default_factory=list, max_length=12)
    warnings: list[WritingWarning] = Field(default_factory=list, max_length=10)


class WritingMessageResponse(StrictModel):
    status: Literal["REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"]
    message: str = Field(min_length=1, max_length=2_000)
    revision: WritingRevision | None

    @model_validator(mode="after")
    def validate_status_payload(self) -> WritingMessageResponse:
        if (self.status == "REVISED") != (self.revision is not None):
            raise ValueError("revision must exist exactly when status is REVISED")
        return self


def load_writing_rubric(path: Path) -> dict[str, Any]:
    try:
        rubric = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read writing rubric: {path}") from exc

    if not isinstance(rubric, dict):
        raise ValueError("writing rubric must be an object")
    if rubric.get("id") != "writing-quality-v1":
        raise ValueError("unsupported writing rubric id")
    if type(rubric.get("version")) is not int or rubric["version"] != 1:
        raise ValueError("unsupported writing rubric version")

    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, list) or dimensions != list(CANONICAL_DIMENSIONS):
        raise ValueError("dimensions must match canonical order without duplicates")

    change_types = rubric.get("change_types")
    if not isinstance(change_types, list) or any(
        change_type not in CANONICAL_CHANGE_TYPES for change_type in change_types
    ):
        raise ValueError("change_types contains an unknown type")
    if rubric.get("default_revision_strength") != "BALANCED":
        raise ValueError("default_revision_strength must be BALANCED")
    return rubric
