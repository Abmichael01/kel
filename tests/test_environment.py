"""The environment summary tells Kel exactly what machine it's running on."""

from __future__ import annotations

from kel.system.environment import format_environment


def test_format_environment_includes_the_key_facts() -> None:
    info = {
        "os": "Linux",
        "distro": "CachyOS",
        "release": "7.0.12",
        "arch": "x86_64",
        "hostname": "box",
        "user": "urkel",
        "shell": "/usr/bin/fish",
        "home": "/home/urkel",
        "cwd": "/home/urkel/proj",
        "python": "3.13",
    }

    text = format_environment(info)

    assert "Linux" in text
    assert "CachyOS" in text
    assert "/usr/bin/fish" in text
    assert "urkel" in text
    assert "x86_64" in text


def test_format_environment_handles_missing_distro() -> None:
    info = {"os": "Darwin", "release": "23.0", "arch": "arm64", "shell": "/bin/zsh"}

    text = format_environment(info)

    assert "Darwin" in text
    assert "/bin/zsh" in text
