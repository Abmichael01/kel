"""GrimScreen — tested with an injected runner, so no real display is touched."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from kel.vision.screen import GrimScreen, ScreenError


def _png(width: int, height: int) -> bytes:
    """A valid PNG of the given size, standing in for grim's output."""
    encoded, buffer = cv2.imencode(".png", np.zeros((height, width, 3), dtype=np.uint8))
    assert encoded
    return buffer.tobytes()


def _decoded(jpeg: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)


def test_capture_returns_decodable_jpeg() -> None:
    screen = GrimScreen(run=lambda _argv: _png(800, 600))

    data = screen.capture_jpeg()

    assert data[:2] == b"\xff\xd8"  # JPEG start-of-image marker
    assert _decoded(data) is not None


def test_wide_capture_is_downscaled_to_max_width() -> None:
    screen = GrimScreen(max_width=640, run=lambda _argv: _png(1920, 1080))

    assert _decoded(screen.capture_jpeg()).shape[1] == 640


def test_small_capture_is_not_upscaled() -> None:
    screen = GrimScreen(max_width=1280, run=lambda _argv: _png(800, 600))

    assert _decoded(screen.capture_jpeg()).shape[1] == 800


def test_it_shells_out_to_grim() -> None:
    seen: dict[str, list[str]] = {}

    def fake_run(argv: list[str]) -> bytes:
        seen["argv"] = argv
        return _png(100, 100)

    GrimScreen(run=fake_run).capture_jpeg()

    assert seen["argv"][0] == "grim"


def test_empty_capture_raises() -> None:
    with pytest.raises(ScreenError):
        GrimScreen(run=lambda _argv: b"").capture_jpeg()


def test_undecodable_capture_raises() -> None:
    with pytest.raises(ScreenError):
        GrimScreen(run=lambda _argv: b"not an image").capture_jpeg()
