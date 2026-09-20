"""기업 분석 대화 저장소 (company_analysis_conversation / company_analysis_message, V30)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    corp_code: str
    job_context_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredMessage:
    message_id: str
    conversation_id: str
    role: str  # USER | ASSISTANT
    content: str
    created_at: datetime
    citations: list[dict[str, Any]] = field(default_factory=list)
    needs: list[dict[str, Any]] = field(default_factory=list)
    sequence_no: int | None = None


class ConversationStore(Protocol):
    def create(self, conversation: Conversation) -> Conversation: ...

    def get(self, conversation_id: str) -> Conversation | None: ...

    def append(self, message: StoredMessage) -> StoredMessage: ...

    def history(self, conversation_id: str, *, limit: int = 20) -> list[StoredMessage]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[StoredMessage]] = {}
        self._sequence = 0
        self._lock = threading.Lock()

    def create(self, conversation: Conversation) -> Conversation:
        with self._lock:
            if conversation.conversation_id in self._conversations:
                raise ValueError(f"duplicate conversation_id: {conversation.conversation_id}")
            self._conversations[conversation.conversation_id] = conversation
            self._messages[conversation.conversation_id] = []
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def append(self, message: StoredMessage) -> StoredMessage:
        with self._lock:
            if message.conversation_id not in self._conversations:
                raise KeyError(message.conversation_id)
            self._sequence += 1
            stored = StoredMessage(**{**message.__dict__, "sequence_no": self._sequence})
            self._messages[message.conversation_id].append(stored)
            current = self._conversations[message.conversation_id]
            self._conversations[message.conversation_id] = Conversation(
                **{**current.__dict__, "updated_at": message.created_at}
            )
        return stored

    def history(self, conversation_id: str, *, limit: int = 20) -> list[StoredMessage]:
        messages = self._messages.get(conversation_id, [])
        return messages[-limit:]


CREATE_SQL = """
INSERT INTO company_analysis_conversation (conversation_id, corp_code, job_context_id, created_at, updated_at)
VALUES (%(conversation_id)s, %(corp_code)s, %(job_context_id)s, %(created_at)s, %(updated_at)s)
"""
GET_SQL = """
SELECT conversation_id, corp_code, job_context_id, created_at, updated_at
  FROM company_analysis_conversation WHERE conversation_id = %s
"""
APPEND_SQL = """
INSERT INTO company_analysis_message (message_id, conversation_id, role, content, citations, needs, created_at)
VALUES (%(message_id)s, %(conversation_id)s, %(role)s, %(content)s, %(citations)s::jsonb, %(needs)s::jsonb, %(created_at)s)
RETURNING sequence_no
"""
TOUCH_SQL = "UPDATE company_analysis_conversation SET updated_at = %s WHERE conversation_id = %s"
HISTORY_SQL = """
SELECT message_id, conversation_id, role, content, citations, needs, created_at, sequence_no
  FROM (SELECT * FROM company_analysis_message WHERE conversation_id = %s ORDER BY sequence_no DESC LIMIT %s) recent
 ORDER BY sequence_no
"""


class PostgresConversationStore:
    def __init__(self, connect: Callable[[], Any]) -> None:
        self._connect = connect

    def create(self, conversation: Conversation) -> Conversation:
        with self._connect() as connection:
            connection.execute(CREATE_SQL, conversation.__dict__)
            connection.commit()
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        with self._connect() as connection:
            row = connection.execute(GET_SQL, (conversation_id,)).fetchone()
        return Conversation(*row) if row else None

    def append(self, message: StoredMessage) -> StoredMessage:
        params = {
            **{k: v for k, v in message.__dict__.items() if k not in ("sequence_no", "citations", "needs")},
            "citations": json.dumps(message.citations, ensure_ascii=False),
            "needs": json.dumps(message.needs, ensure_ascii=False),
        }
        with self._connect() as connection:
            sequence_no = connection.execute(APPEND_SQL, params).fetchone()[0]
            connection.execute(TOUCH_SQL, (message.created_at, message.conversation_id))
            connection.commit()
        return StoredMessage(**{**message.__dict__, "sequence_no": sequence_no})

    def history(self, conversation_id: str, *, limit: int = 20) -> list[StoredMessage]:
        with self._connect() as connection:
            rows = connection.execute(HISTORY_SQL, (conversation_id, limit)).fetchall()
        return [
            StoredMessage(
                message_id=r[0], conversation_id=r[1], role=r[2], content=r[3],
                citations=list(r[4] or []), needs=list(r[5] or []), created_at=r[6], sequence_no=r[7],
            )
            for r in rows
        ]
