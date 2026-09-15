from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


class PositionAgentContext(StrictModel):
    position_profile_id: str = Field(min_length=1, max_length=100)

    @field_validator("position_profile_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class AgentContexts(StrictModel):
    jd: JdAgentContext | None = None
    position: PositionAgentContext | None = None


class SupervisorRunRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=10_000)
    documents: list[SupervisorDocument] = Field(min_length=1, max_length=21)
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=20)
    agent_contexts: AgentContexts

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


class SupervisorPlan(StrictModel):
    selected_agents: list[Literal["jd", "position"]] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2_000)


class AgentResult(StrictModel):
    agent: Literal["jd", "position"]
    status: Literal["SUCCESS", "FAILED"]
    result: dict[str, Any] | None = None
    error: str | None = None


class SupervisorRunResponse(StrictModel):
    status: Literal["SUCCESS", "PARTIAL"]
    message: str
    plan: SupervisorPlan
    agent_results: list[AgentResult]


class NoAvailableAgentError(RuntimeError):
    pass


class AllAgentsFailedError(RuntimeError):
    def __init__(self, results: list[AgentResult]) -> None:
        super().__init__("all selected agents failed")
        self.results = results
