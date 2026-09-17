from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .contracts import (
    CLAIM_TYPES,
    DOCUMENT_TYPES,
    ELEMENT_CODES,
    VERDICTS,
    load_experience_rubric,
    validate_experience_analysis_output,
)


CASE_FIELDS = {
    "schema_version",
    "case_id",
    "label_status",
    "rubric_id",
    "position_context",
    "question",
    "documents",
    "expected_findings",
    "forbidden_output_substrings",
}
DOCUMENT_FIELDS = {"document_id", "document_type", "text"}
EXPECTED_FINDING_FIELDS = {
    "claim_type",
    "claim_quote",
    "verdict",
    "present_elements",
    "missing_elements",
}
PREDICTION_FIELDS = {"schema_valid", "output", "response_text"}
POSITION_CONTEXT_FIELDS = {"position_name", "priority_requirements"}
RUBRIC_PATH = Path(__file__).parent / "resources" / "rubrics" / "experience-depth-v1.json"


def load_evaluation_case(path: Path) -> dict[str, Any]:
    """Load one independently authored evaluation case under the strict v2 contract."""
    if not isinstance(path, Path):
        raise ValueError("evaluation case source must be a Path")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_evaluation_case(payload)


def validate_evaluation_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an in-memory evaluation case and return a detached plain dictionary."""
    payload = _mapping(case, "evaluation case")
    _exact_fields(payload, CASE_FIELDS, "evaluation case")
    if payload["schema_version"] != "2.0":
        raise ValueError("unsupported evaluation case schema_version")

    case_id = _text(payload["case_id"], "case_id")
    label_status = payload["label_status"]
    if type(label_status) is not str or label_status not in {"DRAFT", "HUMAN_APPROVED"}:
        raise ValueError("label_status must be DRAFT or HUMAN_APPROVED")
    rubric_id = payload["rubric_id"]
    if type(rubric_id) is not str or rubric_id != "experience-depth-v1":
        raise ValueError("rubric_id must reference experience-depth-v1")
    position_context = _validate_position_context(payload["position_context"])
    question = _text(payload["question"], "question")

    documents_value = _list(payload["documents"], "documents")
    if not documents_value:
        raise ValueError("documents must not be empty")
    document_ids: set[str] = set()
    documents: list[dict[str, str]] = []
    for item in documents_value:
        document = _mapping(item, "document")
        _exact_fields(document, DOCUMENT_FIELDS, "document")
        document_id = _text(document["document_id"], "document_id")
        if document_id in document_ids:
            raise ValueError("duplicate document_id")
        document_ids.add(document_id)
        document_type = document["document_type"]
        if type(document_type) is not str or document_type not in DOCUMENT_TYPES:
            raise ValueError("unsupported document_type")
        text = _text(document["text"], "document text", strip=False)
        documents.append(
            {"document_id": document_id, "document_type": document_type, "text": text}
        )

    expected_values = _list(payload["expected_findings"], "expected_findings")
    expected_findings: list[dict[str, Any]] = []
    finding_keys: set[tuple[str, str]] = set()
    for item in expected_values:
        finding = _validate_expected_finding(item, documents)
        key = _expected_key(finding)
        if key in finding_keys:
            raise ValueError("duplicate expected finding key")
        finding_keys.add(key)
        expected_findings.append(finding)

    forbidden_values = _list(
        payload["forbidden_output_substrings"], "forbidden_output_substrings"
    )
    forbidden: list[str] = []
    for item in forbidden_values:
        value = _text(item, "forbidden output substring", strip=False)
        if value in forbidden:
            raise ValueError("duplicate forbidden output substring")
        forbidden.append(value)

    return {
        "schema_version": "2.0",
        "case_id": case_id,
        "label_status": label_status,
        "rubric_id": rubric_id,
        "position_context": position_context,
        "question": question,
        "documents": documents,
        "expected_findings": expected_findings,
        "forbidden_output_substrings": forbidden,
    }


def score_evaluation(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Score approved cases without inventing labels for absent or invalid responses."""
    if isinstance(cases, (str, bytes)) or not isinstance(cases, Sequence):
        raise ValueError("cases must be a sequence")
    if not isinstance(predictions, Mapping):
        raise ValueError("predictions must be a mapping")

    validated_cases = [validate_evaluation_case(case) for case in cases]
    case_ids = [case["case_id"] for case in validated_cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate case_id")
    if any(case["label_status"] != "HUMAN_APPROVED" for case in validated_cases):
        raise ValueError("every evaluation case must be HUMAN_APPROVED")
    unknown_predictions = set(predictions) - set(case_ids)
    if unknown_predictions:
        raise ValueError("prediction references unknown case_id")

    received = 0
    schema_valid_count = 0
    forbidden_occurrences = 0
    aligned_pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    rubric = load_experience_rubric(RUBRIC_PATH)

    for case in validated_cases:
        case_id = case["case_id"]
        if case_id not in predictions:
            continue
        received += 1
        envelope = _validate_prediction_envelope(predictions[case_id])
        response_text = envelope["response_text"]
        forbidden_occurrences += sum(
            response_text.count(substring)
            for substring in case["forbidden_output_substrings"]
        )
        if not envelope["schema_valid"]:
            continue

        schema_valid_count += 1
        output = validate_experience_analysis_output(
            envelope["output"], case["documents"], rubric
        )
        expected_by_key = {
            _expected_key(finding): finding for finding in case["expected_findings"]
        }
        actual_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
        for finding in output["findings"]:
            key = _actual_key(finding)
            if key in actual_by_key:
                raise ValueError("duplicate actual finding key")
            actual_by_key[key] = finding
        for key in expected_by_key.keys() & actual_by_key.keys():
            aligned_pairs.append((expected_by_key[key], actual_by_key[key]))

    verdict_hits = sum(
        expected["verdict"] == actual["verdict"]
        for expected, actual in aligned_pairs
    )
    macro_f1_numerator = 0.0
    for verdict in sorted(VERDICTS):
        true_positive = sum(
            expected["verdict"] == verdict and actual["verdict"] == verdict
            for expected, actual in aligned_pairs
        )
        false_positive = sum(
            expected["verdict"] != verdict and actual["verdict"] == verdict
            for expected, actual in aligned_pairs
        )
        false_negative = sum(
            expected["verdict"] == verdict and actual["verdict"] != verdict
            for expected, actual in aligned_pairs
        )
        denominator = 2 * true_positive + false_positive + false_negative
        macro_f1_numerator += 2 * true_positive / denominator if denominator else 0.0

    present_metrics = _element_metrics(aligned_pairs, "present_elements")
    missing_metrics = _element_metrics(aligned_pairs, "missing_elements")
    aligned_count = len(aligned_pairs)

    return {
        "case_count": len(validated_cases),
        "prediction_coverage": _rate(received, len(validated_cases)),
        "schema_valid_response_rate": _rate(schema_valid_count, received),
        "aligned_finding_count": aligned_count,
        "verdict_accuracy": _rate(verdict_hits, aligned_count),
        "verdict_macro_f1": _rate(macro_f1_numerator, len(VERDICTS)),
        "present_elements": present_metrics,
        "missing_elements": missing_metrics,
        "exact_claim_quote_rate": _rate(aligned_count, aligned_count),
        "forbidden_output_occurrence_count": forbidden_occurrences,
    }


def _validate_expected_finding(
    item: Any, documents: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    finding = _mapping(item, "expected finding")
    _exact_fields(finding, EXPECTED_FINDING_FIELDS, "expected finding")
    claim_type = _text(finding["claim_type"], "claim_type")
    if claim_type not in CLAIM_TYPES:
        raise ValueError("unsupported claim_type")
    claim_quote = _text(finding["claim_quote"], "claim_quote", strip=False)
    if not any(claim_quote in document["text"] for document in documents):
        raise ValueError("claim_quote must occur in a case document")
    verdict = finding["verdict"]
    if type(verdict) is not str or verdict not in VERDICTS:
        raise ValueError("unsupported verdict")
    present = _element_list(finding["present_elements"], "present_elements")
    missing = _element_list(finding["missing_elements"], "missing_elements")

    required = set(CLAIM_TYPES[claim_type])
    present_set = set(present)
    missing_set = set(missing)
    if present_set & missing_set or present_set | missing_set != required:
        raise ValueError("present/missing elements must partition required elements")
    if verdict == "NOT_ASSESSABLE":
        if present or missing_set != required:
            raise ValueError("NOT_ASSESSABLE requires all elements to be missing")
    else:
        expected_verdict = (
            "SUFFICIENT"
            if present_set == required
            else "PARTIAL"
            if "ACTION" in present_set
            else "CLAIM_ONLY"
        )
        if verdict != expected_verdict:
            raise ValueError("verdict does not match element partition")

    return {
        "claim_type": claim_type,
        "claim_quote": claim_quote,
        "verdict": verdict,
        "present_elements": present,
        "missing_elements": missing,
    }


def _validate_prediction_envelope(value: Any) -> dict[str, Any]:
    envelope = _mapping(value, "prediction envelope")
    _exact_fields(envelope, PREDICTION_FIELDS, "prediction envelope")
    schema_valid = envelope["schema_valid"]
    if type(schema_valid) is not bool:
        raise ValueError("schema_valid must be a boolean")
    output = envelope["output"]
    if schema_valid and not isinstance(output, Mapping):
        raise ValueError("schema_valid prediction requires a non-null output")
    if not schema_valid and output is not None:
        raise ValueError("schema-invalid prediction requires a null output")
    response_text = envelope["response_text"]
    if type(response_text) is not str:
        raise ValueError("response_text must be a string")
    return {
        "schema_valid": schema_valid,
        "output": output,
        "response_text": response_text,
    }


def _element_metrics(
    pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    field: str,
) -> dict[str, dict[str, int | float | None]]:
    true_positive = false_positive = false_negative = 0
    for expected, actual in pairs:
        expected_elements = set(expected[field])
        actual_value = actual[field]
        actual_elements = (
            {item["element"] for item in actual_value}
            if field == "present_elements"
            else set(actual_value)
        )
        true_positive += len(expected_elements & actual_elements)
        false_positive += len(actual_elements - expected_elements)
        false_negative += len(expected_elements - actual_elements)
    return {
        "precision": _rate(true_positive, true_positive + false_positive),
        "recall": _rate(true_positive, true_positive + false_negative),
        "f1": _rate(2 * true_positive, 2 * true_positive + false_positive + false_negative),
    }


def _rate(numerator: int | float, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _expected_key(finding: Mapping[str, Any]) -> tuple[str, str]:
    return (finding["claim_type"], finding["claim_quote"])


def _actual_key(finding: Mapping[str, Any]) -> tuple[str, str]:
    return (finding["claim_type"], finding["claim"]["quote"])


def _validate_position_context(value: Any) -> dict[str, Any]:
    context = _mapping(value, "position_context")
    _exact_fields(context, POSITION_CONTEXT_FIELDS, "position_context")
    position_name = _text(context["position_name"], "position_name")
    if len(position_name) > 200:
        raise ValueError("position_name is too long")
    priorities = _list(context["priority_requirements"], "priority_requirements")
    if len(priorities) > 20:
        raise ValueError("priority_requirements contains too many items")
    validated_priorities = []
    for priority in priorities:
        normalized = _text(priority, "priority requirement")
        if len(normalized) > 500:
            raise ValueError("priority requirement is too long")
        validated_priorities.append(normalized)
    return {
        "position_name": position_name,
        "priority_requirements": validated_priorities,
    }


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} must contain exactly the required fields")


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _text(value: Any, context: str, *, strip: bool = True) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value.strip() if strip else value


def _element_list(value: Any, context: str) -> list[str]:
    items = _list(value, context)
    if any(type(item) is not str or item not in ELEMENT_CODES for item in items):
        raise ValueError(f"{context} contains an unsupported element")
    if len(items) != len(set(items)):
        raise ValueError(f"{context} contains a duplicate element")
    return list(items)
