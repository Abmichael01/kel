"""The attention state machine: pure logic with no audio or network knowledge."""

from __future__ import annotations

import time
from collections.abc import Callable

from kel.wake.contracts import AttentionState, Phrase, SleepReason


class AttentionGate:
    """Decide when a cloud session may exist, based on local trigger phrases.

    The gate owns no microphone, speaker, or socket. It only tracks state and an
    idle deadline, so it can be exercised with a fake clock in tests.
    """

    def __init__(
        self,
        *,
        auto_sleep_seconds: float,
        on_wake: Callable[[], None],
        on_sleep: Callable[[SleepReason], None],
        quick_sleep_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._auto_sleep_seconds = auto_sleep_seconds
        self._quick_sleep_seconds = quick_sleep_seconds
        self._on_wake = on_wake
        self._on_sleep = on_sleep
        self._clock = clock
        self._state = AttentionState.ASLEEP
        self._deadline: float | None = None
        self._active_timeout = auto_sleep_seconds

    @property
    def state(self) -> AttentionState:
        """The current attention state."""
        return self._state

    def handle_phrase(self, phrase: Phrase) -> None:
        """React to a detected phrase, ignoring ones irrelevant to this state."""
        if self._state is AttentionState.ASLEEP and phrase is Phrase.PAY_ATTENTION:
            self._wake(self._auto_sleep_seconds)
        elif self._state is AttentionState.ASLEEP and phrase is Phrase.QUICK:
            self._wake(self._quick_sleep_seconds)
        elif self._state is AttentionState.AWAKE and phrase is Phrase.AT_EASE:
            self._sleep(SleepReason.AT_EASE)

    def note_user_speech(self) -> None:
        """Postpone auto-sleep; a real exchange earns the full awake window.

        A quick "Kel?" starts with a short window, but the moment the user
        actually speaks it becomes a normal conversation, so it must not nap out
        from under them.
        """
        if self._state is AttentionState.AWAKE:
            self._active_timeout = self._auto_sleep_seconds
            self._arm_deadline()

    def check_timeout(self) -> None:
        """Auto-sleep if Kel has been awake and silent past the idle deadline."""
        if (
            self._state is AttentionState.AWAKE
            and self._deadline is not None
            and self._clock() >= self._deadline
        ):
            self._sleep(SleepReason.TIMEOUT)

    def _wake(self, timeout: float) -> None:
        self._state = AttentionState.AWAKE
        self._active_timeout = timeout
        self._arm_deadline()
        self._on_wake()

    def _sleep(self, reason: SleepReason) -> None:
        self._state = AttentionState.ASLEEP
        self._deadline = None
        self._on_sleep(reason)

    def _arm_deadline(self) -> None:
        if self._active_timeout > 0:
            self._deadline = self._clock() + self._active_timeout
        else:
            self._deadline = None
