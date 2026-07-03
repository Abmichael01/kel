"""Capture a single still frame from a local camera, on demand.

The camera opens on the first look and stays warm for the rest of the awake
session, so later looks are instant instead of paying the slow device-open cost
every time. It is released when the session ends (Kel goes back to sleep).
"""

from __future__ import annotations

import contextlib
from typing import Any, Protocol


class CameraError(RuntimeError):
    """Raised when a frame cannot be captured from the camera."""


class Camera(Protocol):
    """Provide one encoded still image when Kel decides to look."""

    def capture_jpeg(self) -> bytes:
        """Return a single fresh frame as JPEG bytes."""
        ...

    def close(self) -> None:
        """Release the camera device."""
        ...


class OpenCVCamera:
    """Grab one JPEG frame from a local webcam using OpenCV, kept warm."""

    def __init__(
        self,
        *,
        device_index: int = 0,
        max_width: int = 768,
        jpeg_quality: int = 70,
        flush_frames: int = 2,
    ) -> None:
        self._device_index = device_index
        self._max_width = max_width
        self._jpeg_quality = jpeg_quality
        self._flush_frames = flush_frames
        self._capture: Any | None = None

    def capture_jpeg(self) -> bytes:
        """Read the latest frame from the warm camera, downscale, JPEG-encode."""
        import cv2

        frame = self._read_fresh(self._ensure_open(cv2))
        if frame is None:
            # The device may have dropped; reopen once before giving up.
            self.close()
            frame = self._read_fresh(self._ensure_open(cv2))
        if frame is None:
            raise CameraError("The camera did not return a frame.")

        frame = self._downscale(cv2, frame)
        encoded, buffer = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        )
        if not encoded:
            raise CameraError("The frame could not be JPEG-encoded.")
        return buffer.tobytes()

    def close(self) -> None:
        """Release the camera device if it is open."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _ensure_open(self, cv2: Any) -> Any:
        if self._capture is None:
            capture = cv2.VideoCapture(self._device_index)
            if not capture.isOpened():
                capture.release()
                raise CameraError(f"Could not open camera {self._device_index}.")
            with contextlib.suppress(Exception):
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._capture = capture
        return self._capture

    def _read_fresh(self, capture: Any) -> Any:
        """Read a few frames so a stale buffered frame can't be returned."""
        frame = None
        for _ in range(self._flush_frames + 1):
            ok, candidate = capture.read()
            if ok and candidate is not None:
                frame = candidate
        return frame

    def _downscale(self, cv2: Any, frame: Any) -> Any:
        """Shrink wide frames so the image stays small and cheap to send."""
        height, width = frame.shape[:2]
        if width <= self._max_width:
            return frame
        scale = self._max_width / width
        return cv2.resize(frame, (self._max_width, int(height * scale)))
