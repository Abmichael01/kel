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
