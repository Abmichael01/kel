"""Camera frames become the data URL the Realtime API expects."""

from __future__ import annotations

import base64

from kel.vision.encoding import jpeg_to_data_url


def test_jpeg_bytes_become_a_base64_data_url() -> None:
    url = jpeg_to_data_url(b"\xff\xd8\xfffake-jpeg")

    assert url.startswith("data:image/jpeg;base64,")
    payload = url.split(",", 1)[1]
    assert base64.b64decode(payload) == b"\xff\xd8\xfffake-jpeg"
