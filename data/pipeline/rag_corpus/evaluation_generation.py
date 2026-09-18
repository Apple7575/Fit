"""원본 XML 근거를 사용한 평가 질문 생성과 독립 검증."""

from __future__ import annotations

from hashlib import sha256
from dataclasses import replace
import json
import re
from typing import Callable

from lxml import etree

from pipeline.business_report.doc import Document
from pipeline.patterns import patterns
from .evaluation_dataset import CATEGORIES, is_substantive_source, validate_candidate
from .evaluation_numeric import performance_candidate
from pipeline.raw_sources.dart_archive import DartArchive, DartDocumentRef
from pipeline.normalize.text import squash


CATEGORY_TERMS = {
    "BUSINESS": ("사업", "제품", "서비스", "매출", "시장"),
    "PERFORMANCE": ("매출액", "영업이익", "당기순이익", "재무", "실적"),
    "TECHNOLOGY_RND": ("연구개발", "연구", "기술", "개발비", "특허"),
    "INVESTMENT_STRATEGY": ("시설투자", "투자", "출자", "신규사업", "전략"),
    "DISCLOSED_RISKS": ("위험", "리스크", "환율", "원재료", "규제", "의존"),
}


def choose_report(refs: list[DartDocumentRef] | tuple[DartDocumentRef, ...], *, as_of: str) -> DartDocumentRef | None:
    cutoff = as_of.replace("-", "")
    eligible = [ref for ref in refs if ref.rcept_dt <= cutoff]
    return max(eligible, key=lambda ref: (ref.rcept_dt, ref.rcept_no), default=None)


def select_parseable_report(
    archive: DartArchive, corp_code: str, *, as_of: str,
) -> tuple[DartDocumentRef, Document, list[dict[str, str]]]:
    cutoff = as_of.replace("-", "")
    refs = sorted(
        (ref for ref in archive.documents(corp_code) if ref.rcept_dt <= cutoff),
        key=lambda ref: (ref.rcept_dt, ref.rcept_no), reverse=True,
    )
    skipped: list[dict[str, str]] = []
    base_patterns = patterns()
    evaluation_patterns = replace(
        base_patterns, rnd=replace(base_patterns.rnd, cell_tags=(*base_patterns.rnd.cell_tags, "TU")),
    )
    for ref in refs:
        try:
            document = Document.from_bytes(archive.read(ref), rcept_no=ref.rcept_no, p=evaluation_patterns)
        except etree.XMLSyntaxError:
            skipped.append({"rcept_no": ref.rcept_no, "rcept_dt": ref.rcept_dt, "reason": "invalid_xml"})
            continue
        return ref, document, skipped
    raise ValueError(f"기준일 이전에 파싱 가능한 사업보고서가 없습니다: {corp_code}")


def choose_tuning_companies(selection: dict[str, object], *, limit: int) -> list[str]:
    if limit < 1:
        raise ValueError("limit는 1 이상이어야 합니다")
    companies = selection.get("companies")
    if not isinstance(companies, list):
        raise ValueError("companies 목록이 없습니다")
    codes = [str(company["corp_code"]) for company in companies if company.get("group") == "tuning"]
    return codes[:limit]


def select_source_units(
    units: list[dict[str, object]], category: str, *, limit: int = 8, max_chars: int = 1200,
) -> list[dict[str, object]]:
    terms = CATEGORY_TERMS[category]
    ranked = []
    for unit in units:
        if not is_substantive_source(unit):
            continue
        title = str(unit["section_title"])
        body = str(unit["text"])
        score = sum(3 for term in terms if term in title) + sum(1 for term in terms if term in body)
        if score > 0 and len(body) <= max_chars:
            ranked.append((score, unit))
    ranked.sort(key=lambda pair: (-pair[0], int(pair[1]["section_index"]), str(pair[1]["source_index"])))
    return [unit for _, unit in ranked[:limit]]


def generate_cases(
    units: list[dict[str, object]], *, corp_code: str, rcept_no: str, published_at: str,
    categories: tuple[str, ...],
    generate: Callable[[str, list[dict[str, object]]], dict[str, object]],
    judge: Callable[[dict[str, object], dict[str, object]], dict[str, object]],
) -> list[dict[str, object]]:
    cases = []
    for category in categories:
        if category not in CATEGORIES:
            raise ValueError(f"알 수 없는 평가 영역: {category}")
        if category == "PERFORMANCE":
            selected = next(((unit, candidate) for unit in select_source_units(
                units, category, limit=len(units),
            ) if (candidate := performance_candidate(unit)) is not None), None)
            if selected is None:
                continue
            source_unit, generated = selected
            sources = [source_unit]
        else:
            sources = select_source_units(units, category, limit=1)
            if not sources:
                continue
            generated = generate(category, sources)
        candidate = {**generated, "corp_code": corp_code, "rcept_no": rcept_no, "category": category}
        source = next((unit for unit in units if all(
            unit[key] == candidate.get(key) for key in ("section_index", "kind", "source_index")
        )), None)
        coordinate_resolution = "DIRECT"
        if source is None:
            quote = squash(str(candidate.get("source_quote") or ""))
            matches = [unit for unit in sources if quote and quote in squash(str(unit["text"]))]
            if len(matches) == 1:
                source = matches[0]
                candidate.update({key: source[key] for key in ("section_index", "kind", "source_index")})
                coordinate_resolution = "UNIQUE_QUOTE_MATCH"
        quote_resolution = "DIRECT"
        if source is not None:
            quote = squash(str(candidate.get("source_quote") or ""))
            source_text = squash(str(source["text"]))
            answer_numbers = set(re.findall(r"\d[\d,]*(?:\.\d+)?", str(candidate.get("answer") or "")))
            quote_numbers = set(re.findall(r"\d[\d,]*(?:\.\d+)?", quote))
            source_numbers = set(re.findall(r"\d[\d,]*(?:\.\d+)?", source_text))
            if source["kind"] == "table_row" and quote and quote in source_text and quote != source_text:
                candidate["source_quote"] = source_text
                quote_resolution = "EXPANDED_TO_TABLE_CONTEXT"
                quote = source_text
                quote_numbers = source_numbers
            if quote and quote in source_text and not answer_numbers.issubset(quote_numbers) and answer_numbers.issubset(source_numbers):
                candidate["source_quote"] = source_text
                quote_resolution = "EXPANDED_TO_SOURCE_UNIT"
        validation = validate_candidate(candidate, units, corp_code=corp_code, rcept_no=rcept_no)
        judge_result = {"supported": False, "reason": "source not found"}
        if validation["status"] == "AUTO_VALIDATED" and source is not None:
            judge_result = judge(candidate, source)
        reasons = list(validation["reasons"])
        if validation["status"] == "AUTO_VALIDATED" and judge_result.get("supported") is not True:
            reasons.append("judge_rejected")
        source_index = candidate.get("source_index")
        source_key = json.dumps({
            "corp_code": corp_code, "rcept_no": rcept_no, "category": category,
            "section_index": candidate.get("section_index"), "kind": candidate.get("kind"),
            "source_index": source_index, "question": candidate.get("question"),
            "answer": candidate.get("answer"), "source_quote": candidate.get("source_quote"),
        }, ensure_ascii=False, sort_keys=True)
        cases.append({
            "case_id": sha256(source_key.encode()).hexdigest()[:20],
            "generation_method": "EXTRACTIVE_NUMERIC" if category == "PERFORMANCE" else "LLM_GENERATED",
            "corp_code": corp_code, "rcept_no": rcept_no, "published_at": published_at,
            "category": category, "question": candidate.get("question"), "answer": candidate.get("answer"),
            "gold_evidence": {
                "rcept_no": rcept_no, "section_index": candidate.get("section_index"),
                "section_title": source.get("section_title") if source else None,
                "kind": candidate.get("kind"), "source_index": source_index,
                "source_quote": candidate.get("source_quote"),
                "fiscal_year": candidate.get("fiscal_year"), "unit": candidate.get("unit"),
                "accounting_basis": candidate.get("accounting_basis"),
                "table_header_text": source.get("table_header_text") if source else None,
                "table_unit_text": source.get("table_unit_text") if source else None,
            },
            "validation_status": "REJECTED" if reasons else "AUTO_VALIDATED",
            "validation_reasons": reasons, "judge_result": judge_result,
            "coordinate_resolution": coordinate_resolution,
            "quote_resolution": quote_resolution,
            "review_status": "PENDING_HUMAN_REVIEW",
        })
    return cases
