"""Wire the local wake-word gate in front of the realtime voice session.

Heavy, optional dependencies (Porcupine, sounddevice, the realtime stack) are
imported lazily inside the builders so this module stays importable for tests.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from kel.config.settings import ConfigurationError, Settings
from kel.wake.announcer import SpokenAnnouncer
from kel.wake.contracts import Phrase, SleepReason
from kel.wake.gate import AttentionGate
from kel.wake.porcupine_detector import PorcupineWakeWordDetector
from kel.wake.vosk_detector import VoskWakeWordDetector


def _vosk_phrases(settings: Settings) -> dict[str, Phrase]:
    """Map the trigger phrases to gate actions.

    Calling her name wakes her into a full conversation. The name is added LAST so
    it only matches when no sleep phrase did (e.g. "kel at ease" still sleeps).
    """
    mapping = {phrase: Phrase.PAY_ATTENTION for phrase in settings.wake_phrases_wake}
    mapping.update({phrase: Phrase.AT_EASE for phrase in settings.wake_phrases_sleep})
    mapping[settings.robot_name.lower()] = Phrase.PAY_ATTENTION
    return mapping


def _vosk_grammar(settings: Settings) -> str:
    """Tell Vosk exactly which "Kel ..." phrases to listen for, plus a catch-all."""
    name = settings.robot_name.lower()
    phrases = [*settings.wake_phrases_wake, *settings.wake_phrases_sleep]
    entries = [f"{name} {phrase}" for phrase in phrases] + [name, "[unk]"]
    return json.dumps(entries)


class Announcer(Protocol):
    def greet(self) -> None: ...
    def farewell(self) -> None: ...


class SessionController(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


def validate_wake_settings(settings: Settings) -> None:
    """Fail fast with an actionable message when the gate is misconfigured."""
    if not settings.wake_enabled:
        return
    if settings.wake_backend == "vosk":
        if not settings.wake_vosk_model_path:
            raise ConfigurationError(
                "KEL_WAKE_VOSK_MODEL_PATH is missing. Download a free Vosk model (no "
                "account needed) from alphacephei.com/vosk/models, unzip it, and point "
                "KEL_WAKE_VOSK_MODEL_PATH at the folder."
            )
        return
    if not settings.wake_access_key:
        raise ConfigurationError(
            "KEL_WAKE_ACCESS_KEY is missing. Create a free Picovoice access key, add it "
            "to .env, or set KEL_WAKE_BACKEND=vosk to use the no-account wake word."
        )
    if not (settings.wake_keyword_attention_path and settings.wake_keyword_at_ease_path):
        raise ConfigurationError(
            "KEL_WAKE_KEYWORD_ATTENTION_PATH and KEL_WAKE_KEYWORD_AT_EASE_PATH must point "
            "to the .ppn keyword files you downloaded from the Picovoice Console."
        )


def build_attention_gate(
    settings: Settings,
    *,
    announcer: Announcer,
    session_controller: SessionController,
    clock: Callable[[], float] = time.monotonic,
) -> AttentionGate:
    """Connect the pure state machine to spoken feedback and session control."""

    def on_wake() -> None:
        announcer.greet()
        session_controller.start()

    def on_sleep(reason: SleepReason) -> None:
        session_controller.stop()
        # Only acknowledge an explicit sleep; a quiet auto-sleep stays silent.
        if reason is SleepReason.AT_EASE:
            announcer.farewell()

    return AttentionGate(
        auto_sleep_seconds=settings.wake_auto_sleep_seconds,
        quick_sleep_seconds=settings.wake_quick_sleep_seconds,
        on_wake=on_wake,
        on_sleep=on_sleep,
        clock=clock,
    )


def build_announcer(settings: Settings, *, client: Any | None = None) -> SpokenAnnouncer:
    """Build the spoken acknowledgement from the existing TTS and speaker."""
    from openai import OpenAI

    from kel.voice.openai_speech import OpenAISpeechGenerator
    from kel.voice.speaker import SoundDeviceSpeaker

    client = client or OpenAI(api_key=settings.openai_api_key)
    speech = OpenAISpeechGenerator(
        client=client,
        model=settings.speech_model,
        voice=settings.speech_voice,
    )
    player = SoundDeviceSpeaker(device=settings.audio_output_device)
    return SpokenAnnouncer(
        speech_generator=speech,
        player=player,
        greeting=settings.wake_greeting,
        farewell=settings.wake_farewell,
    )


def create_porcupine_engine(settings: Settings, *, create: Callable[..., Any] | None = None) -> Any:
    """Create a Porcupine handle for the two custom trigger phrases."""
    validate_wake_settings(settings)
    if create is None:
        import pvporcupine

        create = pvporcupine.create
    return create(
        access_key=settings.wake_access_key,
        keyword_paths=[
            settings.wake_keyword_attention_path,
            settings.wake_keyword_at_ease_path,
        ],
        sensitivities=[settings.wake_sensitivity, settings.wake_sensitivity],
    )


def create_vosk_recognizer(
    settings: Settings,
    *,
    model_factory: Callable[..., Any] | None = None,
    recognizer_factory: Callable[..., Any] | None = None,
) -> Any:
    """Load a Vosk model and build a recognizer constrained to the trigger phrases."""
    validate_wake_settings(settings)
    if model_factory is None or recognizer_factory is None:
        from vosk import KaldiRecognizer, Model

        model_factory = model_factory or Model
        recognizer_factory = recognizer_factory or KaldiRecognizer
    model = model_factory(settings.wake_vosk_model_path)
    return recognizer_factory(model, 16_000, _vosk_grammar(settings))


def build_detector(
    settings: Settings,
    on_phrase: Callable[[Phrase], None],
    *,
    engine: Any | None = None,
    recognizer: Any | None = None,
) -> PorcupineWakeWordDetector | VoskWakeWordDetector:
    """Build the configured backend's local detector."""
    if settings.wake_backend == "vosk":
        recognizer = recognizer if recognizer is not None else create_vosk_recognizer(settings)
        return VoskWakeWordDetector(
            recognizer=recognizer,
            phrases=_vosk_phrases(settings),
            on_phrase=on_phrase,
            device=settings.audio_input_device,
        )
    engine = engine if engine is not None else create_porcupine_engine(settings)
    return PorcupineWakeWordDetector(
        engine=engine,
        phrases=(Phrase.PAY_ATTENTION, Phrase.AT_EASE),
        on_phrase=on_phrase,
        device=settings.audio_input_device,
    )


class _BackgroundAnnouncer:
    """Play acknowledgements off the event loop.

    The spoken clip plays in a worker thread so the asyncio loop stays free to
    open the realtime connection at the same time. That way the connection is
    already warming up while "I'm listening" is still playing, instead of only
    starting once the greeting finishes.
    """

    def __init__(self, inner: SpokenAnnouncer, loop: asyncio.AbstractEventLoop) -> None:
        self._inner = inner
        self._loop = loop

    def greet(self) -> None:
        self._loop.run_in_executor(None, self._inner.greet)

    def farewell(self) -> None:
        self._loop.run_in_executor(None, self._inner.farewell)


class AsyncSessionController:
    """Run one realtime session as a cancellable task while Kel is awake."""

    def __init__(self, *, run_session: Callable[[], Awaitable[None]]) -> None:
        self._run_session = run_session
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._guarded())

    def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()

    async def _guarded(self) -> None:
        # Cancellation is the normal "go back to sleep" signal, so swallow it.
        with contextlib.suppress(asyncio.CancelledError):
            await self._run_session()


class _GlowSessionController:
    """Wrap the session controller so the orb wakes to 'listening' and sleeps."""

    def __init__(self, inner: SessionController, orb: Any) -> None:
        self._inner = inner
        self._orb = orb

    def start(self) -> None:
        self._orb.set_state("listening")
        self._inner.start()

    def stop(self) -> None:
        self._inner.stop()
        self._orb.sleep()


def _open_body(settings: Settings) -> Any:
    """Open the body for the whole run (so it can glow while asleep), or None.

    Prints a loud status line either way: if the body fails to open, Kel can still
    talk but her LED orb and LCD face will be frozen on the Arduino's power-on
    (sleeping) look, so it must be obvious when that happens.
    """
    if not settings.body_enabled:
        return None
    from kel.body.controller import BodyController
    from kel.body.serial_link import SerialLink, find_port

    port = settings.body_port or find_port()
    if not port:
        print("Body: no Arduino serial port found — her face and orb stay off.")
        return None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            body = BodyController(SerialLink.open(port))
        except Exception as error:  # noqa: BLE001 - body is optional; degrade gracefully
            last_error = error
            if attempt == 0:
                time.sleep(1.0)  # the port may be briefly busy right after a reset
            continue
        # Opening the port resets the Arduino: wait for it to boot, then confirm with
        # a ping so we don't start firing mood commands into a rebooting board.
        time.sleep(2.0)
        reply = ""
        with contextlib.suppress(Exception):
            reply = body.ping()
        if "pong" in reply.lower():
            print(f"Body: connected on {port} — face + orb are LIVE.")
        else:
            print(f"Body: opened {port} but it hasn't answered yet; the face should catch up.")
        return body
    print(
        f"Body: NOT connected ({last_error}). She'll still talk, but her face/orb will be "
        f"frozen asleep. Check the USB cable and that {port} is accessible."
    )
    return None


def _open_face(settings: Settings) -> tuple[Any, Any]:
    """Open the on-screen face (optionally launching its window), or (None, None)."""
    if not settings.face_enabled:
        return None, None
    import subprocess
    import sys

    from kel.face.client import ScreenFace

    proc = None
    if settings.face_autostart:
        try:
            command = [sys.executable, "-m", "kel.face.app",
                       "--host", settings.face_host, "--port", str(settings.face_port)]
            if settings.face_fullscreen:
                command.append("--fullscreen")
            proc = subprocess.Popen(command)
            print("Face: opening the on-screen face window.")
        except Exception as error:  # noqa: BLE001 - the face is optional; degrade gracefully
            print(f"Face: couldn't open the window ({error}); you can run 'kel-face' yourself.")
    return ScreenFace(settings.face_host, settings.face_port), proc


async def run_realtime_with_gate(settings: Settings, *, poll_interval: float = 0.5) -> None:
    """Run realtime mode behind the local attention gate."""
    from kel.body.orb import BodyOrb
    from kel.interfaces.realtime_cli import RealtimeTerminalDisplay
    from kel.realtime.app import build_realtime_session

    validate_wake_settings(settings)
    loop = asyncio.get_running_loop()
    display = RealtimeTerminalDisplay(robot_name=settings.robot_name)
    announcer = build_announcer(settings)
    announcer.prepare()
    background_announcer = _BackgroundAnnouncer(announcer, loop)

    # The body is opened once for the whole run so the orb can animate even while
    # asleep. The orb continuously flows each mood's palette of colours.
    body = _open_body(settings)
    face, face_proc = _open_face(settings)
    orb = BodyOrb(body, face=face)
    orb.start()  # begins animating "sleeping" (a slow red breath)

    def on_event(event: Any) -> None:
        display.show(event)
        kind = event.kind
        if kind == "speech_started":
            gate.note_user_speech()
            orb.set_state("listening")
        elif kind == "speech_stopped":
            orb.set_state("thinking")
        elif kind == "type_mode":
            orb.set_state("typing")
        elif kind == "assistant_transcript":
            orb.set_state("listening")
        elif kind == "assistant_speaking" and face is not None:
            face.set_speaking(True)
        elif kind == "assistant_done" and face is not None:
            face.set_speaking(False)

    async def run_session() -> None:
        session = build_realtime_session(settings, on_event=on_event, body=body, orb=orb)
        await session.run()

    controller = AsyncSessionController(run_session=run_session)
    glow_controller = _GlowSessionController(controller, orb)
    gate = build_attention_gate(
        settings, announcer=background_announcer, session_controller=glow_controller
    )
    detector = build_detector(
        settings,
        lambda phrase: loop.call_soon_threadsafe(gate.handle_phrase, phrase),
    )

    name = settings.robot_name
    print(f"{name} realtime voice mode (wake word on)")
    print(f"Disclosure: {name}'s voice is AI-generated, not human.")
    print("Use headphones to prevent speaker echo. Press Ctrl+C to stop.")
    print(f'[Asleep] Say "{name}, pay attention" to wake me.')

    detector.start()
    try:
        while True:
            await asyncio.sleep(poll_interval)
            gate.check_timeout()
    finally:
        controller.stop()
        detector.stop()
        orb.stop()
        if face is not None:
            face.close()
        if face_proc is not None:
            with contextlib.suppress(Exception):
                face_proc.terminate()
        if body is not None:
            with contextlib.suppress(Exception):
                body.close()
