"""The setup wizard's configuration logic — tested without prompts, files, or network."""

from __future__ import annotations

from io import StringIO

import pytest
from dotenv import dotenv_values

from kel.config.settings import ConfigurationError, Settings
from kel.setup.wizard import Answers, build_env_text, summary


def _settings_from(answers: Answers) -> Settings:
    text = build_env_text(answers)
    return Settings.from_mapping(dotenv_values(stream=StringIO(text)))


def test_gemini_only_env_builds_and_needs_no_openai_key() -> None:
    # The whole point of sharing: a friend with only a free Gemini key can start her.
    settings = _settings_from(Answers(gemini_api_key="g-key"))

    assert settings.realtime_provider == "gemini"
    assert settings.gemini_api_key == "g-key"
    assert settings.openai_api_key == ""  # optional, blank is fine
    assert settings.shell_enabled is False  # safe sharing default


def test_answers_flow_into_the_generated_env() -> None:
    text = build_env_text(
        Answers(
            gemini_api_key="g",
            openai_api_key="o",
            robot_name="Nova",
            wake_enabled=True,
            wake_model_path="/models/vosk",
            body_enabled=True,
            shell_enabled=True,
            face_enabled=False,
        )
    )

    assert "KEL_NAME=Nova" in text
    assert "GEMINI_API_KEY=g" in text
    assert "OPENAI_API_KEY=o" in text
    assert "KEL_WAKE_ENABLED=true" in text
    assert "KEL_WAKE_VOSK_MODEL_PATH=/models/vosk" in text
    assert "KEL_BODY_ENABLED=true" in text
    assert "KEL_SHELL_ENABLED=true" in text
    assert "KEL_FACE_ENABLED=false" in text


def test_defaults_are_safe_when_the_user_skips_everything() -> None:
    text = build_env_text(Answers(gemini_api_key="g"))

    assert "KEL_SHELL_ENABLED=false" in text  # no surprise machine control
    assert "KEL_WAKE_ENABLED=false" in text  # no wake without a model
    assert "KEL_BODY_ENABLED=false" in text  # no body unless detected
    assert "OPENAI_API_KEY=\n" in text  # left blank, not a placeholder key


def test_summary_reflects_state() -> None:
    lines = summary(Answers(gemini_api_key="g"))

    assert any("Gemini (key set)" in line for line in lines)
    assert any("shell off" in line for line in lines)
    assert any("Memory:  off" in line for line in lines)


def test_openai_provider_without_a_key_still_errors_clearly() -> None:
    # We loosened the OpenAI requirement for Gemini — but the OpenAI brain must still demand it.
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_mapping({"KEL_REALTIME_PROVIDER": "openai"})
