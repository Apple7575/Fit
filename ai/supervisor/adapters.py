from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.news_intelligence.contracts import NewsAnalysisRequest
from ai.supervisor.contracts import AgentResult
from ai.supervisor.feedback import normalize_writing_feedback
from ai.writing_coaching.contracts import WritingMessageRequest


class SupervisorAgentAdapter(Protocol):
    name: str

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
        return self._service_provider().analyze(
            context["rubric_id"],
            context["position_context"],
            supported_documents,
            list(conversation),
        )


class WritingAgentAdapter:
    name = "writing"

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


class AgentRegistry:
    def __init__(self, adapters: Sequence[SupervisorAgentAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("agent names must be unique")

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
