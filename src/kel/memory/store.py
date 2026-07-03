"""A small on-disk vector memory: remember everything, recall the relevant few.

Everything Kel remembers lives in a JSON file, never in the base prompt. On
recall, only the closest handful of memories are returned, so the prompt stays
small no matter how much has been remembered.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from kel.memory.contracts import Embedder, Memory


class MemoryStore:
    """Store remembered facts and retrieve the most relevant by vector similarity."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        path: Path | None = None,
        top_k: int = 5,
    ) -> None:
        self._embedder = embedder
        self._path = Path(path) if path is not None else None
        self._top_k = top_k
        self._memories: list[Memory] = []
        self._load()

    def remember(self, text: str) -> None:
        """Embed and store one fact, then persist the whole store."""
        text = text.strip()
        if not text:
            return
        embedding = self._embedder.embed(text)
        self._memories.append(Memory(text=text, embedding=embedding))
        self._persist()

    def recall(self, query: str, k: int | None = None) -> list[str]:
        """Return up to ``k`` remembered facts most relevant to the query."""
        if not self._memories:
            return []
        query_vector = self._embedder.embed(query)
        return self._recall_vector(query_vector, k=k)

    def recall_and_remember(self, text: str, k: int | None = None) -> list[str]:
        """Recall related earlier memories, then store this turn with one embedding."""
        text = text.strip()
        if not text:
            return []
        embedding = self._embedder.embed(text)
        recalled = self._recall_vector(embedding, k=k)
        self._memories.append(Memory(text=text, embedding=embedding))
        self._persist()
        return recalled

    def _recall_vector(self, query_vector: list[float], k: int | None = None) -> list[str]:
        ranked = sorted(
            self._memories,
            key=lambda memory: _cosine_similarity(query_vector, memory.embedding),
            reverse=True,
        )
        limit = k if k is not None else self._top_k
        return [memory.text for memory in ranked[:limit]]

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._memories = [
            Memory(text=item["text"], embedding=list(item["embedding"]))
            for item in raw.get("memories", [])
        ]

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "memories": [
                {"text": memory.text, "embedding": memory.embedding} for memory in self._memories
            ]
        }
        self._path.write_text(json.dumps(payload), encoding="utf-8")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors; 0 when either has no magnitude."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
