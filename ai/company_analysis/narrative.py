"""LLM 서술 블록. 결정적 리포트 위에 사업보고서 원문 근거로 쓴 문장을 덧붙인다.

섹션마다 (넣을 절, 채울 블록, 지시문) 계획이 고정되어 있고, 출력은 JSON 스키마로 강제한다.
citation_ids 는 이번 호출에 넣어 준 근거 ID 만 enum 으로 허용하므로 없는 근거를 인용할 수 없다.
생성 뒤 claim_check 로 숫자를 대조해 위반 문장을 버린다. 서술이 전부 버려지면 그 블록은
넣지 않고 warnings 에 남긴다 — 결정적 블록은 그대로 살아 있다.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .claim_check import CitedText, numeric_claim_violations, share_claim_violations
from .contracts import (
    SECTION_TITLES,
    BulletItem,
    BulletsBlock,
    Citation,
    CompanyReport,
    ReportSection,
    ReportSource,
    SwotBlock,
    SwotQuadrant,
    TableBlock,
    TextBlock,
)
from .evidence import BusinessReport, BusinessReportRepository, EvidenceChunk
from .facts import CompanyFacts
from .llm import StructuredCompletionClient

LOGGER = logging.getLogger("ai.company_analysis.narrative")
PROMPT_PATH = Path(__file__).parent / "resources" / "prompts" / "narrative-v1.md"

# GPU 서버의 Qwen3-32B-AWQ 는 max_model_len 12,288 토큰이다. 한국어는 대략 1.3자/토큰이므로
# 입력(프롬프트 ~1,500자 + 근거) 과 출력을 합쳐 그 안에 들어야 한다. 근거는 호출당 6,500자 안팎으로
# 자르고, 큰 섹션은 여러 호출로 나눈다. INTRO 실측: 근거 12,548자 → 입력 9,289토큰으로 400 이 났다.
MAX_OUTPUT_TOKENS = 2_200
MAX_EVIDENCE_CHARS = 6_500
MAX_ITEMS = 5
MAX_CHUNK_CHARS = 1_300
TABLE_TRUNCATION_MARK = "(표 일부 생략)"

BlockKind = Literal["text", "bullets"]


@dataclass(frozen=True)
class BlockSpec:
    key: str
    kind: BlockKind
    title: str
    purpose: str


@dataclass(frozen=True)
class SectionPlan:
    name: str
    section: str  # BUSINESS | FINANCIALS | COMPETITORS | SWOT | INTRO
    text_patterns: tuple[str, ...]
    table_patterns: tuple[str, ...]
    blocks: tuple[BlockSpec, ...]
    text_budget: int = 5_500
    table_budget: int = 1_000
    # 결정적 표를 근거로 함께 넣을지
    include_metric_tables: bool = False
    include_peer_table: bool = False
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    max_items: int = MAX_ITEMS


MDA_TEXT = (r"재무상태 및 영업실적", r"유동성 및 자금조달", r"요약재무정보", r"그 밖에 투자의사결정")

PLANS: dict[str, SectionPlan] = {
    "INTRO": SectionPlan(
        name="INTRO",
        section="INTRO",
        text_patterns=(r"사업의 개요", r"주요 제품 및 서비스"),
        table_patterns=(),
        blocks=(
            BlockSpec(
                "intro", "text", "기업 소개",
                "기업이 무엇을 하는 회사인지, 핵심 제품과 시장 지위, 최근 실적과 강점을 4~6문장으로 소개한다. "
                "`metrics:` 근거의 최신 연도 매출·영업이익 숫자를 단위와 함께 한 번 언급한다.",
            ),
        ),
        text_budget=3_500,
        include_metric_tables=True,
    ),
    "BUSINESS_CORE": SectionPlan(
        name="BUSINESS_CORE",
        section="BUSINESS",
        text_patterns=(r"사업의 개요", r"주요 제품 및 서비스", r"기타 참고사항"),
        table_patterns=(r"주요 제품 및 서비스",),
        blocks=(
            BlockSpec("overview", "text", "주요 사업 내용", "주력 사업과 제품군, 사업 구조를 3~5문장으로 설명한다."),
            BlockSpec("units", "bullets", "사업 부문별 상세", "제품군·사업 부문별로 무엇을 만들고 어떤 시장·고객을 대상으로 하는지, 기술·시장 지위를 항목으로 쓴다."),
        ),
    ),
    "BUSINESS_GROWTH": SectionPlan(
        name="BUSINESS_GROWTH",
        section="BUSINESS",
        text_patterns=(r"매출 및 수주", r"주요계약 및 연구개발", r"원재료 및 생산설비", r"기타 참고사항"),
        table_patterns=(r"매출 및 수주", r"주요계약 및 연구개발"),
        blocks=(
            BlockSpec("growth", "bullets", "성장 동력과 신사업", "근거에 나온 신제품, 신사업, 수주·계약, 연구개발 성과, 투자·증설 계획을 항목으로 쓴다. 계획과 완료를 구분한다."),
        ),
        table_budget=1_500,
    ),
    "FINANCIALS": SectionPlan(
        name="FINANCIALS",
        section="FINANCIALS",
        text_patterns=MDA_TEXT,
        table_patterns=(),
        blocks=(
            BlockSpec("summary", "text", "재무 추이 요약", "`metrics:` 근거의 3개년 수치로 매출·이익 흐름과 전환점을 2~3문장으로 요약한다."),
            BlockSpec("growth", "bullets", "매출 성장성", "매출 성장률과 그 배경(경영진 해설에 있는 원인)을 항목으로 쓴다."),
            BlockSpec("profitability", "bullets", "수익성", "영업이익률·순이익률·ROE 추이와 R&D 비중을 항목으로 쓴다."),
            BlockSpec("health", "bullets", "재무 건전성", "부채비율·자본총계 추이, 유동성·자금조달 관련 사실을 항목으로 쓴다."),
        ),
        text_budget=4_500,
        include_metric_tables=True,
    ),
    "COMPETITORS_MARKET": SectionPlan(
        name="COMPETITORS_MARKET",
        section="COMPETITORS",
        text_patterns=(r"기타 참고사항",),
        table_patterns=(r"기타 참고사항",),
        blocks=(
            BlockSpec("landscape", "text", "산업과 경쟁 구도", "산업의 특성, 시장 규모·성장, 시장점유율과 경쟁 구도를 3~5문장으로 설명한다."),
            BlockSpec("edge", "bullets", "경쟁 요소와 회사의 경쟁력", "근거가 말하는 시장의 핵심 경쟁 요소와 이 기업의 경쟁력을 항목으로 쓴다."),
        ),
        table_budget=1_200,
    ),
    "COMPETITORS_POSITION": SectionPlan(
        name="COMPETITORS_POSITION",
        section="COMPETITORS",
        text_patterns=(r"사업의 개요", r"기타 참고사항"),
        table_patterns=(),
        blocks=(
            BlockSpec("positioning", "bullets", "포지셔닝과 동일 산업 비교", "`peers:` 근거의 국내 상장사 비교표와 원문을 바탕으로 이 기업의 위치와 차별점을 항목으로 쓴다. 비교표에 없는 기업은 언급하지 않는다."),
        ),
        text_budget=3_500,
        include_metric_tables=True,
        include_peer_table=True,
    ),
    "SWOT": SectionPlan(
        name="SWOT",
        section="SWOT",
        text_patterns=(r"기타 참고사항", r"위험관리 및 파생거래", r"사업의 개요"),
        table_patterns=(),
        blocks=(),
        text_budget=4_000,
        include_metric_tables=True,
        include_peer_table=True,
        # SWOT 은 네 칸을 한 번에 쓰므로 출력이 길다. 2,200 토큰에서 JSON 이 잘렸다(SK하이닉스 v3).
        max_output_tokens=3_200,
        max_items=4,
    ),
}

SWOT_QUADRANTS = (
    ("strengths", "Strengths (강점)", "기술·제품·시장 지위·재무에서 근거로 확인되는 강점"),
    ("weaknesses", "Weaknesses (약점)", "사업 구조 의존도, 수익 변동성, 재무 부담 등 근거로 확인되는 약점"),
    ("opportunities", "Opportunities (기회)", "근거가 말하는 시장 성장, 신제품·신사업, 수요 변화"),
    ("threats", "Threats (위협)", "근거가 말하는 경쟁 심화, 시황·환율·규제 등 외부 위험"),
)


# --- 근거 렌더링 -------------------------------------------------------------


@dataclass
class EvidenceBundle:
    payload: list[dict[str, Any]] = field(default_factory=list)
    citations: dict[str, Citation] = field(default_factory=dict)
    cited_texts: dict[str, CitedText] = field(default_factory=dict)

    def add(
        self,
        evidence_id: str,
        *,
        kind: str,
        title: str,
        content: str,
        citation: Citation,
        unit: str | None = None,
        is_table: bool = False,
        money_table: bool | None = None,
    ) -> None:
        """money_table 이 False 면 숫자 존재만 검사하고 금액 단위 규칙은 건너뛴다(직원 수가 섞인 확정 지표 표)."""
        if evidence_id in self.citations:
            return
        entry = {"evidence_id": evidence_id, "kind": kind, "title": title, "content": content}
        if unit:
            entry["unit"] = unit
        self.payload.append(entry)
        self.citations[evidence_id] = citation
        header = next((line for line in content.splitlines() if line.startswith("표 머리글:")), "")
        check_as_table = is_table if money_table is None else money_table
        self.cited_texts[evidence_id] = CitedText(evidence_id, content, is_table=check_as_table, unit=unit if check_as_table else None, header=header)

    @property
    def ids(self) -> list[str]:
        return list(self.citations)


def _truncate_chunk(chunk: EvidenceChunk) -> str:
    content = chunk.content
    if len(content) <= MAX_CHUNK_CHARS:
        return content
    cut = content[:MAX_CHUNK_CHARS]
    if not chunk.is_table:
        return cut
    boundary = cut.rfind("\n")
    if boundary > 0:
        cut = cut[:boundary]
    return f"{cut}\n{TABLE_TRUNCATION_MARK}"


def _add_chunks(bundle: EvidenceBundle, chunks: Sequence[EvidenceChunk]) -> None:
    for chunk in chunks:
        content = _truncate_chunk(chunk)
        if chunk.is_table and chunk.unit:
            content = f"표 단위: {chunk.unit}\n{content}"
        bundle.add(
            chunk.evidence_id,
            kind="TABLE" if chunk.is_table else "TEXT",
            title=f"{chunk.report_name} · {chunk.section_title}".strip(" ·"),
            content=content,
            citation=chunk.citation(),
            unit=chunk.unit,
            is_table=chunk.is_table,
        )


def _render_table(table: TableBlock) -> str:
    lines = [f"표 머리글: {' | '.join(table.columns)}"]
    for row in table.rows:
        lines.append(" | ".join("" if cell is None else str(cell) for cell in row))
    return "\n".join(lines)


def _add_metric_tables(bundle: EvidenceBundle, report: CompanyReport) -> None:
    corp = report.corp_code
    for section in report.sections:
        if section.type not in ("FINANCIALS", "BUSINESS"):
            continue
        for block in section.blocks:
            if block.kind == "table" and block.title in ("재무 추이", "산출 지표"):
                key = "financials" if block.title == "재무 추이" else "ratios"
                unit = block.unit if key == "financials" else "%"
                bundle.add(
                    f"metrics:{corp}:{key}",
                    kind="TABLE",
                    title=f"확정 지표 · {block.title} (단위: {unit})",
                    content=f"표 단위: {unit}\n{_render_table(block)}",
                    citation=Citation(source_type="COMPANY_METRIC", source_id=f"{corp}:{key}"),
                    unit=unit,
                    is_table=True,
                    money_table=False,
                )
            if block.kind == "kpi":
                content = "\n".join(
                    f"{item.label}: {item.value}{item.unit or ''}"
                    + (f" (전년 대비 {item.delta_pct:+}%)" if item.delta_pct is not None else "")
                    + (f" ({item.note})" if item.note else "")
                    for item in block.items
                )
                bundle.add(
                    f"metrics:{corp}:kpi",
                    kind="TEXT",
                    title="확정 지표 · 최신 연도 핵심 수치",
                    content=content,
                    citation=Citation(source_type="COMPANY_METRIC", source_id=f"{corp}:kpi"),
                )


def _add_peer_table(bundle: EvidenceBundle, report: CompanyReport) -> None:
    for section in report.sections:
        if section.type != "COMPETITORS":
            continue
        for block in section.blocks:
            if block.kind == "table":
                bundle.add(
                    f"peers:{report.corp_code}",
                    kind="TABLE",
                    title=f"확정 지표 · {block.title}",
                    content=f"표 단위: {block.unit}\n{_render_table(block)}",
                    citation=Citation(source_type="INDUSTRY_PEER", source_id=f"{report.corp_code}:peers"),
                    unit=block.unit,
                    is_table=True,
                    money_table=False,
                )


def build_bundle(plan: SectionPlan, business_report: BusinessReport | None, report: CompanyReport) -> EvidenceBundle:
    bundle = EvidenceBundle()
    if plan.include_metric_tables:
        _add_metric_tables(bundle, report)
    if plan.include_peer_table:
        _add_peer_table(bundle, report)
    if business_report is not None:
        _add_chunks(bundle, business_report.select(plan.text_patterns, content_types=("TEXT",), max_chars=plan.text_budget))
        if plan.table_patterns:
            _add_chunks(bundle, business_report.select(plan.table_patterns, content_types=("TABLE",), max_chars=plan.table_budget))
    _fit_to_budget(bundle, MAX_EVIDENCE_CHARS)
    return bundle


def _fit_to_budget(bundle: EvidenceBundle, max_chars: int) -> None:
    """근거 총 글자 수가 예산을 넘으면 뒤에서부터 뺀다. 확정 지표(metrics:/peers:)는 남긴다."""
    total = sum(len(e["content"]) for e in bundle.payload)
    while total > max_chars and bundle.payload:
        index = next(
            (i for i in range(len(bundle.payload) - 1, -1, -1) if not bundle.payload[i]["evidence_id"].startswith(("metrics:", "peers:"))),
            None,
        )
        if index is None:
            break
        removed = bundle.payload.pop(index)
        bundle.citations.pop(removed["evidence_id"], None)
        bundle.cited_texts.pop(removed["evidence_id"], None)
        total -= len(removed["content"])


# --- 스키마 ------------------------------------------------------------------


STATUS_SCHEMA = {"type": "string", "enum": ["AVAILABLE", "INSUFFICIENT_EVIDENCE"]}


def _items_schema(citation_ids: list[str], max_items: int = MAX_ITEMS) -> dict[str, Any]:
    return {
        "type": "array",
        "maxItems": max_items,
        "items": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "citation_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": citation_ids}},
            },
            "required": ["text", "citation_ids"],
            "additionalProperties": False,
        },
    }


def section_schema(plan: SectionPlan, citation_ids: list[str]) -> dict[str, Any]:
    if plan.section == "SWOT":
        quadrant = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "citation_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": citation_ids}},
                "items": _items_schema(citation_ids, plan.max_items),
            },
            "required": ["headline", "summary", "citation_ids", "items"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                **{key: quadrant for key, _, _ in SWOT_QUADRANTS},
                "status": STATUS_SCHEMA,
            },
            "required": [*[key for key, _, _ in SWOT_QUADRANTS], "status"],
            "additionalProperties": False,
        }
    # status 는 마지막에 둔다. 스키마 유도 디코딩은 properties 순서대로 생성하므로, 먼저 status 를 쓰게 하면
    # 항목을 보기 전에 INSUFFICIENT_EVIDENCE 로 끝내 버리는 일이 잦았다(SK하이닉스 BUSINESS_GROWTH 실측: 27토큰).
    properties: dict[str, Any] = {}
    for spec in plan.blocks:
        if spec.kind == "text":
            properties[spec.key] = {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citation_ids": {"type": "array", "items": {"type": "string", "enum": citation_ids}},
                },
                "required": ["text", "citation_ids"],
                "additionalProperties": False,
            }
        else:
            properties[spec.key] = {"type": "object", "properties": {"items": _items_schema(citation_ids, plan.max_items)}, "required": ["items"], "additionalProperties": False}
    properties["status"] = STATUS_SCHEMA
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


COMMON_INSTRUCTIONS = (
    "근거에서 확인되는 사실이 하나라도 있으면 항목을 쓰고 status 는 AVAILABLE 로 한다. "
    "text 블록은 제목·굵은 글씨·번호 없이 이어지는 산문으로만 쓴다. "
    "items 의 각 항목은 `**핵심어**: 설명` 형식으로 1~2문장이며 숫자에는 반드시 단위를 붙인다. "
    "근거 ID(evidence_id, dart-… 로 시작하는 문자열)는 citation_ids 에만 넣고 text 안에는 절대 쓰지 않는다. "
    "모든 문장은 '~입니다/~합니다' 체로 끝낸다."
)


def section_instructions(plan: SectionPlan) -> str:
    if plan.section == "SWOT":
        lines = ["SWOT 네 칸을 채운다. 각 칸은 headline(한 줄 제목), summary(1~2문장), items(항목 2~5개)."]
        lines += [f"- {key}: {label} — {purpose}" for key, label, purpose in SWOT_QUADRANTS]
        lines.append(COMMON_INSTRUCTIONS)
        return "\n".join(lines)
    lines = [f"- {spec.key} ({spec.kind}, 제목 '{spec.title}'): {spec.purpose}" for spec in plan.blocks]
    lines.append(COMMON_INSTRUCTIONS)
    return "\n".join(lines)


# --- 출력 → 블록 ----------------------------------------------------------------


@dataclass
class Conversion:
    blocks: list = field(default_factory=list)
    intro: TextBlock | None = None
    swot: SwotBlock | None = None
    dropped: int = 0
    warnings: list[str] = field(default_factory=list)


_ID_TOKEN = r"(?:dart-[A-Za-z0-9_\-]+|metrics:[A-Za-z0-9:_\-]+|peers:[A-Za-z0-9:_\-]+|evidence_id\s*[:：]\s*[A-Za-z0-9:_\-]+)"
_EVIDENCE_ID_LEAK = re.compile(
    rf"\s*\(\s*(?:evidence_id\s*[:：]\s*)?{_ID_TOKEN}(?:\s*,\s*{_ID_TOKEN})*\s*\)?"  # 괄호 안 ID 목록
    rf"|\s*{_ID_TOKEN}"  # 괄호 없이 붙은 ID
)


def _clean(text: Any, title: str | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    # 모델이 본문 끝에 "(evidence_id: dart-business-report-…)" 를 붙이는 일이 있다(SK하이닉스 v3 실측).
    # 그대로 두면 ID 의 숫자가 근거에 없는 숫자로 잡혀 문장이 전부 버려진다.
    cleaned = _EVIDENCE_ID_LEAK.sub("", cleaned).strip()
    if title:
        # "산업과 경쟁 구도: 반도체는 …" / "**기업 소개** 주력 사업은 …" 처럼 제목을 되풀이하는 일이 있다.
        cleaned = re.sub(rf"^\**{re.escape(title)}\**\s*[:：]?\s*", "", cleaned)
    return cleaned


def _check(text: str, ids: Sequence[str], bundle: EvidenceBundle) -> list[Citation]:
    """숫자 검사를 통과하면 인용 목록을, 아니면 빈 목록을 돌려준다."""
    cited = [bundle.cited_texts[i] for i in ids if i in bundle.cited_texts]
    citations = [bundle.citations[i] for i in ids if i in bundle.citations]
    if not citations:
        return []
    if numeric_claim_violations(text, cited) or share_claim_violations(text, cited):
        return []
    return citations


def _dedupe_citations(citations: Sequence[Citation]) -> list[Citation]:
    seen: set[str] = set()
    unique: list[Citation] = []
    for citation in citations:
        if citation.source_id in seen:
            continue
        seen.add(citation.source_id)
        unique.append(citation)
    return unique[:20]


def _items(raw_items: Any, bundle: EvidenceBundle, conversion: Conversion) -> list[BulletItem]:
    items: list[BulletItem] = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        text = _clean(raw.get("text"))
        if not text:
            continue
        citations = _check(text, raw.get("citation_ids") or [], bundle)
        if not citations:
            conversion.dropped += 1
            continue
        items.append(BulletItem(text=text[:600], citations=_dedupe_citations(citations)[:10]))
    return items[:MAX_ITEMS]


def _has_content(plan: SectionPlan, output: dict[str, Any]) -> bool:
    """모델이 내용을 채우고도 status 를 INSUFFICIENT_EVIDENCE 로 찍는 일이 있어(SK하이닉스 재무 실측) 내용을 본다."""
    keys = [key for key, _, _ in SWOT_QUADRANTS] if plan.section == "SWOT" else [spec.key for spec in plan.blocks]
    for key in keys:
        raw = output.get(key) or {}
        if not isinstance(raw, dict):
            continue
        items = [i for i in raw.get("items") or [] if isinstance(i, dict)]
        if _clean(raw.get("text")) or _clean(raw.get("summary")) or any(_clean(i.get("text")) for i in items):
            return True
    return False


def convert_output(plan: SectionPlan, output: dict[str, Any], bundle: EvidenceBundle) -> Conversion:
    conversion = Conversion()
    if output.get("status") == "INSUFFICIENT_EVIDENCE" and not _has_content(plan, output):
        conversion.warnings.append(f"{plan.name} 서술: 근거 부족으로 생성하지 않았습니다.")
        return conversion

    if plan.section == "SWOT":
        quadrants: dict[str, SwotQuadrant] = {}
        for key, _, _ in SWOT_QUADRANTS:
            raw = output.get(key) or {}
            summary = _clean(raw.get("summary"))
            headline = _clean(raw.get("headline")).strip("*") or key
            items = _items(raw.get("items"), bundle, conversion)
            if not summary or not items or not _check(summary, raw.get("citation_ids") or [], bundle):
                conversion.warnings.append(f"SWOT {key}: 근거가 맞는 항목이 없어 비웠습니다.")
                return conversion
            quadrants[key] = SwotQuadrant(headline=headline[:300], summary=summary[:4_000], items=items)
        conversion.swot = SwotBlock(**quadrants)
        return conversion

    for spec in plan.blocks:
        raw = output.get(spec.key) or {}
        if spec.kind == "text":
            text = _clean(raw.get("text"), spec.title)
            if not text:
                continue
            citations = _check(text, raw.get("citation_ids") or [], bundle)
            if not citations:
                conversion.dropped += 1
                conversion.warnings.append(f"{spec.title}: 숫자가 근거와 맞지 않아 제외했습니다.")
                continue
            block = TextBlock(title=None if spec.key == "intro" else spec.title, text=text[:4_000], citations=_dedupe_citations(citations))
            if spec.key == "intro":
                conversion.intro = block
            else:
                conversion.blocks.append(block)
        else:
            items = _items(raw.get("items"), bundle, conversion)
            if items:
                conversion.blocks.append(BulletsBlock(title=spec.title, items=items))
    return conversion


# --- 리포트에 끼워 넣기 ------------------------------------------------------------


NARRATIVE_KINDS = {"text", "bullets", "swot"}


def _merge_section(report: CompanyReport, section_type: str, leading: list, trailing: list, warnings: list[str]) -> CompanyReport:
    """leading 은 섹션의 서술 영역(확정 블록 앞) 끝에, trailing 은 섹션 맨 뒤에 붙인다.

    서술 영역 안에서는 text 가 bullets 보다 앞에 온다. 같은 섹션을 여러 계획이 채울 때
    (COMPETITORS_MARKET → COMPETITORS_POSITION) 나중 계획의 항목이 먼저 온 문장 앞으로 끼어들지 않게 한다.
    """
    sections = list(report.sections)
    index = next((i for i, s in enumerate(sections) if s.type == section_type), None)
    if index is None:
        if not (leading or trailing):
            return report
        sections.append(ReportSection(type=section_type, title=SECTION_TITLES[section_type], blocks=[*leading, *trailing], warnings=warnings[:10]))
    else:
        current = sections[index]
        existing = list(current.blocks)
        split = next((i for i, b in enumerate(existing) if b.kind not in NARRATIVE_KINDS), len(existing))
        narrative = existing[:split] + leading
        narrative.sort(key=lambda b: 0 if b.kind == "text" else 1)  # 안정 정렬: 같은 종류는 순서 유지
        sections[index] = ReportSection(
            type=current.type,
            title=current.title,
            blocks=[*narrative, *existing[split:], *trailing][:20],
            warnings=[*current.warnings, *warnings][:10],
        )
    order = list(SECTION_TITLES)
    sections.sort(key=lambda s: order.index(s.type))
    return report.model_copy(update={"sections": sections})


class NarrativeEnricher:
    def __init__(
        self,
        client: StructuredCompletionClient,
        reports: BusinessReportRepository,
        *,
        plans: Sequence[SectionPlan] | None = None,
        prompt_path: Path = PROMPT_PATH,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self._client = client
        self._reports = reports
        self._plans = tuple(plans) if plans is not None else tuple(PLANS.values())
        self._prompt = prompt_path.read_text(encoding="utf-8").strip()
        self._max_output_tokens = max_output_tokens

    def enrich(self, facts: CompanyFacts, report: CompanyReport) -> CompanyReport:
        business_report = self._reports.latest(report.corp_code)
        warnings: list[str] = list(report.warnings)
        if business_report is None:
            warnings.append("사업보고서 원문 근거가 없어 확정 데이터 블록만 제공합니다.")
            return report.model_copy(update={"warnings": warnings[:20]})

        sources = list(report.sources)
        if all(source.rcept_no != business_report.rcept_no for source in sources):
            sources.append(ReportSource(**business_report.source_card()))
        report = report.model_copy(update={"sources": sources[:20]})

        for plan in self._plans:
            bundle = build_bundle(plan, business_report, report)
            if not bundle.ids:
                warnings.append(f"{plan.name} 서술: 넣을 근거가 없습니다.")
                continue
            try:
                output = self._client.complete(
                    self._messages(plan, report, bundle),
                    section_schema(plan, bundle.ids),
                    max_tokens=max(self._max_output_tokens, plan.max_output_tokens),
                )
            except Exception as error:  # noqa: BLE001 — 섹션 하나의 실패가 나머지를 막지 않는다
                LOGGER.warning("narrative %s failed corp_code=%s: %s", plan.name, report.corp_code, error)
                warnings.append(f"{plan.name} 서술 생성에 실패했습니다: {type(error).__name__}")
                continue
            conversion = convert_output(plan, output, bundle)
            warnings.extend(conversion.warnings)
            if conversion.dropped:
                warnings.append(f"{plan.name} 서술에서 숫자가 근거와 맞지 않는 항목 {conversion.dropped}건을 제외했습니다.")
            report = self._apply(plan, report, conversion)
        return report.model_copy(update={"warnings": list(dict.fromkeys(warnings))[:20]})

    def _messages(self, plan: SectionPlan, report: CompanyReport, bundle: EvidenceBundle) -> list[dict[str, str]]:
        payload = {
            "company": {"corp_code": report.corp_code, "name": report.corp_name, "fiscal_year": report.fiscal_year},
            "section": {"type": plan.section, "name": plan.name, "instructions": section_instructions(plan)},
            "evidence": bundle.payload,
        }
        return [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        ]

    @staticmethod
    def _apply(plan: SectionPlan, report: CompanyReport, conversion: Conversion) -> CompanyReport:
        if plan.section == "INTRO":
            return report.model_copy(update={"intro": conversion.intro}) if conversion.intro else report
        if plan.section == "SWOT":
            return _merge_section(report, "SWOT", [conversion.swot] if conversion.swot else [], [], conversion.warnings)
        if plan.section == "FINANCIALS":
            # 재무는 요약 문장 → 표·차트 → 해설 항목 순서가 읽기 좋다(목표 서비스와 같은 배치).
            leading = [b for b in conversion.blocks if b.kind == "text"]
            trailing = [b for b in conversion.blocks if b.kind != "text"]
        else:
            # 사업·경쟁사는 서술이 먼저, 확정 데이터 표는 뒤에 붙는 보조 자료다.
            leading, trailing = list(conversion.blocks), []
        return _merge_section(report, plan.section, leading, trailing, conversion.warnings)
