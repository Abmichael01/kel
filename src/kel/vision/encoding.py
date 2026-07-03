"""Turn an encoded camera frame into the data URL the Realtime API accepts."""

from __future__ import annotations

import base64


def jpeg_to_data_url(jpeg: bytes) -> str:
    """Wrap JPEG bytes as a base64 ``data:`` URL for an input_image item."""
    encoded = base64.b64encode(jpeg).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
