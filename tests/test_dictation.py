"""Parsing rules for Kel's direct voice-to-keyboard mode."""

from kel.realtime.dictation import parse_dictation


def test_regular_dictation_preserves_the_transcript() -> None:
    command = parse_dictation("The future is bright.")

    assert command.text == "The future is bright."
    assert command.press_enter is False
    assert command.stop is False


def test_trailing_enter_is_a_command_not_typed_text() -> None:
    command = parse_dictation("The future is bright enter.")

    assert command.text == "The future is bright"
    assert command.press_enter is True
    assert command.stop is False


def test_enter_by_itself_only_presses_return() -> None:
    command = parse_dictation("Enter!")

    assert command.text == ""
    assert command.press_enter is True


def test_space_by_itself_presses_a_real_space_key() -> None:
    command = parse_dictation("Space.")

    assert command.text == ""
    assert command.press_space is True


def test_new_line_by_itself_presses_return() -> None:
    command = parse_dictation("New line.")

    assert command.text == ""
    assert command.press_enter is True


def test_enter_in_the_middle_remains_normal_text() -> None:
    command = parse_dictation("Enter the building carefully.")

    assert command.text == "Enter the building carefully."
    assert command.press_enter is False


def test_stop_typing_leaves_type_mode() -> None:
    command = parse_dictation("Stop typing.")

    assert command.text == ""
    assert command.stop is True


def test_typing_mode_off_is_also_an_exit_phrase() -> None:
    assert parse_dictation("typing mode off").stop is True
