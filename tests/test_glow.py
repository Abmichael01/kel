"""StateGlow turns Kel's current state into a colour on her body."""

from __future__ import annotations

from kel.body.glow import STATE_COLORS, StateGlow


class FakeBody:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []

    def set_color(self, red: int, green: int, blue: int) -> None:
        self.colors.append((red, green, blue))


def test_sleeping_is_red() -> None:
    body = FakeBody()
    StateGlow(body).set("sleeping")

    assert body.colors == [STATE_COLORS["sleeping"]]
    assert STATE_COLORS["sleeping"] == (255, 0, 0)


def test_each_known_state_sends_its_color() -> None:
    body = FakeBody()
    glow = StateGlow(body)

    for state in ("listening", "thinking", "typing"):
        glow.set(state)

    assert body.colors == [
        STATE_COLORS["listening"],
        STATE_COLORS["thinking"],
        STATE_COLORS["typing"],
    ]


def test_unknown_state_does_nothing() -> None:
    body = FakeBody()
    StateGlow(body).set("noodling")

    assert body.colors == []


def test_no_body_is_safe() -> None:
    StateGlow(None).set("sleeping")  # must not raise
