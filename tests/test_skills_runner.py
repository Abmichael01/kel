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
