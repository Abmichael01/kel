from kel.config.settings import Settings
from kel.prompts.kel_personality import build_kel_realtime_instructions
from kel.realtime.options import RealtimeSessionOptions


def test_realtime_options_create_a_low_latency_audio_session() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    options = RealtimeSessionOptions.from_settings(settings)

    payload = options.api_payload(instructions="Be Kel.")

    assert payload["model"] == "gpt-realtime-mini"
    assert payload["output_modalities"] == ["audio"]
    assert payload["audio"]["input"]["format"] == {
        "type": "audio/pcm",
        "rate": 24_000,
    }
    assert payload["audio"]["input"]["transcription"] == {
        "model": "gpt-4o-mini-transcribe",
        "language": "en",
    }
    assert payload["audio"]["input"]["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 450,
        "create_response": False,
        "interrupt_response": True,
    }
    assert payload["audio"]["output"]["voice"] == "marin"
    assert payload["audio"]["output"]["format"] == {
        "type": "audio/pcm",
        "rate": 24_000,
    }


def test_payload_offers_the_look_tool_when_vision_is_enabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_VISION_ENABLED": "true"})
    options = RealtimeSessionOptions.from_settings(settings)

    payload = options.api_payload(instructions="Be Kel.")

    assert payload["tool_choice"] == "auto"
    assert any(tool["name"] == "look" for tool in payload["tools"])


def test_payload_omits_tools_when_all_capabilities_are_disabled() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_VISION_ENABLED": "false",
            "KEL_MEMORY_ENABLED": "false",
            "KEL_BROWSER_ENABLED": "false",
            "KEL_SHELL_ENABLED": "false",
        }
    )
    options = RealtimeSessionOptions.from_settings(settings)

    payload = options.api_payload(instructions="Be Kel.")

    assert "tools" not in payload


def test_payload_offers_browser_tools_when_enabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_BROWSER_ENABLED": "true"})
    options = RealtimeSessionOptions.from_settings(settings)

    names = {tool["name"] for tool in options.api_payload(instructions="x")["tools"]}

    assert {"open_url", "web_search"} <= names


def test_payload_offers_run_command_only_when_shell_is_enabled() -> None:
    on = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SHELL_ENABLED": "true"})
    off = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SHELL_ENABLED": "false"})

    on_payload = RealtimeSessionOptions.from_settings(on).api_payload(instructions="x")
    off_payload = RealtimeSessionOptions.from_settings(off).api_payload(instructions="x")

    on_names = {tool["name"] for tool in on_payload["tools"]}
    off_names = {tool["name"] for tool in off_payload.get("tools", [])}
    assert {
        "run_command",
        "run_in_terminal",
        "type_text",
        "press_key",
        "swipe_desktop",
        "start_type_mode",
    } <= on_names
    assert "run_command" not in off_names
    assert "type_text" not in off_names
    assert "swipe_desktop" not in off_names
    assert "start_type_mode" not in off_names


def test_type_mode_update_keeps_vad_but_disables_automatic_responses() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )

    payload = options.type_mode_update(enabled=True)
    turn_detection = payload["audio"]["input"]["turn_detection"]

    assert payload["type"] == "realtime"
    assert turn_detection["type"] == "server_vad"
    assert turn_detection["create_response"] is False
    assert turn_detection["interrupt_response"] is False


def test_leaving_type_mode_restores_manually_controlled_responses() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )

    turn_detection = options.type_mode_update(enabled=False)["audio"]["input"]["turn_detection"]

    assert turn_detection["create_response"] is False
    assert turn_detection["interrupt_response"] is True


def test_payload_offers_memory_tools_when_memory_is_enabled() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_MEMORY_ENABLED": "true"})
    options = RealtimeSessionOptions.from_settings(settings)

    payload = options.api_payload(instructions="Be Kel.")

    names = {tool["name"] for tool in payload["tools"]}
    assert {"remember", "recall"} <= names


def test_realtime_prompt_keeps_spoken_responses_short() -> None:
    prompt = build_kel_realtime_instructions("Nova")

    assert "You are Nova" in prompt
    assert "one to three short" in prompt
    assert "If the user interrupts" in prompt


def test_realtime_instructions_include_the_machine_context() -> None:
    prompt = build_kel_realtime_instructions("Kel", environment="MACHINE-FACTS-123")

    assert "MACHINE-FACTS-123" in prompt


def test_realtime_prompt_forces_a_fresh_look_every_time() -> None:
    prompt = build_kel_realtime_instructions("Kel").lower()

    assert "blind between looks" in prompt
    assert "fresh frame" in prompt
    assert "do not wait for the user to tell you to look" in prompt


def test_realtime_prompt_maps_spoken_swipes_to_desktop_shortcuts() -> None:
    prompt = build_kel_realtime_instructions("Kel")

    assert "swipe left" in prompt.lower()
    assert "Super+Left" in prompt
    assert "Super+Right" in prompt


def test_realtime_prompt_enters_type_mode_without_asking_for_text() -> None:
    prompt = build_kel_realtime_instructions("Kel").lower()

    assert '"typing mode"' in prompt
    assert '"type mode"' not in prompt
    assert "start_type_mode" in prompt
    assert "do not ask what to type" in prompt


def test_realtime_prompt_acts_before_speaking_for_one_shot_typing() -> None:
    prompt = build_kel_realtime_instructions("Kel").lower()

    assert "direct typing" in prompt
    assert "smart typing" in prompt
    assert "call `type_text` before saying anything" in prompt
    assert "only after the tool result" in prompt


def test_type_text_tool_supports_direct_and_composed_writing() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SHELL_ENABLED": "true"})
    payload = RealtimeSessionOptions.from_settings(settings).api_payload(instructions="x")
    tool = next(tool for tool in payload["tools"] if tool["name"] == "type_text")

    assert "exact words" in tool["description"].lower()
    assert "draft" in tool["description"].lower()
    assert "before speaking" in tool["description"].lower()


def test_api_payload_appends_extra_tools() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )
    extra = [{"type": "function", "name": "make_qr_code", "description": "x", "parameters": {}}]

    payload = options.api_payload(instructions="x", extra_tools=extra)

    names = {tool["name"] for tool in payload["tools"]}
    assert "make_qr_code" in names


def test_tools_update_carries_a_fresh_tool_list() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )
    specs = [{"type": "function", "name": "greet", "description": "x", "parameters": {}}]

    payload = options.tools_update(specs)

    assert payload["type"] == "realtime"
    assert payload["tool_choice"] == "auto"
    assert [tool["name"] for tool in payload["tools"]] == ["greet"]
