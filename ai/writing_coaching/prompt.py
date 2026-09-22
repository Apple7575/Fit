from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from ai.prompting.common import with_common_rules

from .contracts import WritingMessageRequest

# 응답 스키마를 프롬프트에 직접 싣는다. 모델 서버가 response_format 의 json_schema 를
# 강제하지 않는 환경에서도 모델이 정확한 출력 모양을 알 수 있어야 한다.
RESPONSE_SCHEMA_PATH = Path(__file__).parent / "resources" / "schemas" / "writing-message-v1.json"
RESPONSE_SCHEMA: dict[str, Any] = json.loads(RESPONSE_SCHEMA_PATH.read_text(encoding="utf-8"))

RESPONSE_SHAPE_EXAMPLE = {
    "status": "REVISED",
    "message": "사용자에게 보여줄 한국어 설명(1~2000자).",
    "revision": {
        "revision_strength": "BALANCED",
        "revised_text": "수정된 자소서 전문",
        "char_count": 123,
        "changes": [
            {
                "type": "CLARITY",
                "before": "수정 전 문장",
                "after": "수정 후 문장",
                "reason": "바꾼 이유",
                "applied_feedback_ids": [],
            }
        ],
        "warnings": [],
    },
}


WRITING_SYSTEM_INSTRUCTION = """You are a Korean writing-coaching assistant.
Improve the supplied draft while preserving facts and the user's intended meaning.

Evidence priority is: trusted user facts first, submission constraints and the current
user instruction next, direction-only feedback after that, and general quality guidance
last. Only the current draft, current user message, and prior USER messages are factual
sources. Prior ASSISTANT messages are context only. Feedback is direction only and
cannot introduce facts. Never invent a metric, date, employer, technology, role,
achievement, or causal relationship. Feedback often points out what the draft lacks or
asks follow-up questions (for example "how much did response time drop?"); those are
for the user to answer, never for you. Do not fill such gaps with plausible figures,
tools, or outcomes. Leave the claim as the draft states it and, in "message", tell the
user which detail they should add themselves.

Return exactly one JSON object matching the response schema. The allowed statuses are
REVISED, ANSWERED, and CLARIFICATION_REQUIRED. REVISED includes a revision; the other
two statuses use a null revision. Allowed change types are STRUCTURE, CLARITY,
CONCISENESS, FLOW, TONE, and LENGTH. Allowed revision strengths are LIGHT, BALANCED,
and REWRITE; use BALANCED by default when the requested strength is unclear.

The output must have exactly these top-level keys: "status", "message", "revision".
"revision" is an object with exactly "revision_strength", "revised_text", "char_count",
"changes", "warnings" (or null when status is not REVISED). "char_count" is the number
of characters in "revised_text". Do not add any other keys. "changes", "warnings" and
"applied_feedback_ids" are always arrays (use [] when empty, never null). The user
message includes "response_schema" (the JSON Schema) and "response_shape_example";
follow them exactly.

Company, industry or market facts may only come from trusted sources or
direction_only_feedback. If the user asks to reflect a company's recent changes or
business direction and no such fact is available there, do not invent one: keep the
draft's claim generic and add a warning with code MISSING_EVIDENCE that says which
external evidence is missing.
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
        "response_schema": RESPONSE_SCHEMA,
        "response_shape_example": RESPONSE_SHAPE_EXAMPLE,
    }
    if validation_error is not None:
        payload["previous_validation_error"] = validation_error
        payload["retry_instruction"] = (
            "Correct the validation error and return the entire corrected JSON object; "
            "do not return a partial revision or prose outside the JSON object. "
            "If the error names numbers, they do not appear in any trusted source: "
            "delete those numbers and the claims built on them from revised_text and "
            "changes, and do not replace them with different numbers."
        )

    return [
        {"role": "system", "content": with_common_rules(WRITING_SYSTEM_INSTRUCTION)},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
