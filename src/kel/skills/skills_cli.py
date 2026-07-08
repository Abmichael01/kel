"""Manage Kel's skills from the terminal: list, arm, disarm, run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kel.config.settings import Settings
from kel.realtime.options import BUILTIN_TOOL_NAMES
from kel.skills.executor import run_skill
from kel.skills.store import SkillStore


def _store(settings: Settings) -> SkillStore:
    root = Path(settings.skills_path).expanduser()
    return SkillStore(root, reserved_names=BUILTIN_TOOL_NAMES)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage Kel's skills.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list every skill and whether it is armed")
    arm = sub.add_parser("arm", help="turn a skill on")
    arm.add_argument("name")
    disarm = sub.add_parser("disarm", help="turn a skill off")
    disarm.add_argument("name")
    run = sub.add_parser("run", help="run a skill once with JSON args")
    run.add_argument("name")
    run.add_argument("args", nargs="?", default="{}")
    parsed = parser.parse_args(argv)

    settings = Settings.from_env()
    store = _store(settings)

    if parsed.command == "list":
        skills = store.all()
        if not skills:
            print("No skills yet.")
        for skill in skills:
            state = "on " if skill.enabled else "off"
            print(f"[{state}] {skill.name} — {skill.description}")
        return
    if parsed.command == "arm":
        print("armed" if store.arm(parsed.name) else f"no skill named {parsed.name}")
        return
    if parsed.command == "disarm":
        print("disarmed" if store.disarm(parsed.name) else f"no skill named {parsed.name}")
        return
    if parsed.command == "run":
        skill = store.get(parsed.name)
        if skill is None:
            print(f"no skill named {parsed.name}")
            return
        result = run_skill(skill, json.loads(parsed.args), timeout=settings.skills_timeout_seconds)
        print(result.output)


if __name__ == "__main__":
    main()
