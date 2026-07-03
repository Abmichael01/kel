"""The screen-face client speaks the face's line protocol over a socket."""

from __future__ import annotations

import os
import socket
import threading
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402 - the dummy driver must be set before pygame loads

from kel.config.settings import Settings  # noqa: E402
from kel.face.client import ScreenFace  # noqa: E402
from kel.face.screen import EYE_COLOR, FaceRenderer  # noqa: E402


def _settled_face(mood: str, *, talk: float = 0.0, speaking: bool = False) -> FaceRenderer:
    """A face fully morphed into a mood (eased params at their targets), ready to paint."""
    pygame.init()
    face = FaceRenderer(width=200, height=200)
    face.set_mood(mood)
    face.set_speaking(speaking)
    face._talk = talk
    for eased in face._m.values():
        eased.value = eased.target
    return face


def _center_mouth_y(mood: str) -> float:
    """Paint a talking face and return the mean y of the mouth's centre column."""
    face = _settled_face(mood, talk=0.8, speaking=True)
    surf = pygame.Surface((200, 200))
    face.draw(surf)
    ys = [y for y in range(120, 200) for x in range(96, 105)
          if tuple(surf.get_at((x, y)))[:3] == EYE_COLOR]
    assert ys, f"talking {mood} mouth drew nothing"
    return sum(ys) / len(ys)


def _collect(server: socket.socket, lines: list[str], want: int) -> None:
    server.settimeout(3.0)
    try:
        conn, _ = server.accept()
    except OSError:
        return
    with conn:
        conn.settimeout(3.0)
        buffer = b""
        while len(lines) < want:
            try:
                chunk = conn.recv(1024)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if line:
                    lines.append(line.decode())


def test_screen_face_sends_mode_and_speak_lines() -> None:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    received: list[str] = []
    listener = threading.Thread(target=_collect, args=(server, received, 2))
    listener.start()

    face = ScreenFace("127.0.0.1", port)
    face.set_mood("happy")
    face.set_speaking(True)

    listener.join(timeout=4.0)
    face.close()
    server.close()

    assert "mode happy" in received
    assert "speak 1" in received


def test_face_settings_default_off_but_configurable() -> None:
    off = Settings.from_mapping({"OPENAI_API_KEY": "x"})
    assert off.face_enabled is False
    assert off.face_port == 8765
    assert off.face_autostart is True

    on = Settings.from_mapping(
        {"OPENAI_API_KEY": "x", "KEL_FACE_ENABLED": "true", "KEL_FACE_PORT": "9100"}
    )
    assert on.face_enabled is True
    assert on.face_port == 9100


def test_talking_mouth_keeps_the_mood_curve() -> None:
    # A happy mouth curves up (its centre dips lower on screen) while a sad mouth curves
    # down (centre rides higher) - even while talking, so she never smiles through bad news.
    happy = _center_mouth_y("happy")
    flat = _center_mouth_y("normal")
    sad = _center_mouth_y("sad")
    assert happy > flat > sad


def test_mouth_morphs_between_moods_instead_of_swapping() -> None:
    # Mid-transition the mouth's curve sits partway between the two moods - proof it bends
    # from one into the other rather than one shape hiding and another popping in.
    face = _settled_face("happy")          # bow at the smile target
    smile_bow = face._m["bow"].value
    face.set_mood("sad")                   # retarget to a frown, then step once
    face.update(1 / 60)
    mid_bow = face._m["bow"].value
    assert smile_bow > mid_bow > face._m["bow"].target  # smile -> ... -> frown, continuously


def test_screen_face_never_blocks_when_window_is_absent() -> None:
    # Nothing is listening on this port; calls must return immediately, not hang.
    face = ScreenFace("127.0.0.1", 59999)
    start = time.monotonic()
    face.set_mood("listening")
    face.set_speaking(True)
    face.close()
    assert time.monotonic() - start < 1.0
