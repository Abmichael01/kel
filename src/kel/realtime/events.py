"""Provider-independent events shown by a realtime user interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RealtimeDisplayEventKind = Literal[
    "connected",
    "speech_started",
    "speech_stopped",
    "user_transcript",
    "assistant_transcript",
    "assistant_speaking",
    "assistant_done",
    "interrupted",
    "looked",
    "remembered",
    "recalled",
    "acted",
    "type_mode",
    "error",
]


@dataclass(frozen=True, slots=True)
class RealtimeDisplayEvent:
    """A small UI event emitted by the live conversation session."""

    kind: RealtimeDisplayEventKind
    text: str = ""
