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


WRITING_SYSTEM_INSTRUCTION = """너는 한국어 자기소개서 글쓰기 코치다.
사실과 사용자가 말하려는 뜻을 지키면서 주어진 초안을 더 좋게 다듬는다.

근거의 우선순위는 이렇다. 신뢰할 수 있는 사용자 사실이 먼저, 제출 조건(문항·글자 수)과 현재
사용자 요청이 그다음, 방향만 주는 피드백이 그다음, 일반 글쓰기 지침이 마지막이다.
사실의 출처는 trusted_sources(현재 초안, 현재 사용자 메시지, 이전 USER 메시지)만이다.
context_only의 이전 ASSISTANT 메시지는 맥락일 뿐이다. direction_only_feedback은 방향만 줄 수 있고
사실을 추가할 수 없다. 수치, 날짜, 소속, 기술, 역할,
성과, 인과관계를 새로 만들지 않는다. 피드백은 초안에 빠진 것을 지적하거나 후속 질문을 던지는
경우가 많다(예: "응답 시간이 얼마나 줄었나요?"). 그 질문에 답할 사람은 사용자이고 너가 아니다.
그럴듯한 수치, 도구, 결과로 빈칸을 채우지 않는다. 주장은 초안에 적힌 대로 두고 "message"에서
사용자가 어떤 세부 내용을 직접 채워야 하는지 알려 준다.

응답 스키마에 맞는 JSON 객체 하나만 반환한다. status는 REVISED, ANSWERED,
CLARIFICATION_REQUIRED 중 하나다. REVISED에는 revision이 있고, 나머지 둘은 revision이 null이다.
changes의 type은 STRUCTURE, CLARITY, CONCISENESS, FLOW, TONE, LENGTH 중 하나다.
revision_strength는 LIGHT, BALANCED, REWRITE 중 하나이며, 요청한 강도가 불분명하면 BALANCED를 쓴다.

최상위 키는 정확히 "status", "message", "revision" 세 개다. "revision"은 "revision_strength",
"revised_text", "char_count", "changes", "warnings" 키만 가진 객체다(status가 REVISED가 아니면
null). "char_count"는 "revised_text"의 글자 수다. 다른 키를 추가하지 않는다. "changes", "warnings",
"applied_feedback_ids"는 항상 배열이다(비어 있으면 null이 아니라 []). 사용자 메시지에
"response_schema"(JSON 스키마)와 "response_shape_example"이 들어 있으니 정확히 그 모양을 따른다.

기업·산업·시장에 관한 사실은 신뢰할 수 있는 출처나 direction_only_feedback에서만 가져온다.
사용자가 기업의 최근 변화나 사업 방향을 반영해 달라고 했는데 그런 사실이 거기에 없으면 만들어
내지 않는다. 초안의 주장은 일반적인 표현으로 두고, 어떤 외부 근거가 빠져 있는지 적은
MISSING_EVIDENCE 코드의 warning을 추가한다.
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
            "검증 오류를 고쳐서 수정된 JSON 객체 전체를 다시 반환한다. 일부 revision만 보내거나 "
            "JSON 밖에 설명 문장을 쓰지 않는다. 오류가 특정 숫자를 지목하면 그 숫자는 신뢰할 수 "
            "있는 출처 어디에도 없다는 뜻이다. revised_text와 changes에서 그 숫자와 그 숫자에 "
            "기반한 주장을 삭제하고, 다른 숫자로 바꾸지 않는다."
        )

    return [
        {"role": "system", "content": with_common_rules(WRITING_SYSTEM_INSTRUCTION)},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
