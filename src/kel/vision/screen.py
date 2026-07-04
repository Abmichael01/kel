"""Capture a single screenshot on demand, mirroring the camera's `look`.

Kel calls this when a question is about what is on the user's screen. It grabs the
screen with `grim` (Wayland/wlroots), downscales it, and returns JPEG bytes — the
same shape the camera returns — so the rest of the vision plumbing is unchanged.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any, Protocol


class ScreenError(RuntimeError):
    """Raised when a screenshot cannot be captured or encoded."""


class Screen(Protocol):
    """Provide one encoded screenshot when Kel decides to see the screen."""

    def capture_jpeg(self) -> bytes:
        """Return a single fresh screenshot as JPEG bytes."""
        ...


def _run_grim(argv: list[str]) -> bytes:
    """Run grim and return its raw image bytes on stdout."""
    try:
        result = subprocess.run(argv, capture_output=True, timeout=6)
    except FileNotFoundError as error:
        raise ScreenError("grim is not installed (needed to capture the screen).") from error
    except subprocess.SubprocessError as error:
        raise ScreenError(f"the screenshot command failed ({error}).") from error
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or "grim returned an error"
        raise ScreenError(detail[:200])
    return result.stdout


class GrimScreen:
    """Grab one screenshot with grim, downscaled and JPEG-encoded for the model."""

    def __init__(
        self,
        *,
        max_width: int = 1280,
        jpeg_quality: int = 75,
        run: Callable[[list[str]], bytes] = _run_grim,
    ) -> None:
        self._max_width = max_width
        self._jpeg_quality = jpeg_quality
        self._run = run  # injectable so tests never touch a real display

    def capture_jpeg(self) -> bytes:
        """Take a screenshot, shrink it if wide, and return JPEG bytes."""
        import cv2
        import numpy as np

        raw = self._run(["grim", "-t", "png", "-"])
        if not raw:
            raise ScreenError("the screenshot was empty.")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ScreenError("the screenshot could not be decoded.")

        image = self._downscale(cv2, image)
        encoded, buffer = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        )
        if not encoded:
            raise ScreenError("the screenshot could not be JPEG-encoded.")
        return buffer.tobytes()

    def _downscale(self, cv2: Any, image: Any) -> Any:
        """Shrink wide screenshots so they stay affordable to send, keeping text legible."""
        height, width = image.shape[:2]
        if width <= self._max_width:
            return image
        scale = self._max_width / width
        return cv2.resize(image, (self._max_width, int(height * scale)))
