"""Kel's body as a living orb. The Arduino rolls each mood's colours fast and
smoothly on its own; this just names the current mood and latches feelings.

A feeling can be *latched* so it holds — told to stay sad, she stays sad — until she
sleeps or feels something new.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

# The moods the Arduino firmware knows how to animate.
MODES: frozenset[str] = frozenset(
    {
        "sleeping", "listening", "thinking", "typing",
        "happy", "sad", "angry", "excited", "surprised", "confused",
        "playful", "love", "calm", "alert", "normal",
    }
)


class _Moodable(Protocol):
    def set_mode(self, name: str) -> None: ...


class _Face(Protocol):
    def set_mood(self, mood: str) -> None: ...


class BodyOrb:
    """Track Kel's current mood and push it to the Arduino (and screen face)."""

    def __init__(self, body: _Moodable | None, face: _Face | None = None) -> None:
        self._body = body
        self._face = face
        self._mode = "sleeping"
        self._latched = False
        self._task: asyncio.Task[None] | None = None
        self._last_sent: str | None = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def latched(self) -> bool:
        return self._latched

    def start(self) -> None:
        """Begin pushing mood changes to the body (needs a running event loop)."""
        if self._face is not None:
            self._face.set_mood(self._mode)
        if self._task is None and self._body is not None:
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            await self._tick()
            await asyncio.sleep(0.1)

    async def _tick(self) -> None:
        """Push the current mode to the body, retrying until it is acknowledged.

        Opening the port resets the Arduino, and a command sent while it is still
        booting is silently lost. By only advancing ``_last_sent`` once the board
        replies ``ok``, a lost mood self-heals on the next tick instead of leaving
        the face frozen on whatever it last showed.
        """
        mode = self._mode
        if mode != self._last_sent and await asyncio.to_thread(self._push, mode):
            self._last_sent = mode

    def _push(self, mode: str) -> bool:
        """Send one mode and report whether the board acknowledged it."""
        try:
            reply = self._body.set_mode(mode)
        except Exception:  # noqa: BLE001 - a transient serial error just means retry
            return False
        # Real firmware answers "ok"; test doubles return None (treated as success).
        return reply is None or "ok" in str(reply).lower()

    def set_state(self, state: str) -> None:
        """Drive the orb from a system state, unless a feeling is latched."""
        if not self._latched:
            self._switch(state)

    def set_feeling(self, feeling: str) -> None:
        """Latch an emotion so it holds; 'normal' releases the latch."""
        feeling = feeling.strip().lower()
        if feeling in ("normal", "neutral", ""):
            self._latched = False
            self._switch("listening")
            return
        if feeling in MODES:
            self._latched = True
            self._switch(feeling)

    def sleep(self) -> None:
        """Go to sleep, releasing any latched feeling."""
        self._latched = False
        self._switch("sleeping")

    def _switch(self, mode: str) -> None:
        if mode in MODES and mode != self._mode:
            self._mode = mode
            if self._face is not None:
                self._face.set_mood(mode)
