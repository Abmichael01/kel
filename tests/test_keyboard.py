"""The keyboard tool types into whatever field the user has focused."""

from __future__ import annotations

from kel.system.keyboard import Keyboard


def test_type_uses_xdotool_when_available() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(runner=ran.append, which=lambda name: name == "xdotool")

    result = keyboard.type_text("hello world")

    assert ran == [["xdotool", "type", "--clearmodifiers", "--", "hello world"]]
    assert "hello world" in result


def test_press_key_uses_xdotool() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(runner=ran.append, which=lambda name: name == "xdotool")

    keyboard.press_key("Return")

    assert ran == [["xdotool", "key", "Return"]]


def test_swipe_left_uses_super_left_with_xdotool() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(tool="xdotool", runner=ran.append, desktop="")

    result = keyboard.swipe("left")

    assert ran == [["xdotool", "key", "super+Left"]]
    assert "left" in result.lower()


def test_swipe_right_holds_the_logo_modifier_with_wtype() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(tool="wtype", runner=ran.append, desktop="")

    keyboard.swipe("right")

    assert ran == [["wtype", "-M", "logo", "-k", "Right", "-m", "logo"]]


def test_swipe_left_uses_linux_key_codes_with_ydotool() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(tool="ydotool", runner=ran.append, desktop="")

    keyboard.swipe("left")

    assert ran == [["ydotool", "key", "125:1", "105:1", "105:0", "125:0"]]


def test_swipe_rejects_an_unknown_direction() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(tool="xdotool", runner=ran.append, desktop="")

    result = keyboard.swipe("up")

    assert ran == []
    assert "left or right" in result.lower()


def test_swipe_uses_native_niri_navigation_without_a_typing_tool() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(
        runner=ran.append,
        which=lambda name: name == "niri",
        desktop="niri",
    )

    result = keyboard.swipe("left")

    assert ran == [["niri", "msg", "action", "focus-column-left"]]
    assert "niri" in result.lower()


def test_type_uses_wtype_on_wayland() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(runner=ran.append, which=lambda name: name == "wtype")

    keyboard.type_text("hi")

    assert ran == [["wtype", "-d", "12", "hi"]]


def test_autodetect_prefers_the_first_available_tool() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(runner=ran.append, which=lambda name: name in {"ydotool", "wtype"})

    keyboard.type_text("x")

    assert ran[0][0] == "ydotool"  # earlier in the preference list than wtype


def test_no_tool_returns_a_helpful_message() -> None:
    ran: list[list[str]] = []
    keyboard = Keyboard(runner=ran.append, which=lambda _name: None)

    result = keyboard.type_text("hi")

    assert ran == []
    assert "xdotool" in result or "install" in result.lower()
