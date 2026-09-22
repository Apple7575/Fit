from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.news_intelligence.contracts import NewsAnalysisRequest
from ai.position_coaching.render import render_position_message
from ai.supervisor.contracts import AgentResult
from ai.supervisor.feedback import normalize_writing_feedback
from ai.writing_coaching.contracts import WritingMessageRequest


class SupervisorAgentAdapter(Protocol):
    name: str
    # 총괄이 담당을 고를 때 읽는 한 줄 소개. 담당이 실제로 하는 일과 어긋나면 총괄이 잘못 고른다.
    description: str

    def is_available(self, context: Mapping[str, Any] | None) -> bool: ...

    def execute(
        self,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
        prior_results: Sequence[AgentResult] = (),
    ) -> dict[str, Any]: ...


class JdAgentAdapter:
    name = "jd"
    description = "채용 공고 요구사항 하나하나에 대해 지원자 문서에 근거가 있는지 판정"

    def __init__(self, service_provider: Callable[[], Any]) -> None:
        self._service_provider = service_provider

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("job_context_id"))

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        return self._service_provider().analyze_documents(
            context["job_context_id"], list(documents)
        )


class PositionAgentAdapter:
    name = "position"
    description = (
        "사용자 경험(기술·비기술 모두)에서 문제·행동·검증·결과 등 빠진 요소를 찾고 구체화 질문 제시"
    )
    supported_document_types = {"SELF_INTRO", "EXPERIENCE"}

    def __init__(self, service_provider: Callable[[], Any]) -> None:
        self._service_provider = service_provider

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(
            context
            and context.get("rubric_id")
            and context.get("position_context")
        )

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        supported_documents = [
            document
            for document in documents
            if document.get("document_type") in self.supported_document_types
        ]
        if not supported_documents:
            raise ValueError(
                "position agent requires SELF_INTRO or EXPERIENCE document"
            )
        analysis = self._service_provider().analyze(
            context["rubric_id"],
            context["position_context"],
            supported_documents,
            list(conversation),
            instruction=instruction,
        )
        # 단독 API(/position/internal/analyses)와 같은 모양으로 맞춘다. 백엔드는 결과의
        # message 만 말풍선에 띄우므로 이 키가 없으면 성공해도 "답을 만들지 못했다"로 보인다.
        return {**analysis, "message": render_position_message(analysis)}


class WritingAgentAdapter:
    name = "writing"
    description = "자기소개서 첨삭 또는 작성 방식 설명"

    def __init__(self, service_provider: Callable[[], Any]) -> None:
        self._service_provider = service_provider

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(
            context
            and context.get("question")
            and context.get("char_limit")
        )

    def execute(
        self,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
        prior_results: Sequence[AgentResult] = (),
    ) -> dict[str, Any]:
        self_intro_documents = [
            document
            for document in documents
            if document.get("document_type") == "SELF_INTRO"
        ]
        if len(self_intro_documents) != 1:
            raise ValueError("writing agent requires exactly one SELF_INTRO document")
        request = WritingMessageRequest(
            message=instruction,
            question=context["question"],
            draft=self_intro_documents[0]["text"],
            char_limit=context["char_limit"],
            feedback=normalize_writing_feedback(prior_results),
            conversation=list(conversation),
        )
        return self._service_provider().respond(request).model_dump()


class NewsAgentAdapter:
    name = "news"
    description = "기업·산업·직무 변화의 기사 근거와 JD 관련성 분석"

    def __init__(self, service: Any) -> None:
        self._service_provider = service if callable(service) else lambda: service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(
            context and context.get("job_context_id") and context.get("corp_code")
        )

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        response = self._service_provider().analyze(
            NewsAnalysisRequest(
                instruction=instruction,
                job_context_id=context["job_context_id"],
                corp_code=context["corp_code"],
                conversation=list(conversation),
            )
        )
        return response.model_dump(mode="json")


class CompanyAgentAdapter:
    """기업 분석 담당. 총괄이 든 대화를 history 로 넘기고 저장은 하지 않는다(answer 는 stateless)."""

    name = "company"
    description = (
        "공시(사업보고서·확정 재무 지표) 기반 기업 분석 리포트와 기업 관련 질의응답. "
        "뉴스·주가·평판은 다루지 않음"
    )

    def __init__(self, service: Any) -> None:
        self._service_provider = service if callable(service) else lambda: service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("corp_code"))

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        history = [
            {"role": str(item.get("role", "USER")), "content": str(item.get("content", ""))}
            for item in conversation
            if isinstance(item, Mapping)
        ]
        return self._service_provider().answer(
            corp_code=context["corp_code"],
            message=instruction,
            history=history,
        )


class AgentRegistry:
    def __init__(self, adapters: Sequence[SupervisorAgentAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("agent names must be unique")

    def describe(self, names: Sequence[str]) -> dict[str, str]:
        """총괄 계획 프롬프트에 실을 담당별 소개문. 소개문을 안 둔 어댑터는 이름만 넘어간다."""
        return {
            name: getattr(self._adapters[name], "description", "") or name
            for name in names
            if name in self._adapters
        }

    def available_names(self, contexts: Mapping[str, Any]) -> list[str]:
        return [
            name
            for name, adapter in self._adapters.items()
            if adapter.is_available(contexts.get(name))
        ]

    def execute(
        self,
        name: str,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
        prior_results: Sequence[AgentResult] = (),
    ) -> dict[str, Any]:
        if name not in self._adapters:
            raise KeyError(f"unknown agent: {name}")
        return self._adapters[name].execute(
            instruction, documents, conversation, context, prior_results
        )
