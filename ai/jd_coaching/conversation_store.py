from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
from typing import Any, Protocol


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    context_id: str
    analysis_id: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ChatMessage:
    message_id: str
    conversation_id: str
    role: str
    content: str
    client_message_id: str | None
    reply_to_message_id: str | None
    metadata: dict[str, Any]
    created_at: str
    sequence_no: int | None = None


class ConversationStore(Protocol):
    def create_conversation(self, conversation: Conversation) -> Conversation: ...

    def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    def delete_conversation(self, conversation_id: str) -> None: ...

    def append_message(self, message: ChatMessage) -> ChatMessage: ...

    def list_messages(
        self, conversation_id: str, *, limit: int = 100
    ) -> list[ChatMessage]: ...

    def find_user_message(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None: ...

    def find_assistant_reply(self, user_message_id: str) -> ChatMessage | None: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, ChatMessage] = {}
        self._next_sequence = 1
        self._lock = Lock()

    def create_conversation(self, conversation: Conversation) -> Conversation:
        with self._lock:
            if conversation.conversation_id in self._conversations:
                raise ValueError(
                    f"duplicate conversation_id: {conversation.conversation_id}"
                )
            self._conversations[conversation.conversation_id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            return self._conversations.get(conversation_id)

    def delete_conversation(self, conversation_id: str) -> None:
        with self._lock:
            if self._conversations.pop(conversation_id, None) is None:
                raise KeyError(conversation_id)
            self._messages = {
                message_id: message
                for message_id, message in self._messages.items()
                if message.conversation_id != conversation_id
            }

    def append_message(self, message: ChatMessage) -> ChatMessage:
        with self._lock:
            if message.conversation_id not in self._conversations:
                raise KeyError(message.conversation_id)
            if message.message_id in self._messages:
                raise ValueError(f"duplicate message_id: {message.message_id}")
            if message.client_message_id is not None and any(
                existing.conversation_id == message.conversation_id
                and existing.client_message_id == message.client_message_id
                for existing in self._messages.values()
            ):
                raise ValueError(
                    f"duplicate client_message_id: {message.client_message_id}"
                )
            stored = replace(message, sequence_no=self._next_sequence)
            self._next_sequence += 1
            self._messages[message.message_id] = stored
        return stored

    def list_messages(
        self, conversation_id: str, *, limit: int = 100
    ) -> list[ChatMessage]:
        with self._lock:
            messages = sorted(
                (
                    message
                    for message in self._messages.values()
                    if message.conversation_id == conversation_id
                ),
                key=lambda message: message.sequence_no or 0,
            )
        return messages[-limit:]

    def find_user_message(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None:
        with self._lock:
            return next(
                (
                    message
                    for message in self._messages.values()
                    if message.conversation_id == conversation_id
                    and message.role == "USER"
                    and message.client_message_id == client_message_id
                ),
                None,
            )

    def find_assistant_reply(self, user_message_id: str) -> ChatMessage | None:
        with self._lock:
            return next(
                (
                    message
                    for message in self._messages.values()
                    if message.role == "ASSISTANT"
                    and message.reply_to_message_id == user_message_id
                ),
                None,
            )
