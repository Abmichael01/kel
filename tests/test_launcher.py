"""The launcher runs long-running things in their own terminal window."""

from __future__ import annotations

from kel.system.launcher import TerminalLauncher


def test_launch_runs_command_in_the_configured_terminal() -> None:
    spawned: list[list[str]] = []
    launcher = TerminalLauncher(terminal="konsole -e", spawner=spawned.append)

    result = launcher.launch("htop")

    assert spawned == [["konsole", "-e", "bash", "-c", "htop; exec bash"]]
    assert "terminal" in result.lower()


def test_launch_autodetects_an_available_terminal() -> None:
    spawned: list[list[str]] = []
    launcher = TerminalLauncher(spawner=spawned.append, which=lambda name: name == "alacritty")

    launcher.launch("npm run dev")

    assert spawned[0][:2] == ["alacritty", "-e"]
    assert spawned[0][-1] == "npm run dev; exec bash"


def test_launch_falls_back_to_background_without_a_terminal() -> None:
    spawned: list[list[str]] = []
    launcher = TerminalLauncher(spawner=spawned.append, which=lambda _name: None)

    result = launcher.launch("python server.py")

    assert spawned == [["setsid", "bash", "-c", "python server.py"]]
    assert "background" in result.lower()


def test_launch_blocks_dangerous_commands() -> None:
    spawned: list[list[str]] = []
    launcher = TerminalLauncher(terminal="xterm -e", spawner=spawned.append)

    result = launcher.launch("rm -rf /")

    assert spawned == []
    assert "refus" in result.lower()
