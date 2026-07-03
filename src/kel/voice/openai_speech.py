"""OpenAI text-to-speech implementation."""

from __future__ import annotations

from typing import Any

from kel.voice.contracts import AudioClip


class OpenAISpeechGenerator:
    """Generate Kel's spoken answer as WAV audio."""

    def __init__(self, *, client: Any, model: str, voice: str) -> None:
        self._client = client
        self._model = model
        self._voice = voice

    def generate(self, text: str) -> AudioClip:
        """Generate a complete WAV response suitable for local playback."""
        response = self._client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=text,
            instructions="Speak warmly, naturally, and clearly as the robot Kel.",
            response_format="wav",
        )
        audio_data = response.content
        if not audio_data:
            raise RuntimeError("OpenAI returned an empty speech response.")
        return AudioClip(data=audio_data, filename="kel-response.wav")
