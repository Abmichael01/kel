"""The pure logic of first-run setup: turn answers into a complete .env file.

This module has NO input(), no filesystem, and no network so it is trivially
testable. `cli.py` gathers the answers interactively and does the actual I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

FREE_GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


@dataclass(frozen=True, slots=True)
class Answers:
    """Everything the wizard needs to write a working configuration."""

    gemini_api_key: str
    openai_api_key: str = ""
    robot_name: str = "Kel"
    audio_input_device: str = ""
    audio_output_device: str = ""
    wake_enabled: bool = False
    wake_model_path: str = ""
    screen_enabled: bool = False
    body_enabled: bool = False
    body_port: str = ""
    shell_enabled: bool = False
    face_enabled: bool = True


def _b(value: bool) -> str:
    return "true" if value else "false"


def build_env_text(a: Answers) -> str:
    """Render a complete, ready-to-run .env from the wizard's answers.

    Pure function: given the same answers it always returns the same text, so the
    whole configuration step can be unit-tested without prompts or files.
    """
    lines = [
        "# Written by `kel-setup`. Holds your private keys - never commit this file.",
        "",
        "# Her brain: Gemini Live (free key, cheaper audio).",
        "KEL_REALTIME_PROVIDER=gemini",
        f"GEMINI_API_KEY={a.gemini_api_key}",
        "# Optional - only long-term memory + the push-to-talk voice mode use this.",
        f"OPENAI_API_KEY={a.openai_api_key}",
        f"KEL_NAME={a.robot_name}",
        "",
        "# Gemini voice.",
        "KEL_GEMINI_REALTIME_MODEL=gemini-3.1-flash-live-preview",
        "KEL_GEMINI_VOICE=Leda",
        "KEL_TONE_CUES_ENABLED=true",
        "",
        "# Audio (blank = system default).",
        f"KEL_AUDIO_INPUT_DEVICE={a.audio_input_device}",
        f"KEL_AUDIO_OUTPUT_DEVICE={a.audio_output_device}",
        "KEL_REALTIME_HALF_DUPLEX=true",
        "KEL_REALTIME_ECHO_CANCEL=false",
        "",
        "# Vision (photo only when she calls her look tool; fine with no camera).",
        "KEL_VISION_ENABLED=true",
        "KEL_CAMERA_DEVICE=0",
        "# Screen vision via a see_screen tool (needs grim on Wayland/wlroots).",
        f"KEL_SCREEN_ENABLED={_b(a.screen_enabled)}",
        "KEL_SCREEN_MAX_WIDTH=1280",
        "",
        "# Long-term memory (auto-off if no OpenAI key).",
        "KEL_MEMORY_ENABLED=true",
        "KEL_MEMORY_AUTO_CAPTURE=true",
        "KEL_MEMORY_PATH=kel_memory.json",
        "KEL_MEMORY_TOP_K=5",
        "",
        "# Wake word (needs a local Vosk model).",
        f"KEL_WAKE_ENABLED={_b(a.wake_enabled)}",
        "KEL_WAKE_BACKEND=vosk",
        f"KEL_WAKE_VOSK_MODEL_PATH={a.wake_model_path}",
        "KEL_WAKE_PHRASES_SLEEP=at ease",
        "KEL_WAKE_GREETING=Yeah?",
        "KEL_WAKE_FAREWELL=Alright, later.",
        "",
        "# On-screen face.",
        f"KEL_FACE_ENABLED={_b(a.face_enabled)}",
        "KEL_FACE_AUTOSTART=true",
        "KEL_FACE_FULLSCREEN=false",
        "",
        "# Computer control (shell off unless you chose to trust it; tripwire always on).",
        "KEL_BROWSER_ENABLED=true",
        f"KEL_SHELL_ENABLED={_b(a.shell_enabled)}",
        "KEL_SHELL_BLOCK_DANGEROUS=true",
        "KEL_KEYBOARD=wtype",
        "",
        "# Robot body (Arduino over USB; blank port = auto-detect).",
        f"KEL_BODY_ENABLED={_b(a.body_enabled)}",
        f"KEL_BODY_PORT={a.body_port}",
        "KEL_BODY_SERVO_PIN=9",
        "",
        "# OpenAI-only extras (text chat + push-to-talk); ignored on a Gemini setup.",
        "KEL_OPENAI_MODEL=gpt-5.4-mini",
        "KEL_EMBEDDING_MODEL=text-embedding-3-small",
    ]
    return "\n".join(lines) + "\n"


def summary(a: Answers) -> list[str]:
    """Human-readable recap of what will be turned on, for the wizard's closing screen."""
    on = "on"
    off = "off"
    return [
        f"Brain:   Gemini ({'key set' if a.gemini_api_key else 'NO KEY - she will not start'})",
        f"Memory:  {on if a.openai_api_key else off + ' (add an OpenAI key later to enable)'}",
        f"Wake:    {on if a.wake_enabled else off}",
        f"Screen:  {on if a.screen_enabled else off}",
        f"Body:    {on if a.body_enabled else off}",
        f"Face:    {on if a.face_enabled else off}",
        f"Control: browser on, shell {on if a.shell_enabled else off}",
    ]
