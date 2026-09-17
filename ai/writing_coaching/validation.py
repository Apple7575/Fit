from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .contracts import WritingMessageRequest, WritingMessageResponse


# Keep numeric facts in their written unit. This deliberately does not parse or
# translate Korean number words, which are not deterministic numeric evidence.
_NUMERIC_FACT_PATTERN = re.compile(
    r"(?<![\dA-Za-z])"
    r"(?P<number>\d(?:[\d,]*\d)?(?:\s*\.\s*\d(?:[\d,]*\d)?)?)"
    r"(?P<unit>\s*(?:%|퍼센트|시간|개월?|년|월|일|명|개|배|초|분))?"
)
_COMMA_WHITESPACE_PATTERN = re.compile(r"\s*,\s*")


def extract_numeric_facts(text: str) -> set[str]:
    """Return normalized Arabic-number facts, preserving their units."""
    facts: set[str] = set()
    normalized_text = _COMMA_WHITESPACE_PATTERN.sub(",", text)
    for match in _NUMERIC_FACT_PATTERN.finditer(normalized_text):
        number = re.sub(r"[\s,]", "", match.group("number"))
        unit = (match.group("unit") or "").strip()
        facts.add(number + unit)
    return facts


def trusted_fact_texts(request: WritingMessageRequest) -> list[str]:
    return [
        request.draft,
        request.message,
        *[
            item.content
            for item in request.conversation
            if item.role == "USER"
        ],
        # jd/position feedback is advisory (suggested actions), not a verified fact —
        # only news feedback quotes real article evidence and can carry trusted numbers.
        *[item.content for item in request.feedback if item.source == "news"],
    ]


def validate_writing_output(
    output: Mapping[str, Any], request: WritingMessageRequest
) -> WritingMessageResponse:
    """Validate model output and enforce constraints that Pydantic cannot express."""
    response = WritingMessageResponse.model_validate(output)
    if response.status != "REVISED":
        return response

    # WritingMessageResponse's cross-field validator guarantees this for REVISED.
    revision = response.revision
    assert revision is not None
    if len(revision.revised_text) > request.char_limit:
        raise ValueError("revised_text exceeds char_limit")

    for change in revision.changes:
        if change.before not in request.draft:
            raise ValueError("change before must occur in draft")
        if change.after not in revision.revised_text:
            raise ValueError("change after must occur in revised_text")

    known_ids = {item.feedback_id for item in request.feedback}
    used_ids = {
        feedback_id
        for change in revision.changes
        for feedback_id in change.applied_feedback_ids
    }
    if not used_ids <= known_ids:
        raise ValueError("applied_feedback_ids contains unknown feedback_id")

    trusted_numbers: set[str] = set()
    for text in trusted_fact_texts(request):
        trusted_numbers.update(extract_numeric_facts(text))
    untrusted_numbers = extract_numeric_facts(revision.revised_text) - trusted_numbers
    if untrusted_numbers:
        # 어떤 숫자가 문제인지 알려야 재시도 프롬프트와 운영 로그에서 바로잡을 수 있다.
        raise ValueError(
            "revised_text contains untrusted numeric fact: "
            + ", ".join(sorted(untrusted_numbers))
        )

    revision.char_count = len(revision.revised_text)
    return response
