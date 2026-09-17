import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


ELEMENT_CODES = {
    "SITUATION", "PROBLEM", "ROLE", "ACTION", "REASONING",
    "PROCESS", "VERIFICATION", "RESULT", "LEARNING",
}
CLAIM_TYPES = {
    "PROBLEM_SOLVING": ("PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION", "RESULT"),
    "ACHIEVEMENT": ("SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"),
    "DECISION": ("SITUATION", "ROLE", "ACTION", "REASONING", "RESULT"),
    "EXECUTION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "COLLABORATION": ("SITUATION", "ROLE", "ACTION", "PROCESS", "RESULT"),
    "GROWTH": ("SITUATION", "ACTION", "VERIFICATION", "LEARNING"),
    "OTHER": ("SITUATION", "ROLE", "ACTION", "RESULT"),
}
VERDICTS = {"SUFFICIENT", "PARTIAL", "CLAIM_ONLY", "NOT_ASSESSABLE"}
DOCUMENT_TYPES = {"RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"}


def load_experience_rubric(source: Path | Mapping[str, Any]) -> dict[str, Any]:
    """Load the canonical universal experience-depth rubric."""
    if isinstance(source, Path):
        payload = json.loads(source.read_text(encoding="utf-8"))
    elif isinstance(source, Mapping):
        payload = dict(source)
    else:
        raise ValueError("rubric source must be a Path or mapping")

    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported rubric schema_version")
    if payload.get("rubric_id") != "experience-depth-v1":
        raise ValueError("unsupported rubric_id")
    if payload.get("version") != 1:
        raise ValueError("unsupported rubric version")

    elements = payload.get("elements")
    if (
        not isinstance(elements, list)
        or len(elements) != len(set(elements))
        or set(elements) != ELEMENT_CODES
    ):
        raise ValueError("elements must use canonical universal element codes")

    claim_types = payload.get("claim_types")
    if not isinstance(claim_types, list):
        raise ValueError("claim_types must be a list")
    codes: set[str] = set()
    for claim_type in claim_types:
        if not isinstance(claim_type, Mapping):
            raise ValueError("claim_types entries must be mappings")
        code = claim_type.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("claim_types code must be a non-empty string")
        if code in codes:
            raise ValueError("duplicate claim type code")
        codes.add(code)
        required_elements = claim_type.get("required_elements")
        if not isinstance(required_elements, list) or tuple(required_elements) != CLAIM_TYPES.get(code):
            raise ValueError("required_elements must match experience-depth-v1")
    if codes != set(CLAIM_TYPES):
        raise ValueError("claim_types must use canonical experience-depth-v1 codes")
    return payload


def validate_documents(documents: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Validate inference-only source documents and return normalized copies."""
    if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
        raise ValueError("documents must be a sequence")
    validated: list[dict[str, str]] = []
    document_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping):
            raise ValueError("documents entries must be mappings")
        document_id = document.get("document_id")
        document_type = document.get("document_type")
        text = document.get("text")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        document_id = document_id.strip()
        if document_id in document_ids:
            raise ValueError("duplicate document_id")
        if document_type not in DOCUMENT_TYPES:
            raise ValueError("unsupported document_type")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        document_ids.add(document_id)
        validated.append({"document_id": document_id, "document_type": document_type, "text": text})
    return validated


def validate_experience_analysis_output(
    output: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
    rubric: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate universal experience claims against user-authored evidence."""
    validated_documents = validate_documents(documents)
    validated_rubric = load_experience_rubric(rubric)
    payload = _require_mapping(output, "output")
    _require_exact_fields(payload, {"analysis_status", "rubric", "findings", "model_metadata"}, "output")
    analysis_status = _require_string(payload["analysis_status"], "analysis_status")
    if analysis_status not in {"COMPLETED", "NO_EXPERIENCE_CLAIM"}:
        raise ValueError("unsupported analysis_status")
    _validate_output_rubric(payload["rubric"], validated_rubric)
    findings = _require_list(payload["findings"], "findings")
    _validate_model_metadata(payload["model_metadata"])
    if analysis_status == "NO_EXPERIENCE_CLAIM" and findings:
        raise ValueError("NO_EXPERIENCE_CLAIM requires empty findings")
    if analysis_status == "COMPLETED" and not findings:
        raise ValueError("COMPLETED requires findings")

    documents_by_id = {document["document_id"]: document for document in validated_documents}
    rubric_by_claim_type = {item["code"]: item for item in validated_rubric["claim_types"]}
    finding_ids: set[str] = set()
    validated_findings = []
    for finding in findings:
        validated_finding = _validate_finding(finding, documents_by_id, rubric_by_claim_type)
        finding_id = validated_finding["finding_id"]
        if finding_id in finding_ids:
            raise ValueError("duplicate finding_id")
        finding_ids.add(finding_id)
        validated_findings.append(validated_finding)
    return {
        "analysis_status": analysis_status,
        "rubric": dict(payload["rubric"]),
        "findings": validated_findings,
        "model_metadata": dict(payload["model_metadata"]),
    }


def _validate_output_rubric(output_rubric: Any, rubric: Mapping[str, Any]) -> None:
    value = _require_mapping(output_rubric, "rubric")
    _require_exact_fields(value, {"id", "version"}, "rubric")
    _require_string(value["id"], "rubric id")
    if type(value["version"]) is not int or value["version"] < 1:
        raise ValueError("rubric version must be a positive integer")
    if value["id"] != rubric["rubric_id"] or value["version"] != rubric["version"]:
        raise ValueError("output rubric does not match rubric")


def _validate_model_metadata(model_metadata: Any) -> None:
    value = _require_mapping(model_metadata, "model_metadata")
    fields = {"base_model", "base_revision", "adapter", "training_dataset", "prompt_version"}
    _require_exact_fields(value, fields, "model_metadata")
    for field in {"base_model", "base_revision", "prompt_version"}:
        _require_string(value[field], field)
    for field in {"adapter", "training_dataset"}:
        if value[field] is not None:
            _require_string(value[field], field)


def _validate_finding(finding, documents_by_id, rubric_by_claim_type) -> dict[str, Any]:
    value = _require_mapping(finding, "finding")
    fields = {
        "finding_id", "claim_type", "claim", "present_elements",
        "missing_elements", "verdict", "reason", "follow_up_questions",
    }
    _require_exact_fields(value, fields, "finding")
    finding_id = _require_string(value["finding_id"], "finding_id")
    claim_type = _require_string(value["claim_type"], "claim_type")
    if claim_type not in rubric_by_claim_type:
        raise ValueError("unsupported claim_type")
    claim = _validate_claim(value["claim"], documents_by_id)
    present_elements = _validate_present_elements(value["present_elements"], claim["quote"])
    missing_elements = _validate_missing_elements(value["missing_elements"])
    verdict = _require_string(value["verdict"], "verdict")
    if verdict not in VERDICTS:
        raise ValueError("unsupported verdict")
    reason = _require_string(value["reason"], "reason")
    follow_ups = _require_string_list(value["follow_up_questions"], "follow_up_questions")
    if len(follow_ups) > 2:
        raise ValueError("follow_up_questions must contain at most two questions")

    required = set(rubric_by_claim_type[claim_type]["required_elements"])
    present = {item["element"] for item in present_elements}
    missing = set(missing_elements)
    if verdict == "NOT_ASSESSABLE":
        if present_elements or len(missing) != len(missing_elements) or missing != required:
            raise ValueError("NOT_ASSESSABLE requires empty present elements, full missing coverage, and reason")
    else:
        if len(present) != len(present_elements) or len(missing) != len(missing_elements):
            raise ValueError("element coverage is incomplete")
        if present & missing or present | missing != required:
            raise ValueError("element coverage is incomplete")
        expected = "SUFFICIENT" if present == required else "PARTIAL" if "ACTION" in present else "CLAIM_ONLY"
        if verdict != expected:
            raise ValueError("verdict does not match element coverage")
        if verdict == "SUFFICIENT" and follow_ups:
            raise ValueError("SUFFICIENT finding must not contain follow-up questions")
    return {
        "finding_id": finding_id, "claim_type": claim_type, "claim": claim,
        "present_elements": present_elements, "missing_elements": missing_elements,
        "verdict": verdict, "reason": reason, "follow_up_questions": follow_ups,
    }


def _validate_claim(claim, documents_by_id) -> dict[str, Any]:
    value = _require_mapping(claim, "claim")
    _require_exact_fields(value, {"quote", "document_id", "start_offset", "end_offset"}, "claim")
    quote = _require_string(value["quote"], "claim quote")
    document_id = _require_string(value["document_id"], "document_id")
    if document_id not in documents_by_id:
        raise ValueError("unknown document_id")
    start = _require_offset(value["start_offset"], "start_offset")
    end = _require_offset(value["end_offset"], "end_offset")
    text = documents_by_id[document_id]["text"]
    if end < start or end > len(text) or text[start:end] != quote:
        raise ValueError("claim offset does not match quote")
    return {"quote": quote, "document_id": document_id, "start_offset": start, "end_offset": end}


def _validate_present_elements(value, claim_quote) -> list[dict[str, str]]:
    validated = []
    for item in _require_list(value, "present_elements"):
        element = _require_mapping(item, "present_element")
        _require_exact_fields(element, {"element", "quote"}, "present_element")
        code = _require_string(element["element"], "present element")
        quote = _require_string(element["quote"], "present element quote")
        if code not in ELEMENT_CODES:
            raise ValueError("unsupported present element")
        if quote not in claim_quote:
            raise ValueError("present element quote is not inside claim quote")
        validated.append({"element": code, "quote": quote})
    return validated


def _validate_missing_elements(value) -> list[str]:
    elements = _require_string_list(value, "missing_elements")
    if any(element not in ELEMENT_CODES for element in elements):
        raise ValueError("unsupported missing element")
    return elements


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a mapping")
    return value


def _require_exact_fields(value, required_fields, context) -> None:
    if set(value) - required_fields:
        raise ValueError(f"{context} has unknown field")
    if required_fields - set(value):
        raise ValueError(f"{context} is missing required field")


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _require_string_list(value: Any, context: str) -> list[str]:
    return [_require_string(item, context) for item in _require_list(value, context)]


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _require_offset(value: Any, context: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value
