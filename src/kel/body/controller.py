"""Drive the body: friendly methods that send the Arduino's text commands.

Values are clamped here too (belt and braces — the sketch clamps as well), so a
bad number can never reach the hardware.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol


class Link(Protocol):
    def send(self, command: str) -> str: ...


# A gesture is a timed sequence of angle offsets from centre, so the servo actually MOVES
# (nods, shakes, glances) instead of snapping to one angle and freezing. Each step is
# (offset_from_centre_degrees, seconds_to_hold_before_the_next_step).
_GESTURES: dict[str, tuple[tuple[int, float], ...]] = {
    "nod": ((32, 0.22), (-28, 0.22), (20, 0.18), (0, 0.16)),
    "shake": ((-38, 0.2), (38, 0.2), (-26, 0.18), (26, 0.18), (0, 0.16)),
    "look_left": ((55, 0.45), (0, 0.2)),
    "look_right": ((-55, 0.45), (0, 0.2)),
    "wiggle": ((16, 0.12), (-16, 0.12), (12, 0.1), (-12, 0.1), (0, 0.1)),
    "center": ((0, 0.15),),
}
GESTURE_NAMES = tuple(_GESTURES)


class BodyController:
    """Send colour and servo commands to the Arduino body."""

    def __init__(self, link: Link, *, sleep: Callable[[float], None] = time.sleep) -> None:
        self._link = link
        self._sleep = sleep  # injectable so tests don't wait on real time

    def ping(self) -> str:
        """Check the body is alive (expects 'pong')."""
        return self._link.send("ping")

    def set_color(self, red: int, green: int, blue: int) -> str:
        """Set the RGB LED colour (0-255 each) — Kel's feeling as colour."""
        return self._link.send(f"rgb {_byte(red)} {_byte(green)} {_byte(blue)}")

    def move_servo(self, pin: int, angle: int) -> str:
        """Move the servo on a pin to an angle (0-180)."""
        return self._link.send(f"servo {int(pin)} {_angle(angle)}")

    def gesture(self, name: str, pin: int, *, center: int = 90) -> str:
        """Perform a named motion (nod/shake/look_left/look_right/wiggle/center).

        Runs a short sequence of servo writes with pauses so the servo actually moves
        through a recognizable gesture and ends centred, instead of holding one angle.
        """
        steps = _GESTURES.get(name, _GESTURES["nod"])
        for offset, hold in steps:
            self._link.send(f"servo {int(pin)} {_angle(center + offset)}")
            self._sleep(hold)
        return f"Did a {name.replace('_', ' ')}."

    def set_mode(self, name: str) -> str:
        """Switch the body's animated mood (the Arduino rolls its colours)."""
        return self._link.send(f"mode {name}")

    def close(self) -> None:
        """Close the underlying link if it can be closed."""
        close = getattr(self._link, "close", None)
        if close is not None:
            close()


def _byte(value: int) -> int:
    return max(0, min(255, int(value)))


def _angle(value: int) -> int:
    return max(0, min(180, int(value)))
