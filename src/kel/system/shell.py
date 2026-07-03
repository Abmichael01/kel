"""Run shell commands for Kel, with a basic tripwire for catastrophic ones.

The user chose unrestricted execution, so any command runs. The only guard is a
small, disableable check for a handful of almost-never-intentional, irreversible
commands (wiping the disk or root), because a mis-heard voice command should not
be able to destroy the machine.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable

_DANGEROUS = [
    re.compile(r"\brm\b.*\s-[a-z]*[rf][a-z]*\s+/(\s|$|\*)"),  # rm -rf /  or  /*
    re.compile(r"\brm\b.*\s-[a-z]*[rf][a-z]*\s+~(\s|$|/)"),  # rm -rf ~
    re.compile(r"\bmkfs"),  # formatting a filesystem
    re.compile(r"\bdd\b.*\bof=/dev/"),  # writing straight to a device
    re.compile(r">\s*/dev/sd"),  # clobbering a disk device
    re.compile(r":\s*\(\s*\)\s*\{"),  # classic fork bomb
]


def is_dangerous(command: str) -> bool:
    """Return True for a small set of catastrophic, irreversible commands."""
    return any(pattern.search(command) for pattern in _DANGEROUS)


class ShellRunner:
    """Execute shell commands, capturing output, with an optional safety tripwire."""

    def __init__(
        self,
        *,
        timeout: int = 20,
        block_dangerous: bool = True,
        runner: Callable[[str, int], str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._block_dangerous = block_dangerous
        self._runner = runner or self._run_subprocess

    def run(self, command: str) -> str:
        """Run one command and return its combined output (or a refusal)."""
        command = command.strip()
        if not command:
            return "No command was given."
        if self._block_dangerous and is_dangerous(command):
            return (
                "Refused: that looks like a destructive, irreversible command. "
                "(Set KEL_SHELL_BLOCK_DANGEROUS=false to allow it.)"
            )
        return self._runner(command, self._timeout)

    def _run_subprocess(self, command: str, timeout: int) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"The command was still running after {timeout}s and was stopped."
        output = f"{result.stdout}{result.stderr}".strip()
        if not output:
            return f"Done (exit code {result.returncode})."
        return output[:2000]
