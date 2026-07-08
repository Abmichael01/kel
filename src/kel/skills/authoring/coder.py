"""Ask Gemini to write a skill (code + manifest + test args) as JSON."""

from __future__ import annotations

import json
from typing import Any

from kel.skills.authoring.contracts import DraftSkill

_CONTRACT = """
You write ONE Python skill for a voice assistant. Return ONLY a JSON object with keys:
- "name": snake_case identifier for the skill (a valid Python identifier).
- "description": one sentence telling the assistant WHEN to use this skill.
- "parameters": a JSON-Schema object ({"type":"object","properties":{...},"required":[...]}).
- "code": a complete Python module defining `def run(**kwargs) -> str`, taking the declared
  parameters as keyword arguments and RETURNING a human-readable string result. It may use
  the standard library or common pip packages and may read/write files or run commands.
- "invocation_args": a JSON object of concrete arguments to run the skill with to fulfil the
  request right now (must match the declared parameters).
The code MUST define `run` and MUST return a string. Do not include markdown, prose, or fences.
""".strip()


def build_contents(goal: str, feedback: str | None = None) -> str:
    """Build the user turn: the goal, plus the previous failure if retrying."""
    parts = [f"Goal: {goal}"]
    if feedback:
        parts.append(
            "Your previous attempt failed when run. Fix it. The error was:\n" + feedback
        )
    return "\n\n".join(parts)


def parse_draft(text: str) -> DraftSkill:
    """Parse the model's JSON into a DraftSkill, raising ValueError on a bad shape."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip().removesuffix("```").strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("draft is not a JSON object")
    code = str(data.get("code", ""))
    if "def run(" not in code:
        raise ValueError("draft code does not define run()")
    parameters = data.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}
    return DraftSkill(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        parameters=parameters,
        code=code,
        invocation_args=dict(data.get("invocation_args") or {}),
    )


class GeminiCoder:
    """Draft skills with a Gemini text model."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    def draft(self, goal: str, feedback: str | None = None) -> DraftSkill:
        client = self._client or self._make_client()
        response = client.models.generate_content(
            model=self._model,
            contents=build_contents(goal, feedback),
            config=self._config(),
        )
        return parse_draft(response.text)

    def _make_client(self) -> Any:
        from google import genai

        return genai.Client(api_key=self._api_key)

    def _config(self) -> Any:
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=_CONTRACT,
            response_mime_type="application/json",
        )
