"""The serial link sends a line to the Arduino and reads one line back."""

from __future__ import annotations

from kel.body.serial_link import SerialLink


class FakeSerial:
    def __init__(self, response: bytes) -> None:
        self.written: list[bytes] = []
        self._response = response

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def readline(self) -> bytes:
        return self._response


def test_send_writes_the_command_with_a_newline_and_returns_the_reply() -> None:
    fake = FakeSerial(b"pong\n")
    link = SerialLink(serial=fake)

    reply = link.send("ping")

    assert fake.written == [b"ping\n"]
    assert reply == "pong"
