from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import JdDocument


LABEL_STATUSES = {"DRAFT", "HUMAN_APPROVED"}
CONNECTION_LABELS = {"SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED"}


class EvaluationContractError(ValueError):
    """평가 사례의 참조 또는 라벨이 유효하지 않은 경우."""


def summarize_evaluation_cases(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    summary = {
        "total": {"cases": 0, "roles": 0, "connections": 0},
        "human_approved": {"cases": 0, "roles": 0, "connections": 0},
        "draft": {"cases": 0, "roles": 0, "connections": 0},
    }
    for case in cases:
        status_key = (
            "human_approved"
            if case.get("label_status") == "HUMAN_APPROVED"
            else "draft"
        )
        roles = len(case.get("expected_role_elements", []))
        connections = len(case.get("expected_connections", []))
        for key in ("total", status_key):
            summary[key]["cases"] += 1
            summary[key]["roles"] += roles
            summary[key]["connections"] += connections
    return summary


def evaluate_connection_predictions(
    gold_connections: list[Mapping[str, Any]],
    predicted_connections: list[Mapping[str, Any]],
    experience_text_by_id: Mapping[str, str],
) -> dict[str, Any]:
    def key(item: Mapping[str, Any]) -> tuple[str, str]:
        return (
            str(item["role_element_id"]),
            str(item["experience_id"]),
        )

    gold_by_key = {key(item): item for item in gold_connections}
    predicted_by_key = {key(item): item for item in predicted_connections}
    matched_prediction_count = len(gold_by_key.keys() & predicted_by_key.keys())
    correct = sum(
        1
        for pair, gold in gold_by_key.items()
        if pair in predicted_by_key
        and predicted_by_key[pair].get("label") == gold.get("label")
    )

    f1_values = []
    for label in sorted(CONNECTION_LABELS):
        true_positive = sum(
            1
            for pair, gold in gold_by_key.items()
            if gold.get("label") == label
            and predicted_by_key.get(pair, {}).get("label") == label
        )
        false_positive = sum(
            1
            for pair, prediction in predicted_by_key.items()
            if prediction.get("label") == label
            and gold_by_key.get(pair, {}).get("label") != label
        )
        false_negative = sum(
            1
            for pair, gold in gold_by_key.items()
            if gold.get("label") == label
            and predicted_by_key.get(pair, {}).get("label") != label
        )
        denominator = 2 * true_positive + false_positive + false_negative
        f1_values.append(2 * true_positive / denominator if denominator else 0.0)

    def evidence_ids(
        rows: Mapping[tuple[str, str], Mapping[str, Any]],
    ) -> set[tuple[str, str, str]]:
        return {
            (pair[0], pair[1], str(evidence["evidence_requirement_id"]))
            for pair, row in rows.items()
            for evidence in row.get("present_evidence", [])
        }

    gold_evidence = evidence_ids(gold_by_key)
    predicted_evidence = evidence_ids(predicted_by_key)
    evidence_hits = len(gold_evidence & predicted_evidence)
    predicted_quotes = [
        (pair[1], str(evidence.get("evidence_quote", "")))
        for pair, row in predicted_by_key.items()
        for evidence in row.get("present_evidence", [])
    ]
    hallucinated_quotes = sum(
        1
        for experience_id, quote in predicted_quotes
        if not quote or quote not in experience_text_by_id.get(experience_id, "")
    )
    gold_count = len(gold_by_key)
    return {
        "connection_count": gold_count,
        "prediction_coverage": matched_prediction_count / gold_count if gold_count else 0.0,
        "label_accuracy": correct / gold_count if gold_count else 0.0,
        "label_macro_f1": sum(f1_values) / len(f1_values),
        "evidence_requirement_precision": (
            evidence_hits / len(predicted_evidence) if predicted_evidence else 0.0
        ),
        "evidence_requirement_recall": (
            evidence_hits / len(gold_evidence) if gold_evidence else 0.0
        ),
        "hallucinated_quote_rate": (
            hallucinated_quotes / len(predicted_quotes) if predicted_quotes else 0.0
        ),
    }


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationContractError(f"{field} must be a non-empty string")
    return value.strip()


def _unique_ids(items: Any, field: str) -> set[str]:
    if not isinstance(items, list) or not items:
        raise EvaluationContractError(f"{field} collection must be a non-empty list")
    identifiers: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise EvaluationContractError(f"{field} item must be an object")
        identifier = _required_text(item, field)
        if identifier in identifiers:
            raise EvaluationContractError(f"duplicate {field}: {identifier}")
        identifiers.add(identifier)
    return identifiers


def validate_evaluation_case(
    case: Mapping[str, Any], documents: Mapping[str, JdDocument]
) -> None:
    if case.get("schema_version") != "1.0":
        raise EvaluationContractError("unsupported schema_version")
    _required_text(case, "case_id")

    label_status = _required_text(case, "label_status")
    if label_status not in LABEL_STATUSES:
        raise EvaluationContractError(f"unknown label_status: {label_status}")

    source_document_ids = case.get("source_document_ids")
    if not isinstance(source_document_ids, list) or not source_document_ids:
        raise EvaluationContractError("source_document_ids must be a non-empty list")
    selected_documents: list[JdDocument] = []
    for document_id in source_document_ids:
        if not isinstance(document_id, str) or document_id not in documents:
            raise EvaluationContractError(f"unknown source_document_id: {document_id}")
        selected_documents.append(documents[document_id])

    evidence_section_ids = {
        section.section_id
        for document in selected_documents
        for section in document.sections
    }
    experience_ids = _unique_ids(case.get("experiences"), "experience_id")
    experience_text_by_id = {
        experience["experience_id"]: _required_text(experience, "text")
        for experience in case["experiences"]
    }
    role_element_ids = _unique_ids(
        case.get("expected_role_elements"), "role_element_id"
    )
    requirement_ids_by_role: dict[str, set[str]] = {}

    for role in case["expected_role_elements"]:
        role_element_id = _required_text(role, "role_element_id")
        references = role.get("evidence_section_ids")
        if not isinstance(references, list) or not references:
            raise EvaluationContractError(
                "evidence_section_ids must be a non-empty list"
            )
        for section_id in references:
            if section_id not in evidence_section_ids:
                raise EvaluationContractError(
                    f"unknown evidence_section_id: {section_id}"
                )
        requirement_ids_by_role[role_element_id] = _unique_ids(
            role.get("evidence_requirements"), "evidence_requirement_id"
        )
        for requirement in role["evidence_requirements"]:
            _required_text(requirement, "description")

    connections = case.get("expected_connections")
    if not isinstance(connections, list) or not connections:
        raise EvaluationContractError(
            "expected_connections must be a non-empty list"
        )
    seen_pairs: set[tuple[str, str]] = set()
    for connection in connections:
        if not isinstance(connection, dict):
            raise EvaluationContractError("connection must be an object")
        role_element_id = _required_text(connection, "role_element_id")
        experience_id = _required_text(connection, "experience_id")
        if role_element_id not in role_element_ids:
            raise EvaluationContractError(
                f"unknown role_element_id: {role_element_id}"
            )
        if experience_id not in experience_ids:
            raise EvaluationContractError(f"unknown experience_id: {experience_id}")
        pair = (role_element_id, experience_id)
        if pair in seen_pairs:
            raise EvaluationContractError(f"duplicate connection: {pair}")
        seen_pairs.add(pair)

        label = _required_text(connection, "label")
        if label not in CONNECTION_LABELS:
            raise EvaluationContractError(f"unknown connection label: {label}")

        role_requirement_ids = requirement_ids_by_role[role_element_id]
        present_evidence = connection.get("present_evidence")
        if not isinstance(present_evidence, list):
            raise EvaluationContractError("present_evidence must be a list")
        present_requirement_ids: set[str] = set()
        for evidence in present_evidence:
            if not isinstance(evidence, dict):
                raise EvaluationContractError(
                    "present_evidence item must be an object"
                )
            requirement_id = _required_text(
                evidence, "evidence_requirement_id"
            )
            if requirement_id not in role_requirement_ids:
                raise EvaluationContractError(
                    f"unknown evidence_requirement_id: {requirement_id}"
                )
            if requirement_id in present_requirement_ids:
                raise EvaluationContractError(
                    f"duplicate evidence_requirement_id: {requirement_id}"
                )
            present_requirement_ids.add(requirement_id)
            quote = _required_text(evidence, "evidence_quote")
            if quote not in experience_text_by_id[experience_id]:
                raise EvaluationContractError(
                    "evidence_quote must occur in the user experience"
                )

        missing_ids = connection.get("missing_evidence_requirement_ids")
        if not isinstance(missing_ids, list):
            raise EvaluationContractError(
                "missing_evidence_requirement_ids must be a list"
            )
        missing_requirement_ids: set[str] = set()
        for requirement_id in missing_ids:
            if (
                not isinstance(requirement_id, str)
                or requirement_id not in role_requirement_ids
            ):
                raise EvaluationContractError(
                    f"unknown evidence_requirement_id: {requirement_id}"
                )
            if requirement_id in missing_requirement_ids:
                raise EvaluationContractError(
                    f"duplicate evidence_requirement_id: {requirement_id}"
                )
            missing_requirement_ids.add(requirement_id)

        if present_requirement_ids & missing_requirement_ids:
            raise EvaluationContractError(
                "evidence_requirement_id cannot be both present and missing"
            )
        if present_requirement_ids | missing_requirement_ids != role_requirement_ids:
            raise EvaluationContractError(
                "evidence coverage must include every role requirement"
            )

        if present_requirement_ids == role_requirement_ids:
            expected_label = "SUPPORTED"
        elif present_requirement_ids:
            expected_label = "PARTIALLY_SUPPORTED"
        else:
            expected_label = "NOT_SUPPORTED"
        if label != expected_label:
            raise EvaluationContractError(
                f"label disagrees with evidence coverage: "
                f"expected {expected_label}, got {label}"
            )
        _required_text(connection, "reason")
