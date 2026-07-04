"""Load and validate settings without exposing secrets to other concerns."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when Kel cannot safely start with the supplied configuration."""


_TRUE_WORDS = {"true", "1", "yes", "on"}
_FALSE_WORDS = {"false", "0", "no", "off"}


def _parse_bool(raw: str, name: str) -> bool:
    """Read a forgiving boolean flag, rejecting anything ambiguous."""
    text = raw.strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    raise ConfigurationError(f"{name} must be true or false.")


def _parse_phrase_list(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated list of trigger phrases; empty means none."""
    if raw is None:
        return default
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Values required to construct the application."""

    openai_api_key: str
    openai_model: str = "gpt-5.4-mini"
    robot_name: str = "Kel"
    transcription_model: str = "gpt-4o-mini-transcribe"
    speech_model: str = "gpt-4o-mini-tts"
    speech_voice: str = "marin"
    microphone_sample_rate: int = 16_000
    audio_input_device: str | None = None
    audio_output_device: str | None = None
    realtime_model: str = "gpt-realtime-mini"
    realtime_voice: str = "marin"
    realtime_transcription_model: str = "gpt-4o-mini-transcribe"
    realtime_vad_threshold: float = 0.5
    realtime_vad_silence_ms: int = 450
    realtime_noise_reduction: str = "far_field"
    realtime_language: str = "en"
    realtime_half_duplex: bool = True
    realtime_echo_cancel: bool = False
    realtime_provider: str = "openai"
    gemini_api_key: str = ""
    gemini_realtime_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice: str = "Leda"
    gemini_affective_dialog: bool = False
    tone_cues_enabled: bool = True
    wake_enabled: bool = True
    wake_backend: str = "vosk"
    wake_vosk_model_path: str = ""
    wake_phrases_wake: tuple[str, ...] = ()
    wake_phrases_sleep: tuple[str, ...] = ("at ease",)
    wake_access_key: str = ""
    wake_keyword_attention_path: str = ""
    wake_keyword_at_ease_path: str = ""
    wake_sensitivity: float = 0.5
    wake_auto_sleep_seconds: int = 90
    wake_quick_sleep_seconds: int = 30
    wake_greeting: str = "Yeah?"
    wake_farewell: str = "Alright, later."
    vision_enabled: bool = True
    camera_device_index: int = 0
    vision_image_max_width: int = 768
    browser_enabled: bool = True
    shell_enabled: bool = False
    shell_timeout_seconds: int = 20
    shell_block_dangerous: bool = True
    terminal_command: str = ""
    keyboard_tool: str = ""
    body_enabled: bool = False
    body_port: str = ""
    body_servo_pin: int = 9
    face_enabled: bool = False
    face_host: str = "127.0.0.1"
    face_port: int = 8765
    face_autostart: bool = True
    face_fullscreen: bool = True
    memory_enabled: bool = True
    memory_auto_capture: bool = True
    memory_path: str = "kel_memory.json"
    embedding_model: str = "text-embedding-3-small"
    memory_top_k: int = 5

    @classmethod
    def from_env(cls) -> Settings:
        """Load a local `.env`, then read settings from the process environment."""
        load_dotenv()
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        """Create settings from a mapping, keeping validation easy to unit test."""
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if api_key == "replace-with-your-api-key":
            api_key = ""
        # OpenAI is only the brain when the provider is "openai". With the Gemini provider
        # it is optional (used only for long-term memory + the older chained voice), so a
        # Gemini-only user can start with just their free Google key.
        realtime_provider = values.get("KEL_REALTIME_PROVIDER", "openai").strip().lower()
        if realtime_provider == "openai" and not api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is missing. The OpenAI brain needs it - add it to your .env, "
                "or set KEL_REALTIME_PROVIDER=gemini to use Google's free key instead."
            )

        model = values.get("KEL_OPENAI_MODEL", "gpt-5.4-mini").strip()
        robot_name = values.get("KEL_NAME", "Kel").strip()
        transcription_model = values.get(
            "KEL_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
        ).strip()
        speech_model = values.get("KEL_SPEECH_MODEL", "gpt-4o-mini-tts").strip()
        speech_voice = values.get("KEL_SPEECH_VOICE", "marin").strip()
        sample_rate_text = values.get("KEL_MICROPHONE_SAMPLE_RATE", "16000").strip()
        input_device = values.get("KEL_AUDIO_INPUT_DEVICE", "").strip() or None
        output_device = values.get("KEL_AUDIO_OUTPUT_DEVICE", "").strip() or None
        realtime_model = values.get("KEL_REALTIME_MODEL", "gpt-realtime-mini").strip()
        realtime_voice = values.get("KEL_REALTIME_VOICE", "marin").strip()
        realtime_transcription_model = values.get(
            "KEL_REALTIME_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
        ).strip()
        realtime_threshold_text = values.get("KEL_REALTIME_VAD_THRESHOLD", "0.5").strip()
        realtime_silence_text = values.get("KEL_REALTIME_VAD_SILENCE_MS", "450").strip()
        realtime_noise_reduction = values.get("KEL_REALTIME_NOISE_REDUCTION", "far_field").strip()
        realtime_language = values.get("KEL_REALTIME_LANGUAGE", "en").strip()
        realtime_half_duplex = _parse_bool(
            values.get("KEL_REALTIME_HALF_DUPLEX", "true"), "KEL_REALTIME_HALF_DUPLEX"
        )
        realtime_echo_cancel = _parse_bool(
            values.get("KEL_REALTIME_ECHO_CANCEL", "false"),
            "KEL_REALTIME_ECHO_CANCEL",
        )
        gemini_api_key = (
            values.get("GEMINI_API_KEY", "").strip() or values.get("KEL_GEMINI_API_KEY", "").strip()
        )
        gemini_realtime_model = values.get(
            "KEL_GEMINI_REALTIME_MODEL", "gemini-3.1-flash-live-preview"
        ).strip()
        gemini_voice = values.get("KEL_GEMINI_VOICE", "Leda").strip()
        gemini_affective_dialog = _parse_bool(
            values.get("KEL_GEMINI_AFFECTIVE_DIALOG", "false"), "KEL_GEMINI_AFFECTIVE_DIALOG"
        )
        tone_cues_enabled = _parse_bool(
            values.get("KEL_TONE_CUES_ENABLED", "true"), "KEL_TONE_CUES_ENABLED"
        )
        wake_enabled = _parse_bool(values.get("KEL_WAKE_ENABLED", "true"), "KEL_WAKE_ENABLED")
        wake_backend = values.get("KEL_WAKE_BACKEND", "vosk").strip().lower()
        wake_vosk_model_path = values.get("KEL_WAKE_VOSK_MODEL_PATH", "").strip()
        wake_phrases_wake = _parse_phrase_list(values.get("KEL_WAKE_PHRASES_WAKE"), ())
        wake_phrases_sleep = _parse_phrase_list(values.get("KEL_WAKE_PHRASES_SLEEP"), ("at ease",))
        wake_access_key = values.get("KEL_WAKE_ACCESS_KEY", "").strip()
        wake_attention_path = values.get("KEL_WAKE_KEYWORD_ATTENTION_PATH", "").strip()
        wake_at_ease_path = values.get("KEL_WAKE_KEYWORD_AT_EASE_PATH", "").strip()
        wake_sensitivity_text = values.get("KEL_WAKE_SENSITIVITY", "0.5").strip()
        wake_auto_sleep_text = values.get("KEL_WAKE_AUTO_SLEEP_SECONDS", "90").strip()
        wake_quick_sleep_text = values.get("KEL_WAKE_QUICK_SLEEP_SECONDS", "30").strip()
        wake_greeting = values.get("KEL_WAKE_GREETING", "Yeah?")
        wake_farewell = values.get("KEL_WAKE_FAREWELL", "Alright, later.")
        vision_enabled = _parse_bool(values.get("KEL_VISION_ENABLED", "true"), "KEL_VISION_ENABLED")
        camera_device_text = values.get("KEL_CAMERA_DEVICE", "0").strip()
        vision_max_width_text = values.get("KEL_VISION_MAX_WIDTH", "768").strip()
        browser_enabled = _parse_bool(
            values.get("KEL_BROWSER_ENABLED", "true"), "KEL_BROWSER_ENABLED"
        )
        shell_enabled = _parse_bool(values.get("KEL_SHELL_ENABLED", "false"), "KEL_SHELL_ENABLED")
        shell_block_dangerous = _parse_bool(
            values.get("KEL_SHELL_BLOCK_DANGEROUS", "true"), "KEL_SHELL_BLOCK_DANGEROUS"
        )
        shell_timeout_text = values.get("KEL_SHELL_TIMEOUT_SECONDS", "20").strip()
        terminal_command = values.get("KEL_TERMINAL", "").strip()
        keyboard_tool = values.get("KEL_KEYBOARD", "").strip()
        body_enabled = _parse_bool(values.get("KEL_BODY_ENABLED", "false"), "KEL_BODY_ENABLED")
        body_port = values.get("KEL_BODY_PORT", "").strip()
        body_servo_pin_text = values.get("KEL_BODY_SERVO_PIN", "9").strip()
        face_enabled = _parse_bool(values.get("KEL_FACE_ENABLED", "false"), "KEL_FACE_ENABLED")
        face_host = values.get("KEL_FACE_HOST", "127.0.0.1").strip() or "127.0.0.1"
        face_port_text = values.get("KEL_FACE_PORT", "8765").strip()
        face_autostart = _parse_bool(values.get("KEL_FACE_AUTOSTART", "true"), "KEL_FACE_AUTOSTART")
        face_fullscreen = _parse_bool(
            values.get("KEL_FACE_FULLSCREEN", "true"), "KEL_FACE_FULLSCREEN"
        )
        memory_enabled = _parse_bool(values.get("KEL_MEMORY_ENABLED", "true"), "KEL_MEMORY_ENABLED")
        memory_auto_capture = _parse_bool(
            values.get("KEL_MEMORY_AUTO_CAPTURE", "true"), "KEL_MEMORY_AUTO_CAPTURE"
        )
        memory_path = values.get("KEL_MEMORY_PATH", "kel_memory.json").strip()
        embedding_model = values.get("KEL_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        memory_top_k_text = values.get("KEL_MEMORY_TOP_K", "5").strip()

        if not model:
            raise ConfigurationError("KEL_OPENAI_MODEL cannot be empty.")
        if not robot_name:
            raise ConfigurationError("KEL_NAME cannot be empty.")
        if not transcription_model:
            raise ConfigurationError("KEL_TRANSCRIPTION_MODEL cannot be empty.")
        if not speech_model:
            raise ConfigurationError("KEL_SPEECH_MODEL cannot be empty.")
        if not speech_voice:
            raise ConfigurationError("KEL_SPEECH_VOICE cannot be empty.")
        if not realtime_model:
            raise ConfigurationError("KEL_REALTIME_MODEL cannot be empty.")
        if not realtime_voice:
            raise ConfigurationError("KEL_REALTIME_VOICE cannot be empty.")
        if not realtime_transcription_model:
            raise ConfigurationError("KEL_REALTIME_TRANSCRIPTION_MODEL cannot be empty.")
        if realtime_noise_reduction not in {"near_field", "far_field"}:
            raise ConfigurationError(
                "KEL_REALTIME_NOISE_REDUCTION must be near_field or far_field."
            )
        if realtime_provider not in {"openai", "gemini"}:
            raise ConfigurationError("KEL_REALTIME_PROVIDER must be openai or gemini.")
        if realtime_provider == "gemini":
            if not gemini_realtime_model:
                raise ConfigurationError("KEL_GEMINI_REALTIME_MODEL cannot be empty.")
            if not gemini_voice:
                raise ConfigurationError("KEL_GEMINI_VOICE cannot be empty.")
        if keyboard_tool and keyboard_tool not in {"xdotool", "ydotool", "wtype"}:
            raise ConfigurationError(
                "KEL_KEYBOARD must be xdotool, ydotool, wtype, or empty for auto-detection."
            )

        try:
            body_servo_pin = int(body_servo_pin_text)
        except ValueError as error:
            raise ConfigurationError("KEL_BODY_SERVO_PIN must be an integer.") from error

        try:
            face_port = int(face_port_text)
        except ValueError as error:
            raise ConfigurationError("KEL_FACE_PORT must be an integer.") from error

        try:
            sample_rate = int(sample_rate_text)
        except ValueError as error:
            raise ConfigurationError("KEL_MICROPHONE_SAMPLE_RATE must be an integer.") from error
        if sample_rate <= 0:
            raise ConfigurationError("KEL_MICROPHONE_SAMPLE_RATE must be positive.")

        try:
            realtime_threshold = float(realtime_threshold_text)
        except ValueError as error:
            raise ConfigurationError("KEL_REALTIME_VAD_THRESHOLD must be a number.") from error
        if not 0 <= realtime_threshold <= 1:
            raise ConfigurationError("KEL_REALTIME_VAD_THRESHOLD must be between 0 and 1.")

        try:
            realtime_silence_ms = int(realtime_silence_text)
        except ValueError as error:
            raise ConfigurationError("KEL_REALTIME_VAD_SILENCE_MS must be an integer.") from error
        if realtime_silence_ms <= 0:
            raise ConfigurationError("KEL_REALTIME_VAD_SILENCE_MS must be positive.")

        if wake_backend not in {"vosk", "porcupine"}:
            raise ConfigurationError("KEL_WAKE_BACKEND must be vosk or porcupine.")

        try:
            wake_sensitivity = float(wake_sensitivity_text)
        except ValueError as error:
            raise ConfigurationError("KEL_WAKE_SENSITIVITY must be a number.") from error
        if not 0 <= wake_sensitivity <= 1:
            raise ConfigurationError("KEL_WAKE_SENSITIVITY must be between 0 and 1.")

        try:
            wake_auto_sleep_seconds = int(wake_auto_sleep_text)
        except ValueError as error:
            raise ConfigurationError("KEL_WAKE_AUTO_SLEEP_SECONDS must be an integer.") from error
        if wake_auto_sleep_seconds < 0:
            raise ConfigurationError("KEL_WAKE_AUTO_SLEEP_SECONDS cannot be negative.")

        try:
            wake_quick_sleep_seconds = int(wake_quick_sleep_text)
        except ValueError as error:
            raise ConfigurationError("KEL_WAKE_QUICK_SLEEP_SECONDS must be an integer.") from error
        if wake_quick_sleep_seconds < 0:
            raise ConfigurationError("KEL_WAKE_QUICK_SLEEP_SECONDS cannot be negative.")

        try:
            camera_device_index = int(camera_device_text)
        except ValueError as error:
            raise ConfigurationError("KEL_CAMERA_DEVICE must be an integer index.") from error

        try:
            vision_image_max_width = int(vision_max_width_text)
        except ValueError as error:
            raise ConfigurationError("KEL_VISION_MAX_WIDTH must be an integer.") from error
        if vision_image_max_width <= 0:
            raise ConfigurationError("KEL_VISION_MAX_WIDTH must be positive.")

        try:
            shell_timeout_seconds = int(shell_timeout_text)
        except ValueError as error:
            raise ConfigurationError("KEL_SHELL_TIMEOUT_SECONDS must be an integer.") from error
        if shell_timeout_seconds <= 0:
            raise ConfigurationError("KEL_SHELL_TIMEOUT_SECONDS must be positive.")

        try:
            memory_top_k = int(memory_top_k_text)
        except ValueError as error:
            raise ConfigurationError("KEL_MEMORY_TOP_K must be an integer.") from error
        if memory_top_k <= 0:
            raise ConfigurationError("KEL_MEMORY_TOP_K must be positive.")

        return cls(
            openai_api_key=api_key,
            openai_model=model,
            robot_name=robot_name,
            transcription_model=transcription_model,
            speech_model=speech_model,
            speech_voice=speech_voice,
            microphone_sample_rate=sample_rate,
            audio_input_device=input_device,
            audio_output_device=output_device,
            realtime_model=realtime_model,
            realtime_voice=realtime_voice,
            realtime_transcription_model=realtime_transcription_model,
            realtime_vad_threshold=realtime_threshold,
            realtime_vad_silence_ms=realtime_silence_ms,
            realtime_noise_reduction=realtime_noise_reduction,
            realtime_language=realtime_language,
            realtime_half_duplex=realtime_half_duplex,
            realtime_echo_cancel=realtime_echo_cancel,
            realtime_provider=realtime_provider,
            gemini_api_key=gemini_api_key,
            gemini_realtime_model=gemini_realtime_model,
            gemini_voice=gemini_voice,
            gemini_affective_dialog=gemini_affective_dialog,
            tone_cues_enabled=tone_cues_enabled,
            wake_enabled=wake_enabled,
            wake_backend=wake_backend,
            wake_vosk_model_path=wake_vosk_model_path,
            wake_phrases_wake=wake_phrases_wake,
            wake_phrases_sleep=wake_phrases_sleep,
            wake_access_key=wake_access_key,
            wake_keyword_attention_path=wake_attention_path,
            wake_keyword_at_ease_path=wake_at_ease_path,
            wake_sensitivity=wake_sensitivity,
            wake_auto_sleep_seconds=wake_auto_sleep_seconds,
            wake_quick_sleep_seconds=wake_quick_sleep_seconds,
            wake_greeting=wake_greeting,
            wake_farewell=wake_farewell,
            vision_enabled=vision_enabled,
            camera_device_index=camera_device_index,
            vision_image_max_width=vision_image_max_width,
            browser_enabled=browser_enabled,
            shell_enabled=shell_enabled,
            shell_timeout_seconds=shell_timeout_seconds,
            shell_block_dangerous=shell_block_dangerous,
            terminal_command=terminal_command,
            keyboard_tool=keyboard_tool,
            body_enabled=body_enabled,
            body_port=body_port,
            body_servo_pin=body_servo_pin,
            face_enabled=face_enabled,
            face_host=face_host,
            face_port=face_port,
            face_autostart=face_autostart,
            face_fullscreen=face_fullscreen,
            memory_enabled=memory_enabled,
            memory_auto_capture=memory_auto_capture,
            memory_path=memory_path,
            embedding_model=embedding_model,
            memory_top_k=memory_top_k,
        )
