"""Run one skill in its own process: JSON args on stdin, string result on stdout.

Invoked as ``python -m kel.skills.runner <skill_dir>``. It imports the skill's
``skill.py`` by path, so only that file's own imports load here — nothing else of
Kel is pulled in. Any exception the skill raises propagates and exits non-zero.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: python -m kel.skills.runner <skill_dir>")
    skill_dir = Path(args[0])
    raw = sys.stdin.read()
    params = json.loads(raw) if raw.strip() else {}

    spec = importlib.util.spec_from_file_location("kel_active_skill", skill_dir / "skill.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load a skill at {skill_dir}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.run(**params)
    sys.stdout.write(str(result))


if __name__ == "__main__":
    main()
