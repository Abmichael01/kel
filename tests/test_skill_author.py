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


def a_draft(
    name: str = "greet", code: str = "def run(who):\n    return f'hi {who}'\n"
) -> DraftSkill:
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
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output=f"hi {args['who']}"),
    )

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
    results = [
        SkillResult(ok=False, output="skill 'greet' failed: boom"),
        SkillResult(ok=True, output="hi Kel"),
    ]
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: results.pop(0),
    )

    outcome = author.build("say hi")

    assert outcome.ok is True
    assert outcome.attempts == 2
    # The second draft was asked for WITH the first failure as feedback.
    assert coder.feedbacks == [None, "skill 'greet' failed: boom"]


def test_build_gives_up_after_max_attempts_and_removes_the_folder(tmp_path: Path) -> None:
    coder = ScriptedCoder(
        [a_draft(name="greet"), a_draft(name="greet"), a_draft(name="greet")]
    )
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(
            ok=False, output="skill 'greet' failed: nope"
        ),
        max_attempts=3,
    )

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
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel"),
    )

    outcome = author.build("say hi")

    assert outcome.ok is True
    assert outcome.attempts == 2  # the raised draft counted as attempt 1


def test_build_installs_a_missing_dependency_then_reruns(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft()])
    results = [
        SkillResult(
            ok=False,
            output="skill 'greet' failed: ModuleNotFoundError: No module named 'qrcode'",
        ),
        SkillResult(ok=True, output="hi Kel"),
    ]
    installed: list[str] = []
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: results.pop(0),
        install=lambda module: (installed.append(module) or True),
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
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel"),
    )

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


def _write_minimal_skill(root: Path, name: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "skill.py").write_text("def run():\n    return 'x'\n")
    (directory / "skill.json").write_text(
        json.dumps({"name": name, "parameters": {"type": "object", "properties": {}}})
    )


def test_build_rejects_an_empty_name_without_deleting_the_root(tmp_path: Path) -> None:
    # A pre-existing, unrelated skill must survive an empty-name draft: if the empty
    # name were allowed through, `directory = root / ""` == root, and the failed-attempt
    # cleanup would rmtree the WHOLE skills root, taking "keep" down with it.
    _write_minimal_skill(tmp_path, "keep")
    coder = ScriptedCoder([a_draft(name="")])
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel"),
        max_attempts=1,
    )

    outcome = author.build("say hi")

    assert outcome.ok is False
    assert (tmp_path / "keep" / "skill.py").exists()  # root not wiped
    assert (tmp_path / "keep" / "skill.json").exists()
    assert not (tmp_path / "skill.py").exists()  # nothing stray written into the root
    assert not (tmp_path / "skill.json").exists()


def test_build_rejects_a_non_snake_case_name_then_succeeds(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft(name="MakeQR"), a_draft(name="make_qr")])
    results = [SkillResult(ok=True, output="hi Kel")]
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: results[0],
    )

    outcome = author.build("make a qr code")

    assert outcome.ok is True
    assert outcome.skill_name == "make_qr"
    assert outcome.attempts == 2
    assert len(coder.feedbacks) == 2
    assert "snake_case" in coder.feedbacks[1]


def test_build_rejects_a_path_traversal_name(tmp_path: Path) -> None:
    coder = ScriptedCoder([a_draft(name="../evil")])
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel"),
        max_attempts=1,
    )

    outcome = author.build("say hi")

    assert outcome.ok is False
    assert not (tmp_path.parent / "evil").exists()


def test_build_bails_early_on_a_service_error(tmp_path: Path) -> None:
    class AlwaysRaisingCoder:
        def __init__(self) -> None:
            self.calls = 0

        def draft(self, goal: str, feedback: str | None = None) -> DraftSkill:
            self.calls += 1
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    coder = AlwaysRaisingCoder()
    author = SkillAuthor(
        coder=coder,
        store=make_store(tmp_path),
        root=tmp_path,
        run=lambda skill, args, *, timeout: SkillResult(ok=True, output="hi Kel"),
        max_attempts=4,
    )

    outcome = author.build("say hi")

    assert outcome.ok is False
    assert coder.calls == 1  # did NOT burn all 4 attempts hammering the service
    assert "429" in outcome.output or "skill-builder service" in outcome.output
