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

    def __init__(self, service: Any) -> None:
        self._service = service

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("position_profile_id"))

    def execute(self, instruction, documents, conversation, context):
        return self._service.analyze(
            context["position_profile_id"], list(documents), list(conversation)
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
