from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class _Deadline:
    end: float
    clock: Callable[[], float]


# The synchronous worker and its boundaries share one request-local deadline.
_deadline: ContextVar[_Deadline | None] = ContextVar("news_deadline", default=None)


@contextmanager
def news_budget(seconds: float, clock: Callable[[], float]) -> Iterator[None]:
    token = _deadline.set(_Deadline(clock() + seconds, clock))
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_timeout(cap: float, unavailable: Callable[[], Exception]) -> float:
    deadline = _deadline.get()
    remaining = cap if deadline is None else min(cap, deadline.end - deadline.clock())
    if remaining <= 0:
        raise unavailable()
    return remaining
