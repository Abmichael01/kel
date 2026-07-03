"""Local WAV playback through PortAudio and sounddevice."""

from __future__ import annotations

import io
import wave

import numpy as np
import sounddevice as sd

from kel.voice.contracts import AudioClip


class SoundDeviceSpeaker:
    """Play 16-bit WAV audio through the selected computer speaker."""

    def __init__(self, *, device: str | None = None) -> None:
        self._device = device

    def play(self, audio: AudioClip) -> None:
        """Decode a WAV clip and block until playback is complete."""
        with wave.open(io.BytesIO(audio.data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            raw_audio = wav_file.readframes(wav_file.getnframes())

        if sample_width != 2:
            raise ValueError("Kel's speaker currently supports only 16-bit WAV audio.")

        samples = np.frombuffer(raw_audio, dtype="<i2")
        if channels > 1:
            samples = samples.reshape(-1, channels)

        sd.play(samples, samplerate=sample_rate, device=self._device)
        sd.wait()
