"""Launch a command in its own terminal window so it keeps running.

Unlike `run_command` (which waits for output), this starts the command detached in
a new terminal: it survives, the user can watch it, and Kel keeps chatting. If no
terminal emulator is found, the command is started in the background instead.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from kel.system.shell import is_dangerous

# Terminal emulators and the args that precede "bash -c <script>".
_TERMINALS: list[tuple[str, list[str]]] = [
    ("konsole", ["-e"]),
    ("alacritty", ["-e"]),
    ("kitty", []),
    ("wezterm", ["start", "--"]),
    ("foot", []),
    ("gnome-terminal", ["--"]),
    ("xterm", ["-e"]),
]


class TerminalLauncher:
    """Open a command in a new terminal window (or background it as a fallback)."""

    def __init__(
        self,
        *,
        terminal: str = "",
        block_dangerous: bool = True,
        spawner: Callable[[list[str]], Any] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._terminal = terminal
        self._block_dangerous = block_dangerous
        self._spawner = spawner or _spawn_detached
        self._which = which

    def launch(self, command: str) -> str:
        """Start a command in a new terminal window without waiting for it."""
        command = command.strip()
        if not command:
            return "No command was given."
        if self._block_dangerous and is_dangerous(command):
            return "Refused: that looks like a destructive, irreversible command."

        prefix = self._resolve_prefix()
        if prefix is None:
            self._spawner(["setsid", "bash", "-c", command])
            return f"Started in the background (no terminal found): {command}"
        self._spawner([*prefix, "bash", "-c", f"{command}; exec bash"])
        return f"Launched in a new terminal: {command}"

    def _resolve_prefix(self) -> list[str] | None:
        if self._terminal:
            return shlex.split(self._terminal)
        for name, separator in _TERMINALS:
            if self._which(name):
                return [name, *separator]
        return None


def _spawn_detached(argv: list[str]) -> None:
    """Start a process fully detached from Kel, with no I/O attached."""
    subprocess.Popen(
        argv,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
