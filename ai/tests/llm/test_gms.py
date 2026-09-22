"""GMS 어댑터 — 스키마·메시지 변환과 응답 해석."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from ai.llm import complete_structured
from ai.llm.contracts import LlmHttpError, LlmResponseError
from ai.llm.gms import to_gemini_contents, to_gemini_schema


class ToGeminiSchemaTest(unittest.TestCase):
    def test_types_become_uppercase(self):
        converted = to_gemini_schema({
            "type": "object",
            "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["name"],
        })

        self.assertEqual(converted["type"], "OBJECT")
        self.assertEqual(converted["properties"]["name"]["type"], "STRING")
        self.assertEqual(converted["properties"]["count"]["type"], "INTEGER")
        self.assertEqual(converted["required"], ["name"])

    def test_drops_keywords_gemini_does_not_know(self):
        """additionalProperties 를 그대로 보내면 400 이 온다."""
        converted = to_gemini_schema({
            "type": "object",
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#",
            "properties": {"name": {"type": "string", "additionalProperties": False}},
        })

        self.assertNotIn("additionalProperties", converted)
        self.assertNotIn("$schema", converted)
        self.assertNotIn("additionalProperties", converted["properties"]["name"])

    def test_array_bounds_survive(self):
        """떨구면 담당들의 "1~3개" 제약이 사라져 모델이 넘게 낸다 — JD 구조화가 이걸로 깨졌다."""
        converted = to_gemini_schema({
            "type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"},
        })

        self.assertEqual(converted["minItems"], 1)
        self.assertEqual(converted["maxItems"], 3)

    def test_nullable_type_array_becomes_nullable_flag(self):
        converted = to_gemini_schema({"type": ["string", "null"]})

        self.assertEqual(converted["type"], "STRING")
        self.assertTrue(converted["nullable"])

    def test_nested_arrays_are_converted(self):
        converted = to_gemini_schema({
            "type": "array",
            "items": {"type": "object", "properties": {"text": {"type": "string"}}},
        })

        self.assertEqual(converted["type"], "ARRAY")
        self.assertEqual(converted["items"]["type"], "OBJECT")
        self.assertEqual(converted["items"]["properties"]["text"]["type"], "STRING")

    def test_any_of_with_null_becomes_nullable(self):
        converted = to_gemini_schema({"anyOf": [{"type": "string"}, {"type": "null"}]})

        self.assertEqual(converted["type"], "STRING")
        self.assertTrue(converted["nullable"])

    def test_enum_and_description_survive(self):
        converted = to_gemini_schema({
            "type": "string", "enum": ["A", "B"], "description": "고른다",
        })

        self.assertEqual(converted["enum"], ["A", "B"])
        self.assertEqual(converted["description"], "고른다")


class ToGeminiContentsTest(unittest.TestCase):
    def test_system_messages_merge_into_system_instruction(self):
        system, contents = to_gemini_contents([
            {"role": "system", "content": "너는 분석가다."},
            {"role": "system", "content": "한국어로 답해라."},
            {"role": "user", "content": "매출은?"},
        ])

        self.assertEqual(system["parts"][0]["text"], "너는 분석가다.\n\n한국어로 답해라.")
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "user")

    def test_assistant_becomes_model(self):
        _, contents = to_gemini_contents([
            {"role": "user", "content": "매출은?"},
            {"role": "assistant", "content": "186조원입니다."},
            {"role": "user", "content": "작년은?"},
        ])

        self.assertEqual([item["role"] for item in contents], ["user", "model", "user"])

    def test_blank_messages_are_dropped(self):
        system, contents = to_gemini_contents([
            {"role": "system", "content": "   "},
            {"role": "user", "content": "매출은?"},
        ])

        self.assertIsNone(system)
        self.assertEqual(len(contents), 1)


class GmsCompleteTest(unittest.TestCase):
    CONFIG = {
        "provider": "gms",
        "base_url": "https://gms.example/gmsapi",
        "model": "gemini-2.5-flash-lite",
        "api_key": "key",
    }
    SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}

    def test_reads_answer_and_normalises_usage(self):
        """토큰 이름을 vLLM 쪽에 맞춘다 — 사용량을 쓰는 곳이 한 가지만 알면 된다."""
        payload = {
            "candidates": [{"content": {"parts": [{"text": '{"answer": "186조원"}'}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14},
            "modelVersion": "gemini-2.5-flash-lite-001",
        }
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            result = complete_structured(
                self.CONFIG, [{"role": "user", "content": "매출은?"}],
                schema=self.SCHEMA, schema_name="x", max_tokens=100,
            )

        self.assertEqual(result["output"], {"answer": "186조원"})
        self.assertEqual(result["model"], "gemini-2.5-flash-lite-001")
        self.assertEqual(result["usage"], {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})

    def test_sends_converted_schema_and_key_header(self):
        payload = {"candidates": [{"content": {"parts": [{"text": '{"answer": "x"}'}]}}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            complete_structured(
                self.CONFIG, [{"role": "system", "content": "지침"}, {"role": "user", "content": "매출은?"}],
                schema={"type": "object", "additionalProperties": False, "properties": {}},
                schema_name="x", max_tokens=100,
            )
            request = opener.return_value.open.call_args[0][0]

        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["generationConfig"]["responseSchema"]["type"], "OBJECT")
        self.assertNotIn("additionalProperties", body["generationConfig"]["responseSchema"])
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "지침")
        self.assertEqual(request.headers["X-goog-api-key"], "key")
        self.assertTrue(request.full_url.endswith(":generateContent"))

    def test_retries_without_array_bounds_when_schema_is_too_complex(self):
        """중첩 배열에 길이가 붙으면 Gemini 가 400 을 준다. 제약을 빼고 한 번 더 보낸다."""
        bounded = {
            "type": "object",
            "properties": {"items": {"type": "array", "maxItems": 12, "items": {"type": "string"}}},
        }
        ok = {"candidates": [{"content": {"parts": [{"text": '{"items": []}'}]}}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = [
                _HttpError(400, '{"error":{"message":"The specified schema produces a constraint that has too many states for serving."}}'),
                _Response(ok),
            ]
            result = complete_structured(
                self.CONFIG, [{"role": "user", "content": "x"}],
                schema=bounded, schema_name="x", max_tokens=100,
            )
            second = opener.return_value.open.call_args_list[1][0][0]

        self.assertEqual(result["output"], {"items": []})
        body = json.loads(second.data.decode("utf-8"))
        self.assertNotIn("maxItems", json.dumps(body["generationConfig"]["responseSchema"]))

    def test_other_http_errors_are_not_retried(self):
        """키가 틀렸을 때까지 두 번 부르면 원인이 가려진다."""
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = _HttpError(401, "unauthorized")
            with self.assertRaises(LlmHttpError):
                complete_structured(
                    self.CONFIG, [{"role": "user", "content": "x"}],
                    schema=self.SCHEMA, schema_name="x", max_tokens=100,
                )

        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_safety_block_reports_finish_reason(self):
        """안전 필터에 걸리면 parts 가 없다. 원인을 남겨야 추적된다."""
        payload = {"candidates": [{"finishReason": "SAFETY"}]}
        with patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = _Response(payload)
            with self.assertRaises(LlmResponseError) as caught:
                complete_structured(
                    self.CONFIG, [{"role": "user", "content": "x"}],
                    schema=self.SCHEMA, schema_name="x", max_tokens=100,
                )

        self.assertIn("SAFETY", str(caught.exception))


class _HttpError(urllib.error.HTTPError):
    def __init__(self, code: int, body: str) -> None:
        super().__init__("https://gms.example", code, "err", {}, io.BytesIO(body.encode("utf-8")))


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


if __name__ == "__main__":
    unittest.main()


class _RateLimitedError(_HttpError):
    """429 응답. Retry-After 가 있으면 헤더로 싣는다."""

    def __init__(self, retry_after: str | None = None, code: int = 429) -> None:
        super().__init__(code, '{"error":{"code":%d,"status":"RESOURCE_EXHAUSTED"}}' % code)
        if retry_after is not None:
            self.headers = {"Retry-After": retry_after}


class GmsRateLimitTest(unittest.TestCase):
    """429 재시도와 동시 호출 상한. GMS 분당 한도를 넘겨 담당이 곧바로 실패하던 문제(2026-09-22)."""

    CONFIG = GmsCompleteTest.CONFIG
    SCHEMA = GmsCompleteTest.SCHEMA
    OK = {"candidates": [{"content": {"parts": [{"text": '{"answer": "x"}'}]}}]}

    def setUp(self):
        # 여기서는 재시도 규칙만 본다. 429 뒤 줄 전체를 멈추는 휴지는 GmsSchedulerTest 가 따로 본다 —
        # 켜 두면 _sleep 을 가짜로 바꿔도 줄에서 실제 시간을 기다린다.
        from ai.llm import gms
        patcher = patch.object(gms._Scheduler, "cool_down", lambda self, seconds: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _call(self, opener, side_effect, timeout_seconds: int = 45):
        opener.return_value.open.side_effect = side_effect
        return complete_structured(
            self.CONFIG, [{"role": "user", "content": "x"}],
            schema=self.SCHEMA, schema_name="x", max_tokens=100, timeout_seconds=timeout_seconds,
        )

    def test_429_is_retried_after_backoff(self):
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            result = self._call(opener, [_RateLimitedError(), _Response(self.OK)])

        self.assertEqual(result["output"], {"answer": "x"})
        self.assertEqual(opener.return_value.open.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_retry_after_header_wins_over_backoff(self):
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            self._call(opener, [_RateLimitedError(retry_after="3"), _Response(self.OK)])

        sleep.assert_called_once_with(3.0)

    def test_gives_up_after_max_retries_with_growing_waits(self):
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            with self.assertRaises(LlmHttpError) as caught:
                self._call(opener, [_RateLimitedError()] * 4)

        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(opener.return_value.open.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0, 4.0])

    def test_does_not_wait_when_retry_after_exceeds_budget(self):
        """30초를 기다리면 총괄 시간 예산을 잡아먹는다. 그럴 땐 바로 포기해 다음 담당이 간다."""
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            with self.assertRaises(LlmHttpError):
                self._call(opener, [_RateLimitedError(retry_after="30")])

        self.assertEqual(opener.return_value.open.call_count, 1)
        sleep.assert_not_called()

    def test_does_not_wait_past_call_timeout(self):
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            with self.assertRaises(LlmHttpError):
                # 타임아웃 1초짜리 호출은 1초 대기조차 못 한다.
                self._call(opener, [_RateLimitedError()], timeout_seconds=1)

        sleep.assert_not_called()

    def test_503_is_retried_too(self):
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep"):
            result = self._call(opener, [_RateLimitedError(code=503), _Response(self.OK)])

        self.assertEqual(result["output"], {"answer": "x"})

    def test_too_many_states_fallback_still_retries_429(self):
        """스키마 400 뒤의 재전송도 429 를 만나면 기다렸다 다시 보낸다."""
        with patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            result = self._call(opener, [
                _HttpError(400, '{"error":{"message":"too many states"}}'),
                _RateLimitedError(),
                _Response(self.OK),
            ])

        self.assertEqual(result["output"], {"answer": "x"})
        self.assertEqual(opener.return_value.open.call_count, 3)
        sleep.assert_called_once_with(1.0)


class GmsSchedulerTest(unittest.TestCase):
    """GMS 호출 줄. 동시 수·분당 수·선착순·우선순위·공동 휴지. 부하 시험(2026-09-22)에서 세마포어와
    독립 재시도만으로는 분당 한도를 못 지킨다는 것이 드러나 줄 하나로 합쳤다."""

    OK = {"candidates": [{"content": {"parts": [{"text": '{"answer": "x"}'}]}}]}

    def _scheduler(self, **kwargs):
        from ai.llm import gms
        return gms._Scheduler(**{"max_concurrency": 0, "rpm": 0, **kwargs})

    def _complete(self):
        return complete_structured(
            GmsCompleteTest.CONFIG, [{"role": "user", "content": "x"}],
            schema=GmsCompleteTest.SCHEMA, schema_name="x", max_tokens=100, timeout_seconds=5,
        )

    def _run_threads(self, targets):
        import threading
        threads = [threading.Thread(target=target) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        return threads

    def test_no_limits_pass_straight_through(self):
        scheduler = self._scheduler()
        with scheduler.slot(1):
            with scheduler.slot(1):
                self.assertEqual(scheduler.snapshot()["active"], 2)
        self.assertEqual(scheduler.snapshot(), {"queued": 0, "active": 0, "sent_in_window": 2})

    def test_caps_concurrent_calls(self):
        import threading
        import time as _time
        from ai.llm import gms

        lock = threading.Lock()
        state = {"active": 0, "peak": 0}

        def slow_open(*_args, **_kwargs):
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            _time.sleep(0.05)
            with lock:
                state["active"] -= 1
            return _Response(self.OK)

        with patch.object(gms, "_SCHEDULER", self._scheduler(max_concurrency=2)), \
                patch("ai.llm.gms.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = slow_open
            self._run_threads([self._complete] * 8)

        self.assertEqual(opener.return_value.open.call_count, 8)
        self.assertLessEqual(state["peak"], 2)

    def test_first_come_first_served(self):
        """자리가 하나뿐일 때 줄 선 순서대로 나간다. 늦게 온 호출이 먼저 잡아채지 않는다."""
        import threading
        import time as _time

        scheduler = self._scheduler(max_concurrency=1)
        order: list[int] = []
        gate = threading.Event()

        def holder():
            with scheduler.slot(5):
                gate.wait(timeout=5)

        def waiter(index):
            with scheduler.slot(5):
                order.append(index)

        first = threading.Thread(target=holder)
        first.start()
        _time.sleep(0.05)
        threads = []
        for index in range(5):
            thread = threading.Thread(target=waiter, args=(index,))
            thread.start()
            threads.append(thread)
            _time.sleep(0.02)  # 줄 서는 순서를 확정한다
        gate.set()
        first.join(timeout=5)
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(order, [0, 1, 2, 3, 4])

    def test_interactive_goes_before_background_even_if_queued_later(self):
        import threading
        import time as _time
        from ai.llm.priority import BACKGROUND, INTERACTIVE, priority_scope

        scheduler = self._scheduler(max_concurrency=1)
        order: list[str] = []
        gate = threading.Event()

        def holder():
            with scheduler.slot(5):
                gate.wait(timeout=5)

        def waiter(label, level):
            with priority_scope(level):
                with scheduler.slot(5):
                    order.append(label)

        first = threading.Thread(target=holder)
        first.start()
        _time.sleep(0.05)
        background = [threading.Thread(target=waiter, args=(f"bg{i}", BACKGROUND)) for i in range(3)]
        for thread in background:
            thread.start()
            _time.sleep(0.02)
        interactive = threading.Thread(target=waiter, args=("user", INTERACTIVE))
        interactive.start()
        _time.sleep(0.05)
        gate.set()
        for thread in [first, interactive, *background]:
            thread.join(timeout=5)

        self.assertEqual(order[0], "user")
        self.assertEqual(order[1:], ["bg0", "bg1", "bg2"])

    def test_rpm_spaces_calls_across_window(self):
        """창 안에 rpm 건만 보낸다. 다음 건은 가장 오래된 호출이 창을 벗어난 뒤에 나간다."""
        import time as _time

        scheduler = self._scheduler(rpm=2, window_seconds=0.3)
        started = _time.monotonic()
        stamps = []
        for _ in range(4):
            with scheduler.slot(5):
                stamps.append(_time.monotonic() - started)

        self.assertLess(stamps[1], 0.1)
        self.assertGreaterEqual(stamps[2], 0.28)
        self.assertGreaterEqual(stamps[3], 0.28)
        self.assertLess(stamps[3], 0.7)

    def test_refuses_instead_of_waiting_past_budget(self):
        """자리가 예산 안에 안 나면 보내지 않고 429 와 같은 오류를 낸다. 서버 한도를 깎지 않는다."""
        import time as _time

        scheduler = self._scheduler(rpm=1, window_seconds=60.0)
        with scheduler.slot(5):
            pass
        started = _time.monotonic()
        with self.assertRaises(LlmHttpError) as caught:
            with scheduler.slot(0.1):
                pass

        self.assertEqual(caught.exception.status, 429)
        self.assertIn("local rate limit", caught.exception.detail)
        self.assertLess(_time.monotonic() - started, 1.0)
        self.assertEqual(scheduler.snapshot()["queued"], 0)  # 포기한 호출은 줄에서 빠진다

    def test_budget_is_capped_by_max_queue_wait(self):
        scheduler = self._scheduler(rpm=1, window_seconds=60.0, max_queue_wait_seconds=0.1)
        with scheduler.slot(5):
            pass
        with self.assertRaises(LlmHttpError):
            with scheduler.slot(100):  # 호출 타임아웃이 길어도 줄 대기 상한(0.1초)이 이긴다
                pass

    def test_cool_down_pauses_everyone(self):
        import time as _time

        scheduler = self._scheduler()
        scheduler.cool_down(0.2)
        started = _time.monotonic()
        with scheduler.slot(5):
            pass
        self.assertGreaterEqual(_time.monotonic() - started, 0.18)

    def test_local_429_is_not_retried_against_server(self):
        """줄에서 낸 429 는 서버에 닿지 않았다. 재시도·휴지 없이 바로 올라간다."""
        from ai.llm import gms

        scheduler = self._scheduler(rpm=1, window_seconds=60.0)
        with scheduler.slot(5):
            pass
        with patch.object(gms, "_SCHEDULER", scheduler), \
                patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep") as sleep:
            with self.assertRaises(LlmHttpError) as caught:
                complete_structured(
                    GmsCompleteTest.CONFIG, [{"role": "user", "content": "x"}],
                    schema=GmsCompleteTest.SCHEMA, schema_name="x", max_tokens=100, timeout_seconds=0.1,
                )
        self.assertIn("local rate limit", caught.exception.detail)
        opener.return_value.open.assert_not_called()
        sleep.assert_not_called()

    def test_server_429_cools_down_the_queue(self):
        from ai.llm import gms

        import time as _time

        scheduler = self._scheduler()
        paused: list[float] = []
        original = scheduler.cool_down

        def spy(seconds):
            original(seconds)
            paused.append(scheduler._paused_until - _time.monotonic())

        scheduler.cool_down = spy
        with patch.object(gms, "_SCHEDULER", scheduler), \
                patch("ai.llm.gms.urllib.request.build_opener") as opener, \
                patch("ai.llm.gms._sleep"), \
                patch("ai.llm.gms._BACKOFF_SECONDS", (0.05, 0.05, 0.05)):
            opener.return_value.open.side_effect = [_RateLimitedError(), _Response(self.OK)]
            complete_structured(
                GmsCompleteTest.CONFIG, [{"role": "user", "content": "x"}],
                schema=GmsCompleteTest.SCHEMA, schema_name="x", max_tokens=100,
            )
        # 429 를 받자 줄 전체가 첫 대기 시간만큼 멈췄고, 재시도는 그 뒤에 나갔다.
        self.assertEqual(len(paused), 1)
        self.assertGreater(paused[0], 0.0)
        self.assertLessEqual(paused[0], 0.06)
        self.assertEqual(opener.return_value.open.call_count, 2)

    def test_slot_is_released_on_exception(self):
        scheduler = self._scheduler(max_concurrency=1)
        with self.assertRaises(RuntimeError):
            with scheduler.slot(5):
                raise RuntimeError("boom")
        self.assertEqual(scheduler.snapshot()["active"], 0)
        with scheduler.slot(0.1):  # 자리가 돌아왔으니 바로 잡힌다
            pass

    def test_env_controls_limits(self):
        from ai.llm import gms
        with patch.dict("os.environ", {"GMS_MAX_CONCURRENCY": "7", "GMS_MAX_RPM": "15"}):
            self.assertEqual(gms._max_concurrency(), 7)
            self.assertEqual(gms._max_rpm(), 15)
        with patch.dict("os.environ", {"GMS_MAX_CONCURRENCY": "abc", "GMS_MAX_RPM": ""}):
            self.assertEqual(gms._max_concurrency(), 4)
            self.assertEqual(gms._max_rpm(), 0)


class PriorityPropagationTest(unittest.TestCase):
    """우선순위가 총괄 API 에서 담당의 스레드 풀까지 전달되는지."""

    def test_scope_sets_and_restores(self):
        from ai.llm.priority import BACKGROUND, INTERACTIVE, current_priority, priority_scope
        self.assertEqual(current_priority(), INTERACTIVE)
        with priority_scope(BACKGROUND):
            self.assertEqual(current_priority(), BACKGROUND)
        self.assertEqual(current_priority(), INTERACTIVE)

    def test_jd_thread_pool_keeps_priority(self):
        from concurrent.futures import ThreadPoolExecutor
        from ai.jd_coaching.service import _submit_with_context
        from ai.llm.priority import BACKGROUND, current_priority, priority_scope

        with priority_scope(BACKGROUND), ThreadPoolExecutor(max_workers=1) as executor:
            plain = executor.submit(current_priority).result()
            carried = _submit_with_context(executor, current_priority).result()
        self.assertNotEqual(plain, BACKGROUND)  # 그냥 submit 하면 잃는다 — 그래서 감싼다
        self.assertEqual(carried, BACKGROUND)
