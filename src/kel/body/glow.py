"""Drive the body LED from Kel's current state, so it always shows what she's doing.

The Arduino fades between colours on its own, so this just sends the target colour
for each state and the transition is smooth.
"""

from __future__ import annotations

from typing import Protocol

STATE_COLORS: dict[str, tuple[int, int, int]] = {
    "sleeping": (255, 0, 0),     # red — not awake
    "listening": (0, 255, 0),    # green — awake, listening to you
    "thinking": (0, 200, 200),   # cyan — working out a reply
    "speaking": (0, 80, 255),    # blue — talking
    "typing": (160, 0, 255),     # purple — in typing mode
}


class _Colorable(Protocol):
    def set_color(self, red: int, green: int, blue: int) -> None: ...


class StateGlow:
    """Set the body colour for a named state (no-op if there's no body)."""

    def __init__(self, body: _Colorable | None) -> None:
        self._body = body

    def set(self, state: str) -> None:
        """Glow the colour for a state, ignoring unknown states."""
        color = STATE_COLORS.get(state)
        if color is None or self._body is None:
            return
        self._body.set_color(*color)
