"""Shared types for skill authoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DraftSkill:
    """One generated skill: its manifest fields, code, and args to test/run it with."""

    name: str
    description: str
    parameters: dict[str, Any]
    code: str
    invocation_args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuthorOutcome:
    """The result of a build: success + the text Kel reads back, plus bookkeeping."""

    ok: bool
    output: str
    skill_name: str | None = None
    attempts: int = 0
