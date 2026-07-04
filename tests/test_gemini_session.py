"""Regression tests for the Gemini Live receive loop and tool handling.

The key behaviour: Gemini's ``session.receive()`` covers a single turn, so the
session must re-open it for every turn. These tests use fake messages and a fake
session so they need no network, key, or audio hardware.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
from types import SimpleNamespace as NS
from typing import Any

import pytest

from kel.config.settings import Settings
from kel.realtime.gemini_session import GeminiVoiceSession
from kel.realtime.options import RealtimeSessionOptions


class _Stop(Exception):
    """Sentinel used to end the otherwise-infinite receive loop in tests."""


class FakeSpeaker:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue(self, **_kwargs: Any) -> None: ...
    def interrupt(self) -> None:
        return None

    def is_playing(self) -> bool:
        return False


class FakeOrb:
    def __init__(self) -> None:
        self.feelings: list[str] = []

    def set_feeling(self, feeling: str) -> None:
        self.feelings.append(feeling)

    def set_state(self, _state: str) -> None: ...


class FakeBody:
    """A body whose gesture blocks until released, so a test can prove _move
    returns (letting Kel speak) before the servo motion has finished."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.finished = False
        self.release = threading.Event()

    def gesture(self, name: str, pin: int) -> str:
        self.release.wait(timeout=2.0)
        self.calls.append((name, pin))
        self.finished = True
        return f"Did a {name}."


class FakeLiveSession:
    """Hands out one turn's messages per ``receive()`` call, then stops."""

    def __init__(self, turns: list[list[Any]]) -> None:
        self._turns = list(turns)
        self.tool_responses: list[Any] = []
        self.raw_sends: list[str] = []
        # the live session exposes its websocket as ``_ws``; image tool results are
        # posted straight to it because the SDK can't serialize them itself
        self._ws = NS(send=self._ws_send)

    async def _ws_send(self, data: str) -> None:
        self.raw_sends.append(data)

    def receive(self) -> Any:
        if not self._turns:
            raise _Stop
        turn = self._turns.pop(0)

        async def stream() -> Any:
            for message in turn:
                yield message

        return stream()

    async def send_tool_response(self, *, function_responses: Any) -> None:
        self.tool_responses.append(function_responses)

    async def send_realtime_input(self, **_kwargs: Any) -> None: ...


def _msg(**kwargs: Any) -> Any:
    # a Live message always carries these top-level fields (None when unused)
    base = dict(
        tool_call=None,
        server_content=None,
        data=None,
        session_resumption_update=None,
        go_away=None,
    )
    base.update(kwargs)
    return NS(**base)


def _user(text: str) -> Any:
    content = NS(
        interrupted=False,
        input_transcription=NS(text=text),
        output_transcription=None,
        turn_complete=False,
    )
    return _msg(server_content=content)


def _tool(name: str, args: dict[str, Any], call_id: str = "c1") -> Any:
    return _msg(tool_call=NS(function_calls=[NS(id=call_id, name=name, args=args)]))


def _say(text: str) -> Any:
    content = NS(
        interrupted=False,
        input_transcription=None,
        output_transcription=NS(text=text),
        turn_complete=False,
    )
    return _msg(server_content=content, data=b"\x00\x00")


def _done() -> Any:
    content = NS(
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        turn_complete=True,
    )
    return _msg(server_content=content)


def _build_session(
    orb: FakeOrb, on_event: Any, camera: Any = None, body: Any = None, screen: Any = None
) -> GeminiVoiceSession:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "x", "KEL_BODY_ENABLED": "true"})
    options = RealtimeSessionOptions.from_settings(settings)
    return GeminiVoiceSession(
        api_key="x",
        model="gemini-3.1-flash-live-preview",
        voice="Leda",
        instructions="be kel",
        options=options,
        microphone=NS(),
        speaker=FakeSpeaker(),
        on_event=on_event,
        camera=camera,
        screen=screen,
        orb=orb,
        body=body,
    )


def test_receive_loop_processes_every_turn_not_just_the_first() -> None:
    orb = FakeOrb()
    events: list[tuple[str, str]] = []
    session = _build_session(orb, lambda event: events.append((event.kind, event.text)))
    turn_one = [
        _user("I feel sad"),
        _tool("set_feeling", {"feeling": "sad"}),
        _say("I'm here."),
        _done(),
    ]
    turn_two = [
        _user("thanks"),
        _tool("set_feeling", {"feeling": "happy"}),
        _say("Anytime!"),
        _done(),
    ]
    live = FakeLiveSession([turn_one, turn_two])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    transcripts = [text for kind, text in events if kind == "assistant_transcript"]
    assert transcripts == ["I'm here.", "Anytime!"]  # both turns handled, not just the first
    assert orb.feelings == ["sad", "happy"]
    assert len(live.tool_responses) == 2


def test_look_attaches_the_image_inside_the_tool_response_payload() -> None:
    class FakeCamera:
        def capture_jpeg(self) -> bytes:
            return b"FAKEJPEG"

        def close(self) -> None: ...

    orb = FakeOrb()
    session = _build_session(orb, lambda event: None, camera=FakeCamera())
    live = FakeLiveSession([[_tool("look", {}), _say("I see a mug."), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    # An image can't go through send_tool_response (the SDK leaves the bytes raw), so it
    # is posted as a hand-built, base64-encoded wire payload straight to the websocket.
    assert not live.tool_responses  # the normal text path was bypassed
    payload = json.loads(live.raw_sends[0])
    response = payload["toolResponse"]["functionResponses"][0]
    assert response["name"] == "look"
    blob = response["parts"][0]["inlineData"]
    assert blob["mimeType"] == "image/jpeg"
    assert base64.b64decode(blob["data"]) == b"FAKEJPEG"


def test_text_only_tool_results_use_the_normal_send_path() -> None:
    orb = FakeOrb()
    session = _build_session(orb, lambda event: None)
    live = FakeLiveSession([[_tool("set_feeling", {"feeling": "happy"}), _say("Yay!"), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    # No image -> the supported send_tool_response method, no raw socket writes.
    assert not live.raw_sends
    assert live.tool_responses[0][0].name == "set_feeling"


def test_mic_stays_muted_while_speaking_even_after_the_buffer_drains() -> None:
    # Regression: her audio streams in bursts, so mid-sentence the playback buffer empties
    # and is_playing() reads False. If we only muted on is_playing(), the mic would unmute
    # mid-word, feed her own echo back in, and Gemini would cut her off. `_speaking` keeps
    # the mic muted across those gaps.
    orb = FakeOrb()
    session = _build_session(orb, lambda event: None)
    session._speaking = True  # mid-sentence; FakeSpeaker.is_playing() returns False

    class Mic:
        def __init__(self) -> None:
            self.count = 0

        async def read_chunk(self) -> bytes:
            self.count += 1
            if self.count > 4:
                raise _Stop
            return b"\x01\x02"

    class Capturing:
        def __init__(self) -> None:
            self.audio_sends = 0

        async def send_realtime_input(self, **kwargs: Any) -> None:
            if "audio" in kwargs:
                self.audio_sends += 1

    session._microphone = Mic()
    connection = Capturing()
    with pytest.raises(_Stop):
        asyncio.run(session._send_microphone(connection))

    assert connection.audio_sends == 0  # never forwarded the mic while she was speaking


def test_one_bad_message_does_not_end_the_conversation() -> None:
    orb = FakeOrb()
    events: list[tuple[str, str]] = []
    session = _build_session(orb, lambda event: events.append((event.kind, event.text)))
    broken = NS()  # missing attributes -> raises inside _handle_message
    live = FakeLiveSession([[broken, _user("hi"), _say("Hello!"), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    assert any(kind == "error" for kind, _ in events)
    assert ("assistant_transcript", "Hello!") in events  # survived the bad message


class _FakeScreen:
    def __init__(self, jpeg: bytes = b"SCREENSHOT") -> None:
        self._jpeg = jpeg

    def capture_jpeg(self) -> bytes:
        return self._jpeg


def test_see_screen_attaches_a_screenshot_when_a_screen_is_present() -> None:
    session = _build_session(FakeOrb(), lambda _event: None, screen=_FakeScreen(b"IMG"))

    text, image = asyncio.run(session._see_screen())

    assert image == b"IMG"  # the screenshot is attached for the model to read
    assert "screen" in text.lower()


def test_see_screen_degrades_cleanly_with_no_screen() -> None:
    session = _build_session(FakeOrb(), lambda _event: None)  # no screen configured

    text, image = asyncio.run(session._see_screen())

    assert image is None  # nothing attached
    assert "can't see the screen" in text.lower()  # she says so instead of crashing


def test_move_lets_kel_speak_while_the_servo_is_still_moving() -> None:
    """The move tool must not block on the gesture; motion runs in the background so
    it overlaps speech instead of finishing before she says a word."""
    orb = FakeOrb()
    body = FakeBody()
    session = _build_session(orb, lambda _event: None, body=body)

    async def scenario() -> None:
        summary = await session._move("nod")
        # _move returned even though the gesture is still blocked (release not set),
        # so Kel is free to start talking while the servo keeps moving.
        assert body.finished is False
        assert "nod" in summary.lower()

        # Let the background gesture finish and confirm it actually ran with our args.
        body.release.set()
        for _ in range(200):
            if body.finished:
                break
            await asyncio.sleep(0.005)
        assert body.finished is True
        assert body.calls == [("nod", 9)]

    asyncio.run(scenario())
