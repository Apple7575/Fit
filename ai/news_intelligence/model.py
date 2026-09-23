from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, Protocol

from pydantic import Field, StringConstraints

from ai.jd_coaching.baseline import call_qwen
from ai.llm.contracts import LlmRateLimitedError
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


# 총괄이 담당 3개를 병렬로 돌리면 Qwen 응답이 느려진다. 90초 예산 안에서 호출당 상한을 둔다.
_CALL_TIMEOUT_SECONDS = 45


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

# 대소문자만 고르는 열거 필드. 스키마에 enum 을 넣어 보내도 모델이 'company' 처럼 소문자로
# 돌려주는 일이 있어(GMS 실측), 그대로 strict 검증에 넣으면 신호 전부를 버린다. 값의 뜻은
# 같으므로 검증 전에 대문자로 맞춘다. 알 수 없는 값은 그대로 두어 검증이 잡게 한다.
_ENUM_KEYS = frozenset({"scope", "company", "industry", "role", "evidence_level"})
_ENUM_LIST_KEYS = frozenset({"requested_scopes"})


def _uppercase_enums(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in _ENUM_KEYS and isinstance(item, str):
                out[key] = item.strip().upper()
            elif key in _ENUM_LIST_KEYS and isinstance(item, list):
                out[key] = [part.strip().upper() if isinstance(part, str) else part for part in item]
            else:
                out[key] = _uppercase_enums(item)
        return out
    if isinstance(value, list):
        return [_uppercase_enums(item) for item in value]
    return value

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
    _validate_article_claims(draft, sources)
    _validate_jd_relevance(draft, context)


def _validate_article_claims(draft: SignalDraft, sources: Sequence[NewsCandidate]) -> None:
    article_text = " ".join(source.title for source in sources)
    for claim in (draft.title, draft.summary):
        if not _grounded_clauses(claim, article_text) or not _quantities(claim) <= _quantities(article_text):
            raise NewsOutputError("news content lacks grounded evidence")
        _reject_unsafe_prose(claim)


def _validate_jd_relevance(draft: SignalDraft, context: NewsContext) -> None:
    jd_text = " ".join([context.position_name, context.jd_text, *_context_strings(context.role_elements)])
    if not _grounded_clauses(draft.jd_relevance, jd_text) or not _quantities(draft.jd_relevance) <= _quantities(jd_text):
        raise NewsOutputError("news content lacks grounded evidence")
    _reject_unsafe_prose(draft.jd_relevance)


def _reject_unsafe_prose(text: str) -> None:
    normalized = _normalize(text)
    if _ANSWER_MARKER.search(re.sub(r"[\W_]+", "", normalized)) or _FIRST_PERSON.search(normalized):
        raise NewsOutputError("news content exceeds analysis boundaries")


# 모델이 jd_relevance 에 JD 문구 대신 기사 제목을 그대로 넣는 일이 잦다(GMS 실측: 초안 3건
# 전부). 그러면 근거 검증에서 셋 다 떨어져 기사를 찾았는데도 "응답을 만들지 못했습니다" 가
# 된다. 기사 쪽 주장(title·summary)이 제목에 근거하면 신호는 살리고, JD 연결 문장만 서버
# 문구로 바꾼다 — preparation_checks 를 서버가 갖는 것과 같은 원칙이다.
_JD_RELEVANCE_FALLBACK = "JD의 {position_name} 직무와 관련해 살펴볼 기사입니다."


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
                timeout_seconds=remaining_timeout(_CALL_TIMEOUT_SECONDS, NewsModelUnavailable),
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
        except LlmRateLimitedError:
            raise
        except (RuntimeError, TimeoutError, ConnectionError) as error:
            raise NewsModelUnavailable("news model unavailable") from error
        remaining_timeout(_CALL_TIMEOUT_SECONDS, NewsModelUnavailable)
        try:
            return response["output"]
        except (KeyError, TypeError) as error:
            raise NewsOutputError("invalid news response envelope") from error

    def classify_coverage(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
    ) -> CoverageAssessment:
        output = _uppercase_enums(self._call(context, candidates, instruction, coverage=True))
        try:
            return _CoverageOutput.model_validate(output, strict=True)
        except (ValueError, TypeError) as error:
            raise NewsOutputError("invalid news coverage schema") from error

    def extract_signals(
        self, context: NewsContext, candidates: Sequence[NewsCandidate], instruction: str,
        conversation: Sequence[ConversationMessage],
    ) -> list[SignalDraft]:
        # History can contain applicant documents or unrelated facts; do not send it.
        output = _uppercase_enums(self._call(context, candidates, instruction, coverage=False))
        try:
            drafts = _SignalsOutput.model_validate(output, strict=True).signals
        except (ValueError, TypeError) as error:
            raise NewsOutputError("invalid news signals schema") from error
        # 모델이 scope별 3개를 넘겨 내면 실패시키지 않고 앞의 3개만 남긴다.
        # 모델은 이미 중요도 순으로 반환하고, 초과분 때문에 분석 전체를 버릴 이유는 없다.
        kept: list[_SignalOutput] = []
        per_scope: Counter[str] = Counter()
        for draft in drafts:
            if per_scope[draft.scope] >= 3:
                continue
            per_scope[draft.scope] += 1
            kept.append(draft)
        # 근거 검증에 걸린 신호만 버리고 나머지는 살린다. 전부 걸리면 재시도를 위해 실패한다.
        grounded: list[_SignalOutput] = []
        first_error: NewsOutputError | None = None
        for draft in kept:
            sources = resolve_sources(draft.source_ids, candidates)  # 출처 id 오류는 그대로 실패
            try:
                _validate_article_claims(draft, sources)
            except NewsOutputError as error:
                first_error = first_error or error
                continue
            try:
                _validate_jd_relevance(draft, context)
            except NewsOutputError:
                draft = draft.model_copy(update={
                    "jd_relevance": _JD_RELEVANCE_FALLBACK.format(position_name=context.position_name),
                })
            grounded.append(draft)
        if kept and not grounded and first_error is not None:
            raise first_error
        drafts = grounded
        return [
            SignalDraft(
                **draft.model_dump(exclude={"preparation_checks"}),
                preparation_checks=[_PREPARATION_BY_SCOPE[draft.scope], _JD_PREPARATION_CHECK],
            )
            for draft in drafts
        ]
