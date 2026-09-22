"""담당이 자료를 읽는 유일한 통로: 허용된 조회 도구.

담당 서비스는 저장소 객체(JobContextStore, NewsRepository 등)를 그대로 쓴다.
총괄 아래에서 실행할 때는 그 저장소 자리에 여기의 프록시를 끼워 넣어,
모든 조회가 (1) 담당별 허용 목록을 통과하고 (2) 호출 기록으로 남게 한다.
담당 서비스 코드는 바꾸지 않는다.

사용 방법:
    toolbox = ToolBox(job_context_store=..., news_repository=..., ...)
    jd_service = JdAnalysisService(context_store=toolbox.job_context_store("jd"), ...)
    with tool_scope("jd") as calls:
        jd_service.analyze_documents(...)
    # calls -> 이 담당이 실행 중 호출한 ToolCall 목록
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

from ai.supervisor.contracts import AgentName, ToolCall, ToolName


class ToolPolicyError(PermissionError):
    """허용 목록에 없는 도구를 호출했다."""

    def __init__(self, agent: str, tool: str) -> None:
        super().__init__(f"agent '{agent}' is not allowed to call tool '{tool}'")
        self.agent = agent
        self.tool = tool


# 담당별 허용 도구. 코드에 선언하며 모델이 바꿀 수 없다.
DEFAULT_TOOL_POLICY: dict[str, frozenset[str]] = {
    "jd": frozenset({"get_job_context"}),
    "news": frozenset({"get_job_context", "list_news", "search_news_external"}),
    "position": frozenset(),  # 제출 문서만 사용
    "writing": frozenset(),  # 다른 담당의 피드백만 사용
    "company": frozenset(),  # 자기 리포트 저장소와 공시 청크만 사용(총괄 도구 없음)
    "supervisor": frozenset({"get_conversation"}),
}

_current_agent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "supervisor_tool_agent", default=None
)
_current_calls: contextvars.ContextVar[list[ToolCall] | None] = contextvars.ContextVar(
    "supervisor_tool_calls", default=None
)


@contextlib.contextmanager
def tool_scope(agent: AgentName | str) -> Iterator[list[ToolCall]]:
    """이 블록 안에서 일어나는 도구 호출을 `agent` 이름으로 기록한다."""
    calls: list[ToolCall] = []
    agent_token = _current_agent.set(agent)
    calls_token = _current_calls.set(calls)
    try:
        yield calls
    finally:
        _current_calls.reset(calls_token)
        _current_agent.reset(agent_token)


def current_tool_calls() -> list[ToolCall]:
    calls = _current_calls.get()
    return list(calls) if calls is not None else []


class ToolBox:
    def __init__(
        self,
        *,
        job_context_store: Any | None = None,
        news_repository: Any | None = None,
        news_search_provider: Any | None = None,
        conversation_store: Any | None = None,
        policy: Mapping[str, frozenset[str] | set[str]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._job_context_store = job_context_store
        self._news_repository = news_repository
        self._news_search_provider = news_search_provider
        self._conversation_store = conversation_store
        self._policy = {
            key: frozenset(value) for key, value in (policy or DEFAULT_TOOL_POLICY).items()
        }
        self._clock = clock

    # --- 정책 ---------------------------------------------------------------

    def allowed_tools(self, agent: str) -> frozenset[str]:
        return self._policy.get(agent, frozenset())

    def is_allowed(self, agent: str, tool: str) -> bool:
        return tool in self.allowed_tools(agent)

    # --- 저장소 모양의 프록시 ------------------------------------------------

    def job_context_store(self, agent: AgentName) -> JobContextStoreProxy:
        if self._job_context_store is None:
            raise RuntimeError("job_context_store is not configured")
        return JobContextStoreProxy(self, agent, self._job_context_store)

    def news_repository(self, agent: AgentName) -> NewsRepositoryProxy:
        if self._news_repository is None:
            raise RuntimeError("news_repository is not configured")
        return NewsRepositoryProxy(self, agent, self._news_repository)

    def news_search_provider(self, agent: AgentName) -> NewsSearchProviderProxy:
        if self._news_search_provider is None:
            raise RuntimeError("news_search_provider is not configured")
        return NewsSearchProviderProxy(self, agent, self._news_search_provider)

    def conversation_store(self, agent: AgentName | str) -> ConversationStoreProxy:
        if self._conversation_store is None:
            raise RuntimeError("conversation_store is not configured")
        return ConversationStoreProxy(self, agent, self._conversation_store)

    # --- 실행과 기록 ---------------------------------------------------------

    def call(
        self,
        agent: AgentName | str,
        tool: ToolName,
        arguments: Mapping[str, Any],
        operation: Callable[[], Any],
        *,
        count: Callable[[Any], int | None] = lambda value: None,
    ) -> Any:
        """허용 확인 → 실행 → 기록. 거부되면 ToolPolicyError, 실패하면 원래 예외를 다시 던진다."""
        started = self._clock()
        if not self.is_allowed(agent, tool):
            self._record(tool, agent, arguments, "DENIED", started, error="not allowed")
            raise ToolPolicyError(agent, tool)
        try:
            value = operation()
        except Exception as error:
            self._record(
                tool, agent, arguments, "FAILED", started,
                error=f"{type(error).__name__}: {error}"[:500],
            )
            raise
        self._record(tool, agent, arguments, "SUCCESS", started, result_count=count(value))
        return value

    def _record(
        self,
        tool: str,
        agent: str,
        arguments: Mapping[str, Any],
        status: str,
        started: float,
        *,
        result_count: int | None = None,
        error: str | None = None,
    ) -> None:
        calls = _current_calls.get()
        if calls is None:
            return  # 총괄 밖(직접 호출)에서는 기록 대상이 없다.
        calls.append(
            ToolCall(
                tool=tool,
                agent=agent,
                arguments=_safe_arguments(arguments),
                status=status,
                duration_ms=max(0, int((self._clock() - started) * 1000)),
                result_count=result_count,
                error=error,
            )
        )


def _safe_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """기록에는 식별자와 숫자만 남긴다. 본문·목록은 길이만 남긴다."""
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value if not isinstance(value, str) else value[:200]
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)
            if len(items) <= 10 and all(
                isinstance(item, (str, int, float, bool)) or item is None for item in items
            ):
                safe[key] = [item[:200] if isinstance(item, str) else item for item in items]
            else:
                safe[key] = f"<{len(items)} items>"
        else:
            safe[key] = str(value)[:200]
    return safe


def _len_or_none(value: Any) -> int | None:
    if value is None:
        return 0
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return len(value)
    return 1


class _Proxy:
    def __init__(self, toolbox: ToolBox, agent: AgentName | str, target: Any) -> None:
        self._toolbox = toolbox
        self._agent = agent
        self._target = target

    def __getattr__(self, name: str) -> Any:
        # 도구로 선언하지 않은 메서드는 그대로 통과시킨다(쓰기 등은 총괄 경로에서 쓰지 않는다).
        return getattr(self._target, name)


class JobContextStoreProxy(_Proxy):
    def get(self, context_id: str):
        return self._toolbox.call(
            self._agent,
            "get_job_context",
            {"context_id": context_id},
            lambda: self._target.get(context_id),
            count=_len_or_none,
        )


class NewsRepositoryProxy(_Proxy):
    def load_context(self, job_context_id: str, corp_code: str):
        return self._toolbox.call(
            self._agent,
            "get_job_context",
            {"context_id": job_context_id, "corp_code": corp_code},
            lambda: self._target.load_context(job_context_id, corp_code),
            count=_len_or_none,
        )

    def list_recent(self, corp_code: str, since, limit: int):
        return self._toolbox.call(
            self._agent,
            "list_news",
            {"corp_code": corp_code, "since": since.isoformat(), "limit": limit},
            lambda: self._target.list_recent(corp_code, since, limit),
            count=_len_or_none,
        )


class NewsSearchProviderProxy(_Proxy):
    # 검색기 시그니처와 같아야 한다. 검색기에 industry_name 을 더했을 때 여기를 빼먹어
    # 총괄이 한 번 돌고 나면(이 프록시가 공용 뉴스 서비스에 끼워진 뒤) 뉴스 담당 호출이
    # 전부 500 으로 죽었다 — 뉴스 전담 방까지 함께. 앞으로 인자가 늘어도 그대로 넘긴다.
    def search(
        self, corp_name, position_name, missing_scopes, from_date, to_date, limit,
        *, industry_name=None, **kwargs,
    ):
        return self._toolbox.call(
            self._agent,
            "search_news_external",
            {
                "corp_name": corp_name,
                "position_name": position_name,
                "industry_name": industry_name,
                "missing_scopes": [str(scope) for scope in missing_scopes],
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "limit": limit,
                **{key: value for key, value in kwargs.items() if isinstance(value, (str, int, type(None)))},
            },
            lambda: self._target.search(
                corp_name, position_name, missing_scopes, from_date, to_date, limit,
                industry_name=industry_name, **kwargs,
            ),
            count=_len_or_none,
        )


class ConversationStoreProxy(_Proxy):
    def list_messages(self, conversation_id: str, *, limit: int = 100):
        return self._toolbox.call(
            self._agent,
            "get_conversation",
            {"conversation_id": conversation_id, "limit": limit},
            lambda: self._target.list_messages(conversation_id, limit=limit),
            count=_len_or_none,
        )


# --- 기존 서비스에 프록시 끼워 넣기 ------------------------------------------
# 담당 서비스는 생성 시 저장소를 받아 private 속성에 보관한다. 총괄 경로에서만
# 그 속성을 프록시로 바꿔 끼운다. 직접 호출 API(/jd, /news)는 영향받지 않는다.


def instrument_jd_service(service: Any) -> Any:
    store = getattr(service, "_context_store", None)
    if store is None or isinstance(store, _Proxy):
        return service
    toolbox = ToolBox(job_context_store=store)
    service._context_store = toolbox.job_context_store("jd")
    return service


def instrument_news_service(service: Any) -> Any:
    repository = getattr(service, "_repository", None)
    search_provider = getattr(service, "_search_provider", None)
    if repository is None and search_provider is None:
        return service
    if isinstance(repository, _Proxy) or isinstance(search_provider, _Proxy):
        return service
    toolbox = ToolBox(news_repository=repository, news_search_provider=search_provider)
    if repository is not None:
        service._repository = toolbox.news_repository("news")
    if search_provider is not None:
        service._search_provider = toolbox.news_search_provider("news")
    return service
