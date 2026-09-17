from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ai.supervisor.contracts import ConversationMessage

Scope = Literal["COMPANY", "INDUSTRY", "ROLE"]
CoverageState = Literal["COVERED", "INSUFFICIENT"]
EvidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]
Origin = Literal["STORED", "EXTERNAL"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    @field_validator("*", mode="after")
    @classmethod
    def reject_blank_strings(cls, value: Any) -> Any:
        if isinstance(value, str) and not value:
            raise ValueError("must not be blank")
        return value


class NewsAnalysisRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    job_context_id: str = Field(min_length=1, max_length=80)
    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class NewsCandidate(StrictModel):
    article_id: str
    origin: Origin
    title: str
    publisher: str | None = None
    published_at: datetime
    url: HttpUrl
    guid: str | None = None
    importance_score: float | None = Field(default=None, ge=0, le=10)

    @field_validator("published_at")
    @classmethod
    def require_timezone_aware_published_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("published_at must include a timezone offset")
        return value


class NewsContext(StrictModel):
    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    corp_name: str
    industry_name: str | None = None
    position_name: str
    jd_text: str
    role_elements: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class CoverageAssessment(StrictModel):
    company: CoverageState
    industry: CoverageState
    role: CoverageState
    requested_scopes: list[Scope] = Field(
        default_factory=lambda: ["COMPANY", "INDUSTRY", "ROLE"], max_length=3
    )

    @field_validator("requested_scopes")
    @classmethod
    def reject_duplicate_scopes(cls, values: list[Scope]) -> list[Scope]:
        if len(values) != len(set(values)):
            raise ValueError("requested_scopes must not contain duplicates")
        return values


class SearchDecision(StrictModel):
    required: bool
    reason: str
    missing_scopes: list[Scope] = Field(default_factory=list, max_length=3)

    @field_validator("missing_scopes")
    @classmethod
    def reject_duplicate_scopes(cls, values: list[Scope]) -> list[Scope]:
        if len(values) != len(set(values)):
            raise ValueError("missing_scopes must not contain duplicates")
        return values


class ExternalSearch(StrictModel):
    used: bool
    reason: str


class SignalDraft(StrictModel):
    scope: Scope
    title: str
    summary: str
    jd_relevance: str
    preparation_checks: list[str] = Field(default_factory=list, max_length=3)
    source_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("preparation_checks", "source_ids")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("items must not be blank")
        return values


class NewsSignal(StrictModel):
    signal_id: str
    scope: Scope
    title: str
    summary: str
    jd_relevance: str
    preparation_checks: list[str] = Field(default_factory=list, max_length=3)
    evidence_level: EvidenceLevel
    sources: list[NewsCandidate] = Field(min_length=1, max_length=20)

    @field_validator("preparation_checks")
    @classmethod
    def reject_blank_preparation_checks(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("preparation checks must not be blank")
        return values


class CompanyReference(StrictModel):
    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    corp_name: str


class AnalysisWindow(StrictModel):
    from_date: date = Field(alias="from")
    to: date


class NewsAnalysis(StrictModel):
    analysis_status: Literal["COMPLETED", "INSUFFICIENT_EVIDENCE"]
    company: CompanyReference
    window: AnalysisWindow
    signals: list[NewsSignal] = Field(default_factory=list, max_length=9)
    coverage: CoverageAssessment
    external_search: ExternalSearch


class NewsAnalysisResponse(StrictModel):
    message: str
    analysis: NewsAnalysis
