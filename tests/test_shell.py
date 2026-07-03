"""The shell runner executes commands, with a tripwire for catastrophic ones."""

from __future__ import annotations

from kel.system.shell import ShellRunner, is_dangerous


def test_detects_catastrophic_commands() -> None:
    assert is_dangerous("rm -rf /")
    assert is_dangerous("sudo rm -rf ~")
    assert is_dangerous("mkfs.ext4 /dev/sda")
    assert is_dangerous("dd if=/dev/zero of=/dev/sda")


def test_allows_ordinary_commands() -> None:
    assert not is_dangerous("ls -la")
    assert not is_dangerous("echo hello")
    assert not is_dangerous("rm -rf /tmp/cache")  # specific path, not root/home


def test_runner_executes_a_normal_command() -> None:
    calls: list[str] = []
    runner = ShellRunner(runner=lambda cmd, _timeout: calls.append(cmd) or "the output")

    result = runner.run("ls -la")

    assert calls == ["ls -la"]
    assert "the output" in result


def test_runner_blocks_a_catastrophic_command_by_default() -> None:
    calls: list[str] = []
    runner = ShellRunner(runner=lambda cmd, _timeout: calls.append(cmd) or "ran")

    result = runner.run("rm -rf /")

    assert calls == []  # never executed
    assert "refus" in result.lower()


def test_runner_can_be_told_to_allow_catastrophic_commands() -> None:
    calls: list[str] = []
    runner = ShellRunner(
        block_dangerous=False, runner=lambda cmd, _timeout: calls.append(cmd) or "ran"
    )

    runner.run("rm -rf /")

    assert calls == ["rm -rf /"]
