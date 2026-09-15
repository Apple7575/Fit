from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class SupervisorAgentAdapter(Protocol):
    name: str

    def is_available(self, context: Mapping[str, Any] | None) -> bool: ...

    def execute(
        self,
        instruction: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        context: Mapping[str, Any],
    ) -> dict[str, Any]: ...


class JdAgentAdapter:
    name = "jd"

    def __init__(self, service: Any) -> None:
        self._service = service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("job_context_id"))

    def execute(self, instruction, documents, conversation, context):
        return self._service.analyze_documents(context["job_context_id"], list(documents))


class PositionAgentAdapter:
    name = "position"
    supported_document_types = {"SELF_INTRO", "EXPERIENCE"}

    def __init__(self, service: Any) -> None:
        self._service = service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(
            context
            and context.get("rubric_id")
            and context.get("position_context")
        )

    def execute(self, instruction, documents, conversation, context):
        supported_documents = [
            document
            for document in documents
            if document.get("document_type") in self.supported_document_types
        ]
        if not supported_documents:
            raise ValueError(
                "position agent requires SELF_INTRO or EXPERIENCE document"
            )
        return self._service.analyze(
            context["rubric_id"],
            context["position_context"],
            supported_documents,
            list(conversation),
        )


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
    ) -> dict[str, Any]:
        if name not in self._adapters:
            raise KeyError(f"unknown agent: {name}")
        return self._adapters[name].execute(
            instruction, documents, conversation, context
        )
