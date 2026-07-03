"""OpenAI Responses API implementation of Kel's chat gateway."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from kel.ai.gateway import AIReply


class OpenAIChat:
    """Translate Kel's small chat contract into OpenAI SDK calls."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._instructions = instructions
        self._client = client if client is not None else OpenAI(api_key=api_key)

    def reply(self, user_text: str, previous_response_id: str | None = None) -> AIReply:
        """Send one turn while preserving the API's multi-turn conversation state."""
        request: dict[str, Any] = {
            "model": self._model,
            "instructions": self._instructions,
            "input": user_text,
        }
        if previous_response_id is not None:
            request["previous_response_id"] = previous_response_id

        response = self._client.responses.create(**request)
        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("OpenAI returned a response without displayable text.")

        return AIReply(text=answer, response_id=response.id)
