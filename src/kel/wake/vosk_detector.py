"""A free, no-account wake detector built on offline Vosk transcription.

Vosk needs no access key and recognizes any phrase, so triggers are matched as
text inside the local transcript. The recognizer is injected, which keeps the
matching logic testable without the model, microphone, or the `vosk` package.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from kel.wake.contracts import Phrase

OnPhrase = Callable[[Phrase], None]

_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")


def _normalize(text: str) -> str:
    """Lowercase and drop punctuation so "let's" and "lets" compare equal."""
    return _PUNCTUATION.sub("", text.lower()).strip()


class VoskRecognizer(Protocol):
    """The slice of a Vosk KaldiRecognizer the adapter relies on."""

    def AcceptWaveform(self, data: bytes) -> bool:
        """Return True when an utterance has ended and a final result is ready."""
        ...

    def Result(self) -> str:
        """Return the final transcript as a JSON string."""
        ...

    def PartialResult(self) -> str:
        """Return the in-progress transcript as a JSON string."""
        ...


class VoskWakeWordDetector:
    """Spot trigger phrases inside Vosk's locally produced transcripts.

    Only final results are matched: each spoken phrase yields exactly one final
    transcript, so a single utterance fires a phrase at most once.
    """

    def __init__(
        self,
        *,
        recognizer: VoskRecognizer,
        phrases: Mapping[str, Phrase],
        on_phrase: OnPhrase,
        device: str | None = None,
        sample_rate: int = 16_000,
        block_size: int = 4_000,
        stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._recognizer = recognizer
        self._phrases = {_normalize(text): phrase for text, phrase in phrases.items()}
        self._on_phrase = on_phrase
        self._device = device
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._stream_factory = stream_factory or _open_input_stream
        self._stream: Any | None = None

    def feed(self, raw: bytes) -> None:
        """Push one PCM block and report any phrase in a completed transcript."""
        if not self._recognizer.AcceptWaveform(raw):
            return
        text = str(json.loads(self._recognizer.Result()).get("text", ""))
        phrase = self._match(text)
        if phrase is not None:
            self._on_phrase(phrase)

    def _match(self, text: str) -> Phrase | None:
        normalized = _normalize(text)
        for needle, phrase in self._phrases.items():
            if needle in normalized:
                return phrase
        return None

    def start(self) -> None:
        """Open the dedicated 16 kHz input stream and begin recognizing."""
        if self._stream is not None:
            raise RuntimeError("The wake-word detector is already running.")
        self._stream = self._stream_factory(
            sample_rate=self._sample_rate,
            block_size=self._block_size,
            device=self._device,
            on_block=self.feed,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop and close the input stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def _open_input_stream(
    *,
    sample_rate: int,
    block_size: int,
    device: str | None,
    on_block: Callable[[bytes], None],
) -> Any:
    """Build a sounddevice stream that hands raw PCM blocks to the detector."""
    import sounddevice as sd

    def receive_audio(input_data: Any, _frames: int, _time: Any, _status: Any) -> None:
        on_block(bytes(input_data))

    return sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=block_size,
        channels=1,
        dtype="int16",
        device=device,
        callback=receive_audio,
    )
