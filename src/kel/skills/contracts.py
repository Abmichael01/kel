"""Small shared types for the skill runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Skill:
    """One skill: its manifest metadata plus the folder that holds it."""

    name: str
    description: str
    parameters: dict[str, Any]
    enabled: bool
    author: str
    created_at: str
    version: int
    directory: Path

    def tool_spec(self) -> dict[str, Any]:
        """Return this skill as an OpenAI-style function tool declaration."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(frozen=True, slots=True)
class SkillResult:
    """The outcome of running a skill: success plus the text the model reads."""

    ok: bool
    output: str
