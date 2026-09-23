"""한 AI 프로세스 안에서 GMS 요청의 시작 속도를 제어한다."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import threading
import time
from typing import TypeVar

from ai.llm.contracts import LlmRateLimitedError


T = TypeVar("T")


@dataclass(frozen=True)
class GmsGateSettings:
    max_concurrent_requests: int = 1
    min_interval_seconds: float = 1.0
    queue_timeout_seconds: float = 45.0
    rate_limit_cooldown_seconds: float = 10.0
    rate_limit_retry_count: int = 1
    max_queued_requests: int = 40

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "GmsGateSettings":
        def integer(name: str, default: int, *, minimum: int) -> int:
            raw = env.get(name, "").strip()
            try:
                value = int(raw) if raw else default
            except ValueError as error:
                raise ValueError(f"{name} must be an integer") from error
            if value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
            return value

        def decimal(name: str, default: float, *, minimum: float) -> float:
            raw = env.get(name, "").strip()
            try:
                value = float(raw) if raw else default
            except ValueError as error:
                raise ValueError(f"{name} must be a number") from error
            if value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
            return value

        return cls(
            max_concurrent_requests=integer("GMS_MAX_CONCURRENT_REQUESTS", 1, minimum=1),
            min_interval_seconds=decimal("GMS_MIN_INTERVAL_SECONDS", 1.0, minimum=0.0),
            queue_timeout_seconds=decimal("GMS_QUEUE_TIMEOUT_SECONDS", 45.0, minimum=0.001),
            rate_limit_cooldown_seconds=decimal("GMS_RATE_LIMIT_COOLDOWN_SECONDS", 10.0, minimum=0.0),
            rate_limit_retry_count=integer("GMS_RATE_LIMIT_RETRY_COUNT", 1, minimum=0),
            max_queued_requests=integer("GMS_MAX_QUEUED_REQUESTS", 40, minimum=1),
        )


class GmsRateLimitSignal(RuntimeError):
    """GMS 전송 계층이 429를 게이트에 전달하는 내부 신호."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds


class GmsRequestGate:
    def __init__(
        self,
        settings: GmsGateSettings,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._sleeper = sleeper
        self._condition = threading.Condition()
        self._queue: deque[object] = deque()
        self._in_flight = 0
        self._last_started: float | None = None
        self._blocked_until = 0.0

    def run(self, operation: Callable[[], T], *, operation_name: str) -> T:
        del operation_name  # 호출 종류를 기록할 로깅은 다음 단계에서 추가한다.
        queued_at = self._clock()
        retries = 0

        while True:
            ticket = object()
            self._acquire(ticket, queued_at)
            try:
                return operation()
            except GmsRateLimitSignal as error:
                retries += 1
                retry_after = error.retry_after_seconds or self._settings.rate_limit_cooldown_seconds
                with self._condition:
                    self._blocked_until = max(self._blocked_until, self._clock() + retry_after)
                    self._condition.notify_all()
                if retries > self._settings.rate_limit_retry_count:
                    raise LlmRateLimitedError("GMS", _seconds(retry_after)) from error
            finally:
                with self._condition:
                    self._in_flight -= 1
                    self._condition.notify_all()

    def _acquire(self, ticket: object, queued_at: float) -> None:
        with self._condition:
            if len(self._queue) >= self._settings.max_queued_requests:
                raise LlmRateLimitedError("GMS")
            self._queue.append(ticket)

        while True:
            with self._condition:
                now = self._clock()
                remaining = self._settings.queue_timeout_seconds - (now - queued_at)
                if remaining <= 0:
                    self._remove(ticket)
                    raise LlmRateLimitedError("GMS")
                if self._queue[0] is not ticket:
                    self._condition.wait(remaining)
                    continue
                if self._in_flight >= self._settings.max_concurrent_requests:
                    self._condition.wait(remaining)
                    continue
                interval = 0.0 if self._last_started is None else max(
                    0.0, self._settings.min_interval_seconds - (now - self._last_started)
                )
                delay = max(interval, self._blocked_until - now)
                if delay > remaining:
                    self._remove(ticket)
                    raise LlmRateLimitedError("GMS", _seconds(delay))
                if delay <= 0:
                    self._queue.popleft()
                    self._in_flight += 1
                    self._last_started = now
                    return

            self._sleeper(delay)

    def _remove(self, ticket: object) -> None:
        try:
            self._queue.remove(ticket)
        except ValueError:
            return
        self._condition.notify_all()


_REGISTRY_LOCK = threading.Lock()
_GATES: dict[str, GmsRequestGate] = {}


def gate_for(key: str) -> GmsRequestGate:
    """`공급자:모델` 마다 게이트 하나. 한도는 모델별로 따로 잡히므로 줄도 따로 선다.

    한 줄에 전부 세우면 flash-lite 가 429 를 받았을 때 GPT·Claude 호출까지 멈추고,
    모델을 나눠도 처리량이 한 모델일 때와 같아진다. 설정값은 아직 모델 공통이다.
    """
    with _REGISTRY_LOCK:
        gate = _GATES.get(key)
        if gate is None:
            import os

            gate = GmsRequestGate(GmsGateSettings.from_env(os.environ))
            _GATES[key] = gate
        return gate


def reset_gates() -> None:
    """테스트가 설정을 바꾼 뒤 게이트를 새로 만들게 한다."""
    with _REGISTRY_LOCK:
        _GATES.clear()


def _seconds(value: float) -> int:
    return max(1, round(value))
