from pathlib import Path

from kel.skills.contracts import Skill, SkillResult


def make_skill(**overrides) -> Skill:
    base = dict(
        name="make_qr_code",
        description="Make a QR code.",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        enabled=False,
        author="kel",
        created_at="2026-07-08T00:00:00Z",
        version=1,
        directory=Path("/tmp/make_qr_code"),
    )
    base.update(overrides)
    return Skill(**base)


def test_tool_spec_matches_the_openai_function_shape() -> None:
    spec = make_skill().tool_spec()

    assert spec == {
        "type": "function",
        "name": "make_qr_code",
        "description": "Make a QR code.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
    }


def test_skill_result_carries_ok_and_output() -> None:
    result = SkillResult(ok=False, output="skill 'x' failed: boom")

    assert result.ok is False
    assert "boom" in result.output


def test_builtin_tool_names_cover_the_known_tools() -> None:
    from kel.realtime.options import BUILTIN_TOOL_NAMES

    assert {"look", "remember", "run_command", "set_feeling", "move"} <= BUILTIN_TOOL_NAMES
