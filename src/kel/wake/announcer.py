"""Speak short wake/sleep acknowledgements, rendering each line only once."""

from __future__ import annotations

from kel.voice.contracts import AudioClip, AudioPlayer, SpeechGenerator


class SpokenAnnouncer:
    """Render "I'm listening" / "Standing by" once and replay the cached audio.

    Caching keeps the acknowledgement instant on every wake and sleep, instead of
    waiting on the speech endpoint each time. An empty line stays silent.
    """

    def __init__(
        self,
        *,
        speech_generator: SpeechGenerator,
        player: AudioPlayer,
        greeting: str,
        farewell: str,
    ) -> None:
        self._speech_generator = speech_generator
        self._player = player
        self._greeting = greeting
        self._farewell = farewell
        self._greeting_clip: AudioClip | None = None
        self._farewell_clip: AudioClip | None = None

    def prepare(self) -> None:
        """Render both clips ahead of time so the first use is instant."""
        self._greeting_clip = self._render(self._greeting)
        self._farewell_clip = self._render(self._farewell)

    def greet(self) -> None:
        """Play the wake acknowledgement."""
        if not self._greeting:
            return
        if self._greeting_clip is None:
            self._greeting_clip = self._render(self._greeting)
        self._play(self._greeting_clip)

    def farewell(self) -> None:
        """Play the sleep acknowledgement."""
        if not self._farewell:
            return
        if self._farewell_clip is None:
            self._farewell_clip = self._render(self._farewell)
        self._play(self._farewell_clip)

    def _render(self, text: str) -> AudioClip | None:
        if not text:
            return None
        return self._speech_generator.generate(text)

    def _play(self, clip: AudioClip | None) -> None:
        if clip is not None:
            self._player.play(clip)
