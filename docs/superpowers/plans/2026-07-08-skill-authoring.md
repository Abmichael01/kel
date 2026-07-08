# Skill Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Kel build her own skills on the fly — she calls `build_skill(goal)`, Gemini writes the code, a loop tests it in the #1 sandbox until it works (installing deps, feeding errors back), then auto-arms it and returns the real run's output.

**Architecture:** A new `kel.skills.authoring` package: a `Coder` (Gemini) that drafts a skill from a goal, and a `SkillAuthor` loop that writes → runs (via #1's `executor.run_skill`) → installs missing deps → feeds failures back to the coder → retries → arms on success. A flag-gated `build_skill` tool is exposed to both realtime brains and dispatched to an injected `SkillAuthor`.

**Tech Stack:** Python ≥3.11; `google-genai` (already a dependency) for the coder; stdlib `subprocess`/`json`/`re`; pytest with injected fakes (no network in tests).

## Global Constraints

- **Python ≥ 3.11**, `from __future__ import annotations` at the top of every new module.
- **Ruff**: line-length 100, rules `E, F, I, UP, B, SIM`. Run `uv run ruff check` before each commit; append test imports to the TOP import block (never mid-file — ruff E402).
- **Tests**: plain pytest functions; inject fakes (`FakeCoder`, fake `run`/`install`) — **no network, no real Gemini, no real pip, no real subprocess** except the one explicit end-to-end integration test noted in Task 3. Real objects over mock libraries.
- **Layering**: the core authoring modules (`contracts`, `coder`, `author`) must NOT import `kel.realtime`. Built-in tool names reach `SkillAuthor` via an injected `reserved_names` param (as `SkillStore` does). Only the wiring modules (`authoring/app.py`, `realtime/app.py`) may import both sides.
- **Full autonomy**: a successfully-built skill is written with `enabled: true` (armed) and its real-args test run IS the fulfilment — its output is what `build_skill` returns. No approval step.
- **Isolation is stability, not security** (inherited from #1): generated code runs with full user privileges. Do not add or imply a sandbox.
- **Settings**: new options are `KEL_`-prefixed, parsed in `Settings.from_mapping`, validated with `ConfigurationError`. Mirror existing fields.
- **Commits**: end every commit message with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Work on the current `kel-skills` branch (it carries #1).
- Run a task's tests with `uv run pytest <path> -q`; run the full suite once before each commit.

---

### Task 1: Authoring settings

**Files:**
- Modify: `src/kel/config/settings.py`
- Test: `tests/test_settings.py` (append)

**Interfaces:**
- Produces: `Settings.skills_author_enabled: bool = True` (`KEL_SKILLS_AUTHOR_ENABLED`), `Settings.coder_model: str = "gemini-2.5-flash"` (`KEL_CODER_MODEL`), `Settings.skills_author_max_attempts: int = 4` (`KEL_SKILLS_AUTHOR_MAX_ATTEMPTS`, positive int), `Settings.skills_author_allow_pip: bool = True` (`KEL_SKILLS_AUTHOR_ALLOW_PIP`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_settings.py`:

```python
def test_skill_authoring_defaults() -> None:
    settings = Settings.from_mapping({"OPENAI_API_KEY": "test-key"})

    assert settings.skills_author_enabled is True
    assert settings.coder_model == "gemini-2.5-flash"
    assert settings.skills_author_max_attempts == 4
    assert settings.skills_author_allow_pip is True


def test_skill_authoring_can_be_configured() -> None:
    settings = Settings.from_mapping(
        {
            "OPENAI_API_KEY": "test-key",
            "KEL_SKILLS_AUTHOR_ENABLED": "false",
            "KEL_CODER_MODEL": "gemini-3-flash",
            "KEL_SKILLS_AUTHOR_MAX_ATTEMPTS": "6",
            "KEL_SKILLS_AUTHOR_ALLOW_PIP": "false",
        }
    )

    assert settings.skills_author_enabled is False
    assert settings.coder_model == "gemini-3-flash"
    assert settings.skills_author_max_attempts == 6
    assert settings.skills_author_allow_pip is False


def test_a_non_positive_author_attempts_is_rejected() -> None:
    import pytest

    from kel.config.settings import ConfigurationError

    with pytest.raises(ConfigurationError):
        Settings.from_mapping(
            {"OPENAI_API_KEY": "test-key", "KEL_SKILLS_AUTHOR_MAX_ATTEMPTS": "0"}
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_settings.py -q -k author`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'skills_author_enabled'`.

- [ ] **Step 3: Add the fields**

In the `Settings` dataclass body, after `skills_timeout_seconds: int = 20`:

```python
    skills_author_enabled: bool = True
    coder_model: str = "gemini-2.5-flash"
    skills_author_max_attempts: int = 4
    skills_author_allow_pip: bool = True
```

- [ ] **Step 4: Parse and validate in `from_mapping`**

Alongside the other parsing (after the `skills_timeout_text` line from #1):

```python
        skills_author_enabled = _parse_bool(
            values.get("KEL_SKILLS_AUTHOR_ENABLED", "true"), "KEL_SKILLS_AUTHOR_ENABLED"
        )
        coder_model = values.get("KEL_CODER_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        author_attempts_text = values.get("KEL_SKILLS_AUTHOR_MAX_ATTEMPTS", "4").strip()
        skills_author_allow_pip = _parse_bool(
            values.get("KEL_SKILLS_AUTHOR_ALLOW_PIP", "true"), "KEL_SKILLS_AUTHOR_ALLOW_PIP"
        )
```

Add validation next to the `skills_timeout_seconds` check:

```python
        try:
            skills_author_max_attempts = int(author_attempts_text)
        except ValueError as error:
            raise ConfigurationError("KEL_SKILLS_AUTHOR_MAX_ATTEMPTS must be an integer.") from error
        if skills_author_max_attempts <= 0:
            raise ConfigurationError("KEL_SKILLS_AUTHOR_MAX_ATTEMPTS must be positive.")
```

Pass into the returned `cls(...)`, after the `skills_timeout_seconds=` line:

```python
            skills_author_enabled=skills_author_enabled,
            coder_model=coder_model,
            skills_author_max_attempts=skills_author_max_attempts,
            skills_author_allow_pip=skills_author_allow_pip,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_settings.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src/kel/config/settings.py tests/test_settings.py
git add src/kel/config/settings.py tests/test_settings.py
git commit -m "feat(authoring): add skill-authoring settings"
```

---

### Task 2: Authoring contracts

**Files:**
- Create: `src/kel/skills/authoring/__init__.py`
- Create: `src/kel/skills/authoring/contracts.py`
- Test: `tests/test_authoring_contracts.py`

**Interfaces:**
- Produces: `DraftSkill(name, description, parameters: dict, code: str, invocation_args: dict)` and `AuthorOutcome(ok: bool, output: str, skill_name: str | None = None, attempts: int = 0)` — both frozen dataclasses.

- [ ] **Step 1: Write the failing test**

Create `tests/test_authoring_contracts.py`:

```python
from kel.skills.authoring.contracts import AuthorOutcome, DraftSkill


def test_draft_skill_holds_the_generated_pieces() -> None:
    draft = DraftSkill(
        name="make_qr_code",
        description="Make a QR code.",
        parameters={"type": "object", "properties": {}},
        code="def run():\n    return 'ok'\n",
        invocation_args={"text": "hi"},
    )

    assert draft.name == "make_qr_code"
    assert draft.invocation_args == {"text": "hi"}


def test_author_outcome_defaults() -> None:
    outcome = AuthorOutcome(ok=True, output="done")

    assert outcome.ok is True
    assert outcome.skill_name is None
    assert outcome.attempts == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_authoring_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.authoring'`.

- [ ] **Step 3: Create the package and contracts**

Create `src/kel/skills/authoring/__init__.py`:

```python
"""Kel writes her own skills: a coder + a build/test/arm loop."""
```

Create `src/kel/skills/authoring/contracts.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_authoring_contracts.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/authoring tests/test_authoring_contracts.py
git add src/kel/skills/authoring/__init__.py src/kel/skills/authoring/contracts.py tests/test_authoring_contracts.py
git commit -m "feat(authoring): add DraftSkill and AuthorOutcome contracts"
```

---

### Task 3: The `SkillAuthor` loop

**Files:**
- Create: `src/kel/skills/authoring/author.py`
- Test: `tests/test_skill_author.py`

**Interfaces:**
- Consumes: `DraftSkill`/`AuthorOutcome` (Task 2); `Skill`/`SkillResult` and `run_skill` from `kel.skills` (#1).
- Produces: `SkillAuthor(*, coder, store, root: Path, reserved_names=frozenset(), max_attempts=4, timeout=20.0, allow_pip=True, run=run_skill, install=None, install_budget=3)` with `build(goal: str) -> AuthorOutcome`. `coder` is any object with `draft(goal: str, feedback: str | None) -> DraftSkill`. `install` defaults to a real `pip install <module>`-returns-bool; tests inject a fake. On success the skill folder is written armed (`enabled: true`) under `root`; on total failure the folder is removed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_author.py`:

```python
import json
from pathlib import Path

from kel.skills.authoring.author import SkillAuthor
from kel.skills.authoring.contracts import DraftSkill
from kel.skills.contracts import SkillResult


class ScriptedCoder:
    """Returns pre-scripted drafts and records the feedback it was given."""

    def __init__(self, drafts: list[DraftSkill]) -> None:
        self._drafts = list(drafts)
        self.feedbacks: list[str | None] = []

    def draft(self, goal: str, feedback: str | None = None) -> DraftSkill:
        self.feedbacks.append(feedback)
        return self._drafts.pop(0)


def a_draft(name: str = "greet", code: str = "def run(who):\n    return f'hi {who}'\n") -> DraftSkill:
    return DraftSkill(
        name=name,
        description=f"{name} skill",
        parameters={"type": "object", "properties": {"who": {"type": "string"}}},
        code=code,
        invocation_args={"who": "Kel"},
    )


def make_store(tmp_path: Path):
    from kel.skills.store import SkillStore

    return SkillStore(tmp_path)


def test_build_succeeds_on_the_first_draft_and_arms_the_skill(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft()])
    fake_run = lambda skill, args, *, timeout: SkillResult(ok=True, output=f"hi {args['who']}")
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run)

    outcome = author.build("say hi to Kel")

    assert outcome.ok is True
    assert outcome.output == "hi Kel"
    assert outcome.skill_name == "greet"
    assert outcome.attempts == 1
    manifest = json.loads((tmp_path / "greet" / "skill.json").read_text())
    assert manifest["enabled"] is True  # auto-armed
    assert (tmp_path / "greet" / "skill.py").exists()


def test_build_feeds_the_error_back_and_retries(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft(code="broken"), a_draft()])
    results = [SkillResult(ok=False, output="skill 'greet' failed: boom"), SkillResult(ok=True, output="hi Kel")]
    fake_run = lambda skill, args, *, timeout: results.pop(0)
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run)

    outcome = author.build("say hi")

    assert outcome.ok is True
    assert outcome.attempts == 2
    # The second draft was asked for WITH the first failure as feedback.
    assert coder.feedbacks == [None, "skill 'greet' failed: boom"]


def test_build_gives_up_after_max_attempts_and_removes_the_folder(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft(name="greet"), a_draft(name="greet"), a_draft(name="greet")])
    fake_run = lambda skill, args, *, timeout: SkillResult(ok=False, output="skill 'greet' failed: nope")
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run, max_attempts=3)

    outcome = author.build("do a thing")

    assert outcome.ok is False
    assert outcome.attempts == 3
    assert "nope" in outcome.output
    assert not (tmp_path / "greet").exists()  # cleaned up


def test_build_treats_a_coder_error_as_a_failed_attempt(tmp_path: Path) -> None:
    class RaisingThenOkCoder:
        def __init__(self) -> None:
            self.calls = 0

        def draft(self, goal: str, feedback: str | None = None) -> DraftSkill:
            self.calls += 1
            if self.calls == 1:
                raise ValueError("bad JSON from model")
            return a_draft()

    coder = RaisingThenOkCoder()
    fake_run = lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel")
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run)

    outcome = author.build("say hi")

    assert outcome.ok is True
    assert outcome.attempts == 2  # the raised draft counted as attempt 1


def test_build_installs_a_missing_dependency_then_reruns(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft()])
    results = [
        SkillResult(ok=False, output="skill 'greet' failed: ModuleNotFoundError: No module named 'qrcode'"),
        SkillResult(ok=True, output="hi Kel"),
    ]
    fake_run = lambda skill, args, *, timeout: results.pop(0)
    installed: list[str] = []
    fake_install = lambda module: (installed.append(module) or True)
    author = SkillAuthor(
        coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run, install=fake_install
    )

    outcome = author.build("make a qr code")

    assert outcome.ok is True
    assert installed == ["qrcode"]
    assert outcome.attempts == 1  # dep install re-runs the SAME draft, not a new coder attempt


def test_build_suffixes_a_name_that_collides_with_an_existing_skill(tmp_path: Path) -> None:
    # Pre-existing skill named "greet".
    existing = tmp_path / "greet"
    existing.mkdir()
    (existing / "skill.py").write_text("def run():\n    return 'x'\n")
    (existing / "skill.json").write_text(
        json.dumps({"name": "greet", "parameters": {"type": "object", "properties": {}}})
    )
    coder = ScriptedCoder([a_draft(name="greet")])
    fake_run = lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel")
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path, run=fake_run)

    outcome = author.build("say hi")

    assert outcome.skill_name == "greet_2"
    assert (tmp_path / "greet_2" / "skill.py").exists()


def test_build_end_to_end_with_the_real_runner(tmp_path: Path) -> None:
    # No fake run: exercise the real #1 executor/runner subprocess for one success.
    coder = ScriptedCoder([a_draft()])
    author = SkillAuthor(coder=coder, store=make_store(tmp_path), root=tmp_path)

    outcome = author.build("say hi to Kel")

    assert outcome.ok is True
    assert outcome.output == "hi Kel"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_skill_author.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.authoring.author'`.

- [ ] **Step 3: Implement the author loop**

Create `src/kel/skills/authoring/author.py`:

```python
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
            except Exception as error:  # noqa: BLE001 - a bad draft is a failed attempt, not a crash
                last_error = f"the coder produced an unusable draft: {error}"
                feedback = last_error
                continue
            name = self._resolve_name(draft.name)
            directory = self._write(name, draft, enabled=False)
            result = self._run_with_deps(name, directory, draft.invocation_args)
            if result.ok:
                self._arm(name, draft, directory)
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

    def _arm(self, name: str, draft: DraftSkill, directory: Path) -> None:
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_skill_author.py -q`
Expected: PASS (the last test runs a real subprocess — ~1s).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/authoring/author.py tests/test_skill_author.py
git add src/kel/skills/authoring/author.py tests/test_skill_author.py
git commit -m "feat(authoring): add the SkillAuthor build/test/fix/arm loop"
```

---

### Task 4: The Gemini coder

**Files:**
- Create: `src/kel/skills/authoring/coder.py`
- Test: `tests/test_authoring_coder.py`

**Interfaces:**
- Consumes: `DraftSkill` (Task 2).
- Produces: `GeminiCoder(*, api_key: str, model: str, client=None)` with `draft(goal, feedback=None) -> DraftSkill`. A module function `parse_draft(text: str) -> DraftSkill` (strips ```json fences, `json.loads`, validates shape, raises `ValueError` on bad shape) and `build_contents(goal, feedback) -> str`. The coder must NOT import `kel.realtime`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_authoring_coder.py`:

```python
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
    bad = json.dumps({"name": "x", "description": "", "parameters": {}, "code": "print(1)", "invocation_args": {}})
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_authoring_coder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'kel.skills.authoring.coder'`.

- [ ] **Step 3: Implement the coder**

Create `src/kel/skills/authoring/coder.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_authoring_coder.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/skills/authoring/coder.py tests/test_authoring_coder.py
git add src/kel/skills/authoring/coder.py tests/test_authoring_coder.py
git commit -m "feat(authoring): add the Gemini coder and draft JSON parsing"
```

---

### Task 5: The `build_skill` tool + author factory

**Files:**
- Modify: `src/kel/realtime/options.py` (tool + name + `skills_author_enabled` field + gating)
- Create: `src/kel/skills/authoring/app.py` (`build_author` factory)
- Test: `tests/test_realtime_options.py` (append)

**Interfaces:**
- Consumes: `Settings` (Task 1), `SkillAuthor` (Task 3), `GeminiCoder` (Task 4), `SkillStore` + `BUILTIN_TOOL_NAMES` (#1).
- Produces: `options.BUILD_SKILL_TOOL_NAME = "build_skill"`; `_BUILD_SKILL_TOOL` dict; `BUILD_SKILL_TOOL_NAME` added to `BUILTIN_TOOL_NAMES`; `RealtimeSessionOptions.skills_author_enabled: bool = False` (set from settings), and `tool_specs()` appends the tool when enabled. `kel.skills.authoring.app.build_author(settings) -> SkillAuthor | None` (None when disabled or no Gemini key).

- [ ] **Step 1: Write the failing option test**

Append to `tests/test_realtime_options.py`:

```python
def test_build_skill_tool_offered_only_when_authoring_enabled() -> None:
    on = Settings.from_mapping({"OPENAI_API_KEY": "k", "KEL_SKILLS_AUTHOR_ENABLED": "true"})
    off = Settings.from_mapping({"OPENAI_API_KEY": "k", "KEL_SKILLS_AUTHOR_ENABLED": "false"})

    on_names = {t["name"] for t in RealtimeSessionOptions.from_settings(on).tool_specs()}
    off_names = {t["name"] for t in RealtimeSessionOptions.from_settings(off).tool_specs()}

    assert "build_skill" in on_names
    assert "build_skill" not in off_names


def test_build_skill_is_a_reserved_builtin_name() -> None:
    from kel.realtime.options import BUILTIN_TOOL_NAMES

    assert "build_skill" in BUILTIN_TOOL_NAMES
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_options.py -q -k build_skill`
Expected: FAIL — `build_skill` not offered / not in `BUILTIN_TOOL_NAMES`.

- [ ] **Step 3: Add the tool to options**

In `src/kel/realtime/options.py`, near the other tool definitions add:

```python
BUILD_SKILL_TOOL_NAME = "build_skill"
_BUILD_SKILL_TOOL = {
    "type": "function",
    "name": BUILD_SKILL_TOOL_NAME,
    "description": (
        "Build YOURSELF a new skill to do something you cannot already do with your "
        "current tools. Call this whenever the user asks for something none of your "
        "tools cover - do not say you can't and do not ask permission. Give a clear "
        "one-line goal of what the skill should accomplish, including any specific "
        "values from the request. Building takes a few seconds; say a short holding "
        "line first, then report the result it gives back."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "A clear one-line description of what the new skill should do, "
                    "including the specific values from the user's request."
                ),
            }
        },
        "required": ["goal"],
    },
}
```

Add `BUILD_SKILL_TOOL_NAME` to the `BUILTIN_TOOL_NAMES` frozenset.

Add the field to `RealtimeSessionOptions` (after `body_enabled: bool = False`):

```python
    skills_author_enabled: bool = False
```

Set it in `from_settings(...)`:

```python
            skills_author_enabled=settings.skills_author_enabled,
```

Append it in `tool_specs()` (after the existing tool blocks, before `return tools`):

```python
        if self.skills_author_enabled:
            tools.append(_BUILD_SKILL_TOOL)
```

- [ ] **Step 4: Create the author factory**

Create `src/kel/skills/authoring/app.py`:

```python
"""Wire settings into a SkillAuthor (or None when authoring is off)."""

from __future__ import annotations

from pathlib import Path

from kel.config.settings import Settings
from kel.skills.authoring.author import SkillAuthor
from kel.skills.authoring.coder import GeminiCoder
from kel.skills.store import SkillStore


def build_author(settings: Settings) -> SkillAuthor | None:
    """Build the author, or return None when it's disabled or has no Gemini key."""
    if not settings.skills_author_enabled:
        return None
    if not settings.gemini_api_key:
        print("Skill authoring is off (needs GEMINI_API_KEY); continuing without it.")
        return None
    from kel.realtime.options import BUILTIN_TOOL_NAMES

    root = Path(settings.skills_path).expanduser()
    coder = GeminiCoder(api_key=settings.gemini_api_key, model=settings.coder_model)
    store = SkillStore(root, reserved_names=BUILTIN_TOOL_NAMES)
    return SkillAuthor(
        coder=coder,
        store=store,
        root=root,
        reserved_names=BUILTIN_TOOL_NAMES,
        max_attempts=settings.skills_author_max_attempts,
        timeout=settings.skills_timeout_seconds,
        allow_pip=settings.skills_author_allow_pip,
    )
```

- [ ] **Step 5: Run the option tests to verify they pass**

Run: `uv run pytest tests/test_realtime_options.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src/kel/realtime/options.py src/kel/skills/authoring/app.py tests/test_realtime_options.py
git add src/kel/realtime/options.py src/kel/skills/authoring/app.py tests/test_realtime_options.py
git commit -m "feat(authoring): add the build_skill tool and author factory"
```

---

### Task 6: OpenAI session — dispatch `build_skill`

**Files:**
- Modify: `src/kel/realtime/session.py`
- Test: `tests/test_realtime_session.py` (append)

**Interfaces:**
- Consumes: `SkillAuthor` (Task 3), `BUILD_SKILL_TOOL_NAME` (Task 5).
- Produces: `RealtimeVoiceSession(..., author: SkillAuthor | None = None)`. A `build_skill` tool call runs `author.build(goal)` in a thread and replies with `outcome.output`; missing author or empty goal → a safe "can't build right now" reply.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_realtime_session.py` (imports go in the top block):

```python
class FakeAuthor:
    def __init__(self, output: str = "built and ran it: done") -> None:
        self.goals: list[str] = []
        self._output = output

    def build(self, goal: str):
        from kel.skills.authoring.contracts import AuthorOutcome

        self.goals.append(goal)
        return AuthorOutcome(ok=True, output=self._output, skill_name="new_skill", attempts=1)


def build_author_session(author, events: list[object]) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
        skills_author_enabled=True,
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        author=author,
    )


def test_build_skill_tool_runs_the_author_and_returns_its_output() -> None:
    author = FakeAuthor(output="built qr_code and ran it: saved /tmp/x.png")
    session = build_author_session(author, [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("build_skill", {"goal": "make a qr code"}), connection))

    assert author.goals == ["make a qr code"]
    assert "saved /tmp/x.png" in items.created[0]["output"]
    assert responses.count == 1


def test_build_skill_without_an_author_replies_safely() -> None:
    session = build_author_session(None, [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("build_skill", {"goal": "x"}), connection))

    assert "build" in items.created[0]["output"].lower()
    assert responses.count == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_session.py -q -k build_skill`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'author'`.

- [ ] **Step 3: Wire the author into the session**

In `src/kel/realtime/session.py`:

Add `BUILD_SKILL_TOOL_NAME` to the existing `from kel.realtime.options import (...)` list, and add the import:

```python
from kel.skills.authoring.author import SkillAuthor
```

Add the constructor param (after `skills_timeout: float = 20.0,`):

```python
        author: SkillAuthor | None = None,
```

Store it (near `self._skills = skills`):

```python
        self._author = author
```

In `_handle_tool_call`, add an `elif` BEFORE the final `else:` skill branch:

```python
        elif name == BUILD_SKILL_TOOL_NAME:
            await self._build_skill(event, connection)
```

Add the method (near `_run_skill`):

```python
    async def _build_skill(self, event: Any, connection: Any) -> None:
        """Have Kel author a new skill for a goal, then report the result."""
        goal = self._tool_argument(event, "goal")
        if self._author is None or not goal:
            await self._reply_to_tool(
                connection, event.call_id, "I can't build new skills right now."
            )
            return
        self._emit("acted", f"Building a skill: {goal}")
        outcome = await asyncio.to_thread(self._author.build, goal)
        await self._reply_to_tool(connection, event.call_id, outcome.output)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_realtime_session.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/realtime/session.py tests/test_realtime_session.py
git add src/kel/realtime/session.py tests/test_realtime_session.py
git commit -m "feat(authoring): dispatch build_skill in the OpenAI session"
```

---

### Task 7: Gemini session dispatch + app wiring

**Files:**
- Modify: `src/kel/realtime/gemini_session.py`
- Modify: `src/kel/realtime/app.py`
- Test: `tests/test_gemini_session.py` (append)

**Interfaces:**
- Consumes: `SkillAuthor` (Task 3), `BUILD_SKILL_TOOL_NAME` (Task 5), `build_author` (Task 5).
- Produces: `GeminiVoiceSession(..., author: SkillAuthor | None = None)` dispatching `build_skill` to the author (mirroring the OpenAI session). `build_realtime_session` builds the author via `build_author(settings)` and adds `author=author` to the `shared` dict passed to both sessions; `options.skills_author_enabled` follows settings.

- [ ] **Step 1: Write the failing Gemini test**

Append to `tests/test_gemini_session.py` (top-block imports):

```python
def test_gemini_build_skill_tool_runs_the_author() -> None:
    import asyncio
    from types import SimpleNamespace

    from kel.realtime.gemini_session import GeminiVoiceSession
    from kel.realtime.options import RealtimeSessionOptions
    from kel.config.settings import Settings
    from kel.skills.authoring.contracts import AuthorOutcome

    class FakeAuthor:
        def __init__(self) -> None:
            self.goals: list[str] = []

        def build(self, goal: str):
            self.goals.append(goal)
            return AuthorOutcome(ok=True, output="built and ran it: done", attempts=1)

    author = FakeAuthor()
    options = RealtimeSessionOptions.from_settings(Settings.from_mapping({"OPENAI_API_KEY": "k"}))
    session = GeminiVoiceSession(
        api_key="unused",
        model="test-model",
        voice="Leda",
        instructions="Be Kel.",
        options=options,
        microphone=SimpleNamespace(),
        speaker=SimpleNamespace(),
        on_event=lambda _e: None,
        client=SimpleNamespace(),
        author=author,
    )

    output, image = asyncio.run(session._run_tool("build_skill", {"goal": "make a qr code"}))

    assert author.goals == ["make a qr code"]
    assert "done" in output
    assert image is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_gemini_session.py -q -k build_skill`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'author'`.

- [ ] **Step 3: Wire the author into the Gemini session**

In `src/kel/realtime/gemini_session.py`:

Add `BUILD_SKILL_TOOL_NAME` to the `from kel.realtime.options import (...)` list, and add:

```python
from kel.skills.authoring.author import SkillAuthor
```

Add the constructor param (after `skills_timeout: float = 20.0,`) and store it:

```python
        author: SkillAuthor | None = None,
```
```python
        self._author = author
```

In `_run_tool`, add BEFORE the skill fallthrough (the `skill = self._skills.get(name) ...` block):

```python
        if name == BUILD_SKILL_TOOL_NAME:
            return await self._build_skill(self._arg(args, "goal")), None
```

Add the method:

```python
    async def _build_skill(self, goal: str) -> str:
        if self._author is None or not goal:
            return "I can't build new skills right now."
        self._emit("acted", f"Building a skill: {goal}")
        outcome = await asyncio.to_thread(self._author.build, goal)
        return outcome.output
```

- [ ] **Step 4: Wire the author into `build_realtime_session`**

In `src/kel/realtime/app.py`, after the `skills = None` / `SkillStore` block, add:

```python
    from kel.skills.authoring.app import build_author

    author = build_author(settings)
```

Add to the `shared` dict (after `skills_timeout=settings.skills_timeout_seconds,`):

```python
        author=author,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_gemini_session.py -q`
Expected: PASS.

- [ ] **Step 6: Verify the whole suite**

Run: `uv run pytest -q`
Expected: PASS (both session constructors now accept `author`; `shared` carries it).

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check src/kel/realtime/gemini_session.py src/kel/realtime/app.py tests/test_gemini_session.py
git add src/kel/realtime/gemini_session.py src/kel/realtime/app.py tests/test_gemini_session.py
git commit -m "feat(authoring): dispatch build_skill in Gemini and wire the author into the app"
```

---

### Task 8: Decisive personality

**Files:**
- Modify: `src/kel/prompts/kel_personality.py`
- Test: `tests/test_realtime_options.py` (append — it already tests the prompt) or `tests/test_prompt.py`

**Interfaces:**
- Produces: added guidance in `build_kel_realtime_instructions` so Kel acts decisively and reaches for `build_skill` herself.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_realtime_options.py`:

```python
def test_realtime_prompt_tells_kel_to_build_skills_and_be_decisive() -> None:
    prompt = build_kel_realtime_instructions("Kel").lower()

    assert "build_skill" in prompt
    assert "without asking" in prompt or "don't ask" in prompt or "do not ask" in prompt
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_realtime_options.py -q -k decisive`
Expected: FAIL — the cues aren't in the prompt yet.

- [ ] **Step 3: Add the guidance**

In `src/kel/prompts/kel_personality.py`, inside `build_kel_realtime_instructions`, append a paragraph to the `base` string (before the `if environment:` block):

```python
    base += """

You can also BUILD YOURSELF NEW SKILLS. When the user asks for something none of
your current tools or skills can do, do NOT say you can't and do NOT ask permission
- call `build_skill` yourself with a clear one-line goal that includes the specific
details from their request. Building takes a few seconds, so say a short holding
line first ("give me a sec, putting that together"), then tell them the result it
hands back. Be decisive in general: when a request is doable with reasonable
assumptions, make them and act instead of asking a pile of clarifying questions -
only ask when you genuinely cannot proceed."""
```

(Insert this right after the memory paragraph and before `if environment:`.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_realtime_options.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/kel/prompts/kel_personality.py tests/test_realtime_options.py
git add src/kel/prompts/kel_personality.py tests/test_realtime_options.py
git commit -m "feat(authoring): prompt Kel to build skills herself and act decisively"
```

---

## Final verification

- [ ] Full suite: `uv run pytest -q` — expect all green.
- [ ] Lint: `uv run ruff check src/kel/skills src/kel/realtime tests` — expect clean.
- [ ] **Manual end-to-end smoke (real Gemini, needs `GEMINI_API_KEY`):**

```bash
uv run python -c "from kel.config.settings import Settings; from kel.skills.authoring.app import build_author; a=build_author(Settings.from_env()); print(a.build('generate a QR code PNG for the text hello and save it to /tmp/hello.png').output)"
```

Expect Gemini to author a skill, the loop to install `qrcode` if needed, run it, and print the saved path — with the new skill left armed in `~/.kel/skills/`. Then confirm `uv run kel-skills list` shows it armed.

## Notes for the implementer

- **The core authoring modules never import `kel.realtime`.** Reserved built-in names reach `SkillAuthor` via the injected `reserved_names` param. Only `authoring/app.py` and `realtime/app.py` bridge the two, and `authoring/app.py` imports `BUILTIN_TOOL_NAMES` *inside* `build_author` to keep module import order clean.
- **Most author tests inject a fake `run`/`install`/coder** for determinism; exactly one test (`test_build_end_to_end_with_the_real_runner`) exercises the real #1 subprocess for a success case. Do not add real-network or real-pip tests.
- **The Gemini and OpenAI sessions mirror each other** — keep the `build_skill` hooks parallel (same param name `author`, same holding-line emit, same safe fallback).
- The `created_at` manifest field is written as `""` by the author (kept deterministic); it's cosmetic metadata the store tolerates.
