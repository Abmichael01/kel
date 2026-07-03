"""Seeding Kel's backstory loads her life into the vector memory store."""

from __future__ import annotations

from kel.memory.seed_memories import KEL_BACKSTORY, seed_backstory
from kel.memory.store import MemoryStore


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


def test_seed_adds_every_backstory_fact() -> None:
    store = MemoryStore(embedder=FakeEmbedder())

    count = seed_backstory(store)

    assert count == len(KEL_BACKSTORY)
    assert count >= 10  # she has a real, fleshed-out life
    assert store.recall("tell me about yourself")  # the facts are retrievable
