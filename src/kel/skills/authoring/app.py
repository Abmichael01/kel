"""Wire settings into a SkillAuthor (or None when authoring is off)."""

from __future__ import annotations

from pathlib import Path

from kel.config.settings import Settings
from kel.skills.authoring.author import SkillAuthor
from kel.skills.authoring.coder import GeminiCoder
from kel.skills.store import SkillStore


def build_author(settings: Settings) -> SkillAuthor | None:
    """Build the author, or return None when it's disabled or has no Gemini key."""
    if not settings.skills_author_enabled:
        return None
    if not settings.gemini_api_key:
        print("Skill authoring is off (needs GEMINI_API_KEY); continuing without it.")
        return None
    from kel.realtime.options import BUILTIN_TOOL_NAMES

    root = Path(settings.skills_path).expanduser()
    coder = GeminiCoder(api_key=settings.gemini_api_key, model=settings.coder_model)
    store = SkillStore(root, reserved_names=BUILTIN_TOOL_NAMES)
    return SkillAuthor(
        coder=coder,
        store=store,
        root=root,
        reserved_names=BUILTIN_TOOL_NAMES,
        max_attempts=settings.skills_author_max_attempts,
        timeout=settings.skills_timeout_seconds,
        allow_pip=settings.skills_author_allow_pip,
    )
