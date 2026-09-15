from collections.abc import Mapping
from typing import Any


NO_TECHNICAL_CLAIM_MESSAGE = (
    "구체화할 기술 경험을 찾지 못했습니다. "
    "맡았던 문제와 직접 수행한 행동을 알려 주세요."
)

ELEMENT_ORDER = (
    "PROBLEM",
    "ROLE",
    "ACTION",
    "REASONING",
    "MECHANISM",
    "VERIFICATION",
    "RESULT",
)
ELEMENT_LABELS = {
    "PROBLEM": "문제 상황",
    "ROLE": "담당 역할",
    "ACTION": "직접 수행한 행동",
    "REASONING": "선택 이유",
    "MECHANISM": "구체적인 동작 방식",
    "VERIFICATION": "검증 방법",
    "RESULT": "결과",
}
QUESTION_BY_ELEMENT = {
    "PROBLEM": "당시 해결해야 했던 문제나 제약이 무엇이었는지 설명해 주세요.",
    "ROLE": "그 과정에서 본인이 직접 맡은 범위가 무엇이었는지 설명해 주세요.",
    "ACTION": "문제를 해결하기 위해 본인이 직접 수행한 행동을 설명해 주세요.",
    "REASONING": "그 방법을 선택한 기준과 다른 선택지보다 적합했던 이유를 설명해 주세요.",
    "MECHANISM": "적용한 방법이 실제로 어떻게 동작했는지 설명해 주세요.",
    "VERIFICATION": "변화 여부를 어떤 방법과 기준으로 확인했는지 설명해 주세요.",
    "RESULT": "그 행동으로 실제로 무엇이 달라졌는지 설명해 주세요.",
}


def render_position_message(analysis: Mapping[str, Any]) -> str:
    if analysis["analysis_status"] == "NO_TECHNICAL_CLAIM":
        return NO_TECHNICAL_CLAIM_MESSAGE

    blocks: list[str] = []
    for finding in analysis["findings"]:
        claim = finding["claim"]["quote"]
        missing = set(finding["missing_elements"])
        ordered_missing = [element for element in ELEMENT_ORDER if element in missing]
        if finding["verdict"] == "SUFFICIENT":
            blocks.append(f'"{claim}" 경험은 필요한 연결고리가 모두 확인됩니다.')
            continue

        missing_labels = ", ".join(ELEMENT_LABELS[element] for element in ordered_missing)
        lines = [f'"{claim}" 경험에서 {missing_labels} 설명이 빠져 있습니다.']
        lines.extend(
            f"- {QUESTION_BY_ELEMENT[element]}" for element in ordered_missing[:2]
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
