from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ai.llm import complete_structured, load_llm_config


CONNECTION_LABELS = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "NOT_SUPPORTED",
}


def load_qwen_config(path: Path, *, prefix: str = "") -> dict[str, str]:
    """LLM 설정을 읽는다. 이름은 Qwen 이지만 공급자·모델은 설정이 정한다.

    `prefix` 는 담당 이름(JD·POSITION·WRITING·SUPERVISOR_PLAN·SUPERVISOR_AGGREGATE·NEWS).
    담당별 기본 배정(`ai.llm.config.AGENT_DEFAULTS`)과 `<PREFIX>_LLM_*` 덮어쓰기가 여기서 적용된다.
    비우면 전역 `LLM_PROVIDER` 를 따른다.

    이름을 그대로 둔 것은 담당 다섯이 이 함수를 부르고 있어서다. 공급자 전환을 이름 바꾸기와
    섞으면 무엇 때문에 깨졌는지 가려진다 — 이름 정리는 전환이 끝난 뒤에 한다.
    """
    return load_llm_config(path, prefix=prefix).as_dict()


def build_messages(
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
    system_prompt = f"""
너는 JD 근거와 사용자 경험의 연결을 판정한다.
판정 단위는 역할 요소 1개와 사용자 경험 1개의 조합이다.
반드시 제공된 target_connections 전부를 한 번씩 판정한다.
역할 요소의 evidence_requirements를 사용자 경험의 명시적 문장으로 확인한다.
주제나 키워드가 유사하다는 이유만으로 근거가 있다고 판단하지 않는다.
사용자 경험에 없는 행동, 기술, 방법, 성과를 추정하지 않는다.

연결 정책:
{json.dumps(policy, ensure_ascii=False)}

각 결과에는 JD section_id, 충족된 evidence_requirement_id와 사용자 원문 인용,
누락된 evidence_requirement_id, 라벨, 판정 이유를 반환한다.
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(model_input, ensure_ascii=False),
        },
    ]


def output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["connections"],
        "properties": {
            "connections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "role_element_id",
                        "experience_id",
                        "label",
                        "job_evidence_section_ids",
                        "present_evidence",
                        "missing_evidence_requirement_ids",
                        "reason",
                    ],
                    "properties": {
                        "role_element_id": {"type": "string"},
                        "experience_id": {"type": "string"},
                        "label": {
                            "type": "string",
                            "enum": sorted(CONNECTION_LABELS),
                        },
                        "job_evidence_section_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "present_evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "evidence_requirement_id",
                                    "evidence_quote",
                                ],
                                "properties": {
                                    "evidence_requirement_id": {
                                        "type": "string"
                                    },
                                    "evidence_quote": {"type": "string"},
                                },
                            },
                        },
                        "missing_evidence_requirement_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }


def validate_model_output(
    output: Mapping[str, Any],
    case: Mapping[str, Any],
    document: Mapping[str, Any],
) -> None:
    connections = output.get("connections")
    if not isinstance(connections, list):
        raise ValueError("connections must be a list")

    expected_pairs = {
        (item["role_element_id"], item["experience_id"])
        for item in case["expected_connections"]
    }
    role_by_id = {
        item["role_element_id"]: item for item in case["expected_role_elements"]
    }
    experience_by_id = {
        item["experience_id"]: item["text"] for item in case["experiences"]
    }
    section_ids = {item["section_id"] for item in document["sections"]}
    actual_pairs: set[tuple[str, str]] = set()

    for connection in connections:
        if not isinstance(connection, dict):
            raise ValueError("connection must be an object")
        role_id = connection.get("role_element_id")
        experience_id = connection.get("experience_id")
        pair = (role_id, experience_id)
        if pair in actual_pairs:
            raise ValueError(f"duplicate connection pair: {pair}")
        actual_pairs.add(pair)
        if pair not in expected_pairs:
            raise ValueError(f"unknown connection pair: {pair}")

        label = connection.get("label")
        if label not in CONNECTION_LABELS:
            raise ValueError(f"unknown label: {label}")
        references = connection.get("job_evidence_section_ids")
        if not isinstance(references, list) or not references:
            raise ValueError("job_evidence_section_ids must be a non-empty list")
        if set(references) - section_ids:
            raise ValueError("unknown job evidence section_id")

        requirements = {
            item["evidence_requirement_id"]
            for item in role_by_id[role_id]["evidence_requirements"]
        }
        present = connection.get("present_evidence")
        missing = connection.get("missing_evidence_requirement_ids")
        if not isinstance(present, list) or not isinstance(missing, list):
            raise ValueError("present and missing evidence must be lists")

        present_ids: set[str] = set()
        for evidence in present:
            if not isinstance(evidence, dict):
                raise ValueError("present_evidence item must be an object")
            requirement_id = evidence.get("evidence_requirement_id")
            quote = evidence.get("evidence_quote")
            if requirement_id not in requirements:
                raise ValueError(f"unknown evidence_requirement_id: {requirement_id}")
            if requirement_id in present_ids:
                raise ValueError(f"duplicate evidence_requirement_id: {requirement_id}")
            if (
                not isinstance(quote, str)
                or not quote.strip()
                or quote.strip() not in experience_by_id[experience_id]
            ):
                raise ValueError("evidence_quote must occur in the user experience")
            present_ids.add(requirement_id)

        missing_ids = set(missing)
        if len(missing_ids) != len(missing) or not missing_ids <= requirements:
            raise ValueError("invalid missing evidence_requirement_id")
        if present_ids & missing_ids or present_ids | missing_ids != requirements:
            raise ValueError("evidence coverage is incomplete")

        expected_label = (
            "SUPPORTED"
            if present_ids == requirements
            else "PARTIALLY_SUPPORTED"
            if present_ids
            else "NOT_SUPPORTED"
        )
        if label != expected_label:
            raise ValueError("label disagrees with evidence coverage")
        reason = connection.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

    if actual_pairs != expected_pairs:
        raise ValueError("connection pairs do not match the evaluation case")


def score_connections(
    output: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    if case.get("label_status") != "HUMAN_APPROVED":
        raise ValueError("only HUMAN_APPROVED cases can be scored")
    gold = {
        (item["role_element_id"], item["experience_id"]): item["label"]
        for item in case["expected_connections"]
    }
    predicted = {
        (item["role_element_id"], item["experience_id"]): item["label"]
        for item in output["connections"]
    }
    correct = sum(predicted.get(pair) == label for pair, label in gold.items())
    per_label: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for label in sorted(CONNECTION_LABELS):
        true_positive = sum(
            gold[pair] == label and predicted.get(pair) == label for pair in gold
        )
        false_positive = sum(
            gold[pair] != label and predicted.get(pair) == label for pair in gold
        )
        false_negative = sum(
            gold[pair] == label and predicted.get(pair) != label for pair in gold
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        f1_values.append(f1)
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(value == label for value in gold.values()),
        }
    total = len(gold)
    mismatches = [
        {
            "role_element_id": pair[0],
            "experience_id": pair[1],
            "gold_label": gold_label,
            "predicted_label": predicted.get(pair),
        }
        for pair, gold_label in gold.items()
        if predicted.get(pair) != gold_label
    ]
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "per_label": per_label,
        "mismatches": mismatches,
    }


def call_qwen(
    config: Mapping[str, str],
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4096,
    timeout_seconds: int = 180,
    schema: Mapping[str, Any] | None = None,
    schema_name: str = "jd_connection_baseline_output",
) -> dict[str, Any]:
    """담당들이 공유하는 LLM 호출 자리. 어느 서버로 나가는지는 `config["provider"]` 가 정한다.

    담당 다섯이 이 함수를 기본값으로 주입받고 있어 시그니처를 그대로 둔다. 공급자별 차이는
    `ai.llm` 이 흡수한다.
    """
    return complete_structured(
        config,
        messages,
        schema=dict(schema) if schema is not None else output_schema(),
        schema_name=schema_name,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
