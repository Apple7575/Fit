"""SSAFY GMS 경유 Gemini(`:generateContent`) 어댑터.

vLLM 과 주고받는 모양이 전부 다르다. 그 차이를 여기서 흡수해 바깥에는 같은 dict 를 돌려준다.

| | vLLM | GMS |
| --- | --- | --- |
| 인증 | `Authorization: Bearer` | `x-goog-api-key` |
| 대화 | `messages[{role, content}]` | `systemInstruction` + `contents[{role, parts}]` |
| 구조화 출력 | `response_format.json_schema` | `generationConfig.responseSchema` |
| 답 꺼내기 | `choices[0].message.content` | `candidates[0].content.parts[0].text` |

스키마도 그대로 넘기지 못한다. Gemini 는 타입을 대문자로 쓰고 `additionalProperties` 같은
JSON Schema 키워드를 모른다 — 그대로 보내면 400 이 온다. `to_gemini_schema` 가 옮긴다.

할당량도 다르다. GMS 는 분당 요청 수를 넘기면 429(RESOURCE_EXHAUSTED)를 준다. 검토 방 턴 하나가
담당 여럿을 병렬로 돌려 첫 몇 초에 6~8건이 한꺼번에 나가므로 순간 한도를 넘기기 쉽다(2026-09-22
QA 실측). 그래서 이 어댑터는 모든 호출을 프로세스 안의 줄(`_Scheduler`) 하나에 세운다. 줄은
동시 호출 수와 분당 호출 수를 지키고, 사용자 질문을 자동 검토보다 먼저 보내며, 429·503 을 받으면
줄 전체를 잠시 멈춘 뒤 다시 보낸다. 외부 큐를 두지 않는 이유: 한도는 분당 건수라 큐가 있어도
내보내는 양은 같고, Spring 이 120초 안에 답을 기다리는 동기 경로를 바꿀 일이 아니기 때문이다.
"""
from __future__ import annotations

import bisect
import contextlib
import json
import logging
import os
import threading
import time
from collections.abc import Iterator
from typing import Any, Callable
import urllib.error
import urllib.request

from ai.llm.priority import current_priority
from ai.llm.contracts import (
    LlmConnectionError,
    LlmHttpError,
    LlmResponseError,
    StructuredCompletion,
)

NAME = "gms"
_LABEL = "GMS"
LOGGER = logging.getLogger("ai.llm.gms")

# --- 할당량 방어 -----------------------------------------------------------------
# 검토 방 턴 하나가 JD(항목별 병렬)·포지션·뉴스를 함께 띄워 첫 몇 초에 6~8건이 몰리고, 자동 검토는
# 방 여섯 개를 연달아 돌린다. GMS 한도는 분당 건수라 이 폭주가 곧 429 다. 아래 `_Scheduler` 하나가
# (1) 동시 호출 수, (2) 분당 호출 수, (3) 429 를 받은 뒤의 공동 휴지, (4) 선착순·우선순위를 함께 맡는다.
_DEFAULT_MAX_CONCURRENCY = 4
# 429·503 은 잠깐 뒤 다시 보내면 대개 통한다. 1초·2초·4초로 늘리며 최대 3번 더 시도한다.
_RETRY_STATUSES = frozenset({429, 503})
_MAX_RETRIES = 3
_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
# 한 호출이 재시도로 기다리는 시간의 총합 상한. Spring 총괄 타임아웃(120초)·위임 상한(60초) 안에서
# 담당 여럿이 순서대로 도는 것을 감안해 짧게 둔다. Retry-After 가 이보다 길면 기다리지 않고 포기한다.
_MAX_TOTAL_WAIT_SECONDS = 10.0
# 줄에서 기다리는 시간 상한. 호출 자체의 타임아웃과 둘 중 짧은 쪽을 쓴다. 이보다 오래 기다려야 하면
# 보내지 않고 429 와 같은 오류를 낸다 — GMS 한도를 한 번 더 깎아 먹는 것보다 낫다.
# 30초인 이유: 총괄 한 요청은 계획→분석→글쓰기→종합이 차례로 도는데 Spring 은 전체를 120초만 기다린다.
# 단계마다 60초씩 줄에 서면 Spring 이 먼저 포기해 담당 전원이 실패로 찍히고 그 뒤 GMS 호출은 버려진다.
# 담당 하나가 줄에서 포기하는 편(PARTIAL)이 전원 실패보다 낫다.
_MAX_QUEUE_WAIT_SECONDS = 30.0
_RATE_WINDOW_SECONDS = 60.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _max_concurrency() -> int:
    """동시에 GMS 로 나갈 수 있는 호출 수. 0 이하면 제한 없음."""
    return _env_int("GMS_MAX_CONCURRENCY", _DEFAULT_MAX_CONCURRENCY)


def _max_rpm() -> int:
    """분당 호출 상한. 0 이면 끈다. GMS 사용 조회 화면의 한도에 맞춰 넣는다."""
    return _env_int("GMS_MAX_RPM", 0)


# 테스트에서 바꿔 끼울 수 있게 모듈 변수로 둔다.
_sleep: Callable[[float], None] = time.sleep
_monotonic: Callable[[], float] = time.monotonic


class _Scheduler:
    """GMS 호출 줄 세우기.

    호출은 번호표를 받아 줄에 선다. 줄의 맨 앞만 나갈 수 있고, 나가려면 세 조건이 맞아야 한다:
    동시 호출 수가 상한 아래, 최근 1분 호출 수가 분당 상한 아래, 429 를 받은 뒤의 휴지가 끝남.
    줄은 (우선순위, 번호표) 순이다. 사용자가 직접 보낸 질문(INTERACTIVE)이 자동 검토(BACKGROUND)보다
    먼저 서고, 같은 우선순위 안에서는 먼저 온 것이 먼저 나간다. 조건 변수 하나로 깨우므로 늦게 온
    호출이 먼저 잡아채는 일이 없다.

    상한이 0 이면 그 조건은 검사하지 않는다. 셋 다 0 이어도 줄은 서지만 곧바로 통과한다.
    """

    def __init__(
        self,
        max_concurrency: int,
        rpm: int,
        window_seconds: float = _RATE_WINDOW_SECONDS,
        max_queue_wait_seconds: float = _MAX_QUEUE_WAIT_SECONDS,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.rpm = rpm
        self.window = window_seconds
        self.max_queue_wait = max_queue_wait_seconds
        self._cond = threading.Condition()
        self._queue: list[tuple[int, int]] = []  # (priority, ticket) 오름차순
        self._ticket = 0
        self._active = 0
        self._sent: list[float] = []
        self._paused_until = 0.0

    # --- 바깥에 보이는 것 ---------------------------------------------------------

    @contextlib.contextmanager
    def slot(self, timeout_seconds: float) -> Iterator[None]:
        """자리를 잡고 블록을 돈다. 블록 안에서는 HTTP 왕복만 해야 한다."""
        self._acquire(timeout_seconds)
        try:
            yield
        finally:
            self._release()

    def cool_down(self, seconds: float) -> None:
        """서버가 429 를 줬다. 이 스레드만 기다리는 게 아니라 줄 전체를 그 시간만큼 멈춘다.

        각자 따로 재시도하면 기다리던 다른 호출이 그 사이 나가서 같은 429 를 또 받는다.
        """
        with self._cond:
            self._paused_until = max(self._paused_until, _monotonic() + seconds)
            self._cond.notify_all()

    def snapshot(self) -> dict[str, int]:
        """로그·시험용. 줄 길이와 진행 중 호출 수."""
        with self._cond:
            return {"queued": len(self._queue), "active": self._active, "sent_in_window": len(self._sent)}

    # --- 안쪽 ---------------------------------------------------------------------

    def _acquire(self, timeout_seconds: float) -> None:
        budget = min(timeout_seconds, self.max_queue_wait)
        with self._cond:
            self._ticket += 1
            me = (current_priority(), self._ticket)
            bisect.insort(self._queue, me)
            deadline = _monotonic() + budget
            while True:
                now = _monotonic()
                self._sent = [stamp for stamp in self._sent if now - stamp < self.window]
                is_head = self._queue[0] == me
                has_capacity = self.max_concurrency <= 0 or self._active < self.max_concurrency
                under_rate = self.rpm <= 0 or len(self._sent) < self.rpm
                not_paused = now >= self._paused_until
                if is_head and has_capacity and under_rate and not_paused:
                    self._queue.pop(0)
                    self._active += 1
                    self._sent.append(now)
                    self._cond.notify_all()  # 다음 사람이 조건을 다시 보게 한다
                    return
                if now >= deadline:
                    self._queue.remove(me)
                    self._cond.notify_all()
                    raise LlmHttpError(
                        _LABEL, 429,
                        f"local rate limit: {budget:.0f}초 안에 보낼 자리가 나지 않음 "
                        f"(대기 {len(self._queue)}건, 진행 {self._active}건, 분당 한도 {self.rpm})",
                    )
                # 앞사람이 나가거나 누가 끝나면 notify 로 깨운다. 시간이 풀어 주는 조건(분당 창·휴지)은
                # 그 시각에 맞춰 스스로 깬다. 그 밖에는 마감까지 기다린다.
                wake_at = deadline
                if not under_rate:
                    wake_at = min(wake_at, self._sent[0] + self.window)
                if not not_paused:
                    wake_at = min(wake_at, self._paused_until)
                self._cond.wait(timeout=max(wake_at - now, 0.01))

    def _release(self) -> None:
        with self._cond:
            self._active -= 1
            self._cond.notify_all()


_SCHEDULER = _Scheduler(_max_concurrency(), _max_rpm())


def _retry_after_seconds(error: LlmHttpError) -> float | None:
    """서버가 기다릴 시간을 알려 줬으면 그 값을 쓴다(초 단위 숫자만 해석한다)."""
    headers = getattr(error, "headers", None)
    if not headers:
        return None
    raw = headers.get("Retry-After") if hasattr(headers, "get") else None
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    return value if value >= 0 else None

# Gemini responseSchema 가 아는 키만 남긴다. 나머지는 보내면 400 이다.
_KEPT_KEYS = frozenset({
    "type", "format", "description", "nullable", "enum", "items", "properties", "required",
    # 배열 길이는 Gemini 도 지킨다. 떨구면 담당들의 "1~3개" 같은 제약이 사라져 모델이 넘게 낸다.
    "minItems", "maxItems",
})
# 길이 제약. 중첩된 배열에 붙으면 Gemini 가 감당하지 못해 400 을 준다.
_BOUND_KEYS = frozenset({"minItems", "maxItems"})
# 그 400 의 본문에 이 말이 들어 있다. 제약을 빼고 한 번 더 보내는 신호로 쓴다.
_TOO_MANY_STATES = "too many states"
_TYPES = {
    "object": "OBJECT",
    "array": "ARRAY",
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
}


class _NoRedirectOpener(urllib.request.HTTPRedirectHandler):
    """인증 헤더(x-goog-api-key)가 다른 호스트로 새지 않도록 리다이렉트를 막는다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def to_gemini_schema(schema: Any, *, with_bounds: bool = True) -> Any:
    """JSON Schema → Gemini responseSchema.

    타입을 대문자로 올리고, Gemini 가 모르는 키워드를 떨군다. `["string", "null"]` 처럼 타입을
    배열로 쓴 곳은 첫 타입 + `nullable` 로 옮긴다 — 담당들의 스키마가 선택 필드를 이렇게 쓴다.

    `with_bounds=False` 면 배열 길이 제약을 뺀다. 중첩된 배열에 길이가 붙으면 Gemini 가
    "too many states" 로 거절하는데, 그때 이 형태로 한 번 더 보낸다.
    """
    if isinstance(schema, list):
        return [to_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        concrete = [item for item in raw_type if item != "null"]
        if concrete:
            out["type"] = _TYPES.get(concrete[0], str(concrete[0]).upper())
        if "null" in raw_type:
            out["nullable"] = True
    elif isinstance(raw_type, str):
        out["type"] = _TYPES.get(raw_type, raw_type.upper())

    for key, value in schema.items():
        if key == "type" or key not in _KEPT_KEYS:
            continue
        if not with_bounds and key in _BOUND_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            out["properties"] = {
                name: to_gemini_schema(item, with_bounds=with_bounds)
                for name, item in value.items()
            }
        elif key == "items":
            out["items"] = to_gemini_schema(value, with_bounds=with_bounds)
        else:
            out[key] = value

    # anyOf/oneOf 로 null 을 표현한 스키마도 있다. Gemini 는 모르므로 첫 갈래만 쓰고 nullable 로 둔다.
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and branches:
            concrete = [b for b in branches if not (isinstance(b, dict) and b.get("type") == "null")]
            chosen = to_gemini_schema(
                concrete[0] if concrete else branches[0], with_bounds=with_bounds
            )
            if isinstance(chosen, dict):
                merged = {**chosen, **out}
                if len(concrete) != len(branches):
                    merged["nullable"] = True
                return merged
    return out


def to_gemini_contents(messages: list[dict[str, str]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """OpenAI messages → (systemInstruction, contents).

    system 은 여러 개가 와도 하나로 합친다. Gemini 는 systemInstruction 을 하나만 받는다.
    assistant 는 Gemini 에서 `model` 이다.
    """
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user")).lower()
        content = str(message.get("content", ""))
        if not content.strip():
            continue
        if role == "system":
            system_parts.append(content)
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}],
        })
    system = {"parts": [{"text": "\n\n".join(system_parts)}]} if system_parts else None
    return system, contents


def complete(
    config: dict[str, str],
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    timeout_seconds: int,
) -> StructuredCompletion:
    system, contents = to_gemini_contents(messages)
    if not contents:
        raise LlmResponseError(_LABEL, "보낼 메시지가 없습니다")

    url = (
        f"{config['base_url']}/generativelanguage.googleapis.com/v1beta/models/"
        f"{config['model']}:generateContent"
    )

    def send(with_bounds: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": to_gemini_schema(schema, with_bounds=with_bounds),
                "temperature": 0,
                "maxOutputTokens": max_tokens,
            },
        }
        if system is not None:
            body["systemInstruction"] = system
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": config["api_key"]},
            method="POST",
        )
        opener = urllib.request.build_opener(_NoRedirectOpener())
        try:
            # 줄에 서서 자리를 잡은 뒤 HTTP 왕복만 한다. 재시도 대기는 자리를 놓은 뒤에 한다.
            with _SCHEDULER.slot(timeout_seconds):
                with opener.open(request, timeout=timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            http_error = LlmHttpError(_LABEL, error.code, detail)
            http_error.headers = error.headers  # Retry-After 를 읽기 위해 남긴다
            raise http_error from error
        except urllib.error.URLError as error:
            raise LlmConnectionError(_LABEL, error.reason) from error

    def send_with_retry(with_bounds: bool) -> dict[str, Any]:
        """429·503 이면 잠시 기다렸다 다시 보낸다. 총 대기와 호출 타임아웃을 넘기지 않는다."""
        started = _monotonic()
        waited = 0.0
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return send(with_bounds)
            except LlmHttpError as error:
                if (
                    error.status not in _RETRY_STATUSES
                    or attempt == _MAX_RETRIES
                    # 우리 줄에서 낸 429 는 서버에 닿지도 않았다. 기다려 봐야 같은 답이다.
                    or error.detail.startswith("local rate limit")
                ):
                    raise
                wait = _retry_after_seconds(error)
                if wait is None:
                    wait = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                elapsed = _monotonic() - started
                if (
                    waited + wait > _MAX_TOTAL_WAIT_SECONDS
                    or elapsed + wait >= timeout_seconds
                ):
                    LOGGER.warning(
                        "GMS %s: 재시도 대기 %.1fs 가 상한을 넘어 포기 (누적 대기 %.1fs, 경과 %.1fs)",
                        error.status, wait, waited, elapsed,
                    )
                    raise
                LOGGER.warning(
                    "GMS %s: %.1fs 뒤 재시도 (%d/%d)", error.status, wait, attempt + 1, _MAX_RETRIES,
                )
                # 나만 기다리면 줄 뒤의 호출이 그 사이 나가 같은 429 를 또 받는다. 줄 전체를 멈춘다.
                _SCHEDULER.cool_down(wait)
                _sleep(wait)
                waited += wait
        raise RuntimeError("unreachable")  # pragma: no cover

    try:
        raw = send_with_retry(with_bounds=True)
    except LlmHttpError as error:
        # 중첩된 배열에 길이 제약이 붙으면 Gemini 가 감당하지 못한다. 제약을 빼고 한 번 더 보낸다 —
        # 길이는 파서가 어차피 검사하므로, 아예 못 부르는 것보다 낫다.
        if error.status != 400 or _TOO_MANY_STATES not in error.detail.lower():
            raise
        raw = send_with_retry(with_bounds=False)

    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        output = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        # 안전 필터에 걸리면 candidates 가 비고 finishReason 만 온다. 원인을 남겨야 추적된다.
        reason = ""
        candidates = raw.get("candidates") or []
        if candidates and isinstance(candidates[0], dict):
            reason = str(candidates[0].get("finishReason", ""))
        elif raw.get("promptFeedback"):
            reason = str(raw["promptFeedback"])
        raise LlmResponseError(_LABEL, reason) from error
    if not isinstance(output, dict):
        raise LlmResponseError(_LABEL, "최상위가 객체가 아닙니다")

    usage = raw.get("usageMetadata") or {}
    return {
        "model": raw.get("modelVersion", config["model"]),
        # 토큰 이름을 vLLM 쪽에 맞춘다. 사용량을 기록하는 곳이 한 가지만 알면 되게 한다.
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
        "output": output,
    }
