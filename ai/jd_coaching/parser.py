from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def build_extraction_messages(
    company_name: str, position_name: str, jd_text: str
) -> list[dict[str, str]]:
    system_prompt = """
너는 채용공고 원문에서 지원자 경험과 비교할 직무 요구사항을 추출한다.
공고에 명시된 직무, 자격요건, 우대사항만 추출한다.
한 문장에 서로 독립적으로 평가할 요구사항이 있으면 각각 나눈다.
단, 쉼표나 슬래시로 나열된 기술 대안은 하나의 요구사항으로 유지한다.
source_quote는 입력 JD에 실제로 존재하는 연속된 원문을 정확히 복사한다.
기업에 대한 일반 지식이나 JD에 없는 자격을 추가하지 않는다.
중복 요구사항을 만들지 말고 핵심 요구사항을 최대 8개까지만 반환한다.
이 단계에서는 필요 근거나 연결 라벨을 만들지 않는다.
""".strip()
    payload = {
        "company_name": company_name,
        "position_name": position_name,
        "jd_text": jd_text,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def extraction_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["role_elements"],
        "properties": {
            "role_elements": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "source_quote"],
                    "properties": {
                        "name": {"type": "string"},
                        "source_quote": {"type": "string"},
                    },
                },
            }
        },
    }


def build_evidence_decomposition_messages(
    role: Mapping[str, Any],
) -> list[dict[str, str]]:
    system_prompt = """
너는 JD 요구사항 하나를 지원자 경험에서 확인할 수 있는 최소 근거로 분해한다.
근거는 제공된 요구사항 원문의 의미 요소만 사용하며 1~3개로 제한한다.
JD가 명시하지 않았다면 배포, 최적화, 오류 처리, 협업, 정량 성과를 추가하지 않는다.
"역량"이나 "경험"만 요구하면 관련 대상이나 기술을 실제 행동에 사용한 근거까지만 요구한다.
쉼표, 슬래시, "등", "하나 이상"으로 나열된 기술은 대안으로 묶는다.
대안 중 하나를 사용했는지는 하나의 evidence_requirement로 표현한다.
문장에 "그리고"로 연결된 조건은 각각 필요하므로 evidence_logic은 ALL이다.
문장 전체가 "또는"으로 연결된 대체 조건이면 evidence_logic은 ANY이다.
**evidence_logic이 ANY이면 evidence_requirements는 반드시 정확히 1개다.** 대체 조건을
여러 개로 쪼개지 말고, "둘 중 하나에 해당하는지"를 묻는 근거 하나로 합쳐라.
근거를 2개 이상 만들어야 한다면 evidence_logic은 ALL이다.
요구사항의 동사와 대상이 필요 근거에서 사라지지 않게 한다.
""".strip()
    payload = {
        "role_element_id": role["role_element_id"],
        "name": role["name"],
        "source_quote": role["source_quote"],
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def evidence_decomposition_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_logic", "evidence_requirements"],
        "properties": {
            "evidence_logic": {
                "type": "string",
                "enum": ["ALL", "ANY"],
                # 제약을 필드 옆에 적는다. 프롬프트 본문보다 여기를 더 잘 지키는 모델이 있다.
                "description": "근거를 모두 만족해야 하면 ALL. 대체 조건이면 ANY이며, 이때 evidence_requirements는 반드시 1개다.",
            },
            "evidence_requirements": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "description": "1~3개. evidence_logic이 ANY이면 정확히 1개여야 한다.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description"],
                    "properties": {"description": {"type": "string"}},
                },
            },
        },
    }


def normalize_role_elements(
    output: Mapping[str, Any], jd_text: str
) -> list[dict[str, Any]]:
    raw_roles = output.get("role_elements")
    if not isinstance(raw_roles, list) or not 1 <= len(raw_roles) <= 8:
        raise ValueError("role_elements must contain 1 to 8 items")

    roles = []
    seen: set[tuple[str, str]] = set()
    for role_index, raw_role in enumerate(raw_roles, start=1):
        if not isinstance(raw_role, Mapping):
            raise ValueError("role_element must be an object")
        name = _non_empty_text(raw_role.get("name"), "name")
        source_quote = _non_empty_text(
            raw_role.get("source_quote"), "source_quote"
        )
        source_quote = _resolve_source_quote(jd_text, source_quote)
        if source_quote is None:
            raise ValueError("source_quote must occur in jd_text")
        if name in jd_text:
            source_quote = name
        identity = (name, source_quote)
        if identity in seen:
            raise ValueError("duplicate role_element")
        seen.add(identity)
        roles.append(
            {
                "role_element_id": f"role-{role_index:03d}",
                "name": name,
                "source_quote": source_quote,
                "evidence_section_ids": [f"jd-role-{role_index:03d}"],
            }
        )
    return roles


def _resolve_source_quote(jd_text: str, requested_quote: str) -> str | None:
    if requested_quote in jd_text:
        return requested_quote

    normalized_source, source_positions = _normalize_quote_with_positions(jd_text)
    normalized_quote, _ = _normalize_quote_with_positions(requested_quote)
    if len(normalized_quote) < 12:
        return None
    match_start = normalized_source.find(normalized_quote)
    if match_start < 0 or normalized_source.find(
        normalized_quote, match_start + 1
    ) >= 0:
        return None
    match_end = match_start + len(normalized_quote) - 1
    return jd_text[source_positions[match_start] : source_positions[match_end] + 1]


def _normalize_quote_with_positions(value: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    positions: list[int] = []
    at_line_start = True
    for index, character in enumerate(value):
        if character == "\n":
            at_line_start = True
            continue
        if character.isspace():
            continue
        if at_line_start and character in {"-", "·", "•", "▪", "●"}:
            at_line_start = False
            continue
        at_line_start = False
        characters.append(character)
        positions.append(index)
    return "".join(characters), positions


def normalize_evidence_requirements(
    role: Mapping[str, Any], output: Mapping[str, Any]
) -> dict[str, Any]:
    evidence_logic = output.get("evidence_logic")
    if evidence_logic not in {"ALL", "ANY"}:
        raise ValueError("evidence_logic must be ALL or ANY")
    raw_requirements = output.get("evidence_requirements")
    if not isinstance(raw_requirements, list) or not 1 <= len(raw_requirements) <= 3:
        raise ValueError("evidence_requirements must contain 1 to 3 items")
    if evidence_logic == "ANY" and len(raw_requirements) != 1:
        raise ValueError("ANY role must contain exactly one evidence requirement")

    normalized = deepcopy(dict(role))
    requirements = []
    descriptions: set[str] = set()
    for index, raw_requirement in enumerate(raw_requirements, start=1):
        if not isinstance(raw_requirement, Mapping):
            raise ValueError("evidence_requirement must be an object")
        description = _non_empty_text(
            raw_requirement.get("description"), "description"
        )
        if description in descriptions:
            raise ValueError("duplicate evidence requirement")
        descriptions.add(description)
        requirements.append(
            {
                "evidence_requirement_id": (
                    f"{role['role_element_id']}-evidence-{index:03d}"
                ),
                "description": description,
            }
        )
    normalized["evidence_logic"] = evidence_logic
    normalized["evidence_requirements"] = requirements
    return normalized


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()
