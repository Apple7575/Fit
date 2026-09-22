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
        elif result.agent == "company":
            items.extend(_company_feedback(result.result))
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
        if requirement_id is None or label is None:
            continue
        feedback_id = f"jd-{requirement_id}"
        if len(feedback_id) > MAX_WRITING_FEEDBACK_ID_LENGTH:
            continue
        name = _non_blank_string(requirement.get("requirement")) or requirement_id
        if label == "SUPPORTED":
            # 확인된 근거는 글쓰기가 앞세울 재료다. 없는 것만 넘기면 글쓰기는 고칠 게 없다고 되묻는다.
            quotes = [
                item["evidence_quote"]
                for item in (requirement.get("present_evidence") or [])
                if isinstance(item, Mapping) and _non_blank_string(item.get("evidence_quote"))
            ][:2]
            content = f"SUPPORTED: 공고 요구사항 '{name}'의 근거가 초안에 있다. 이 부분을 요구사항과 연결해 앞세운다."
            if quotes:
                content += " 근거 문장: " + " / ".join(quotes)
        else:
            actions = _string_list(requirement.get("suggested_actions"))
            if actions is None or not actions:
                continue
            # "추가하세요"는 글쓰기가 할 수 없는 일(사실 추가)이라 되묻기의 원인이 된다.
            # 글쓰기가 할 수 있는 일로 바꿔 말한다: 주장하지 않고, 사용자에게 알린다.
            content = (
                f"{label}: 공고 요구사항 '{name}'의 근거가 초안에 없다. 이 역량을 갖춘 것처럼 쓰지 말고, "
                f"message 에서 사용자에게 채울 항목으로 알린다. 참고: " + " ".join(actions)
            )
        feedback.append({"feedback_id": feedback_id, "source": "jd", "content": content})
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


def _company_feedback(result: Mapping[str, Any]) -> list[dict[str, str]]:
    """기업 담당의 공시 기반 답을 방향 피드백으로 넘긴다. 글쓰기는 여기 있는 회사 사실만 쓸 수 있다."""
    message = _non_blank_string(result.get("message"))
    if message is None:
        return []
    corp_name = _non_blank_string(result.get("corp_name")) or "지원 기업"
    return [{
        "feedback_id": "company-analysis",
        "source": "company",
        "content": f"[{corp_name} 공시 기반 사실] {message.strip()} 이 사실과 지원자의 경험을 연결할 때만 회사 이야기를 쓴다.",
    }]


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
