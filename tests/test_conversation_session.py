from kel.ai.gateway import AIReply
from kel.conversation.session import ConversationSession


class FakeChatGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def reply(self, user_text: str, previous_response_id: str | None = None) -> AIReply:
        self.calls.append((user_text, previous_response_id))
        turn_number = len(self.calls)
        return AIReply(text=f"answer {turn_number}", response_id=f"response-{turn_number}")


def test_session_passes_response_id_to_the_next_turn() -> None:
    gateway = FakeChatGateway()
    session = ConversationSession(gateway=gateway)

    session.send("Hello")
    second_reply = session.send("Do you remember me?")

    assert second_reply.text == "answer 2"
    assert gateway.calls == [
        ("Hello", None),
        ("Do you remember me?", "response-1"),
    ]


def test_session_reset_starts_a_new_conversation() -> None:
    gateway = FakeChatGateway()
    session = ConversationSession(gateway=gateway)

    session.send("First chat")
    session.reset()
    session.send("New chat")

    assert gateway.calls[-1] == ("New chat", None)


def test_session_rejects_an_empty_message() -> None:
    session = ConversationSession(gateway=FakeChatGateway())

    try:
        session.send("   ")
    except ValueError as error:
        assert str(error) == "A message cannot be empty."
    else:
        raise AssertionError("Expected an empty message to be rejected")
