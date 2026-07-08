"""The build/test/arm loop: draft a skill, run it, fix it, arm it."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from kel.skills.authoring.contracts import AuthorOutcome, DraftSkill
from kel.skills.contracts import Skill, SkillResult
from kel.skills.executor import run_skill

_MISSING_MODULE_RE = re.compile(r"No module named '([\w.]+)'")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class Coder(Protocol):
    def draft(self, goal: str, feedback: str | None = None) -> DraftSkill: ...


def _pip_install(module: str) -> bool:
    """Install one module into Kel's own venv; return whether it succeeded."""
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", module],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode == 0


class SkillAuthor:
    """Turn a natural-language goal into a working, armed skill."""

    def __init__(
        self,
        *,
        coder: Coder,
        store: Any,
        root: Path,
        reserved_names: frozenset[str] = frozenset(),
        max_attempts: int = 4,
        timeout: float = 20.0,
        allow_pip: bool = True,
        run: Callable[..., SkillResult] = run_skill,
        install: Callable[[str], bool] | None = None,
        install_budget: int = 3,
    ) -> None:
        self._coder = coder
        self._store = store
        self._root = Path(root)
        self._reserved = reserved_names
        self._max_attempts = max_attempts
        self._timeout = timeout
        self._allow_pip = allow_pip
        self._run = run
        self._install = install or _pip_install
        self._install_budget = install_budget

    def build(self, goal: str) -> AuthorOutcome:
        feedback: str | None = None
        last_error = "no attempts were made"
        for attempt in range(1, self._max_attempts + 1):
            try:
                draft = self._coder.draft(goal, feedback)
            except ValueError as error:
                # A malformed draft (bad JSON, missing run(), etc.) is retryable.
                last_error = f"your previous output was not a valid skill draft: {error}"
                feedback = last_error
                continue
            except Exception as error:  # noqa: BLE001 - a service/API failure, not a bad draft
                return AuthorOutcome(
                    ok=False,
                    output=f"I couldn't reach the skill-builder service: {error}",
                    attempts=attempt,
                )
            if not _NAME_RE.match(draft.name):
                # An empty/invalid name would make `directory = root / name` collapse onto
                # (or escape) the skills root; writing nothing keeps a failed attempt from
                # ever touching the filesystem.
                last_error = (
                    "the skill name must be a snake_case identifier (lowercase letters, "
                    "digits, underscores, starting with a letter)"
                )
                feedback = last_error
                continue
            name = self._resolve_name(draft.name)
            directory = self._write(name, draft, enabled=False)
            result = self._run_with_deps(name, directory, draft.invocation_args)
            if result.ok:
                self._arm(name, draft)
                return AuthorOutcome(
                    ok=True, output=result.output, skill_name=name, attempts=attempt
                )
            shutil.rmtree(directory, ignore_errors=True)
            last_error = result.output
            feedback = result.output
        return AuthorOutcome(
            ok=False,
            output=f"I tried {self._max_attempts} times but couldn't get that working. "
            f"Last error: {last_error}",
            attempts=self._max_attempts,
        )

    def _run_with_deps(self, name: str, directory: Path, args: dict[str, Any]) -> SkillResult:
        skill = self._skill_object(name, directory, enabled=False)
        result = self._run(skill, args, timeout=self._timeout)
        for _ in range(self._install_budget):
            if result.ok:
                return result
            match = _MISSING_MODULE_RE.search(result.output)
            if not match or not self._allow_pip:
                return result
            module = match.group(1).split(".")[0]
            if not self._install(module):
                return result
            result = self._run(skill, args, timeout=self._timeout)
        return result

    def _resolve_name(self, base: str) -> str:
        name, index = base, 2
        while name in self._reserved or self._store.get(name) is not None:
            name = f"{base}_{index}"
            index += 1
        return name

    def _write(self, name: str, draft: DraftSkill, *, enabled: bool) -> Path:
        directory = self._root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "skill.py").write_text(draft.code)
        (directory / "skill.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "description": draft.description,
                    "parameters": draft.parameters,
                    "enabled": enabled,
                    "author": "kel",
                    "created_at": "",
                    "version": 1,
                },
                indent=2,
            )
        )
        return directory

    def _arm(self, name: str, draft: DraftSkill) -> None:
        self._write(name, draft, enabled=True)

    @staticmethod
    def _skill_object(name: str, directory: Path, *, enabled: bool) -> Skill:
        return Skill(
            name=name,
            description="",
            parameters={"type": "object", "properties": {}},
            enabled=enabled,
            author="kel",
            created_at="",
            version=1,
            directory=directory,
        )
