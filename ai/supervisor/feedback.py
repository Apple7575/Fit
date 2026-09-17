from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ai.supervisor.contracts import AgentResult


MAX_WRITING_FEEDBACK_ID_LENGTH = 100


def normalize_writing_feedback(
    results: Sequence[AgentResult],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for result in results:
        if result.status != "SUCCESS" or not isinstance(result.result, Mapping):
            continue
        if result.agent == "jd":
            items.extend(_jd_feedback(result.result))
        elif result.agent == "position":
            items.extend(_position_feedback(result.result))
        elif result.agent == "news":
            items.extend(_news_feedback(result.result))
    return [
        {**item, "content": item["content"][:2_000]}
        for item in items[:20]
    ]


def _jd_feedback(result: Mapping[str, Any]) -> list[dict[str, str]]:
    requirements = result.get("requirements")
    if not isinstance(requirements, list):
        return []
    feedback: list[dict[str, str]] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            continue
        requirement_id = _non_blank_string(requirement.get("requirement_id"))
        label = _non_blank_string(requirement.get("label"))
        actions = _string_list(requirement.get("suggested_actions"))
        if requirement_id is None or label is None or actions is None or not actions:
            continue
        feedback_id = f"jd-{requirement_id}"
        if len(feedback_id) > MAX_WRITING_FEEDBACK_ID_LENGTH:
            continue
        feedback.append({
            "feedback_id": feedback_id,
            "source": "jd",
            "content": f"{label}: " + " ".join(actions),
        })
    return feedback


def _position_feedback(result: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = result.get("findings")
    if not isinstance(findings, list):
        return []
    feedback: list[dict[str, str]] = []
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        finding_id = _non_blank_string(finding.get("finding_id"))
        missing_elements = _string_list(finding.get("missing_elements"))
        reason = _non_blank_string(finding.get("reason"))
        questions = _string_list(finding.get("follow_up_questions"))
        if (
            finding_id is None
            or missing_elements is None
            or reason is None
            or questions is None
            or (not missing_elements and not questions)
        ):
            continue
        feedback_id = f"position-{finding_id}"
        if len(feedback_id) > MAX_WRITING_FEEDBACK_ID_LENGTH:
            continue
        content = f"누락 요소: {', '.join(missing_elements)}. 근거: {reason}"
        if questions:
            content += f" 후속 질문: {' '.join(questions)}"
        feedback.append({
            "feedback_id": feedback_id,
            "source": "position",
            "content": content,
        })
    return feedback


def _news_feedback(result: Mapping[str, Any]) -> list[dict[str, str]]:
    """뉴스 신호를 글쓰기 방향 피드백으로 바꾼다. 기사 사실은 출처와 함께 전달한다."""
    analysis = result.get("analysis")
    if not isinstance(analysis, Mapping):
        return []
    signals = analysis.get("signals")
    if not isinstance(signals, list):
        return []
    feedback: list[dict[str, str]] = []
    for signal in signals:
        if not isinstance(signal, Mapping):
            continue
        signal_id = _non_blank_string(signal.get("signal_id"))
        title = _non_blank_string(signal.get("title"))
        summary = _non_blank_string(signal.get("summary"))
        relevance = _non_blank_string(signal.get("jd_relevance"))
        if signal_id is None or title is None or summary is None:
            continue
        feedback_id = f"news-{signal_id}"
        if len(feedback_id) > MAX_WRITING_FEEDBACK_ID_LENGTH:
            continue
        sources = signal.get("sources")
        titles = [
            source["title"]
            for source in (sources if isinstance(sources, list) else [])
            if isinstance(source, Mapping) and _non_blank_string(source.get("title"))
        ][:3]
        content = f"[{signal.get('scope', 'COMPANY')}] {title}: {summary}"
        if relevance:
            content += f" 직무 관련성: {relevance}"
        if titles:
            content += f" 출처: {' / '.join(titles)}"
        feedback.append({"feedback_id": feedback_id, "source": "news", "content": content})
    return feedback


def _non_blank_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if any(_non_blank_string(item) is None for item in value):
        return None
    return value
