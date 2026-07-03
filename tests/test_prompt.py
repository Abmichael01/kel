from kel.prompts.kel_personality import build_kel_instructions


def test_prompt_uses_the_configured_name_and_requires_hardware_honesty() -> None:
    prompt = build_kel_instructions("Nova")

    assert "You are Nova" in prompt
    assert "Do not claim" in prompt
    assert "physical hardware" in prompt


def test_prompt_frames_kel_as_a_friend_not_a_servile_assistant() -> None:
    prompt = build_kel_instructions("Kel").lower()

    assert "friend" in prompt
    assert "not a formal assistant" in prompt
    assert "servile" in prompt


def test_prompt_is_playful_but_smart_when_it_matters() -> None:
    prompt = build_kel_instructions("Kel").lower()

    assert "silly" in prompt
    assert "funny" in prompt
    assert "smart" in prompt


def test_prompt_tells_kel_to_admit_when_she_did_not_hear() -> None:
    prompt = build_kel_instructions("Kel").lower()

    assert "didn't catch that" in prompt
    assert "never guess" in prompt
