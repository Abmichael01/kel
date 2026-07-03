from types import SimpleNamespace

from kel.ai.openai_chat import OpenAIChat


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(output_text="Hello from Kel", id="response-2")


def test_openai_chat_translates_the_gateway_call() -> None:
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    chat = OpenAIChat(
        api_key="unused-in-test",
        model="test-model",
        instructions="Be Kel.",
        client=client,
    )

    reply = chat.reply("Hello", previous_response_id="response-1")

    assert reply.text == "Hello from Kel"
    assert reply.response_id == "response-2"
    assert responses.request == {
        "model": "test-model",
        "instructions": "Be Kel.",
        "input": "Hello",
        "previous_response_id": "response-1",
    }
