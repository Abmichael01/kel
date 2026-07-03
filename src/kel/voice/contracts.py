"""Small contracts that keep voice stages independently replaceable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AudioClip:
    """Encoded audio plus the metadata needed by an API or player."""

    data: bytes
    filename: str = "audio.wav"
    media_type: str = "audio/wav"


@dataclass(frozen=True, slots=True)
class VoiceTurn:
    """Visible results of every stage in one push-to-talk turn."""

    transcript: str
    reply_text: str
    reply_audio: AudioClip


class AudioRecorder(Protocol):
    """Capture microphone audio without knowing anything about the UI."""

    def start(self) -> None:
        """Begin capturing audio."""
        ...

    def stop(self) -> AudioClip:
        """Stop capturing and return the recorded clip."""
        ...

    def cancel(self) -> None:
        """Stop capturing and discard the recording."""
        ...


class Transcriber(Protocol):
    """Convert speech audio to text."""

    def transcribe(self, audio: AudioClip) -> str:
        """Return the spoken words in an audio clip."""
        ...


class SpeechGenerator(Protocol):
    """Convert response text to generated speech."""

    def generate(self, text: str) -> AudioClip:
        """Return generated speech for the supplied text."""
        ...


class AudioPlayer(Protocol):
    """Play an encoded audio clip through a local output device."""

    def play(self, audio: AudioClip) -> None:
        """Block until the supplied clip finishes playing."""
        ...
