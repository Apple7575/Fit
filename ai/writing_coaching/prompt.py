from __future__ import annotations

import json
from typing import Any, Mapping

from .contracts import WritingMessageRequest


WRITING_SYSTEM_INSTRUCTION = """You are a Korean writing-coaching assistant.
Improve the supplied draft while preserving facts and the user's intended meaning.

Evidence priority is: trusted user facts first, submission constraints and the current
user instruction next, direction-only feedback after that, and general quality guidance
last. Only the current draft, current user message, and prior USER messages are factual
sources. Prior ASSISTANT messages are context only. Feedback is direction only and
cannot introduce facts. Never invent a metric, date, employer, technology, role,
achievement, or causal relationship.

Return exactly one JSON object matching the response schema. The allowed statuses are
REVISED, ANSWERED, and CLARIFICATION_REQUIRED. REVISED includes a revision; the other
two statuses use a null revision. Allowed change types are STRUCTURE, CLARITY,
CONCISENESS, FLOW, TONE, and LENGTH. Allowed revision strengths are LIGHT, BALANCED,
and REWRITE; use BALANCED by default when the requested strength is unclear.
"""


def build_writing_messages(
    request: WritingMessageRequest,
    rubric: Mapping[str, Any],
    validation_error: str | None = None,
) -> list[dict[str, str]]:
    """Build two messages while keeping factual and non-factual input zones explicit."""
    trusted_user_messages = [
        item.model_dump() for item in request.conversation if item.role == "USER"
    ]
    context_assistant_messages = [
        item.model_dump() for item in request.conversation if item.role == "ASSISTANT"
    ]
    payload: dict[str, Any] = {
        "question": request.question,
        "char_limit": request.char_limit,
        "trusted_sources": {
            "current_draft": request.draft,
            "current_message": request.message,
            "prior_user_messages": trusted_user_messages,
        },
        "context_only": {
            "prior_assistant_messages": context_assistant_messages,
        },
        "direction_only_feedback": [item.model_dump() for item in request.feedback],
        "rubric": dict(rubric),
    }
    if validation_error is not None:
        payload["previous_validation_error"] = validation_error
        payload["retry_instruction"] = (
            "Correct the validation error and return the entire corrected JSON object; "
            "do not return a partial revision or prose outside the JSON object."
        )

    return [
        {"role": "system", "content": WRITING_SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
