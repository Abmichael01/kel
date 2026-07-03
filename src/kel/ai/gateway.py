"""Provider-independent types used by the conversation layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AIReply:
    """The small part of an AI response the application needs."""

    text: str
    response_id: str


class ChatGateway(Protocol):
    """Contract implemented by any conversational AI provider."""

    def reply(self, user_text: str, previous_response_id: str | None = None) -> AIReply:
        """Return the next assistant response in a conversation."""
        ...
