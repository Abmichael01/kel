"""Small shared types for the memory subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Memory:
    """One remembered fact and the embedding used to find it again."""

    text: str
    embedding: list[float]


class Embedder(Protocol):
    """Turn a piece of text into a vector that captures its meaning."""

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for the supplied text."""
        ...
