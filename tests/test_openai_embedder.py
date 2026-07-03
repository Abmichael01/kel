"""The OpenAI embedder turns text into a vector via the embeddings endpoint."""

from __future__ import annotations

from types import SimpleNamespace

from kel.memory.openai_embedder import OpenAIEmbedder


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create(self, *, model: str, input: str) -> SimpleNamespace:
        self.calls.append((model, input))
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


def test_embedder_calls_the_model_and_returns_the_vector() -> None:
    embeddings = FakeEmbeddings()
    client = SimpleNamespace(embeddings=embeddings)
    embedder = OpenAIEmbedder(client=client, model="text-embedding-3-small")

    vector = embedder.embed("hello there")

    assert vector == [0.1, 0.2, 0.3]
    assert embeddings.calls == [("text-embedding-3-small", "hello there")]
