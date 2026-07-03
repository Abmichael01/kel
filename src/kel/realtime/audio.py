"""Full-duplex 24 kHz PCM streaming for Realtime conversations."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any

import sounddevice as sd

from kel.realtime.options import REALTIME_SAMPLE_RATE

SAMPLE_WIDTH_BYTES = 2


class StreamingMicrophone:
    """Continuously place small PCM microphone chunks onto an async queue."""

    def __init__(
        self,
        *,
        sample_rate: int = REALTIME_SAMPLE_RATE,
        block_duration_ms: int = 20,
        device: str | None = None,
        queue_capacity: int = 100,
    ) -> None:
        self._sample_rate = sample_rate
        self._block_size = sample_rate * block_duration_ms // 1000
        self._device = device
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_capacity)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: Any | None = None

    def start(self) -> None:
        """Open the local input device and begin queuing PCM chunks."""
        if self._stream is not None:
            raise RuntimeError("The realtime microphone is already running.")

        self._loop = asyncio.get_running_loop()

        def receive_audio(
            input_data: Any,
            _frame_count: int,
            _time_info: Any,
            _status: Any,
        ) -> None:
            chunk = bytes(input_data)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._offer_chunk, chunk)

        self._stream = sd.RawInputStream(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            channels=1,
            dtype="int16",
            device=self._device,
            callback=receive_audio,
        )
        self._stream.start()

    def _offer_chunk(self, chunk: bytes) -> None:
        """Keep recent audio if networking temporarily falls behind."""
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(chunk)

    async def read_chunk(self) -> bytes:
        """Wait for the next microphone chunk."""
        return await self._queue.get()

    def stop(self) -> None:
        """Stop and close the local input device immediately."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


@dataclass(frozen=True, slots=True)
class PlaybackProgress:
    """The portion of one model response that actually reached playback."""

    item_id: str
    content_index: int
    audio_end_ms: int


class PcmPlaybackBuffer:
    """A thread-safe byte buffer shared by network and audio callback threads."""

    def __init__(self, *, sample_rate: int = REALTIME_SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._audio = bytearray()
        self._lock = threading.Lock()
        self._item_id: str | None = None
        self._content_index = 0
        self._played_bytes = 0

    def append(self, *, item_id: str, content_index: int, audio: bytes) -> None:
        """Add one server audio delta to the current response buffer."""
        with self._lock:
            if item_id != self._item_id:
                self._audio.clear()
                self._item_id = item_id
                self._content_index = content_index
                self._played_bytes = 0
            self._audio.extend(audio)

    def read(self, size: int) -> bytes:
        """Remove up to `size` bytes for the sounddevice output callback."""
        with self._lock:
            count = min(size, len(self._audio))
            result = bytes(self._audio[:count])
            del self._audio[:count]
            self._played_bytes += count
            return result

    def interrupt(self) -> PlaybackProgress | None:
        """Discard unplayed audio and report how far playback reached."""
        with self._lock:
            if self._item_id is None or not self._audio:
                return None

            bytes_per_second = self._sample_rate * SAMPLE_WIDTH_BYTES
            audio_end_ms = self._played_bytes * 1000 // bytes_per_second
            progress = PlaybackProgress(
                item_id=self._item_id,
                content_index=self._content_index,
                audio_end_ms=audio_end_ms,
            )
            self._audio.clear()
            self._item_id = None
            self._played_bytes = 0
            return progress

    def clear(self) -> None:
        """Discard all audio and response tracking."""
        with self._lock:
            self._audio.clear()
            self._item_id = None
            self._played_bytes = 0

    def is_playing(self) -> bool:
        """Report whether any audio is still waiting to reach the speaker."""
        with self._lock:
            return len(self._audio) > 0


class StreamingSpeaker:
    """Play server PCM deltas continuously through a callback output stream."""

    def __init__(
        self,
        *,
        sample_rate: int = REALTIME_SAMPLE_RATE,
        block_duration_ms: int = 20,
        device: str | None = None,
        playback_buffer: PcmPlaybackBuffer | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._block_size = sample_rate * block_duration_ms // 1000
        self._device = device
        self._buffer = playback_buffer or PcmPlaybackBuffer(sample_rate=sample_rate)
        self._stream: Any | None = None

    def start(self) -> None:
        """Open the local speaker and begin consuming queued PCM audio."""
        if self._stream is not None:
            raise RuntimeError("The realtime speaker is already running.")

        def provide_audio(
            output_data: Any,
            _frame_count: int,
            _time_info: Any,
            _status: Any,
        ) -> None:
            audio = self._buffer.read(len(output_data))
            output_data[:] = audio + bytes(len(output_data) - len(audio))

        self._stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            channels=1,
            dtype="int16",
            device=self._device,
            callback=provide_audio,
        )
        self._stream.start()

    def enqueue(self, *, item_id: str, content_index: int, audio: bytes) -> None:
        """Queue a decoded server audio delta for immediate playback."""
        self._buffer.append(item_id=item_id, content_index=content_index, audio=audio)

    def interrupt(self) -> PlaybackProgress | None:
        """Immediately discard PCM not yet handed to the speaker device."""
        return self._buffer.interrupt()

    def is_playing(self) -> bool:
        """Report whether Kel is still speaking through the device."""
        return self._buffer.is_playing()

    def stop(self) -> None:
        """Abort pending playback and close the output device."""
        self._buffer.clear()
        if self._stream is not None:
            self._stream.abort()
            self._stream.close()
            self._stream = None
