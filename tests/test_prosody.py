"""The prosody reader turns loud/quiet/high-pitch voice into tone cues."""

from __future__ import annotations

import numpy as np

from kel.realtime.prosody import ProsodyReader

SR = 16_000
FRAME = SR * 20 // 1000  # 20 ms chunks, like the live mic


def _tone(freq: float, amp: float, frames: int = 1) -> bytes:
    n = FRAME * frames
    t = np.arange(n) / SR
    wave = np.sin(2 * np.pi * freq * t) * amp
    return (wave * 32767).astype(np.int16).tobytes()


def _calibrate(reader: ProsodyReader) -> None:
    # establish a "normal voice" baseline: moderate level, ~150 Hz
    for _ in range(40):
        reader.add(_tone(150, 0.12))


def test_silence_gives_no_cue() -> None:
    reader = ProsodyReader(SR)
    for _ in range(20):
        assert reader.add(_tone(150, 0.0005)) is None


def _labels(reader: ProsodyReader, freq: float, amp: float, frames: int = 25) -> list[str]:
    return [label for _ in range(frames) if (label := reader.add(_tone(freq, amp)))]


def test_loud_voice_reads_as_forceful_or_excited() -> None:
    reader = ProsodyReader(SR)
    _calibrate(reader)
    labels = _labels(reader, 150, 0.55)
    assert any("loud" in label or "excited" in label or "animated" in label for label in labels)


def test_quiet_voice_reads_as_subdued() -> None:
    reader = ProsodyReader(SR)
    _calibrate(reader)
    labels = _labels(reader, 150, 0.03)
    assert any("subdued" in label or "flat" in label for label in labels)


def test_high_pitch_loud_reads_as_excited() -> None:
    reader = ProsodyReader(SR)
    _calibrate(reader)
    labels = _labels(reader, 320, 0.55)
    assert "sounds excited and animated" in labels
