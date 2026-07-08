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
