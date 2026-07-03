"""PipeWire echo cancellation is configured without leaking into audio logic."""

from __future__ import annotations

import subprocess

from kel.realtime.echo_cancel import PulseEchoCanceller


class ScriptedRunner:
    def __init__(self, *, fail_on: str = "") -> None:
        self.commands: list[list[str]] = []
        self._fail_on = fail_on

    def __call__(self, argv: list[str]) -> str:
        self.commands.append(argv)
        if self._fail_on and self._fail_on in argv:
            raise subprocess.CalledProcessError(1, argv)
        if argv[1] == "get-default-source":
            return "physical-mic\n"
        if argv[1] == "get-default-sink":
            return "physical-speaker\n"
        if argv[1] == "load-module":
            return "42\n"
        return ""


def test_start_routes_audio_through_the_echo_cancel_nodes() -> None:
    runner = ScriptedRunner()
    echo = PulseEchoCanceller(runner=runner, which=lambda _name: "/usr/bin/pactl")

    assert echo.start() is True

    assert runner.commands[2][:2] == ["pactl", "load-module"]
    assert runner.commands[3] == [
        "pactl",
        "set-default-source",
        "kel_echo_cancel_source",
    ]
    assert runner.commands[4] == [
        "pactl",
        "set-default-sink",
        "kel_echo_cancel_sink",
    ]


def test_stop_restores_defaults_and_unloads_the_module() -> None:
    runner = ScriptedRunner()
    echo = PulseEchoCanceller(runner=runner, which=lambda _name: "/usr/bin/pactl")
    echo.start()

    echo.stop()

    assert runner.commands[-3:] == [
        ["pactl", "set-default-source", "physical-mic"],
        ["pactl", "set-default-sink", "physical-speaker"],
        ["pactl", "unload-module", "42"],
    ]


def test_start_failure_cleans_up_and_reports_false() -> None:
    runner = ScriptedRunner(fail_on="set-default-sink")
    echo = PulseEchoCanceller(runner=runner, which=lambda _name: "/usr/bin/pactl")

    assert echo.start() is False
    assert ["pactl", "unload-module", "42"] in runner.commands


def test_missing_pactl_reports_false_without_running_commands() -> None:
    runner = ScriptedRunner()
    echo = PulseEchoCanceller(runner=runner, which=lambda _name: None)

    assert echo.start() is False
    assert runner.commands == []
