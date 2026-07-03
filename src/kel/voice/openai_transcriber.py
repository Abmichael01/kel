"""OpenAI speech-to-text implementation."""

from __future__ import annotations

from typing import Any

from kel.voice.contracts import AudioClip


class OpenAITranscriber:
    """Turn an audio clip into text with OpenAI's transcription endpoint."""

    def __init__(self, *, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def transcribe(self, audio: AudioClip) -> str:
        """Upload one recording and return its trimmed transcript."""
        result = self._client.audio.transcriptions.create(
            model=self._model,
            file=(audio.filename, audio.data, audio.media_type),
        )
        transcript = result.text.strip()
        if not transcript:
            raise RuntimeError("No speech was detected in the recording.")
        return transcript
