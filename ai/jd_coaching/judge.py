from __future__ import annotations

import json
from ai.prompting.common import with_common_rules
from collections.abc import Mapping
from copy import deepcopy
from typing import Any


EVIDENCE_STATUSES = {"PRESENT", "ABSENT"}


def select_relevant_document_sections(
    document: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    referenced_ids = {
        section_id
        for role in case["expected_role_elements"]
        for section_id in role["evidence_section_ids"]
    }
    available_ids = {
        section["section_id"] for section in document["sections"]
    }
    missing = referenced_ids - available_ids
    if missing:
        raise ValueError(
            f"JD document에 없는 evidence section: {sorted(missing)}"
        )
    selected = deepcopy(dict(document))
    selected["sections"] = [
        deepcopy(section)
        for section in document["sections"]
        if section["section_id"] in referenced_ids
    ]
    return selected


def select_connection_cases(
    case: Mapping[str, Any], *, reference_label: str | None = None
) -> list[dict[str, Any]]:
    selected = [
        connection
        for connection in case["expected_connections"]
        if reference_label is None or connection["label"] == reference_label
    ]
    roles = {
        role["role_element_id"]: role for role in case["expected_role_elements"]
    }
    experiences = {
        experience["experience_id"]: experience
        for experience in case["experiences"]
    }
    result = []
    for connection in selected:
        sliced = deepcopy(dict(case))
        sliced["case_id"] = (
            f"{case['case_id']}--{connection['role_element_id']}"
            f"--{connection['experience_id']}"
        )
        sliced["expected_role_elements"] = [
            deepcopy(roles[connection["role_element_id"]])
        ]
        sliced["experiences"] = [
            deepcopy(experiences[connection["experience_id"]])
        ]
        sliced["expected_connections"] = [deepcopy(connection)]
        result.append(sliced)
    return result


def build_judge_messages(
    document: Mapping[str, Any],
    case: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, str]]:
    role_elements = [
        {
            "role_element_id": role["role_element_id"],
            "name": role["name"],
            "evidence_section_ids": role["evidence_section_ids"],
            "evidence_requirements": role["evidence_requirements"],
        }
        for role in case["expected_role_elements"]
    ]
    target_connections = [
        {
            "role_element_id": connection["role_element_id"],
            "experience_id": connection["experience_id"],
        }
        for connection in case["expected_connections"]
    ]
    model_input = {
        "jd_document": {
            "document_id": document["document_id"],
            "company_name": document["company_name"],
            "organization": document.get("organization"),
            "job_title": document.get("job_title"),
            "source_type": document["source_type"],
            "sections": document["sections"],
        },
        "question": case["question"],
        "experiences": case["experiences"],
        "role_elements": role_elements,
        "target_connections": target_connections,
    }
    system_prompt = with_common_rules(f"""
너는 JD 역할 요소와 사용자 경험 사이의 필요 근거를 확인하는 평가자다.
최종 연결 라벨은 결정하지 않는다. 각 evidence_requirement만 독립적으로 PRESENT 또는 ABSENT로 판정한다.
PRESENT는 해당 사용자 경험의 원문에 근거가 명시된 경우에만 선택한다.
PRESENT이면 evidence_quote에 사용자 경험의 연속된 원문 일부를 정확히 복사한다.
ABSENT이면 evidence_quote는 빈 문자열로 둔다.
주제나 키워드가 비슷하거나 일반적으로 그럴 것이라는 추론은 근거로 인정하지 않는다.
경험에 없는 행동, 기술, 방법, 성과를 보충하지 않는다.
target_connections의 모든 조합과 각 역할 요소의 모든 evidence_requirement를 정확히 한 번씩 판정한다.

연결 정책 참고:
{json.dumps(policy, ensure_ascii=False)}
""")
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(model_input, ensure_ascii=False)},
    ]


def judge_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["judgments"],
        "properties": {
            "judgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "role_element_id",
                        "experience_id",
                        "evidence_checks",
                    ],
                    "properties": {
                        "role_element_id": {"type": "string"},
                        "experience_id": {"type": "string"},
                        "evidence_checks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "evidence_requirement_id",
                                    "status",
                                    "evidence_quote",
                                    "reason",
                                ],
                                "properties": {
                                    "evidence_requirement_id": {"type": "string"},
                                    "status": {
                                        "type": "string",
                                        "enum": sorted(EVIDENCE_STATUSES),
                                    },
                                    "evidence_quote": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
    }


def _case_indexes(case: Mapping[str, Any]) -> tuple[dict, dict, set]:
    roles = {
        role["role_element_id"]: role for role in case["expected_role_elements"]
    }
    experiences = {
        experience["experience_id"]: experience["text"]
        for experience in case["experiences"]
    }
    target_pairs = {
        (connection["role_element_id"], connection["experience_id"])
        for connection in case["expected_connections"]
    }
    return roles, experiences, target_pairs


def validate_judge_output(
    output: Mapping[str, Any], case: Mapping[str, Any]
) -> None:
    judgments = output.get("judgments")
    if not isinstance(judgments, list):
        raise ValueError("judgments must be a list")

    roles, experiences, target_pairs = _case_indexes(case)
    actual_pairs: set[tuple[str, str]] = set()
    for judgment in judgments:
        if not isinstance(judgment, dict):
            raise ValueError("judgment must be an object")
        role_id = judgment.get("role_element_id")
        experience_id = judgment.get("experience_id")
        pair = (role_id, experience_id)
        if pair in actual_pairs:
            raise ValueError(f"duplicate judgment pair: {pair}")
        if pair not in target_pairs:
            raise ValueError(f"unknown judgment pair: {pair}")
        actual_pairs.add(pair)

        expected_requirement_ids = {
            requirement["evidence_requirement_id"]
            for requirement in roles[role_id]["evidence_requirements"]
        }
        checks = judgment.get("evidence_checks")
        if not isinstance(checks, list):
            raise ValueError("evidence_checks must be a list")
        actual_requirement_ids: set[str] = set()
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("evidence_check must be an object")
            requirement_id = check.get("evidence_requirement_id")
            if requirement_id in actual_requirement_ids:
                raise ValueError(f"duplicate evidence_requirement_id: {requirement_id}")
            if requirement_id not in expected_requirement_ids:
                raise ValueError(f"unknown evidence_requirement_id: {requirement_id}")
            actual_requirement_ids.add(requirement_id)

            status = check.get("status")
            quote = check.get("evidence_quote")
            reason = check.get("reason")
            if status not in EVIDENCE_STATUSES:
                raise ValueError(f"unknown evidence status: {status}")
            if not isinstance(quote, str):
                raise ValueError("evidence_quote must be a string")
            if status == "PRESENT" and (
                not quote.strip() or quote.strip() not in experiences[experience_id]
            ):
                raise ValueError("PRESENT evidence_quote must occur in the user experience")
            if status == "ABSENT" and quote:
                raise ValueError("ABSENT evidence_quote must be empty")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("reason must be a non-empty string")

        if actual_requirement_ids != expected_requirement_ids:
            raise ValueError("evidence requirement coverage is incomplete")

    if actual_pairs != target_pairs:
        raise ValueError("judgment pairs do not match the evaluation case")


def derive_labels(
    output: Mapping[str, Any], case: Mapping[str, Any]
) -> list[dict[str, Any]]:
    validate_judge_output(output, case)
    roles = {
        role["role_element_id"]: role for role in case["expected_role_elements"]
    }
    derived = []
    for judgment in output["judgments"]:
        present = [
            check
            for check in judgment["evidence_checks"]
            if check["status"] == "PRESENT"
        ]
        missing = [
            check["evidence_requirement_id"]
            for check in judgment["evidence_checks"]
            if check["status"] == "ABSENT"
        ]
        label = (
            "SUPPORTED"
            if not missing
            else "PARTIALLY_SUPPORTED"
            if present
            else "NOT_SUPPORTED"
        )
        requirement_descriptions = {
            requirement["evidence_requirement_id"]: requirement["description"]
            for requirement in roles[judgment["role_element_id"]][
                "evidence_requirements"
            ]
        }
        missing_evidence = [
            {
                "evidence_requirement_id": requirement_id,
                "description": requirement_descriptions[requirement_id],
            }
            for requirement_id in missing
        ]
        feedback = (
            "필요 근거가 모두 확인됩니다."
            if not missing_evidence
            else "다음 내용을 경험에 구체적으로 보완해 주세요: "
            + " ".join(item["description"] for item in missing_evidence)
        )
        derived.append(
            {
                "role_element_id": judgment["role_element_id"],
                "experience_id": judgment["experience_id"],
                "derived_label": label,
                "present_evidence": [
                    {
                        "evidence_requirement_id": check[
                            "evidence_requirement_id"
                        ],
                        "evidence_quote": check["evidence_quote"],
                    }
                    for check in present
                ],
                "missing_evidence_requirement_ids": missing,
                "missing_evidence": missing_evidence,
                "feedback": feedback,
            }
        )
    return derived


def compare_with_reference_labels(
    output: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    derived = {
        (item["role_element_id"], item["experience_id"]): item
        for item in derive_labels(output, case)
    }
    judgments = {
        (item["role_element_id"], item["experience_id"]): item
        for item in output["judgments"]
    }
    roles = {
        role["role_element_id"]: role for role in case["expected_role_elements"]
    }
    experiences = {
        experience["experience_id"]: experience["text"]
        for experience in case["experiences"]
    }
    disagreements = []
    agreement_count = 0
    for draft in case["expected_connections"]:
        pair = (draft["role_element_id"], draft["experience_id"])
        judged = derived[pair]
        if draft["label"] == judged["derived_label"]:
            agreement_count += 1
            continue
        disagreements.append(
            {
                "role_element_id": pair[0],
                "role_element_name": roles[pair[0]]["name"],
                "experience_id": pair[1],
                "experience_text": experiences[pair[1]],
                "reference_label": draft["label"],
                "judge_derived_label": judged["derived_label"],
                "evidence_checks": judgments[pair]["evidence_checks"],
            }
        )
    total = len(case["expected_connections"])
    return {
        "total": total,
        "agreement_count": agreement_count,
        "disagreement_count": len(disagreements),
        "agreement_rate": round(agreement_count / total, 4) if total else 0.0,
        "disagreements": disagreements,
    }


# 기존 호출부와 저장 결과를 다시 읽을 수 있도록 이름을 유지한다.
compare_with_draft = compare_with_reference_labels
