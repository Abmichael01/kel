"""A tiny local read of HOW the user sounds, from their microphone audio.

The half-cascade live model only sees the user's words (a transcript), so it is deaf
to intonation. This estimates loudness and pitch from the raw mic PCM, relative to the
user's own running baseline, and turns a notable change into a short cue like
"sounds quiet and subdued" - which the session feeds to the model so it can sense the
user's mood. It is deliberately rough (DSP, no model, no network, no cost); the model
combines this *arousal* hint with the *words* to read the real emotion.
"""

from __future__ import annotations

import numpy as np


class ProsodyReader:
    """Estimate the speaker's vocal energy/pitch and label notable shifts."""

    def __init__(self, sample_rate: int = 16_000, window_ms: int = 350) -> None:
        self._sr = sample_rate
        self._win = sample_rate * window_ms // 1000
        self._buf = np.zeros(0, dtype=np.float32)
        self._energy_base: float | None = None
        self._pitch_base: float = 0.0
        # Adapt the baseline slowly (~seconds) so a single utterance's shift stays
        # "notable" instead of the baseline catching up within the same breath.
        self._alpha = 0.008

    def add(self, pcm: bytes) -> str | None:
        """Feed one mic chunk; return a tone cue when the voice notably shifts."""
        chunk = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        self._buf = np.concatenate([self._buf, chunk])[-self._win:]
        if len(self._buf) < self._win * 0.6:
            return None

        energy = float(np.sqrt(np.mean(self._buf**2)))
        if energy < 0.012:  # silence / not really voiced
            return None
        pitch = self._pitch(self._buf)

        if self._energy_base is None:  # first voiced frame calibrates the baseline
            self._energy_base = energy
            self._pitch_base = pitch or 150.0
            return None
        self._energy_base = (1 - self._alpha) * self._energy_base + self._alpha * energy
        if pitch > 0:
            self._pitch_base = (1 - self._alpha) * self._pitch_base + self._alpha * pitch
        return self._label(energy, pitch)

    def _pitch(self, samples: np.ndarray) -> float:
        """Dominant voice pitch via FFT autocorrelation (fast), or 0 if unclear."""
        windowed = samples * np.hanning(len(samples))
        spectrum = np.fft.rfft(windowed)
        corr = np.fft.irfft(spectrum * np.conj(spectrum))
        lo, hi = self._sr // 350, self._sr // 80  # human F0 ~ 80-350 Hz
        region = corr[lo:hi]
        if len(region) == 0 or float(region.max()) <= 0:
            return 0.0
        return self._sr / (int(np.argmax(region)) + lo)

    def _label(self, energy: float, pitch: float) -> str | None:
        e = energy / max(self._energy_base or 1e-6, 1e-6)
        p = pitch / max(self._pitch_base, 1e-6) if pitch > 0 else 1.0
        if e > 1.5 and p > 1.15:
            return "sounds excited and animated"
        if e > 1.5:
            return "sounds loud and forceful"
        if e < 0.55:
            return "sounds quiet and subdued"
        if p > 1.3:
            return "sounds animated and lively"
        if p < 0.8 and e < 0.85:
            return "sounds low and flat"
        return None
