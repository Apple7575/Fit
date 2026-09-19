"""사업보고서 원본 좌표에 고정된 검색 평가 후보를 만든다."""

from __future__ import annotations

import re

from pipeline.business_report.doc import Document
from pipeline.normalize.text import squash


CATEGORIES = frozenset({
    "BUSINESS", "PERFORMANCE", "TECHNOLOGY_RND", "INVESTMENT_STRATEGY", "DISCLOSED_RISKS",
})
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_UNIT_CONTEXT = re.compile(r"단위\s*[:：]\s*[^)\]|]{1,60}")
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?=\s*(?:년|연도)|\b)")
_FACT_ENDING = re.compile(r"(?:다|요|함|됨)[.!?]?\s*$")


def is_substantive_source(unit: dict[str, object]) -> bool:
    if unit["kind"] == "table_row":
        return True
    return bool(_FACT_ENDING.search(squash(str(unit["text"]))))


def _table_unit_text(document: Document, table_index: int) -> str:
    lookback = document.p.rnd.unit_lookback_tables
    for index in range(table_index, max(-1, table_index - lookback - 1), -1):
        table = document.tables[index]
        match = _UNIT_CONTEXT.search(table.caption + " " + table.head(3))
        if match:
            return squash(match.group())
    return ""


def extract_source_units(document: Document) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    for section_index, section in enumerate(document.sections):
        for paragraph in section.paragraph_entries:
            text = squash(paragraph.text)
            if text:
                units.append({
                    "section_index": section_index, "section_title": section.title,
                    "kind": "paragraph", "source_index": paragraph.index, "text": text,
                })
        for table in section.tables:
            if table.excluded_reason or not table.m:
                continue
            header_rows = table.header_rows or 1
            header = "\n".join(" | ".join(squash(cell) for cell in row)
                               for row in table.m[:header_rows])
            unit_text = _table_unit_text(document, table.idx)
            for row_index, row in enumerate(table.m[header_rows:], start=header_rows):
                row_text = " | ".join(squash(cell) for cell in row)
                text = "\n".join(part for part in (unit_text, header, row_text) if part)
                if text.strip(" |\n"):
                    units.append({
                        "section_index": section_index, "section_title": section.title,
                        "kind": "table_row", "source_index": f"{table.idx}:{row_index}", "text": text,
                        "table_header_text": header, "table_unit_text": unit_text,
                    })
    return units


def validate_candidate(
    candidate: dict[str, object], units: list[dict[str, object]], *, corp_code: str, rcept_no: str,
) -> dict[str, object]:
    reasons: list[str] = []
    if candidate.get("corp_code") != corp_code:
        reasons.append("company_mismatch")
    if candidate.get("rcept_no") != rcept_no:
        reasons.append("receipt_mismatch")
    if candidate.get("category") not in CATEGORIES:
        reasons.append("invalid_category")
    if not str(candidate.get("question") or "").strip() or not str(candidate.get("answer") or "").strip():
        reasons.append("missing_question_or_answer")
    unit = next((item for item in units if all(
        item[key] == candidate.get(key) for key in ("section_index", "kind", "source_index")
    )), None)
    if unit is None:
        reasons.append("source_unit_not_found")
    elif not is_substantive_source(unit):
        reasons.append("heading_only_source")
    quote = squash(str(candidate.get("source_quote") or ""))
    answer_numbers = set(_NUMBER.findall(str(candidate.get("answer") or "")))
    if not quote or unit is None or quote not in squash(str(unit["text"])):
        reasons.append("quote_not_in_source")
    claim = str(candidate.get("question") or "") + " " + str(candidate.get("answer") or "")
    if re.search(r"명시되지|확인할 수 없|기재되지", str(candidate.get("answer") or "")):
        reasons.append("missing_value_answer")
    if re.search(r"\d[\d,.]*\s*%", claim) and not re.search(r"%|퍼센트", quote):
        reasons.append("percent_unit_not_in_quote")
    if candidate.get("category") == "BUSINESS" and "시장" in claim and unit is not None and unit["kind"] == "paragraph" \
            and not re.search(r"당사|자사|동사|회사|기업", quote):
        reasons.append("market_context_not_company_fact")
    claim_years = set(_YEAR.findall(claim))
    fiscal_year = str(candidate.get("fiscal_year") or "")
    if fiscal_year:
        claim_years.update(_YEAR.findall(fiscal_year))
    if claim_years - set(_YEAR.findall(quote)):
        reasons.append("claim_year_not_in_quote")
    basis = str(candidate.get("accounting_basis") or "").upper()
    required_basis = "연결" if basis == "CONSOLIDATED" or "연결" in claim else (
        "별도" if basis == "SEPARATE" or "별도" in claim else ""
    )
    if required_basis and required_basis not in quote:
        reasons.append("accounting_basis_not_in_quote")
    if any(term in claim for term in ("전년 대비", "전기 대비")) and not any(
        term in quote for term in ("전년 대비", "전기 대비")
    ):
        reasons.append("comparison_not_in_quote")
    if re.search(r"전체\s*매출(?:액)?\s*(?:중|대비)", claim) and not re.search(
        r"전체\s*매출(?:액)?", quote,
    ):
        reasons.append("denominator_not_explicit")
    if unit is not None and unit["kind"] == "table_row":
        header = squash(str(unit.get("table_header_text") or ""))
        unit_text = squash(str(unit.get("table_unit_text") or ""))
        answer = squash(str(candidate.get("answer") or ""))
        if answer and any(answer == squash(cell) for row in header.split("\n") for cell in row.split("|")):
            reasons.append("header_as_answer")
        if (header and header not in quote) or (unit_text and unit_text not in quote):
            reasons.append("table_context_not_in_quote")
        if _NUMBER.search(str(candidate.get("answer") or "")):
            if not unit_text:
                reasons.append("table_unit_not_verified")
            elif "," in unit_text or "，" in unit_text:
                reasons.append("table_unit_ambiguous")
            declared_unit = str(candidate.get("unit") or "").strip()
            source_unit = unit_text.replace("：", ":").split(":", 1)[-1].strip()
            compact_answer = re.sub(r"\s+", "", str(candidate.get("answer") or ""))
            answer_has_unit = declared_unit and any(
                number + declared_unit in compact_answer for number in answer_numbers
            )
            if not declared_unit or (unit_text and declared_unit != source_unit) or not answer_has_unit:
                reasons.append("table_answer_unit_mismatch")
    quote_numbers = set(_NUMBER.findall(quote))
    if answer_numbers and not answer_numbers.issubset(quote_numbers):
        reasons.append("number_not_in_quote")
    if candidate.get("category") == "PERFORMANCE" and answer_numbers and any(
        not str(candidate.get(key) or "").strip() for key in ("fiscal_year", "unit", "accounting_basis")
    ):
        reasons.append("missing_numeric_context")
    if candidate.get("category") == "PERFORMANCE" and answer_numbers and any(
        value and value not in quote for value in (
            str(candidate.get("fiscal_year") or ""), str(candidate.get("unit") or ""),
        )
    ):
        reasons.append("numeric_context_not_in_quote")
    return {
        "status": "REJECTED" if reasons else "AUTO_VALIDATED",
        "review_status": "PENDING_HUMAN_REVIEW",
        "reasons": reasons,
    }
