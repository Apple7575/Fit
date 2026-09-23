"""GMS 요청 게이트의 순서·대기·제한 초과 동작."""
from __future__ import annotations

import unittest
from threading import Event, Thread
import time

from ai.llm.gms_gate import GmsGateSettings, GmsRequestGate
from ai.llm.gms_gate import GmsRateLimitSignal
from ai.llm.contracts import LlmRateLimitedError


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


class GmsRequestGateTest(unittest.TestCase):
    def test_reads_limits_from_environment(self):
        settings = GmsGateSettings.from_env({
            "GMS_MAX_CONCURRENT_REQUESTS": "2",
            "GMS_MIN_INTERVAL_SECONDS": "0.5",
            "GMS_QUEUE_TIMEOUT_SECONDS": "30",
            "GMS_RATE_LIMIT_COOLDOWN_SECONDS": "8",
            "GMS_RATE_LIMIT_RETRY_COUNT": "2",
            "GMS_MAX_QUEUED_REQUESTS": "7",
        })

        self.assertEqual(settings, GmsGateSettings(2, 0.5, 30.0, 8.0, 2, 7))

    def test_rejects_invalid_environment_limit(self):
        with self.assertRaisesRegex(ValueError, "GMS_MAX_QUEUED_REQUESTS"):
            GmsGateSettings.from_env({"GMS_MAX_QUEUED_REQUESTS": "0"})

    def test_waits_minimum_interval_before_second_send(self):
        clock = FakeClock()
        gate = GmsRequestGate(
            GmsGateSettings(
                max_concurrent_requests=1,
                min_interval_seconds=1.0,
                queue_timeout_seconds=45.0,
                rate_limit_cooldown_seconds=10.0,
                rate_limit_retry_count=1,
            ),
            clock=clock.now,
            sleeper=clock.sleep,
        )
        sent: list[str] = []

        self.assertEqual(gate.run(lambda: sent.append("first") or "one", operation_name="plan"), "one")
        self.assertEqual(gate.run(lambda: sent.append("second") or "two", operation_name="aggregate"), "two")

        self.assertEqual(sent, ["first", "second"])
        self.assertEqual(clock.sleeps, [1.0])

    def test_blocks_second_send_when_concurrency_limit_is_one(self):
        gate = GmsRequestGate(
            GmsGateSettings(1, 0.0, 45.0, 10.0, 1),
        )
        first_started = Event()
        second_started = Event()
        release = Event()

        first = Thread(target=lambda: gate.run(
            lambda: first_started.set() or release.wait(1), operation_name="first"
        ))
        second = Thread(target=lambda: gate.run(
            lambda: second_started.set() or release.wait(1), operation_name="second"
        ))
        first.start()
        self.assertTrue(first_started.wait(0.5))
        second.start()

        self.assertFalse(second_started.wait(0.1))
        release.set()
        first.join(1)
        second.join(1)
        self.assertTrue(second_started.is_set())

    def test_retries_once_after_rate_limit_cooldown(self):
        clock = FakeClock()
        gate = GmsRequestGate(
            GmsGateSettings(1, 0.0, 45.0, 10.0, 1),
            clock=clock.now,
            sleeper=clock.sleep,
        )
        attempts = 0

        def call() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise GmsRateLimitSignal(retry_after_seconds=7)
            return "ok"

        self.assertEqual(gate.run(call, operation_name="plan"), "ok")
        self.assertEqual(attempts, 2)
        self.assertEqual(clock.sleeps, [7.0])

    def test_expires_instead_of_waiting_past_queue_deadline(self):
        clock = FakeClock()
        gate = GmsRequestGate(
            GmsGateSettings(1, 0.0, 5.0, 10.0, 1),
            clock=clock.now,
            sleeper=clock.sleep,
        )

        with self.assertRaises(LlmRateLimitedError):
            gate.run(
                lambda: (_ for _ in ()).throw(GmsRateLimitSignal(retry_after_seconds=10)),
                operation_name="plan",
            )

    def test_rejects_request_when_waiting_queue_is_full(self):
        gate = GmsRequestGate(
            GmsGateSettings(1, 0.0, 45.0, 10.0, 1, max_queued_requests=1),
        )
        first_started = Event()
        release = Event()
        first = Thread(target=lambda: gate.run(
            lambda: first_started.set() or release.wait(1), operation_name="first"
        ))
        second = Thread(target=lambda: gate.run(lambda: "second", operation_name="second"))
        first.start()
        self.assertTrue(first_started.wait(0.5))
        second.start()
        deadline = time.monotonic() + 0.5
        while len(gate._queue) != 1 and time.monotonic() < deadline:
            time.sleep(0.01)

        with self.assertRaises(LlmRateLimitedError):
            gate.run(lambda: "third", operation_name="third")

        release.set()
        first.join(1)
        second.join(1)

    def test_burst_of_ten_thousand_requests_keeps_capacity_and_rejects_overflow(self):
        gate = GmsRequestGate(
            GmsGateSettings(1, 0.0, 45.0, 10.0, 1, max_queued_requests=40),
        )
        started = Event()
        release = Event()
        completed: list[int] = []
        rejected: list[int] = []

        def operation(number: int, *, hold: bool = False) -> None:
            def send() -> None:
                if hold:
                    started.set()
                    release.wait(1)
                completed.append(number)
            try:
                gate.run(send, operation_name="burst")
            except LlmRateLimitedError:
                rejected.append(number)

        first = Thread(target=lambda: operation(0, hold=True))
        first.start()
        self.assertTrue(started.wait(0.5))

        queued = [Thread(target=lambda number=number: operation(number)) for number in range(1, 41)]
        for worker in queued:
            worker.start()
        deadline = time.monotonic() + 1
        while len(gate._queue) != 40 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(gate._queue), 40)

        # 포화 상태의 나머지 9,959건은 새 스레드를 만들 필요조차 없다. 게이트 입구에서 즉시
        # 거절돼야 하며, 이 경로가 큐 길이 제한이 보호하려는 폭주 요청이다.
        for number in range(41, 10_000):
            operation(number)

        self.assertEqual(len(rejected), 9_959)
        self.assertEqual(len(completed), 0)
        release.set()
        first.join(1)
        for worker in queued:
            worker.join(1)

        self.assertEqual(completed, list(range(41)))
        self.assertFalse(any(worker.is_alive() for worker in [first, *queued]))


if __name__ == "__main__":
    unittest.main()
