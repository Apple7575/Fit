from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai.jd_coaching.baseline import call_qwen
from ai.jd_coaching.conversation_store import (
    ChatMessage,
    Conversation,
    ConversationStore,
)


QwenCaller = Callable[..., dict[str, Any]]


def chat_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "answer",
            "referenced_requirement_ids",
            "follow_up_questions",
        ],
        "properties": {
            "answer": {"type": "string"},
            "referenced_requirement_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


class ChatService:
    def __init__(
        self,
        *,
        config: Mapping[str, str],
        store: ConversationStore,
        qwen_caller: QwenCaller = call_qwen,
        history_limit: int = 20,
    ) -> None:
        self._config = config
        self._store = store
        self._qwen_caller = qwen_caller
        self._history_limit = history_limit

    def respond(
        self,
        *,
        conversation: Conversation,
        context: Mapping[str, Any],
        analysis_result: Mapping[str, Any],
        client_message_id: str,
        content: str,
    ) -> dict[str, Any]:
        existing_user = self._store.find_user_message(
            conversation.conversation_id, client_message_id
        )
        if existing_user is not None:
            if existing_user.content != content:
                raise ValueError("client_message_id was already used for other content")
            existing_reply = self._store.find_assistant_reply(existing_user.message_id)
            if existing_reply is not None:
                return _exchange_response(existing_user, existing_reply)
            user_message = existing_user
        else:
            user_message = ChatMessage(
                message_id=f"msg_{uuid4().hex}",
                conversation_id=conversation.conversation_id,
                role="USER",
                content=content,
                client_message_id=client_message_id,
                reply_to_message_id=None,
                metadata={},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            user_message = self._store.append_message(user_message)

        history = self._store.list_messages(
            conversation.conversation_id, limit=self._history_limit
        )
        response = self._qwen_caller(
            self._config,
            _build_messages(context, analysis_result, history),
            max_tokens=1600,
            timeout_seconds=120,
            schema=chat_output_schema(),
            schema_name="jd_coaching_chat_response",
        )
        output = response["output"]
        _validate_output(output, analysis_result)
        assistant_message = ChatMessage(
            message_id=f"msg_{uuid4().hex}",
            conversation_id=conversation.conversation_id,
            role="ASSISTANT",
            content=output["answer"].strip(),
            client_message_id=None,
            reply_to_message_id=user_message.message_id,
            metadata={
                "referenced_requirement_ids": output[
                    "referenced_requirement_ids"
                ],
                "follow_up_questions": output["follow_up_questions"],
                "model": response.get("model", self._config["model"]),
                "usage": response.get("usage", {}),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assistant_message = self._store.append_message(assistant_message)
        return _exchange_response(user_message, assistant_message)


def _build_messages(
    context: Mapping[str, Any],
    analysis_result: Mapping[str, Any],
    history: list[ChatMessage],
) -> list[dict[str, str]]:
    system = {
        "company_name": context.get("company_name"),
        "position_name": context.get("position_name"),
        "analysis": {
            "summary": analysis_result.get("summary", {}),
            "requirements": analysis_result.get("requirements", []),
        },
    }
    messages = [
        {
            "role": "system",
            "content": (
                "너는 지원자의 JD 적합성 분석 결과를 설명하고 경험을 구체화하는 "
                "코치다. 제공된 분석 결과와 대화에만 근거해 답한다. 확인되지 않은 "
                "경험이나 성과를 만들지 않는다. 근거가 부족하면 부족하다고 말하고 "
                "확인 질문을 제시한다. referenced_requirement_ids에는 실제로 답변에 "
                "사용한 requirement_id만 넣는다.\n\n"
                + json.dumps(system, ensure_ascii=False)
            ),
        }
    ]
    for message in history:
        messages.append(
            {
                "role": "user" if message.role == "USER" else "assistant",
                "content": message.content,
            }
        )
    return messages


def _validate_output(
    output: Mapping[str, Any], analysis_result: Mapping[str, Any]
) -> None:
    answer = output.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be a non-empty string")
    references = output.get("referenced_requirement_ids")
    questions = output.get("follow_up_questions")
    if not isinstance(references, list) or not all(
        isinstance(item, str) for item in references
    ):
        raise ValueError("referenced_requirement_ids must be a string list")
    if len(references) != len(set(references)):
        raise ValueError("referenced_requirement_ids must not contain duplicates")
    known = {
        item.get("requirement_id")
        for item in analysis_result.get("requirements", [])
        if isinstance(item, Mapping)
    }
    unknown = set(references) - known
    if unknown:
        raise ValueError(f"unknown requirement reference: {sorted(unknown)}")
    if not isinstance(questions, list) or not all(
        isinstance(item, str) and item.strip() for item in questions
    ):
        raise ValueError("follow_up_questions must be a non-empty string list")


def _exchange_response(
    user_message: ChatMessage, assistant_message: ChatMessage
) -> dict[str, Any]:
    return {
        "user_message": _message_response(user_message),
        "assistant_message": _message_response(assistant_message),
    }


def _message_response(message: ChatMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "content": message.content,
        "client_message_id": message.client_message_id,
        "reply_to_message_id": message.reply_to_message_id,
        "metadata": message.metadata,
        "created_at": message.created_at,
        "sequence_no": message.sequence_no,
    }
