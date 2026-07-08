import json
from types import SimpleNamespace

import pytest

from kel.skills.authoring.coder import GeminiCoder, build_contents, parse_draft


def valid_json() -> str:
    return json.dumps(
        {
            "name": "make_qr_code",
            "description": "Make a QR code.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
            "code": "def run(text):\n    return text\n",
            "invocation_args": {"text": "hi"},
        }
    )


def test_parse_draft_reads_a_json_object() -> None:
    draft = parse_draft(valid_json())

    assert draft.name == "make_qr_code"
    assert draft.code.startswith("def run(")
    assert draft.invocation_args == {"text": "hi"}


def test_parse_draft_strips_markdown_fences() -> None:
    draft = parse_draft("```json\n" + valid_json() + "\n```")

    assert draft.name == "make_qr_code"


def test_parse_draft_rejects_a_draft_missing_run_code() -> None:
    bad = json.dumps(
        {
            "name": "x",
            "description": "",
            "parameters": {},
            "code": "print(1)",
            "invocation_args": {},
        }
    )
    with pytest.raises(ValueError):
        parse_draft(bad)


def test_build_contents_includes_goal_and_feedback() -> None:
    contents = build_contents("make a qr code", "skill 'x' failed: boom")

    assert "make a qr code" in contents
    assert "boom" in contents


def test_gemini_coder_drafts_via_the_client() -> None:
    # Fake google-genai client: .models.generate_content(...) -> object with .text
    captured = {}

    def generate_content(*, model, contents, config):
        captured["model"] = model
        return SimpleNamespace(text=valid_json())

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    coder = GeminiCoder(api_key="unused", model="gemini-2.5-flash", client=fake_client)

    draft = coder.draft("make a qr code")

    assert draft.name == "make_qr_code"
    assert captured["model"] == "gemini-2.5-flash"
