"""The memory store keeps everything on disk and recalls only what's relevant."""

from __future__ import annotations

from kel.memory.store import MemoryStore


class FakeEmbedder:
    """Maps known text to fixed vectors so retrieval is deterministic in tests."""

    def __init__(self, table: dict[str, list[float]]) -> None:
        self._table = table
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self._table[text]


TABLE = {
    "I love dogs": [1.0, 0.0, 0.0],
    "cats are alright": [0.0, 1.0, 0.0],
    "pizza is the best food": [0.0, 0.0, 1.0],
    "tell me about my dog": [0.9, 0.1, 0.0],
    "what food do I like": [0.0, 0.1, 0.9],
}


def build_store(**kwargs: object) -> MemoryStore:
    return MemoryStore(embedder=FakeEmbedder(TABLE), **kwargs)


def test_recall_returns_the_most_relevant_memory_first() -> None:
    store = build_store(top_k=1)
    store.remember("I love dogs")
    store.remember("cats are alright")
    store.remember("pizza is the best food")

    assert store.recall("tell me about my dog") == ["I love dogs"]


def test_recall_ranks_by_relevance_and_limits_to_top_k() -> None:
    store = build_store(top_k=2)
    store.remember("I love dogs")
    store.remember("cats are alright")
    store.remember("pizza is the best food")

    result = store.recall("what food do I like")

    assert result[0] == "pizza is the best food"
    assert len(result) == 2


def test_recall_on_an_empty_store_returns_nothing() -> None:
    store = build_store()

    assert store.recall("anything") == []


def test_memories_persist_across_store_instances(tmp_path: object) -> None:
    path = tmp_path / "memories.json"  # type: ignore[operator]

    first = build_store(path=path)
    first.remember("I love dogs")

    reloaded = build_store(path=path)

    assert reloaded.recall("tell me about my dog") == ["I love dogs"]


def test_recall_and_remember_reuses_one_embedding_for_the_current_turn() -> None:
    embedder = FakeEmbedder(TABLE)
    store = MemoryStore(embedder=embedder, top_k=1)
    store.remember("I love dogs")
    embedder.calls.clear()

    result = store.recall_and_remember("tell me about my dog")

    assert result == ["I love dogs"]
    assert embedder.calls == ["tell me about my dog"]
