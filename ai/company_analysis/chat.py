"""리포트 위에서 나누는 대화.

흐름: 저장된 리포트를 읽고(없으면 결정적 리포트를 지금 만든다) → 질문으로 사업보고서 청크를 검색해
근거 8개를 고르고 → 리포트 블록 + 근거 + 최근 대화를 Qwen 에 넣어 JSON 답을 받고 → 답의 숫자를
인용 근거와 대조해(claim_check) 어긋나면 한 번 다시 묻고, 그래도 어긋나면 근거 부족으로 답한다 →
대화를 저장한다. 뉴스가 필요하면 needs 에 남겨 총괄이 뉴스 담당에 1홉 위임할 수 있게 한다.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chat_store import Conversation, ConversationStore, StoredMessage
from .claim_check import CitedText, numeric_claim_violations, share_claim_violations
from .contracts import ChatMessage, ChatNeed, ChatRequest, ChatResponse, Citation, CompanyReport, ConversationHistory
from .evidence import BusinessReport, BusinessReportRepository
from .llm import StructuredCompletionClient
from .retrieval import CompanyRetriever, Hit
from .service import CompanyAnalysisService

LOGGER = logging.getLogger("ai.company_analysis.chat")
PROMPT_PATH = Path(__file__).parent / "resources" / "prompts" / "chat-v1.md"

MAX_HISTORY = 8
MAX_EVIDENCE = 8
MAX_CHUNK_CHARS = 900
MAX_REPORT_CHARS = 4_500
MAX_OUTPUT_TOKENS = 1_200
INSUFFICIENT_ANSWER = "공시 자료(사업보고서·확정 지표)에서 이 질문에 답할 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 해 주시거나 다른 항목을 물어봐 주세요."


class ConversationNotFoundError(LookupError):
    pass


class ConversationMismatchError(ValueError):
    pass


@dataclass
class ChatEvidence:
    payload: list[dict[str, Any]] = field(default_factory=list)
    citations: dict[str, Citation] = field(default_factory=dict)
    cited_texts: dict[str, CitedText] = field(default_factory=dict)

    def add(self, evidence_id: str, *, title: str, content: str, citation: Citation, is_table: bool = False, unit: str | None = None) -> None:
        if evidence_id in self.citations:
            return
        self.payload.append({"evidence_id": evidence_id, "title": title, "content": content})
        self.citations[evidence_id] = citation
        header = next((line for line in content.splitlines() if line.startswith("표 머리글:")), "")
        self.cited_texts[evidence_id] = CitedText(evidence_id, content, is_table=is_table, unit=unit, header=header)

    @property
    def ids(self) -> list[str]:
        return list(self.citations)


def _render_block(block: Any) -> str:
    if block.kind == "text":
        return block.text
    if block.kind == "bullets":
        return "\n".join(f"- {item.text}" for item in block.items)
    if block.kind == "table":
        lines = [f"표 머리글: {' | '.join(block.columns)}"]
        lines += [" | ".join("" if c is None else str(c) for c in row) for row in block.rows]
        return ("표 단위: " + block.unit + "\n" if block.unit else "") + "\n".join(lines)
    if block.kind == "kpi":
        return "\n".join(f"{i.label}: {i.value}{i.unit or ''}" + (f" (전년 대비 {i.delta_pct:+}%)" if i.delta_pct is not None else "") for i in block.items)
    if block.kind == "swot":
        parts = []
        for key, label in (("strengths", "강점"), ("weaknesses", "약점"), ("opportunities", "기회"), ("threats", "위협")):
            quad = getattr(block, key)
            parts.append(f"[{label}] {quad.headline}: {quad.summary}\n" + "\n".join(f"- {i.text}" for i in quad.items))
        return "\n".join(parts)
    return ""


def report_evidence(report: CompanyReport, bundle: ChatEvidence, *, max_chars: int = MAX_REPORT_CHARS) -> None:
    """리포트 블록을 근거로 넣는다. 소개 → 각 섹션 순서로, 글자 예산 안에서."""
    budget = max_chars
    entries: list[tuple[str, str, str, Any]] = [("report:intro", "리포트 · 기업 소개", report.intro.text, report.intro)]
    for section in report.sections:
        for index, block in enumerate(section.blocks):
            if block.kind == "chart":
                continue
            title = getattr(block, "title", None) or section.title
            entries.append((f"report:{section.type.lower()}:{index}", f"리포트 · {section.title} · {title}", _render_block(block), block))
    for evidence_id, title, content, block in entries:
        if not content or len(content) > budget:
            continue
        # 리포트 블록의 원 출처를 그대로 이어 준다. 여러 인용이 있으면 첫 번째를 대표로 쓴다.
        # 인용이 없는 확정 블록(KPI·표·차트)은 확정 지표 출처로 표시한다.
        source = getattr(block, "citations", None)
        if source:
            citation = source[0]
        elif block.kind in ("kpi", "table", "chart"):
            citation = Citation(source_type="COMPANY_METRIC", source_id=f"{report.corp_code}:{evidence_id}")
        else:
            citation = Citation(source_type="COMPANY_PROFILE", source_id=f"{report.corp_code}:{evidence_id}")
        bundle.add(evidence_id, title=title, content=content, citation=citation, is_table=False)
        budget -= len(content)


def chunk_evidence(hits: list[Hit], bundle: ChatEvidence) -> None:
    for hit in hits[:MAX_EVIDENCE]:
        chunk = hit.chunk
        content = chunk.content if len(chunk.content) <= MAX_CHUNK_CHARS else chunk.content[:MAX_CHUNK_CHARS]
        if chunk.is_table and chunk.unit:
            content = f"표 단위: {chunk.unit}\n{content}"
        bundle.add(
            chunk.evidence_id,
            title=f"{chunk.report_name} · {chunk.section_title}".strip(" ·"),
            content=content,
            citation=chunk.citation(),
            is_table=chunk.is_table,
            unit=chunk.unit,
        )


def chat_schema(citation_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citation_ids": {"type": "array", "items": {"type": "string", "enum": citation_ids}},
            "needs_news": {"type": "boolean"},
            "needs_reason": {"type": "string"},
            "follow_up_questions": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
        },
        "required": ["answer", "citation_ids", "needs_news", "needs_reason", "follow_up_questions"],
        "additionalProperties": False,
    }


_ID_LEAK = re.compile(r"\s*\(?\s*(?:evidence_id\s*[:：]\s*)?(?:dart-[A-Za-z0-9_\-]+|report:[a-z_]+(?::\d+)?)(?:\s*,\s*(?:dart-[A-Za-z0-9_\-]+|report:[a-z_]+(?::\d+)?))*\s*\)?")


_FOOTNOTE_TAIL = re.compile(r"(?<=[.다요!?])\s*\d{1,2}\s*$")
_NUMBER_TOKEN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def _clean(text: Any) -> str:
    cleaned = _ID_LEAK.sub("", re.sub(r"[ \t]+", " ", str(text or ""))).strip()
    # 모델이 문장 끝에 각주 번호("…있습니다.1")를 붙이는 일이 있다(총괄 lead 실측).
    return _FOOTNOTE_TAIL.sub("", cleaned).strip()


MAX_EXTRA_HOLDERS = 4


def _holders_of(text: str, bundle: ChatEvidence, cited_ids: Sequence[str] = ()) -> list[str]:
    """인용에 없는 숫자를 담은 근거 ID(최대 4건). 인용을 빠뜨린 문장에 근거를 보태는 데 쓴다.

    숫자는 온전한 토큰으로만 맞춘다("35.5" 가 "135.5" 에 맞지 않게). 이미 인용한 근거에 있는 숫자는 건너뛴다.
    """
    already = " ".join(bundle.cited_texts[i].content for i in cited_ids if i in bundle.cited_texts).replace(",", "")
    numbers = {
        m.group(0).replace(",", "")
        for m in _NUMBER_TOKEN.finditer(text)
        if not re.fullmatch(r"(?:19|20)\d{2}", m.group(0))
    }
    missing = [n for n in numbers if not re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", already)]
    if not missing:
        return []
    holders: list[str] = []
    for evidence_id, cited in bundle.cited_texts.items():
        if evidence_id in cited_ids:
            continue
        plain = cited.content.replace(",", "")
        if any(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", plain) for n in missing):
            holders.append(evidence_id)
        if len(holders) >= MAX_EXTRA_HOLDERS:
            break
    return holders


class CompanyChatService:
    def __init__(
        self,
        *,
        analysis: CompanyAnalysisService,
        reports: BusinessReportRepository,
        retriever: CompanyRetriever,
        client: StructuredCompletionClient,
        store: ConversationStore,
        prompt_path: Path = PROMPT_PATH,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._analysis = analysis
        self._reports = reports
        self._retriever = retriever
        self._client = client
        self._store = store
        self._prompt = prompt_path.read_text(encoding="utf-8").strip()
        self._clock = clock
        self._new_id = id_factory

    # --- 조회 ----------------------------------------------------------------

    def history(self, conversation_id: str) -> ConversationHistory:
        conversation = self._store.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return ConversationHistory(
            conversation_id=conversation.conversation_id,
            corp_code=conversation.corp_code,
            job_context_id=conversation.job_context_id,
            messages=[_to_message(m) for m in self._store.history(conversation_id, limit=100)],
        )

    # --- 대화 ----------------------------------------------------------------

    def respond(self, request: ChatRequest) -> ChatResponse:
        conversation = self._conversation(request)
        stored = self._analysis.get_or_generate(request.corp_code)
        report = stored.report
        if report is None:
            raise RuntimeError(f"리포트를 만들 수 없습니다: {request.corp_code}")
        history = self._store.history(conversation.conversation_id, limit=MAX_HISTORY)

        bundle = ChatEvidence()
        report_evidence(report, bundle)
        business_report = self._reports.latest(request.corp_code)
        if business_report is not None:
            chunk_evidence(self._retriever.search(business_report, request.message, top_k=MAX_EVIDENCE), bundle)

        output, usage = self._ask(report, bundle, history, request.message)
        answer, citations, needs = self._verify(output, bundle)
        if answer is None:
            # 숫자가 근거와 어긋났다. 규칙을 상기시켜 한 번 다시 묻는다.
            output, usage = self._ask(report, bundle, history, request.message, retry_note=True)
            answer, citations, needs = self._verify(output, bundle)
        if answer is None:
            answer, citations = INSUFFICIENT_ANSWER, []

        now = self._clock()
        user = self._store.append(StoredMessage(self._new_id(), conversation.conversation_id, "USER", request.message, now))
        assistant = self._store.append(
            StoredMessage(
                self._new_id(),
                conversation.conversation_id,
                "ASSISTANT",
                answer,
                self._clock(),
                citations=[c.model_dump(mode="json", exclude_none=True) for c in citations],
                needs=[n.model_dump(mode="json") for n in needs],
            )
        )
        questions = [q.strip()[:200] for q in output.get("follow_up_questions") or [] if isinstance(q, str) and q.strip()][:3]
        return ChatResponse(
            conversation_id=conversation.conversation_id,
            corp_code=request.corp_code,
            user_message=_to_message(user),
            assistant_message=_to_message(assistant),
            follow_up_questions=questions,
            report_stage=report.stage,
            usage=usage,
        )

    def answer(
        self,
        *,
        corp_code: str,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """저장 없이 한 번 답한다. 총괄(supervisor)이 담당으로 호출할 때 쓴다.

        총괄은 대화를 스스로 들고 있으므로 여기서는 저장하지 않고, 결과를 총괄 규격에 맞는
        평범한 dict 로 돌려준다: message, citations, needs, follow_up_questions, report_stage.
        """
        stored = self._analysis.get_or_generate(corp_code)
        report = stored.report
        if report is None:
            raise RuntimeError(f"리포트를 만들 수 없습니다: {corp_code}")
        bundle = ChatEvidence()
        report_evidence(report, bundle)
        business_report = self._reports.latest(corp_code)
        if business_report is not None:
            chunk_evidence(self._retriever.search(business_report, message, top_k=MAX_EVIDENCE), bundle)
        turns = [
            StoredMessage("h", "h", str(item.get("role", "USER")).upper(), str(item.get("content", "")), self._clock())
            for item in (history or [])[-MAX_HISTORY:]
            if str(item.get("content", "")).strip()
        ]
        output, usage = self._ask(report, bundle, turns, message)
        answer, citations, needs = self._verify(output, bundle)
        if answer is None:
            output, usage = self._ask(report, bundle, turns, message, retry_note=True)
            answer, citations, needs = self._verify(output, bundle)
        if answer is None:
            answer, citations = INSUFFICIENT_ANSWER, []
        return {
            "corp_code": corp_code,
            "corp_name": report.corp_name,
            "message": answer,
            "citations": [c.model_dump(mode="json", exclude_none=True) for c in citations],
            "needs": [n.model_dump(mode="json") for n in needs],
            "follow_up_questions": [q.strip()[:200] for q in output.get("follow_up_questions") or [] if isinstance(q, str) and q.strip()][:3],
            "report_stage": report.stage,
            "usage": usage,
        }

    def _conversation(self, request: ChatRequest) -> Conversation:
        if request.conversation_id is None:
            now = self._clock()
            return self._store.create(Conversation(self._new_id(), request.corp_code, request.job_context_id, now, now))
        conversation = self._store.get(request.conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(request.conversation_id)
        if conversation.corp_code != request.corp_code:
            raise ConversationMismatchError(f"대화 {request.conversation_id} 는 {conversation.corp_code} 의 대화입니다")
        return conversation

    def _ask(self, report: CompanyReport, bundle: ChatEvidence, history: list[StoredMessage], message: str, *, retry_note: bool = False) -> tuple[dict[str, Any], dict[str, int] | None]:
        context = {
            "company": {"corp_code": report.corp_code, "name": report.corp_name, "fiscal_year": report.fiscal_year, "report_stage": report.stage},
            "evidence": bundle.payload,
            "history": [{"role": m.role.lower(), "content": m.content[:1_500]} for m in history],
        }
        system = self._prompt
        if retry_note:
            system += "\n\n주의: 직전 답의 숫자가 근거와 맞지 않았다. 근거에 적힌 숫자와 단위만 그대로 쓰고, 계산한 값은 쓰지 않는다."
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":")) + f"\n\n질문: {message}"},
        ]
        output = self._client.complete(messages, chat_schema(bundle.ids), max_tokens=MAX_OUTPUT_TOKENS)
        usage = getattr(self._client, "last_usage", None)
        return output, usage

    @staticmethod
    def _verify(output: dict[str, Any], bundle: ChatEvidence) -> tuple[str | None, list[Citation], list[ChatNeed]]:
        answer = _clean(output.get("answer"))
        ids = [i for i in output.get("citation_ids") or [] if i in bundle.citations]
        needs: list[ChatNeed] = []
        if output.get("needs_news"):
            reason = _clean(output.get("needs_reason")) or "최근 뉴스·시황 정보가 필요합니다."
            needs.append(ChatNeed(agent="news", reason=reason[:1_000]))
        if not answer:
            return None, [], needs
        cited = [bundle.cited_texts[i] for i in ids]
        if numeric_claim_violations(answer, cited) or share_claim_violations(answer, cited):
            # 모델이 인용을 빠뜨렸을 수 있다(실측: 재무 표만 인용하고 이익률 표는 안 인용). 이번에 넣어 준
            # 근거 전체에서 다시 찾아 통과하면 숫자를 담은 근거를 인용에 보태고, 그래도 안 되면 버린다.
            everything = list(bundle.cited_texts.values())
            if numeric_claim_violations(answer, everything) or share_claim_violations(answer, everything):
                return None, [], needs
            ids = ids + _holders_of(answer, bundle, ids)
        citations: list[Citation] = []
        seen: set[str] = set()
        for i in ids:
            citation = bundle.citations[i]
            if citation.source_id in seen:
                continue
            seen.add(citation.source_id)
            citations.append(citation)
        return answer[:4_000], citations[:20], needs


def _to_message(stored: StoredMessage) -> ChatMessage:
    return ChatMessage(
        message_id=stored.message_id,
        role=stored.role,  # type: ignore[arg-type]
        content=stored.content,
        created_at=stored.created_at,
        citations=[Citation.model_validate(c) for c in stored.citations][:20],
        needs=[ChatNeed.model_validate(n) for n in stored.needs][:4],
    )
