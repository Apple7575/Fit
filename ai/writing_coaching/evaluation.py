from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import CANONICAL_DIMENSIONS, WritingMessageRequest


REQUIRED_STATUSES = {"REVISED", "ANSWERED", "CLARIFICATION_REQUIRED"}
REQUIRED_STRENGTHS = {"LIGHT", "BALANCED", "REWRITE"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate the fixed human-review writing evaluation cases."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read writing evaluation cases: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("writing evaluation cases must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 12:
        raise ValueError("writing evaluation requires at least 12 cases")

    ids: list[str | None] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every writing evaluation case must be an object")
        ids.append(case.get("case_id"))
    if any(not isinstance(case_id, str) or not case_id.strip() for case_id in ids):
        raise ValueError("every writing case requires case_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate writing evaluation case_id")

    for case in cases:
        if case.get("label_status") != "DRAFT":
            raise ValueError("writing cases remain DRAFT until human approval")
        try:
            WritingMessageRequest.model_validate(case.get("request"))
        except (TypeError, ValueError) as exc:
            raise ValueError("writing case request does not match API contract") from exc
        expected_status = case.get("expected_status")
        if expected_status not in REQUIRED_STATUSES:
            raise ValueError("unknown expected_status")
        if (
            expected_status == "REVISED"
            and case.get("expected_strength") not in REQUIRED_STRENGTHS
        ):
            raise ValueError("revised cases require expected_strength")

        expectations = case.get("review_expectations")
        if not isinstance(expectations, list) or not expectations:
            raise ValueError("review_expectations must be a list")
        dimensions = []
        for expectation in expectations:
            if not isinstance(expectation, dict):
                raise ValueError("review_expectations items must be objects")
            dimension = expectation.get("dimension")
            description = expectation.get("expectation")
            if not isinstance(dimension, str) or dimension not in CANONICAL_DIMENSIONS:
                raise ValueError("review_expectations contains an unknown dimension")
            if not isinstance(description, str) or not description.strip():
                raise ValueError("review_expectations expectation must be non-blank")
            dimensions.append(dimension)
        if dimensions != list(CANONICAL_DIMENSIONS):
            raise ValueError("review_expectations must match canonical dimensions")

        forbidden_outputs = case.get("forbidden_outputs")
        if not isinstance(forbidden_outputs, list) or not forbidden_outputs:
            raise ValueError("forbidden_outputs must be a non-empty list")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in forbidden_outputs
        ):
            raise ValueError("forbidden_outputs must contain non-blank strings")

    return cases
