"""Type text and press keys into whatever the user has focused.

Kel doesn't aim the cursor — the user clicks/focuses a text box, then asks Kel to
type. We send keystrokes through whatever tool is available: xdotool on X11,
ydotool or wtype on Wayland.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from collections.abc import Callable

_TOOLS = ("xdotool", "ydotool", "wtype")
_WTYPE_DELAY_MS = 12

# ydotool presses by Linux key code (press:1, release:0); a few common ones.
_YDOTOOL_KEYS = {
    "return": ["28:1", "28:0"],
    "enter": ["28:1", "28:0"],
    "tab": ["15:1", "15:0"],
    "space": ["57:1", "57:0"],
    "backspace": ["14:1", "14:0"],
    "escape": ["1:1", "1:0"],
}
_YDOTOOL_SWIPE_KEYS = {"left": "105", "right": "106"}


class Keyboard:
    """Send typed text and key presses to the focused window."""

    def __init__(
        self,
        *,
        tool: str = "",
        runner: Callable[[list[str]], object] | None = None,
        which: Callable[[str], str | None] = shutil.which,
        desktop: str | None = None,
    ) -> None:
        self._tool = tool or self._detect(which)
        self._runner = runner or _run
        desktop_name = os.environ.get("XDG_CURRENT_DESKTOP", "") if desktop is None else desktop
        self._use_niri = desktop_name.strip().lower() == "niri" and bool(which("niri"))

    def type_text(self, text: str) -> str:
        """Type text into the currently focused field."""
        if not self._tool:
            return "No typing tool found. Install xdotool (X11) or ydotool/wtype (Wayland)."
        if not text:
            return "Nothing to type."
        self._runner(self._type_argv(text))
        return f"Typed: {text}"

    def press_key(self, key: str) -> str:
        """Press a single key (like Return or Tab) in the focused field."""
        if not self._tool:
            return "No typing tool found. Install xdotool (X11) or ydotool/wtype (Wayland)."
        argv = self._key_argv(key)
        if argv is None:
            return f"I can't press '{key}' with {self._tool}."
        self._runner(argv)
        return f"Pressed {key}."

    def swipe(self, direction: str) -> str:
        """Send the allowlisted Super+Left or Super+Right desktop shortcut."""
        normalized = direction.strip().lower()
        if normalized not in {"left", "right"}:
            return "Swipe direction must be left or right."
        if self._use_niri:
            self._runner(self._swipe_argv(normalized))
            return f"Swiped {normalized} with Niri navigation."
        if not self._tool:
            return "No typing tool found. Install xdotool (X11) or ydotool/wtype (Wayland)."
        self._runner(self._swipe_argv(normalized))
        return f"Swiped {normalized} with Super+{normalized.title()}."

    def _detect(self, which: Callable[[str], str | None]) -> str:
        for name in _TOOLS:
            if which(name):
                return name
        return ""

    def _type_argv(self, text: str) -> list[str]:
        if self._tool == "xdotool":
            return ["xdotool", "type", "--clearmodifiers", "--", text]
        if self._tool == "ydotool":
            return ["ydotool", "type", text]
        return ["wtype", "-d", str(_WTYPE_DELAY_MS), text]

    def _key_argv(self, key: str) -> list[str] | None:
        if self._tool == "xdotool":
            return ["xdotool", "key", key]
        if self._tool == "wtype":
            return ["wtype", "-k", key]
        codes = _YDOTOOL_KEYS.get(key.lower())
        return ["ydotool", "key", *codes] if codes else None

    def _swipe_argv(self, direction: str) -> list[str]:
        if self._use_niri:
            return ["niri", "msg", "action", f"focus-column-{direction}"]
        arrow = direction.title()
        if self._tool == "xdotool":
            return ["xdotool", "key", f"super+{arrow}"]
        if self._tool == "wtype":
            return ["wtype", "-M", "logo", "-k", arrow, "-m", "logo"]
        arrow_code = _YDOTOOL_SWIPE_KEYS[direction]
        return [
            "ydotool",
            "key",
            "125:1",
            f"{arrow_code}:1",
            f"{arrow_code}:0",
            "125:0",
        ]


def _run(argv: list[str]) -> None:
    # wtype types with a per-key delay, so a long sentence can take many seconds.
    # Use a generous window and swallow a timeout/missing tool so typing can never
    # crash the conversation.
    with contextlib.suppress(subprocess.TimeoutExpired, FileNotFoundError):
        subprocess.run(argv, timeout=30, check=False)
