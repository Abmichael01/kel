"""A line-based serial link to the Arduino: send one command, read one reply.

This is just the pipe between the brain (Python) and the body (Arduino). It knows
nothing about specific commands — it writes a line and reads the line back.
"""

from __future__ import annotations

import glob
import threading
from typing import Any


def find_port() -> str | None:
    """Return the first Arduino-style serial port, or None if none is plugged in."""
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


class SerialLink:
    """Send newline-terminated commands to the board and read its reply."""

    def __init__(self, *, serial: Any) -> None:
        self._serial = serial
        self._lock = threading.Lock()

    def send(self, command: str) -> str:
        """Write one command line and return the board's reply line.

        Guarded by a lock so the orb's mood updates and a servo move (which run on
        separate worker threads) can't interleave their writes and replies.
        """
        with self._lock:
            self._serial.write(f"{command}\n".encode())
            return self._serial.readline().decode(errors="replace").strip()

    def close(self) -> None:
        """Close the underlying serial port."""
        close = getattr(self._serial, "close", None)
        if close is not None:
            close()

    @classmethod
    def open(cls, port: str, *, baud: int = 9600, timeout: float = 2.0) -> SerialLink:
        """Open a real serial port (needs the `robot` extra: pyserial)."""
        import serial

        return cls(serial=serial.Serial(port, baud, timeout=timeout))
