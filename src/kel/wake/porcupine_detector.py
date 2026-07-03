"""The only module that knows Picovoice Porcupine and owns its 16 kHz capture.

The engine is injected so the adapter logic is testable with a fake handle, with
no real SDK, microphone, or model file required.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from kel.wake.contracts import Phrase

OnPhrase = Callable[[Phrase], None]


class PorcupineEngine(Protocol):
    """The slice of a pvporcupine handle the adapter relies on."""

    sample_rate: int
    frame_length: int

    def process(self, frame: Sequence[int]) -> int:
        """Return the index of a detected keyword, or -1 for none."""
        ...

    def delete(self) -> None:
        """Release the native resources."""
        ...


class PorcupineWakeWordDetector:
    """Feed 16 kHz PCM frames to Porcupine and report recognized phrases.

    Phrase order must match the keyword order given to the engine: index 0 is the
    first keyword path, index 1 the second, and so on.
    """

    def __init__(
        self,
        *,
        engine: PorcupineEngine,
        phrases: Sequence[Phrase],
        on_phrase: OnPhrase,
        device: str | None = None,
        stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._engine = engine
        self._phrases = tuple(phrases)
        self._on_phrase = on_phrase
        self._device = device
        self._stream_factory = stream_factory or _open_input_stream
        self._stream: Any | None = None

    def process_frame(self, frame: Sequence[int]) -> None:
        """Hand one frame to Porcupine and report any recognized phrase."""
        index = self._engine.process(frame)
        if index >= 0:
            self._on_phrase(self._phrases[index])

    def feed(self, raw: bytes) -> None:
        """Decode a raw little-endian 16-bit PCM block, then process it."""
        self.process_frame(array("h", raw))

    def start(self) -> None:
        """Open the dedicated 16 kHz input stream and begin recognizing."""
        if self._stream is not None:
            raise RuntimeError("The wake-word detector is already running.")
        self._stream = self._stream_factory(
            sample_rate=self._engine.sample_rate,
            frame_length=self._engine.frame_length,
            device=self._device,
            on_block=self.feed,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop the input stream and release the engine."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._engine.delete()


def _open_input_stream(
    *,
    sample_rate: int,
    frame_length: int,
    device: str | None,
    on_block: Callable[[bytes], None],
) -> Any:
    """Build a sounddevice stream that hands raw PCM blocks to the detector."""
    import sounddevice as sd

    def receive_audio(input_data: Any, _frames: int, _time: Any, _status: Any) -> None:
        on_block(bytes(input_data))

    return sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=frame_length,
        channels=1,
        dtype="int16",
        device=device,
        callback=receive_audio,
    )
