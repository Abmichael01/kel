"""Run a skill in an isolated subprocess with a timeout, failures mapped to text.

The subprocess is for stability, not security: a broken or hung skill cannot wedge
the live voice session, and a timeout kills it. Skill code still runs with full
user privileges, exactly like the shell tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from kel.skills.contracts import Skill, SkillResult


def run_skill(
    skill: Skill,
    args: dict[str, Any],
    *,
    timeout: float,
    python: str | None = None,
) -> SkillResult:
    """Run one skill and return its result, never raising for a bad skill."""
    interpreter = python or sys.executable
    try:
        proc = subprocess.run(
            [interpreter, "-m", "kel.skills.runner", str(skill.directory)],
            input=json.dumps(args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SkillResult(ok=False, output=f"skill '{skill.name}' timed out after {int(timeout)}s")
    if proc.returncode == 0:
        return SkillResult(ok=True, output=proc.stdout)
    lines = [line for line in proc.stderr.strip().splitlines() if line.strip()]
    reason = lines[-1] if lines else "unknown error"
    return SkillResult(ok=False, output=f"skill '{skill.name}' failed: {reason}")
