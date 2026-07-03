import pytest

from kel.config.settings import ConfigurationError, Settings


def test_provider_defaults_to_openai_and_needs_no_gemini_key() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.realtime_provider == "openai"
    assert settings.gemini_realtime_model == "gemini-3.1-flash-live-preview"
    assert settings.gemini_voice == "Leda"
    assert settings.gemini_affective_dialog is False


def test_gemini_provider_reads_its_own_key_model_and_voice() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_REALTIME_PROVIDER": "gemini",
            "GEMINI_API_KEY": "g-key",
            "KEL_GEMINI_REALTIME_MODEL": "gemini-live-2.5-flash-preview",
            "KEL_GEMINI_VOICE": "Puck",
            "KEL_GEMINI_AFFECTIVE_DIALOG": "true",
        }
    )

    assert settings.realtime_provider == "gemini"
    assert settings.gemini_api_key == "g-key"
    assert settings.gemini_voice == "Puck"
    assert settings.gemini_affective_dialog is True


def test_gemini_provider_loads_without_a_key_so_other_tools_still_run() -> None:
    # The Google key is only required when the Gemini brain is actually built, so
    # unrelated commands (memory seeding, body demos) keep working without it.
    settings = Settings.from_mapping(
        {"OPENAI_API_KEY": "test-key", "KEL_REALTIME_PROVIDER": "gemini"}
    )

    assert settings.realtime_provider == "gemini"
    assert settings.gemini_api_key == ""


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="KEL_REALTIME_PROVIDER"):
        Settings.from_mapping(
            {"OPENAI_API_KEY": "test-key", "KEL_REALTIME_PROVIDER": "anthropic"}
        )
