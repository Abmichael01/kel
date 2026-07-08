# Skill Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Kel skills that live as folders on disk and appear as real callable tools in her live voice session — loaded, run in an isolated subprocess, and gated behind a review-then-arm switch.

**Architecture:** A new `kel.skills` package owns the on-disk format (`SkillStore`), a subprocess `runner`, and an `executor` that runs a skill with a timeout and maps failures to a safe string. Armed skills are appended to the tool list both realtime sessions already build from `RealtimeSessionOptions.tool_specs()`, so they light up on OpenAI and Gemini alike; each session's tool-call dispatcher gains a fallback that runs a skill when the called name isn't a built-in.

**Tech Stack:** Python ≥3.11, standard library only for the runtime (`json`, `subprocess`, `importlib`, `argparse`, `logging`), pytest for tests, `uv` to run everything.

## Global Constraints

- **Python ≥ 3.11**, `from __future__ import annotations` at the top of every new module (matches the codebase).
- **Ruff**: line-length 100, rules `E, F, I, UP, B, SIM`. Run `uv run ruff check` before every commit; fix what it flags.
- **Tests**: plain pytest functions (no classes for the tests themselves), descriptive `test_...` names, real objects / small fakes over mocking libraries. No network, no audio, no real model in any test.
- **Settings**: new options are `KEL_`-prefixed, parsed in `Settings.from_mapping`, validated with `ConfigurationError` on bad input — mirror the existing fields exactly.
- **Review-then-arm**: a skill's `enabled` defaults to `false`. Nothing arms a skill implicitly.
- **Isolation is stability, not security**: skills run in a subprocess with a timeout so they can't wedge or hang the session. They still run with full user privileges — do not add or imply a security sandbox.
- **Skills live outside the repo**: default root `~/.kel/skills/`. Never write skill folders into the git tree.
- **Commits**: end every commit message with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Work happens on the current `kel-skills` branch.
- Run a task's tests with `uv run pytest <path> -q`.

---

### Task 1: Skill settings

**Files:**
- Modify: `src/kel/config/settings.py` (add three fields + parsing/validation)
- Test: `tests/test_settings.py` (append)

**Interfaces:**
- Produces: `Settings.skills_enabled: bool` (default `True`), `Settings.skills_path: str` (default `"~/.kel/skills"`), `Settings.skills_timeout_seconds: int` (default `20`). Env vars `KEL_SKILLS_ENABLED`, `KEL_SKILLS_PATH`, `KEL_SKILLS_TIMEOUT_SECONDS`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_settings.py`:

```python
def test_skills_are_enabled_by_default_with_a_home_path() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.skills_enabled is True
    assert settings.skills_path == "~/.kel/skills"
    assert settings.skills_timeout_seconds == 20


def test_skills_can_be_configured() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_SKILLS_ENABLED": "false",
            "KEL_SKILLS_PATH": "/tmp/kel-skills",
            "KEL_SKILLS_TIMEOUT_SECONDS": "45",
        }
    )

    assert settings.skills_enabled is False
    assert settings.skills_path == "/tmp/kel-skills"
    assert settings.skills_timeout_seconds == 45


def test_a_non_positive_skills_timeout_is_rejected() -> None:
    import pytest

    from kel.config.settings import ConfigurationError

    with pytest.raises(ConfigurationError):
        Settings.from_mapping({"OPENAI_API_KEY": "test-key", "KEL_SKILLS_TIMEOUT_SECONDS": "0"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_settings.py -q -k skills`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'skills_enabled'`.

- [ ] **Step 3: Add the fields to the dataclass**

In `src/kel/config/settings.py`, in the `Settings` dataclass body, after `memory_top_k: int = 5` add:

```python
    skills_enabled: bool = True
    skills_path: str = "~/.kel/skills"
    skills_timeout_seconds: int = 20
```

- [ ] **Step 4: Parse and validate in `from_mapping`**

In `from_mapping`, alongside the other parsing (e.g. just after the `memory_top_k_text = ...` line):

```python
        skills_enabled = _parse_bool(values.get("KEL_SKILLS_ENABLED", "true"), "KEL_SKILLS_ENABLED")
        skills_path = values.get("KEL_SKILLS_PATH", "~/.kel/skills").strip() or "~/.kel/skills"
        skills_timeout_text = values.get("KEL_SKILLS_TIMEOUT_SECONDS", "20").strip()
```

Add the validation next to the other numeric checks (e.g. after the `memory_top_k` block):

```python
        try:
            skills_timeout_seconds = int(skills_timeout_text)
        except ValueError as error:
            raise ConfigurationError("KEL_SKILLS_TIMEOUT_SECONDS must be an integer.") from error
        if skills_timeout_seconds <= 0:
            raise ConfigurationError("KEL_SKILLS_TIMEOUT_SECONDS must be positive.")
```

Then pass them into the returned `cls(...)`, after `memory_top_k=memory_top_k,`:

```python
            skills_enabled=skills_enabled,
            skills_path=skills_path,
            skills_timeout_seconds=skills_timeout_seconds,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_settings.py -q`
Expected: PASS (all settings tests, old and new).

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src/kel/config/settings.py tests/test_settings.py
git add src/kel/config/settings.py tests/test_settings.py
git commit -m "feat(skills): add skills settings (enabled, path, timeout)"
```

---

### Task 2: Skill contracts and the built-in tool-name set

**Files:**
- Create: `src/kel/skills/__init__.py`
- Create: `src/kel/skills/contracts.py`
- Modify: `src/kel/realtime/options.py` (add `BUILTIN_TOOL_NAMES`)
- Test: `tests/test_skills_contracts.py`

**Interfaces:**
- Produces: `Skill(name, description, parameters, enabled, author, created_at, version, directory)` frozen dataclass with `Skill.tool_spec() -> dict`. `SkillResult(ok: bool, output: str)` frozen dataclass. `kel.realtime.options.BUILTIN_TOOL_NAMES: frozenset[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skills_contracts.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skills_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills'`.

- [ ] **Step 3: Create the package and contracts**

Create `src/kel/skills/__init__.py`:

```python
"""Kel's on-disk skill runtime: skills as folders that become live tools."""
```

Create `src/kel/skills/contracts.py`:

```python
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
```

- [ ] **Step 4: Add `BUILTIN_TOOL_NAMES` to options**

In `src/kel/realtime/options.py`, after the last `*_TOOL_NAME`/`_*_TOOL` definition (just before `@dataclass ... class RealtimeSessionOptions`), add:

```python
BUILTIN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        LOOK_TOOL_NAME,
        SEE_SCREEN_TOOL_NAME,
        REMEMBER_TOOL_NAME,
        RECALL_TOOL_NAME,
        OPEN_URL_TOOL_NAME,
        WEB_SEARCH_TOOL_NAME,
        RUN_COMMAND_TOOL_NAME,
        RUN_IN_TERMINAL_TOOL_NAME,
        TYPE_TEXT_TOOL_NAME,
        PRESS_KEY_TOOL_NAME,
        START_TYPE_MODE_TOOL_NAME,
        SWIPE_DESKTOP_TOOL_NAME,
        SET_FEELING_TOOL_NAME,
        MOVE_TOOL_NAME,
    }
)
```

- [ ] **Step 5: Write a test for the built-in name set**

Append to `tests/test_skills_contracts.py`:

```python
def test_builtin_tool_names_cover_the_known_tools() -> None:
    from kel.realtime.options import BUILTIN_TOOL_NAMES

    assert {"look", "remember", "run_command", "set_feeling", "move"} <= BUILTIN_TOOL_NAMES
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skills_contracts.py -q`
Expected: PASS.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check src/kel/skills tests/test_skills_contracts.py src/kel/realtime/options.py
git add src/kel/skills/__init__.py src/kel/skills/contracts.py tests/test_skills_contracts.py src/kel/realtime/options.py
git commit -m "feat(skills): add Skill/SkillResult contracts and built-in tool-name set"
```

---

### Task 3: `SkillStore` — scan, validate, emit tool specs

**Files:**
- Create: `src/kel/skills/store.py`
- Test: `tests/test_skills_store.py`

**Interfaces:**
- Consumes: `Skill` (Task 2), `BUILTIN_TOOL_NAMES` (Task 2).
- Produces: `SkillStore(root: Path, *, reserved_names: frozenset[str] = frozenset())` with `all() -> list[Skill]`, `armed() -> list[Skill]`, `tool_specs() -> list[dict]`, `get(name) -> Skill | None`. Invalid skill folders are skipped (logged), never fatal. A skill loads only when its folder name equals its manifest `name`, the name matches `^[a-z][a-z0-9_]*$`, it isn't reserved, `parameters` is an object schema, and `skill.py` compiles.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skills_store.py`:

```python
import json
from pathlib import Path

from kel.skills.store import SkillStore


def write_skill(
    root: Path,
    name: str,
    *,
    enabled: bool = False,
    parameters: dict | None = None,
    code: str = "def run(**kwargs):\n    return 'ok'\n",
    folder: str | None = None,
) -> Path:
    directory = root / (folder or name)
    directory.mkdir(parents=True)
    manifest = {
        "name": name,
        "description": f"{name} skill",
        "parameters": parameters or {"type": "object", "properties": {}},
        "enabled": enabled,
        "author": "kel",
        "created_at": "2026-07-08T00:00:00Z",
        "version": 1,
    }
    (directory / "skill.json").write_text(json.dumps(manifest))
    (directory / "skill.py").write_text(code)
    return directory


def test_missing_root_yields_no_skills(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "does-not-exist")

    assert store.all() == []
    assert store.tool_specs() == []


def test_store_scans_and_parses_a_skill(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet", enabled=True)
    store = SkillStore(tmp_path)

    skills = store.all()

    assert [s.name for s in skills] == ["greet"]
    assert skills[0].directory == tmp_path / "greet"
    assert skills[0].enabled is True


def test_armed_and_tool_specs_only_include_enabled_skills(tmp_path: Path) -> None:
    write_skill(tmp_path, "armed_one", enabled=True)
    write_skill(tmp_path, "off_one", enabled=False)
    store = SkillStore(tmp_path)

    assert [s.name for s in store.armed()] == ["armed_one"]
    assert [spec["name"] for spec in store.tool_specs()] == ["armed_one"]
    assert store.tool_specs()[0]["type"] == "function"


def test_a_skill_colliding_with_a_builtin_tool_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "look", enabled=True)  # "look" is a built-in tool name
    store = SkillStore(tmp_path, reserved_names=frozenset({"look"}))

    assert store.all() == []


def test_a_non_compiling_skill_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "broken", enabled=True, code="def run(:\n")  # syntax error
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_a_folder_name_mismatch_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "real_name", folder="different_folder")
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_invalid_parameters_are_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "bad_params", parameters={"type": "string"})
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_get_returns_a_skill_by_name(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet")
    store = SkillStore(tmp_path)

    assert store.get("greet").name == "greet"
    assert store.get("nope") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_skills_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.store'`.

- [ ] **Step 3: Implement the store**

Create `src/kel/skills/store.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skills_store.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/store.py tests/test_skills_store.py
git add src/kel/skills/store.py tests/test_skills_store.py
git commit -m "feat(skills): add SkillStore scanning, validation, and tool specs"
```

---

### Task 4: `SkillStore` — arm and disarm

**Files:**
- Modify: `src/kel/skills/store.py` (add `arm`, `disarm`)
- Test: `tests/test_skills_store.py` (append)

**Interfaces:**
- Produces: `SkillStore.arm(name) -> bool` and `SkillStore.disarm(name) -> bool` — flip `enabled` in that skill's `skill.json` and persist; return `False` if no such skill.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_skills_store.py`:

```python
def test_arm_turns_a_skill_on_and_persists(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet", enabled=False)
    store = SkillStore(tmp_path)

    assert store.arm("greet") is True
    assert [s.name for s in store.armed()] == ["greet"]
    # Persisted, so a fresh store sees it too.
    assert [s.name for s in SkillStore(tmp_path).armed()] == ["greet"]


def test_disarm_turns_a_skill_off_and_persists(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet", enabled=True)
    store = SkillStore(tmp_path)

    assert store.disarm("greet") is True
    assert store.armed() == []
    assert SkillStore(tmp_path).armed() == []


def test_arming_an_unknown_skill_returns_false(tmp_path: Path) -> None:
    store = SkillStore(tmp_path)

    assert store.arm("ghost") is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_skills_store.py -q -k arm`
Expected: FAIL — `AttributeError: 'SkillStore' object has no attribute 'arm'`.

- [ ] **Step 3: Implement arm/disarm**

In `src/kel/skills/store.py`, add these methods to `SkillStore` (after `get`):

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skills_store.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/store.py tests/test_skills_store.py
git add src/kel/skills/store.py tests/test_skills_store.py
git commit -m "feat(skills): arm and disarm skills by persisting the manifest gate"
```

---

### Task 5: The subprocess runner

**Files:**
- Create: `src/kel/skills/runner.py`
- Test: `tests/test_skills_runner.py`

**Interfaces:**
- Produces: `python -m kel.skills.runner <skill_dir>` — reads a JSON object from stdin, imports `<skill_dir>/skill.py`, calls its `run(**args)`, writes `str(result)` to stdout. An empty stdin means no args. Uncaught exceptions propagate (non-zero exit, traceback on stderr). Also exposes `main(argv: list[str] | None = None) -> None` for direct calls.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skills_runner.py`:

```python
import subprocess
import sys
from pathlib import Path


def write_runner_skill(root: Path, code: str) -> Path:
    directory = root / "greet"
    directory.mkdir(parents=True)
    (directory / "skill.py").write_text(code)
    return directory


def run_runner(skill_dir: Path, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "kel.skills.runner", str(skill_dir)],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_runner_calls_run_with_args_and_prints_the_result(tmp_path: Path) -> None:
    skill_dir = write_runner_skill(
        tmp_path, "def run(name):\n    return f'hello {name}'\n"
    )

    result = run_runner(skill_dir, '{"name": "Kel"}')

    assert result.returncode == 0
    assert result.stdout == "hello Kel"


def test_runner_handles_empty_stdin_as_no_args(tmp_path: Path) -> None:
    skill_dir = write_runner_skill(tmp_path, "def run():\n    return 'no args'\n")

    result = run_runner(skill_dir, "")

    assert result.returncode == 0
    assert result.stdout == "no args"


def test_runner_exits_nonzero_when_the_skill_raises(tmp_path: Path) -> None:
    skill_dir = write_runner_skill(
        tmp_path, "def run():\n    raise ValueError('boom')\n"
    )

    result = run_runner(skill_dir, "{}")

    assert result.returncode != 0
    assert "boom" in result.stderr
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skills_runner.py -q`
Expected: FAIL — the module `kel.skills.runner` does not exist (non-zero exit, "No module named").

- [ ] **Step 3: Implement the runner**

Create `src/kel/skills/runner.py`:

```python
"""Run one skill in its own process: JSON args on stdin, string result on stdout.

Invoked as ``python -m kel.skills.runner <skill_dir>``. It imports the skill's
``skill.py`` by path, so only that file's own imports load here — nothing else of
Kel is pulled in. Any exception the skill raises propagates and exits non-zero.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: python -m kel.skills.runner <skill_dir>")
    skill_dir = Path(args[0])
    raw = sys.stdin.read()
    params = json.loads(raw) if raw.strip() else {}

    spec = importlib.util.spec_from_file_location("kel_active_skill", skill_dir / "skill.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load a skill at {skill_dir}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.run(**params)
    sys.stdout.write(str(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_skills_runner.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/runner.py tests/test_skills_runner.py
git add src/kel/skills/runner.py tests/test_skills_runner.py
git commit -m "feat(skills): add the subprocess skill runner"
```

---

### Task 6: The executor (spawn, timeout, error mapping)

**Files:**
- Create: `src/kel/skills/executor.py`
- Test: `tests/test_skills_executor.py`

**Interfaces:**
- Consumes: `Skill`, `SkillResult` (Task 2); the runner (Task 5).
- Produces: `run_skill(skill: Skill, args: dict, *, timeout: float, python: str | None = None) -> SkillResult`. Success → `ok=True, output=<stdout>`. Timeout → `ok=False, output="skill '<name>' timed out after <N>s"`. Crash/non-zero → `ok=False, output="skill '<name>' failed: <last stderr line>"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skills_executor.py`:

```python
import json
from pathlib import Path

from kel.skills.contracts import Skill
from kel.skills.executor import run_skill


def make_skill(tmp_path: Path, code: str, name: str = "greet") -> Skill:
    directory = tmp_path / name
    directory.mkdir(parents=True)
    (directory / "skill.py").write_text(code)
    (directory / "skill.json").write_text(json.dumps({"name": name}))
    return Skill(
        name=name,
        description="",
        parameters={"type": "object", "properties": {}},
        enabled=True,
        author="kel",
        created_at="",
        version=1,
        directory=directory,
    )


def test_run_skill_returns_the_output_on_success(tmp_path: Path) -> None:
    skill = make_skill(tmp_path, "def run(name):\n    return f'hi {name}'\n")

    result = run_skill(skill, {"name": "Kel"}, timeout=10)

    assert result.ok is True
    assert result.output == "hi Kel"


def test_run_skill_reports_a_crash_as_a_failure_string(tmp_path: Path) -> None:
    skill = make_skill(tmp_path, "def run():\n    raise ValueError('kaboom')\n")

    result = run_skill(skill, {}, timeout=10)

    assert result.ok is False
    assert "greet" in result.output
    assert "failed" in result.output


def test_run_skill_reports_a_timeout(tmp_path: Path) -> None:
    skill = make_skill(tmp_path, "import time\n\ndef run():\n    time.sleep(5)\n")

    result = run_skill(skill, {}, timeout=1)

    assert result.ok is False
    assert "timed out" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_skills_executor.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.executor'`.

- [ ] **Step 3: Implement the executor**

Create `src/kel/skills/executor.py`:

```python
"""Run a skill in an isolated subprocess with a timeout, failures mapped to text.

The subprocess is for stability, not security: a broken or hung skill cannot wedge
the live voice session, and a timeout kills it. Skill code still runs with full
user privileges, exactly like the shell tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from kel.skills.contracts import Skill, SkillResult


def run_skill(
    skill: Skill,
    args: dict[str, Any],
    *,
    timeout: float,
    python: str | None = None,
) -> SkillResult:
    """Run one skill and return its result, never raising for a bad skill."""
    interpreter = python or sys.executable
    try:
        proc = subprocess.run(
            [interpreter, "-m", "kel.skills.runner", str(skill.directory)],
            input=json.dumps(args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SkillResult(ok=False, output=f"skill '{skill.name}' timed out after {int(timeout)}s")
    if proc.returncode == 0:
        return SkillResult(ok=True, output=proc.stdout)
    lines = [line for line in proc.stderr.strip().splitlines() if line.strip()]
    reason = lines[-1] if lines else "unknown error"
    return SkillResult(ok=False, output=f"skill '{skill.name}' failed: {reason}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skills_executor.py -q`
Expected: PASS (the timeout test takes ~1s).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/executor.py tests/test_skills_executor.py
git add src/kel/skills/executor.py tests/test_skills_executor.py
git commit -m "feat(skills): add the subprocess executor with timeout and error mapping"
```

---

### Task 7: The `kel-skills` CLI

**Files:**
- Create: `src/kel/skills/skills_cli.py`
- Modify: `pyproject.toml` (add the `kel-skills` script)
- Test: `tests/test_skills_cli.py`

**Interfaces:**
- Consumes: `Settings` (Task 1), `SkillStore` (Tasks 3–4), `run_skill` (Task 6), `BUILTIN_TOOL_NAMES` (Task 2).
- Produces: `main(argv: list[str] | None = None) -> None` handling `list`, `arm <name>`, `disarm <name>`, `run <name> [json]`. Console script `kel-skills = "kel.skills.skills_cli:main"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skills_cli.py`:

```python
import json
from pathlib import Path

from kel.skills.skills_cli import main


def write_skill(root: Path, name: str, *, enabled: bool = False) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "skill.json").write_text(
        json.dumps(
            {
                "name": name,
                "description": f"{name} skill",
                "parameters": {"type": "object", "properties": {}},
                "enabled": enabled,
                "author": "kel",
                "created_at": "2026-07-08T00:00:00Z",
                "version": 1,
            }
        )
    )
    (directory / "skill.py").write_text("def run(**kwargs):\n    return 'ran ' + repr(kwargs)\n")


def prepare_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("KEL_SKILLS_PATH", str(tmp_path))


def test_list_shows_every_skill_and_its_state(monkeypatch, tmp_path, capsys) -> None:
    write_skill(tmp_path, "greet", enabled=True)
    write_skill(tmp_path, "quiet", enabled=False)
    prepare_env(monkeypatch, tmp_path)

    main(["list"])

    out = capsys.readouterr().out
    assert "greet" in out
    assert "quiet" in out
    assert "on" in out
    assert "off" in out


def test_arm_turns_a_skill_on(monkeypatch, tmp_path, capsys) -> None:
    write_skill(tmp_path, "greet", enabled=False)
    prepare_env(monkeypatch, tmp_path)

    main(["arm", "greet"])

    assert json.loads((tmp_path / "greet" / "skill.json").read_text())["enabled"] is True


def test_run_executes_a_skill_and_prints_its_output(monkeypatch, tmp_path, capsys) -> None:
    write_skill(tmp_path, "greet", enabled=True)
    prepare_env(monkeypatch, tmp_path)

    main(["run", "greet", '{"who": "you"}'])

    out = capsys.readouterr().out
    assert "who" in out
    assert "you" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_skills_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.skills_cli'`.

- [ ] **Step 3: Implement the CLI**

Create `src/kel/skills/skills_cli.py`:

```python
"""Manage Kel's skills from the terminal: list, arm, disarm, run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kel.config.settings import Settings
from kel.realtime.options import BUILTIN_TOOL_NAMES
from kel.skills.executor import run_skill
from kel.skills.store import SkillStore


def _store(settings: Settings) -> SkillStore:
    root = Path(settings.skills_path).expanduser()
    return SkillStore(root, reserved_names=BUILTIN_TOOL_NAMES)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage Kel's skills.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list every skill and whether it is armed")
    arm = sub.add_parser("arm", help="turn a skill on")
    arm.add_argument("name")
    disarm = sub.add_parser("disarm", help="turn a skill off")
    disarm.add_argument("name")
    run = sub.add_parser("run", help="run a skill once with JSON args")
    run.add_argument("name")
    run.add_argument("args", nargs="?", default="{}")
    parsed = parser.parse_args(argv)

    settings = Settings.from_env()
    store = _store(settings)

    if parsed.command == "list":
        skills = store.all()
        if not skills:
            print("No skills yet.")
        for skill in skills:
            state = "on " if skill.enabled else "off"
            print(f"[{state}] {skill.name} — {skill.description}")
        return
    if parsed.command == "arm":
        print("armed" if store.arm(parsed.name) else f"no skill named {parsed.name}")
        return
    if parsed.command == "disarm":
        print("disarmed" if store.disarm(parsed.name) else f"no skill named {parsed.name}")
        return
    if parsed.command == "run":
        skill = store.get(parsed.name)
        if skill is None:
            print(f"no skill named {parsed.name}")
            return
        result = run_skill(skill, json.loads(parsed.args), timeout=settings.skills_timeout_seconds)
        print(result.output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Register the console script**

In `pyproject.toml`, under `[project.scripts]`, after `kel-face = "kel.face.app:main"`, add:

```toml
kel-skills = "kel.skills.skills_cli:main"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skills_cli.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src/kel/skills/skills_cli.py tests/test_skills_cli.py
git add src/kel/skills/skills_cli.py tests/test_skills_cli.py pyproject.toml
git commit -m "feat(skills): add the kel-skills CLI (list, arm, disarm, run)"
```

---

### Task 8: OpenAI session — expose armed skills and dispatch calls

**Files:**
- Modify: `src/kel/realtime/options.py` (`api_payload` gains `extra_tools`)
- Modify: `src/kel/realtime/session.py` (accept `skills`/`skills_timeout`, expose specs, dispatch fallback)
- Test: `tests/test_realtime_session.py` (append), `tests/test_realtime_options.py` (append)

**Interfaces:**
- Consumes: `SkillStore` (Tasks 3–4), `run_skill` (Task 6).
- Produces: `RealtimeSessionOptions.api_payload(*, instructions, extra_tools=None)`. `RealtimeVoiceSession(..., skills: SkillStore | None = None, skills_timeout: float = 20.0)`. A tool call whose name is not a built-in runs the matching armed skill and returns its output; an unknown/unarmed name replies with a clear "no skill" string.

- [ ] **Step 1: Write the failing option test**

Append to `tests/test_realtime_options.py`:

```python
def test_api_payload_appends_extra_tools() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )
    extra = [{"type": "function", "name": "make_qr_code", "description": "x", "parameters": {}}]

    payload = options.api_payload(instructions="x", extra_tools=extra)

    names = {tool["name"] for tool in payload["tools"]}
    assert "make_qr_code" in names
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_options.py -q -k extra_tools`
Expected: FAIL — `TypeError: api_payload() got an unexpected keyword argument 'extra_tools'`.

- [ ] **Step 3: Add `extra_tools` to `api_payload`**

Two precise edits to `RealtimeSessionOptions.api_payload` in `src/kel/realtime/options.py`, leaving the `payload` dict body untouched.

Edit A — change the signature line from:

```python
    def api_payload(self, *, instructions: str) -> dict[str, Any]:
```

to:

```python
    def api_payload(
        self, *, instructions: str, extra_tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
```

Edit B — insert two lines so the existing tail changes from:

```python
        tools = self.tool_specs()
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload
```

to:

```python
        tools = self.tool_specs()
        if extra_tools:
            tools = [*tools, *extra_tools]
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload
```

- [ ] **Step 4: Run the option test to verify it passes**

Run: `uv run pytest tests/test_realtime_options.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing session tests**

Append to `tests/test_realtime_session.py`:

```python
import json as _json
from pathlib import Path

from kel.skills.store import SkillStore


def write_session_skill(root: Path, name: str, code: str, *, enabled: bool = True) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    directory.joinpath("skill.json").write_text(
        _json.dumps(
            {
                "name": name,
                "description": f"{name} skill",
                "parameters": {"type": "object", "properties": {"who": {"type": "string"}}},
                "enabled": enabled,
                "author": "kel",
                "created_at": "2026-07-08T00:00:00Z",
                "version": 1,
            }
        )
    )
    directory.joinpath("skill.py").write_text(code)


def build_skill_session(store: SkillStore, events: list[object]) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        skills=store,
        skills_timeout=10,
    )


def test_a_tool_call_for_an_armed_skill_runs_it_and_returns_output(tmp_path: Path) -> None:
    write_session_skill(tmp_path, "greet", "def run(who):\n    return f'hi {who}'\n")
    session = build_skill_session(SkillStore(tmp_path), [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("greet", {"who": "Kel"}), connection))

    assert items.created[0]["type"] == "function_call_output"
    assert items.created[0]["output"] == "hi Kel"
    assert responses.count == 1


def test_a_tool_call_for_an_unknown_skill_replies_gracefully(tmp_path: Path) -> None:
    session = build_skill_session(SkillStore(tmp_path), [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("ghost", {}), connection))

    assert "ghost" in items.created[0]["output"]
    assert responses.count == 1
```

- [ ] **Step 6: Run the session tests to verify they fail**

Run: `uv run pytest tests/test_realtime_session.py -q -k skill`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'skills'`.

- [ ] **Step 7: Wire skills into the session**

In `src/kel/realtime/session.py`:

Add imports near the other `kel` imports:

```python
from kel.skills.executor import run_skill
from kel.skills.store import SkillStore
```

Add two constructor parameters (place them at the end of the `__init__` keyword list, e.g. after `orb: Any | None = None,`):

```python
        skills: SkillStore | None = None,
        skills_timeout: float = 20.0,
```

Store them in `__init__`'s body (near `self._orb = orb`):

```python
        self._skills = skills
        self._skills_timeout = skills_timeout
```

Change the payload build in `run()` from:

```python
            await connection.session.update(
                session=self._options.api_payload(instructions=self._instructions)
            )
```

to:

```python
            await connection.session.update(
                session=self._options.api_payload(
                    instructions=self._instructions, extra_tools=self._skill_specs()
                )
            )
```

Add a fallback branch at the end of `_handle_tool_call` (after the `SWIPE_DESKTOP_TOOL_NAME` branch):

```python
        else:
            await self._run_skill(event, connection)
```

Add these two methods (e.g. just after `_handle_tool_call`):

```python
    def _skill_specs(self) -> list[dict[str, Any]]:
        return self._skills.tool_specs() if self._skills is not None else []

    async def _run_skill(self, event: Any, connection: Any) -> None:
        """Run a matching armed skill and feed its output back to the model."""
        name = getattr(event, "name", "") or ""
        skill = self._skills.get(name) if self._skills is not None else None
        if skill is None or not skill.enabled:
            await self._reply_to_tool(
                connection, event.call_id, f"I don't have a skill called {name}."
            )
            return
        try:
            args = json.loads(getattr(event, "arguments", "") or "{}")
        except ValueError:
            args = {}
        self._emit("acted", f"Running skill: {name}")
        result = await asyncio.to_thread(run_skill, skill, args, timeout=self._skills_timeout)
        await self._reply_to_tool(connection, event.call_id, result.output)
```

- [ ] **Step 8: Run the session tests to verify they pass**

Run: `uv run pytest tests/test_realtime_session.py -q`
Expected: PASS (new skill tests and all existing ones).

- [ ] **Step 9: Lint and commit**

```bash
uv run ruff check src/kel/realtime/options.py src/kel/realtime/session.py tests/test_realtime_session.py tests/test_realtime_options.py
git add src/kel/realtime/options.py src/kel/realtime/session.py tests/test_realtime_session.py tests/test_realtime_options.py
git commit -m "feat(skills): expose and dispatch skills in the OpenAI realtime session"
```

---

### Task 9: Gemini session dispatch + application wiring

**Files:**
- Modify: `src/kel/realtime/gemini_session.py` (accept `skills`/`skills_timeout`, append specs, dispatch fallback)
- Modify: `src/kel/realtime/app.py` (build the store, pass it into both sessions)
- Test: `tests/test_gemini_session.py` (append)

**Interfaces:**
- Consumes: `SkillStore` (Tasks 3–4), `run_skill` (Task 6), `BUILTIN_TOOL_NAMES` (Task 2), `Settings.skills_*` (Task 1).
- Produces: `GeminiVoiceSession(..., skills: SkillStore | None = None, skills_timeout: float = 20.0)` with the same dispatch behavior as the OpenAI session. `build_realtime_session` constructs a `SkillStore` when `settings.skills_enabled` and passes `skills`/`skills_timeout` to whichever session it builds.

- [ ] **Step 1: Write the failing Gemini test**

Append to `tests/test_gemini_session.py` (match the file's existing imports/fakes; this test only exercises `_run_tool`, which touches no audio):

```python
import json as _json
from pathlib import Path
from types import SimpleNamespace

from kel.realtime.gemini_session import GeminiVoiceSession
from kel.realtime.options import RealtimeSessionOptions
from kel.skills.store import SkillStore


def _skill_options() -> RealtimeSessionOptions:
    from kel.config.settings import Settings

    return RealtimeSessionOptions.from_settings(Settings.from_mapping({"OPENAI_API_KEY": "k"}))


def _build_gemini_skill_session(store: SkillStore) -> GeminiVoiceSession:
    return GeminiVoiceSession(
        api_key="unused",
        model="test-model",
        voice="Leda",
        instructions="Be Kel.",
        options=_skill_options(),
        microphone=SimpleNamespace(),
        speaker=SimpleNamespace(),
        on_event=lambda _event: None,
        client=SimpleNamespace(),
        skills=store,
        skills_timeout=10,
    )


def _write_gemini_skill(root: Path, name: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    directory.joinpath("skill.json").write_text(
        _json.dumps(
            {
                "name": name,
                "description": "greet",
                "parameters": {"type": "object", "properties": {"who": {"type": "string"}}},
                "enabled": True,
                "author": "kel",
                "created_at": "2026-07-08T00:00:00Z",
                "version": 1,
            }
        )
    )
    directory.joinpath("skill.py").write_text("def run(who):\n    return f'hi {who}'\n")


def test_gemini_runs_an_armed_skill_tool(tmp_path: Path) -> None:
    import asyncio

    _write_gemini_skill(tmp_path, "greet")
    session = _build_gemini_skill_session(SkillStore(tmp_path))

    output, image = asyncio.run(session._run_tool("greet", {"who": "Kel"}))

    assert output == "hi Kel"
    assert image is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_gemini_session.py -q -k skill`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'skills'`.

- [ ] **Step 3: Wire skills into the Gemini session**

In `src/kel/realtime/gemini_session.py`:

Add imports near the other `kel` imports:

```python
from kel.skills.executor import run_skill
from kel.skills.store import SkillStore
```

Add the two constructor parameters (end of the `__init__` keyword list, after `orb: Any | None = None,`):

```python
        skills: SkillStore | None = None,
        skills_timeout: float = 20.0,
```

Store them in the body (near `self._orb = orb`):

```python
        self._skills = skills
        self._skills_timeout = skills_timeout
```

In `_build_config`, change the tools line from:

```python
        tools = gemini_tools(self._options.tool_specs())
```

to:

```python
        tools = gemini_tools([*self._options.tool_specs(), *self._skill_specs()])
```

Replace the final fallthrough of `_run_tool` — the line `return "I don't have that tool.", None` — with:

```python
        skill = self._skills.get(name) if self._skills is not None else None
        if skill is not None and skill.enabled:
            result = await asyncio.to_thread(
                run_skill, skill, args, timeout=self._skills_timeout
            )
            return result.output, None
        return "I don't have that tool.", None
```

Add the helper (e.g. next to `_arg`):

```python
    def _skill_specs(self) -> list[dict[str, Any]]:
        return self._skills.tool_specs() if self._skills is not None else []
```

- [ ] **Step 4: Run the Gemini test to verify it passes**

Run: `uv run pytest tests/test_gemini_session.py -q`
Expected: PASS.

- [ ] **Step 5: Wire the store into `build_realtime_session`**

In `src/kel/realtime/app.py`, after the `body`/`close_body` block and before `shared = dict(...)`, add:

```python
    skills = None
    if settings.skills_enabled:
        from pathlib import Path

        from kel.realtime.options import BUILTIN_TOOL_NAMES
        from kel.skills.store import SkillStore

        skills = SkillStore(
            Path(settings.skills_path).expanduser(),
            reserved_names=BUILTIN_TOOL_NAMES,
        )
```

Then, inside the `shared` dict, after `orb=orb,`, add:

```python
        skills=skills,
        skills_timeout=settings.skills_timeout_seconds,
```

- [ ] **Step 6: Verify the whole suite still passes**

Run: `uv run pytest -q`
Expected: PASS (full suite; `shared` now carries `skills`/`skills_timeout`, which both session constructors accept).

- [ ] **Step 7: Manual smoke check of the end-to-end runtime**

The store wiring in `app.py` has no unit test (constructing a live session needs audio hardware), so verify it by hand:

```bash
mkdir -p ~/.kel/skills/say_hi
printf '%s\n' 'def run(who="world"):' '    return f"hello {who}"' > ~/.kel/skills/say_hi/skill.py
cat > ~/.kel/skills/say_hi/skill.json <<'JSON'
{"name":"say_hi","description":"Say hi to someone.","parameters":{"type":"object","properties":{"who":{"type":"string"}}},"enabled":false,"author":"user","created_at":"2026-07-08T00:00:00Z","version":1}
JSON
uv run kel-skills list          # expect: [off] say_hi — Say hi to someone.
uv run kel-skills arm say_hi    # expect: armed
uv run kel-skills run say_hi '{"who":"Kel"}'   # expect: hello Kel
```

Expected: the three commands print the annotated outputs. (Leaving `say_hi` armed is fine, or `uv run kel-skills disarm say_hi` to reset.)

- [ ] **Step 8: Lint and commit**

```bash
uv run ruff check src/kel/realtime/gemini_session.py src/kel/realtime/app.py tests/test_gemini_session.py
git add src/kel/realtime/gemini_session.py src/kel/realtime/app.py tests/test_gemini_session.py
git commit -m "feat(skills): dispatch skills in the Gemini session and wire the store into the app"
```

---

### Task 10 (optional): Live re-arm on the OpenAI session

Skippable — the runtime is complete after Task 9 (armed skills load at session start). This adds the nicety that a skill armed *during* a conversation becomes callable on the next turn without a restart, on the OpenAI brain. Gemini Live re-sends tools only on reconnect, so it already picks up newly armed skills on its next session.

**Files:**
- Modify: `src/kel/realtime/options.py` (add `tools_update`)
- Modify: `src/kel/realtime/session.py` (re-send tools when the armed set changes)
- Test: `tests/test_realtime_session.py` (append), `tests/test_realtime_options.py` (append)

**Interfaces:**
- Produces: `RealtimeSessionOptions.tools_update(tool_specs: list[dict]) -> dict` — a partial `session.update` payload carrying a fresh tool list. `RealtimeVoiceSession._sync_skill_tools(connection)` — re-scans armed skills each user turn and pushes a `session.update` only when the set changed.

- [ ] **Step 1: Write the failing option test**

Append to `tests/test_realtime_options.py`:

```python
def test_tools_update_carries_a_fresh_tool_list() -> None:
    options = RealtimeSessionOptions.from_settings(
        Settings.from_mapping({"OPENAI_API_KEY": "test-key"})
    )
    specs = [{"type": "function", "name": "greet", "description": "x", "parameters": {}}]

    payload = options.tools_update(specs)

    assert payload["type"] == "realtime"
    assert payload["tool_choice"] == "auto"
    assert [tool["name"] for tool in payload["tools"]] == ["greet"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_options.py -q -k tools_update`
Expected: FAIL — `AttributeError: 'RealtimeSessionOptions' object has no attribute 'tools_update'`.

- [ ] **Step 3: Add `tools_update`**

In `src/kel/realtime/options.py`, add to `RealtimeSessionOptions` (e.g. after `type_mode_update`):

```python
    def tools_update(self, tool_specs: list[dict[str, Any]]) -> dict[str, Any]:
        """A partial session update that re-declares the available tools."""
        return {"type": "realtime", "tools": tool_specs, "tool_choice": "auto"}
```

- [ ] **Step 4: Run the option test to verify it passes**

Run: `uv run pytest tests/test_realtime_options.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing session test**

Append to `tests/test_realtime_session.py` (reuses `write_session_skill`, `build_skill_session`, `fake_connection`, `transcript_event` from Task 8):

```python
def test_arming_a_skill_mid_session_re_sends_the_tool_list(tmp_path: Path) -> None:
    write_session_skill(tmp_path, "greet", "def run(who=''):\n    return who\n")
    store = SkillStore(tmp_path)
    session = build_skill_session(store, [])
    connection, _, _ = fake_connection()

    async def drive() -> None:
        # First turn establishes the baseline (greet is already armed).
        await session.handle_event(transcript_event("hello"), connection)
        # Arm a second skill, then take another turn.
        write_session_skill(tmp_path, "bye", "def run(who=''):\n    return who\n")
        await session.handle_event(transcript_event("still there?"), connection)

    asyncio.run(drive())

    tool_updates = [u for u in connection.session.updated if "tools" in u]
    assert tool_updates, "expected a session.update carrying tools after arming a new skill"
    assert "bye" in {tool["name"] for tool in tool_updates[-1]["tools"]}
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_session.py -q -k mid_session`
Expected: FAIL — no tools-bearing `session.update` is sent (the assertion on `tool_updates` fails).

- [ ] **Step 7: Implement per-turn re-sync**

In `src/kel/realtime/session.py`:

Initialize a baseline in `__init__` (near `self._skills = skills`):

```python
        self._sent_skill_names: set[str] | None = None
```

At the very start of `_respond_to_transcript`, right after the `if not transcript: return` guard, add:

```python
        await self._sync_skill_tools(connection)
```

Add the method (e.g. after `_run_skill`):

```python
    async def _sync_skill_tools(self, connection: Any) -> None:
        """Re-send the tool list when the armed-skill set changed since last turn."""
        if self._skills is None:
            return
        current = {spec["name"] for spec in self._skill_specs()}
        if self._sent_skill_names is None:
            self._sent_skill_names = current
            return
        if current != self._sent_skill_names:
            self._sent_skill_names = current
            await connection.session.update(
                session=self._options.tools_update(
                    [*self._options.tool_specs(), *self._skill_specs()]
                )
            )
```

- [ ] **Step 8: Run the session tests to verify they pass**

Run: `uv run pytest tests/test_realtime_session.py -q`
Expected: PASS.

- [ ] **Step 9: Lint and commit**

```bash
uv run ruff check src/kel/realtime/options.py src/kel/realtime/session.py tests/test_realtime_session.py tests/test_realtime_options.py
git add src/kel/realtime/options.py src/kel/realtime/session.py tests/test_realtime_session.py tests/test_realtime_options.py
git commit -m "feat(skills): re-send the tool list when a skill is armed mid-session"
```

---

## Final verification

- [ ] Run the whole suite: `uv run pytest -q` — expect all green.
- [ ] Lint everything new: `uv run ruff check src/kel/skills src/kel/realtime tests` — expect no errors.
- [ ] Confirm the manual smoke check from Task 9 Step 7 still works end-to-end.

## Notes for the implementer

- **Nothing here generates skill code** — that is sub-project #2. This plan makes hand-written or dropped-in skills real, callable, and gated. The `run_skill` executor and the `kel-skills run` command are the exact seams #2's "write a skill, test it until it works" loop will drive.
- **The Gemini and OpenAI sessions deliberately mirror each other** (the codebase already duplicates their tool handlers on purpose). Keep the skill hooks parallel: same parameter names, same helper `_skill_specs`, same "unknown → run skill" fallback.
- **Reserved names** flow from `options.BUILTIN_TOOL_NAMES` into the store only via the caller (CLI and `app.py`), so `kel.skills` never imports `kel.realtime` — keep it that way to avoid an import cycle.
