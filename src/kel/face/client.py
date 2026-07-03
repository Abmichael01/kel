"""Drive Kel's desktop face window over its local socket.

Sends the same ``mode <name>`` commands the Arduino body understands, plus a
``speak <0|1>`` lip-sync signal. All sending happens on a background thread and
never blocks the caller; if the face window isn't running, commands are simply
dropped and it reconnects when it comes back.
"""

from __future__ import annotations

import queue
import socket
import threading


class ScreenFace:
    """A non-blocking client for the on-screen face window."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._addr = (host, port)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_mood(self, mood: str) -> None:
        """Show a mood (one of the face's known modes)."""
        self._queue.put(f"mode {mood}")

    def set_speaking(self, speaking: bool) -> None:
        """Start or stop the talking lip-sync."""
        self._queue.put(f"speak {1 if speaking else 0}")

    def close(self) -> None:
        """Stop the sender thread and drop the connection."""
        self._stop.set()
        self._queue.put(None)

    def _run(self) -> None:
        sock: socket.socket | None = None
        while not self._stop.is_set():
            try:
                command = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if command is None:
                break
            try:
                if sock is None:
                    sock = socket.create_connection(self._addr, timeout=1.0)
                sock.sendall((command + "\n").encode())
            except OSError:
                # The window may be closed or still starting; drop and retry later.
                if sock is not None:
                    sock.close()
                sock = None
        if sock is not None:
            sock.close()
