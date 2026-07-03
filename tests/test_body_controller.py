"""The body controller turns nice calls into the Arduino's text commands."""

from __future__ import annotations

from kel.body.controller import BodyController


class FakeLink:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, command: str) -> str:
        self.sent.append(command)
        return "ok"


def test_set_color_clamps_to_bytes_and_formats() -> None:
    link = FakeLink()
    BodyController(link).set_color(300, -5, 128)

    assert link.sent == ["rgb 255 0 128"]


def test_move_servo_clamps_the_angle() -> None:
    link = FakeLink()
    BodyController(link).move_servo(9, 200)

    assert link.sent == ["servo 9 180"]


def test_ping_sends_ping() -> None:
    link = FakeLink()
    BodyController(link).ping()

    assert link.sent == ["ping"]


def test_gesture_runs_a_motion_sequence_and_ends_centered() -> None:
    link = FakeLink()
    body = BodyController(link, sleep=lambda _seconds: None)  # don't wait on real time

    summary = body.gesture("nod", 9)

    assert len(link.sent) >= 2  # a real motion, not a single frozen angle
    assert all(command.startswith("servo 9 ") for command in link.sent)
    assert link.sent[-1] == "servo 9 90"  # returns to centre
    assert summary == "Did a nod."


def test_unknown_gesture_falls_back_to_a_nod() -> None:
    link = FakeLink()
    body = BodyController(link, sleep=lambda _seconds: None)

    body.gesture("backflip", 9)

    assert link.sent[-1] == "servo 9 90"  # still a safe, centred motion
