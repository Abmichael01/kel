"""Embed text with OpenAI; the only module that knows the embeddings endpoint."""

from __future__ import annotations

from typing import Any


class OpenAIEmbedder:
    """Turn text into a vector using an OpenAI embedding model."""

    def __init__(self, *, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for one piece of text."""
        response = self._client.embeddings.create(model=self._model, input=text)
        return list(response.data[0].embedding)
