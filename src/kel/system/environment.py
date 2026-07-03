"""Describe the computer Kel is running on, so it runs the right commands."""

from __future__ import annotations

import contextlib
import getpass
import os
import platform
import socket
from pathlib import Path


def collect_environment() -> dict[str, str]:
    """Gather facts about the current machine."""
    info: dict[str, str] = {
        "os": platform.system(),
        "release": platform.release(),
        "arch": platform.machine(),
        "hostname": socket.gethostname(),
        "user": _current_user(),
        "shell": os.environ.get("SHELL", ""),
        "home": str(Path.home()),
        "cwd": os.getcwd(),
        "python": platform.python_version(),
    }
    if info["os"] == "Linux":
        with contextlib.suppress(OSError):
            release = platform.freedesktop_os_release()
            info["distro"] = release.get("PRETTY_NAME") or release.get("NAME", "")
    return {key: value for key, value in info.items() if value}


def format_environment(info: dict[str, str]) -> str:
    """Render the machine facts as a system-context paragraph for the prompt."""
    os_line = info.get("os", "")
    if info.get("distro"):
        os_line += f" ({info['distro']})"
    if info.get("release"):
        os_line += f", kernel {info['release']}"
    if info.get("arch"):
        os_line += f", {info['arch']}"

    lines = [
        "System context — the computer you are actually running on right now:",
        f"- OS: {os_line}",
        f"- Shell: {info.get('shell', 'unknown')}",
        f"- User: {info.get('user', 'unknown')} (home {info.get('home', '?')})",
        f"- Working directory: {info.get('cwd', '?')}",
    ]
    lines.append(
        "Before running commands, use commands, paths, and package managers that fit "
        "THIS exact OS and shell. Don't assume macOS on Linux or vice versa."
    )
    return "\n".join(lines)


def describe_environment() -> str:
    """Return the system-context paragraph for the live machine."""
    return format_environment(collect_environment())


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - fall back to env if the OS lookup fails
        return os.environ.get("USER", "")
