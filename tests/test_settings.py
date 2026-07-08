import pytest

from kel.config.settings import ConfigurationError, Settings


def test_settings_require_an_api_key() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_mapping({})


def test_settings_read_values_and_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-5.4-mini"
    assert settings.robot_name == "Kel"
    assert settings.transcription_model == "gpt-4o-mini-transcribe"
    assert settings.speech_model == "gpt-4o-mini-tts"
    assert settings.speech_voice == "marin"
    assert settings.microphone_sample_rate == 16_000
    assert settings.realtime_model == "gpt-realtime-mini"
    assert settings.realtime_voice == "marin"
    assert settings.realtime_vad_threshold == 0.5
    assert settings.realtime_vad_silence_ms == 450
    assert settings.realtime_noise_reduction == "far_field"
    assert settings.realtime_language == "en"


def test_settings_reject_the_example_placeholder() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_mapping({"OPENAI_API_KEY": "replace-with-your-api-key"})


def test_settings_reject_an_invalid_sample_rate() -> None:
    with pytest.raises(ConfigurationError, match="SAMPLE_RATE"):
        Settings.from_mapping(
            {
                "OPENAI_API_KEY": "test-key",
                "KEL_MICROPHONE_SAMPLE_RATE": "fast",
            }
        )


def test_settings_reject_invalid_realtime_vad_values() -> None:
    with pytest.raises(ConfigurationError, match="VAD_THRESHOLD"):
        Settings.from_mapping(
            {
                "OPENAI_API_KEY": "test-key",
                "KEL_REALTIME_VAD_THRESHOLD": "1.5",
            }
        )

    with pytest.raises(ConfigurationError, match="NOISE_REDUCTION"):
        Settings.from_mapping(
            {
                "OPENAI_API_KEY": "test-key",
                "KEL_REALTIME_NOISE_REDUCTION": "magic",
            }
        )


def test_settings_wake_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.wake_enabled is True
    assert settings.wake_backend == "vosk"
    assert settings.wake_vosk_model_path == ""
    assert settings.wake_access_key == ""
    assert settings.wake_keyword_attention_path == ""
    assert settings.wake_keyword_at_ease_path == ""
    assert settings.wake_sensitivity == 0.5
    assert settings.wake_auto_sleep_seconds == 90
    assert settings.wake_quick_sleep_seconds == 30
    assert settings.wake_greeting == "Yeah?"
    assert settings.wake_farewell == "Alright, later."


def test_settings_wake_phrase_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.wake_phrases_wake == ()  # the name alone wakes her
    assert settings.wake_phrases_sleep == ("at ease",)


def test_settings_reject_a_negative_quick_sleep() -> None:
    with pytest.raises(ConfigurationError, match="QUICK_SLEEP"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_QUICK_SLEEP_SECONDS": "-1"})


def test_settings_wake_phrases_parse_comma_separated_lists() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_WAKE_PHRASES_WAKE": "Hey there, you up ",
            "KEL_WAKE_PHRASES_SLEEP": "bye",
        }
    )

    assert settings.wake_phrases_wake == ("hey there", "you up")
    assert settings.wake_phrases_sleep == ("bye",)


def test_settings_empty_wake_phrases_means_name_only() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_PHRASES_WAKE": ""})

    assert settings.wake_phrases_wake == ()


def test_settings_wake_backend_can_be_porcupine() -> None:
    settings = Settings.from_mapping(
        {"OPENAI_API_KEY": "test-key", "KEL_WAKE_BACKEND": "porcupine"}
    )

    assert settings.wake_backend == "porcupine"


def test_settings_reject_an_unknown_wake_backend() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_BACKEND"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_BACKEND": "magic"})


def test_settings_system_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.browser_enabled is True
    assert settings.shell_enabled is False  # off until explicitly enabled
    assert settings.shell_timeout_seconds == 20
    assert settings.shell_block_dangerous is True
    assert settings.terminal_command == ""  # empty = auto-detect
    assert settings.keyboard_tool == ""  # empty = auto-detect


def test_settings_shell_can_be_enabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SHELL_ENABLED": "true"})

    assert settings.shell_enabled is True


def test_settings_accepts_a_keyboard_tool_override() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_KEYBOARD": "wtype"})

    assert settings.keyboard_tool == "wtype"


def test_settings_rejects_an_unknown_keyboard_tool() -> None:
    with pytest.raises(ConfigurationError, match="KEL_KEYBOARD"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_KEYBOARD": "typewriter"})


def test_settings_dangerous_block_can_be_turned_off() -> None:
    settings = Settings.from_mapping(
        {"OPENAI_API_KEY": "test-key", "KEL_SHELL_BLOCK_DANGEROUS": "false"}
    )

    assert settings.shell_block_dangerous is False


def test_settings_memory_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.memory_enabled is True
    assert settings.memory_auto_capture is True
    assert settings.memory_path == "kel_memory.json"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.memory_top_k == 5


def test_settings_memory_can_be_disabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_MEMORY_ENABLED": "false"})

    assert settings.memory_enabled is False


def test_settings_reject_a_non_positive_memory_top_k() -> None:
    with pytest.raises(ConfigurationError, match="MEMORY_TOP_K"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_MEMORY_TOP_K": "0"})


def test_settings_vision_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.vision_enabled is True
    assert settings.camera_device_index == 0
    assert settings.vision_image_max_width == 768


def test_settings_vision_can_be_disabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_VISION_ENABLED": "false"})

    assert settings.vision_enabled is False


def test_settings_reject_a_non_integer_camera_device() -> None:
    with pytest.raises(ConfigurationError, match="CAMERA_DEVICE"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_CAMERA_DEVICE": "front"})


def test_settings_realtime_half_duplex_defaults_on() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.realtime_half_duplex is True


def test_settings_realtime_half_duplex_can_be_disabled() -> None:
    settings = Settings.from_mapping(
        {"OPENAI_API_KEY": "test-key", "KEL_REALTIME_HALF_DUPLEX": "false"}
    )

    assert settings.realtime_half_duplex is False


def test_settings_realtime_echo_cancel_defaults_off() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.realtime_echo_cancel is False


def test_settings_realtime_echo_cancel_can_be_enabled() -> None:
    settings = Settings.from_mapping(
        {"OPENAI_API_KEY": "test-key", "KEL_REALTIME_ECHO_CANCEL": "true"}
    )

    assert settings.realtime_echo_cancel is True


def test_settings_wake_can_be_disabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_ENABLED": "false"})

    assert settings.wake_enabled is False


def test_settings_reject_an_unparsable_wake_enabled() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_ENABLED"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_ENABLED": "maybe"})


def test_settings_reject_an_out_of_range_wake_sensitivity() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_SENSITIVITY"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_SENSITIVITY": "2"})


def test_settings_reject_a_negative_auto_sleep() -> None:
    with pytest.raises(ConfigurationError, match="AUTO_SLEEP"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_AUTO_SLEEP_SECONDS": "-5"})


def test_settings_reject_an_unparsable_auto_sleep() -> None:
    with pytest.raises(ConfigurationError, match="AUTO_SLEEP"):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_WAKE_AUTO_SLEEP_SECONDS": "soon"})


def test_skills_are_enabled_by_default_with_a_home_path() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.skills_enabled is True
    assert settings.skills_path == "~/.kel/skills"
    assert settings.skills_timeout_seconds == 20


def test_skills_can_be_configured() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_SKILLS_ENABLED": "false",
            "KEL_SKILLS_PATH": "/tmp/kel-skills",
            "KEL_SKILLS_TIMEOUT_SECONDS": "45",
        }
    )

    assert settings.skills_enabled is False
    assert settings.skills_path == "/tmp/kel-skills"
    assert settings.skills_timeout_seconds == 45


def test_a_non_positive_skills_timeout_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SKILLS_TIMEOUT_SECONDS": "0"})


def test_skill_authoring_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.skills_author_enabled is True
    assert settings.coder_model == "gemini-2.5-flash"
    assert settings.skills_author_max_attempts == 4
    assert settings.skills_author_allow_pip is True


def test_skill_authoring_can_be_configured() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_SKILLS_AUTHOR_ENABLED": "false",
            "KEL_CODER_MODEL": "gemini-3-flash",
            "KEL_SKILLS_AUTHOR_MAX_ATTEMPTS": "6",
            "KEL_SKILLS_AUTHOR_ALLOW_PIP": "false",
        }
    )

    assert settings.skills_author_enabled is False
    assert settings.coder_model == "gemini-3-flash"
    assert settings.skills_author_max_attempts == 6
    assert settings.skills_author_allow_pip is False


def test_a_non_positive_author_attempts_is_rejected() -> None:
    import pytest

    from kel.config.settings import ConfigurationError

    with pytest.raises(ConfigurationError):
        Settings.from_mapping(
            {"OPENAI_API_KEY": "test-key", "KEL_SKILLS_AUTHOR_MAX_ATTEMPTS": "0"}
        )
