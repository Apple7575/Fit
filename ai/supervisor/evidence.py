"""담당별 결과에서 공통 근거(Evidence)와 사용량(usage)을 추출한다.

담당 서비스의 출력 형태는 각자 다르다. 여기서 한 번만 변환해 총괄 응답에
같은 형태로 싣는다. 담당 서비스 자체는 건드리지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ai.supervisor.contracts import AgentName, Evidence

MAX_EXCERPT = 1_000


def extract_evidence(agent: AgentName, result: Mapping[str, Any] | None) -> list[Evidence]:
    if not isinstance(result, Mapping):
        return []
    extractor = _EXTRACTORS.get(agent)
    if extractor is None:
        return []
    try:
        return _dedupe(extractor(result))
    except (KeyError, TypeError, ValueError, AttributeError):
        # 근거 추출 실패가 담당 결과 자체를 실패로 만들면 안 된다.
        return []


def extract_usage(result: Mapping[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(result, Mapping):
        return None
    usage = result.get("usage")
    if not isinstance(usage, Mapping):
        return None
    cleaned = {
        str(key): int(value)
        for key, value in usage.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    return cleaned or None


def merge_evidence(results: Iterable[Any]) -> list[Evidence]:
    """여러 담당 결과의 근거를 순서를 유지하며 중복 제거해 합친다."""
    collected: list[Evidence] = []
    for item in results:
        collected.extend(getattr(item, "evidence", []) or [])
    return _dedupe(collected)


def _dedupe(items: Sequence[Evidence]) -> list[Evidence]:
    seen: set[str] = set()
    unique: list[Evidence] = []
    for item in items:
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        unique.append(item)
    return unique


def _news(result: Mapping[str, Any]) -> list[Evidence]:
    analysis = result.get("analysis")
    if not isinstance(analysis, Mapping):
        return []
    evidence: list[Evidence] = []
    for signal in analysis.get("signals") or []:
        for source in signal.get("sources") or []:
            article_id = str(source["article_id"])
            evidence.append(
                Evidence(
                    evidence_id=f"news:{article_id}",
                    source_type="NEWS_ARTICLE",
                    source_id=article_id,
                    agent="news",
                    title=_text(source.get("title")),
                    date=_text(source.get("published_at")),
                    url=_text(source.get("url")),
                    excerpt=_text(signal.get("summary")),
                )
            )
    return evidence


def _jd(result: Mapping[str, Any]) -> list[Evidence]:
    evidence: list[Evidence] = []
    context_id = _text(result.get("context_id"))
    if context_id:
        title = " / ".join(
            part
            for part in (_text(result.get("company_name")), _text(result.get("position_name")))
            if part
        )
        evidence.append(
            Evidence(
                evidence_id=f"jd:{context_id}",
                source_type="JOB_POSTING",
                source_id=context_id,
                agent="jd",
                title=title or None,
            )
        )
    for requirement in result.get("requirements") or []:
        for present in requirement.get("present_evidence") or []:
            document_id = str(present["document_id"])
            start = present.get("start_offset")
            end = present.get("end_offset")
            evidence.append(
                Evidence(
                    evidence_id=f"doc:{document_id}:{start}-{end}",
                    source_type="USER_DOCUMENT",
                    source_id=document_id,
                    agent="jd",
                    title=_text(requirement.get("requirement")),
                    excerpt=_text(present.get("evidence_quote")),
                )
            )
    return evidence


def _position(result: Mapping[str, Any]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for finding in result.get("findings") or []:
        claim = finding.get("claim")
        if not isinstance(claim, Mapping):
            continue
        document_id = str(claim["document_id"])
        start = claim.get("start_offset")
        end = claim.get("end_offset")
        evidence.append(
            Evidence(
                evidence_id=f"doc:{document_id}:{start}-{end}",
                source_type="USER_DOCUMENT",
                source_id=document_id,
                agent="position",
                title=_text(finding.get("claim_type")),
                excerpt=_text(claim.get("quote")),
            )
        )
    return evidence


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:MAX_EXCERPT]


# writing 담당은 사실 근거를 생산하지 않는다(다른 담당의 feedback을 소비만 한다).
_EXTRACTORS = {"news": _news, "jd": _jd, "position": _position}
