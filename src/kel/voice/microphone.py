"""Local microphone recording through PortAudio and sounddevice."""

from __future__ import annotations

import io
import wave
from typing import Any

import numpy as np
import sounddevice as sd

from kel.voice.contracts import AudioClip


def encode_pcm_as_wav(pcm_data: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap signed 16-bit PCM samples in a standard WAV container."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return output.getvalue()


class SoundDeviceMicrophone:
    """Record one-channel, 16-bit audio from the computer's microphone."""

    def __init__(self, *, sample_rate: int = 16_000, device: str | None = None) -> None:
        self._sample_rate = sample_rate
        self._device = device
        self._stream: Any | None = None
        self._chunks: list[Any] = []
        self._status_messages: list[str] = []

    def start(self) -> None:
        """Open the input device and begin collecting audio chunks."""
        if self._stream is not None:
            raise RuntimeError("The microphone is already recording.")

        self._chunks = []
        self._status_messages = []

        def receive_audio(
            input_data: Any,
            _frame_count: int,
            _time_info: Any,
            status: Any,
        ) -> None:
            if status:
                self._status_messages.append(str(status))
            self._chunks.append(input_data.copy())

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            device=self._device,
            callback=receive_audio,
        )
        self._stream.start()

    def stop(self) -> AudioClip:
        """Close the input stream and return the captured audio as WAV."""
        if self._stream is None:
            raise RuntimeError("The microphone is not recording.")

        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()

        if not self._chunks:
            raise RuntimeError("The microphone did not capture any audio.")

        samples = np.concatenate(self._chunks, axis=0)
        wav_data = encode_pcm_as_wav(samples.tobytes(), sample_rate=self._sample_rate)
        return AudioClip(data=wav_data, filename="microphone.wav")

    def cancel(self) -> None:
        """Close the input stream and discard any captured audio."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._chunks = []
