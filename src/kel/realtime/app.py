"""Construct the concrete components used by Kel's realtime interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from kel.config.settings import Settings
from kel.prompts.kel_personality import build_kel_realtime_instructions
from kel.realtime.audio import StreamingMicrophone, StreamingSpeaker
from kel.realtime.events import RealtimeDisplayEvent
from kel.realtime.options import RealtimeSessionOptions
from kel.realtime.session import RealtimeVoiceSession

if TYPE_CHECKING:
    from kel.realtime.gemini_session import GeminiVoiceSession


def build_realtime_session(
    settings: Settings,
    *,
    on_event: Callable[[RealtimeDisplayEvent], None],
    body: object | None = None,
    orb: object | None = None,
) -> RealtimeVoiceSession | GeminiVoiceSession:
    """Create live audio I/O and the persistent Realtime API session.

    If ``body`` is supplied (the wake orchestrator owns one for the whole run so it
    can glow while asleep), this session uses it and does NOT close it. Otherwise,
    when the body is enabled, this session opens and owns its own.
    """
    options = RealtimeSessionOptions.from_settings(settings)
    provider = settings.realtime_provider
    if provider == "gemini":
        from kel.realtime.gemini_session import GEMINI_INPUT_RATE, GEMINI_OUTPUT_RATE

        input_rate, output_rate = GEMINI_INPUT_RATE, GEMINI_OUTPUT_RATE
    else:
        input_rate = output_rate = options.sample_rate
    microphone = StreamingMicrophone(
        sample_rate=input_rate,
        device=settings.audio_input_device,
    )
    speaker = StreamingSpeaker(
        sample_rate=output_rate,
        device=settings.audio_output_device,
    )
    camera = None
    if settings.vision_enabled:
        from kel.vision.camera import OpenCVCamera

        camera = OpenCVCamera(
            device_index=settings.camera_device_index,
            max_width=settings.vision_image_max_width,
        )
    screen = None
    if settings.screen_enabled:
        from kel.vision.screen import GrimScreen

        screen = GrimScreen(max_width=settings.screen_max_width)
    memory = None
    if settings.memory_enabled and not settings.openai_api_key:
        # Long-term memory currently embeds through OpenAI, so without that key she simply
        # runs without memory rather than failing to start (fine for a Gemini-only setup).
        print("Long-term memory is off (needs an OpenAI key for embeddings); continuing.")
    elif settings.memory_enabled:
        from pathlib import Path

        from openai import OpenAI

        from kel.memory.openai_embedder import OpenAIEmbedder
        from kel.memory.store import MemoryStore

        embedder = OpenAIEmbedder(
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.embedding_model,
        )
        memory = MemoryStore(
            embedder=embedder,
            path=Path(settings.memory_path),
            top_k=settings.memory_top_k,
        )
    browser = None
    if settings.browser_enabled:
        from kel.system.browser import Browser

        browser = Browser()
    shell = None
    launcher = None
    keyboard = None
    if settings.shell_enabled:
        from kel.system.keyboard import Keyboard
        from kel.system.launcher import TerminalLauncher
        from kel.system.shell import ShellRunner

        shell = ShellRunner(
            timeout=settings.shell_timeout_seconds,
            block_dangerous=settings.shell_block_dangerous,
        )
        launcher = TerminalLauncher(
            terminal=settings.terminal_command,
            block_dangerous=settings.shell_block_dangerous,
        )
        keyboard = Keyboard(tool=settings.keyboard_tool)
    echo_canceller = None
    if settings.realtime_echo_cancel:
        from kel.realtime.echo_cancel import PulseEchoCanceller

        echo_canceller = PulseEchoCanceller()
    close_body = False
    if body is None and settings.body_enabled:
        from kel.body.controller import BodyController
        from kel.body.serial_link import SerialLink, find_port

        port = settings.body_port or find_port()
        if port:
            try:
                body = BodyController(SerialLink.open(port))
                close_body = True
            except Exception as error:  # noqa: BLE001 - body is optional; degrade gracefully
                print(f"Body not connected ({error}); continuing without it.")
    from kel.system.environment import describe_environment

    skills = None
    if settings.skills_enabled:
        from pathlib import Path

        from kel.realtime.options import BUILTIN_TOOL_NAMES
        from kel.skills.store import SkillStore

        skills = SkillStore(
            Path(settings.skills_path).expanduser(),
            reserved_names=BUILTIN_TOOL_NAMES,
        )

    from kel.skills.authoring.app import build_author

    author = build_author(settings)

    shared: dict[str, object | None] = dict(
        instructions=build_kel_realtime_instructions(
            settings.robot_name, environment=describe_environment()
        ),
        options=options,
        microphone=microphone,
        speaker=speaker,
        on_event=on_event,
        half_duplex=settings.realtime_half_duplex,
        camera=camera,
        screen=screen,
        memory=memory,
        auto_capture_memory=settings.memory_auto_capture,
        browser=browser,
        shell=shell,
        launcher=launcher,
        keyboard=keyboard,
        echo_canceller=echo_canceller,
        body=body,
        body_servo_pin=settings.body_servo_pin,
        close_body=close_body,
        orb=orb,
        skills=skills,
        skills_timeout=settings.skills_timeout_seconds,
        author=author,
    )
    if provider == "gemini":
        if not settings.gemini_api_key:
            from kel.config.settings import ConfigurationError

            raise ConfigurationError(
                "KEL_REALTIME_PROVIDER=gemini needs a Google AI Studio key. Get a free one "
                "at https://aistudio.google.com/apikey and set GEMINI_API_KEY in your .env."
            )
        from kel.realtime.gemini_session import GeminiVoiceSession

        return GeminiVoiceSession(
            api_key=settings.gemini_api_key,
            model=settings.gemini_realtime_model,
            voice=settings.gemini_voice,
            affective_dialog=settings.gemini_affective_dialog,
            tone_cues=settings.tone_cues_enabled,
            **shared,
        )
    return RealtimeVoiceSession(api_key=settings.openai_api_key, **shared)
