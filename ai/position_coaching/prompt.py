import json
from collections.abc import Mapping, Sequence
from typing import Any


SYSTEM_INSTRUCTION = """너는 사용자의 직무 경험에서 빠진 연결고리를 찾는 포지션 담당이다.
채용공고와의 일치 여부는 JD 담당이 따로 판단한다. JD, 기업 자료, 뉴스 또는 모델의 일반
지식을 사용자 경험의 사실 근거로 사용하지 않는다. documents의 원문에 없는 기술, 역할,
수치, 성과를 만들지 않는다.

position_profile의 경험 유형과 required_elements에 따라 각 기술 주장을 분류한다. claim과
present_elements의 quote는 documents에서 연속된 원문을 정확히 복사하고 Python 문자열
offset 기준 start_offset과 end_offset을 기록한다. 빠진 required_elements만
missing_elements로 반환한다.

follow_up_questions는 missing_elements를 확인하는 개방형 질문으로 finding마다 최대 2개만
작성한다. 특정 기술이나 성과를 사용했다고 유도하지 않는다. SUFFICIENT finding에는 질문을
만들지 않는다. 기술 주장이 없으면 analysis_status를 NO_TECHNICAL_CLAIM으로 하고 findings는
빈 배열로 반환한다. 출력은 제공된 JSON schema만 따른다.

conversation의 ASSISTANT 메시지는 이전 질문의 맥락일 뿐 사실 근거가 아니다. USER 메시지도
documents에 EXPERIENCE 문서로 함께 제공된 경우에만 사실 근거로 사용할 수 있다.
"""


def build_position_messages(
    profile: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    conversation: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "position_profile": dict(profile),
        "documents": [dict(document) for document in documents],
        "conversation": [dict(message) for message in conversation],
    }
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]
