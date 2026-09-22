"""LLM 호출의 우선순위.

GMS 분당 한도가 찼을 때 누가 먼저 나가야 하는지 정한다. 사용자가 방에 직접 남긴 질문(INTERACTIVE)이
사용자가 묻기 전에 미리 도는 자동 검토(BACKGROUND)보다 앞선다 — 자동 검토가 방 여섯 개를 돌며 한도를
다 쓰면 방금 보낸 질문이 뒤에 서게 되는데, 그 반대여야 한다.

요청을 받는 자리(총괄 API)에서 `priority_scope` 로 감싸면, 그 요청이 부르는 모든 담당·모델 호출이
같은 우선순위를 물려받는다. contextvar 라 LangGraph 의 병렬 노드에도 전달된다. 직접 스레드 풀을
쓰는 곳은 `contextvars.copy_context()` 로 옮겨 줘야 한다(JD 담당 참고).
"""
from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator

INTERACTIVE = 0
BACKGROUND = 1

_current: contextvars.ContextVar[int] = contextvars.ContextVar("llm_priority", default=INTERACTIVE)


def current_priority() -> int:
    return _current.get()


@contextlib.contextmanager
def priority_scope(level: int) -> Iterator[None]:
    token = _current.set(level)
    try:
        yield
    finally:
        _current.reset(token)
