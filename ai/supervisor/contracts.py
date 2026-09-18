from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


AgentName = Literal["jd", "position", "writing", "news", "company"]


class SupervisorDocument(StrictModel):
    document_id: str = Field(min_length=1, max_length=100)
    document_type: Literal["RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"]
    text: str = Field(min_length=1, max_length=50_000)

    @field_validator("document_id", "text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ConversationMessage(StrictModel):
    message_id: str = Field(min_length=1, max_length=100)
    role: Literal["USER", "ASSISTANT"]
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("message_id", "content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class JdAgentContext(StrictModel):
    job_context_id: str = Field(min_length=1, max_length=100)

    @field_validator("job_context_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class NewsAgentContext(StrictModel):
    job_context_id: str = Field(min_length=1, max_length=80)
    corp_code: str = Field(pattern=r"^[0-9]{8}$")

    @field_validator("job_context_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class CompanyAgentContext(StrictModel):
    """기업 분석 담당. 공시(사업보고서·확정 지표) 리포트 위에서 답한다. 제출 문서가 없어도 된다."""

    corp_code: str = Field(pattern=r"^[0-9]{8}$")
    # 지원 직무 맥락이 있으면 직무 관점 답변에 쓴다.
    job_context_id: str | None = Field(default=None, min_length=1, max_length=80)


class PositionContext(StrictModel):
    position_name: str = Field(min_length=1, max_length=200)
    priority_requirements: list[
        Annotated[str, Field(min_length=1, max_length=500)]
    ] = Field(default_factory=list, max_length=20)

    @field_validator("position_name")
    @classmethod
    def reject_blank_position_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("priority_requirements")
    @classmethod
    def reject_blank_priorities(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("priority requirement must not be blank")
        return values


class PositionAgentContext(StrictModel):
    rubric_id: Literal["experience-depth-v1"]
    position_context: PositionContext


class WritingAgentContext(StrictModel):
    question: str = Field(min_length=1, max_length=500)
    char_limit: int = Field(strict=True, ge=1, le=50_000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class AgentContexts(StrictModel):
    jd: JdAgentContext | None = None
    position: PositionAgentContext | None = None
    writing: WritingAgentContext | None = None
    news: NewsAgentContext | None = None
    company: CompanyAgentContext | None = None


class SupervisorRunRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    documents: list[SupervisorDocument] = Field(default_factory=list, max_length=21)
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)
    agent_contexts: AgentContexts
    # lead 모드: 총괄의 계획 단계를 건너뛰고 이 담당부터 실행한다(담당 직접 호출).
    # 위임과 재실행은 그대로 동작하고 최종 메시지는 lead 담당의 것을 쓴다.
    lead: AgentName | None = None

    @field_validator("instruction")
    @classmethod
    def reject_blank_instruction(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instruction must not be blank")
        return value

    @field_validator("documents")
    @classmethod
    def reject_duplicate_document_ids(
        cls, value: list[SupervisorDocument]
    ) -> list[SupervisorDocument]:
        ids = [document.document_id for document in value]
        if len(ids) != len(set(ids)):
            raise ValueError("documents must not contain duplicate document_id")
        return value


EvidenceSourceType = Literal[
    "NEWS_ARTICLE",  # 뉴스 담당이 조회한 기사
    "JOB_POSTING",  # JD 담당이 조회한 채용 공고 (job_context)
    "USER_DOCUMENT",  # 사용자가 제출한 문서의 인용 구간
    "COMPANY_REPORT",  # 사업보고서 등 기업 공시 (기업 RAG 합류 시 사용)
]


class Evidence(StrictModel):
    """담당이 판단에 실제로 사용한 근거 한 건.

    모든 담당의 근거를 같은 형태로 모아 총괄 응답에 실어 보내기 위한 공통 규격이다.
    사실 근거는 도구로 가져온 자료와 사용자 제출 문서만 허용하고, 대화 내용은
    근거로 등록하지 않는다.
    """

    evidence_id: str = Field(min_length=1, max_length=200)
    source_type: EvidenceSourceType
    source_id: str = Field(min_length=1, max_length=200)
    agent: AgentName
    title: str | None = Field(default=None, max_length=500)
    date: str | None = Field(default=None, max_length=40)
    url: str | None = Field(default=None, max_length=2_000)
    excerpt: str | None = Field(default=None, max_length=1_000)


ToolName = Literal[
    "get_job_context",  # 등록된 채용 공고 컨텍스트 조회
    "list_news",  # 저장된 기사 목록 조회
    "search_news_external",  # 외부 뉴스 검색(일회성 후보)
    "get_conversation",  # 저장된 대화 조회
]


ToolCaller = Literal["jd", "position", "writing", "news", "company", "supervisor"]


class ToolCall(StrictModel):
    """담당이 실행 중 호출한 조회 도구 한 건. 추적과 호출 제한의 단위다."""

    tool: ToolName
    agent: ToolCaller
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["SUCCESS", "FAILED", "DENIED"]
    duration_ms: int = Field(ge=0)
    result_count: int | None = None
    error: str | None = None


TracePhase = Literal["plan", "analysis", "writing", "delegation", "rerun", "aggregate"]


class TraceStep(StrictModel):
    """실행 단계 한 건. 재실행으로 대체된 1차 결과도 남겨 전 과정을 추적할 수 있게 한다."""

    step: int = Field(ge=1)
    phase: TracePhase
    agent: ToolCaller
    called_by: str = Field(min_length=1, max_length=40)  # "request" | "plan" | "lead" | 요청 담당 이름
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    duration_ms: int = Field(ge=0)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    superseded: bool = False  # 같은 담당의 재실행으로 대체된 결과
    note: str | None = Field(default=None, max_length=1_000)


class AgentNeed(StrictModel):
    """담당이 스스로 채울 수 없어 총괄에게 요청하는 추가 담당 호출."""

    agent: AgentName
    reason: str = Field(min_length=1, max_length=1_000)


class SupervisorPlan(StrictModel):
    selected_agents: list[AgentName] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2_000)


class AgentResult(StrictModel):
    agent: AgentName
    status: Literal["SUCCESS", "FAILED"]
    result: dict[str, Any] | None = None
    error: str | None = None
    evidence: list[Evidence] = Field(default_factory=list, max_length=200)
    needs: list[AgentNeed] = Field(default_factory=list, max_length=4)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=100)
    usage: dict[str, int] | None = None
    delegated_from: AgentName | None = None


class SupervisorRunResponse(StrictModel):
    status: Literal["SUCCESS", "PARTIAL"]
    message: str
    plan: SupervisorPlan
    agent_results: list[AgentResult]
    evidence: list[Evidence] = Field(default_factory=list)
    lead: AgentName | None = None
    trace: list[TraceStep] = Field(default_factory=list)


class NoAvailableAgentError(RuntimeError):
    pass


class AllAgentsFailedError(RuntimeError):
    def __init__(self, results: list[AgentResult]) -> None:
        super().__init__("all selected agents failed")
        self.results = results
