"""Parse direct voice-dictation transcripts into safe keyboard actions."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EXIT_PHRASES = {
    "exit typing mode",
    "stop typing",
    "stop typing mode",
    "typing mode off",
}
_TRAILING_ENTER = re.compile(
    r"(?:^|\s)(?:press\s+)?enter[.!?]*\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DictationCommand:
    """Text and allowlisted control actions extracted from one transcript."""

    text: str = ""
    press_enter: bool = False
    press_space: bool = False
    stop: bool = False


def parse_dictation(transcript: str) -> DictationCommand:
    """Treat exit phrases and a final `enter` as commands, not dictated text."""
    text = transcript.strip()
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
    if normalized in _EXIT_PHRASES:
        return DictationCommand(stop=True)
    if normalized == "space":
        return DictationCommand(press_space=True)
    if normalized in {"new line", "newline"}:
        return DictationCommand(press_enter=True)

    enter_match = _TRAILING_ENTER.search(text)
    if enter_match is None:
        return DictationCommand(text=text)
    return DictationCommand(
        text=text[: enter_match.start()].rstrip(),
        press_enter=True,
    )
