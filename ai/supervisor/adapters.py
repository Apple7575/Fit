import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ai.llm.prompt_guard import looks_like_injection, refusal
from ai.news_intelligence.contracts import NewsAnalysisRequest
from ai.position_coaching.render import render_position_message
from ai.supervisor.contracts import AgentResult
from ai.supervisor.feedback import normalize_writing_feedback

LOGGER = logging.getLogger(__name__)
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
    """채용공고 담당. 공고 요구사항과 자소서를 대조하고, 그 결과 위에서 대화한다.

    자동 검토처럼 물어본 것이 없으면 대조 결과를 그대로 낸다. 사용자가 물으면 그 결과를
    바탕으로 답한다 — 대조만 반복하면 무엇을 묻든 같은 말이 돌아온다.
    """

    name = "jd"
    description = "채용 공고 요구사항 하나하나에 대해 지원자 문서에 근거가 있는지 판정"

    def __init__(
        self,
        service_provider: Callable[[], Any],
        chat_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._service_provider = service_provider
        self._chat_provider = chat_provider

    def is_available(self, context: Mapping[str, Any] | None) -> bool:
        return bool(context and context.get("job_context_id"))

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        service = self._service_provider()
        analysis = service.analyze_documents(context["job_context_id"], list(documents))
        if self._chat_provider is None or not str(instruction or "").strip():
            return analysis
        current = next(
            (dict(document) for document in documents
             if document.get("document_type") == "SELF_INTRO"),
            None,
        )
        if current is None:
            return analysis
        try:
            answer = self._chat_provider().respond(
                context=service.get_context(context["job_context_id"]),
                analysis_result=analysis,
                current_document=current,
                message=str(instruction),
                history=[
                    {"role": str(item.get("role", "USER")).lower(),
                     "content": str(item.get("content", ""))}
                    for item in conversation
                    if str(item.get("content", "")).strip()
                ],
            )
        except Exception:  # noqa: BLE001
            # 대화는 대조 결과 위에 얹는 것이다. 여기서 실패해도 대조 결과는 보여 준다 —
            # 담당을 통째로 실패시키면 사용자는 아무것도 못 본다.
            LOGGER.exception("jd chat failed; falling back to the analysis result")
            return analysis
        # 대화 서비스는 답을 answer 로 준다. 백엔드 말풍선은 message 를 읽으므로 옮겨 담는다 —
        # 안 옮기면 대조 목록이 그대로 나가 무엇을 묻든 같은 답이 된다.
        reply = str(answer.get("answer") or answer.get("message") or "").strip()
        if not reply:
            return analysis
        return {**analysis, **answer, "message": reply}


class PositionAgentAdapter:
    name = "position"
    description = (
        "지원 직무와 관련된 사용자 경험(기술·비기술 모두)에서 문제·행동·검증·결과 등 "
        "빠진 요소를 찾고 구체화 질문 제시"
    )
    supported_document_types = {"SELF_INTRO", "EXPERIENCE"}

    def __init__(
        self,
        service_provider: Callable[[], Any],
        chat_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._service_provider = service_provider
        self._chat_provider = chat_provider

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
        # 이번에 물은 것은 instruction 인자로 따로 전달한다(포지션 프롬프트의 user_instruction).
        # 이력 끝에도 붙이면 같은 질문이 프롬프트에 두 번 실린다.
        question = str(instruction or "").strip()
        analysis = self._service_provider().analyze(
            context["rubric_id"],
            context["position_context"],
            supported_documents,
            list(conversation),
            instruction=instruction,
        )
        # 단독 API(/position/internal/analyses)와 같은 모양으로 맞춘다. 백엔드는 결과의
        # message 만 말풍선에 띄우므로 이 키가 없으면 성공해도 "답을 만들지 못했다"로 보인다.
        evaluated = {**analysis, "message": render_position_message(analysis)}
        if self._chat_provider is None or not question:
            return evaluated
        try:
            reply = self._chat_provider().respond(
                position_context=context["position_context"],
                analysis_result=analysis,
                documents=supported_documents,
                message=question,
                # 방금 붙인 이번 질문은 빼고 넘긴다. 대화 서비스가 message 로 따로 받는다.
                history=[dict(item) for item in conversation],
            )
        except Exception:  # noqa: BLE001
            # 대화는 평가 위에 얹는 것이다. 여기서 실패해도 평가 결과는 보여 준다 —
            # 담당을 통째로 실패시키면 사용자는 아무것도 못 본다.
            LOGGER.exception("position chat failed; falling back to the analysis result")
            return evaluated
        answer = str(reply.get("answer") or "").strip()
        if not answer:
            return evaluated
        return {**evaluated, **reply, "message": answer}


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
        # 채용공고·포지션·뉴스 담당에만 걸려 있던 가드를 여기에도 건다. 문구 규칙만으로는
        # 이 모델이 마지막 지시를 그대로 따른다는 것이 팀 실측이다(prompt_guard 주석 참고).
        if looks_like_injection(str(instruction or "")):
            return {
                "status": "ANSWERED",
                "message": refusal("자기소개서 첨삭"),
                "revision": None,
            }
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
        if looks_like_injection(str(instruction or "")):
            return {"answer": refusal("기업 분석"), "citations": [], "model": None, "usage": {}}
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
