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
