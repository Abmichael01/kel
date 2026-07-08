"""Scan a directory of skill folders into validated, tool-ready Skill objects."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from kel.skills.contracts import Skill

_LOG = logging.getLogger(__name__)
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SkillStore:
    """Load skills from ``root``; each subfolder is one skill (manifest + code)."""

    def __init__(self, root: Path, *, reserved_names: frozenset[str] = frozenset()) -> None:
        self._root = Path(root)
        self._reserved = reserved_names

    def all(self) -> list[Skill]:
        """Return every valid skill in the root, invalid folders skipped."""
        if not self._root.is_dir():
            return []
        skills: list[Skill] = []
        seen: set[str] = set()
        for directory in sorted(p for p in self._root.iterdir() if p.is_dir()):
            skill = self._load_one(directory)
            if skill is None:
                continue
            if skill.name in self._reserved:
                _LOG.warning("skill %s collides with a built-in tool; skipping", skill.name)
                continue
            if skill.name in seen:
                _LOG.warning("duplicate skill name %s; skipping %s", skill.name, directory)
                continue
            seen.add(skill.name)
            skills.append(skill)
        return skills

    def armed(self) -> list[Skill]:
        """Return only the skills whose gate is on."""
        return [skill for skill in self.all() if skill.enabled]

    def tool_specs(self) -> list[dict[str, Any]]:
        """Return armed skills as OpenAI-style tool declarations."""
        return [skill.tool_spec() for skill in self.armed()]

    def get(self, name: str) -> Skill | None:
        """Return the skill with this name, or None."""
        return next((skill for skill in self.all() if skill.name == name), None)

    def arm(self, name: str) -> bool:
        """Turn a skill's gate on; return False if there is no such skill."""
        return self._set_enabled(name, True)

    def disarm(self, name: str) -> bool:
        """Turn a skill's gate off; return False if there is no such skill."""
        return self._set_enabled(name, False)

    def _set_enabled(self, name: str, enabled: bool) -> bool:
        skill = self.get(name)
        if skill is None:
            return False
        manifest_path = skill.directory / "skill.json"
        data = json.loads(manifest_path.read_text())
        data["enabled"] = enabled
        manifest_path.write_text(json.dumps(data, indent=2))
        return True

    def _load_one(self, directory: Path) -> Skill | None:
        manifest_path = directory / "skill.json"
        script_path = directory / "skill.py"
        if not manifest_path.is_file() or not script_path.is_file():
            return None
        try:
            data = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            _LOG.warning("skill folder %s has an unreadable manifest; skipping", directory.name)
            return None
        if not isinstance(data, dict):
            _LOG.warning("skill folder %s has a non-object manifest; skipping", directory.name)
            return None
        name = str(data.get("name", ""))
        if not _NAME_RE.match(name):
            _LOG.warning("skill folder %s has invalid name %r; skipping", directory.name, name)
            return None
        if name != directory.name:
            _LOG.warning("skill %s does not match folder %s; skipping", name, directory.name)
            return None
        parameters = data.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            _LOG.warning("skill %s has invalid parameters; skipping", name)
            return None
        try:
            compile(script_path.read_text(), str(script_path), "exec")
        except (OSError, SyntaxError):
            _LOG.warning("skill %s has a skill.py that does not compile; skipping", name)
            return None
        try:
            return Skill(
                name=name,
                description=str(data.get("description", "")),
                parameters=parameters,
                enabled=bool(data.get("enabled", False)),
                author=str(data.get("author", "unknown")),
                created_at=str(data.get("created_at", "")),
                version=int(data.get("version", 1)),
                directory=directory,
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            _LOG.warning("skill %s has a malformed manifest; skipping", name)
            return None
