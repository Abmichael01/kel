from google.genai import types

from kel.config.settings import Settings
from kel.realtime.gemini_tools import function_declarations, gemini_tools
from kel.realtime.options import RealtimeSessionOptions


def _all_tools_options() -> RealtimeSessionOptions:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_VISION_ENABLED": "true",
            "KEL_MEMORY_ENABLED": "true",
            "KEL_BROWSER_ENABLED": "true",
            "KEL_BODY_ENABLED": "true",
            "KEL_SHELL_ENABLED": "true",
        }
    )
    return RealtimeSessionOptions.from_settings(settings)


def test_empty_specs_make_no_tool() -> None:
    assert gemini_tools([]) == []


def test_every_enabled_tool_becomes_one_declaration() -> None:
    specs = _all_tools_options().tool_specs()

    declarations = function_declarations(specs)
    names = {declaration.name for declaration in declarations}

    assert len(declarations) == len(specs)
    assert {"look", "remember", "recall", "set_feeling", "move"} <= names
    assert {"run_command", "type_text", "press_key", "swipe_desktop"} <= names


def test_declarations_carry_typed_parameters_and_enums() -> None:
    specs = _all_tools_options().tool_specs()
    by_name = {d.name: d for d in function_declarations(specs)}

    remember = by_name["remember"]
    assert remember.parameters.type == types.Type.OBJECT
    assert "text" in remember.parameters.properties
    assert remember.parameters.properties["text"].type == types.Type.STRING
    assert remember.parameters.required == ["text"]

    # the swipe direction is an enum, which must survive the conversion
    assert by_name["swipe_desktop"].parameters.properties["direction"].enum == ["left", "right"]


def test_no_argument_tool_has_no_required_parameters() -> None:
    specs = _all_tools_options().tool_specs()
    look = {d.name: d for d in function_declarations(specs)}["look"]

    # `look` takes no parameters, so it must not carry an object schema with required keys
    assert look.parameters is None


def test_specs_wrap_into_a_single_tool() -> None:
    specs = _all_tools_options().tool_specs()

    tools = gemini_tools(specs)

    assert len(tools) == 1
    assert len(tools[0].function_declarations) == len(specs)
