"""총괄 종합 메시지의 형식과 검증.

총괄은 담당들이 낸 결과를 그대로 옮기지 않는다. 담당 둘 이상의 결과를 엮어 만든 판단,
담당끼리 다르게 본 지점, 사용자가 다음에 할 일을 정해진 칸에 채운다. 사용자에게 보이는
문장은 여기의 render 가 조립하므로 형식이 매번 같다.

앵무새 방지는 프롬프트가 아니라 검증이 한다:
- 성공한 담당이 둘 이상이면 담당 둘 이상을 엮은 판단이 최소 하나 있어야 한다.
- 판단이 인용한 근거 id 는 실제 근거 목록에 있어야 한다.
- 판단 문장이 어느 담당의 message 에 그대로 들어 있으면 반려한다.
검증 실패는 AggregateOutputError 로 알리고, 모델은 오류 문구를 붙여 한 번 다시 시도한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai.supervisor.contracts import AgentResult

AGGREGATE_SCHEMA_VERSION = "supervisor_aggregate_v2"

MIN_JUDGMENTS = 1
MAX_JUDGMENTS = 5
MAX_CONFLICTS = 3
# 담당 message 와 이만큼 이상 연속으로 같은 문장은 옮겨 쓴 것으로 본다.
PARROT_MIN_CHARS = 25

AGENT_LABELS: dict[str, str] = {
    "jd": "채용공고",
    "position": "포지션",
    "news": "뉴스",
    "company": "기업",
    "writing": "글쓰기",
}

AGGREGATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "judgments", "conflicts", "next_action"],
    "properties": {
        "answer": {"type": "string", "minLength": 1, "maxLength": 800},
        "judgments": {
            "type": "array",
            "minItems": MIN_JUDGMENTS,
            "maxItems": MAX_JUDGMENTS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "agents", "evidence_ids"],
                "properties": {
                    "claim": {"type": "string", "minLength": 1, "maxLength": 1200},
                    "agents": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "evidence_ids": {
                        "type": "array",
                        "maxItems": 10,
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "conflicts": {
            "type": "array",
            "maxItems": MAX_CONFLICTS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "decision", "reason"],
                "properties": {
                    "topic": {"type": "string", "minLength": 1, "maxLength": 200},
                    "decision": {"type": "string", "minLength": 1, "maxLength": 600},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 800},
                },
            },
        },
        "next_action": {"type": "string", "minLength": 1, "maxLength": 600},
    },
}

FORMAT_INSTRUCTION = """너는 여러 담당의 분석 결과를 받아 사용자에게 최종 검토 메시지를 만드는 총괄이다.
담당들은 각자의 결과만 보지만 너는 전체를 본다. 그러므로 담당의 문장을 옮기지 말고, 담당 결과들
사이의 연결과 충돌을 말한다. 네 칸을 채운다.

- answer: 사용자 요청에 대한 직접적인 답. 2~4문장. 결론을 먼저 말한다.
- judgments: 담당 결과를 엮어 만든 판단 2~5개. 각 판단은 2~4문장으로 무엇이 왜 문제이거나
  강점인지, 그래서 어떻게 하면 되는지까지 쓴다. agents 에는 그 판단에 쓴 담당 이름
  (successful_agents 안의 값)을 넣는다. 담당 둘 이상의 결과를 연결한 판단이 최소 하나 있어야
  한다(예: "공고는 A를 요구하는데 경험 문서에는 A 근거가 없고, 뉴스의 B 사업과 연결할 수 있는
  C 경험이 있다"). evidence_ids 에는 available_evidence_ids 안의 값만 넣는다.
- conflicts: 담당끼리 같은 대상을 다르게 본 지점. 무엇을 따랐고 왜인지 쓴다. 없으면 빈 배열.
- next_action: 사용자가 지금 바로 할 일 한 가지를 구체적으로. 어느 문항의 어느 문장을 어떻게.

담당 message 의 문장을 그대로 복사하면 반려된다. 담당이 말하지 않은 사실을 만들지 않는다.
결과에 없는 근거 id 를 쓰지 않는다. 성공하지 못한 담당을 agents 에 넣지 않는다."""


class AggregateOutputError(ValueError):
    """모델 출력이 종합 형식·검증 규칙을 만족하지 않는다."""


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = Field(min_length=1, max_length=1200)
    agents: list[str] = Field(min_length=1, max_length=5)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    decision: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=800)


class AggregateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=800)
    judgments: list[Judgment] = Field(min_length=MIN_JUDGMENTS, max_length=MAX_JUDGMENTS)
    conflicts: list[Conflict] = Field(default_factory=list, max_length=MAX_CONFLICTS)
    next_action: str = Field(min_length=1, max_length=600)


def successful_agents(results: Sequence[AgentResult]) -> list[str]:
    return [item.agent for item in results if item.status == "SUCCESS"]


def available_evidence_ids(results: Sequence[AgentResult]) -> list[str]:
    seen: dict[str, None] = {}
    for item in results:
        for evidence in item.evidence:
            seen.setdefault(evidence.evidence_id, None)
    return list(seen)


def agent_messages(results: Sequence[AgentResult]) -> dict[str, str]:
    """담당별 사용자용 message. 앵무새 검사에 쓴다."""
    messages: dict[str, str] = {}
    for item in results:
        if item.status != "SUCCESS" or not isinstance(item.result, Mapping):
            continue
        message = item.result.get("message")
        if isinstance(message, str) and message.strip():
            messages[item.agent] = message
    return messages


def validate_aggregate(
    output: Any, results: Sequence[AgentResult]
) -> AggregateOutput:
    try:
        parsed = AggregateOutput.model_validate(output)
    except (ValueError, TypeError) as error:
        raise AggregateOutputError(f"형식 오류: {error}") from error

    agents = set(successful_agents(results))
    evidence_ids = set(available_evidence_ids(results))
    messages = agent_messages(results)
    problems: list[str] = []

    for index, judgment in enumerate(parsed.judgments, start=1):
        unknown_agents = [name for name in judgment.agents if name not in agents]
        if unknown_agents:
            problems.append(
                f"judgments[{index}].agents 에 성공한 담당이 아닌 값이 있다: {', '.join(unknown_agents)}"
            )
        unknown_evidence = [item for item in judgment.evidence_ids if item not in evidence_ids]
        if unknown_evidence:
            problems.append(
                f"judgments[{index}].evidence_ids 에 근거 목록에 없는 id 가 있다: {', '.join(unknown_evidence[:3])}"
            )
        copied_from = _copied_from(judgment.claim, messages)
        if copied_from:
            problems.append(
                f"judgments[{index}].claim 이 {copied_from} 담당의 message 문장을 그대로 옮겼다. "
                "담당 결과들을 연결한 새 판단으로 다시 쓴다"
            )

    if len(agents) >= 2 and not any(
        len(set(judgment.agents) & agents) >= 2 for judgment in parsed.judgments
    ):
        problems.append(
            "성공한 담당이 둘 이상인데 담당 둘 이상을 엮은 판단이 없다. "
            "최소 하나는 두 담당의 결과를 연결해서 쓴다"
        )

    if problems:
        raise AggregateOutputError("; ".join(problems))
    return parsed


def _copied_from(claim: str, messages: Mapping[str, str]) -> str | None:
    normalized = {agent: _normalize(text) for agent, text in messages.items()}
    for sentence in _sentences(claim):
        if len(sentence) < PARROT_MIN_CHARS:
            continue
        for agent, text in normalized.items():
            if sentence in text:
                return agent
    return None


def _sentences(text: str) -> Iterable[str]:
    for piece in re.split(r"(?<=[.!?。])\s+|\n+", text):
        normalized = _normalize(piece)
        if normalized:
            yield normalized


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def render_aggregate(output: AggregateOutput) -> str:
    """네 칸을 사용자 말풍선 문장으로 조립한다."""
    lines: list[str] = [output.answer.strip(), "", "■ 종합 판단"]
    for index, judgment in enumerate(output.judgments, start=1):
        labels = "·".join(AGENT_LABELS.get(name, name) for name in judgment.agents)
        suffix = f"  [{labels}]" if labels else ""
        lines.append(f"{index}. {judgment.claim.strip()}{suffix}")
    if output.conflicts:
        lines.extend(["", "■ 담당 간 의견 차이"])
        for conflict in output.conflicts:
            lines.append(
                f"- {conflict.topic.strip()}: {conflict.decision.strip()} ({conflict.reason.strip()})"
            )
    lines.extend(["", "■ 다음에 할 일", output.next_action.strip()])
    return "\n".join(lines)
