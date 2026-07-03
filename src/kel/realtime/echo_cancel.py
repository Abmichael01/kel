"""Route Realtime audio through PipeWire's WebRTC echo canceller."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from collections.abc import Callable

_SOURCE_NAME = "kel_echo_cancel_source"
_SINK_NAME = "kel_echo_cancel_sink"


class PulseEchoCanceller:
    """Temporarily install echo-cancel nodes and make them the audio defaults."""

    def __init__(
        self,
        *,
        runner: Callable[[list[str]], str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._runner = runner or _run
        self._available = bool(which("pactl"))
        self._module_id = ""
        self._previous_source = ""
        self._previous_sink = ""

    def start(self) -> bool:
        """Create and select the AEC nodes, returning false on any setup failure."""
        if self._module_id:
            return True
        if not self._available:
            return False
        try:
            self._previous_source = self._runner(["pactl", "get-default-source"]).strip()
            self._previous_sink = self._runner(["pactl", "get-default-sink"]).strip()
            self._module_id = self._runner(
                [
                    "pactl",
                    "load-module",
                    "module-echo-cancel",
                    f"source_name={_SOURCE_NAME}",
                    f"sink_name={_SINK_NAME}",
                    "aec_method=webrtc",
                ]
            ).strip()
            if not self._module_id:
                raise RuntimeError("PipeWire returned no echo-cancel module ID.")
            self._runner(["pactl", "set-default-source", _SOURCE_NAME])
            self._runner(["pactl", "set-default-sink", _SINK_NAME])
        except (OSError, RuntimeError, subprocess.SubprocessError):
            self._restore()
            return False
        return True

    def stop(self) -> None:
        """Restore the user's previous audio defaults and remove the AEC nodes."""
        self._restore()

    def _restore(self) -> None:
        commands: list[list[str]] = []
        if self._previous_source:
            commands.append(["pactl", "set-default-source", self._previous_source])
        if self._previous_sink:
            commands.append(["pactl", "set-default-sink", self._previous_sink])
        if self._module_id:
            commands.append(["pactl", "unload-module", self._module_id])
        for command in commands:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                self._runner(command)
        self._module_id = ""
        self._previous_source = ""
        self._previous_sink = ""


def _run(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout
