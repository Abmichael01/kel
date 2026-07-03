"""Small shared types that keep the wake detector and the gate replaceable."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol


class Phrase(enum.Enum):
    """A trigger phrase the local detector can recognize."""

    PAY_ATTENTION = "pay_attention"
    AT_EASE = "at_ease"
    QUICK = "quick"


class AttentionState(enum.Enum):
    """Whether Kel is currently allowed to hear and answer."""

    ASLEEP = "asleep"
    AWAKE = "awake"


class SleepReason(enum.Enum):
    """Why the gate returned to sleep, for logging and feedback."""

    AT_EASE = "at_ease"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class WakeEvent:
    """One trigger phrase recognized by the local detector."""

    phrase: Phrase


class WakeWordDetector(Protocol):
    """Listen locally for trigger phrases and report them, knowing no cloud."""

    def start(self) -> None:
        """Open the local microphone and begin recognizing phrases."""
        ...

    def stop(self) -> None:
        """Stop recognizing and release the local microphone."""
        ...
