"""담당 간 위임 규칙.

담당은 서로를 직접 부르지 않는다. 담당이 "이게 더 필요하다"(needs)고 말하면
총괄이 그 담당을 대신 실행하고, 요청한 담당을 한 번 더 돌린다.

제한:
- 위임 라운드는 요청당 1회(MAX_ROUNDS). 위임으로 실행된 담당의 needs는 무시한다.
- 라운드당 최대 MAX_DELEGATIONS개 담당만 추가 실행한다.
- 위임 대상은 분석 담당(jd/position/news)이어야 하고, 컨텍스트가 있어야 하며,
  이미 실행된 담당은 다시 부르지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import re

from ai.supervisor.contracts import AgentNeed, AgentResult

_COMPANY_INFO_HINT = re.compile(r"기업|회사|사업|뉴스|기사|변화|동향|전략|투자|산업|시장")

ANALYSIS_AGENT_NAMES = frozenset({"jd", "position", "news"})
DOCUMENT_FREE_AGENTS = frozenset({"news"})  # 제출 문서 없이도 실행 가능한 담당
MAX_ROUNDS = 1
MAX_DELEGATIONS = 2


def extract_needs(agent: str, result: Mapping[str, Any] | None) -> list[AgentNeed]:
    """담당 결과에서 위임 요청을 읽는다. 필터링 전 원본 목록이다."""
    if not isinstance(result, Mapping):
        return []
    needs: list[AgentNeed] = []
    for item in result.get("needs") or []:
        if not isinstance(item, Mapping):
            continue
        try:
            needs.append(AgentNeed.model_validate(dict(item)))
        except (ValueError, TypeError):
            continue
    if agent == "writing":
        needs.extend(_writing_rule_needs(result))
    return needs


def _writing_rule_needs(result: Mapping[str, Any]) -> list[AgentNeed]:
    """글쓰기가 근거 부족(MISSING_EVIDENCE)을 경고하면 뉴스 근거를 요청한다.

    글쓰기 모델의 출력 규격을 바꾸지 않고 이미 있는 경고 코드를 위임 신호로 쓴다.
    """
    if result.get("status") == "CLARIFICATION_REQUIRED":
        # 글쓰기가 기업·사업 정보를 더 요구하면 사용자에게 되묻기 전에 뉴스 담당에게 먼저 묻는다.
        message = str(result.get("message") or "")
        if _COMPANY_INFO_HINT.search(message):
            return [AgentNeed(agent="news", reason=message.strip()[:1_000] or "기업 정보 필요")]
        return []
    revision = result.get("revision")
    if not isinstance(revision, Mapping):
        return []
    for warning in revision.get("warnings") or []:
        if isinstance(warning, Mapping) and warning.get("code") == "MISSING_EVIDENCE":
            message = str(warning.get("message") or "근거 부족").strip()[:1_000]
            return [AgentNeed(agent="news", reason=message or "근거 부족")]
    return []


def select_delegations(
    results: Sequence[AgentResult],
    *,
    available_agents: Iterable[str],
    already_run: Iterable[str],
    round_index: int,
) -> list[dict[str, str]]:
    """이번 라운드에 실행할 위임 목록 `{agent, requested_by, reason}`을 정한다."""
    if round_index >= MAX_ROUNDS:
        return []
    available = set(available_agents)
    executed = set(already_run)
    chosen: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    for result in results:
        if result.status != "SUCCESS" or result.delegated_from is not None:
            continue
        for need in result.needs:
            target = need.agent
            if (
                target == result.agent
                or target not in ANALYSIS_AGENT_NAMES
                or target not in available
                or target in executed
                or target in seen_targets
            ):
                continue
            seen_targets.add(target)
            chosen.append(
                {"agent": target, "requested_by": result.agent, "reason": need.reason}
            )
            if len(chosen) >= MAX_DELEGATIONS:
                return chosen
    return chosen


def latest_results(results: Sequence[AgentResult]) -> list[AgentResult]:
    """담당별로 마지막 실행 결과만 남긴다(재실행이 이전 결과를 대체)."""
    latest: dict[str, AgentResult] = {}
    for item in results:
        latest[item.agent] = item
    return list(latest.values())


def superseded_results(results: Sequence[AgentResult]) -> list[AgentResult]:
    """재실행으로 대체된 이전 결과들(추적용)."""
    seen: set[str] = set()
    superseded: list[AgentResult] = []
    for item in reversed(results):
        if item.agent in seen:
            superseded.append(item)
        seen.add(item.agent)
    superseded.reverse()
    return superseded


def order_results(
    results: Sequence[AgentResult], plan_agents: Sequence[str]
) -> list[AgentResult]:
    """계획 순서 → 위임으로 추가된 담당(실행 순서) 순으로 정렬한다."""
    order = {name: index for index, name in enumerate(plan_agents)}
    fallback = len(order)
    indexed = sorted(
        enumerate(results),
        key=lambda pair: (order.get(pair[1].agent, fallback), pair[0]),
    )
    return [item for _, item in indexed]
