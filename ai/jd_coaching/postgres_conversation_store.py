from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ai.jd_coaching.conversation_store import (
    ChatMessage,
    Conversation,
    ConversationStore,
)


class PostgresConversationStore(ConversationStore):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _connect(self):
        return psycopg.connect(
            self._database_url,
            connect_timeout=5,
            row_factory=dict_row,
        )

    def create_conversation(self, conversation: Conversation) -> Conversation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_conversations (
                    conversation_id, context_id, analysis_id,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    conversation.conversation_id,
                    conversation.context_id,
                    conversation.analysis_id,
                    conversation.created_at,
                    conversation.updated_at,
                ),
            )
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_conversations WHERE conversation_id = %s",
                (conversation_id,),
            ).fetchone()
        return _conversation_from_row(row)

    def delete_conversation(self, conversation_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_conversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            if cursor.rowcount != 1:
                raise KeyError(conversation_id)

    def append_message(self, message: ChatMessage) -> ChatMessage:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    INSERT INTO ai_conversation_messages (
                        message_id, conversation_id, role, content,
                        client_message_id, reply_to_message_id, metadata,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING sequence_no
                    """,
                    (
                        message.message_id,
                        message.conversation_id,
                        message.role,
                        message.content,
                        message.client_message_id,
                        message.reply_to_message_id,
                        Jsonb(message.metadata),
                        message.created_at,
                    ),
                ).fetchone()
                connection.execute(
                    """
                    UPDATE ai_conversations
                    SET updated_at = %s
                    WHERE conversation_id = %s
                    """,
                    (message.created_at, message.conversation_id),
                )
        except UniqueViolation as error:
            raise ValueError("duplicate message or client_message_id") from error
        return replace(message, sequence_no=int(row["sequence_no"]))

    def list_messages(
        self, conversation_id: str, *, limit: int = 100
    ) -> list[ChatMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT *
                    FROM ai_conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY sequence_no DESC
                    LIMIT %s
                ) recent
                ORDER BY sequence_no ASC
                """,
                (conversation_id, limit),
            ).fetchall()
        return [_message_from_row(row) for row in rows]

    def find_user_message(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM ai_conversation_messages
                WHERE conversation_id = %s
                  AND role = 'USER'
                  AND client_message_id = %s
                """,
                (conversation_id, client_message_id),
            ).fetchone()
        return _message_from_row(row)

    def find_assistant_reply(self, user_message_id: str) -> ChatMessage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM ai_conversation_messages
                WHERE role = 'ASSISTANT' AND reply_to_message_id = %s
                """,
                (user_message_id,),
            ).fetchone()
        return _message_from_row(row)


def _conversation_from_row(
    row: dict[str, Any] | None,
) -> Conversation | None:
    if row is None:
        return None
    return Conversation(
        conversation_id=row["conversation_id"],
        context_id=row["context_id"],
        analysis_id=row["analysis_id"],
        created_at=_isoformat(row["created_at"]),
        updated_at=_isoformat(row["updated_at"]),
    )


def _message_from_row(row: dict[str, Any] | None) -> ChatMessage | None:
    if row is None:
        return None
    return ChatMessage(
        message_id=row["message_id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        client_message_id=row["client_message_id"],
        reply_to_message_id=row["reply_to_message_id"],
        metadata=row["metadata"],
        created_at=_isoformat(row["created_at"]),
        sequence_no=row["sequence_no"],
    )


def _isoformat(value: str | datetime) -> str:
    return value if isinstance(value, str) else value.isoformat()
