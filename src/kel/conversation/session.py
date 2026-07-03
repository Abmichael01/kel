"""Manage conversation state without depending on a specific AI provider."""

from __future__ import annotations

from dataclasses import dataclass, field

from kel.ai.gateway import AIReply, ChatGateway


@dataclass(slots=True)
class ConversationSession:
    """A single multi-turn conversation between one human and Kel."""

    gateway: ChatGateway
    _previous_response_id: str | None = field(default=None, init=False, repr=False)

    def send(self, user_text: str) -> AIReply:
        """Validate and send a user message, then remember the returned state ID."""
        message = user_text.strip()
        if not message:
            raise ValueError("A message cannot be empty.")

        reply = self.gateway.reply(message, self._previous_response_id)
        self._previous_response_id = reply.response_id
        return reply

    def reset(self) -> None:
        """Forget the server-side conversation link and begin a new chat."""
        self._previous_response_id = None
