from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, Protocol

from pydantic import Field, StringConstraints

from ai.jd_coaching.baseline import call_qwen
from ai.news_intelligence.budget import remaining_timeout
from ai.news_intelligence.contracts import (
    CoverageAssessment,
    NewsCandidate,
    NewsContext,
    Scope,
    SignalDraft,
    StrictModel,
)
from ai.news_intelligence.prompt import build_news_messages
from ai.supervisor.contracts import ConversationMessage


class NewsOutputError(ValueError):
    """Qwen output failed the news schema or citation contract."""


class NewsModelUnavailable(RuntimeError):
    """Qwen transport or configuration failed before a usable response."""


class _CoverageOutput(CoverageAssessment):
    requested_scopes: list[Scope] = Field(..., min_length=1, max_length=3)


class _SignalOutput(SignalDraft):
    preparation_checks: list[str] = Field(..., max_length=3)
    source_ids: list[Annotated[str, StringConstraints(strip_whitespace=False)]] = Field(
        min_length=1, max_length=20,
    )


class _SignalsOutput(StrictModel):
    signals: list[_SignalOutput] = Field(max_length=9)


COVERAGE_SCHEMA = _CoverageOutput.model_json_schema()
SIGNALS_SCHEMA = _SignalsOutput.model_json_schema()

# V1 preparation checks are server-owned; model prose is never returned in this field.
_PREPARATION_BY_SCOPE = {
    "COMPANY": "해당 기업 변화와 관련된 본인 경험이 있는지 확인하세요.",
    "INDUSTRY": "해당 산업 변화와 관련된 본인 경험이 있는지 확인하세요.",
    "ROLE": "해당 직무 변화와 관련된 본인 경험이 있는지 확인하세요.",
}
_JD_PREPARATION_CHECK = "JD 요구사항과 연결할 수 있는 사실 근거를 정리하세요."

_GENERIC_TERMS = frozenset(
    "jd job jobs requirement requirements required requires relevant relevance "
    "the this that with from for and are was has have name "
    "기사 제목 내용 확인 점검 검토 정리 비교 준비 관련 관련성 요구 요구사항 직무 공고 기업 산업 변화 분석 "
    "대한 있습니다 있는 것으로 여부 및".split()
)
_KOREAN_ENDINGS = (
    "됐다는", "된다는", "했습니다", "됩니다", "입니다", "한다는", "한다", "합니다",
    "했는지", "했나요", "하세요", "하십시오", "해주세요", "하는", "하고", "이며", "라는", "할", "한",
    "에서는", "으로", "에서", "에게", "에는", "과의", "와의",
    "의", "은", "는", "이", "가", "을", "를", "에", "과", "와", "도",
)
_ANSWER_MARKER = re.compile(
    r"자기소개서|자소서|면접답변|coverletter|interviewanswer|copyinto|"
    r"그대로|제출|말하고|말하세요|답하세요|submit|sayas|repeatthis"
)
_FIRST_PERSON = re.compile(
    r"(?<![가-힣])(?:저[\W_]*는|제[\W_]*가|나[\W_]*는|내[\W_]*가)|\bi[\W_]+[a-z]|\bi['’]"
)
_PUNCTUATION_BREAK = r"(?<!\d)[.,]+|[.,]+(?!\d)|[!?;:\r\n。！？；，、\u2028\u2029]+"
_CLAUSE_BREAK = re.compile(
    _PUNCTUATION_BREAK + r"|\b(?:and|but)\b|"
    r"\s+(?:그리고|하지만|반면|및)\s+|(?<=[가-힣])(?:하고|하며|되며|이며|지만)\s+"
)


def _normalize(text: str) -> str:
    text = "".join(
        char for char in unicodedata.normalize("NFKC", text).casefold()
        if unicodedata.category(char) != "Cf"
    )
    return re.sub(r"퍼\s*센\s*트|\bp\s*e\s*r\s*c\s*e\s*n\s*t\b|\bper\s+cent\b|٪", "%", text)


def _terms(text: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[가-힣]+|[a-z]+", _normalize(text)):
        # Strip common particles only; this is a conservative lexical gate, not entailment.
        if re.fullmatch(r"[가-힣]+", token):
            for ending in _KOREAN_ENDINGS:
                if token.endswith(ending) and len(token) - len(ending) >= 2:
                    token = token[:-len(ending)]
                    break
        if len(token) >= 2 and token not in _GENERIC_TERMS:
            terms.add(token)
    return terms


def _quantities(text: str) -> set[str]:
    text = _normalize(text)
    return {
        re.sub(r"[\s,]", "", value)
        for value in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?\s*%?", text)
    }


def _grounded_clauses(claim: str, evidence: str) -> bool:
    # Each clause needs >=2 distinct source terms and >=80% content-token coverage.
    evidence_terms = _terms(evidence)
    clauses = [part.strip() for part in _CLAUSE_BREAK.split(_normalize(claim)) if part.strip()]
    for clause in clauses:
        terms = _terms(clause)
        grounded = terms & evidence_terms
        if len(grounded) < 2 or len(grounded) / max(len(terms), 1) < 0.8:
            return False
    return bool(clauses)


def _context_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            text for key, item in value.items()
            if key != "id" and not key.endswith("_id")
            for text in _context_strings(item)
        ]
    if isinstance(value, list):
        return [text for item in value for text in _context_strings(item)]
    return []


def _validate_content(
    draft: SignalDraft, sources: Sequence[NewsCandidate], context: NewsContext,
) -> None:
    """Reject lexical mismatches and unsafe prose; this does not prove semantic entailment."""
    article_text = " ".join(source.title for source in sources)
    jd_text = " ".join([context.position_name, context.jd_text, *_context_strings(context.role_elements)])
    for claim, evidence in (
        (draft.title, article_text), (draft.summary, article_text), (draft.jd_relevance, jd_text),
    ):
        if not _grounded_clauses(claim, evidence) or not _quantities(claim) <= _quantities(evidence):
            raise NewsOutputError("news content lacks grounded evidence")
    for text in (draft.title, draft.summary, draft.jd_relevance):
        normalized = _normalize(text)
        if _ANSWER_MARKER.search(re.sub(r"[\W_]+", "", normalized)) or _FIRST_PERSON.search(normalized):
            raise NewsOutputError("news content exceeds analysis boundaries")


class NewsModel(Protocol):
    def classify_coverage(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
    ) -> CoverageAssessment: ...

    def extract_signals(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
        conversation: Sequence[ConversationMessage],
    ) -> list[SignalDraft]: ...


def resolve_sources(
    source_ids: Sequence[str], candidates: Sequence[NewsCandidate],
) -> list[NewsCandidate]:
    by_id = {candidate.article_id: candidate for candidate in candidates}
    if len(by_id) != len(candidates):
        raise NewsOutputError("ambiguous candidate ids")
    if len(source_ids) != len(set(source_ids)):
        raise NewsOutputError("duplicate source ids")
    if any(source_id not in by_id for source_id in source_ids):
        raise NewsOutputError("unknown source ids")
    return [by_id[source_id] for source_id in source_ids]


class QwenNewsModel:
    def __init__(
        self, config: Mapping[str, str],
        qwen_caller: Callable[..., dict[str, Any]] = call_qwen,
    ) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller

    def _call(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
        *, coverage: bool,
    ) -> Any:
        try:
            response = self._qwen_caller(
                self._config,
                build_news_messages(context, candidates, instruction, coverage=coverage),
                timeout_seconds=remaining_timeout(30, NewsModelUnavailable),
                max_tokens=700 if coverage else 1800,
                schema=COVERAGE_SCHEMA if coverage else SIGNALS_SCHEMA,
                schema_name="news_coverage_v1" if coverage else "news_signals_v1",
            )
        except json.JSONDecodeError as error:
            raise NewsOutputError("invalid news JSON") from error
        except ValueError as error:
            # The shared caller wraps invalid content JSON in a legacy ValueError.
            if str(error) == "Qwen response does not contain valid JSON" and isinstance(
                error.__cause__, (KeyError, IndexError, TypeError, json.JSONDecodeError)
            ):
                raise NewsOutputError("invalid news JSON") from error
            raise NewsModelUnavailable("news model unavailable") from error
        except (RuntimeError, TimeoutError, ConnectionError) as error:
            raise NewsModelUnavailable("news model unavailable") from error
        remaining_timeout(30, NewsModelUnavailable)
        try:
            return response["output"]
        except (KeyError, TypeError) as error:
            raise NewsOutputError("invalid news response envelope") from error

    def classify_coverage(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
    ) -> CoverageAssessment:
        output = self._call(context, candidates, instruction, coverage=True)
        try:
            return _CoverageOutput.model_validate(output, strict=True)
        except (ValueError, TypeError) as error:
            raise NewsOutputError("invalid news coverage schema") from error

    def extract_signals(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
        conversation: Sequence[ConversationMessage],
    ) -> list[SignalDraft]:
        # History can contain applicant documents or unrelated facts; do not send it.
        output = self._call(context, candidates, instruction, coverage=False)
        try:
            drafts = _SignalsOutput.model_validate(output, strict=True).signals
        except (ValueError, TypeError) as error:
            raise NewsOutputError("invalid news signals schema") from error
        if any(count > 3 for count in Counter(draft.scope for draft in drafts).values()):
            raise NewsOutputError("at most three signals per scope")
        for draft in drafts:
            sources = resolve_sources(draft.source_ids, candidates)
            _validate_content(draft, sources, context)
        return [
            SignalDraft(
                **draft.model_dump(exclude={"preparation_checks"}),
                preparation_checks=[_PREPARATION_BY_SCOPE[draft.scope], _JD_PREPARATION_CHECK],
            )
            for draft in drafts
        ]
