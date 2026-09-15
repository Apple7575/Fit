import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


ELEMENT_CODES = {
    "PROBLEM",
    "ROLE",
    "ACTION",
    "REASONING",
    "MECHANISM",
    "VERIFICATION",
    "RESULT",
}
VERDICTS = {"SUFFICIENT", "PARTIAL", "CLAIM_ONLY", "NOT_ASSESSABLE"}
DOCUMENT_TYPES = {"RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"}
BACKEND_V1_EXPERIENCE_TYPES = {
    "API_DESIGN": ("PROBLEM", "ROLE", "ACTION", "REASONING", "VERIFICATION"),
    "DATABASE": ("PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"),
    "CONCURRENCY": ("PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"),
    "CACHE_PERFORMANCE": ("PROBLEM", "ACTION", "MECHANISM", "VERIFICATION", "RESULT"),
    "MESSAGING": ("PROBLEM", "ACTION", "MECHANISM", "VERIFICATION"),
    "RELIABILITY": ("PROBLEM", "ACTION", "REASONING", "VERIFICATION", "RESULT"),
    "OBSERVABILITY": ("PROBLEM", "ACTION", "MECHANISM", "RESULT"),
    "SECURITY": ("PROBLEM", "ACTION", "REASONING", "VERIFICATION"),
    "OTHER_BACKEND": ("PROBLEM", "ROLE", "ACTION", "RESULT"),
}


def load_position_profile(source: Path | Mapping[str, Any]) -> dict[str, Any]:
    """Load and validate the sole supported position profile."""
    if isinstance(source, Path):
        payload = json.loads(source.read_text(encoding="utf-8"))
    elif isinstance(source, Mapping):
        payload = dict(source)
    else:
        raise ValueError("profile source must be a Path or mapping")

    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported profile schema_version")
    if payload.get("profile_id") != "backend-v1":
        raise ValueError("unsupported profile_id")
    if payload.get("position") != "BACKEND" or payload.get("version") != 1:
        raise ValueError("unsupported backend-v1 profile")

    experience_types = payload.get("experience_types")
    if not isinstance(experience_types, list):
        raise ValueError("experience_types must be a list")

    codes: set[str] = set()
    for experience_type in experience_types:
        if not isinstance(experience_type, Mapping):
            raise ValueError("experience_types entries must be mappings")
        code = experience_type.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("experience_types code must be a non-empty string")
        if code in codes:
            raise ValueError("duplicate experience type code")
        codes.add(code)

        required_elements = experience_type.get("required_elements")
        if not isinstance(required_elements, list) or not all(
            isinstance(element, str) and element in ELEMENT_CODES
            for element in required_elements
        ):
            raise ValueError("required_elements must contain known element codes")

        expected_required_elements = BACKEND_V1_EXPERIENCE_TYPES.get(code)
        if (
            expected_required_elements is not None
            and tuple(required_elements) != expected_required_elements
        ):
            raise ValueError("required_elements must match backend-v1")

    if codes != set(BACKEND_V1_EXPERIENCE_TYPES):
        raise ValueError("experience_types must use canonical backend-v1 codes")

    return payload


def validate_documents(documents: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Validate inference-only source documents and return normalized copies."""
    if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
        raise ValueError("documents must be a sequence")

    validated_documents: list[dict[str, str]] = []
    document_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping):
            raise ValueError("documents entries must be mappings")

        document_id = document.get("document_id")
        document_type = document.get("document_type")
        text = document.get("text")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string")
        normalized_document_id = document_id.strip()
        if normalized_document_id in document_ids:
            raise ValueError("duplicate document_id")
        if document_type not in DOCUMENT_TYPES:
            raise ValueError("unsupported document_type")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        document_ids.add(normalized_document_id)
        validated_documents.append(
            {
                "document_id": normalized_document_id,
                "document_type": document_type,
                "text": text,
            }
        )

    return validated_documents


def validate_analysis_output(
    output: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate model analysis evidence against user documents and position policy."""
    validated_documents = validate_documents(documents)
    validated_profile = load_position_profile(profile)
    payload = _require_mapping(output, "output")

    _require_exact_fields(
        payload,
        {
            "analysis_status",
            "position_profile",
            "findings",
            "model_metadata",
        },
        "output",
    )
    analysis_status = _require_string(payload["analysis_status"], "analysis_status")
    if analysis_status not in {"COMPLETED", "NO_TECHNICAL_CLAIM"}:
        raise ValueError("unsupported analysis_status")

    _validate_output_profile(payload["position_profile"], validated_profile)
    findings = _require_list(payload["findings"], "findings")
    _validate_model_metadata(payload["model_metadata"])

    if analysis_status == "NO_TECHNICAL_CLAIM" and findings:
        raise ValueError("NO_TECHNICAL_CLAIM requires empty findings")
    if analysis_status == "COMPLETED" and not findings:
        raise ValueError("COMPLETED requires findings")

    documents_by_id = {
        document["document_id"]: document for document in validated_documents
    }
    profile_by_type = {
        item["code"]: item for item in validated_profile["experience_types"]
    }
    finding_ids: set[str] = set()
    validated_findings: list[dict[str, Any]] = []
    for finding in findings:
        validated_finding = _validate_finding(
            finding,
            documents_by_id,
            profile_by_type,
        )
        finding_id = validated_finding["finding_id"]
        if finding_id in finding_ids:
            raise ValueError("duplicate finding_id")
        finding_ids.add(finding_id)
        validated_findings.append(validated_finding)

    return {
        "analysis_status": analysis_status,
        "position_profile": dict(payload["position_profile"]),
        "findings": validated_findings,
        "model_metadata": dict(payload["model_metadata"]),
    }


def _validate_output_profile(
    output_profile: Any,
    profile: Mapping[str, Any],
) -> None:
    value = _require_mapping(output_profile, "position_profile")
    _require_exact_fields(value, {"id", "version"}, "position_profile")
    _require_string(value["id"], "position_profile id")
    if type(value["version"]) is not int or value["version"] < 1:
        raise ValueError("position_profile version must be a positive integer")
    if value["id"] != profile["profile_id"] or value["version"] != profile["version"]:
        raise ValueError("position_profile does not match profile")


def _validate_model_metadata(model_metadata: Any) -> None:
    value = _require_mapping(model_metadata, "model_metadata")
    _require_exact_fields(
        value,
        {
            "base_model",
            "base_revision",
            "adapter",
            "training_dataset",
            "prompt_version",
        },
        "model_metadata",
    )
    for field in {"base_model", "base_revision", "prompt_version"}:
        _require_string(value[field], field)
    for field in {"adapter", "training_dataset"}:
        if value[field] is not None:
            _require_string(value[field], field)


def _validate_finding(
    finding: Any,
    documents_by_id: Mapping[str, Mapping[str, str]],
    profile_by_type: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    value = _require_mapping(finding, "finding")
    _require_exact_fields(
        value,
        {
            "finding_id",
            "experience_type",
            "claim",
            "present_elements",
            "missing_elements",
            "verdict",
            "reason",
            "follow_up_questions",
        },
        "finding",
    )
    finding_id = _require_string(value["finding_id"], "finding_id")
    experience_type = _require_string(value["experience_type"], "experience_type")
    if experience_type not in profile_by_type:
        raise ValueError("unsupported experience_type")

    claim = _validate_claim(value["claim"], documents_by_id)
    present_elements = _validate_present_elements(value["present_elements"], claim["quote"])
    missing_elements = _validate_missing_elements(value["missing_elements"])
    verdict = _require_string(value["verdict"], "verdict")
    if verdict not in VERDICTS:
        raise ValueError("unsupported verdict")
    reason = _require_string(value["reason"], "reason")
    follow_up_questions = _require_string_list(
        value["follow_up_questions"], "follow_up_questions"
    )
    if len(follow_up_questions) > 2:
        raise ValueError("follow_up_questions must contain at most two questions")

    required = set(profile_by_type[experience_type]["required_elements"])
    present = {item["element"] for item in present_elements}
    missing = set(missing_elements)

    if verdict == "NOT_ASSESSABLE":
        if (
            present_elements
            or len(missing) != len(missing_elements)
            or missing != required
            or not reason.strip()
        ):
            raise ValueError("NOT_ASSESSABLE requires empty present elements, full missing coverage, and reason")
    else:
        if len(present) != len(present_elements) or len(missing) != len(missing_elements):
            raise ValueError("element coverage is incomplete")
        if present & missing or present | missing != required:
            raise ValueError("element coverage is incomplete")
        expected_verdict = (
            "SUFFICIENT" if present == required
            else "PARTIAL" if "ACTION" in present
            else "CLAIM_ONLY"
        )
        if verdict != expected_verdict:
            raise ValueError("verdict does not match element coverage")
        if verdict == "SUFFICIENT" and follow_up_questions:
            raise ValueError("SUFFICIENT finding must not contain follow-up questions")

    return {
        "finding_id": finding_id,
        "experience_type": experience_type,
        "claim": claim,
        "present_elements": present_elements,
        "missing_elements": missing_elements,
        "verdict": verdict,
        "reason": reason,
        "follow_up_questions": follow_up_questions,
    }


def _validate_claim(
    claim: Any,
    documents_by_id: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    value = _require_mapping(claim, "claim")
    _require_exact_fields(
        value,
        {"quote", "document_id", "start_offset", "end_offset"},
        "claim",
    )
    quote = _require_string(value["quote"], "claim quote")
    document_id = _require_string(value["document_id"], "document_id")
    if document_id not in documents_by_id:
        raise ValueError("unknown document_id")
    start_offset = _require_offset(value["start_offset"], "start_offset")
    end_offset = _require_offset(value["end_offset"], "end_offset")
    text = documents_by_id[document_id]["text"]
    if end_offset < start_offset or end_offset > len(text):
        raise ValueError("invalid claim offset")
    if text[start_offset:end_offset] != quote:
        raise ValueError("claim offset does not match quote")
    return {
        "quote": quote,
        "document_id": document_id,
        "start_offset": start_offset,
        "end_offset": end_offset,
    }


def _validate_present_elements(present_elements: Any, claim_quote: str) -> list[dict[str, str]]:
    values = _require_list(present_elements, "present_elements")
    validated: list[dict[str, str]] = []
    for present_element in values:
        value = _require_mapping(present_element, "present_element")
        _require_exact_fields(value, {"element", "quote"}, "present_element")
        element = _require_string(value["element"], "present element")
        if element not in ELEMENT_CODES:
            raise ValueError("unsupported present element")
        quote = _require_string(value["quote"], "present element quote")
        if quote not in claim_quote:
            raise ValueError("present element quote is not inside claim quote")
        validated.append({"element": element, "quote": quote})
    return validated


def _validate_missing_elements(missing_elements: Any) -> list[str]:
    values = _require_string_list(missing_elements, "missing_elements")
    if any(element not in ELEMENT_CODES for element in values):
        raise ValueError("unsupported missing element")
    return values


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a mapping")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    required_fields: set[str],
    context: str,
) -> None:
    actual_fields = set(value)
    unknown_fields = actual_fields - required_fields
    if unknown_fields:
        raise ValueError(f"{context} has unknown field")
    missing_fields = required_fields - actual_fields
    if missing_fields:
        raise ValueError(f"{context} is missing required field")


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _require_string_list(value: Any, context: str) -> list[str]:
    values = _require_list(value, context)
    return [_require_string(item, context) for item in values]


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _require_offset(value: Any, context: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value
