"""기존 검색 평가 후보의 근거 부족 위험을 보수적으로 표시한다."""

from __future__ import annotations

import re


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_YEAR = re.compile(r"\b(20\d{2})년")


def audit_case(case: dict[str, object]) -> dict[str, object]:
    result = {"case_id": case["case_id"], "audit_status": "REVIEWABLE", "reasons": []}
    if case.get("validation_status") != "AUTO_VALIDATED":
        result["audit_status"] = "REJECTED_ORIGINAL"
        return result

    question = str(case.get("question") or "")
    answer = str(case.get("answer") or "")
    evidence = case.get("gold_evidence") or {}
    quote = str(evidence.get("source_quote") or "")
    reasons: list[str] = []

    if evidence.get("kind") == "table_row":
        reasons.append(
            "table_numeric_context_unverified" if _NUMBER.search(question + answer)
            else "table_column_context_unverified"
        )
    if "전체 매출 중" in question + answer and "전체 매출" not in quote:
        reasons.append("denominator_not_explicit")
    published_year = int(str(case.get("published_at") or "")[:4] or 0)
    if any(int(year) > published_year for year in _YEAR.findall(question + answer)):
        reasons.append("year_after_publication")

    result["reasons"] = reasons
    if reasons:
        result["audit_status"] = "NEEDS_CONTEXT"
    return result
