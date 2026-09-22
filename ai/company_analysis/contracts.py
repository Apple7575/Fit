"""기업 분석 리포트·대화 API 계약.

리포트는 섹션 4개(사업·재무·경쟁사·SWOT)와 상단 소개로 구성한다. 블록 종류는 여섯 개로
고정하고, 숫자가 들어가는 블록(table·kpi·chart)은 결정적 생성기가 DB 값으로 채운다.
서술 항목(text·bullets·swot)은 반드시 citations 를 갖는다 — 근거 없는 문장은 계약 위반이다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


CorpCode = Annotated[str, Field(pattern=r"^[0-9]{8}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=300)]
BodyText = Annotated[str, Field(min_length=1, max_length=4_000)]

SectionType = Literal["BUSINESS", "FINANCIALS", "COMPETITORS", "SWOT"]
SECTION_TITLES: dict[str, str] = {
    "BUSINESS": "사업 내용",
    "FINANCIALS": "재무 분석",
    "COMPETITORS": "경쟁사 및 포지셔닝",
    "SWOT": "SWOT 분석 및 활용점",
}

# 근거 출처 종류. 뉴스는 리포트 근거에서 제외한다.
CitationSourceType = Literal[
    "DART_BUSINESS_REPORT",  # 사업보고서 원문 청크 (rag_evidence.evidence_id)
    "COMPANY_METRIC",  # company_metric (corp_code:fiscal_year:metric_code)
    "SEGMENT_METRIC",  # segment_metric
    "COMPANY_ACTIVITY",  # company_activity.id
    "COMPANY_PROFILE",  # company / company_business / company_product 등 프로필 표
    "INDUSTRY_PEER",  # 산업 비교 데이터 (동일 KSIC 상장사)
]

ReportStatusValue = Literal["PENDING", "RUNNING", "READY", "FAILED"]


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class Citation(StrictModel):
    """서술 한 줄이 어디에서 왔는지. 총괄의 공통 Evidence 로 그대로 변환된다."""

    source_type: CitationSourceType
    source_id: str = Field(min_length=1, max_length=200)
    rcept_no: str | None = Field(default=None, pattern=r"^[0-9]{14}$")
    excerpt: str | None = Field(default=None, max_length=1_000)

    @field_validator("source_id")
    @classmethod
    def reject_blank_source_id(cls, value: str) -> str:
        return _reject_blank(value)


class TextBlock(StrictModel):
    kind: Literal["text"] = "text"
    title: ShortText | None = None
    text: BodyText
    citations: list[Citation] = Field(min_length=1, max_length=20)


class BulletItem(StrictModel):
    text: Annotated[str, Field(min_length=1, max_length=600)]
    citations: list[Citation] = Field(min_length=1, max_length=10)
    # 지원 직무 관점 항목이면 "JOB". 일반 항목은 None.
    perspective: Literal["JOB"] | None = None


class BulletsBlock(StrictModel):
    kind: Literal["bullets"] = "bullets"
    title: ShortText | None = None
    items: list[BulletItem] = Field(min_length=1, max_length=12)


TableCell = str | int | float | None
ChartHint = Literal["donut", "bar", "line"]


class TableBlock(StrictModel):
    """결정적 표. 값은 DB 에서 그대로 오고 LLM 은 손대지 않는다."""

    kind: Literal["table"] = "table"
    title: ShortText
    columns: list[ShortText] = Field(min_length=2, max_length=12)
    rows: list[list[TableCell]] = Field(min_length=1, max_length=60)
    unit: str | None = Field(default=None, max_length=30)
    chart: ChartHint | None = None
    citations: list[Citation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def rows_match_columns(self) -> "TableBlock":
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(f"row {index} has {len(row)} cells, expected {width}")
        return self


class KpiItem(StrictModel):
    label: ShortText
    value: float | int | None
    unit: str | None = Field(default=None, max_length=30)
    # 전년 대비 변화율(%). 계산 불가하면 None.
    delta_pct: float | None = None
    note: str | None = Field(default=None, max_length=100)
    citations: list[Citation] = Field(default_factory=list, max_length=5)


class KpiBlock(StrictModel):
    kind: Literal["kpi"] = "kpi"
    items: list[KpiItem] = Field(min_length=1, max_length=6)


class ChartSeries(StrictModel):
    name: ShortText
    values: list[float | int | None] = Field(min_length=1, max_length=20)


class ChartBlock(StrictModel):
    kind: Literal["chart"] = "chart"
    title: ShortText
    chart: ChartHint
    categories: list[ShortText] = Field(min_length=1, max_length=20)
    series: list[ChartSeries] = Field(min_length=1, max_length=6)
    unit: str | None = Field(default=None, max_length=30)
    citations: list[Citation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def series_match_categories(self) -> "ChartBlock":
        width = len(self.categories)
        for series in self.series:
            if len(series.values) != width:
                raise ValueError(
                    f"series '{series.name}' has {len(series.values)} values, expected {width}"
                )
        return self


class SwotQuadrant(StrictModel):
    headline: ShortText
    summary: BodyText
    items: list[BulletItem] = Field(min_length=1, max_length=6)


class SwotBlock(StrictModel):
    kind: Literal["swot"] = "swot"
    strengths: SwotQuadrant
    weaknesses: SwotQuadrant
    opportunities: SwotQuadrant
    threats: SwotQuadrant


Block = Annotated[
    TextBlock | BulletsBlock | TableBlock | KpiBlock | ChartBlock | SwotBlock,
    Field(discriminator="kind"),
]


class ReportSection(StrictModel):
    type: SectionType
    title: ShortText
    blocks: list[Block] = Field(min_length=1, max_length=20)
    # 근거 부족으로 비운 블록이 있으면 이유를 남긴다.
    warnings: list[ShortText] = Field(default_factory=list, max_length=10)


class ReportSource(StrictModel):
    """출처 카드. 사업보고서 접수번호 단위."""

    rcept_no: str = Field(pattern=r"^[0-9]{14}$")
    title: ShortText
    published_at: datetime
    url: str = Field(min_length=1, max_length=500)


class CompanyReport(StrictModel):
    schema_version: Literal["company-report-v1"] = "company-report-v1"
    # DETERMINISTIC: 확정 데이터 블록만 있음(서술 생성 중이거나 실패). FULL: 서술 블록까지 완료.
    stage: Literal["DETERMINISTIC", "FULL"] = "DETERMINISTIC"
    corp_code: CorpCode
    corp_name: ShortText
    # 리포트가 기준으로 삼은 최신 사업연도.
    fiscal_year: int = Field(ge=2000, le=2100)
    generated_at: datetime
    intro: TextBlock
    sections: list[ReportSection] = Field(min_length=1, max_length=4)
    sources: list[ReportSource] = Field(default_factory=list, max_length=20)
    warnings: list[ShortText] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def sections_unique_and_ordered(self) -> "CompanyReport":
        order = list(SECTION_TITLES)
        seen = [section.type for section in self.sections]
        if len(set(seen)) != len(seen):
            raise ValueError("duplicate section type")
        if seen != sorted(seen, key=order.index):
            raise ValueError(f"sections must follow order {order}")
        return self


class ReportStatus(StrictModel):
    corp_code: CorpCode
    status: ReportStatusValue
    updated_at: datetime
    fiscal_year: int | None = None
    error: str | None = Field(default=None, max_length=500)


# --- API 요청/응답 ---------------------------------------------------------


class ReportGenerateRequest(StrictModel):
    corp_code: CorpCode
    # True 면 READY 상태여도 다시 만든다.
    force: bool = False


class ChatRequest(StrictModel):
    corp_code: CorpCode
    message: str = Field(min_length=1, max_length=4_000)
    # 없으면 새 대화를 만든다. 있으면 그 대화의 corp_code 와 같아야 한다.
    conversation_id: str | None = Field(default=None, min_length=1, max_length=80)
    # 지원 직무 맥락이 있으면 직무 관점 답변에 쓴다.
    job_context_id: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        return _reject_blank(value)


class ChatNeed(StrictModel):
    """공시 근거로 답할 수 없어 총괄에게 다른 담당 호출을 요청한다. 총괄의 AgentNeed 와 같은 모양."""

    agent: Literal["news"]
    reason: str = Field(min_length=1, max_length=1_000)


class ChatMessage(StrictModel):
    message_id: str
    role: Literal["USER", "ASSISTANT"]
    content: str
    created_at: datetime
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    needs: list[ChatNeed] = Field(default_factory=list, max_length=4)


class CompanyConversationMessage(StrictModel):
    """담당 방의 지난 대화 한 줄. 저장하지 않고 이번 답에만 쓴다."""

    message_id: str = Field(min_length=1, max_length=80)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=4_000)


class CompanyMessageRequest(StrictModel):
    """무상태 대화 요청. 대화는 호출자가 들고 있고 여기서는 저장하지 않는다.

    `ChatRequest` 와 달리 `conversation_id` 가 없다 — 담당 방은 백엔드가 대화를 보관하므로
    AI 쪽에 같은 대화를 두 벌 쌓을 이유가 없다. 다른 담당(글쓰기·포지션)의 무상태 API 와 같은 모양이다.
    """

    corp_code: CorpCode
    message: str = Field(min_length=1, max_length=4_000)
    conversation: list[CompanyConversationMessage] = Field(default_factory=list, max_length=20)
    # 지원 직무 맥락이 있으면 직무 관점 답변에 쓴다.
    job_context_id: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        return _reject_blank(value)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "CompanyMessageRequest":
        ids = [item.message_id for item in self.conversation]
        if len(ids) != len(set(ids)):
            raise ValueError("message_id values must be unique")
        return self


class CompanyMessageResponse(StrictModel):
    """무상태 대화 응답. 총괄 어댑터가 받는 dict 와 같은 필드를 쓴다."""

    corp_code: CorpCode
    corp_name: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4_000)
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    needs: list[ChatNeed] = Field(default_factory=list, max_length=4)
    follow_up_questions: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=3)
    # 리포트 stage 가 DETERMINISTIC 이면 서술 섹션이 아직 없다는 뜻이다.
    report_stage: Literal["DETERMINISTIC", "FULL"]
    usage: dict[str, int] | None = None


class ChatResponse(StrictModel):
    conversation_id: str
    corp_code: CorpCode
    user_message: ChatMessage
    assistant_message: ChatMessage
    follow_up_questions: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=3)
    # 리포트 stage 가 DETERMINISTIC 이면 서술 섹션이 아직 없다는 뜻이다.
    report_stage: Literal["DETERMINISTIC", "FULL"]
    usage: dict[str, int] | None = None


class ConversationHistory(StrictModel):
    conversation_id: str
    corp_code: CorpCode
    job_context_id: str | None
    messages: list[ChatMessage]
